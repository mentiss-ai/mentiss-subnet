# Testnet Development Guide

This guide walks through setting up and running the Mentiss subnet on the Bittensor testnet.

## Prerequisites

- Python 3.10+
- A Mentiss API key (set as `MENTISS_API_KEY` env var or pass via `--mentiss.api_key`)
- Testnet TAO for registration (get from the [Bittensor faucet](https://faucet.opentensor.ai))

## 1. Install Dependencies

```bash
git clone https://github.com/mentiss-ai/mentiss-subnet.git
cd mentiss-subnet
pip install -e .
```

Or install from requirements:

```bash
pip install -r requirements.txt
pip install -e .
```

## 2. Create Wallets

Create separate wallets for validator and miner:

```bash
# Validator wallet
btcli wallet create --wallet.name validator --wallet.hotkey default

# Miner wallet(s)
btcli wallet create --wallet.name miner1 --wallet.hotkey default
btcli wallet create --wallet.name miner2 --wallet.hotkey default
btcli wallet create --wallet.name miner3 --wallet.hotkey default
```

## 3. Get Testnet TAO

Fund your wallets with testnet TAO:

```bash
btcli wallet faucet --wallet.name validator --subtensor.network test
btcli wallet faucet --wallet.name miner1 --subtensor.network test
```

## 4. Register on Testnet

Register your wallets on the subnet:

```bash
# Register validator
btcli subnet register \
  --wallet.name validator \
  --wallet.hotkey default \
  --subtensor.network test \
  --netuid <TESTNET_NETUID>

# Register miner
btcli subnet register \
  --wallet.name miner1 \
  --wallet.hotkey default \
  --subtensor.network test \
  --netuid <TESTNET_NETUID>
```

Replace `<TESTNET_NETUID>` with the actual subnet netuid on testnet.

## 5. Run a Miner

The reference miner selects random actions. Replace this with your own strategy.

```bash
python neurons/miner.py \
  --wallet.name miner1 \
  --wallet.hotkey default \
  --subtensor.network test \
  --netuid <TESTNET_NETUID> \
  --axon.port 8091 \
  --logging.debug
```

To run multiple miners on the same machine, use different ports:

```bash
# Terminal 1
python neurons/miner.py --wallet.name miner1 --axon.port 8091 ...

# Terminal 2
python neurons/miner.py --wallet.name miner2 --axon.port 8092 ...

# Terminal 3
python neurons/miner.py --wallet.name miner3 --axon.port 8093 ...
```

## 6. Run a Validator

```bash
export MENTISS_API_KEY="sk_mentiss_..."

python neurons/validator.py \
  --wallet.name validator \
  --wallet.hotkey default \
  --subtensor.network test \
  --netuid <TESTNET_NETUID> \
  --logging.debug
```

### Validator Configuration

For testnet development, you may want to adjust these defaults:

```bash
python neurons/validator.py \
  --wallet.name validator \
  --wallet.hotkey default \
  --subtensor.network test \
  --netuid <TESTNET_NETUID> \
  --mentiss.game_setting "G9_1SR1WT1HT_2WW1AW_3VG-S" \
  --mentiss.reward_threshold 0.30 \
  --mentiss.reward_steepness 20.0 \
  --mentiss.games_per_cycle 1 \
  --mentiss.weight_win_rate 0.5 \
  --mentiss.weight_game_dominance 0.25 \
  --mentiss.weight_vote_influence 0.25 \
  --mentiss.poll_interval 2.0 \
  --neuron.epoch_length 100 \
  --logging.debug
```

See [validation-logic.md](./validation-logic.md) for details on each parameter.

## 7. Game Settings

The `--mentiss.game_setting` string defines the player composition:

| Setting | Players | Composition |
|---------|---------|-------------|
| `G9_1SR1WT1HT_2WW1AW_3VG-S` | 9 | 1 Seer, 1 Witch, 1 Hunter, 3 Villagers, 2 Werewolves, 1 Alpha Werewolf (default) |

The selected miner controls the **entire evil faction** via faction-level model assignment — all 3 werewolves (2 WW + 1 Alpha) route every action back to the same miner. The 6 good-faction players are controlled by a single Mentiss-managed model per game.

## 8. Developing a Miner

The reference miner (`neurons/miner.py`) makes random choices. To build a competitive miner:

### Key Files

- `neurons/miner.py` - Entry point. Modify `forward()` and `_select_action()`.
- `mentiss/protocol.py` - `WerewolfSynapse` defines the data contract.

### The Synapse

The validator sends a `WerewolfSynapse` with:

| Field | Type | Description |
|-------|------|-------------|
| `game_id` | str | Unique game identifier |
| `player_id` | str | Your player's ID in the game |
| `role` | str | The specific role of the acting player this turn (e.g. "werewolf", "alpha_wolf"). Because the miner controls the entire evil faction, this rotates across seats within a single game. |
| `game_context` | str (JSON) | Full game state: phase, players, actions, logs |
| `pending_action` | str (JSON) | Available options and prompt |
| `phase` | str | Current phase ("night" / "day") |
| `sub_phase` | str | Current sub-phase (e.g. "round_vote", "round_speech") |
| `round_number` | int | Current round number |

Your miner should return `synapse.response` as a JSON string containing an array of action responses matching the options in `pending_action`.

### Scoring Tips

Your miner is scored on three metrics (see [validation-logic.md](./validation-logic.md)):

1. **Win Rate (50%)** - Win as many games as possible
2. **Game Dominance (25%)** - Keep your werewolf teammates alive
3. **Vote Influence (25%)** - Persuade good players to vote with you

Focus on:
- **Deception**: Craft believable day speeches that hide your werewolf identity
- **Strategic voting**: Guide the village to vote out key good-faction roles (Seer, Witch)
- **Self-preservation**: Avoid getting voted out or targeted by special roles
- **Coordination**: You control all three evil seats yourself, so night-phase discussions, kill targets, and day-phase speeches should be planned as a unified strategy across all three characters

## 9. Debugging

### Check Validator Logs

The validator logs each game's outcome:

```
Game abc123 ended: win (faction=evil, winner=werewolf, dominance=0.67, vote_influence=0.45, survived=True)
Updated scores from composite metrics
```

### Inspect Game Stats

Game stats are persisted to `game_stats.json` in the neuron's data directory:

```bash
cat ~/.bittensor/validators/<wallet_name>/<hotkey>/netuid<N>/validator/game_stats.json | python3 -m json.tool
```

### Check Weights

```bash
btcli subnet metagraph --netuid <TESTNET_NETUID> --subtensor.network test
```

### Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| "MENTISS_API_KEY not set" | Missing API key | Set `MENTISS_API_KEY` env var or pass `--mentiss.api_key` |
| "No available miners" | No registered miners on subnet | Register a miner first |
| "Failed to start game" | API error or invalid game setting | Check API key and `--mentiss.game_setting` value |
| Miner returns no response | Miner timeout or crash | Check miner logs, increase `MINER_TIMEOUT` if needed |
| Scores all zero | Not enough games played | Lower `--mentiss.games_per_cycle` or wait for more games |

## 10. Development Workflow

A typical testnet development cycle:

1. **Start local miner(s)** with `--logging.debug`
2. **Start local validator** pointing to the same testnet
3. **Watch logs** to see games being played and scores updating
4. **Iterate on miner strategy** - modify `_select_action()` in `neurons/miner.py`
5. **Check metagraph** to see weight changes taking effect
6. **Review game_stats.json** to analyze per-metric performance

### Running Validator + Miner on the Same Machine

This is common during development. Make sure to:
- Use different wallet names for validator and miner
- Assign different axon ports to each miner
- Both connect to the same `--subtensor.network test` and `--netuid`
