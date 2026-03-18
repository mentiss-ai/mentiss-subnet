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

> [forward.py:42-49](file:///Users/jeremywang/mentiss-ai/mentiss-subnet/mentiss/validator/forward.py#L42-L49)

### Step 2: Start a Game
The validator calls the **Mentiss API** to create a Werewolf game:
- Game setting: `G6_1SR1WT_2WW_2VG-H` (6 players: 1 Seer, 1 Witch, 2 Werewolves, 2 Villagers)
- The miner controls **one werewolf** (the "human" player in `-H` mode)
- The other 5 players are AI-controlled by the Mentiss API

> [forward.py:56-63](file:///Users/jeremywang/mentiss-ai/mentiss-subnet/mentiss/validator/forward.py#L56-L63)

### Step 3: Game Loop
The validator orchestrates the game in a loop:

```
repeat until game over (max 100 rounds):
    1. Poll Mentiss API for game status
    2. If game needs miner input:
       a. Package game state into WerewolfSynapse
       b. Send synapse to miner via Bittensor dendrite
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

> [forward.py:83-197](file:///Users/jeremywang/mentiss-ai/mentiss-subnet/mentiss/validator/forward.py#L83-L197)

### Step 4: Game Ends → Collect Metrics
When the game finishes, the validator fetches **player stats** from the Mentiss API:

| Metric | What it measures | Range |
|--------|-----------------|-------|
| **Win/Loss** | Did the werewolf team win? | binary |
| **Game Dominance** | How many of the miner's werewolf teammates survived? Higher = miner protected the pack well | 0.0 - 1.0 |
| **Vote Influence** | Did the miner persuade good players to vote with them during day phase? Higher = better deceiver | 0.0 - 1.0 |
| **Survived** | Did the miner's werewolf survive until the end? | boolean |

> [forward.py:100-131](file:///Users/jeremywang/mentiss-ai/mentiss-subnet/mentiss/validator/forward.py#L100-L131)

### Step 5: Composite Score
The scoring is **win-gated**: losses always receive 0 reward. Wins are scored by quality:

```
if win_rate == 0  → score = 0 (never won, no reward)
if win_rate > 0   → score = 0.50 × win_rate
                         + 0.50 × win_rate × quality

where quality = average of game_dominance and vote_influence
```

This means:
- **Lucky wins** (low dominance, low influence) → lower score (0.55)
- **Dominant wins** (high dominance, high influence) → higher score (0.875)
- **Losses** → always 0, regardless of how well the miner played

> [reward.py:36-68](file:///Users/jeremywang/mentiss-ai/mentiss-subnet/mentiss/validator/reward.py#L36-L68)

### Step 6: Sigmoid Reward
The composite score is passed through a **sigmoid function** with a hard cutoff:

```
                reward
                  1.0 ─────────────────────────
                      │                /
                      │               /
                      │              /  ← steep sigmoid curve
                      │             /
                  0.0 ─────────────┤
                      0    0.3    0.5    0.7    1.0
                           ↑                        composite score
                        threshold
                     (hard cutoff)
```

- **Below 0.30 threshold** → reward = 0 (no reward for spam/random miners)
- **Above 0.30** → sigmoid curve from 0 to 1 (better play = exponentially more reward)
- **Steepness = 20** → very sharp transition around the threshold

> [reward.py:18-33](file:///Users/jeremywang/mentiss-ai/mentiss-subnet/mentiss/validator/reward.py#L18-L33)

### Step 7: Set Weights on Chain
The rewards array is passed to `self.update_scores()`, which feeds into Bittensor's `set_weights` mechanism. This determines how much TAO each miner earns.

> [forward.py:200-228](file:///Users/jeremywang/mentiss-ai/mentiss-subnet/mentiss/validator/forward.py#L200-L228)

---

## Malicious Miner Protection

The validator tracks **error strikes** per miner per game. Errors include:
- No response (timeout or empty)
- Invalid JSON format
- Action submission failures

**After 3 strikes in a single game**, the validator:
1. Stops the game immediately (saves API resources)
2. Records the game as an `ERROR` (zero score)
3. Logs the penalty for auditability

Successful actions **reset the strike counter**, so occasional network hiccups are tolerated.

For multi-miner games (3 miners controlling 3 werewolves), each miner is scored independently — one bad miner doesn't penalize the others.

---

## Why This Design is Strong (for Hackathon Judges)

### Anti-Gaming
- **Metrics come from the Mentiss API**, not self-reported by miners
- The API runs the actual game logic — miners can't fake wins
- The sigmoid threshold ensures random/spam miners get **zero reward**
- **Error strike system** catches malicious miners sending garbage responses

### Proof of Intelligence
- Werewolf requires **real reasoning**: deception, persuasion, strategic voting
- A random miner will have ~33% win rate as werewolf, which is **below the 0.30 threshold**
- To earn rewards, miners must demonstrably outperform random play

### Win-Gated Scoring
- **Losses always get 0** — no participation trophies
- Win rate determines how **often** rewards happen
- Game dominance + vote influence determine **how much** reward per win
- A miner who wins through luck gets less than one who dominates

### Transparency
- All scoring logic is open-source in `reward.py`
- Game stats persist to `game_stats.json` for auditability
- Weights are set on-chain, verifiable by anyone
