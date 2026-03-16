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


@dataclass
class MinerGameStats:
    uid: int
    total_games: int = 0
    wins: int = 0
    losses: int = 0
    errors: int = 0

    @property
    def win_rate(self) -> float:
        completed = self.wins + self.losses
        if completed == 0:
            return 0.0
        return self.wins / completed
