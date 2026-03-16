import json
import os
import time
import bittensor as bt
from typing import Dict, List, Optional

from .state import GameOutcome, GameResult, MinerGameStats


class GameManager:
    """Tracks active Werewolf games and accumulated outcomes per miner."""

    def __init__(self, state_dir: str = ""):
        self.state_dir = state_dir
        self.active_games: Dict[str, GameOutcome] = {}
        self.miner_stats: Dict[int, MinerGameStats] = {}

    def register_game(self, game_id: str, miner_uid: int, role: str):
        outcome = GameOutcome(
            game_id=game_id,
            miner_uid=miner_uid,
            role=role,
        )
        self.active_games[game_id] = outcome
        bt.logging.info(f"Registered game {game_id} for miner {miner_uid} as {role}")

    def record_result(
        self,
        game_id: str,
        result: GameResult,
        game_dominance: float = 0.0,
        vote_influence: float = 0.0,
        survived: bool = False,
    ):
        if game_id not in self.active_games:
            bt.logging.warning(f"Game {game_id} not found in active games")
            return

        outcome = self.active_games.pop(game_id)
        outcome.result = result
        outcome.finished_at = time.time()
        outcome.game_dominance = game_dominance
        outcome.vote_influence = vote_influence
        outcome.survived = survived

        uid = outcome.miner_uid
        if uid not in self.miner_stats:
            self.miner_stats[uid] = MinerGameStats(uid=uid)

        stats = self.miner_stats[uid]
        stats.total_games += 1
        if result == GameResult.WIN:
            stats.wins += 1
        elif result == GameResult.LOSS:
            stats.losses += 1
        else:
            stats.errors += 1

        if result in (GameResult.WIN, GameResult.LOSS):
            stats.game_dominance_sum += game_dominance
            stats.vote_influence_sum += vote_influence
            if survived:
                stats.survived_count += 1

        bt.logging.info(
            f"Game {game_id} result: {result.value} for miner {uid} "
            f"(wins={stats.wins}, losses={stats.losses}, total={stats.total_games}, "
            f"dominance={game_dominance:.2f}, vote_influence={vote_influence:.2f}, "
            f"survived={survived})"
        )

    def get_stats(self, miner_uid: int) -> MinerGameStats:
        return self.miner_stats.get(miner_uid, MinerGameStats(uid=miner_uid))

    def get_win_rate(self, miner_uid: int) -> float:
        return self.get_stats(miner_uid).win_rate

    def save_state(self, path: str):
        data = {}
        for uid, stats in self.miner_stats.items():
            data[str(uid)] = {
                "total_games": stats.total_games,
                "wins": stats.wins,
                "losses": stats.losses,
                "errors": stats.errors,
                "game_dominance_sum": stats.game_dominance_sum,
                "vote_influence_sum": stats.vote_influence_sum,
                "survived_count": stats.survived_count,
            }
        filepath = os.path.join(path, "game_stats.json")
        with open(filepath, "w") as f:
            json.dump(data, f)
        bt.logging.debug(f"Saved game stats to {filepath}")

    def load_state(self, path: str):
        filepath = os.path.join(path, "game_stats.json")
        if not os.path.exists(filepath):
            bt.logging.info("No game stats file found, starting fresh")
            return
        with open(filepath, "r") as f:
            data = json.load(f)
        for uid_str, stats_data in data.items():
            uid = int(uid_str)
            self.miner_stats[uid] = MinerGameStats(
                uid=uid,
                total_games=stats_data.get("total_games", 0),
                wins=stats_data.get("wins", 0),
                losses=stats_data.get("losses", 0),
                errors=stats_data.get("errors", 0),
                game_dominance_sum=stats_data.get("game_dominance_sum", 0.0),
                vote_influence_sum=stats_data.get("vote_influence_sum", 0.0),
                survived_count=stats_data.get("survived_count", 0),
            )
        bt.logging.info(f"Loaded game stats for {len(self.miner_stats)} miners")
