# Validation and Scoring Logic

This document describes how validators evaluate miners and compute on-chain weights in the Mentiss subnet.

## Overview

Validators run Werewolf games via the Mentiss API. Each game picks **one** miner and assigns that miner to the **entire evil faction** — both Werewolves and the Alpha Werewolf — using faction-level model assignments (`model_assignments={"good": <pool_model>, "evil": "bittensor/<miner_hotkey>"}`). Only one miner participates per game, so the win rate is an objective measure of that miner's competency. After each game, the validator collects deterministic metrics from the game engine, combines them into a composite score, and updates the miner's on-chain weight accordingly.

## Game Flow

```
Validator                    Mentiss API                 Miner
   |                             |                        |
   |--- start_game() ---------->|                        |
   |<-- game_id ----------------|                        |
   |                             |                        |
   |--- get_status() ---------->|                        |  (loop)
   |<-- needs_action, context ---|                        |
   |--- WerewolfSynapse -------------------------------->|
   |<-- action response ---------------------------------|
   |--- submit_action() ------->|                        |
   |                             |                        |
   |  ... repeat until game over ...                      |
   |                             |                        |
   |--- get_player_stats() ---->|                        |
   |<-- gameMetrics + humanPlayerMetrics                  |
   |                             |                        |
   |  [compute composite score, update weights]           |
```

Each forward pass:

1. Select a single random miner UID
2. Start a game via `playRouter.start` with faction-level model assignment — the miner controls all three evil-faction seats
3. Poll `playRouter.status` in a loop; when action is needed, send a `WerewolfSynapse` to the miner via dendrite and submit the response back to the API
4. When the game ends, call `playRouter.playerStats` to retrieve scoring metrics
5. Record the result and metrics in `GameManager`
6. Recompute rewards for all miners and update the score moving average

## Three Scoring Metrics

All metrics are extracted from the deterministic game engine. No subjective grading or LLM-as-judge.

### 1. Win Rate (weight: 50%)

The primary metric. Did the werewolf team win?

```
win_rate = wins / (wins + losses)
```

Tracked per miner across all completed games. The competitive baseline is approximately 45%. Miners below 30% win rate receive zero reward due to the sigmoid threshold.

### 2. Game Dominance (weight: 25%)

How decisively did the werewolf team win? Measured by the proportion of werewolves surviving at game's end.

```
game_dominance = surviving_werewolves / total_werewolves
```

- A complete victory (all werewolves alive) scores 1.0
- A narrow win (1 werewolf alive out of 3) scores ~0.33
- Computed per game, averaged across all completed games for the miner

### 3. Vote Influence (weight: 25%)

How effectively did this miner manipulate the good faction's voting? Measured by how often good-faction players voted for the same target as the miner during day votes.

```
vote_influence = aligned_good_votes / total_good_votes
```

For each day vote round:
- Find the miner's vote target
- Count how many good-faction players voted for the same target
- Aggregate across all rounds in the game

A high vote influence means the miner successfully persuaded good players to follow their lead. Computed per game, averaged across all completed games.

## Composite Score

The three metrics are combined into a single composite score:

```
composite = W_wr * win_rate + W_gd * avg_game_dominance + W_vi * avg_vote_influence
```

Default weights:
- `W_wr` = 0.5 (win rate)
- `W_gd` = 0.25 (game dominance)
- `W_vi` = 0.25 (vote influence)

Configurable via `--mentiss.weight_win_rate`, `--mentiss.weight_game_dominance`, `--mentiss.weight_vote_influence`.

## Sigmoid Reward Function

The composite score is passed through a sigmoid function with a hard cutoff:

```
reward(s) = 0                          if s < threshold
reward(s) = 1 / (1 + exp(-k*(s-t)))   if s >= threshold
```

Where:
- `s` = composite score
- `t` = threshold (default: 0.30, configurable via `--mentiss.reward_threshold`)
- `k` = steepness (default: 20.0, configurable via `--mentiss.reward_steepness`)

This creates a steep reward curve: high performers earn disproportionately more, while miners below the threshold receive zero.

## Score Update (Exponential Moving Average)

Rewards are applied to the validator's score array using an exponential moving average:

```
scores = alpha * new_rewards + (1 - alpha) * scores
```

- `alpha` = 0.1 (configurable via `--neuron.moving_average_alpha`)
- This smooths out variance from individual games while still responding to performance changes

## Weight Setting

Periodically (every `epoch_length` blocks, default 100), the validator:

1. Normalizes the score array (L1 norm)
2. Processes weights through `process_weights_for_netuid()` to satisfy chain constraints (min allowed weights, max weight limit)
3. Converts to uint16 representation
4. Sets weights on-chain via `subtensor.set_weights()`

## Data Persistence

- **Game stats**: `game_stats.json` in the neuron's data directory. Stores per-miner cumulative stats (wins, losses, game_dominance_sum, vote_influence_sum, survived_count).
- **Validator state**: `state.npz` in the neuron's data directory. Stores step counter, scores array, and hotkeys.

Both are saved after each game and loaded on startup.

## Anti-Gaming Properties

- **Faction lock**: Miners always control the full evil faction. Only one miner participates per game, so cross-miner collusion is impossible by design.
- **Single-miner games**: Because one miner owns all three evil seats, the win rate reflects that miner's own competency — there is no teammate to free-ride on.
- **Sybil resistance**: Multiple UIDs from the same operator are randomly assigned to different games. Statistical averaging over many games prevents artificial score inflation.
- **Deterministic metrics**: All scoring is derived from game engine outcomes, not subjective evaluation.

## Configuration Reference

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--mentiss.reward_threshold` | 0.30 | Composite score below this gets zero reward |
| `--mentiss.reward_steepness` | 20.0 | Steepness of sigmoid curve |
| `--mentiss.games_per_cycle` | 1 | Minimum completed games before rewards apply |
| `--mentiss.weight_win_rate` | 0.50 | Win rate weight in composite score |
| `--mentiss.weight_game_dominance` | 0.25 | Game dominance weight in composite score |
| `--mentiss.weight_vote_influence` | 0.25 | Vote influence weight in composite score |
| `--neuron.moving_average_alpha` | 0.10 | EMA smoothing factor for score updates |
| `--neuron.epoch_length` | 100 | Blocks between weight-setting attempts |

## File Reference

| File | Purpose |
|------|---------|
| `mentiss/validator/forward.py` | Game orchestration, metric collection, reward updates |
| `mentiss/validator/reward.py` | `sigmoid_reward()`, `composite_score()`, `determine_game_result()` |
| `mentiss/game/state.py` | `MinerGameStats` with cumulative metric tracking |
| `mentiss/game/manager.py` | `GameManager` for per-miner stat accumulation and persistence |
| `mentiss/api/client.py` | `MentissAPIClient` including `get_player_stats()` |
| `mentiss/api/types.py` | `PlayerStatsResponse`, `GameMetrics`, `HumanPlayerMetrics` |
| `mentiss/base/validator.py` | `update_scores()` (EMA), `set_weights()` (on-chain) |
| `mentiss/utils/config.py` | All CLI argument definitions |
