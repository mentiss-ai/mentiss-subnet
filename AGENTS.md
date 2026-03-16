# Mentiss Subnet

Bittensor subnet where AI miners compete in Werewolf (social deduction) games. Validators run games via the Mentiss API and score miners based on three deterministic metrics.

## Tech Stack

- Python 3.10+
- Bittensor SDK (`bittensor >= 9.10.1`)
- Async HTTP via `httpx`
- NumPy for score arrays and weight computation

## Project Structure

```
mentiss/
  api/          # Mentiss API client (tRPC over HTTP)
    client.py   # MentissAPIClient: start_game, get_status, submit_action, get_player_stats
    types.py    # Request/response dataclasses
  base/         # Bittensor neuron base classes
    validator.py  # BaseValidatorNeuron: score EMA, weight setting, metagraph sync
    miner.py      # BaseMinerNeuron: axon serving
    utils/        # Weight normalization utilities
  game/         # Game state tracking
    state.py    # MinerGameStats (cumulative metrics), GameResult, GameOutcome
    manager.py  # GameManager: per-miner stat accumulation, persistence to game_stats.json
  validator/    # Validator-specific logic
    forward.py  # Game orchestration loop, metric collection, reward updates
    reward.py   # sigmoid_reward(), composite_score(), determine_game_result()
  utils/        # Shared utilities
    config.py   # All CLI args (neuron + mentiss-specific)
    uids.py     # Miner UID selection
neurons/
  validator.py  # Validator entry point
  miner.py      # Reference miner (random actions)
docs/
  validation-logic.md      # Scoring system documentation
  testnet-development.md   # Testnet setup guide
```

## Key Concepts

- **Composite Score**: `0.5 * win_rate + 0.25 * game_dominance + 0.25 * vote_influence`
- **Sigmoid Reward**: Hard cutoff at 30% composite score, steep curve above
- **EMA Scores**: `scores = 0.1 * new_rewards + 0.9 * scores`
- Weights are set on-chain every 100 blocks

## Coding Conventions

- Strong typing, avoid `any`.
- Async for all API calls (httpx).
- Sequential external requests (no `asyncio.gather` for API calls) to avoid rate limits.
- One class/function per file where practical. Split complex logic into `service` or `components` folders.
- Keep functions focused. If a function grows beyond ~100 lines, split it.

## Development Workflow

1. Make changes
2. Compile check: `python -m py_compile <file>`
3. Test locally against testnet (see `docs/testnet-development.md`)

## API Endpoints Used

All via `MentissAPIClient` -> `https://api.mentiss.ai/api/trpc/`:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `playRouter.start` | POST | Start a new game |
| `playRouter.status` | GET | Poll game state |
| `playRouter.submitAction` | POST | Submit player action |
| `playRouter.playerStats` | GET | Get per-player scoring metrics (after game completes) |

## Rules

- When modifying scoring or validation logic, always update `docs/validation-logic.md` to keep documentation in sync.

## Important Files to Read First

- `docs/validation-logic.md` for the complete scoring system
- `mentiss/validator/forward.py` for the main game loop
- `mentiss/validator/reward.py` for score computation
- `neurons/miner.py` for the miner interface
