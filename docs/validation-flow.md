# How the Validator Evaluates Miner Performance

## The Big Picture

```
┌─────────────┐    ┌──────────────┐    ┌──────────────┐
│  Validator   │◄──►│  Mentiss API  │    │              │
│              │    │  (Game Host)  │    │   Bittensor   │
│  Picks miner │    │              │    │    Chain      │
│  Runs game   │    │  Runs the    │    │              │
│  Scores      │───►│  Werewolf    │    │  Receives    │
│  Sets weights│    │  game logic  │    │  set_weights │
│              │    │              │    │              │
└──────┬───────┘    └──────────────┘    └──────────────┘
       │
       │  WerewolfSynapse
       ▼
┌──────────────┐
│    Miner     │
│              │
│  Receives    │
│  game state  │
│  Returns     │
│  action      │
└──────────────┘
```

## Step-by-Step Flow

### Step 1: Pick a Miner
The validator randomly selects a miner UID from the metagraph.

### Step 2: Start a Game
The validator calls the **Mentiss API** to create a Werewolf game:
- Game setting: `G6_1SR1WT_2WW_2VG-H` (6 players: 1 Seer, 1 Witch, 2 Werewolves, 2 Villagers)
- The miner controls **one werewolf** (the "human" player in `-H` mode)
- The other 5 players are AI-controlled by the Mentiss API

### Step 3: Game Loop
The validator orchestrates the game in a loop (with a 1-hour safety cap):

```
repeat until game over:
    1. Poll Mentiss API for game status (every 2 seconds)
    2. If game needs miner input:
       a. Package game state into WerewolfSynapse
       b. Send synapse to miner via Bittensor dendrite (2-minute timeout)
       c. Miner returns action (speech, vote, kill target, etc.)
       d. Submit miner's action back to Mentiss API
    3. Wait for next poll
```

#### What the miner sees (WerewolfSynapse):
| Field | What it contains |
|-------|-----------------|
| `game_id` | Unique game identifier |
| `player_id` | Which player the miner controls |
| `role` | "werewolf" |
| `game_context` | Full game state: phase, players, god log, actions history |
| `pending_action` | Available options + prompt (e.g., "Who do you want to kill?") |
| `phase` | "night" or "day" |
| `sub_phase` | "round_vote", "round_speech", "werewolf_kill", etc. |

#### What the miner returns:
A JSON array of action responses matching the options in `pending_action`.

### Step 4: Game Ends → Record Result
When the game finishes, the validator determines **win or loss** based on the team outcome:

- **Werewolf team wins** → all miners on that team get a **WIN**
- **Villager team wins** → all miners on that team get a **LOSS**

All miners on the winning team receive **equal reward**, regardless of individual performance. This is intentional — strategic self-sacrifice (getting voted out early to protect teammates) is a legitimate Werewolf strategy.

### Step 5: Reward Calculation

The reward system is simple and fair:

```
score = win_rate  (wins ÷ completed games)
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
                     (hard cutoff)
```

| Win Rate | Reward | Explanation |
|----------|--------|-------------|
| 0% – 29% | **0.0** | Below threshold → zero reward |
| 30% | **0.5** | Threshold → sigmoid midpoint |
| 40% | **0.88** | Above threshold → rapidly increasing |
| 50%+ | **~1.0** | Strong performance → maximum reward |

**Why 30% threshold?** A random werewolf player wins ~33% of games. After accounting for errors and timeouts, a random/spam miner typically lands **below 30%** — earning zero. To get rewards, miners must demonstrate genuine social deduction intelligence.

### Step 6: Set Weights on Chain
The reward array is passed to `self.update_scores()`, which feeds into Bittensor's `set_weights` mechanism. This determines how much TAO each miner earns.

---

## Malicious Miner Protection

The validator tracks **error strikes per action call** (not cumulative across the game). Errors include:
- No response (timeout after 2 minutes)
- Invalid JSON format
- Action submission failures (API rejects the response)

**After 3 strikes on a single action**, the validator:
1. Stops the game immediately (saves API resources)
2. Records the game as an `ERROR` (zero score)
3. Logs the penalty for auditability

Each new action call **resets the strike counter to 0**, so a miner that recovers from a bad action gets a fresh start. Only persistent failure on a single action (3 consecutive bad responses) triggers the penalty.

### Constants
| Parameter | Value | Purpose |
|-----------|-------|---------|
| `MINER_TIMEOUT` | 120s (2 min) | Max time for miner to respond to a single action |
| `MAX_ERROR_STRIKES` | 3 | Max retries per action before penalty |
| Game loop safety cap | 1 hour | Prevents infinite loops from API bugs |
| `poll_interval` | 2s | How often the validator checks game status |

---

## Why This Design is Strong

### Anti-Gaming
- **Metrics come from the Mentiss API**, not self-reported by miners
- The API runs the actual game logic — miners can't fake wins
- The sigmoid threshold ensures random/spam miners get **zero reward**
- **Per-action error strikes** catch malicious miners sending garbage responses

### Proof of Intelligence
- Werewolf requires **real reasoning**: deception, persuasion, strategic voting
- A random miner lands below the 30% threshold → zero reward
- To earn rewards, miners must demonstrably outperform random play

### Team-Level Scoring
- All miners on the winning team get **equal reward**
- Strategic self-sacrifice is not penalized
- Win rate is the sole metric — simple, fair, hard to game

### Transparency
- All scoring logic is open-source in `reward.py`
- Game stats persist to `game_stats.json` for auditability
- Weights are set on-chain, verifiable by anyone
