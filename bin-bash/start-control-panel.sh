#!/usr/bin/env bash

cd /Users/kalerv/zynfosoft/u107_level_driven_algo/ui-control-panel/ui-dashboard/

PORTFOLIO_ID="p107"
SCRIPT_PATH="npm run dev -- --host 0.0.0.0"
COMMAND="${SCRIPT_PATH}"
PROCESS_MATCH="npm"

LOG_DIR="../../portfolios/${PORTFOLIO_ID}/logs"
LOG_FILE="$LOG_DIR/control-panel.log"

mkdir -p "$LOG_DIR"

echo "--------------------------------------"
echo "Checking trading_api for ${PORTFOLIO_ID}..."
echo "Log file: $LOG_FILE"

# 🔍 Check if already running
RUNNING_PID=$(pgrep -f "$PROCESS_MATCH")

if [ -n "$RUNNING_PID" ]; then
    echo "Process already running with PID(s): $RUNNING_PID"
    exit 0
fi

echo "Process not running. Starting..."
echo $COMMAND

$COMMAND >> "$LOG_FILE" 2>&1 &

NEW_PID=$!
echo "Started trading_api with PID: $NEW_PID"

exit 0
