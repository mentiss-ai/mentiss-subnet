# Mentiss Subnet — Deployment Plan (Localnet → Testnet)

This document is a step-by-step plan to validate that the Mentiss Werewolf subnet works end-to-end. We start with **localnet** (a local blockchain on your machine — no real tokens, instant feedback) and then graduate to **testnet** (the public Bittensor test network).

No code changes are required — this is purely an operational checklist.

---

## Table of Contents

### Part 1: Localnet (Start Here)
1. [Localnet Prerequisites](#1-localnet-prerequisites)
2. [Start the Local Blockchain](#2-start-the-local-blockchain)
3. [Environment Setup](#3-environment-setup)
4. [Create Wallets](#4-create-wallets)
5. [Fund Wallets via Local Faucet](#5-fund-wallets-via-local-faucet)
6. [Create the Subnet Locally](#6-create-the-subnet-locally)
7. [Register Neurons](#7-register-neurons)
8. [Bootstrap Incentives (Stake)](#8-bootstrap-incentives-stake)
9. [Launch Miners on Localnet](#9-launch-miners-on-localnet)
10. [Launch the Validator on Localnet](#10-launch-the-validator-on-localnet)
11. [Localnet Validation Checklist](#11-localnet-validation-checklist)
12. [Enable Emissions on Localnet](#12-enable-emissions-on-localnet)
13. [Localnet Troubleshooting](#13-localnet-troubleshooting)
14. [Localnet Teardown](#14-localnet-teardown)

### Part 2: Testnet (After Localnet Passes)
15. [Testnet Prerequisites](#15-testnet-prerequisites)
16. [Obtain Testnet TAO](#16-obtain-testnet-tao)
17. [Create the Subnet on Testnet](#17-create-the-subnet-on-testnet)
18. [Register, Launch, and Validate on Testnet](#18-register-launch-and-validate-on-testnet)
19. [Enable Emissions on Testnet](#19-enable-emissions-on-testnet)
20. [Invite External Miners](#20-invite-external-miners)
21. [Testnet Troubleshooting](#21-testnet-troubleshooting)
22. [Testnet Teardown](#22-testnet-teardown)

### Appendix
- [Full Validation Checklist](#full-validation-checklist)
- [Timeline Estimate](#timeline-estimate)
- [References](#references)

---

# Part 1: Localnet (Start Here)

Localnet runs a Bittensor blockchain entirely on your machine via Docker. There is **no activation delay**, **no need for Discord faucet requests**, and blocks can be produced in fast mode (250ms). This is the fastest way to validate the subnet.

---

## 1. Localnet Prerequisites

| Requirement | Details |
|---|---|
| **Docker** | Docker Engine 20+ with at least **20 GB RAM** allocated |
| **Python 3.10+** | Required by the subnet code and Bittensor SDK |
| **Bittensor SDK & CLI** | `bittensor >= 9.10.1` and btcli (installed via `requirements.txt`) |
| **Mentiss API key** | Obtain from the Mentiss team; needed by the validator to call the game API |
| **4-5 terminal windows** | One for the chain, one for the validator, and 1-3 for miners |

---

## 2. Start the Local Blockchain

Pull and run the official subtensor localnet Docker image:

```bash
# Pull the localnet image
docker pull ghcr.io/opentensor/subtensor-localnet:devnet-ready

# Run in fast-block mode (250ms blocks — recommended for development)
docker run --rm --name local_chain \
  -p 9944:9944 \
  -p 9945:9945 \
  ghcr.io/opentensor/subtensor-localnet:devnet-ready
```

Leave this running in its own terminal. You should see block production logs.

**Verify the chain is reachable** (in a new terminal):

```bash
python -c "
from substrateinterface import SubstrateInterface
substrate = SubstrateInterface(url='ws://127.0.0.1:9945')
print(f'Connected to local chain, block #{substrate.get_block_number(None)}')
"
```

> **Tip:** To use standard 12-second blocks instead of fast mode, append `False` to the docker run command. Fast mode is recommended for initial testing since everything happens much quicker.

> **Note:** The `--rm` flag means the chain state is wiped when you stop the container. Remove `--rm` if you want to persist state across restarts.

---

## 3. Environment Setup

In a **new terminal** (keep the chain running):

```bash
cd mentiss-subnet

# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -e .

# Verify
btcli --version
python -c "import mentiss; print(mentiss.__version__)"
```

---

## 4. Create Wallets

Create wallets for the subnet owner, validator, and miners. On localnet these are throwaway — no real value.

```bash
# Subnet owner
btcli wallet new_coldkey --wallet.name owner

# Validator
btcli wallet new_coldkey --wallet.name validator
btcli wallet new_hotkey --wallet.name validator --wallet.hotkey default

# Miner 1
btcli wallet new_coldkey --wallet.name miner1
btcli wallet new_hotkey --wallet.name miner1 --wallet.hotkey default

# (Optional) Miner 2 & 3
btcli wallet new_coldkey --wallet.name miner2
btcli wallet new_hotkey --wallet.name miner2 --wallet.hotkey default

btcli wallet new_coldkey --wallet.name miner3
btcli wallet new_hotkey --wallet.name miner3 --wallet.hotkey default
```

Verify:

```bash
btcli wallet list
```

---

## 5. Fund Wallets via Local Faucet

On localnet, you can mint free TAO using the built-in faucet. Each call grants ~100 TAO. Run it multiple times if needed (subnet creation costs ~1000 TAO on a fresh local chain).

```bash
# Fund the owner (run multiple times to accumulate enough for subnet creation)
btcli wallet faucet --wallet.name owner --subtensor.chain_endpoint ws://127.0.0.1:9945
btcli wallet faucet --wallet.name owner --subtensor.chain_endpoint ws://127.0.0.1:9945
btcli wallet faucet --wallet.name owner --subtensor.chain_endpoint ws://127.0.0.1:9945
btcli wallet faucet --wallet.name owner --subtensor.chain_endpoint ws://127.0.0.1:9945
btcli wallet faucet --wallet.name owner --subtensor.chain_endpoint ws://127.0.0.1:9945
btcli wallet faucet --wallet.name owner --subtensor.chain_endpoint ws://127.0.0.1:9945
btcli wallet faucet --wallet.name owner --subtensor.chain_endpoint ws://127.0.0.1:9945
btcli wallet faucet --wallet.name owner --subtensor.chain_endpoint ws://127.0.0.1:9945
btcli wallet faucet --wallet.name owner --subtensor.chain_endpoint ws://127.0.0.1:9945
btcli wallet faucet --wallet.name owner --subtensor.chain_endpoint ws://127.0.0.1:9945

# Fund the validator (needs TAO for registration + staking)
btcli wallet faucet --wallet.name validator --subtensor.chain_endpoint ws://127.0.0.1:9945
btcli wallet faucet --wallet.name validator --subtensor.chain_endpoint ws://127.0.0.1:9945
btcli wallet faucet --wallet.name validator --subtensor.chain_endpoint ws://127.0.0.1:9945

# Fund miners
btcli wallet faucet --wallet.name miner1 --subtensor.chain_endpoint ws://127.0.0.1:9945
btcli wallet faucet --wallet.name miner2 --subtensor.chain_endpoint ws://127.0.0.1:9945
btcli wallet faucet --wallet.name miner3 --subtensor.chain_endpoint ws://127.0.0.1:9945
```

Check balances:

```bash
btcli wallet balance --wallet.name owner --subtensor.chain_endpoint ws://127.0.0.1:9945
btcli wallet balance --wallet.name validator --subtensor.chain_endpoint ws://127.0.0.1:9945
btcli wallet balance --wallet.name miner1 --subtensor.chain_endpoint ws://127.0.0.1:9945
```

You need at least ~1000 TAO in the owner wallet for subnet creation on a fresh chain.

---

## 6. Create the Subnet Locally

```bash
btcli subnet create \
  --wallet.name owner \
  --subtensor.chain_endpoint ws://127.0.0.1:9945
```

Confirm when prompted. The first subnet on a fresh chain gets **netuid 1**.

Verify:

```bash
btcli subnet list --subtensor.chain_endpoint ws://127.0.0.1:9945
```

You should see your subnet in the list.

---

## 7. Register Neurons

Register the validator and miners on your subnet. On a fresh chain the netuid is `1`.

```bash
# Register validator
btcli subnet register \
  --netuid 1 \
  --wallet.name validator \
  --wallet.hotkey default \
  --subtensor.chain_endpoint ws://127.0.0.1:9945

# Register miner 1
btcli subnet register \
  --netuid 1 \
  --wallet.name miner1 \
  --wallet.hotkey default \
  --subtensor.chain_endpoint ws://127.0.0.1:9945

# (Optional) Register additional miners
btcli subnet register \
  --netuid 1 \
  --wallet.name miner2 \
  --wallet.hotkey default \
  --subtensor.chain_endpoint ws://127.0.0.1:9945

btcli subnet register \
  --netuid 1 \
  --wallet.name miner3 \
  --wallet.hotkey default \
  --subtensor.chain_endpoint ws://127.0.0.1:9945
```

Verify:

```bash
btcli subnet metagraph --netuid 1 --subtensor.chain_endpoint ws://127.0.0.1:9945
```

You should see your validator and miner UIDs listed.

---

## 8. Bootstrap Incentives (Stake)

Add stake to the validator so the incentive mechanism activates. This gives the validator "weight" in the network.

```bash
btcli stake add \
  --wallet.name validator \
  --wallet.hotkey default \
  --subtensor.chain_endpoint ws://127.0.0.1:9945
```

When prompted for the amount, stake a significant portion (e.g., 100+ TAO).

---

## 9. Launch Miners on Localnet

Open a **new terminal** for each miner.

**Terminal — Miner 1:**

```bash
cd mentiss-subnet
source .venv/bin/activate

python neurons/miner.py \
  --wallet.name miner1 \
  --wallet.hotkey default \
  --subtensor.chain_endpoint ws://127.0.0.1:9945 \
  --netuid 1 \
  --axon.port 8091 \
  --logging.debug
```

**Terminal — Miner 2 (optional):**

```bash
cd mentiss-subnet && source .venv/bin/activate

python neurons/miner.py \
  --wallet.name miner2 \
  --wallet.hotkey default \
  --subtensor.chain_endpoint ws://127.0.0.1:9945 \
  --netuid 1 \
  --axon.port 8092 \
  --logging.debug
```

**Terminal — Miner 3 (optional):**

```bash
cd mentiss-subnet && source .venv/bin/activate

python neurons/miner.py \
  --wallet.name miner3 \
  --wallet.hotkey default \
  --subtensor.chain_endpoint ws://127.0.0.1:9945 \
  --netuid 1 \
  --axon.port 8093 \
  --logging.debug
```

**What to look for:**
- `Miner running...` heartbeat messages in each terminal
- No import errors or crashes on startup
- The axon binds to the specified port

---

## 10. Launch the Validator on Localnet

Open another **new terminal**:

```bash
cd mentiss-subnet
source .venv/bin/activate

export MENTISS_API_KEY="sk_mentiss_your_key_here"

python neurons/validator.py \
  --wallet.name validator \
  --wallet.hotkey default \
  --subtensor.chain_endpoint ws://127.0.0.1:9945 \
  --netuid 1 \
  --mentiss.game_setting "G6_1SR1WT_2WW_2VG-H" \
  --mentiss.games_per_cycle 1 \
  --mentiss.poll_interval 2.0 \
  --neuron.epoch_length 100 \
  --logging.debug
```

**What to look for in validator logs:**

| Log message | What it confirms |
|---|---|
| `Started game: <game_id>` | Mentiss API connectivity works |
| `Selected miner UID <N> for Werewolf game` | Metagraph sees registered miners |
| `Submitted action for game <game_id>` | Dendrite → miner axon → response round-trip works |
| `Game <game_id> ended: win/loss` | Full game loop completed |
| `Updated scores from composite metrics` | Reward computation ran successfully |

---

## 11. Localnet Validation Checklist

This is the core checklist. Every item should pass before moving to testnet.

### Phase A: Infrastructure (no games yet)

- [ ] Local chain is running (`docker ps` shows `local_chain`)
- [ ] All wallets created and funded via faucet
- [ ] Subnet created — `btcli subnet list` shows netuid 1
- [ ] Validator and at least 1 miner registered on subnet
- [ ] Miner process starts without errors and serves the axon
- [ ] Validator process starts without errors
- [ ] Validator sees miners in the metagraph

### Phase B: Game Loop (single game)

- [ ] Validator starts a game via the Mentiss API (`Started game: ...`)
- [ ] Validator polls game status successfully (no API errors)
- [ ] Validator sends `WerewolfSynapse` to miner via dendrite
- [ ] Miner receives synapse and returns a response (`Responding with action: ...` in miner logs)
- [ ] Validator submits miner's action back to API (`Submitted action for game ...`)
- [ ] Game completes — validator logs `Game <id> ended: win/loss`
- [ ] Validator fetches player stats post-game (`game_dominance`, `vote_influence` visible in logs)
- [ ] `game_stats.json` is created/updated in the validator's data directory

### Phase C: Scoring and Weights

- [ ] Validator computes composite scores and sigmoid rewards
- [ ] After multiple games, score array is non-zero for active miners
- [ ] After `epoch_length` blocks, validator sets weights on-chain
- [ ] `btcli subnet metagraph --netuid 1 --subtensor.chain_endpoint ws://127.0.0.1:9945` shows non-zero weights for active miners

### Phase D: Multi-Miner (scaling test)

- [ ] Run 2-3 miners simultaneously on different ports
- [ ] Validator plays games with different miners over time
- [ ] `game_stats.json` shows stats for multiple miner UIDs
- [ ] Weights reflect relative performance across miners

### Phase E: Persistence and Recovery

- [ ] Stop the validator (`Ctrl+C`)
- [ ] Restart the validator — confirm it loads saved state
- [ ] `game_stats.json` stats survived the restart
- [ ] Validator resumes game cycles without issues

---

## 12. Enable Emissions on Localnet

To test the full incentive loop with emissions:

```bash
# Register validator on the root subnet
btcli root register \
  --wallet.name validator \
  --wallet.hotkey default \
  --subtensor.chain_endpoint ws://127.0.0.1:9945

# Boost your subnet to direct emissions to it
btcli root boost \
  --netuid 1 \
  --increase 1 \
  --wallet.name validator \
  --wallet.hotkey default \
  --subtensor.chain_endpoint ws://127.0.0.1:9945
```

After a few blocks, check that emissions are flowing:

```bash
btcli subnet metagraph --netuid 1 --subtensor.chain_endpoint ws://127.0.0.1:9945
```

Look for non-zero `emission` values next to your miner UIDs.

---

## 13. Localnet Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| Docker container won't start | Insufficient RAM | Allocate at least 20 GB to Docker |
| `Connection refused` on ws://127.0.0.1:9945 | Chain not running | Check `docker ps`, restart container |
| Faucet gives 0 TAO or errors | Chain not ready yet | Wait a few seconds for blocks to produce, retry |
| `btcli subnet create` fails — insufficient balance | Need more faucet calls | Run faucet 10+ times for the owner wallet |
| Miner/validator can't connect to chain | Wrong endpoint | Ensure you're using `ws://127.0.0.1:9945` (not 9944) |
| Validator logs `No available miners` | Miners not registered or not running | Check metagraph, ensure miners are up |
| `MENTISS_API_KEY not set` | Missing env var | `export MENTISS_API_KEY="sk_mentiss_..."` |
| Weights not changing | Not enough blocks elapsed | In fast mode, 100 blocks = ~25 seconds. Wait and check again |

---

## 14. Localnet Teardown

```bash
# Stop all miner/validator processes (Ctrl+C in each terminal)

# Stop the local chain
docker stop local_chain
```

The `--rm` flag means the container and chain state are automatically cleaned up. If you removed `--rm`, manually clean up with `docker rm local_chain`.

---

# Part 2: Testnet (After Localnet Passes)

Once all localnet validation phases (A-E) pass, you're ready to deploy on the public Bittensor testnet. The main differences from localnet:

| Aspect | Localnet | Testnet |
|---|---|---|
| **Blockchain** | Docker on your machine | Public test chain |
| **TAO** | Free via faucet (unlimited) | Request from Bittensor Discord |
| **Subnet activation** | Immediate | ~1 week delay after creation |
| **Network flag** | `--subtensor.chain_endpoint ws://127.0.0.1:9945` | `--subtensor.network test` |
| **Other miners** | Only yours | Anyone can join |

---

## 15. Testnet Prerequisites

Everything from localnet, plus:

| Requirement | Details |
|---|---|
| **Discord access** | Join the [Bittensor Discord](https://discord.gg/bittensor) to request testnet TAO |
| **Public IP / VPS** | Recommended so external miners can reach your validator. A cloud instance (AWS, GCP, etc.) works well |

You can **reuse the same wallets** from localnet — they work on any network. Or create fresh ones if you prefer.

---

## 16. Obtain Testnet TAO

The automated faucet is **disabled** on the public testnet. You must request TAO manually:

1. Join the [Bittensor Discord](https://discord.gg/bittensor).
2. Go to the testnet faucet channel.
3. Post your **owner** coldkey address and request **at least 150 test TAO**.
4. Also request TAO for your **validator** and **miner** wallets (~5 TAO each).

Check balances:

```bash
btcli wallet balance --wallet.name owner --subtensor.network test
btcli wallet balance --wallet.name validator --subtensor.network test
btcli wallet balance --wallet.name miner1 --subtensor.network test
```

Check the current subnet creation cost:

```bash
btcli subnet lock_cost --subtensor.network test
```

---

## 17. Create the Subnet on Testnet

```bash
btcli subnet create \
  --wallet.name owner \
  --subtensor.network test
```

Write down the assigned **netuid**.

```bash
btcli subnet list --subtensor.network test
```

**Important:** New subnets have an **activation delay** of ~7 × 7200 blocks (~1 week) before emissions activate. You can still register neurons, run validators/miners, and test the game loop during this period.

---

## 18. Register, Launch, and Validate on Testnet

Follow the same steps as localnet (steps 7-11), but replace the chain endpoint flag:

| Localnet | Testnet |
|---|---|
| `--subtensor.chain_endpoint ws://127.0.0.1:9945` | `--subtensor.network test` |

```bash
# Register
btcli subnet register --netuid <NETUID> --wallet.name validator --wallet.hotkey default --subtensor.network test
btcli subnet register --netuid <NETUID> --wallet.name miner1 --wallet.hotkey default --subtensor.network test

# Stake
btcli stake add --wallet.name validator --wallet.hotkey default --subtensor.network test

# Launch miner
python neurons/miner.py \
  --wallet.name miner1 --wallet.hotkey default \
  --subtensor.network test --netuid <NETUID> \
  --axon.port 8091 --logging.debug

# Launch validator
export MENTISS_API_KEY="sk_mentiss_your_key_here"
python neurons/validator.py \
  --wallet.name validator --wallet.hotkey default \
  --subtensor.network test --netuid <NETUID> \
  --mentiss.game_setting "G6_1SR1WT_2WW_2VG-H" \
  --mentiss.games_per_cycle 1 \
  --mentiss.poll_interval 2.0 \
  --neuron.epoch_length 100 \
  --logging.debug
```

Run through the same **validation checklist** (Phases A-E) from step 11 — this time on the live testnet.

---

## 19. Enable Emissions on Testnet

After the ~1 week activation delay:

```bash
btcli root register \
  --wallet.name validator \
  --wallet.hotkey default \
  --subtensor.network test

btcli root weights --subtensor.network test
```

---

## 20. Invite External Miners

Once validation passes on testnet, share these details with miners:

```
Subnet netuid:  <NETUID>
Network:        test (Bittensor testnet)
Repo:           https://github.com/mentiss-ai/mentiss-subnet
Install:        pip install -r requirements.txt && pip install -e .
Run:            python neurons/miner.py \
                  --wallet.name <wallet> \
                  --wallet.hotkey default \
                  --subtensor.network test \
                  --netuid <NETUID> \
                  --axon.port <port> \
                  --logging.debug
```

External miners need their own testnet TAO for registration (~1-5 TAO).

---

## 21. Testnet Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| `btcli subnet create` insufficient balance | Owner underfunded | Request more testnet TAO from Discord |
| Validator logs `No available miners` | Miners not registered or unreachable | Check `btcli subnet metagraph --netuid <NETUID> --subtensor.network test` |
| `Failed to start game` | Bad API key or game setting | Verify `MENTISS_API_KEY`; check `--mentiss.game_setting` |
| Miner logs `Missing dendrite or hotkey` | Validator not registered on same subnet | Ensure same netuid |
| `Dendrite error for miner <uid>` | Miner unreachable (port/firewall) | Open the axon port, check miner is running |
| Weights not changing | Not enough blocks elapsed | Wait for `epoch_length` (100) blocks (~20 min on testnet) |
| Weights all zero | No games completed or scores below threshold | Play more games or lower `--mentiss.reward_threshold` |
| Subnet not emitting | Activation delay not elapsed | Wait ~1 week, then register on root |

---

## 22. Testnet Teardown

1. Stop all miner and validator processes (`Ctrl+C`)
2. Testnet wallets can be safely deleted — they hold no real value
3. The subnet will eventually be deregistered by the chain if inactive, returning locked TAO

---

## Full Validation Checklist

Summary of everything that must pass (on either localnet or testnet):

- [ ] **Infra:** Chain running, wallets funded, subnet created, neurons registered
- [ ] **Startup:** Miner and validator processes start without errors
- [ ] **Discovery:** Validator sees miners in metagraph
- [ ] **Game start:** Validator calls Mentiss API to create a game
- [ ] **Communication:** Validator sends synapse to miner, miner responds
- [ ] **Action submission:** Validator submits miner action to API
- [ ] **Game completion:** Game runs to completion (win/loss logged)
- [ ] **Stats collection:** Player stats fetched, `game_stats.json` updated
- [ ] **Scoring:** Composite scores and sigmoid rewards computed
- [ ] **Weights:** Weights set on-chain, visible in metagraph
- [ ] **Multi-miner:** Multiple miners scored and weighted correctly
- [ ] **Persistence:** Validator state survives restart
- [ ] **Emissions:** (Optional) TAO flows to miners based on weights

---

## Timeline Estimate

| Phase | Duration | Notes |
|---|---|---|
| **Localnet setup** (steps 1-8) | **30 minutes** | Docker + wallets + faucet + subnet |
| **Localnet validation** (steps 9-12) | **1-2 hours** | Run games, check all phases |
| **Testnet TAO acquisition** (step 16) | 1-2 days | Waiting for Discord response |
| **Testnet subnet creation** (step 17) | 30 minutes | Quick once funded |
| **Testnet activation delay** | ~1 week | Can test game loop during this time |
| **Testnet validation** (step 18) | 1-2 days | Re-run all phases on live network |
| **External miner invitations** (step 20) | Ongoing | After testnet validation passes |

**Total time to first localnet validation: ~2 hours.**

---

## References

- [Bittensor: Run a Local Blockchain Instance](https://docs.learnbittensor.org/local-build/deploy)
- [Bittensor: Using Docker for Subtensor](https://docs.learnbittensor.org/subtensor-nodes/using-docker)
- [Bittensor: Create a Subnet](https://docs.learnbittensor.org/subnets/create-a-subnet)
- [Bittensor Subnet Template: Running on Staging (Local)](https://github.com/opentensor/bittensor-subnet-template/blob/main/docs/running_on_staging.md)
- [Bittensor Subnet Template: Running on Testnet](https://github.com/opentensor/bittensor-subnet-template/blob/main/docs/running_on_testnet.md)
- [Bittensor: Register, Validate and Mine](https://docs.learnbittensor.org/subnets/register-validate-mine/)
- [Subtensor GitHub: Running Locally](https://github.com/opentensor/subtensor/blob/main/docs/running-subtensor-locally.md)
- [Mentiss Subnet: Validation Logic](./validation-logic.md)
