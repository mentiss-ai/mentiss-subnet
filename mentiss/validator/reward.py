import math
import numpy as np
from typing import Dict


WEREWOLF_ROLES = {
    "werewolf", "snow_wolf", "alpha_wolf", "gargoyle",
    "wraith_knight", "blood_moon_herald",
}

GOOD_ROLES = {
    "seer", "witch", "villager", "hunter", "guard",
    "gravekeeper", "knight", "demon_hunter",
    "black_market_dealer", "lucky_one",
}


def sigmoid_reward(
    score: float,
    threshold: float = 0.30,
    steepness: float = 20.0,
) -> float:
    """
    Sigmoid reward with a hard cutoff at the threshold.

    Below threshold -> 0 (no reward for low-effort miners).
    Above threshold -> sigmoid curve approaching 1.
    """
    if score < threshold:
        return 0.0
    x = steepness * (score - threshold)
    x = max(-500, min(500, x))
    return 1.0 / (1.0 + math.exp(-x))


def composite_score(
    win_rate: float,
    game_dominance: float = 0.0,
    vote_influence: float = 0.0,
    weight_win_rate: float = 1.0,
    weight_game_dominance: float = 0.0,
    weight_vote_influence: float = 0.0,
) -> float:
    """
    Score a miner based on win rate.

    Design philosophy:
    - All miners on the winning team get EQUAL reward
    - Strategic self-sacrifice (dying early to protect the team) is valid
    - Win rate is the sole metric — it captures team-level success
    - game_dominance and vote_influence are tracked for analytics but
      not used in scoring (kept as params for backward compatibility)

    Returns a score in [0, 1].
    """
    return win_rate



def determine_game_result(role: str, winner: str) -> str:
    """
    Determine if the miner won based on their role and the game winner.
    Returns "win" or "loss".
    """
    if role in WEREWOLF_ROLES:
        return "win" if winner in ("werewolf", "evil") else "loss"
    if role in GOOD_ROLES:
        return "win" if winner in ("villager", "good") else "loss"
    return "loss"


def calculate_rewards(
    miner_win_rates: Dict[int, float],
    num_uids: int,
    threshold: float = 0.30,
    steepness: float = 20.0,
) -> np.ndarray:
    """Calculate reward array for all UIDs based on win rates."""
    rewards = np.zeros(num_uids, dtype=np.float32)
    for uid, win_rate in miner_win_rates.items():
        if 0 <= uid < num_uids:
            rewards[uid] = sigmoid_reward(win_rate, threshold, steepness)
    return rewards
