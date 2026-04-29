#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd $SCRIPT_DIR || exit 1
echo "We are at script directory: $SCRIPT_DIR"
source ../venv/bin/activate

PORTFOLIO_ID="p107"
SCRIPT_PATH="../trading_api/trading_api_service.py"
COMMAND="${SCRIPT_PATH}  --portfolio-id=$PORTFOLIO_ID"

LOG_DIR="../../portfolios/${PORTFOLIO_ID}/logs"
LOG_FILE="$LOG_DIR/trading_api.log"
PID_FILE="$LOG_DIR/trading_api.pid"

mkdir -p "$LOG_DIR"

echo "--------------------------------------"
echo "Log file: $LOG_FILE"
echo "PID file: $PID_FILE"

# Check if PID file exists and process is still running
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    echo "Found previous PID file with PID: $OLD_PID"

    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "Previous process (PID: $OLD_PID) is still running. Killing it..."
        kill "$OLD_PID"
        sleep 1

        # Force kill if still running
        if kill -0 "$OLD_PID" 2>/dev/null; then
            echo "Force killing process..."
            kill -9 "$OLD_PID"
        fi
        echo "Previous process killed."
    else
        echo "Previous process (PID: $OLD_PID) is not running."
    fi
fi

echo "Starting new process..."
echo $COMMAND

nohup python $COMMAND >> "$LOG_FILE" 2>&1 &
NEW_PID=$!
echo "Started app with PID: $NEW_PID"

# Write PID to file
echo "$NEW_PID" > "$PID_FILE"
echo "Saved PID to $PID_FILE"

exit 0