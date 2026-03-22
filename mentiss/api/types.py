from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Union


@dataclass
class GameSettings:
    language: str = "en"
    game_setting: str = "G6_1SR1WT_2WW_2VG-H"
    role: str = "werewolf"
    has_memory: bool = True
    is_high_performance: bool = False
    model_assignments: Dict[str, str] = field(default_factory=dict)  # per-role model overrides


@dataclass
class GameMetrics:
    surviving_werewolves: int = 0
    total_werewolves: int = 0
    game_dominance: float = 0.0
    total_eliminated_by_vote: int = 0
    good_eliminated_by_vote: int = 0
    voting_manipulation_rate: float = 0.0


@dataclass
class HumanPlayerMetrics:
    player_id: str = ""
    role: str = ""
    survived: bool = False
    vote_influence: float = 0.0
    rounds_survived: int = 0
    total_rounds: int = 0


@dataclass
class PlayerStatsResponse:
    game_id: str = ""
    winner: Optional[str] = None
    game_metrics: GameMetrics = field(default_factory=GameMetrics)
    human_player_metrics: HumanPlayerMetrics = field(default_factory=HumanPlayerMetrics)


@dataclass
class NextInput:
    options: List[Dict[str, Any]] = field(default_factory=list)
    prompt: str = ""
    action_id: str = ""
    player_id: str = ""


@dataclass
class HumanPlayer:
    id: str = ""
    position: int = 0
    role: str = ""
    status: str = ""


@dataclass
class GameStatus:
    game_id: str = ""
    status: str = ""
    winner: Optional[str] = None
    phase: str = ""
    sub_phase: str = ""
    current_round: int = 0
    players: List[Dict[str, Any]] = field(default_factory=list)
    actions: List[Dict[str, Any]] = field(default_factory=list)
    human_log: str = ""
    next_input: Optional[NextInput] = None
    human_player: Optional[HumanPlayer] = None
    god_log: str = ""
    summary_log: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_game_over(self) -> bool:
        return self.status in ("completed", "error")

    @property
    def needs_action(self) -> bool:
        return self.next_input is not None and len(self.next_input.options) > 0
