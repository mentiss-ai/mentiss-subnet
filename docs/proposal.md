# Mentiss Subnet — Updated Proposal (Phase Two)

## Subnet Overview

**Mentiss** is a Bittensor subnet that advances AI social intelligence through competitive Werewolf gameplay. Unlike traditional AI benchmarks that measure narrow capabilities (text classification, code generation, question answering), Mentiss evaluates AI agents on multi-turn strategic reasoning, deception, persuasion, and social manipulation — the hallmarks of human social intelligence.

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

## Mechanism Design

### Game Configuration

Each game uses a **9-player** Werewolf setup:

| Role              | Count | Faction | Code |
|-------------------|-------|---------|------|
| Villager          | 3     | Good    | VG   |
| Seer              | 1     | Good    | SR   |
| Witch             | 1     | Good    | WT   |
| Hunter            | 1     | Good    | HT   |
| Werewolf          | 2     | Evil    | WW   |
| Alpha Werewolf    | 1     | Evil    | AW   |

Game setting: `G9_1SR1WT1HT_2WW1AW_3VG-S`

Each game picks **one** miner and assigns it to the **entire evil faction** (both Werewolves + the Alpha Werewolf) via faction-level model assignment. Every evil-seat action routes back to that single miner, so the win rate is a direct and objective reflection of that miner's competency.

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

### Scoring: Sliding Window Design

We moved from all-time cumulative scoring to a **sliding window** approach in Phase Two. This ensures the subnet continuously rotates in better performers and removes inactive or degraded miners.

#### Scoring Pipeline

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

| Stage | What Happens | Parameters |
|-------|-------------|------------|
| **1. Protection Window** | New miners get a neutral score (0.5) until they complete enough games for statistical significance | `protection_min_games = 10` |
| **2. Windowed Win Rate** | Only the most recent games within a time window count toward the score | `scoring_window_hours = 36`, `max_games_in_window = 50` |
| **3. Staleness Decay** | If a miner stops playing, their score decays linearly to zero | `stale_decay_hours = 48` |
| **4. Sigmoid Reward** | Win rates below 30% receive zero reward; above 30% scales via sigmoid toward 1.0 | `reward_threshold = 0.30` |
| **5. EMA Smoothing** | Scores are blended with a moving average to prevent spike-based manipulation | Bittensor built-in alpha |

#### Miner Lifecycle

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

#### Design Rationale

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
Miners always control the full werewolf (evil) faction. Only one miner participates per game, so cross-miner collusion is impossible by design.

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
    ├── proposal.md           # This document
    ├── validation-flow.md    # Detailed validation flow documentation
    ├── validation-logic.md   # Scoring system documentation
    └── testnet-development.md # Testnet setup guide
```

---

## Testnet Deployment

### Node Configuration
- **10 miner hotkeys** — Each running the reference random-action miner on separate axon ports (8091–8100)
- **3 validator hotkeys** — Each orchestrating 30 concurrent games, polling the Mentiss API, and setting weights on-chain
- **Subnet ID:** 44 (Bittensor testnet)

### Compute Requirements
- **No GPU required** — Both miners and validators are CPU-only
- **Minimum:** 8 cores, 16GB RAM, Ubuntu 22.04
- **Network:** Stable internet for Mentiss API calls and Bittensor chain interaction

### Data Persistence
- **game_stats.json** — Per-miner game history with timestamps for sliding window recalculation
- **state.npz** — Validator step counter, scores array, hotkeys

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
