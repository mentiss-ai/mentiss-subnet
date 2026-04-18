#!/usr/bin/env python3
"""
End-to-end evidence test: Smart Miner (Gemini) ↔ Mentiss API.

Runs N games through the full pipeline, producing clean logs for
submission evidence. Good-faction AI models are assigned randomly
by the Mentiss API (default model pool).

Usage:
    python scripts/run_evidence_test.py --games 6
"""

import os
import sys
import json
import asyncio
import argparse
import time

# Add project root to path
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIR)

# Load .env
env_path = os.path.join(PROJECT_DIR, ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())

from mentiss.api.client import MentissAPIClient
from mentiss.api.types import GameSettings, GameStatus

# ---- Config ----
GAME_SETTING = "G4_1SR_1WW_2VG-S"

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY_BITTENSOR", "")
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_API_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}"
    f":generateContent?key={GOOGLE_API_KEY}"
)


def log(msg, level="INFO"):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"{ts} | {level:7s} | {msg}")


async def call_gemini(system_prompt: str, user_message: str) -> str:
    """Call Gemini API directly."""
    import httpx

    payload = {
        "contents": [{"role": "user", "parts": [{"text": user_message}]}],
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 2048},
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(GEMINI_API_URL, json=payload)
        resp.raise_for_status()
        data = resp.json()
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                return parts[0].get("text", "")
    return ""


def parse_ai_response(ai_text: str, options: list) -> list:
    """Parse Gemini's response into game actions."""
    import re
    responses = []
    ai_lower = ai_text.lower()

    for opt in options:
        tag = opt.get("tag", "")
        possible_values = opt.get("possibleValues", [])
        if not possible_values:
            continue

        if tag in ("speaking", "speech", "discuss", "thinking", "memory", "inner_thought"):
            responses.append({"tag": tag, "value": ai_text[:500]})
            continue

        numeric_values = [v for v in possible_values if isinstance(v, (int, float))]
        string_values = [v for v in possible_values if isinstance(v, str)]

        if numeric_values:
            chosen = None
            patterns = [r'player\s*(\d+)', r'seat\s*(\d+)', r'position\s*(\d+)',
                        r'#(\d+)', r'choose\s*(\d+)', r'vote.*?(\d+)', r'kill.*?(\d+)']
            for p in patterns:
                m = re.search(p, ai_lower)
                if m:
                    num = int(m.group(1))
                    if num in numeric_values:
                        chosen = num
                        break
            if chosen is None:
                for num in numeric_values:
                    if str(num) in ai_text:
                        chosen = num
                        break
            if chosen is None:
                chosen = numeric_values[0]
            responses.append({"tag": tag, "value": chosen})

        elif string_values:
            chosen = None
            yes_vals = [v for v in string_values if v.lower() in ("yes", "true", "use")]
            no_vals = [v for v in string_values if v.lower() in ("no", "false", "skip", "pass")]
            if yes_vals and no_vals:
                if any(w in ai_lower for w in ("yes", "use", "save", "antidote")):
                    chosen = yes_vals[0]
                elif any(w in ai_lower for w in ("no", "skip", "pass", "don't")):
                    chosen = no_vals[0]
            if chosen is None:
                for val in string_values:
                    if val.lower() in ai_lower:
                        chosen = val
                        break
            if chosen is None:
                chosen = string_values[0]
            responses.append({"tag": tag, "value": chosen})

    return responses


async def run_game(api: MentissAPIClient, game_num: int) -> dict:
    """Run a single game end-to-end."""
    settings = GameSettings(
        language="en",
        game_setting=GAME_SETTING,
        role="werewolf",
    )

    log(f"[Game {game_num}] Starting (good-faction models: platform default)")
    game_id = await api.start_game(settings)
    log(f"[Game {game_num}] Game ID: {game_id}")

    # Fetch system prompt
    system_prompt = ""
    for attempt in range(5):
        system_prompt = await api.get_system_prompt(game_id)
        if system_prompt:
            break
        await asyncio.sleep(2)
    log(f"[Game {game_num}] System prompt: {len(system_prompt)} chars")

    # Game for model info
    try:
        import httpx
        input_data = json.dumps({"json": {"gameId": game_id}})
        async with httpx.AsyncClient(
            base_url=os.environ.get("MENTISS_API_URL", "https://api.mentiss.ai"),
            headers={"Authorization": f"Bearer {os.environ.get('MENTISS_API_KEY', '')}", "Content-Type": "application/json"},
            timeout=30.0,
        ) as client:
            r = await client.get("/api/queryRouter.getGameDataById", params={"input": input_data})
            data = r.json()
            players = data.get("result", {}).get("data", {}).get("json", {}).get("data", {}).get("players", [])
            models_used = [f"{p.get('role', '?')}={p.get('modelName', '?')}" for p in players]
            log(f"[Game {game_num}] Players: {', '.join(models_used)}")
    except Exception as e:
        log(f"[Game {game_num}] Could not fetch player models: {e}", "WARN")

    # Game loop
    actions_taken = 0
    for poll in range(600):  # max ~20 min
        await asyncio.sleep(2)

        try:
            status: GameStatus = await api.get_status(game_id)
        except Exception as e:
            log(f"[Game {game_num}] Status error: {e}", "ERROR")
            continue

        if status.is_game_over:
            result = "WIN" if status.winner == "evil" else "LOSS"
            log(f"[Game {game_num}] GAME OVER: {result} (winner={status.winner})")
            return {
                "game_id": game_id,
                "game_num": game_num,
                "result": result,
                "winner": status.winner,
                "actions_taken": actions_taken,
            }

        if not status.needs_action:
            continue

        # Build context for Gemini
        human_log = status.human_log or ""
        prompt = status.next_input.prompt if status.next_input else ""
        options = status.next_input.options if status.next_input else []

        options_desc = "\n".join(
            f"  - {opt.get('tag', '?')}: possible values = {opt.get('possibleValues', [])}"
            for opt in options
        )

        user_message = (
            f"=== YOUR GAME HISTORY ===\n{human_log}\n\n"
            f"=== CURRENT ACTION ===\n{prompt}\n\n"
            f"=== AVAILABLE OPTIONS ===\n{options_desc}\n\n"
            f"You are playing as: werewolf\n"
            f"Current phase: {status.phase} / {status.sub_phase}\n"
            f"Round: {status.current_round}\n\n"
            f"Based on your role, the game history, and available options, "
            f"decide what to do. Be strategic."
        )

        log(f"[Game {game_num}] Action needed: {status.phase}/{status.sub_phase} R{status.current_round}")

        # Call Gemini
        ai_response = await call_gemini(system_prompt, user_message)
        if not ai_response:
            log(f"[Game {game_num}] Gemini returned empty, using random fallback", "WARN")
            import random
            action_data = [{"tag": opt.get("tag", ""), "value": random.choice(opt.get("possibleValues", [""]))}
                           for opt in options if opt.get("possibleValues")]
        else:
            log(f"[Game {game_num}] Gemini: {ai_response[:150]}...")
            action_data = parse_ai_response(ai_response, options)

        # Submit action
        player_id = status.next_input.player_id if status.next_input else ""
        if not player_id and status.human_player:
            player_id = status.human_player.id

        try:
            await api.submit_action(game_id, action_data, player_id)
            actions_taken += 1
            log(f"[Game {game_num}] Submitted action #{actions_taken}: {json.dumps(action_data)[:200]}")
        except Exception as e:
            log(f"[Game {game_num}] Submit error: {e}", "ERROR")

    log(f"[Game {game_num}] Game did not finish in time", "ERROR")
    return {"game_id": game_id, "game_num": game_num, "result": "TIMEOUT", "actions_taken": actions_taken}


async def main():
    parser = argparse.ArgumentParser(description="Run evidence test games")
    parser.add_argument("--games", type=int, default=6, help="Number of games to play")
    args = parser.parse_args()

    num_games = args.games

    log("=" * 60)
    log("MENTISS SUBNET — EVIDENCE TEST")
    log(f"Games: {num_games} | Setting: {GAME_SETTING}")
    log(f"Good-faction models: platform default (random pool)")
    log("=" * 60)

    api = MentissAPIClient()
    results = []

    for i in range(1, num_games + 1):
        result = await run_game(api, i)
        results.append(result)
        log("-" * 40)

    await api.close()

    # Summary
    log("")
    log("=" * 60)
    log("TEST RESULTS SUMMARY")
    log("=" * 60)
    wins = sum(1 for r in results if r["result"] == "WIN")
    losses = sum(1 for r in results if r["result"] == "LOSS")
    errors = sum(1 for r in results if r["result"] not in ("WIN", "LOSS"))
    log(f"Total: {len(results)} | Wins: {wins} | Losses: {losses} | Errors: {errors}")
    log(f"Win rate: {wins/len(results)*100:.1f}%")
    log("")
    for r in results:
        log(f"  Game {r['game_num']}: {r['result']:5s} | actions={r['actions_taken']} | id={r['game_id']}")
    log("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
