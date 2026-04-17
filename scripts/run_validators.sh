#!/bin/bash
# =============================================================================
# Mentiss Subnet — Run 3 Validators (Local Testing)
# Points validators at local Mentiss API (localhost:3001) with mock AI.
#
# Usage:
#   ./scripts/run_validators.sh <NETUID> [API_URL]
#
# Example:
#   ./scripts/run_validators.sh 44                           # uses localhost:3001
#   ./scripts/run_validators.sh 44 https://api.mentiss.ai    # uses production
# =============================================================================

set -euo pipefail

NETWORK="test"
NUM_VALIDATORS=3
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

# --------------------------------------------------------------------------
# Parse arguments
# --------------------------------------------------------------------------
NETUID="${1:-}"
API_URL="${2:-http://localhost:3001}"

if [ -z "$NETUID" ]; then
    echo "Usage: $0 <NETUID> [API_URL]"
    echo ""
    echo "  API_URL defaults to http://localhost:3001 (local dev)"
    echo "  For production: $0 44 https://api.mentiss.ai"
    exit 1
fi

# Load .env if it exists
if [ -f "$ENV_FILE" ]; then
    log_info "Loading environment from $ENV_FILE"
    set -a
    source "$ENV_FILE"
    set +a
fi

# For local testing, API key can be empty (mock AI doesn't need auth)
MENTISS_API_KEY="${MENTISS_API_KEY:-local-test-key}"

# Determine concurrent forwards based on test vs prod
if [[ "$API_URL" == *"localhost"* ]]; then
    # Local testing: lower concurrency (10 miners, not 128)
    CONCURRENT=5
    POLL_INTERVAL=1.0
    log_info "Local testing mode: $CONCURRENT concurrent games, poll every ${POLL_INTERVAL}s"
else
    CONCURRENT=30
    POLL_INTERVAL=2.0
    log_info "Production mode: $CONCURRENT concurrent games, poll every ${POLL_INTERVAL}s"
fi

# Check python
if [ ! -f "$PYTHON" ]; then
    log_warn "venv not found at $PYTHON, trying system python"
    PYTHON="python"
fi

# Create log directory
mkdir -p "$LOG_DIR"

# Kill existing validators if any
if [ -f "$LOG_DIR/validator_pids.txt" ]; then
    log_warn "Stopping existing validators..."
    while read -r pid; do
        kill "$pid" 2>/dev/null || true
    done < "$LOG_DIR/validator_pids.txt"
    rm -f "$LOG_DIR/validator_pids.txt"
    sleep 2
fi

log_info "Starting $NUM_VALIDATORS validators on testnet (netuid=$NETUID)"
log_info "API URL: $API_URL"
echo ""

# --------------------------------------------------------------------------
# Launch validators
# --------------------------------------------------------------------------
> "$LOG_DIR/validator_pids.txt"

for i in $(seq 1 $NUM_VALIDATORS); do
    WALLET_NAME="validator${i}"
    LOG_FILE="$LOG_DIR/validator${i}.log"

    log_info "Starting validator${i} (wallet=$WALLET_NAME, log=$LOG_FILE)"

    MENTISS_API_KEY="$MENTISS_API_KEY" \
    MENTISS_API_URL="$API_URL" \
    nohup "$PYTHON" "$PROJECT_DIR/neurons/validator.py" \
        --wallet.name "$WALLET_NAME" \
        --wallet.hotkey default \
        --subtensor.network "$NETWORK" \
        --netuid "$NETUID" \
        --mentiss.game_setting "G9_1SR1WT1HT_2WW1AW_3VG-R" \
        --mentiss.reward_threshold 0.30 \
        --mentiss.reward_steepness 20.0 \
        --mentiss.poll_interval "$POLL_INTERVAL" \
        --mentiss.protection_min_games 10 \
        --mentiss.scoring_window_hours 36.0 \
        --mentiss.max_games_in_window 50 \
        --mentiss.stale_decay_hours 48.0 \
        --mentiss.game_cost_tao "${GAME_COST_TAO:-0}" \
        --mentiss.payment_address "${PAYMENT_ADDRESS:-}" \
        --neuron.num_concurrent_forwards "$CONCURRENT" \
        --neuron.epoch_length 50 \
        --logging.debug \
        > "$LOG_FILE" 2>&1 &

    PID=$!
    echo "$PID" >> "$LOG_DIR/validator_pids.txt"
    log_ok "validator${i} started (PID=$PID)"
done

echo ""
echo "==========================================="
echo " All $NUM_VALIDATORS validators started"
echo "==========================================="
echo ""
echo "  API URL:   $API_URL"
echo "  Concurrent: $CONCURRENT games per validator"
echo "  PIDs:      $LOG_DIR/validator_pids.txt"
echo "  Logs:      $LOG_DIR/validator<N>.log"
echo ""
echo "  To check status:   ps -p \$(cat $LOG_DIR/validator_pids.txt | tr '\n' ',')"
echo "  To tail all logs:  tail -f $LOG_DIR/validator*.log"
echo "  To stop all:       kill \$(cat $LOG_DIR/validator_pids.txt)"
