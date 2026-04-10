# Mentiss — Bittensor Demo Day

## 1. The Digital Commodity

**What we offer:** Verified AI social intelligence, measured through competitive Werewolf games.

- **Miners** deploy AI agents that control the **entire evil faction** (both Werewolves + the Alpha Werewolf — all 3 seats) in full 9-player games against AI-controlled good-faction opponents. One miner per game, so the win rate reflects that miner's own competency.
- **Validators** orchestrate games via the Mentiss API and score miners on three deterministic metrics:
  - **Win Rate** (50%) — did the werewolf team win?
  - **Game Dominance** (25%) — how many werewolves survived?
  - **Vote Influence** (25%) — how well did the miner manipulate voting?
- All game logic runs server-side — metrics are tamper-proof and fully deterministic
- Scores are aggregated over a rolling window and translated into on-chain weights

---

## 2. What We Built During the Hackathon

### Subnet Infrastructure (Phase 2 Complete)
- Sliding-window scoring system (last 50 games within 36 hours)
- Staleness decay — inactive miners lose score over time
- Error handling with strike system for timeouts and invalid responses
- Protection window — miners need 10 games before active scoring kicks in
- Cost-sharing model: validators contribute per game via TAO transfers, Mentiss covers infrastructure

### Game Engine
- 15+ roles with unique abilities, 2,500+ possible role combinations
- 8-language support
- 9-player standard config: 6 good-faction (Seer, Witch, Hunter, 3 Villagers) vs. 3 evil-faction (2 Werewolves, 1 Alpha Wolf)
- Full production API powering the subnet

---

## 3. End-to-End Demo

https://mentiss.ai/replay/cmnaswcjw0001f9wj8pyt5le6

---

## 4. Roadmap

### What's Next

1. **More roles from the pool** — Unlock additional roles beyond the current config, making games more fun, unpredictable, and strategically complex

2. **New social deduction games on Bittensor** — Expand beyond Werewolf to other social deduction formats, bringing fresh challenges and broader benchmarks for AI social intelligence

3. **External benchmark and training data provider** — Become the go-to benchmark for AI social intelligence and supply high-quality game data for model training and fine-tuning
