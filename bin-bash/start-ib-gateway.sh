#!/usr/bin/env bash

cd /opt/ibc || exit 1

PORTFOLIO_ID="p107"
COMMAND="xvfb-run -a ./gatewaystart.sh  -inline"
PROCESS_MATCH="gatewaystart.sh"

LOG_DIR="../../portfolios/${PORTFOLIO_ID}/logs"
LOG_FILE="$LOG_DIR/gateway.log"

mkdir -p "$LOG_DIR"

echo "--------------------------------------"
echo "Log file: $LOG_FILE"

# 🔍 Check if already running
RUNNING_PID=$(pgrep -f "$PROCESS_MATCH")

if [ -n "$RUNNING_PID" ]; then
    echo "Process already running with PID(s): $RUNNING_PID"
    exit 0
fi

echo "Process not running. Starting..."
echo $COMMAND

xvfb-run -a ./gatewaystart.sh  -inline &

NEW_PID=$!
echo "Started trading_api with PID: $NEW_PID"

exit 0
