#!/bin/bash
# =============================================================================
# Mentiss Subnet — Testnet Setup Script
# Creates wallets, funds them via transfer, and registers on the Bittensor testnet.
#
# Prerequisites:
#   - btcli installed (or available in venv/)
#   - Existing funded wallet to transfer from (default: owner_testnet)
#   - Internet connection to testnet
#
# Usage:
#   chmod +x scripts/setup_testnet.sh
#   ./scripts/setup_testnet.sh <NETUID> [FUNDER_WALLET]
#
# Example:
#   ./scripts/setup_testnet.sh 44 owner_testnet
# =============================================================================

set -euo pipefail

NETWORK="test"
NUM_MINERS=10
NUM_VALIDATORS=3
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BTCLI="$PROJECT_DIR/venv/bin/btcli"
TRANSFER_AMOUNT="0.15"  # τ per wallet (enough for registration + buffer)

# Check btcli exists
if [ ! -f "$BTCLI" ]; then
    echo "btcli not found at $BTCLI — trying global btcli"
    BTCLI="btcli"
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# --------------------------------------------------------------------------
# Parse arguments
# --------------------------------------------------------------------------
NETUID="${1:-}"
FUNDER="${2:-owner_testnet}"

if [ -z "$NETUID" ]; then
    log_warn "No NETUID provided."
    echo ""
    echo "Usage: $0 <NETUID> [FUNDER_WALLET]"
    echo ""
    echo "Example: $0 44 owner_testnet"
    exit 1
fi

log_info "Setting up Mentiss subnet on testnet (netuid=$NETUID, funder=$FUNDER)"
echo ""

# --------------------------------------------------------------------------
# Define all wallet names
# --------------------------------------------------------------------------
VALIDATOR_WALLETS=()
for i in $(seq 1 $NUM_VALIDATORS); do
    VALIDATOR_WALLETS+=("validator${i}")
done

MINER_WALLETS=()
for i in $(seq 1 $NUM_MINERS); do
    MINER_WALLETS+=("miner${i}")
done

ALL_WALLETS=("${VALIDATOR_WALLETS[@]}" "${MINER_WALLETS[@]}")

# ==========================================================================
# Step 1: Create All Wallets
# ==========================================================================
echo "==========================================="
echo " Step 1: Creating wallets"
echo "==========================================="

for wallet in "${ALL_WALLETS[@]}"; do
    log_info "Creating wallet: $wallet"
    $BTCLI wallet create \
        --wallet.name "$wallet" \
        --wallet.hotkey default \
        --no-prompt 2>/dev/null && log_ok "Created $wallet" || log_warn "$wallet may already exist (continuing)"
done
echo ""

# ==========================================================================
# Step 2: Transfer TAO from funder to each wallet that needs it
# ==========================================================================
echo "==========================================="
echo " Step 2: Funding wallets from $FUNDER"
echo "==========================================="

for wallet in "${ALL_WALLETS[@]}"; do
    # Get the coldkey address of the target wallet
    ADDR=$($BTCLI wallet overview --wallet.name "$wallet" --subtensor.network "$NETWORK" 2>&1 | grep -oE '5[A-HJ-NP-Za-km-z1-9]{47}' | head -1 || echo "")

    if [ -z "$ADDR" ]; then
        log_warn "Could not find address for $wallet — skipping transfer"
        continue
    fi

    log_info "Transferring $TRANSFER_AMOUNT τ from $FUNDER to $wallet ($ADDR)"
    $BTCLI wallet transfer \
        --wallet.name "$FUNDER" \
        --dest "$ADDR" \
        --amount "$TRANSFER_AMOUNT" \
        --subtensor.network "$NETWORK" \
        --no-prompt 2>&1 | tail -1 || log_warn "Transfer to $wallet may have failed"
done
echo ""

# ==========================================================================
# Step 3: Register All Wallets on the Subnet
# ==========================================================================
echo "==========================================="
echo " Step 3: Registering all wallets on subnet $NETUID"
echo "==========================================="

for wallet in "${ALL_WALLETS[@]}"; do
    log_info "Registering $wallet on subnet $NETUID"
    $BTCLI subnet register \
        --wallet.name "$wallet" \
        --wallet.hotkey default \
        --subtensor.network "$NETWORK" \
        --netuid "$NETUID" \
        --no-prompt 2>&1 | tail -3 || log_warn "Registration for $wallet may have failed"
done
echo ""

# ==========================================================================
# Step 4: Verify — show metagraph
# ==========================================================================
echo "==========================================="
echo " Step 4: Verifying registration"
echo "==========================================="

$BTCLI subnet metagraph --netuid "$NETUID" --subtensor.network "$NETWORK" 2>&1 || log_warn "Could not fetch metagraph"

echo ""
echo "==========================================="
echo " Setup Complete"
echo "==========================================="
echo ""
log_ok "Created and registered $NUM_VALIDATORS validators + $NUM_MINERS miners on testnet (netuid=$NETUID)"
echo ""
echo "Next steps:"
echo "  1. Run validators:  ./scripts/run_validators.sh $NETUID"
echo "  2. Run miners:      ./scripts/run_miners.sh $NETUID"
echo "  3. Collect evidence: ./scripts/collect_evidence.sh $NETUID"
