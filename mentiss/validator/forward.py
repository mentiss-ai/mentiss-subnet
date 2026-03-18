import json
import asyncio
import numpy as np
import bittensor as bt

from mentiss.protocol import WerewolfSynapse
from mentiss.api.client import MentissAPIClient
from mentiss.api.types import GameSettings, GameStatus
from mentiss.game.manager import GameManager
from mentiss.game.state import GameResult
from mentiss.validator.reward import (
    sigmoid_reward,
    composite_score,
    determine_game_result,
)
from mentiss.utils.uids import get_random_uids

MINER_TIMEOUT = 120  # 2 minutes per action response
MAX_ERROR_STRIKES = 3  # 3 retries per action call


async def forward(self):
    """
    Main forward pass: run one Werewolf game for a selected miner.

    Each invocation plays a complete game:
    1. Pick a miner
    2. Start game via Mentiss API
    3. Game loop: poll status -> send to miner -> submit action
    4. Record outcome and fetch per-player scoring metrics
    5. Update rewards using composite score
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
    game_setting = getattr(mentiss_cfg, "game_setting", "G6_1SR1WT_2WW_2VG-H") if mentiss_cfg else "G6_1SR1WT_2WW_2VG-H"
    role = getattr(mentiss_cfg, "role", "werewolf") if mentiss_cfg else "werewolf"
    poll_interval = getattr(mentiss_cfg, "poll_interval", 2.0) if mentiss_cfg else 2.0

    settings = GameSettings(
        language="en",
        game_setting=game_setting,
        role=role,
    )

    try:
        game_id = await self._api_client.start_game(settings)
    except Exception as e:
        bt.logging.error(f"Failed to start game: {e}")
        await asyncio.sleep(5)
        return

    self._game_manager.register_game(game_id, miner_uid, role)

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
    """Update scores from accumulated game stats using composite scoring."""
    mentiss_cfg = getattr(self.config, "mentiss", None)
    threshold = getattr(mentiss_cfg, "reward_threshold", 0.30) if mentiss_cfg else 0.30
    steepness = getattr(mentiss_cfg, "reward_steepness", 20.0) if mentiss_cfg else 20.0
    min_games = getattr(mentiss_cfg, "games_per_cycle", 1) if mentiss_cfg else 1
    w_wr = getattr(mentiss_cfg, "weight_win_rate", 0.5) if mentiss_cfg else 0.5
    w_gd = getattr(mentiss_cfg, "weight_game_dominance", 0.25) if mentiss_cfg else 0.25
    w_vi = getattr(mentiss_cfg, "weight_vote_influence", 0.25) if mentiss_cfg else 0.25

    all_uids = list(range(self.metagraph.n.item()))
    rewards = np.zeros(len(all_uids), dtype=np.float32)

    for i, uid in enumerate(all_uids):
        stats = self._game_manager.get_stats(uid)
        if stats.total_games < min_games:
            continue
        score = composite_score(
            stats.win_rate,
            stats.avg_game_dominance,
            stats.avg_vote_influence,
            w_wr,
            w_gd,
            w_vi,
        )
        rewards[i] = sigmoid_reward(score, threshold, steepness)

    self.update_scores(rewards, all_uids)
    bt.logging.info(f"Updated scores from composite metrics")
