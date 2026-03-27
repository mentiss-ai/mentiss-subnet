"""Test validator modelAssignments against Mentiss prod API.

Verifies:
1. Game creation with faction-level modelAssignments
2. Good players get the baseline model (no bittensor/ prefix)
3. Evil players get bittensor/ prefix (miner-controlled)
4. Game status is paused (waiting for bittensor/ player input)
"""
import asyncio
import json
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mentiss.api.client import MentissAPIClient
from mentiss.api.types import GameSettings


API_KEY = os.environ.get("MENTISS_API_KEY", "")
API_URL = os.environ.get("MENTISS_API_URL", "https://api.mentiss.ai")

# Hackathon config: 9 players
GAME_SETTING = "G9_1SR1WT1HT_2WW1AW_3VG-R"
GOOD_MODEL = "google/gemini-3-flash-preview"
MINER_HOTKEY = "5FakeHotkey123456789"  # fake for testing


async def test_game_creation():
    client = MentissAPIClient(api_key=API_KEY, base_url=API_URL)

    print(f"API: {API_URL}")
    print(f"Game Setting: {GAME_SETTING}")
    print(f"Good model: {GOOD_MODEL}")
    print(f"Evil model: bittensor/{MINER_HOTKEY}")
    print()

    # 1. Create game with faction-level modelAssignments
    settings = GameSettings(
        language="en",
        game_setting=GAME_SETTING,
        model_assignments={
            "good": GOOD_MODEL,
            "evil": f"bittensor/{MINER_HOTKEY}",
        },
    )

    print("--- Test 1: Create game ---")
    try:
        game_id = await client.start_game(settings)
        print(f"✅ Game created: {game_id}")
    except Exception as e:
        print(f"❌ Failed to create game: {e}")
        await client.close()
        return

    # 2. Wait a moment for game to initialize
    await asyncio.sleep(3)

    # 3. Check game status and player assignments
    print("\n--- Test 2: Check player assignments ---")
    try:
        status = await client.get_status(game_id)
        print(f"Status: {status.status}")
        print(f"Phase: {status.phase} / {status.sub_phase}")

        good_count = 0
        evil_count = 0
        for p in sorted(status.players, key=lambda x: x.get("position", 0)):
            pos = p.get("position", "?")
            role = p.get("role") or "?"
            model = p.get("modelName", "?")
            print(f"  [{pos}] {role:20s} model={model}")

            if model == GOOD_MODEL:
                good_count += 1
            elif model.startswith("bittensor/"):
                evil_count += 1

        print(f"\nGood (Gemini): {good_count}, Evil (bittensor/): {evil_count}")

        if good_count == 6 and evil_count == 3:
            print("✅ Player assignment correct: 6 good + 3 evil = 9")
        else:
            print(f"❌ Expected 6 good + 3 evil, got {good_count} + {evil_count}")

    except Exception as e:
        print(f"❌ Failed to get status: {e}")

    # 4. Check if game is paused (waiting for bittensor/ player)
    print("\n--- Test 3: Game should be paused ---")
    try:
        status = await client.get_status(game_id)
        if status.status == "paused":
            print("✅ Game is paused (waiting for external player input)")
        elif status.status == "in_progress":
            if status.needs_action:
                print(f"✅ Game needs action from player: {status.next_input.player_id}")
            else:
                print("⚠️ Game in_progress but no action needed (AI players running)")
        else:
            print(f"⚠️ Unexpected status: {status.status}")
    except Exception as e:
        print(f"❌ Failed: {e}")

    # 5. Fetch system prompt
    print("\n--- Test 4: System prompt ---")
    try:
        system_prompt = await client.get_system_prompt(game_id)
        if system_prompt:
            print(f"✅ System prompt fetched: {len(system_prompt)} chars")
        else:
            print("⚠️ System prompt is empty")
    except Exception as e:
        print(f"❌ Failed to fetch system prompt: {e}")

    await client.close()
    print("\n=== All tests complete ===")


if __name__ == "__main__":
    asyncio.run(test_game_creation())
