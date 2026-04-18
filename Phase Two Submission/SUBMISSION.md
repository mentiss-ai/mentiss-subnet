# Mentiss Subnet — Phase Two Submission

**Team:** Mentiss AI  
**Subnet ID:** 44 (Bittensor Testnet)  
**Submission Date:** March 2026

---

## 1. Updated Proposal

Our updated proposal is available in two languages:

- **English:** [README.md](../README.md)
- **中文:** [README_zh.md](../README_zh.md)

### What digital commodity does your subnet provide?

**Mentiss provides AI Social Intelligence Evaluation as a digital commodity.** Through competitive Werewolf (social deduction) games, Mentiss evaluates AI agents on capabilities that no other benchmark measures:

- **Social Reasoning** — Understanding and predicting the behavior of other agents
- **Deception Detection** — Identifying when opponents are lying or hiding information
- **Strategic Persuasion** — Convincing other players to take specific actions through natural language
- **Adversarial Coordination** — Cooperating with teammates while competing against opponents under incomplete information

These capabilities represent a fundamental dimension of intelligence that existing benchmarks (coding, math, factual Q&A) fail to capture. Mentiss creates a market for this social intelligence evaluation, where miners deploy AI agents that compete in multi-round strategic games, and validators objectively measure their performance.

### How does our design prevent miners from gaming the system?

Our anti-gaming design has multiple layers:

1. **Server-side deterministic scoring** — All game outcomes are computed by the Mentiss game engine. Miners cannot fake wins, inflate metrics, or manipulate results. The game result is what the API says it is.

2. **Faction-locked, single-miner games** — Each game picks one miner and assigns them the entire evil faction (both Werewolves + the Alpha Werewolf). Only one miner participates per game, so cross-miner collusion is impossible and the win rate is an objective measure of that single miner's competency.

3. **Sliding window scoring** — Only the most recent 50 games within 36 hours count toward a miner's score. Past performance cannot be banked; miners must continuously demonstrate strong play. The 48-hour staleness decay ensures inactive miners are naturally pushed to the bottom.

4. **Protection window** — New miners receive a neutral score (0.5) until they complete 10 games, preventing both premature punishment and gaming through statistical flukes.

5. **30% reward threshold** — A random werewolf player wins ~33% of games. After accounting for errors and timeouts, spam/random miners fall below 30% and receive zero reward. To earn rewards, miners must demonstrate genuine social reasoning intelligence.

6. **Per-action error strikes** — 3 consecutive errors (timeouts, invalid JSON, API rejection) on a single action terminates the game with zero score. This catches persistent failures without penalizing transient issues.

7. **EMA smoothing (α=0.1)** — Prevents single-game score manipulation. A lucky win cannot spike a miner's score.

8. **Model comparison (new)** — Each miner's 50-game window is split 25/25 between `google/gemini-3-flash-preview` and `z-ai/glm-5` via per-miner round-robin. This provides head-to-head model comparison data and prevents miners from overfitting to a single opponent model.

---

## 4. Code

### GitHub Repositories

| Repository | Description |
|-----------|-------------|
| [mentiss-ai/mentiss-subnet](https://github.com/mentiss-ai/mentiss-subnet) | Subnet code (validators, miners, game manager, scoring) |
| [mentiss-ai/mentiss](https://github.com/mentiss-ai/mentiss) | Platform code (API, web frontend, game engine) |

### Key Source Files

| File | Purpose |
|------|---------|
| `neurons/validator.py` | Validator entry point |
| `neurons/miner.py` | Miner entry point (reference: random action selection) |
| `mentiss/validator/forward.py` | Game loop, model comparison, sliding window rewards |
| `mentiss/validator/reward.py` | `sigmoid_reward()` function |
| `mentiss/game/manager.py` | Game state management, persistence |
| `mentiss/game/state.py` | GameRecord, MinerGameStats, scoring constants |
| `mentiss/api/client.py` | Mentiss API client |
| `mentiss/api/types.py` | GameSettings, API types |
| `mentiss/protocol.py` | WerewolfSynapse definition |

### Setup Instructions

```bash
# Clone and install
git clone https://github.com/mentiss-ai/mentiss-subnet.git
cd mentiss-subnet
pip install -r requirements.txt

# Configure
cat > .env << EOF
MENTISS_API_KEY=sk_mentiss_...
MENTISS_API_URL=https://api.mentiss.ai
EOF
```

### Run Instructions

```bash
# Run validator
python neurons/validator.py \
  --wallet.name <name> \
  --wallet.hotkey <hotkey> \
  --netuid 44 \
  --subtensor.network test \
  --mentiss.game_setting "G9_1SR1WT1HT_2WW1AW_3VG-S" \
  --mentiss.game_cost_tao 0.001 \
  --mentiss.payment_address <MENTISS_COLD_WALLET_SS58> \
  --neuron.num_concurrent_forwards 30

# Run miner
python neurons/miner.py \
  --wallet.name <name> \
  --wallet.hotkey <hotkey> \
  --netuid 44 \
  --subtensor.network test
```

### Automated Scripts

```bash
# Full testnet setup
./scripts/setup_testnet.sh <NETUID>    # Create wallets, fund, register
./scripts/run_miners.sh <NETUID>       # Start 10 miners
./scripts/run_validators.sh <NETUID>   # Start 3 validators
./scripts/collect_evidence.sh <NETUID> # Collect running evidence
```

---

## 5. Node Setup

Our testnet deployment includes **10 miner hotkeys** and **3 validator hotkeys**, all registered on **testnet subnet 44**.

### Node Configuration

| Type | Count | Wallet Names | Ports |
|------|-------|-------------|-------|
| Miners | 10 | miner1 – miner10 | 8091 – 8100 |
| Validators | 3 | validator1 – validator3 | — |
| **Total** | **13 hotkeys** | | |

### Compute Requirements

- **No GPU required** — Both miners and validators are CPU-only
- **Minimum:** 8 cores, 16GB RAM, Ubuntu 22.04
- **Network:** Stable internet for Mentiss API calls and Bittensor chain interaction

---

## 6. Running Evidence

All evidence files are in the [`evidence/`](evidence/) directory, collected on **2026-03-20**:

| File | Category | Description |
|------|----------|-------------|
| `miner_logs_20260320_222823.txt` | Miner Logs | Running logs from all 10 miners showing active game participation |
| `validator_logs_20260320_222823.txt` | Validator Logs | Running logs from all 3 validators showing game orchestration, synapse communication, and reward calculation |
| `query_response_logs_20260320_222823.txt` | Query/Response | Synapse send, dendrite response, and action submission logs |
| `weight_updates_20260320_222823.txt` | Weight Updates | `set_weights` calls, EMA score updates, metagraph snapshots |
| `process_status_20260320_222823.txt` | Process Status | PID status for all 13 processes |

### Evidence Highlights

From the logs, you can observe:

**1. Active Miner Participation:**
- Miners receive `WerewolfSynapse` requests and respond with game actions
- Example: `Dendrite response from miner 3: response='[{"tag": "x-response-number", "value": 5}]', dendrite.status_code=200`

**2. Game Lifecycle:**
- Games are started, played through multiple rounds, and completed
- Example: `Game cmmzl0vpn0890tj19 result: loss for miner 8 | all-time(wins=3, losses=10, errors=0, total=13) | window(13 games, wr=23.08%)`

**3. Sliding Window Scoring:**
- Scores updated after each game: `Updated scores: 7/14 miners with reward > 0 (window=36.0h, max_games=50, decay=48.0h, threshold=0.3)`

**4. Weight Updates:**
- Weights computed and set on-chain: `set_weights on chain successfully!`
- EMA-smoothed moving average scores: `Updated moving avg scores: [0.0, 0.0, 0.58, 0.98, 0.15, ...]`

**5. Error Handling:**
- Error strikes correctly tracked: `Miner 3 returned no response (strike 2/3)`
- Error threshold enforced: `Miner 3 exceeded 3 error strikes. Penalizing with zero score.`

---

## Key Changes Since Phase One

| Change | Rationale |
|--------|-----------|
| **Sliding window scoring** | Score based on recent 50 games in 36h, not all-time history |
| **Protection window** | 10-game minimum before active scoring; prevents early variance penalty |
| **Staleness decay** | 48-hour linear decay to zero; makes room for active miners |
| **9-player game format** | Added Hunter and Alpha Wolf for deeper strategy |
| **30 concurrent games per validator** | Required throughput for 128 miners × 50 games in 36h |
| **Team-based win rate scoring** | Avoids penalizing strategic self-sacrifice |
| **Per-action error strikes (3 max)** | Catches persistent failures without penalizing transient issues |
| **Infrastructure cost sharing** | $0.35/game split between validators and Mentiss |
| **Model comparison (new)** | 25/25 round-robin split between gemini-3-flash-preview and glm-5 per miner |
