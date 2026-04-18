"""Simulate a full G9 Werewolf game with 3 fake miners (DeepSeek V3.2).

Good faction (6 players): google/gemini-3-flash-preview (Mentiss AI auto-runs)
Evil faction (3 players): bittensor/fake-miner (this script controls via DeepSeek V3.2)

All logs saved to evidence/ directory.
"""
import asyncio
import json
import os
import re
import sys
import time
from datetime import datetime

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mentiss.api.client import MentissAPIClient
from mentiss.api.types import GameSettings

# ============================================================
# CONFIG
# ============================================================
MENTISS_API_KEY = os.environ.get("MENTISS_API_KEY", "")
MENTISS_API_URL = "https://api.mentiss.ai"

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = "deepseek/deepseek-chat-v3-0324"  # DeepSeek V3.2

GAME_SETTING = "G9_1SR1WT1HT_2WW1AW_3VG-S"
GOOD_MODEL = "google/gemini-3-flash-preview"
MINER_MODEL = "bittensor/fake-miner-deepseek-v3.2"

POLL_INTERVAL = 3
MAX_TURNS = 300
GAME_TIMEOUT = 3600  # 60 min

# ============================================================
# EVIDENCE LOGGING
# ============================================================
EVIDENCE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "evidence")
os.makedirs(EVIDENCE_DIR, exist_ok=True)

game_log = []

def log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    entry = f"[{timestamp}] {msg}"
    game_log.append(entry)
    print(entry)


# ============================================================
# OPENROUTER LLM CALL
# ============================================================

async def call_deepseek(system_prompt: str, user_prompt: str) -> str:
    """Call DeepSeek V3.2 via OpenRouter."""
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": OPENROUTER_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt[:8000]},
                    {"role": "user", "content": user_prompt[:8000]},
                ],
                "temperature": 0.7,
                "max_tokens": 1024,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


# ============================================================
# RESPONSE PARSER (same as smart_miner.py)
# ============================================================

def parse_response(ai_text: str, options: list) -> list:
    """Parse LLM response into structured [{tag, value}]."""
    responses = []
    for opt in options:
        tag = opt.get("tag", "")
        possible = opt.get("possibleValues", [])

        # Text responses
        if tag in ("speaking", "speech", "discuss", "thinking", "memory",
                    "inner_thought", "x-response-message", "x-response-memory",
                    "x-claim-identity"):
            responses.append({"tag": tag, "value": (ai_text or "(no response)")[:1000]})
            continue

        numeric_vals = [v for v in possible if isinstance(v, (int, float))]
        string_vals = [v for v in possible if isinstance(v, str)]

        if numeric_vals:
            chosen = None
            for n in re.findall(r'-?\d+', ai_text or ""):
                if int(n) in numeric_vals:
                    chosen = int(n)
                    break
            if chosen is None:
                chosen = -1 if -1 in numeric_vals else numeric_vals[0]
            responses.append({"tag": tag, "value": chosen})
        elif string_vals:
            chosen = None
            for sv in string_vals:
                if sv.lower() in (ai_text or "").lower():
                    chosen = sv
                    break
            if chosen is None:
                chosen = string_vals[0]
            responses.append({"tag": tag, "value": chosen})

    return responses


# ============================================================
# MAIN GAME LOOP
# ============================================================

async def run_game():
    client = MentissAPIClient(api_key=MENTISS_API_KEY, base_url=MENTISS_API_URL)

    log("=" * 60)
    log("MENTISS SUBNET G9 SIMULATION")
    log(f"Game Setting: {GAME_SETTING}")
    log(f"Good faction: {GOOD_MODEL} (Mentiss AI)")
    log(f"Evil faction: {MINER_MODEL} → DeepSeek V3.2 via OpenRouter")
    log("=" * 60)

    # 1. Create game
    settings = GameSettings(
        language="en",
        game_setting=GAME_SETTING,
        model_assignments={
            "good": GOOD_MODEL,
            "evil": MINER_MODEL,
        },
    )

    try:
        game_id = await client.start_game(settings)
        log(f"Game created: {game_id}")
    except Exception as e:
        log(f"FATAL: Failed to create game: {e}")
        await client.close()
        return

    # 2. Get system prompt
    system_prompt = ""
    for attempt in range(5):
        try:
            system_prompt = await client.get_system_prompt(game_id)
            if system_prompt:
                log(f"System prompt: {len(system_prompt)} chars")
                break
        except Exception:
            pass
        await asyncio.sleep(2)

    if not system_prompt:
        log("WARNING: Could not fetch system prompt")

    # 3. Log player assignments
    await asyncio.sleep(3)
    try:
        status = await client.get_status(game_id)
        log(f"\nPlayer assignments:")
        for p in sorted(status.players, key=lambda x: x.get("position", 0)):
            pos = p.get("position", "?")
            role = p.get("role") or "?"
            model = p.get("modelName", "?")
            faction = "EVIL (miner)" if "bittensor/" in model else "GOOD (AI)"
            log(f"  [{pos}] {role:20s} {faction:15s} model={model}")
    except Exception as e:
        log(f"WARNING: Could not fetch initial status: {e}")

    # 4. Game loop — control evil players via DeepSeek
    log(f"\n{'=' * 60}")
    log("GAME LOOP START")
    log(f"{'=' * 60}")

    calls = 0
    game_start = time.time()

    for turn in range(MAX_TURNS):
        if time.time() - game_start > GAME_TIMEOUT:
            log(f"TIMEOUT after {GAME_TIMEOUT/60:.0f} min")
            break

        await asyncio.sleep(POLL_INTERVAL)

        try:
            status = await client.get_status(game_id)
        except Exception as e:
            log(f"  Status error: {e}")
            continue

        game_status = status.status
        if game_status in ("completed", "error"):
            log(f"\nGAME ENDED: status={game_status}, winner={status.winner}")
            log(f"Rounds played: {status.current_round}")
            break

        if not status.needs_action:
            continue

        next_input = status.next_input
        player_id = next_input.player_id
        options = next_input.options
        prompt_label = next_input.prompt

        # Find player info
        player_info = ""
        player_model = ""
        for p in status.players:
            if p.get("id") == player_id:
                player_model = p.get("modelName", "")
                pos = p.get("position", "?")
                name = p.get("name", "?")
                role = p.get("role") or "?"
                player_info = f"[{pos}]{name}({role})"
                break

        calls += 1
        log(f"\n  Turn {calls}: {player_info} - {prompt_label}")

        # Build LLM prompt
        human_log = status.human_log or ""
        options_desc = "\n".join(
            f"  - {opt.get('tag','?')}: possible values = {opt.get('possibleValues',[])}"
            for opt in options
        )
        user_prompt = (
            f"=== YOUR GAME HISTORY ===\n{human_log}\n\n"
            f"=== CURRENT ACTION ===\n{prompt_label}\n\n"
            f"=== RESPONSE OPTIONS ===\n{options_desc}\n\n"
            "Respond naturally as a Werewolf player. Include numbers for numeric choices."
        )

        # Call DeepSeek V3.2
        try:
            ai_response = await call_deepseek(system_prompt, user_prompt)
            log(f"  DeepSeek response: {ai_response[:200]}...")
        except Exception as e:
            log(f"  DeepSeek ERROR: {e}")
            ai_response = ""

        # Parse response
        parsed = parse_response(ai_response, options)
        log(f"  Parsed: {json.dumps(parsed)[:200]}")

        # Submit to Mentiss
        try:
            success = await client.submit_action(
                game_id=game_id,
                responses=parsed,
                player_id=player_id,
            )
            log(f"  Submitted: {success}")
        except Exception as e:
            log(f"  Submit ERROR: {e}")

    # 5. Final results
    log(f"\n{'=' * 60}")
    log("FINAL RESULTS")
    log(f"{'=' * 60}")

    try:
        final_status = await client.get_status(game_id)
        log(f"Game ID: {game_id}")
        log(f"Status: {final_status.status}")
        log(f"Winner: {final_status.winner}")
        log(f"Rounds: {final_status.current_round}")
        log(f"LLM calls (miner): {calls}")
        log(f"Duration: {time.time() - game_start:.0f}s")

        # Player final status
        log(f"\nFinal player status:")
        for p in sorted(final_status.players, key=lambda x: x.get("position", 0)):
            pos = p.get("position", "?")
            role = p.get("role") or "?"
            status_str = p.get("status", "?")
            model = p.get("modelName", "?")
            icon = "💀" if status_str == "dead" else "✅"
            log(f"  {icon} [{pos}] {role:20s} {status_str:8s} model={model}")

    except Exception as e:
        log(f"Failed to get final status: {e}")

    # 6. Try to get player stats
    try:
        player_stats = await client.get_player_stats(game_id)
        log(f"\nScoring metrics:")
        log(f"  Game dominance: {player_stats.game_metrics.game_dominance:.2f}")
        log(f"  Voting manipulation: {player_stats.game_metrics.voting_manipulation_rate:.2f}")
        log(f"  Good eliminated by vote: {player_stats.game_metrics.good_eliminated_by_vote}")
        log(f"  Miner survived: {player_stats.human_player_metrics.survived}")
        log(f"  Miner vote influence: {player_stats.human_player_metrics.vote_influence:.2f}")
        log(f"  Miner rounds survived: {player_stats.human_player_metrics.rounds_survived}/{player_stats.human_player_metrics.total_rounds}")
    except Exception as e:
        log(f"Player stats not available: {e}")

    await client.close()

    # 7. Save evidence
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    evidence_file = os.path.join(EVIDENCE_DIR, f"g9_simulation_{timestamp}_{game_id}.log")
    with open(evidence_file, "w") as f:
        f.write("\n".join(game_log))
    log(f"\n📁 Evidence saved to: {evidence_file}")


if __name__ == "__main__":
    asyncio.run(run_game())
