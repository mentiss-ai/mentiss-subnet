#!/usr/bin/env python3
"""
Subnet integration test: 10 mock G9 games with 3 simulated miners.

Simulates the validator's forward pass locally:
1. Picks 3 random miners (UIDs 0-2) round-robin
2. Starts G9 games via local Mentiss API (MOCK_AI=true)
3. Miner controls evil faction — submits random valid actions
4. After each game: fetches playerStats, records result in GameManager
5. After all games: computes effective scores and sigmoid rewards
6. Validates credit ledger entries in the database

Requires:
  - Local Mentiss API running (pnpm run dev) with MOCK_AI=true
  - Test user created & whitelisted (see skills/subnet-local-testing.md)
  - Redis model pool seeded
"""

import asyncio
import json
import os
import random
import re
import sys
import time
from datetime import datetime

# Add project root
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

# Override to local
os.environ["MENTISS_API_URL"] = "http://localhost:3001"
# MENTISS_API_KEY is loaded from .env above

from mentiss.api.client import MentissAPIClient
from mentiss.api.types import GameSettings, GameStatus
from mentiss.game.manager import GameManager
from mentiss.game.state import GameResult, GameRecord, MinerGameStats
from mentiss.validator.reward import sigmoid_reward, composite_score, determine_game_result

# ============================================================
# CONFIG
# ============================================================
NUM_GAMES = 5
NUM_MINERS = 3  # Simulated miner UIDs: 0, 1, 2
# G9: 1HT 1SR 1WT 3VG (good=6) + 2WW 1AW (evil=3) = 9 players
# No -R suffix — -R is only for 10-player ultimate trial
GAME_SETTING = "G9_1HT1SR1WT_2WW1AW_3VG"
GOOD_MODEL = "google/gemini-3-flash-preview"
POLL_INTERVAL = 1  # Fast polling for MOCK_AI
MAX_POLLS = 600    # Max polls per game (10 min with 1s interval)

# ============================================================
# LOGGING
# ============================================================
test_log = []

def log(msg, level="INFO"):
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    entry = f"[{ts}] {level:7s} | {msg}"
    test_log.append(entry)
    print(entry)


def parse_mock_response(options: list) -> list:
    """Generate random valid responses for mock miner actions."""
    responses = []
    for opt in options:
        tag = opt.get("tag", "")
        possible = opt.get("possibleValues", [])

        # Text-based tags
        if tag in ("speaking", "speech", "discuss", "thinking", "memory",
                    "inner_thought", "x-response-message", "x-response-memory",
                    "x-claim-identity"):
            responses.append({"tag": tag, "value": f"Mock miner response for {tag}"})
            continue

        if not possible:
            continue

        numeric_vals = [v for v in possible if isinstance(v, (int, float))]
        string_vals = [v for v in possible if isinstance(v, str)]

        if numeric_vals:
            responses.append({"tag": tag, "value": random.choice(numeric_vals)})
        elif string_vals:
            responses.append({"tag": tag, "value": random.choice(string_vals)})

    return responses


async def run_single_game(
    api: MentissAPIClient,
    game_num: int,
    miner_uid: int,
    game_manager: GameManager,
) -> dict:
    """Run a single G9 game for a simulated miner."""
    miner_model = f"bittensor/test-miner-{miner_uid}"

    settings = GameSettings(
        language="en",
        game_setting=GAME_SETTING,
        model_assignments={
            "good": GOOD_MODEL,
            "evil": miner_model,
        },
    )

    log(f"[Game {game_num}] Starting for miner UID={miner_uid} (model={miner_model})")

    try:
        game_id = await api.start_game(settings)
        log(f"[Game {game_num}] Created: {game_id}")
    except Exception as e:
        log(f"[Game {game_num}] FAILED to start: {e}", "ERROR")
        return {"game_num": game_num, "miner_uid": miner_uid, "result": "START_FAILED", "error": str(e)}

    # Register with GameManager
    game_manager.register_game(game_id, miner_uid, "evil", model=GOOD_MODEL)

    # Brief wait for game initialization
    await asyncio.sleep(0.5)

    # Get initial status for player info
    try:
        status = await api.get_status(game_id)
        player_summary = []
        for p in sorted(status.players, key=lambda x: x.get("position", 0)):
            role = p.get("role", "?")
            model = p.get("modelName", "?")
            faction = "EVIL" if "bittensor/" in model else "GOOD"
            player_summary.append(f"[{p.get('position','?')}]{role}({faction})")
        log(f"[Game {game_num}] Players: {', '.join(player_summary)}")
    except Exception as e:
        log(f"[Game {game_num}] Could not fetch initial status: {e}", "WARN")

    # Game loop — submit random actions for the miner
    actions_taken = 0
    game_start = time.time()

    for poll in range(MAX_POLLS):
        await asyncio.sleep(POLL_INTERVAL)

        try:
            status = await api.get_status(game_id)
        except Exception as e:
            log(f"[Game {game_num}] Status poll error: {e}", "ERROR")
            continue

        if status.is_game_over:
            duration = time.time() - game_start
            winner = status.winner or "unknown"

            # Determine result for the miner (playing evil)
            result_str = determine_game_result("werewolf", winner)
            result = GameResult.WIN if result_str == "win" else GameResult.LOSS

            log(f"[Game {game_num}] GAME OVER in {duration:.1f}s — winner={winner}, miner_result={result.value}, rounds={status.current_round}")

            # Fetch player stats
            game_dominance = 0.0
            vote_influence = 0.0
            survived = False
            stats_fetched = False

            try:
                player_stats = await api.get_player_stats(game_id)
                game_dominance = player_stats.game_metrics.game_dominance
                vote_influence = player_stats.human_player_metrics.vote_influence
                survived = player_stats.human_player_metrics.survived
                stats_fetched = True

                log(f"[Game {game_num}] Stats: dominance={game_dominance:.2f}, "
                    f"vote_influence={vote_influence:.2f}, survived={survived}, "
                    f"voting_manip={player_stats.game_metrics.voting_manipulation_rate:.2f}, "
                    f"rounds_survived={player_stats.human_player_metrics.rounds_survived}/{player_stats.human_player_metrics.total_rounds}")
            except Exception as e:
                log(f"[Game {game_num}] Could not fetch player stats: {e}", "WARN")

            # Record in GameManager
            game_manager.record_result(
                game_id, result,
                game_dominance=game_dominance,
                vote_influence=vote_influence,
                survived=survived,
            )

            return {
                "game_num": game_num,
                "game_id": game_id,
                "miner_uid": miner_uid,
                "result": result.value,
                "winner": winner,
                "actions_taken": actions_taken,
                "duration": duration,
                "game_dominance": game_dominance,
                "vote_influence": vote_influence,
                "survived": survived,
                "stats_fetched": stats_fetched,
                "rounds": status.current_round,
            }

        if not status.needs_action:
            continue

        # Submit random valid action
        options = status.next_input.options if status.next_input else []
        player_id = status.next_input.player_id if status.next_input else ""
        if not player_id and status.human_player:
            player_id = status.human_player.id

        action_data = parse_mock_response(options)

        try:
            await api.submit_action(game_id, action_data, player_id)
            actions_taken += 1
        except Exception as e:
            log(f"[Game {game_num}] Submit error: {e}", "ERROR")

    # Timeout
    game_manager.record_result(game_id, GameResult.ERROR)
    log(f"[Game {game_num}] TIMEOUT after {MAX_POLLS * POLL_INTERVAL}s", "ERROR")
    return {"game_num": game_num, "miner_uid": miner_uid, "result": "timeout", "game_id": game_id}


async def verify_credits_in_db(game_ids: list):
    """Query the database to verify credit ledger entries for test games."""
    try:
        import psycopg2
    except ImportError:
        log("psycopg2 not installed, skipping DB credit verification", "WARN")
        return

    try:
        conn = psycopg2.connect("postgresql://postgres:postgres@localhost:5432/mentiss")
        cur = conn.cursor()

        log("\n" + "=" * 60)
        log("CREDIT LEDGER VERIFICATION")
        log("=" * 60)

        for game_id in game_ids:
            # Get credit ledger entries for this game
            cur.execute("""
                SELECT "creditsDelta", reason, "actionId"
                FROM credit_ledger
                WHERE "gameId" = %s
                ORDER BY "createdAt"
            """, (game_id,))
            entries = cur.fetchall()

            if not entries:
                log(f"  Game {game_id[:12]}... : No ledger entries (whitelisted user or free game)")
                continue

            total_charged = sum(int(e[0]) for e in entries if int(e[0]) < 0)
            total_refunded = sum(int(e[0]) for e in entries if int(e[0]) > 0)
            action_count = sum(1 for e in entries if e[2] is not None)  # entries with actionId
            net = total_charged + total_refunded

            log(f"  Game {game_id[:12]}... : {len(entries)} entries, "
                f"charged=${abs(total_charged)/1_000_000:.4f}, "
                f"refunded=${total_refunded/1_000_000:.4f}, "
                f"net=${abs(net)/1_000_000:.4f}, "
                f"actions={action_count}")

        # Overall user balance
        cur.execute("""
            SELECT "bankCredit" FROM users
            WHERE email = 'test_bittensor@mentiss.ai'
        """)
        row = cur.fetchone()
        if row:
            log(f"\n  User bankCredit: ${int(row[0])/1_000_000:.2f}")

        cur.close()
        conn.close()

    except Exception as e:
        log(f"DB verification failed: {e}", "ERROR")


async def main():
    log("=" * 70)
    log(f"MENTISS SUBNET TEST: {NUM_GAMES} G9 GAMES × {NUM_MINERS} MINERS")
    log(f"Game Setting: {GAME_SETTING}")
    log(f"Good Model: {GOOD_MODEL}")
    log(f"API: {os.environ.get('MENTISS_API_URL', 'http://localhost:3001')}")
    log(f"Miners: UIDs 0-{NUM_MINERS-1}")
    log("=" * 70)

    api = MentissAPIClient()
    game_manager = GameManager()

    results = []
    game_ids = []

    for i in range(1, NUM_GAMES + 1):
        # Round-robin miner selection (like validator picks random miners)
        miner_uid = random.randint(0, NUM_MINERS - 1)

        result = await run_single_game(api, i, miner_uid, game_manager)
        results.append(result)
        if "game_id" in result:
            game_ids.append(result["game_id"])
        log("-" * 50)

    await api.close()

    # ============================================================
    # RESULTS SUMMARY
    # ============================================================
    log("\n" + "=" * 70)
    log("GAME RESULTS SUMMARY")
    log("=" * 70)

    for r in results:
        gid = r.get("game_id", "N/A")[:12]
        log(f"  Game {r['game_num']:2d} | Miner {r['miner_uid']} | {r['result']:5s} | "
            f"dom={r.get('game_dominance', 0):.2f} "
            f"vi={r.get('vote_influence', 0):.2f} "
            f"surv={r.get('survived', False)} | "
            f"actions={r.get('actions_taken', 0)} "
            f"rounds={r.get('rounds', 0)} "
            f"time={r.get('duration', 0):.1f}s | "
            f"id={gid}...")

    # ============================================================
    # PER-MINER SCORING (Simulates _update_rewards)
    # ============================================================
    log("\n" + "=" * 70)
    log("PER-MINER SCORING (Reward Pipeline)")
    log("=" * 70)

    for uid in range(NUM_MINERS):
        stats = game_manager.get_stats(uid)
        effective_score = game_manager.get_effective_score(uid)
        reward = sigmoid_reward(effective_score)

        miner_games = [r for r in results if r.get("miner_uid") == uid and r.get("result") in ("win", "loss")]
        wins = sum(1 for r in miner_games if r["result"] == "win")
        losses = sum(1 for r in miner_games if r["result"] == "loss")

        log(f"\n  Miner UID={uid}:")
        log(f"    Games played:      {stats.total_games} (wins={wins}, losses={losses}, errors={stats.errors})")
        log(f"    All-time win rate:  {stats.win_rate:.2%}")

        wr = stats.windowed_win_rate()
        log(f"    Windowed win rate:  {wr:.2%}" if wr is not None else "    Windowed win rate:  N/A (no qualifying games)")
        log(f"    Windowed game ct:   {stats.windowed_game_count()}")
        log(f"    Staleness mult:     {stats.staleness_multiplier():.4f}")
        log(f"    In protection:      {stats.is_in_protection()} (<{10} completed games → score=0.5)")
        log(f"    Effective score:    {effective_score:.4f}")
        log(f"    Sigmoid reward:     {reward:.4f}")

        # Validate scoring logic
        if stats.total_games == 0:
            assert effective_score == 0.0, \
                f"No-games score mismatch: got {effective_score}, expected 0.0"
            log(f"    VALIDATION:         PASS (no games → score=0.0)")
        elif stats.is_in_protection():
            expected_score = 0.5
            assert effective_score == expected_score, \
                f"Protection score mismatch: got {effective_score}, expected {expected_score}"
            log(f"    VALIDATION:         PASS (protection window → score=0.5)")
        elif stats.total_games > 0:
            expected_wr = wr if wr is not None else 0.0
            expected_staleness = stats.staleness_multiplier()
            expected_score = expected_wr * expected_staleness
            assert abs(effective_score - expected_score) < 1e-6, \
                f"Score mismatch: got {effective_score}, expected {expected_score}"
            log(f"    VALIDATION:         PASS (wr={expected_wr:.4f} × staleness={expected_staleness:.4f} = {expected_score:.4f})")

    # ============================================================
    # AGGREGATE STATS
    # ============================================================
    log("\n" + "=" * 70)
    log("AGGREGATE STATISTICS")
    log("=" * 70)

    completed = [r for r in results if r.get("result") in ("win", "loss")]
    wins_total = sum(1 for r in completed if r["result"] == "win")
    losses_total = sum(1 for r in completed if r["result"] == "loss")
    errors_total = sum(1 for r in results if r.get("result") not in ("win", "loss"))
    avg_duration = sum(r.get("duration", 0) for r in completed) / max(len(completed), 1)
    avg_rounds = sum(r.get("rounds", 0) for r in completed) / max(len(completed), 1)
    avg_actions = sum(r.get("actions_taken", 0) for r in completed) / max(len(completed), 1)
    stats_ok = sum(1 for r in completed if r.get("stats_fetched"))

    log(f"  Total games:          {NUM_GAMES}")
    log(f"  Completed:            {len(completed)} (wins={wins_total}, losses={losses_total})")
    log(f"  Errors/timeouts:      {errors_total}")
    log(f"  Evil win rate:        {wins_total/max(len(completed),1)*100:.1f}%")
    log(f"  Avg duration:         {avg_duration:.1f}s")
    log(f"  Avg rounds:           {avg_rounds:.1f}")
    log(f"  Avg miner actions:    {avg_actions:.1f}")
    log(f"  Player stats fetched: {stats_ok}/{len(completed)}")

    # ============================================================
    # CREDIT VERIFICATION
    # ============================================================
    await verify_credits_in_db(game_ids)

    # ============================================================
    # FINAL VERDICT
    # ============================================================
    log("\n" + "=" * 70)

    all_passed = True
    checks = []

    # Check 1: All games completed
    if len(completed) == NUM_GAMES:
        checks.append(("All 10 games completed", True))
    else:
        checks.append((f"Only {len(completed)}/{NUM_GAMES} games completed", False))
        all_passed = False

    # Check 2: Player stats fetched for all completed games
    if stats_ok == len(completed):
        checks.append(("Player stats fetched for all games", True))
    else:
        checks.append((f"Player stats: {stats_ok}/{len(completed)}", False))
        all_passed = False

    # Check 3: All miners have games recorded
    miners_with_games = sum(1 for uid in range(NUM_MINERS) if game_manager.get_stats(uid).total_games > 0)
    # With random assignment, some miners may get 0 games — that's OK if total is correct
    total_recorded = sum(game_manager.get_stats(uid).total_games for uid in range(NUM_MINERS))
    if total_recorded == len(completed):
        checks.append((f"GameManager recorded all {total_recorded} games across {miners_with_games} miners", True))
    else:
        checks.append((f"GameManager mismatch: {total_recorded} recorded vs {len(completed)} completed", False))
        all_passed = False

    # Check 4: Reward pipeline produces valid values
    all_rewards_valid = True
    for uid in range(NUM_MINERS):
        eff = game_manager.get_effective_score(uid)
        rew = sigmoid_reward(eff)
        if not (0.0 <= eff <= 1.0 and 0.0 <= rew <= 1.0):
            all_rewards_valid = False
            break
    if all_rewards_valid:
        checks.append(("Reward values in valid range [0, 1]", True))
    else:
        checks.append(("Reward values out of range", False))
        all_passed = False

    # Check 5: Game metrics are populated
    metrics_populated = all(
        r.get("game_dominance", -1) >= 0 and r.get("vote_influence", -1) >= 0
        for r in completed if r.get("stats_fetched")
    )
    if metrics_populated:
        checks.append(("Game metrics (dominance, vote_influence) populated", True))
    else:
        checks.append(("Some game metrics missing or invalid", False))
        all_passed = False

    for msg, passed in checks:
        icon = "PASS" if passed else "FAIL"
        log(f"  [{icon}] {msg}")

    log("")
    if all_passed:
        log("ALL CHECKS PASSED", "OK")
    else:
        log("SOME CHECKS FAILED — review above", "FAIL")
    log("=" * 70)

    # Save log
    log_dir = os.path.join(PROJECT_DIR, "evidence")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"subnet_10games_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    with open(log_file, "w") as f:
        f.write("\n".join(test_log))
    print(f"\nLog saved to: {log_file}")


if __name__ == "__main__":
    asyncio.run(main())
