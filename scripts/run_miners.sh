#!/bin/bash
# =============================================================================
# Mentiss Subnet — Run 10 Miners
# Launches all miner instances in the background with proper port assignment
# and log capture.
#
# Usage:
#   chmod +x scripts/run_miners.sh
#   ./scripts/run_miners.sh <NETUID>
#
# Logs are written to: logs/miner<N>.log
# PIDs are written to: logs/miner_pids.txt
# =============================================================================

set -euo pipefail

NETWORK="test"
NUM_MINERS=10
BASE_PORT=8091
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_DIR/logs"
PYTHON="$PROJECT_DIR/venv/bin/python"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()   { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC}  $*"; }

# --------------------------------------------------------------------------
# Parse arguments
# --------------------------------------------------------------------------
NETUID="${1:-}"

if [ -z "$NETUID" ]; then
    echo "Usage: $0 <NETUID>"
    exit 1
fi

# Create log directory
mkdir -p "$LOG_DIR"

# Kill existing miners if any
if [ -f "$LOG_DIR/miner_pids.txt" ]; then
    log_warn "Stopping existing miners..."
    while read -r pid; do
        kill "$pid" 2>/dev/null || true
    done < "$LOG_DIR/miner_pids.txt"
    rm -f "$LOG_DIR/miner_pids.txt"
    sleep 2
fi

log_info "Starting $NUM_MINERS miners on testnet (netuid=$NETUID)"
echo ""

# --------------------------------------------------------------------------
# Launch miners
# --------------------------------------------------------------------------
> "$LOG_DIR/miner_pids.txt"  # Clear PID file

for i in $(seq 1 $NUM_MINERS); do
    PORT=$((BASE_PORT + i - 1))
    WALLET_NAME="miner${i}"
    LOG_FILE="$LOG_DIR/miner${i}.log"

    log_info "Starting miner${i} (wallet=$WALLET_NAME, port=$PORT, log=$LOG_FILE)"

    nohup "$PYTHON" "$PROJECT_DIR/neurons/miner.py" \
        --wallet.name "$WALLET_NAME" \
        --wallet.hotkey default \
        --subtensor.network "$NETWORK" \
        --netuid "$NETUID" \
        --axon.port "$PORT" \
        --logging.debug \
        > "$LOG_FILE" 2>&1 &

    PID=$!
    echo "$PID" >> "$LOG_DIR/miner_pids.txt"
    log_ok "miner${i} started (PID=$PID, port=$PORT)"
done

echo ""
echo "==========================================="
echo " All $NUM_MINERS miners started"
echo "==========================================="
echo ""
echo "  PIDs saved to: $LOG_DIR/miner_pids.txt"
echo "  Logs saved to: $LOG_DIR/miner<N>.log"
echo ""
echo "  To check status:   ps -p \$(cat $LOG_DIR/miner_pids.txt | tr '\n' ',')"
echo "  To tail all logs:  tail -f $LOG_DIR/miner*.log"
echo "  To stop all:       kill \$(cat $LOG_DIR/miner_pids.txt)"
