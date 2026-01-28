import requests
import time

import logging
import json
import os
logger = logging.getLogger(__name__)


# Try this
# https://api.nasdaq.com/api/quote/nvda/option-chain?assetclass=stocks
#
# This is work around ...

def get_strikes(symbol):
    global options_meta_date_dic

    try:
        asset_class = "etf" if symbol in ["SPY", "QQQ"] else "stocks"
        url = f"https://api.nasdaq.com/api/quote/{symbol}/option-chain?assetclass={asset_class}"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()
        #print(data)

        rows = data.get("data", {}).get("table", {}).get("rows", [])
        if not rows:
            print(f"{symbol}: ⚠️ No options data found.")
            return []

        strikes = sorted({
            float(x.get("strike") or x.get("strikePrice"))
            for x in rows if (x.get("strike") or x.get("strikePrice"))
        })
        # ignore it for now. it is loke this ['None', 'Nov 14', 'Nov 21', 'Nov 28']
        # expreis are not good ....
        expiries = sorted({
            str(x.get("expiryDate") or x.get("expiryDate"))
            for x in rows if (x.get("expiryDate") or x.get("expirygroup"))
        })

        print(f"{symbol}: {len(strikes)} valid strikes")
        strikes = list(sorted(set(strikes)))

        print(strikes)

        expirations = list(sorted(set(expiries)))
        print(expirations)


        options_meta_date_dic[f'{symbol}-strikes'] = strikes
        return strikes

    except Exception as e:
        print(f"{symbol}: ❌ Error → {e}")
        print(data)
        return []


def dump_a_map_to_file(map, file_path):
    with open(file_path, 'w') as f:
        try:
            logger.info(f"saving at file_path: {file_path}")
            json.dump(map, f, indent=4)
            logger.info(f"saving done. ")
        except Exception as e:
            # TODO add
            logger.error(e)
    return


if __name__ == "__main__":

    options_meta_date_dic = {}

    for symbol in ['QQQ', 'TSLA', 'AAPL', 'NVDA', 'AMD', 'PLTR', 'TSLL', 'AMZN', 'MNQ', 'SPY' , 'MU']:
        print(f"\n===== {symbol} =====")
        get_strikes(symbol)
        time.sleep(1)

    intermediate_dir = f'../../portfolios/shared'
    os.makedirs(intermediate_dir, exist_ok=True)
    if os.path.exists(intermediate_dir):
        file_path = f'{intermediate_dir}/85-strikes-nazdaq.json'
        dump_a_map_to_file(options_meta_date_dic, file_path )