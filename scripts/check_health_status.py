import time
from datetime import datetime, timedelta
import os
import sys
sys.path.insert(0, f'../')
from utils import email_util_ver_02

mode = 'live'
portfolio_id = 'p250'
log_dir = f'../../portfolios/logs/{portfolio_id}-{mode}'

def check_health_status(log_path=f"{log_dir}/health_status.log"):
    if not os.path.exists(log_path):
        print("⚠️ Health log not found — application might be down.")
        return False

    try:
        with open(log_path, "r", encoding="utf-8") as f:
            line = f.readline().strip()
    except Exception as e:
        print(f"⚠️ Error reading health file: {e}")
        return False

    if not line:
        print("⚠️ Health file is empty — no status found.")
        return False

    # Expected line format: "2025-10-28 22:15:03 - APPLICATION IS HEALTHY"
    try:
        timestamp_str, _ = line.split(" - ", 1)
        last_healthy_time = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        print(f"⚠️ Invalid format in health file: {line}")
        return False

    now = datetime.now()
    diff = now - last_healthy_time

    if diff > timedelta(minutes=2):
        print(f"🚨 {datetime.now()} - Application might be hanged! Last healthy update was {diff.seconds // 60} minutes ago.")
        return False
    else:
        print(f"✅ {datetime.now()} - Application is healthy (last update {diff.seconds // 60} minutes ago).")
        return True

    return False

if __name__ == "__main__":
    while True:
        now = datetime.now()
        current_hh_mm_ny = int(now.strftime("%H%M"))
        is_healthy = check_health_status()
        if 920 < current_hh_mm_ny < 1100 and not is_healthy:
            email_util_ver_02.send_email('saeed.bx1@yahoo.com', f'{portfolio_id} is not healthy',
                                         body=f"<br\><br\><br\>Application is not healthy")
        time.sleep(1 * 60)
