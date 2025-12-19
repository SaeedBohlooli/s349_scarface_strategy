import argparse
import asyncio
import sys

sys.path.insert(0, f'../')

from trading_core.bootstrap import Boot
from trading_engine.engine import TradingEngine   # <-- you will create this


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--portfolio-id", required=False,default='p250', help="Portfolio ID for the trading engine")
    args = parser.parse_args()

    boot = Boot(args.portfolio_id)

    engine = TradingEngine(boot)

    asyncio.run(engine.run())   # <------ run async engine


if __name__ == "__main__":
    main()
