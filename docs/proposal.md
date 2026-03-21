# Mentiss Subnet — Updated Proposal

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

### Game Flow

```
Validator                     Mentiss API                  Miner
   │                              │                         │
   │── start_game() ────────────>│                         │
   │<── game_id ─────────────────│                         │
   │                              │                         │
   │── get_status() ────────────>│                         │  (polling loop)
   │<── needs_action, context ───│                         │
   │── WerewolfSynapse ─────────────────────────────────>│
   │<── action response ─────────────────────────────────│
   │── submit_action() ─────────>│                         │
   │                              │                         │
   │  ... repeat until game over ...                       │
   │                              │                         │
   │── get_player_stats() ──────>│                         │
   │<── gameMetrics + humanPlayerMetrics                   │
   │                              │                         │
   │  [compute score, update weights on chain]             │
```

1. **Validator** selects a random miner UID from the metagraph
2. **Validator** creates a 6-player Werewolf game via the Mentiss API (1 Seer, 1 Witch, 2 Werewolves, 2 Villagers)
3. **Miner** controls one werewolf; the other 5 players are AI-controlled by the Mentiss game engine
4. **Validator** polls game status, packages state into a `WerewolfSynapse`, sends it to the miner via Bittensor dendrite, and submits the miner's response back to the API
5. When the game ends, the validator collects deterministic metrics and updates the miner's on-chain weight

### Scoring: Win Rate with Sigmoid Reward

We use a deliberately simple scoring mechanism: **win rate is the sole scoring metric.**

```
score = wins ÷ completed_games
reward = sigmoid(score, threshold=0.30, steepness=20)
```

```
            reward
              1.0 ─────────────────────────
                  │                /
                  │               /
                  │              /  ← steep sigmoid curve
                  │             /
              0.0 ─────────────┤
                  0    0.3    0.5    0.7    1.0
                       ↑                        win_rate
                    threshold
```

| Win Rate | Reward | Explanation |
|----------|--------|-------------|
| 0% – 29% | **0.0** | Below threshold → zero reward |
| 30% | **0.5** | Threshold → sigmoid midpoint |
| 40% | **0.88** | Above threshold → rapidly increasing |
| 50%+ | **~1.0** | Strong performance → maximum reward |

**Why 30% threshold?** A random werewolf player wins ~33% of games. After accounting for errors and timeouts, a random/spam miner typically lands **below 30%** — earning zero. To get rewards, miners must demonstrate genuine social deduction intelligence.

**Why team-level scoring?** All miners on the winning werewolf team receive equal reward. This is intentional — strategic self-sacrifice (getting voted out early to protect teammates) is a legitimate Werewolf strategy that should never be penalized.

### Additional Tracked Metrics

While only win rate affects scoring, we track two additional metrics for analytics and future refinement:

| Metric | Description | Range |
|--------|-------------|-------|
| **Game Dominance** | Proportion of werewolves surviving at game end | 0.0 – 1.0 |
| **Vote Influence** | How often good-faction players voted with the miner | 0.0 – 1.0 |

These are persisted to `game_stats.json` for auditability and potential future composite scoring.

---

## Anti-Gaming Properties

### Deterministic, Server-Side Metrics
All scoring metrics are computed by the Mentiss game engine on the server side. Miners cannot fabricate wins or inflate metrics — the game outcome is determined by the API.

### Faction Lock
Miners always play werewolf-faction roles. Cross-faction collusion is impossible by design.

### Per-Action Error Strikes
The validator tracks consecutive errors per action call. After 3 strikes on a single action (timeout, invalid JSON, API rejection), the game is terminated and recorded as `ERROR` with zero score. This prevents miners from sending garbage responses.

Error strikes reset to 0 on any successful action submission, so a miner that recovers from a transient failure gets a fresh start. Only persistent failure triggers the penalty.

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
│   │   ├── manager.py        # Per-miner stat accumulation, persistence
│   │   └── state.py          # MinerGameStats, GameResult, GameOutcome
│   ├── validator/
│   │   ├── forward.py        # Game orchestration loop, metric collection
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
- **3 validator hotkeys** — Each orchestrating games independently, polling the Mentiss API, and setting weights on-chain

### Compute Requirements
- **No GPU required** — Both miners and validators are CPU-only
- **Minimum:** 8 cores, 16GB RAM, Ubuntu 22.04
- **Network:** Stable internet for Mentiss API calls and Bittensor chain interaction

### Data Persistence
- **game_stats.json** — Per-miner cumulative statistics (wins, losses, errors, dominance, influence)
- **state.npz** — Validator step counter, scores array, hotkeys

---

## Why Mentiss Adds Value to Bittensor

1. **Novel evaluation dimension** — No other subnet measures social intelligence, deception, or strategic reasoning
2. **Proof of Intelligence** — Winning at Werewolf requires multi-turn reasoning that can't be faked with random responses
3. **Scalable difficulty** — Game configurations can grow from 6-player to 10-12 player games, increasing strategic complexity
4. **Real-world applications** — Social deduction skills transfer to negotiation AI, fraud detection, and adversarial robustness evaluation
5. **Community engagement** — The Mentiss platform already supports BYOM (Bring Your Own Model) for researchers to benchmark custom models

---

## Key Changes Since Round 1

| Change | Rationale |
|--------|-----------|
| Simplified to pure win-rate scoring | Team-level reward avoids penalizing strategic self-sacrifice |
| Per-action error strikes (3 max) | More granular than per-game limits; catches persistent failures without penalizing transient issues |
| 1-hour game safety cap | Prevents infinite loops from API bugs or stalled games |
| 2-minute miner timeout | Generous enough for LLM inference, strict enough to prevent stalling |
| EMA smoothing (α=0.1) | Prevents single-game score manipulation while responding to performance trends |
