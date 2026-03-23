"""
Smart Miner — Uses Google Gemini to play Werewolf intelligently.

Instead of random action selection, this miner:
1. Receives game context + system prompt from the validator
2. Calls Google Gemini API with the full game context
3. Parses the AI response to select the best action

Usage:
    python neurons/smart_miner.py \
        --wallet.name miner1 --wallet.hotkey default \
        --subtensor.network test --netuid 44

Requires GOOGLE_API_KEY_BITTENSOR in .env
"""

import os
import re
import time
import json
import typing
import bittensor as bt

from mentiss.base.miner import BaseMinerNeuron
from mentiss.protocol import WerewolfSynapse

# Load .env if present
_env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
if os.path.exists(_env_path):
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY_BITTENSOR", "")
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_API_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}"
    f":generateContent?key={GOOGLE_API_KEY}"
)


def _call_gemini(system_prompt: str, user_message: str) -> str:
    """Call Google Gemini API and return the text response."""
    import httpx

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_message}],
            }
        ],
        "systemInstruction": {
            "parts": [{"text": system_prompt}],
        },
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 2048,
        },
    }

    try:
        response = httpx.post(
            GEMINI_API_URL,
            json=payload,
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                return parts[0].get("text", "")
        bt.logging.warning(f"Gemini returned empty response: {data}")
        return ""
    except Exception as e:
        bt.logging.error(f"Gemini API call failed: {e}")
        return ""


def _parse_action_from_response(
    ai_text: str, options: list
) -> list:
    """Parse the AI's natural language response into structured action.

    The AI response may contain:
    - Direct player position references (e.g., "I choose player 3", "kill seat 2")
    - Player name references (e.g., "I vote for Alice")
    - Yes/No decisions (e.g., "I choose to use the antidote")
    - Speech text

    We try to map these to the available options.
    """
    responses = []
    ai_lower = ai_text.lower()

    for option in options:
        tag = option.get("tag", "")
        possible_values = option.get("possibleValues", [])
        db_action = option.get("dbAction", "")

        if not possible_values:
            continue

        # For speech/discussion actions, just pass the AI text directly
        if tag in ("speaking", "speech", "discuss"):
            # Extract just the speech part if the AI included other content
            responses.append({"tag": tag, "value": ai_text[:500]})
            continue

        # For thinking/memory, pass the AI reasoning
        if tag in ("thinking", "memory", "inner_thought"):
            responses.append({"tag": tag, "value": ai_text[:500]})
            continue

        # For actions with numeric values (typically player positions)
        numeric_values = [v for v in possible_values if isinstance(v, (int, float))]
        string_values = [v for v in possible_values if isinstance(v, str)]

        if numeric_values:
            # Try to find a number reference in the AI response
            # Look for patterns like "player 3", "seat 2", "position 5", or just bare numbers
            number_patterns = [
                r'player\s*(\d+)',
                r'seat\s*(\d+)',
                r'position\s*(\d+)',
                r'#(\d+)',
                r'choose\s*(\d+)',
                r'vote.*?(\d+)',
                r'kill.*?(\d+)',
                r'target.*?(\d+)',
                r'eliminate.*?(\d+)',
            ]

            chosen = None
            for pattern in number_patterns:
                match = re.search(pattern, ai_lower)
                if match:
                    num = int(match.group(1))
                    if num in numeric_values:
                        chosen = num
                        break

            # If no pattern matched, try to find any mentioned number that's a valid option
            if chosen is None:
                for num in numeric_values:
                    if str(num) in ai_text:
                        chosen = num
                        break

            # Fallback: pick the first option
            if chosen is None:
                chosen = numeric_values[0]
                bt.logging.warning(
                    f"Could not parse number from AI response for tag '{tag}', "
                    f"defaulting to {chosen}"
                )

            responses.append({"tag": tag, "value": chosen})

        elif string_values:
            # For string options (yes/no, specific choices)
            chosen = None

            # Check for yes/no
            yes_vals = [v for v in string_values if v.lower() in ("yes", "true", "use")]
            no_vals = [v for v in string_values if v.lower() in ("no", "false", "skip", "pass")]

            if yes_vals and no_vals:
                # Binary choice
                if any(w in ai_lower for w in ("yes", "use", "save", "protect", "antidote", "cure")):
                    chosen = yes_vals[0]
                elif any(w in ai_lower for w in ("no", "skip", "pass", "don't", "do not")):
                    chosen = no_vals[0]

            # Try exact match
            if chosen is None:
                for val in string_values:
                    if val.lower() in ai_lower:
                        chosen = val
                        break

            # Fallback
            if chosen is None:
                chosen = string_values[0]
                bt.logging.warning(
                    f"Could not parse string choice from AI response for tag '{tag}', "
                    f"defaulting to {chosen}"
                )

            responses.append({"tag": tag, "value": chosen})

    return responses


class SmartMiner(BaseMinerNeuron):
    """
    AI-powered Werewolf miner using Google Gemini.

    Receives game context from the validator and uses Gemini to make
    strategic decisions rather than random action selection.
    """

    def __init__(self, config=None):
        super(SmartMiner, self).__init__(config=config)

        if not GOOGLE_API_KEY:
            bt.logging.error(
                "GOOGLE_API_KEY_BITTENSOR not set! "
                "Smart miner requires a Google API key to call Gemini."
            )

    async def forward(self, synapse: WerewolfSynapse) -> WerewolfSynapse:
        bt.logging.info(
            f"Game {synapse.game_id} | role={synapse.role} | "
            f"phase={synapse.phase} | sub_phase={synapse.sub_phase} | "
            f"round={synapse.round_number}"
        )

        try:
            pending = json.loads(synapse.pending_action) if synapse.pending_action else {}
        except json.JSONDecodeError:
            bt.logging.error("Failed to parse pending_action")
            synapse.response = None
            return synapse

        options = pending.get("options", [])
        prompt = pending.get("prompt", "")

        if not options:
            bt.logging.warning("No options available")
            synapse.response = None
            return synapse

        # Build the context for Gemini
        try:
            context = json.loads(synapse.game_context) if synapse.game_context else {}
        except json.JSONDecodeError:
            context = {}

        human_log = context.get("humanLog", "")

        # Build the user message:
        # 1. The player's first-person game log (full history)
        # 2. The current action prompt and available options
        options_desc = "\n".join(
            f"  - {opt.get('tag', '?')}: possible values = {opt.get('possibleValues', [])}"
            for opt in options
        )

        user_message = (
            f"=== YOUR GAME HISTORY ===\n{human_log}\n\n"
            f"=== CURRENT ACTION ===\n{prompt}\n\n"
            f"=== AVAILABLE OPTIONS ===\n{options_desc}\n\n"
            f"You are playing as: {synapse.role}\n"
            f"Current phase: {synapse.phase} / {synapse.sub_phase}\n"
            f"Round: {synapse.round_number}\n\n"
            f"Based on your role, the game history, and available options, "
            f"decide what to do. Be strategic. If you need to pick a player "
            f"to target, refer to them by their seat number. If you need to "
            f"speak, craft a convincing and strategic message."
        )

        # Use system prompt from validator, fallback to a generic one
        system_prompt = synapse.system_prompt or (
            "You are an AI playing the Werewolf social deduction game. "
            "Analyze the game state and make strategic decisions based on your role."
        )

        bt.logging.info(f"Calling Gemini for game {synapse.game_id}...")
        ai_response = _call_gemini(system_prompt, user_message)

        if not ai_response:
            bt.logging.warning("Gemini returned empty; falling back to random")
            import random
            action = []
            for opt in options:
                pv = opt.get("possibleValues", [])
                if pv:
                    action.append({"tag": opt.get("tag", ""), "value": random.choice(pv)})
            synapse.response = json.dumps(action)
            return synapse

        bt.logging.info(f"Gemini response (truncated): {ai_response[:200]}...")

        # Parse the AI response into structured actions
        action = _parse_action_from_response(ai_response, options)
        synapse.response = json.dumps(action)
        bt.logging.info(f"Smart action: {action}")
        return synapse

    async def blacklist(
        self, synapse: WerewolfSynapse
    ) -> typing.Tuple[bool, str]:
        if synapse.dendrite is None or synapse.dendrite.hotkey is None:
            return True, "Missing dendrite or hotkey"

        if (
            not self.config.blacklist.allow_non_registered
            and synapse.dendrite.hotkey not in self.metagraph.hotkeys
        ):
            return True, "Unrecognized hotkey"

        if self.config.blacklist.force_validator_permit:
            uid = self.metagraph.hotkeys.index(synapse.dendrite.hotkey)
            if not self.metagraph.validator_permit[uid]:
                return True, "Non-validator hotkey"

        return False, "Hotkey recognized"

    async def priority(self, synapse: WerewolfSynapse) -> float:
        if synapse.dendrite is None or synapse.dendrite.hotkey is None:
            return 0.0
        caller_uid = self.metagraph.hotkeys.index(synapse.dendrite.hotkey)
        return float(self.metagraph.S[caller_uid])


if __name__ == "__main__":
    with SmartMiner() as miner:
        while True:
            bt.logging.info(f"Smart miner running... {time.time()}")
            time.sleep(5)
