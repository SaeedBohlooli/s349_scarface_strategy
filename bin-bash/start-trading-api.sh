#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

source ../venv/bin/activate

PORTFOLIO_ID="p107"
SCRIPT_PATH="../trading_api/trading_api_service.py"
COMMAND="${SCRIPT_PATH}  --portfolio-id=$PORTFOLIO_ID"
PROCESS_MATCH="trading_api_service.py --portfolio-id=${PORTFOLIO_ID}"

LOG_DIR="../../portfolios/${PORTFOLIO_ID}/logs"
LOG_FILE="$LOG_DIR/trading_api.log"

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

nohup python $COMMAND >> "$LOG_FILE" 2>&1 &

NEW_PID=$!
echo "Started trading_api with PID: $NEW_PID"

exit 0
