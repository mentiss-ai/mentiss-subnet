import json
import asyncio
import numpy as np
import bittensor as bt

from mentiss.protocol import WerewolfSynapse
from mentiss.api.client import MentissAPIClient
from mentiss.api.types import GameSettings, GameStatus
from mentiss.game.manager import GameManager
from mentiss.game.state import GameResult, SCORING_WINDOW_HOURS, MAX_GAMES_IN_WINDOW
from mentiss.validator.reward import (
    sigmoid_reward,
    composite_score,
    determine_game_result,
)
from mentiss.validator.credits import CreditManager
from mentiss.utils.uids import get_random_uids

MINER_TIMEOUT = 120  # 2 minutes per action response
MAX_ERROR_STRIKES = 3  # 3 retries per action call

# ---- Model Comparison Pool ----
# Two models to compare; the validator round-robins these per miner.
MODEL_POOL = [
    "google/gemini-3-flash-preview",
    "z-ai/glm-5",
]

# Good-faction roles for G9_1SR1WT1HT_2WW1AW_3VG-H
# Used to build modelAssignments so the chosen model is applied to all good-faction AI players.
G9_GOOD_FACTION_KEYS = [
    "seer",
    "witch",
    "hunter",
    "villager",       # 1st villager
    "villager_0",     # 2nd villager
    "villager_1",     # 3rd villager
]


def _select_model_for_miner(game_manager: GameManager, miner_uid: int) -> str:
    """Pick the model with fewer qualifying games for this miner (round-robin)."""
    stats = game_manager.get_stats(miner_uid)
    counts = stats.model_game_counts(MODEL_POOL)

    # Find the model(s) with the minimum count
    min_count = min(counts.values())
    candidates = [m for m, c in counts.items() if c == min_count]

    # If tied, pick the first one in pool order for determinism
    for m in MODEL_POOL:
        if m in candidates:
            return m
    return MODEL_POOL[0]


def _build_model_assignments(model: str) -> dict:
    """Build modelAssignments dict assigning all good-faction roles to the given model."""
    return {key: model for key in G9_GOOD_FACTION_KEYS}


async def forward(self):
    """
    Main forward pass: run one Werewolf game for a selected miner.

    Each invocation plays a complete game:
    1. Pick a miner
    2. Select comparison model (round-robin per miner)
    3. Start game via Mentiss API with model assignments
    4. Game loop: poll status -> send to miner -> submit action
    5. Record outcome and fetch per-player scoring metrics
    6. Update rewards using composite score
    """
    if not hasattr(self, "_api_client") or self._api_client is None:
        api_key = getattr(self.config, "mentiss", None)
        api_key = getattr(api_key, "api_key", None) if api_key else None
        self._api_client = MentissAPIClient(api_key=api_key)

    if not hasattr(self, "_game_manager") or self._game_manager is None:
        self._game_manager = GameManager(state_dir=self.config.neuron.full_path)
        self._game_manager.load_state(self.config.neuron.full_path)

    miner_uids = get_random_uids(self, k=1)
    if len(miner_uids) == 0:
        bt.logging.warning("No available miners, skipping forward")
        await asyncio.sleep(10)
        return

    miner_uid = int(miner_uids[0])
    bt.logging.info(f"Selected miner UID {miner_uid} for Werewolf game")

    mentiss_cfg = getattr(self.config, "mentiss", None)
    game_setting = getattr(mentiss_cfg, "game_setting", "G9_1SR1WT1HT_2WW1AW_3VG-H") if mentiss_cfg else "G9_1SR1WT1HT_2WW1AW_3VG-H"
    role = getattr(mentiss_cfg, "role", "werewolf") if mentiss_cfg else "werewolf"
    poll_interval = getattr(mentiss_cfg, "poll_interval", 2.0) if mentiss_cfg else 2.0

    # --- Model comparison: round-robin selection per miner ---
    selected_model = _select_model_for_miner(self._game_manager, miner_uid)
    model_assignments = _build_model_assignments(selected_model)
    bt.logging.info(
        f"Model comparison: miner {miner_uid} → {selected_model} "
        f"(counts={self._game_manager.get_stats(miner_uid).model_game_counts(MODEL_POOL)})"
    )

    # --- Bulk credit system (TAO → game credits) ---
    game_cost_tao = getattr(mentiss_cfg, "game_cost_tao", 0.0) if mentiss_cfg else 0.0
    payment_address = getattr(mentiss_cfg, "payment_address", None) if mentiss_cfg else None

    if game_cost_tao > 0 and payment_address:
        # Initialize credit manager once
        if not hasattr(self, "_credit_manager") or self._credit_manager is None:
            batch_size = getattr(mentiss_cfg, "credit_batch_size", 100) if mentiss_cfg else 100
            self._credit_manager = CreditManager(
                state_dir=self.config.neuron.full_path,
                subtensor=self.subtensor,
                wallet=self.wallet,
                payment_address=payment_address,
                cost_per_game_tao=game_cost_tao,
                batch_size=batch_size,
                refill_threshold=max(10, batch_size // 10),
            )

        if not self._credit_manager.use_credit():
            bt.logging.error(
                "[Credits] No credits available and purchase failed. "
                "Check wallet balance. Skipping game."
            )
            await asyncio.sleep(30)
            return

    settings = GameSettings(
        language="en",
        game_setting=game_setting,
        role=role,
        model_assignments=model_assignments,
    )

    try:
        game_id = await self._api_client.start_game(settings)
    except Exception as e:
        bt.logging.error(f"Failed to start game: {e}")
        await asyncio.sleep(5)
        return

    self._game_manager.register_game(game_id, miner_uid, role, model=selected_model)

    try:
        await _run_game_loop(
            self, game_id, miner_uid, role, poll_interval,
        )
    except Exception as e:
        bt.logging.error(f"Game {game_id} error: {e}")
        self._game_manager.record_result(game_id, GameResult.ERROR)

    self._game_manager.save_state(self.config.neuron.full_path)
    _update_rewards(self)


async def _run_game_loop(
    self,
    game_id: str,
    miner_uid: int,
    role: str,
    poll_interval: float,
):
    """Run the game loop until the game ends or miner is penalized."""
    # Consecutive error counter — persists across loop iterations.
    # Resets to 0 on any successful action.
    error_strikes = 0

    # Safety cap: 1 hour max (1800 polls × 2s interval)
    for _ in range(1800):
        await asyncio.sleep(poll_interval)

        try:
            status: GameStatus = await self._api_client.get_status(game_id)
        except Exception as e:
            bt.logging.error(f"Failed to get status for game {game_id}: {e}")
            continue

        if status.is_game_over:
            result_str = determine_game_result(role, status.winner or "")
            result = GameResult.WIN if result_str == "win" else GameResult.LOSS

            game_dominance = 0.0
            vote_influence = 0.0
            survived = False

            try:
                player_stats = await self._api_client.get_player_stats(game_id)
                game_dominance = player_stats.game_metrics.game_dominance
                vote_influence = player_stats.human_player_metrics.vote_influence
                survived = player_stats.human_player_metrics.survived
            except Exception as e:
                bt.logging.warning(
                    f"Failed to get player stats for game {game_id}: {e}"
                )

            self._game_manager.record_result(
                game_id,
                result,
                game_dominance=game_dominance,
                vote_influence=vote_influence,
                survived=survived,
            )
            bt.logging.info(
                f"Game {game_id} ended: {result.value} "
                f"(role={role}, winner={status.winner}, "
                f"dominance={game_dominance:.2f}, "
                f"vote_influence={vote_influence:.2f}, "
                f"survived={survived})"
            )
            return

        if not status.needs_action:
            continue

        player_id = ""
        if status.next_input:
            player_id = status.next_input.player_id
        if not player_id and status.human_player:
            player_id = status.human_player.id

        context_data = {
            "game": {
                "phase": status.phase,
                "subPhase": status.sub_phase,
                "currentRound": status.current_round,
                "godLog": status.god_log,
                "summaryLog": status.summary_log,
            },
            "players": status.players,
            "actions": status.actions,
            "humanLog": status.human_log,
        }

        synapse = WerewolfSynapse(
            game_id=game_id,
            player_id=player_id,
            role=role,
            game_context=json.dumps(context_data),
            pending_action=json.dumps({
                "options": status.next_input.options,
                "prompt": status.next_input.prompt,
            }) if status.next_input else "{}",
            phase=status.phase,
            sub_phase=status.sub_phase,
            round_number=status.current_round,
        )

        try:
            bt.logging.debug(
                f"Sending synapse to miner {miner_uid} at "
                f"{self.metagraph.axons[miner_uid]}"
            )
            responses = await self.dendrite(
                axons=[self.metagraph.axons[miner_uid]],
                synapse=synapse,
                deserialize=False,
                timeout=MINER_TIMEOUT,
            )
        except Exception as e:
            bt.logging.error(f"Dendrite error for miner {miner_uid}: {e}")
            error_strikes += 1
            bt.logging.warning(f"Miner {miner_uid} strike {error_strikes}/{MAX_ERROR_STRIKES}")
            if error_strikes >= MAX_ERROR_STRIKES:
                bt.logging.error(
                    f"Miner {miner_uid} exceeded {MAX_ERROR_STRIKES} error strikes "
                    f"in game {game_id}. Penalizing with zero score."
                )
                self._game_manager.record_result(game_id, GameResult.ERROR)
                return
            continue

        # Debug: inspect raw response
        if responses:
            r = responses[0]
            bt.logging.debug(
                f"Dendrite response from miner {miner_uid}: "
                f"response={r.response!r}, "
                f"dendrite.status_code={r.dendrite.status_code if r.dendrite else 'N/A'}, "
                f"dendrite.status_message={r.dendrite.status_message if r.dendrite else 'N/A'}, "
                f"axon.status_code={r.axon.status_code if r.axon else 'N/A'}"
            )

        if not responses or responses[0].response is None:
            error_strikes += 1
            bt.logging.warning(
                f"Miner {miner_uid} returned no response for game {game_id} "
                f"(strike {error_strikes}/{MAX_ERROR_STRIKES})"
            )
            if error_strikes >= MAX_ERROR_STRIKES:
                bt.logging.error(
                    f"Miner {miner_uid} exceeded {MAX_ERROR_STRIKES} error strikes "
                    f"in game {game_id}. Penalizing with zero score."
                )
                self._game_manager.record_result(game_id, GameResult.ERROR)
                return
            continue

        try:
            action_data = json.loads(responses[0].response)
            await self._api_client.submit_action(
                game_id=game_id,
                responses=action_data,
                player_id=player_id,
            )
            bt.logging.info(f"Submitted action for game {game_id}: {action_data}")
            # Reset consecutive error counter on success
            error_strikes = 0
        except (json.JSONDecodeError, Exception) as e:
            error_strikes += 1
            bt.logging.error(
                f"Failed to submit action for game {game_id}: {e} "
                f"(strike {error_strikes}/{MAX_ERROR_STRIKES})"
            )
            if error_strikes >= MAX_ERROR_STRIKES:
                bt.logging.error(
                    f"Miner {miner_uid} exceeded {MAX_ERROR_STRIKES} error strikes "
                    f"in game {game_id}. Penalizing with zero score."
                )
                self._game_manager.record_result(game_id, GameResult.ERROR)
                return


def _update_rewards(self):
    """Update scores using sliding window scoring.

    Scoring pipeline per miner:
      1. Protection window: if < PROTECTION_MIN_GAMES completed → neutral score (0.5)
      2. Active scoring: windowed win rate (last MAX_GAMES within SCORING_WINDOW)
      3. Staleness decay: linear decay to 0 if no games in STALE_DECAY_HOURS
      4. Sigmoid reward: maps effective score through sigmoid with cutoff threshold
      5. EMA smoothing: blended into running scores via exponential moving average
    """
    from mentiss.game.state import (
        PROTECTION_MIN_GAMES,
        SCORING_WINDOW_HOURS,
        MAX_GAMES_IN_WINDOW,
        STALE_DECAY_HOURS,
    )

    mentiss_cfg = getattr(self.config, "mentiss", None)
    threshold = getattr(mentiss_cfg, "reward_threshold", 0.30) if mentiss_cfg else 0.30
    steepness = getattr(mentiss_cfg, "reward_steepness", 20.0) if mentiss_cfg else 20.0
    window_hours = getattr(mentiss_cfg, "scoring_window_hours", SCORING_WINDOW_HOURS) if mentiss_cfg else SCORING_WINDOW_HOURS
    max_games = getattr(mentiss_cfg, "max_games_in_window", MAX_GAMES_IN_WINDOW) if mentiss_cfg else MAX_GAMES_IN_WINDOW
    decay_hours = getattr(mentiss_cfg, "stale_decay_hours", STALE_DECAY_HOURS) if mentiss_cfg else STALE_DECAY_HOURS
    min_games = getattr(mentiss_cfg, "protection_min_games", PROTECTION_MIN_GAMES) if mentiss_cfg else PROTECTION_MIN_GAMES

    all_uids = list(range(self.metagraph.n.item()))
    rewards = np.zeros(len(all_uids), dtype=np.float32)

    for i, uid in enumerate(all_uids):
        effective_score = self._game_manager.get_effective_score(
            uid,
            window_hours=window_hours,
            max_games=max_games,
            decay_hours=decay_hours,
            min_games=min_games,
        )
        rewards[i] = sigmoid_reward(effective_score, threshold, steepness)

    self.update_scores(rewards, all_uids)

    # Periodic pruning of old game records (every update)
    self._game_manager.prune_all_old_games(window_hours)

    # Log summary
    active_miners = sum(1 for r in rewards if r > 0)
    bt.logging.info(
        f"Updated scores: {active_miners}/{len(all_uids)} miners with reward > 0 "
        f"(window={window_hours}h, max_games={max_games}, "
        f"decay={decay_hours}h, threshold={threshold})"
    )

