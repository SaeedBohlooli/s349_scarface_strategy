#
#
cd /opt/u107_level_driven_algo/bin-bash
source ../venv/bin/activate
LOG_DIR="../../portfolios/p107/logs"
LOG_FILE="$LOG_DIR/chart.log"
echo "Starting app ..."
echo "Logging to $LOG_FILE"
nohup python ../scripts/charts_ver1.py  >> "$LOG_FILE" 2>&1 &
exit 0

