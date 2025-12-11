from ib_insync import *
import pandas as pd
from datetime import datetime, timedelta

# ==============================================================
# CONFIGURE HERE
# ==============================================================

START_DATE = "2025-01-01"
OUTPUT_CSV = "MNQ_1min_2025_to_now.csv"
IB_HOST = "127.0.0.1"
IB_PORT = 4002
IB_CLIENT_ID = 20

# ==============================================================
# MAIN PROCEDURE
# ==============================================================

def download_mnq_1min_continuous(start_date_str, output_csv):
    # Connect to IBKR
    print("Connecting to IBKR...")
    ib = IB()
    ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID)

    # Continuous future (the correct IB contract for MNQ history)
    contract = ContFuture("MNQ", exchange="GLOBEX")

    # Ensure IBKR resolves it
    qc = ib.qualifyContracts(contract)
    if not qc:
        print("❌ Could not qualify MNQ continuous contract. Check permissions.")
        return
    contract = qc[0]

    print("Connected. Contract resolved:", contract)

    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.now()

    all_rows = []
    cur = start_date

    print("\nStarting historical download...")
    print("From:", start_date, "To:", end_date, "\n")

    while cur <= end_date:
        try:
            print(f"Downloading {cur.strftime('%Y-%m-%d')} ...")

            bars = ib.reqHistoricalData(
                contract,
                endDateTime=cur.strftime("%Y%m%d 23:59:59"),
                durationStr="1 D",
                barSizeSetting="1 min",
                whatToShow="TRADES",
                useRTH=False,
                formatDate=1,
                keepUpToDate=False
            )

            if bars:
                df = util.df(bars)
                df["contract"] = contract.localSymbol
                all_rows.append(df)
            else:
                print(f"⚠ No data for {cur.strftime('%Y-%m-%d')}")

        except Exception as e:
            print(f"⚠ Error requesting {cur}: {e}")

        cur += timedelta(days=1)

    ib.disconnect()

    if not all_rows:
        print("❌ No data downloaded.")
        return

    final_df = pd.concat(all_rows)
    final_df.sort_values("date", inplace=True)
    final_df.to_csv(output_csv, index=False)

    print(f"\n=================================================")
    print(f"✅ Download completed successfully.")
    print(f"📁 Saved CSV → {output_csv}")
    print(f"=================================================\n")


# ==============================================================
# RUN SCRIPT
# ==============================================================

if __name__ == "__main__":
    download_mnq_1min_continuous(START_DATE, OUTPUT_CSV)
