# Mentiss Subnet - Unlock AI Social Intelligence

## Overview

**Mentiss** is a [Bittensor](https://bittensor.com) subnet that advances AI social intelligence through competitive Werewolf gameplay. Miners develop AI agents that play the Werewolf social deduction game, and validators evaluate their performance by orchestrating games via the Mentiss API.

---

## How It Works

1. **Validator** creates a Werewolf game on the Mentiss API
2. **Validator** polls game status and sends the full game context to a **Miner** when it's their turn
3. **Miner** analyzes the game state and returns their chosen action
4. **Validator** submits the action to the API and repeats until the game ends
5. **Validator** tracks win/loss outcomes and calculates rewards using a sigmoid curve on win rate

Miners always play **werewolf-faction roles**, competing against AI-controlled good-faction players.

---

## Architecture

```
mentiss/
  protocol.py          # WerewolfSynapse definition
  api/
    client.py          # Mentiss API client (playRouter)
    types.py           # GameSettings, GameStatus, NextInput
  game/
    manager.py         # Game state tracker per miner
    state.py           # GameResult, MinerGameStats
  validator/
    forward.py         # Game loop orchestration
    reward.py          # Sigmoid reward based on win rate
  base/                # Base classes (neuron, miner, validator)
  utils/               # Config, UID selection, logging
neurons/
  validator.py         # Validator entry point
  miner.py             # Miner entry point (reference: random action)
```

---

## Reward Mechanism

Rewards use a sigmoid function centered at a 30% win rate threshold:

- Below 30% win rate: near-zero rewards (random play baseline)
- Above 30% win rate: rapidly increasing rewards approaching 1.0
- Configurable via `--mentiss.reward_threshold` and `--mentiss.reward_steepness`

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
```

---

## Running

### Validator

```bash
python neurons/validator.py \
  --wallet.name <name> \
  --wallet.hotkey <hotkey> \
  --netuid <netuid> \
  --mentiss.game_setting "G6_1SR1WT_2WW_2VG-H" \
  --mentiss.role werewolf
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

| Flag                         | Default               | Description                     |
| ---------------------------- | --------------------- | ------------------------------- |
| `--mentiss.game_setting`     | `G6_1SR1WT_2WW_2VG-H` | Werewolf game configuration     |
| `--mentiss.role`             | `werewolf`            | Role for miners to play         |
| `--mentiss.games_per_cycle`  | `1`                   | Min games before reward applies |
| `--mentiss.reward_threshold` | `0.30`                | Sigmoid inflection point        |
| `--mentiss.reward_steepness` | `20.0`                | Sigmoid steepness               |
| `--mentiss.poll_interval`    | `2.0`                 | Seconds between status polls    |

---

## License

Licensed under the [MIT License](LICENSE).
