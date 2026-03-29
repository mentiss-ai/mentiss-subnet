# Mentiss Subnet — 5-Minute Pitch

## 1. Game Setup

- 9-player Werewolf (social deduction) game on Bittensor testnet (subnet 44)
- Miners control the **evil faction** (2 Werewolves + 1 Alpha Werewolf)
- Good faction (3 Villagers, 1 Seer, 1 Witch, 1 Hunter) is AI-controlled by the Mentiss game engine
- All 6 good-faction players share the **same model** in each game — one model is randomly selected per game from a rotating pool
- Current model pool: `google/gemini-3-flash-preview`, `z-ai/glm-5`, `deepseek/deepseek-v3.2` (health-checked; only responsive models are included)
- Validators orchestrate games via the Mentiss API, send game state to miners as `WerewolfSynapse`, and submit miner responses back

## 2. Scoring

**Sliding Window Win Rate**
- Only the most recent **50 games within 36 hours** count
- New miners get a neutral score (0.5) until they complete **10 games** (protection window)
- Inactive miners decay linearly to zero over **48 hours**

**Sigmoid Reward**
- Win rate below **30%** = zero reward (random play wins ~33%, but errors/timeouts drag it below 30%)
- Above 30%, reward scales via sigmoid toward 1.0

**Staleness Decay**
- If a miner stops playing, their score decays linearly to zero over **48 hours**
- Frees up subnet slots for active miners

## 3. Anti-Gaming & Error Handling

- **Server-side scoring** — All game outcomes computed by Mentiss engine. Miners cannot fake wins.
- **Faction lock** — Miners always play werewolf. No cross-faction collusion possible.
- **Per-action error strikes** — 3 consecutive failures (timeout, invalid JSON, API rejection) on a single action → game terminated, zero score
- **2-minute timeout** per miner action response
- **1-hour max** per game (1800 polls × 2s)
- **Sliding window** — Can't ride on past wins. Must keep performing.
- **Staleness decay** — Stop playing → score drops to zero in 48h

## 4. Cost Sharing Between Validators and Mentiss

Each game costs ~**$0.70** (AI API calls for 9 players + infrastructure).

| | Per Game | Covers |
|--|----------|--------|
| **Validator pays** | $0.35 | AI API inference costs |
| **Mentiss absorbs** | $0.35 | Infrastructure, maintenance, development |

**How it works:**
- Validators buy credits in bulk via a single on-chain TAO transfer (default: 100 credits)
- Each game deducts 1 credit locally
- When credits run low, a new batch is auto-purchased
- One transaction per 100 games → ~100× fewer chain fees

**Why:**
- At scale (128 miners × 50 games/36h), AI costs reach $3,000+/day — unsustainable for one party
- Validators spend ~$504/day, earn ~$1,300/day in emissions → **~2.5× ROI**
- Every payment is an on-chain TAO transfer, fully auditable
