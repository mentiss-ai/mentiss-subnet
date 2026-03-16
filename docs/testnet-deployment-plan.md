# Mentiss Subnet — Bittensor Testnet Deployment Plan

This document is a step-by-step plan to validate that the Mentiss Werewolf subnet can be deployed and operated on the Bittensor testnet. No code changes are required — this is purely an operational checklist.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Environment Setup](#2-environment-setup)
3. [Wallet Creation](#3-wallet-creation)
4. [Obtain Testnet TAO](#4-obtain-testnet-tao)
5. [Create the Subnet on Testnet](#5-create-the-subnet-on-testnet)
6. [Register Neurons (Validator + Miners)](#6-register-neurons-validator--miners)
7. [Configure and Launch Miners](#7-configure-and-launch-miners)
8. [Configure and Launch the Validator](#8-configure-and-launch-the-validator)
9. [Validation Checklist — What to Verify](#9-validation-checklist--what-to-verify)
10. [Enable Emissions (Root Network)](#10-enable-emissions-root-network)
11. [Invite External Miners](#11-invite-external-miners)
12. [Troubleshooting](#12-troubleshooting)
13. [Teardown / Cleanup](#13-teardown--cleanup)

---

## 1. Prerequisites

Before you begin, make sure you have:

| Requirement | Details |
|---|---|
| **Python 3.10+** | Required by the subnet code and Bittensor SDK |
| **Bittensor SDK & CLI** | `bittensor >= 9.10.1` and `bittensor-cli >= 9.10.1` (installed via `requirements.txt`) |
| **Mentiss API key** | Obtain from the Mentiss team; needed by the validator to run games |
| **A server or machine** | For running the validator (and optionally test miners). A VPS or cloud instance with a public IP is recommended so miners can reach the validator's dendrite |
| **Discord access** | Join the [Bittensor Discord](https://discord.gg/bittensor) — needed to request testnet TAO |

---

## 2. Environment Setup

```bash
# Clone the repo (if not already done)
git clone https://github.com/mentiss-ai/mentiss-subnet.git
cd mentiss-subnet

# Create a virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -e .

# Verify bittensor CLI is available
btcli --version
```

Confirm the Mentiss package is importable:

```bash
python -c "import mentiss; print(mentiss.__version__)"
```

---

## 3. Wallet Creation

You need **three wallets**: one subnet owner, one validator, and at least one miner. The owner creates and controls the subnet; the validator and miner are registered as neurons on it.

```bash
# --- Subnet Owner ---
btcli wallet new_coldkey --wallet.name owner
# (No hotkey needed for the owner — it only owns the subnet)

# --- Validator ---
btcli wallet new_coldkey --wallet.name validator
btcli wallet new_hotkey --wallet.name validator --wallet.hotkey default

# --- Miner 1 ---
btcli wallet new_coldkey --wallet.name miner1
btcli wallet new_hotkey --wallet.name miner1 --wallet.hotkey default

# --- (Optional) Miner 2 & 3 for multi-miner testing ---
btcli wallet new_coldkey --wallet.name miner2
btcli wallet new_hotkey --wallet.name miner2 --wallet.hotkey default

btcli wallet new_coldkey --wallet.name miner3
btcli wallet new_hotkey --wallet.name miner3 --wallet.hotkey default
```

**Security note:** These are testnet-only wallets. Never reuse mainnet passwords or keys. Store the mnemonics in a safe place for the duration of testing.

Verify your wallets exist:

```bash
btcli wallet list
```

---

## 4. Obtain Testnet TAO

The automated faucet is **disabled** on the Bittensor testnet. You must request test TAO manually:

1. Join the [Bittensor Discord](https://discord.gg/bittensor).
2. Go to the appropriate faucet or testnet channel.
3. Post your **owner** coldkey address and request **at least 150 test TAO** (100+ for subnet creation, plus extra for registration fees and transaction costs).
4. Also request test TAO for your **validator** and **miner** wallets (a few TAO each for registration).

Check your balances:

```bash
btcli wallet balance --wallet.name owner --subtensor.network test
btcli wallet balance --wallet.name validator --subtensor.network test
btcli wallet balance --wallet.name miner1 --subtensor.network test
```

**You need at minimum:**
- Owner: ~100+ TAO (subnet creation lock cost — this is returned when subnet is deregistered)
- Validator: ~1-5 TAO (for registration recycling cost)
- Each miner: ~1-5 TAO (for registration recycling cost)

The exact costs are dynamic. Check the current lock cost with:

```bash
btcli subnet lock_cost --subtensor.network test
```

---

## 5. Create the Subnet on Testnet

Once the owner wallet is funded:

```bash
btcli subnet create \
  --wallet.name owner \
  --subtensor.network test
```

This will prompt you to confirm the TAO lock cost. Once confirmed, the chain assigns a **netuid** to your new subnet. **Write this number down** — you will use it in every subsequent command.

```bash
# Verify your subnet exists
btcli subnet list --subtensor.network test
```

Look for your subnet in the list and confirm the netuid.

**Important:** New subnets have an **activation delay** of approximately 7 × 7200 blocks (~1 week) before they can fully operate with emissions. During this period you can still register neurons and run validators/miners, but weight-setting and emissions won't be active until the subnet activates. Use this time to test the game loop and debugging.

---

## 6. Register Neurons (Validator + Miners)

Register the validator and miner(s) on your new subnet. Replace `<NETUID>` with the number from step 5.

```bash
# Register validator
btcli subnet register \
  --netuid <NETUID> \
  --wallet.name validator \
  --wallet.hotkey default \
  --subtensor.network test

# Register miner 1
btcli subnet register \
  --netuid <NETUID> \
  --wallet.name miner1 \
  --wallet.hotkey default \
  --subtensor.network test

# (Optional) Register additional miners
btcli subnet register \
  --netuid <NETUID> \
  --wallet.name miner2 \
  --wallet.hotkey default \
  --subtensor.network test

btcli subnet register \
  --netuid <NETUID> \
  --wallet.name miner3 \
  --wallet.hotkey default \
  --subtensor.network test
```

Verify registrations:

```bash
btcli wallet overview --wallet.name validator --subtensor.network test
btcli wallet overview --wallet.name miner1 --subtensor.network test

# Or view the full metagraph:
btcli subnet metagraph --netuid <NETUID> --subtensor.network test
```

You should see your validator and miner UIDs listed.

---

## 7. Configure and Launch Miners

Each miner needs its own terminal/process and a unique axon port.

**Terminal 1 — Miner 1:**

```bash
cd mentiss-subnet
source .venv/bin/activate

python neurons/miner.py \
  --wallet.name miner1 \
  --wallet.hotkey default \
  --subtensor.network test \
  --netuid <NETUID> \
  --axon.port 8091 \
  --logging.debug
```

**Terminal 2 — Miner 2 (optional):**

```bash
python neurons/miner.py \
  --wallet.name miner2 \
  --wallet.hotkey default \
  --subtensor.network test \
  --netuid <NETUID> \
  --axon.port 8092 \
  --logging.debug
```

**Terminal 3 — Miner 3 (optional):**

```bash
python neurons/miner.py \
  --wallet.name miner3 \
  --wallet.hotkey default \
  --subtensor.network test \
  --netuid <NETUID> \
  --axon.port 8093 \
  --logging.debug
```

**What to look for:**
- Miner logs should show `Miner running...` heartbeat messages
- No import errors or crash on startup
- The axon should bind to the specified port

**Note:** The reference miner (`neurons/miner.py`) uses random action selection. This is fine for testnet validation — you are testing infrastructure, not AI strategy.

---

## 8. Configure and Launch the Validator

The validator requires the **Mentiss API key** to start and run Werewolf games.

```bash
cd mentiss-subnet
source .venv/bin/activate

export MENTISS_API_KEY="sk_mentiss_your_key_here"

python neurons/validator.py \
  --wallet.name validator \
  --wallet.hotkey default \
  --subtensor.network test \
  --netuid <NETUID> \
  --mentiss.game_setting "G6_1SR1WT_2WW_2VG-H" \
  --mentiss.games_per_cycle 1 \
  --mentiss.poll_interval 2.0 \
  --neuron.epoch_length 100 \
  --logging.debug
```

**What to look for in validator logs:**
1. `Started game: <game_id>` — confirms Mentiss API connectivity
2. `Selected miner UID <N> for Werewolf game` — confirms metagraph sees miners
3. `Submitted action for game <game_id>` — confirms miner communication works (dendrite → axon → response)
4. `Game <game_id> ended: win/loss ...` — confirms full game loop completion
5. `Updated scores from composite metrics` — confirms reward computation ran

---

## 9. Validation Checklist — What to Verify

This is the core of the testnet plan. Each item should be checked off to confirm the subnet is working end-to-end.

### Phase A: Infrastructure (no games yet)

- [ ] All wallets created and funded with testnet TAO
- [ ] Subnet created and netuid confirmed via `btcli subnet list`
- [ ] Validator and at least 1 miner registered on the subnet
- [ ] Miner process starts without errors and serves the axon
- [ ] Validator process starts without errors
- [ ] Validator can see miners in the metagraph (`Selected miner UID ...` in logs)

### Phase B: Game Loop (single game)

- [ ] Validator starts a game via the Mentiss API (`Started game: ...`)
- [ ] Validator polls game status successfully (no API errors in logs)
- [ ] Validator sends `WerewolfSynapse` to miner via dendrite
- [ ] Miner receives the synapse and returns a response (check miner logs for `Responding with action: ...`)
- [ ] Validator submits the miner's action back to the API (`Submitted action for game ...`)
- [ ] Game completes — validator logs `Game <id> ended: win/loss`
- [ ] Validator fetches player stats post-game (`game_dominance`, `vote_influence` values visible in log)
- [ ] `game_stats.json` is created/updated in the validator's data directory

### Phase C: Scoring and Weights

- [ ] Validator computes composite scores and sigmoid rewards (`Updated scores from composite metrics`)
- [ ] After running multiple games, check that score array is non-zero for active miners
- [ ] After `epoch_length` blocks (default 100), validator attempts to set weights on-chain
- [ ] Confirm weights via: `btcli subnet metagraph --netuid <NETUID> --subtensor.network test`
- [ ] Miners that played games should have non-zero weights; inactive UIDs should have zero

### Phase D: Multi-Miner (scaling test)

- [ ] Run 2-3 miners simultaneously, each on different ports
- [ ] Validator plays games against different miners over time (random UID selection)
- [ ] `game_stats.json` shows stats accumulated for multiple miner UIDs
- [ ] Weights reflect relative performance across miners

### Phase E: Persistence and Recovery

- [ ] Stop the validator (`Ctrl+C`)
- [ ] Restart the validator — confirm it loads saved state (`load_state()` in logs)
- [ ] Verify `game_stats.json` stats survived the restart
- [ ] Confirm the validator resumes game cycles without issues

---

## 10. Enable Emissions (Root Network)

Once the subnet is activated (after the ~1 week activation delay), you can enable emissions by registering on the root network and setting root weights:

```bash
# Register the validator on the root network
btcli root register \
  --wallet.name validator \
  --wallet.hotkey default \
  --subtensor.network test

# Set root weights to direct emissions to your subnet
btcli root weights --subtensor.network test
```

This step is optional for basic testnet validation but is required to test the full incentive loop with emissions.

---

## 11. Invite External Miners

Once the basic validation (Phases A-E) is complete, you can invite others to mine on your testnet subnet. They need:

1. **Your subnet's netuid** on testnet
2. **Testnet TAO** for registration (direct them to Discord)
3. **The Mentiss subnet repo** to install and run the miner
4. **A guide** — point them to `docs/testnet-development.md` (sections 1-8 cover miner setup)

Provide them with:

```
Subnet netuid:  <NETUID>
Network:        test (testnet)
Repo:           https://github.com/mentiss-ai/mentiss-subnet
Miner command:  python neurons/miner.py \
                  --wallet.name <their_wallet> \
                  --wallet.hotkey default \
                  --subtensor.network test \
                  --netuid <NETUID> \
                  --axon.port <their_port> \
                  --logging.debug
```

---

## 12. Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| `btcli subnet create` fails with insufficient balance | Owner wallet underfunded | Request more testnet TAO from Discord |
| Validator logs `No available miners` | Miners not registered or not running | Check `btcli subnet metagraph`, ensure miners are up |
| Validator logs `MENTISS_API_KEY not set` | Missing or incorrect env var | `export MENTISS_API_KEY="sk_mentiss_..."` |
| Validator logs `Failed to start game` | Bad API key or invalid game setting | Verify API key works; check `--mentiss.game_setting` |
| Miner logs `Missing dendrite or hotkey` | Validator not registered or blacklist issue | Ensure validator is registered on the same netuid |
| `Dendrite error for miner <uid>` | Miner unreachable (port/firewall) | Ensure miner axon port is open and miner is running |
| Weights not changing | Not enough blocks elapsed | Wait for `epoch_length` (100) blocks (~20 minutes on testnet) |
| Weights all zero | No games completed or below threshold | Lower `--mentiss.reward_threshold` for testing, or play more games |
| Subnet not emitting | Activation delay not elapsed | Wait ~1 week after subnet creation, then register on root |

---

## 13. Teardown / Cleanup

When testing is complete:

1. Stop all miner and validator processes (`Ctrl+C`)
2. Optionally deregister from the subnet to reclaim test TAO:
   ```bash
   btcli subnet list --subtensor.network test
   ```
3. Testnet wallets can be safely deleted if no longer needed — they hold no real value

---

## Timeline Estimate

| Phase | Duration | Notes |
|---|---|---|
| Setup (steps 1-4) | 1-2 days | Most time spent waiting for testnet TAO from Discord |
| Subnet creation + registration (steps 5-6) | 30 minutes | Quick once funded |
| Activation delay | ~1 week | Chain-enforced; can test game loop during this time |
| Basic validation (steps 7-9, Phases A-C) | 1-2 days | Running games and checking logs |
| Multi-miner and persistence tests (Phases D-E) | 1 day | |
| External miner invitations (step 11) | Ongoing | After internal validation passes |

---

## References

- [Bittensor: Create a Subnet](https://docs.learnbittensor.org/subnets/create-a-subnet)
- [Bittensor Subnet Template: Running on Testnet](https://github.com/opentensor/bittensor-subnet-template/blob/main/docs/running_on_testnet.md)
- [Bittensor: Register, Validate and Mine](https://docs.learnbittensor.org/subnets/register-validate-mine/)
- [Mentiss Subnet: Testnet Development Guide](./testnet-development.md)
- [Mentiss Subnet: Validation Logic](./validation-logic.md)
