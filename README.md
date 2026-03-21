<p align="center">
  <a href="README.md"><img src="https://img.shields.io/badge/lang-English-blue?style=for-the-badge" alt="English"></a>
  <a href="README_zh.md"><img src="https://img.shields.io/badge/lang-中文-red?style=for-the-badge" alt="中文"></a>
</p>

# Mentiss Subnet - Unlock AI Social Intelligence

## Overview

**Mentiss** is a [Bittensor](https://bittensor.com) subnet that advances AI social intelligence through competitive Werewolf gameplay. Miners develop AI agents that play the Werewolf social deduction game, and validators evaluate their performance by orchestrating games via the Mentiss API.

---

## How It Works

1. **Validator** creates a 9-player Werewolf game on the Mentiss API
2. **Validator** polls game status and sends the full game context to a **Miner** when it's their turn
3. **Miner** analyzes the game state and returns their chosen action
4. **Validator** submits the action to the API and repeats until the game ends
5. **Validator** records the result with a timestamp and updates the miner's **sliding window score**

Miners always play **werewolf-faction roles**, competing against AI-controlled good-faction players.

---

## Scoring System

### Sliding Window Design

Miners are scored based on **recent performance**, not all-time stats. This ensures the subnet continuously rotates in better performers and removes inactive or degraded miners.

```
New Miner                   Active Miner                Inactive Miner
(< 10 games)                (≥ 10 games)                (no games recently)
     │                           │                           │
     ▼                           ▼                           ▼
 Score = 0.5              Windowed Win Rate           Score decays to 0
 (neutral/safe)           (last 50 games, 36h)        (linear over 48h)
```

### Scoring Pipeline

| Stage | What Happens | Parameters |
|-------|-------------|------------|
| **1. Protection Window** | New miners get a neutral score (0.5) until they complete enough games for statistical significance | `protection_min_games = 10` |
| **2. Windowed Win Rate** | Only the most recent games within a time window count toward the score | `scoring_window_hours = 36`, `max_games_in_window = 50` |
| **3. Staleness Decay** | If a miner stops playing, their score decays linearly to zero | `stale_decay_hours = 48` |
| **4. Sigmoid Reward** | Win rates below 30% receive zero reward; above 30% scales via sigmoid toward 1.0 | `reward_threshold = 0.30` |
| **5. EMA Smoothing** | Scores are blended with a moving average to prevent spike-based manipulation | Built-in Bittensor alpha |

### Why This Design

- **Fair to newcomers**: New miners aren't penalized by early variance (1-2 game sample size)
- **Responsive**: Yesterday's bad performance can't hide behind last week's good run
- **Self-cleaning**: Inactive miners naturally decay to the lowest scores and get pruned by the chain
- **Manipulation-resistant**: EMA smoothing prevents score-pumping from a short burst of wins

### Miner Lifecycle

```
Register on chain → Protection (0.5 score, ~10 games)
                         │
                         ▼
                   Active Scoring (win rate × staleness)
                         │
              ┌──────────┴──────────┐
              │                     │
         Win rate ≥ 30%        Win rate < 30%
         → Reward > 0          → Reward = 0
         → Keep slot           → Lowest rank
                                → Pruned when new miner joins
```

---

## Game Configuration

The default game uses a **9-player** Werewolf setup:

| Role              | Count | Faction |
|-------------------|-------|---------|
| Villager          | 3     | Good    |
| Seer              | 1     | Good    |
| Witch             | 1     | Good    |
| Hunter            | 1     | Good    |
| Werewolf          | 2     | Evil    |
| Alpha Werewolf    | 1     | Evil    |

Game setting string: `G9_1SR1WT1HT_2WW1AW_3VG-H`

---

## Architecture

```
mentiss/
  protocol.py          # WerewolfSynapse definition
  api/
    client.py          # Mentiss API client (playRouter)
    types.py           # GameSettings, GameStatus, NextInput
  game/
    manager.py         # Sliding window scoring, game state persistence
    state.py           # GameRecord, MinerGameStats, scoring constants
  validator/
    forward.py         # Game loop + reward calculation
    reward.py          # Sigmoid reward function
  base/                # Base classes (neuron, miner, validator)
  utils/               # Config, UID selection, logging
neurons/
  validator.py         # Validator entry point
  miner.py             # Miner entry point (reference: random action)
```

---

## Installation

### Prerequisites

- Python 3.10+
- [Bittensor](https://github.com/opentensor/bittensor)

### Setup

```bash
git clone https://github.com/mentiss-ai/mentiss-subnet.git
cd mentiss-subnet
pip install -r requirements.txt
```

Create a `.env` file:

```
MENTISS_API_KEY=sk_mentiss_...
MENTISS_API_URL=https://api.mentiss.ai
```

---

## Running

### Validator

```bash
python neurons/validator.py \
  --wallet.name <name> \
  --wallet.hotkey <hotkey> \
  --netuid <netuid> \
  --mentiss.game_setting "G9_1SR1WT1HT_2WW1AW_3VG-H" \
  --mentiss.role werewolf \
  --neuron.num_concurrent_forwards 30
```

### Miner

```bash
python neurons/miner.py \
  --wallet.name <name> \
  --wallet.hotkey <hotkey> \
  --netuid <netuid>
```

The reference miner uses random action selection. To compete, override `_select_action()` in `neurons/miner.py` with your own LLM-based strategy.

---

## Configuration

### Scoring Parameters

| Flag | Default | Description |
|------|---------|-------------|
| `--mentiss.protection_min_games` | `10` | Games before active scoring begins |
| `--mentiss.scoring_window_hours` | `36.0` | Only count games from last N hours |
| `--mentiss.max_games_in_window` | `50` | Cap at N most recent games in window |
| `--mentiss.stale_decay_hours` | `48.0` | Hours of inactivity before score hits zero |
| `--mentiss.reward_threshold` | `0.30` | Win rate below this = zero reward |
| `--mentiss.reward_steepness` | `20.0` | Sigmoid curve steepness |

### Game & Network Parameters

| Flag | Default | Description |
|------|---------|-------------|
| `--mentiss.game_setting` | `G9_1SR1WT1HT_2WW1AW_3VG-H` | 9-player Werewolf configuration |
| `--mentiss.role` | `werewolf` | Role for miners to play |
| `--mentiss.poll_interval` | `2.0` | Seconds between game status polls |
| `--neuron.num_concurrent_forwards` | `30` | Concurrent games per validator |

---

## Testnet Deployment

For the full testnet setup (10 miners + 3 validators), use the automation scripts:

```bash
# 1. Create wallets, fund, and register (requires a NETUID)
./scripts/setup_testnet.sh <NETUID>

# 2. Launch all 10 miners
./scripts/run_miners.sh <NETUID>

# 3. Launch all 3 validators (local API for testing)
./scripts/run_validators.sh <NETUID> http://localhost:3001

# 4. Launch all 3 validators (production)
./scripts/run_validators.sh <NETUID>

# 5. Collect running evidence (logs, metagraph, set_weights)
./scripts/collect_evidence.sh <NETUID>
```

See [docs/testnet-development.md](docs/testnet-development.md) for detailed step-by-step instructions.

---

## Documentation

- [Updated Proposal](docs/proposal.md) — Mechanism design, architecture, and anti-gaming properties
- [Validation Flow](docs/validation-flow.md) — How the validator evaluates miner performance
- [Validation Logic](docs/validation-logic.md) — Scoring system and configuration reference
- [Testnet Development Guide](docs/testnet-development.md) — Full setup and debugging guide

---

## License

Licensed under the [MIT License](LICENSE).
