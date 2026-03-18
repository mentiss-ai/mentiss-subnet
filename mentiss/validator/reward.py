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
    game_dominance: float,
    vote_influence: float,
    weight_win_rate: float = 0.5,
    weight_game_dominance: float = 0.25,
    weight_vote_influence: float = 0.25,
) -> float:
    """
    Combine scoring metrics into a single composite score.

    Design philosophy:
    - Losses always get 0 reward (no participation trophies)
    - Win rate determines how OFTEN a miner gets rewarded over time
    - Game dominance + vote influence determine HOW MUCH reward per win
    - A miner who wins through luck (low dominance/influence) gets less
    - A miner who wins AND dominates gets maximum reward

    All inputs and output are in [0, 1].
    """
    # Win rate is the base: if you never win, score is 0
    if win_rate == 0:
        return 0.0

    # Quality score: how well does the miner play when they win?
    quality = (
        weight_game_dominance * game_dominance
        + weight_vote_influence * vote_influence
    ) / (weight_game_dominance + weight_vote_influence)

    # Final score: win_rate determines base, quality adjusts the magnitude
    return weight_win_rate * win_rate + (1 - weight_win_rate) * (win_rate * quality)


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
