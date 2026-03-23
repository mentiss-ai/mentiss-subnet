#!/bin/bash
# =============================================================================
# Mentiss Subnet — Run Smart Miners for Testnet Evidence
# Uses Google Gemini for intelligent Werewolf play.
#
# Usage:
#   ./scripts/run_smart_miners.sh <NETUID> [NUM_MINERS]
#
# Example:
#   ./scripts/run_smart_miners.sh 44 3
# =============================================================================

set -euo pipefail

NETWORK="test"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_DIR/logs"
ENV_FILE="$PROJECT_DIR/.env"
PYTHON="$PROJECT_DIR/venv/bin/python"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# Parse arguments
NETUID="${1:-}"
NUM_MINERS="${2:-3}"

if [ -z "$NETUID" ]; then
    echo "Usage: $0 <NETUID> [NUM_MINERS]"
    echo ""
    echo "  NUM_MINERS defaults to 3"
    exit 1
fi

# Load .env
if [ -f "$ENV_FILE" ]; then
    log_info "Loading environment from $ENV_FILE"
    set -a
    source "$ENV_FILE"
    set +a
fi

# Check Google API key
if [ -z "${GOOGLE_API_KEY_BITTENSOR:-}" ]; then
    log_error "GOOGLE_API_KEY_BITTENSOR not set in .env"
    exit 1
fi
log_ok "Google API key loaded"

# Check python
if [ ! -f "$PYTHON" ]; then
    log_warn "venv not found at $PYTHON, trying system python"
    PYTHON="python"
fi

# Create log directory
mkdir -p "$LOG_DIR"

# Kill existing smart miners if any
if [ -f "$LOG_DIR/smart_miner_pids.txt" ]; then
    log_warn "Stopping existing smart miners..."
    while read -r pid; do
        kill "$pid" 2>/dev/null || true
    done < "$LOG_DIR/smart_miner_pids.txt"
    rm -f "$LOG_DIR/smart_miner_pids.txt"
    sleep 2
fi

log_info "Starting $NUM_MINERS smart miners on testnet (netuid=$NETUID)"
echo ""

# Launch miners
> "$LOG_DIR/smart_miner_pids.txt"

for i in $(seq 1 $NUM_MINERS); do
    WALLET_NAME="miner${i}"
    LOG_FILE="$LOG_DIR/smart_miner${i}.log"

    log_info "Starting smart_miner${i} (wallet=$WALLET_NAME, log=$LOG_FILE)"

    GOOGLE_API_KEY_BITTENSOR="$GOOGLE_API_KEY_BITTENSOR" \
    nohup "$PYTHON" "$PROJECT_DIR/neurons/smart_miner.py" \
        --wallet.name "$WALLET_NAME" \
        --wallet.hotkey default \
        --subtensor.network "$NETWORK" \
        --netuid "$NETUID" \
        --blacklist.force_validator_permit false \
        --logging.debug \
        > "$LOG_FILE" 2>&1 &

    PID=$!
    echo "$PID" >> "$LOG_DIR/smart_miner_pids.txt"
    log_ok "smart_miner${i} started (PID=$PID)"
done

echo ""
echo "==========================================="
echo " All $NUM_MINERS smart miners started"
echo "==========================================="
echo ""
echo "  PIDs:      $LOG_DIR/smart_miner_pids.txt"
echo "  Logs:      $LOG_DIR/smart_miner<N>.log"
echo ""
echo "  To check:  ps -p \$(cat $LOG_DIR/smart_miner_pids.txt | tr '\n' ',')"
echo "  To tail:   tail -f $LOG_DIR/smart_miner*.log"
echo "  To stop:   kill \$(cat $LOG_DIR/smart_miner_pids.txt)"
