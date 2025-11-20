from datetime import datetime 
import time 
from options_greeks.core import fetch_and_export_es_options
# from options_greeks_file import fetch_and_export_es_options (non-Modular version)

if __name__ == "__main__":
    print("🕒 Starting hourly snapshot loop using modular version...")
    while True:
        start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n🚀 Starting new snapshot at {start_time}")
        try:
            fetch_and_export_es_options()
        except Exception as e:
            print(f"❌ Error during snapshot: {e}")

        print("😴 Sleeping for 60 minutes...\n")
        time.sleep(3600)

        # As at 2025-11-06 11:19am