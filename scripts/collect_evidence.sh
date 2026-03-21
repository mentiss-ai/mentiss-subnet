#!/bin/bash
# =============================================================================
# Mentiss Subnet — Collect Testnet Running Evidence
# Gathers all evidence required for hackathon submission:
#   - Miner running logs
#   - Validator running logs
#   - Query / response logs (extracted from debug logs)
#   - Weight update evidence (set_weights + metagraph)
#
# Output is saved to: evidence/ directory
#
# Usage:
#   chmod +x scripts/collect_evidence.sh
#   ./scripts/collect_evidence.sh <NETUID>
# =============================================================================

set -euo pipefail

NETWORK="test"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_DIR/logs"
EVIDENCE_DIR="$PROJECT_DIR/evidence"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

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

# Create evidence directory
mkdir -p "$EVIDENCE_DIR"

echo "==========================================="
echo " Collecting Testnet Evidence"
echo " Timestamp: $TIMESTAMP"
echo " Netuid: $NETUID"
echo "==========================================="
echo ""

# ==========================================================================
# 1. Miner Running Logs
# ==========================================================================
log_info "Collecting miner running logs..."

MINER_EVIDENCE="$EVIDENCE_DIR/miner_logs_${TIMESTAMP}.txt"
echo "# Mentiss Subnet — Miner Running Logs" > "$MINER_EVIDENCE"
echo "# Collected: $(date)" >> "$MINER_EVIDENCE"
echo "# Netuid: $NETUID" >> "$MINER_EVIDENCE"
echo "" >> "$MINER_EVIDENCE"

for i in $(seq 1 10); do
    LOG_FILE="$LOG_DIR/miner${i}.log"
    if [ -f "$LOG_FILE" ]; then
        echo "=========================================" >> "$MINER_EVIDENCE"
        echo "=== MINER ${i} ===" >> "$MINER_EVIDENCE"
        echo "=========================================" >> "$MINER_EVIDENCE"
        # Capture last 100 lines of each miner log
        tail -n 100 "$LOG_FILE" >> "$MINER_EVIDENCE" 2>/dev/null || echo "(no output yet)" >> "$MINER_EVIDENCE"
        echo "" >> "$MINER_EVIDENCE"
    else
        echo "=== MINER ${i}: log file not found ($LOG_FILE) ===" >> "$MINER_EVIDENCE"
        echo "" >> "$MINER_EVIDENCE"
    fi
done
log_ok "Saved to $MINER_EVIDENCE"

# ==========================================================================
# 2. Validator Running Logs
# ==========================================================================
log_info "Collecting validator running logs..."

VALIDATOR_EVIDENCE="$EVIDENCE_DIR/validator_logs_${TIMESTAMP}.txt"
echo "# Mentiss Subnet — Validator Running Logs" > "$VALIDATOR_EVIDENCE"
echo "# Collected: $(date)" >> "$VALIDATOR_EVIDENCE"
echo "# Netuid: $NETUID" >> "$VALIDATOR_EVIDENCE"
echo "" >> "$VALIDATOR_EVIDENCE"

for i in $(seq 1 3); do
    LOG_FILE="$LOG_DIR/validator${i}.log"
    if [ -f "$LOG_FILE" ]; then
        echo "=========================================" >> "$VALIDATOR_EVIDENCE"
        echo "=== VALIDATOR ${i} ===" >> "$VALIDATOR_EVIDENCE"
        echo "=========================================" >> "$VALIDATOR_EVIDENCE"
        # Capture last 200 lines of each validator log (validators are more verbose)
        tail -n 200 "$LOG_FILE" >> "$VALIDATOR_EVIDENCE" 2>/dev/null || echo "(no output yet)" >> "$VALIDATOR_EVIDENCE"
        echo "" >> "$VALIDATOR_EVIDENCE"
    else
        echo "=== VALIDATOR ${i}: log file not found ($LOG_FILE) ===" >> "$VALIDATOR_EVIDENCE"
        echo "" >> "$VALIDATOR_EVIDENCE"
    fi
done
log_ok "Saved to $VALIDATOR_EVIDENCE"

# ==========================================================================
# 3. Query / Response Logs
# ==========================================================================
log_info "Extracting query/response logs from validator debug output..."

QR_EVIDENCE="$EVIDENCE_DIR/query_response_logs_${TIMESTAMP}.txt"
echo "# Mentiss Subnet — Query / Response Logs" > "$QR_EVIDENCE"
echo "# Collected: $(date)" >> "$QR_EVIDENCE"
echo "# Netuid: $NETUID" >> "$QR_EVIDENCE"
echo "# Extracted from validator debug logs: synapse sends, dendrite responses, action submissions" >> "$QR_EVIDENCE"
echo "" >> "$QR_EVIDENCE"

for i in $(seq 1 3); do
    LOG_FILE="$LOG_DIR/validator${i}.log"
    if [ -f "$LOG_FILE" ]; then
        echo "=========================================" >> "$QR_EVIDENCE"
        echo "=== VALIDATOR ${i} — QUERY/RESPONSE FLOW ===" >> "$QR_EVIDENCE"
        echo "=========================================" >> "$QR_EVIDENCE"
        echo "" >> "$QR_EVIDENCE"

        # Extract synapse sends, dendrite responses, and action submissions
        grep -E "(Sending synapse|Dendrite response|Submitted action|Started game|Game .* ended|Selected miner)" \
            "$LOG_FILE" 2>/dev/null | tail -n 100 >> "$QR_EVIDENCE" || echo "(no matching entries)" >> "$QR_EVIDENCE"
        echo "" >> "$QR_EVIDENCE"
    fi
done
log_ok "Saved to $QR_EVIDENCE"

# ==========================================================================
# 4. Weight Update Evidence
# ==========================================================================
log_info "Collecting weight update evidence..."

WEIGHT_EVIDENCE="$EVIDENCE_DIR/weight_updates_${TIMESTAMP}.txt"
echo "# Mentiss Subnet — Weight Update Evidence" > "$WEIGHT_EVIDENCE"
echo "# Collected: $(date)" >> "$WEIGHT_EVIDENCE"
echo "# Netuid: $NETUID" >> "$WEIGHT_EVIDENCE"
echo "" >> "$WEIGHT_EVIDENCE"

# Extract set_weights calls from validator logs
echo "=========================================" >> "$WEIGHT_EVIDENCE"
echo "=== set_weights LOG ENTRIES ===" >> "$WEIGHT_EVIDENCE"
echo "=========================================" >> "$WEIGHT_EVIDENCE"
echo "" >> "$WEIGHT_EVIDENCE"

for i in $(seq 1 3); do
    LOG_FILE="$LOG_DIR/validator${i}.log"
    if [ -f "$LOG_FILE" ]; then
        echo "--- Validator ${i} ---" >> "$WEIGHT_EVIDENCE"
        grep -E "(set_weights|Updated scores|raw_weights|processed_weights|uint_weights)" \
            "$LOG_FILE" 2>/dev/null | tail -n 50 >> "$WEIGHT_EVIDENCE" || echo "(no weight entries yet)" >> "$WEIGHT_EVIDENCE"
        echo "" >> "$WEIGHT_EVIDENCE"
    fi
done

# Capture metagraph
echo "=========================================" >> "$WEIGHT_EVIDENCE"
echo "=== METAGRAPH SNAPSHOT ===" >> "$WEIGHT_EVIDENCE"
echo "=========================================" >> "$WEIGHT_EVIDENCE"
echo "" >> "$WEIGHT_EVIDENCE"

log_info "Fetching metagraph from testnet..."
btcli subnet metagraph \
    --netuid "$NETUID" \
    --subtensor.network "$NETWORK" \
    >> "$WEIGHT_EVIDENCE" 2>&1 || echo "(failed to fetch metagraph — is btcli installed?)" >> "$WEIGHT_EVIDENCE"

log_ok "Saved to $WEIGHT_EVIDENCE"

# ==========================================================================
# 5. Process Status
# ==========================================================================
log_info "Checking running processes..."

STATUS_FILE="$EVIDENCE_DIR/process_status_${TIMESTAMP}.txt"
echo "# Mentiss Subnet — Process Status" > "$STATUS_FILE"
echo "# Collected: $(date)" >> "$STATUS_FILE"
echo "" >> "$STATUS_FILE"

echo "=== Running Miner Processes ===" >> "$STATUS_FILE"
if [ -f "$LOG_DIR/miner_pids.txt" ]; then
    while read -r pid; do
        if ps -p "$pid" > /dev/null 2>&1; then
            echo "  PID $pid: RUNNING" >> "$STATUS_FILE"
        else
            echo "  PID $pid: STOPPED" >> "$STATUS_FILE"
        fi
    done < "$LOG_DIR/miner_pids.txt"
else
    echo "  (no miner PID file found)" >> "$STATUS_FILE"
fi
echo "" >> "$STATUS_FILE"

echo "=== Running Validator Processes ===" >> "$STATUS_FILE"
if [ -f "$LOG_DIR/validator_pids.txt" ]; then
    while read -r pid; do
        if ps -p "$pid" > /dev/null 2>&1; then
            echo "  PID $pid: RUNNING" >> "$STATUS_FILE"
        else
            echo "  PID $pid: STOPPED" >> "$STATUS_FILE"
        fi
    done < "$LOG_DIR/validator_pids.txt"
else
    echo "  (no validator PID file found)" >> "$STATUS_FILE"
fi

log_ok "Saved to $STATUS_FILE"

# ==========================================================================
# Summary
# ==========================================================================
echo ""
echo "==========================================="
echo " Evidence Collection Complete"
echo "==========================================="
echo ""
echo "  All evidence saved to: $EVIDENCE_DIR/"
echo ""
echo "  Files:"
echo "    1. $MINER_EVIDENCE"
echo "    2. $VALIDATOR_EVIDENCE"
echo "    3. $QR_EVIDENCE"
echo "    4. $WEIGHT_EVIDENCE"
echo "    5. $STATUS_FILE"
echo ""
echo "  These files cover all 4 evidence categories required:"
echo "    ✓ Miner running logs"
echo "    ✓ Validator running logs"
echo "    ✓ Query / response logs"
echo "    ✓ Weight update evidence (set_weights + metagraph)"
