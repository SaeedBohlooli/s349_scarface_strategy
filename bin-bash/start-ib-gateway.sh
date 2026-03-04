


log_info() {
	  echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO ] $1"
}

log_info "-------------------"
log_info "Starting restart ...."
log_info "Calling stop ..."

log_info "Starting IBG ...."

cd /opt/ibc
xvfb-run -a ./gatewaystart.sh  -inline

log_info "IBG started ...."



#!/usr/bin/env bash

cd /opt/u107_level_driven_algo/bin-bash || exit 1
source ../venv/bin/activate

PORTFOLIO_ID="p107"
SCRIPT_PATH="../trading_api/trading_api_service.py"
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

$COMMAND

NEW_PID=$!
echo "Started trading_api with PID: $NEW_PID"

exit 0
