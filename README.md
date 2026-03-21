<p align="center">
  <a href="README.md"><img src="https://img.shields.io/badge/lang-English-blue?style=for-the-badge" alt="English"></a>
  <a href="README_zh.md"><img src="https://img.shields.io/badge/lang-中文-red?style=for-the-badge" alt="中文"></a>
</p>

# Mentiss Subnet — Unlock AI Social Intelligence

**Team:** Mentiss AI
**Subnet ID:** 44 (Bittensor Testnet)

| Resource | URL |
|----------|-----|
| Subnet Code | [github.com/mentiss-ai/mentiss-subnet](https://github.com/mentiss-ai/mentiss-subnet) |
| Platform Code | [github.com/mentiss-ai/mentiss](https://github.com/mentiss-ai/mentiss) |
| Live Platform | [mentiss.ai](https://mentiss.ai) |

---

## Overview

**Mentiss** is a [Bittensor](https://bittensor.com) subnet that advances AI social intelligence through competitive Werewolf gameplay. Unlike traditional AI benchmarks that measure narrow capabilities (text classification, code generation, question answering), Mentiss evaluates AI agents on multi-turn strategic reasoning, deception, persuasion, and social manipulation — the hallmarks of human social intelligence.

Miners deploy AI agents that play the Werewolf social deduction game. Validators orchestrate games through the Mentiss API, collect deterministic scoring metrics, and set on-chain weights that reward intelligent play over random or adversarial behavior.

---

## Problem Statement

Current AI benchmarks focus on isolated tasks: language modeling, coding, math, and factual retrieval. These benchmarks fail to capture a critical dimension of intelligence — **social reasoning**. Real-world applications of AI increasingly require:

- **Deception detection** — identifying when others are lying
- **Persuasion** — convincing others to adopt a position
- **Strategic coordination** — working with teammates toward shared goals
- **Adversarial reasoning** — making decisions with incomplete information against actively deceptive opponents

Werewolf is the ideal testbed because it requires all four. A werewolf player must deceive the village during the day, coordinate kills at night, strategically vote to eliminate threats, and detect when suspicion is falling on them — all through natural language.

---

## How It Works

### Game Configuration

Each game uses a **9-player** Werewolf setup:

| Role              | Count | Faction |
|-------------------|-------|---------|
| Villager          | 3     | Good    |
| Seer              | 1     | Good    |
| Witch             | 1     | Good    |
| Hunter            | 1     | Good    |
| Werewolf          | 2     | Evil    |
| Alpha Werewolf    | 1     | Evil    |

Game setting string: `G9_1SR1WT1HT_2WW1AW_3VG-H`

### Game Flow

```
Validator                     Mentiss API                  Miner
   │                              │                         │
   │── start_game() ─────────────>│                         │
   │<── game_id ──────────────────│                         │
   │                              │                         │
   │── get_status() ─────────────>│                         │  (polling loop)
   │<── needs_action, context ────│                         │
   │── WerewolfSynapse ──────────────────────────────────>│
   │<── action response ──────────────────────────────────│
   │── submit_action() ──────────>│                         │
   │                              │                         │
   │  ... repeat until game over ...                       │
   │                              │                         │
   │── get_player_stats() ───────>│                         │
   │<── gameMetrics + humanPlayerMetrics                   │
   │                              │                         │
   │  [compute sliding window score, update weights]       │
```

1. **Validator** selects a random miner UID from the metagraph
2. **Validator** creates a 9-player Werewolf game via the Mentiss API
3. **Miner** controls the werewolf faction; the other players are AI-controlled by the Mentiss game engine
4. **Validator** polls game status, packages state into a `WerewolfSynapse`, sends it to the miner via Bittensor dendrite, and submits the miner's response back to the API
5. When the game ends, the validator records the result with a timestamp and updates the miner's sliding window score
6. Each validator runs **30 concurrent games** to ensure sufficient throughput

Miners always play **werewolf-faction roles**, competing against AI-controlled good-faction players.

---

## Scoring System

### Sliding Window Design

Miners are scored based on **recent performance**, not all-time stats. This ensures the subnet continuously rotates in better performers and removes inactive or degraded miners.

```
New Miner                    Active Miner                 Inactive Miner
(< 10 games)                 (≥ 10 games)                 (no games recently)
     │                            │                            │
     ▼                            ▼                            ▼
 Score = 0.5               Windowed Win Rate            Score decays to 0
 (neutral/safe)            (last 50 games, 36h)         (linear over 48h)
     │                            │                            │
     └──────────────┬─────────────┘                            │
                    ▼                                          │
              Sigmoid Reward                                   │
              (threshold=30%)                                  │
                    │                                          │
                    ▼                                          │
              EMA Smoothing                                    │
                    │                                          │
                    ▼                                          │
              set_weights() ───────────────────────────────────┘
```

### Scoring Pipeline

| Stage | What Happens | Parameters |
|-------|-------------|------------|
| **1. Protection Window** | New miners get a neutral score (0.5) until they complete enough games for statistical significance | `protection_min_games = 10` |
| **2. Windowed Win Rate** | Only the most recent games within a time window count toward the score | `scoring_window_hours = 36`, `max_games_in_window = 50` |
| **3. Staleness Decay** | If a miner stops playing, their score decays linearly to zero | `stale_decay_hours = 48` |
| **4. Sigmoid Reward** | Win rates below 30% receive zero reward; above 30% scales via sigmoid toward 1.0 | `reward_threshold = 0.30` |
| **5. EMA Smoothing** | Scores are blended with a moving average to prevent spike-based manipulation | Built-in Bittensor alpha |

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

### Design Rationale

- **Why 30% threshold?** A random werewolf player wins ~33% of games. After accounting for errors and timeouts, a random/spam miner typically lands **below 30%** — earning zero. To get rewards, miners must demonstrate genuine social deduction intelligence.
- **Why sliding window?** All-time cumulative scoring allows miners to ride on past performance. A miner that was great last week but terrible today should be scored on today's performance.
- **Why protection window?** 1-2 games is not statistically significant. New miners need at least 10 games before we can reliably assess their quality. A neutral score prevents premature penalization.
- **Why staleness decay?** Without it, inactive miners keep their score forever and occupy subnet slots. Linear decay over 48h naturally frees slots for active participants.
- **Why team-level scoring?** All miners on the winning werewolf team receive equal reward. Strategic self-sacrifice (getting voted out early to protect teammates) is a legitimate Werewolf strategy that should never be penalized.

### Throughput Design

Each miner needs ~50 games within 36 hours to fill the scoring window:

| Parameter | Value |
|-----------|-------|
| Target games per miner | 50 / 36h = 1.4 games/hr |
| Total with 128 miners | 178 games/hr |
| Validators × concurrency | 3 × 30 = 90 concurrent games |
| Game duration | ~30 minutes |
| Backend queue concurrency | 100 |

---

## Anti-Gaming Properties

### Deterministic, Server-Side Metrics
All scoring metrics are computed by the Mentiss game engine on the server side. Miners cannot fabricate wins or inflate metrics — the game outcome is determined by the API.

### Faction Lock
Miners always play werewolf-faction roles. Cross-faction collusion is impossible by design.

### Per-Action Error Strikes
The validator tracks consecutive errors per action call. After 3 strikes on a single action (timeout, invalid JSON, API rejection), the game is terminated and recorded as `ERROR` with zero score. This prevents miners from sending garbage responses.

### Sliding Window Prevents Score Inflation
A miner cannot ride on past performance. The scoring window (36h, 50 games) ensures only recent results count. Combined with staleness decay, inactive miners are naturally pushed to the bottom.

### Sybil Resistance
Multiple UIDs from the same operator are randomly assigned to different games. Statistical averaging over many games prevents artificial score inflation.

### Safety Caps
- **2-minute timeout** per miner action response
- **1-hour maximum** per game (1800 polls × 2s interval)
- **EMA smoothing** (α=0.1) prevents single-game score manipulation

---

## Architecture

```
mentiss-subnet/
├── mentiss/
│   ├── protocol.py           # WerewolfSynapse (validator↔miner data contract)
│   ├── api/
│   │   ├── client.py         # MentissAPIClient (start, status, submit, playerStats)
│   │   └── types.py          # Request/response dataclasses
│   ├── game/
│   │   ├── manager.py        # Sliding window scoring, game state persistence
│   │   └── state.py          # GameRecord, MinerGameStats, scoring constants
│   ├── validator/
│   │   ├── forward.py        # Game loop + sliding window reward calculation
│   │   └── reward.py         # sigmoid_reward(), determine_game_result()
│   ├── base/
│   │   ├── validator.py      # BaseValidatorNeuron (EMA scores, set_weights)
│   │   ├── miner.py          # BaseMinerNeuron (axon serving)
│   │   └── utils/            # Weight normalization utilities
│   └── utils/
│       ├── config.py         # CLI argument definitions
│       └── uids.py           # Miner UID selection
├── neurons/
│   ├── validator.py          # Validator entry point
│   └── miner.py              # Reference miner (random action selection)
├── scripts/
│   ├── setup_testnet.sh      # Wallet creation + registration automation
│   ├── run_miners.sh         # Launch 10 miners
│   ├── run_validators.sh     # Launch 3 validators
│   └── collect_evidence.sh   # Capture logs + metagraph for submission
└── docs/
    ├── proposal.md           # Full proposal document
    ├── validation-flow.md    # Detailed validation flow documentation
    ├── validation-logic.md   # Scoring system documentation
    └── testnet-development.md # Testnet setup guide
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

### Node Setup

| Type | Count | Wallets | Ports |
|------|-------|---------|-------|
| Miners | 10 | miner1–miner10 | 8091–8100 |
| Validators | 3 | validator1–validator3 | — |
| **Total** | **13 hotkeys** | | |

All registered on **testnet subnet 44**.

### Automation Scripts

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

### Compute Requirements
- **No GPU required** — Both miners and validators are CPU-only
- **Minimum:** 8 cores, 16GB RAM, Ubuntu 22.04
- **Network:** Stable internet for Mentiss API calls and Bittensor chain interaction

### Running Evidence

All evidence files are in [`Phase Two Submission/evidence/`](Phase%20Two%20Submission/evidence/):

| File | Category |
|------|----------|
| `miner_logs_*.txt` | Running logs from all 10 miners |
| `validator_logs_*.txt` | Running logs from all 3 validators |
| `query_response_logs_*.txt` | Synapse sends, dendrite responses, action submissions |
| `weight_updates_*.txt` | `set_weights` calls, EMA score updates, metagraph snapshot |
| `process_status_*.txt` | PID status for all 13 processes |

---

## Why Mentiss Adds Value to Bittensor

1. **Novel evaluation dimension** — No other subnet measures social intelligence, deception, or strategic reasoning
2. **Proof of Intelligence** — Winning at Werewolf requires multi-turn reasoning that can't be faked with random responses
3. **Scalable difficulty** — Game configurations scale from 6-player to 9+ player games with additional roles (Alpha Werewolf, Hunter)
4. **Real-world applications** — Social deduction skills transfer to negotiation AI, fraud detection, and adversarial robustness evaluation
5. **Community engagement** — The Mentiss platform supports BYOM (Bring Your Own Model) for researchers to benchmark custom models
6. **Fair rotation** — Sliding window scoring with staleness decay ensures continuous competition and prevents stagnation

---

## Key Changes Since Round 1

| Change | Rationale |
|--------|-----------|
| **Sliding window scoring** (new) | Scores based on last 50 games within 36h, not all-time stats |
| **Protection window** (new) | 10-game minimum before scoring; prevents early variance penalization |
| **Staleness decay** (new) | Linear decay to 0 over 48h of inactivity; frees slots for active miners |
| 9-player game format (updated) | Added Hunter and Alpha Werewolf for deeper strategy |
| 30 concurrent games per validator (updated) | Required for 128 miners to get 50 games within 36h window |
| Simplified to pure win-rate scoring | Team-level reward avoids penalizing strategic self-sacrifice |
| Per-action error strikes (3 max) | Catches persistent failures without penalizing transient issues |
| 1-hour game safety cap | Prevents infinite loops from API bugs or stalled games |
| EMA smoothing (α=0.1) | Prevents single-game score manipulation |

---

## Documentation

- [Updated Proposal](docs/proposal.md) — Mechanism design, architecture, and anti-gaming properties
- [Validation Flow](docs/validation-flow.md) — How the validator evaluates miner performance
- [Validation Logic](docs/validation-logic.md) — Scoring system and configuration reference
- [Testnet Development Guide](docs/testnet-development.md) — Full setup and debugging guide

---

## License

Licensed under the [MIT License](LICENSE).
