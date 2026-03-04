#
#
cd /opt/u107_level_driven_algo/bin-bash
source ../venv/bin/activate
LOG_DIR="../../portfolios/p107/logs"
LOG_FILE="$LOG_DIR/main.log"
echo "Starting app ..."
echo "Logging to $LOG_FILE"
nohup python ../main/main.py --portfolio-id=p107  >> "$LOG_FILE" 2>&1 &
exit 0


