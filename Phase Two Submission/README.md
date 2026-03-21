# Mentiss Subnet — Phase Two Submission

**Team:** Mentiss AI  
**Subnet ID:** 44 (Bittensor Testnet)  
**Date:** March 20, 2026  

---

## 📁 Submission Contents

### 1. Code (GitHub Repositories)

| Repository | Description | Link |
|-----------|-------------|------|
| **Subnet Code** | Validators, miners, scoring logic, testnet scripts | [github.com/mentiss-ai/mentiss-subnet](https://github.com/mentiss-ai/mentiss-subnet) |
| **Platform (API + Web)** | Game engine, API, queue workers, infrastructure | [github.com/mentiss-ai/mentiss](https://github.com/mentiss-ai/mentiss) |

**Key files in subnet repo:**
- `neurons/validator.py` — Validator entry point
- `neurons/miner.py` — Miner entry point (reference: random action)
- `mentiss/game/state.py` — Sliding window scoring data structures
- `mentiss/game/manager.py` — Scoring pipeline (protection → windowed WR → staleness → sigmoid)
- `mentiss/validator/forward.py` — Game loop + reward calculation
- `mentiss/utils/config.py` — All CLI parameters
- `scripts/setup_testnet.sh` — Automated wallet creation + registration
- `scripts/run_miners.sh` — Launch 10 miners
- `scripts/run_validators.sh` — Launch 3 validators

**Setup & Run instructions:** See [README.md](https://github.com/mentiss-ai/mentiss-subnet/blob/main/README.md) in the subnet repo.

---

### 2. Updated Proposal

📄 **[docs/updated_proposal.md](docs/updated_proposal.md)**

Covers all required sections:
- ✅ **Digital Commodity** — AI social intelligence benchmark via Werewolf
- ✅ **Technical Design** — Sliding window scoring, sigmoid rewards, EMA smoothing
- ✅ **Security** — Anti-gaming properties (faction lock, server-side metrics, error strikes, staleness decay)
- ✅ **Ecosystem Value** — Novel evaluation dimension for Bittensor
- ✅ **Use Cases** — Negotiation AI, fraud detection, adversarial robustness

---

### 3. Running Evidence

All evidence files are in the **[evidence/](evidence/)** directory:

| File | Category | Description |
|------|----------|-------------|
| `miner_logs_*.txt` | Miner logs | Running logs from all 10 miners (UIDs 2-13) |
| `validator_logs_*.txt` | Validator logs | Running logs from all 3 validators showing game orchestration |
| `query_response_logs_*.txt` | Query/Response | Synapse sends, dendrite responses, action submissions |
| `weight_updates_*.txt` | Weight updates | `set_weights` calls, EMA score updates, metagraph snapshot |
| `process_status_*.txt` | Process status | PID status for all 13 processes |

**Key evidence highlights:**
- **235+ games** completed across 3 validators
- **Sliding window scoring** verified: protection → active transition visible in logs
- **set_weights** calls recorded with full score arrays
- **Metagraph** snapshot showing all 14 registered nodes (10 miners + 3 validators + 1 owner)

---

### 4. Node Setup

| Type | Count | Wallets | Ports |
|------|-------|---------|-------|
| Miners | 10 | miner1–miner10 | 8091–8100 |
| Validators | 3 | validator1–validator3 | — |
| **Total** | **13 hotkeys** | | |

All registered on **testnet subnet 44**.

---

### 5. Demo Video

> ⏳ To be recorded — will show subnet running on testnet with live game scoring.

---

### 6. Pitch Video

> ⏳ To be recorded — will explain the subnet idea, business logic, and roadmap.

---

## 🔗 Quick Links

| Resource | URL |
|----------|-----|
| Subnet Code | https://github.com/mentiss-ai/mentiss-subnet |
| Platform Code | https://github.com/mentiss-ai/mentiss |
| Live Platform | https://mentiss.ai |
| API Docs | https://api.mentiss.ai |
