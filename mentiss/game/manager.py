import json
import os
import time
import bittensor as bt
from typing import Dict, List, Optional

from .state import (
    GameOutcome,
    GameRecord,
    GameResult,
    MinerGameStats,
    PROTECTION_MIN_GAMES,
    SCORING_WINDOW_HOURS,
    MAX_GAMES_IN_WINDOW,
    STALE_DECAY_HOURS,
    PROTECTION_SCORE,
)


class GameManager:
    """Tracks active Werewolf games and accumulated outcomes per miner.

    Uses sliding window scoring: only recent games within a time window
    contribute to the miner's win rate. Supports protection windows for
    new miners and staleness decay for inactive miners.
    """

    def __init__(self, state_dir: str = ""):
        self.state_dir = state_dir
        self.active_games: Dict[str, GameOutcome] = {}
        self.miner_stats: Dict[int, MinerGameStats] = {}

    def register_game(self, game_id: str, miner_uid: int, role: str, model: str = ""):
        outcome = GameOutcome(
            game_id=game_id,
            miner_uid=miner_uid,
            role=role,
            model=model,
        )
        self.active_games[game_id] = outcome
        model_info = f" (model={model})" if model else ""
        bt.logging.info(f"Registered game {game_id} for miner {miner_uid} as {role}{model_info}")

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

        if result == GameResult.ERROR:
            stats.add_error()
        else:
            record = GameRecord(
                timestamp=outcome.finished_at,
                result=result,
                game_dominance=game_dominance,
                vote_influence=vote_influence,
                survived=survived,
                model=outcome.model,
            )
            stats.add_game(record)

        bt.logging.info(
            f"Game {game_id} result: {result.value} for miner {uid} | "
            f"all-time(wins={stats.all_time_wins}, losses={stats.all_time_losses}, "
            f"errors={stats.errors}, total={stats.total_games}) | "
            f"window({stats.windowed_game_count()} games, "
            f"wr={stats.windowed_win_rate() or 0:.2%}) | "
            f"protection={stats.is_in_protection()} | "
            f"staleness={stats.staleness_multiplier():.2f}"
        )

    def get_stats(self, miner_uid: int) -> MinerGameStats:
        return self.miner_stats.get(miner_uid, MinerGameStats(uid=miner_uid))

    def get_win_rate(self, miner_uid: int) -> float:
        """Get windowed win rate for a miner, or 0.0 if no data."""
        stats = self.get_stats(miner_uid)
        wr = stats.windowed_win_rate()
        return wr if wr is not None else 0.0

    def get_effective_score(
        self,
        miner_uid: int,
        window_hours: float = SCORING_WINDOW_HOURS,
        max_games: int = MAX_GAMES_IN_WINDOW,
        decay_hours: float = STALE_DECAY_HOURS,
        min_games: int = PROTECTION_MIN_GAMES,
    ) -> float:
        """Get the effective score for a miner, considering all scoring rules.

        Returns:
            - PROTECTION_SCORE if miner is still in protection window
            - windowed_win_rate * staleness_multiplier otherwise
            - 0.0 if no games at all
        """
        stats = self.get_stats(miner_uid)

        # No games at all
        if stats.total_games == 0:
            return 0.0

        # Protection window: not enough completed games yet
        if stats.is_in_protection(min_games):
            return PROTECTION_SCORE

        # Active scoring: windowed win rate with staleness decay
        wr = stats.windowed_win_rate(window_hours, max_games)
        if wr is None:
            wr = 0.0

        staleness = stats.staleness_multiplier(decay_hours)
        return wr * staleness

    def prune_all_old_games(self, window_hours: float = SCORING_WINDOW_HOURS):
        """Prune old game records from all miners to prevent memory growth."""
        for stats in self.miner_stats.values():
            stats.prune_old_games(window_hours)

    def save_state(self, path: str):
        data = {}
        for uid, stats in self.miner_stats.items():
            data[str(uid)] = {
                "total_games": stats.total_games,
                "all_time_wins": stats.all_time_wins,
                "all_time_losses": stats.all_time_losses,
                "errors": stats.errors,
                "game_dominance_sum": stats.game_dominance_sum,
                "vote_influence_sum": stats.vote_influence_sum,
                "survived_count": stats.survived_count,
                "last_game_at": stats.last_game_at,
                "game_history": [
                    {
                        "timestamp": r.timestamp,
                        "result": r.result.value,
                        "game_dominance": r.game_dominance,
                        "vote_influence": r.vote_influence,
                        "survived": r.survived,
                        "model": r.model,
                    }
                    for r in stats.game_history
                ],
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

            # Reconstruct game history
            history = []
            for rec in stats_data.get("game_history", []):
                history.append(GameRecord(
                    timestamp=rec["timestamp"],
                    result=GameResult(rec["result"]),
                    game_dominance=rec.get("game_dominance", 0.0),
                    vote_influence=rec.get("vote_influence", 0.0),
                    survived=rec.get("survived", False),
                    model=rec.get("model", ""),
                ))

            self.miner_stats[uid] = MinerGameStats(
                uid=uid,
                total_games=stats_data.get("total_games", 0),
                errors=stats_data.get("errors", 0),
                all_time_wins=stats_data.get("all_time_wins", stats_data.get("wins", 0)),
                all_time_losses=stats_data.get("all_time_losses", stats_data.get("losses", 0)),
                game_dominance_sum=stats_data.get("game_dominance_sum", 0.0),
                vote_influence_sum=stats_data.get("vote_influence_sum", 0.0),
                survived_count=stats_data.get("survived_count", 0),
                last_game_at=stats_data.get("last_game_at"),
                game_history=history,
            )
        bt.logging.info(f"Loaded game stats for {len(self.miner_stats)} miners")

        # Prune on load to clean up old data
        self.prune_all_old_games()
