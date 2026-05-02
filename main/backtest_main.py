import argparse
import asyncio
import logging
import sys

sys.path.insert(0, "../")

from trading_engine.backtest_replay import run_backtest_job_from_cli


def main():
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Replay 1m bars and emit chart bundles (NYSE session).")
    parser.add_argument("--portfolio-id", required=False, default="p107", help="Portfolio id (config-{id}.yaml)")
    parser.add_argument(
        "--config-folder",
        required=False,
        default="",
        help="Absolute or relative folder containing configs/ (defaults to sibling ../configs from main/).",
    )
    args = parser.parse_args()

    asyncio.run(run_backtest_job_from_cli(portfolio_id=args.portfolio_id, config_folder=args.config_folder))


if __name__ == "__main__":
    main()
