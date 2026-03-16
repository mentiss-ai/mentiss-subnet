from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
import time


class GameResult(str, Enum):
    WIN = "win"
    LOSS = "loss"
    IN_PROGRESS = "in_progress"
    ERROR = "error"


@dataclass
class GameOutcome:
    game_id: str
    miner_uid: int
    role: str
    result: GameResult = GameResult.IN_PROGRESS
    started_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None
    game_dominance: float = 0.0
    vote_influence: float = 0.0
    survived: bool = False


@dataclass
class MinerGameStats:
    uid: int
    total_games: int = 0
    wins: int = 0
    losses: int = 0
    errors: int = 0
    game_dominance_sum: float = 0.0
    vote_influence_sum: float = 0.0
    survived_count: int = 0

    @property
    def completed_games(self) -> int:
        return self.wins + self.losses

    @property
    def win_rate(self) -> float:
        if self.completed_games == 0:
            return 0.0
        return self.wins / self.completed_games

    @property
    def avg_game_dominance(self) -> float:
        if self.completed_games == 0:
            return 0.0
        return self.game_dominance_sum / self.completed_games

    @property
    def avg_vote_influence(self) -> float:
        if self.completed_games == 0:
            return 0.0
        return self.vote_influence_sum / self.completed_games

    @property
    def survival_rate(self) -> float:
        if self.completed_games == 0:
            return 0.0
        return self.survived_count / self.completed_games
