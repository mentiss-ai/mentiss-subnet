from dataclasses import dataclass, field
from typing import Dict, List, Optional
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
    model: str = ""  # Good-faction model used for this game


@dataclass
class GameRecord:
    """A single completed game result with timestamp for sliding window scoring."""
    timestamp: float
    result: GameResult  # WIN or LOSS (ERROR games are not stored)
    game_dominance: float = 0.0
    vote_influence: float = 0.0
    survived: bool = False
    model: str = ""  # Good-faction model used (for model comparison tracking)


# ---- Scoring Constants ----
PROTECTION_MIN_GAMES = 10       # Neutral score until this many games completed
SCORING_WINDOW_HOURS = 36       # Only count games from last 36 hours
MAX_GAMES_IN_WINDOW = 50        # Cap at 50 most recent within window
STALE_DECAY_HOURS = 48          # Linear decay to 0 if no games in this period
PROTECTION_SCORE = 0.5          # Score given to miners still in protection window


@dataclass
class MinerGameStats:
    """Per-miner stats with sliding window support.

    Keeps a list of individual GameRecords so we can compute
    win rate within a time/count window rather than all-time.
    """
    uid: int
    game_history: List[GameRecord] = field(default_factory=list)
    total_games: int = 0       # lifetime total (including errors)
    errors: int = 0            # lifetime error count
    last_game_at: Optional[float] = None  # timestamp of most recent game

    # ----- All-time counters (kept for backward compat / analytics) -----
    all_time_wins: int = 0
    all_time_losses: int = 0
    game_dominance_sum: float = 0.0
    vote_influence_sum: float = 0.0
    survived_count: int = 0

    def add_game(self, record: GameRecord):
        """Add a completed game (WIN or LOSS) to the history."""
        self.game_history.append(record)
        self.last_game_at = record.timestamp
        self.total_games += 1

        if record.result == GameResult.WIN:
            self.all_time_wins += 1
        elif record.result == GameResult.LOSS:
            self.all_time_losses += 1

        self.game_dominance_sum += record.game_dominance
        self.vote_influence_sum += record.vote_influence
        if record.survived:
            self.survived_count += 1

    def add_error(self):
        """Record an error game (not added to game_history for win rate)."""
        self.total_games += 1
        self.errors += 1
        self.last_game_at = time.time()

    def _get_qualifying_games(
        self,
        window_hours: float = SCORING_WINDOW_HOURS,
        max_games: int = MAX_GAMES_IN_WINDOW,
    ) -> List[GameRecord]:
        """Get games qualifying for scoring: within time window, capped at max_games."""
        now = time.time()
        cutoff = now - (window_hours * 3600)

        # Filter to games within time window
        recent = [g for g in self.game_history if g.timestamp >= cutoff]

        # If more than max_games, take the most recent
        if len(recent) > max_games:
            recent = sorted(recent, key=lambda g: g.timestamp, reverse=True)[:max_games]

        return recent

    def windowed_win_rate(
        self,
        window_hours: float = SCORING_WINDOW_HOURS,
        max_games: int = MAX_GAMES_IN_WINDOW,
    ) -> Optional[float]:
        """Calculate win rate from qualifying games.

        Returns None if no qualifying games (caller should handle).
        """
        games = self._get_qualifying_games(window_hours, max_games)
        if not games:
            return None

        wins = sum(1 for g in games if g.result == GameResult.WIN)
        return wins / len(games)

    def windowed_game_count(
        self,
        window_hours: float = SCORING_WINDOW_HOURS,
        max_games: int = MAX_GAMES_IN_WINDOW,
    ) -> int:
        """Number of qualifying games in the current window."""
        return len(self._get_qualifying_games(window_hours, max_games))

    def model_game_counts(
        self,
        models: List[str],
        window_hours: float = SCORING_WINDOW_HOURS,
        max_games: int = MAX_GAMES_IN_WINDOW,
    ) -> Dict[str, int]:
        """Count qualifying games per model within the scoring window.

        Used for round-robin balancing between comparison models.
        """
        games = self._get_qualifying_games(window_hours, max_games)
        counts = {m: 0 for m in models}
        for g in games:
            if g.model in counts:
                counts[g.model] += 1
        return counts

    def staleness_multiplier(self, decay_hours: float = STALE_DECAY_HOURS) -> float:
        """Linear decay from 1.0 to 0.0 based on time since last game.

        Returns 1.0 if a game was played recently.
        Returns 0.0 if no game in the last `decay_hours`.
        """
        if self.last_game_at is None:
            return 0.0

        hours_since_last = (time.time() - self.last_game_at) / 3600
        if hours_since_last <= 0:
            return 1.0
        if hours_since_last >= decay_hours:
            return 0.0

        return 1.0 - (hours_since_last / decay_hours)

    def is_in_protection(self, min_games: int = PROTECTION_MIN_GAMES) -> bool:
        """Check if miner is still in the protection window."""
        completed = self.all_time_wins + self.all_time_losses
        return completed < min_games

    def prune_old_games(self, window_hours: float = SCORING_WINDOW_HOURS):
        """Remove games older than 2x the window to prevent unbounded memory growth."""
        cutoff = time.time() - (window_hours * 2 * 3600)
        self.game_history = [g for g in self.game_history if g.timestamp >= cutoff]

    # ----- Legacy properties (backward compat) -----

    @property
    def completed_games(self) -> int:
        return self.all_time_wins + self.all_time_losses

    @property
    def win_rate(self) -> float:
        """All-time win rate (for backward compatibility)."""
        if self.completed_games == 0:
            return 0.0
        return self.all_time_wins / self.completed_games

    @property
    def wins(self) -> int:
        return self.all_time_wins

    @property
    def losses(self) -> int:
        return self.all_time_losses

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
