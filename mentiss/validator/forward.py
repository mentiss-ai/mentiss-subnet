import json
import asyncio
import numpy as np
import bittensor as bt

from mentiss.protocol import WerewolfSynapse
from mentiss.api.client import MentissAPIClient
from mentiss.api.types import GameSettings, GameStatus
from mentiss.game.manager import GameManager
from mentiss.game.state import GameResult
from mentiss.validator.reward import sigmoid_reward, determine_game_result
from mentiss.utils.uids import get_random_uids

MAX_ROUNDS_PER_GAME = 100
MINER_TIMEOUT = 30


async def forward(self):
    """
    Main forward pass: run one Werewolf game for a selected miner.

    Each invocation plays a complete game:
    1. Pick a miner
    2. Start game via Mentiss API
    3. Game loop: poll status -> send to miner -> submit action
    4. Record outcome
    5. Update rewards if enough data
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
    """Run the game loop until completion."""
    for _ in range(MAX_ROUNDS_PER_GAME):
        await asyncio.sleep(poll_interval)

        try:
            status: GameStatus = await self._api_client.get_status(game_id)
        except Exception as e:
            bt.logging.error(f"Failed to get status for game {game_id}: {e}")
            continue

        if status.is_game_over:
            result_str = determine_game_result(role, status.winner or "")
            result = GameResult.WIN if result_str == "win" else GameResult.LOSS
            self._game_manager.record_result(game_id, result)
            bt.logging.info(
                f"Game {game_id} ended: {result.value} "
                f"(role={role}, winner={status.winner})"
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
            responses = await self.dendrite(
                axons=[self.metagraph.axons[miner_uid]],
                synapse=synapse,
                deserialize=False,
                timeout=MINER_TIMEOUT,
            )
        except Exception as e:
            bt.logging.error(f"Dendrite error for miner {miner_uid}: {e}")
            continue

        if not responses or responses[0].response is None:
            bt.logging.warning(f"Miner {miner_uid} returned no response for game {game_id}")
            continue

        try:
            action_data = json.loads(responses[0].response)
            await self._api_client.submit_action(
                game_id=game_id,
                responses=action_data,
                player_id=player_id,
            )
            bt.logging.info(f"Submitted action for game {game_id}: {action_data}")
        except Exception as e:
            bt.logging.error(f"Failed to submit action for game {game_id}: {e}")

    bt.logging.warning(f"Game {game_id} exceeded max rounds")
    self._game_manager.record_result(game_id, GameResult.ERROR)


def _update_rewards(self):
    """Update scores from accumulated game stats."""
    mentiss_cfg = getattr(self.config, "mentiss", None)
    threshold = getattr(mentiss_cfg, "reward_threshold", 0.30) if mentiss_cfg else 0.30
    steepness = getattr(mentiss_cfg, "reward_steepness", 20.0) if mentiss_cfg else 20.0
    min_games = getattr(mentiss_cfg, "games_per_cycle", 1) if mentiss_cfg else 1

    all_uids = list(range(self.metagraph.n.item()))
    rewards = np.zeros(len(all_uids), dtype=np.float32)

    for i, uid in enumerate(all_uids):
        stats = self._game_manager.get_stats(uid)
        if stats.total_games < min_games:
            continue
        rewards[i] = sigmoid_reward(stats.win_rate, threshold, steepness)

    self.update_scores(rewards, all_uids)
    bt.logging.info(f"Updated scores from win rates")
