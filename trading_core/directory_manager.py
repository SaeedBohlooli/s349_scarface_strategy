# trading_core/directory_manager.py

import os
import datetime

class DirectoryPaths:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

class DirectoryManager:

    def __init__(self, portfolio_id: str, mode: str):
        self.portfolio_id = portfolio_id
        self.mode = mode

        alias = '' if mode == 'live' else '-backtest'

        now = datetime.datetime.now().strftime("%Y-%m-%d")

        self.portfolio_dir = f'../../portfolios/results/{portfolio_id}{alias}'
        self.ib_dir = f'../../portfolios/ib/{portfolio_id}{alias}'
        self.reports_dir = f'../../portfolios/reports/{portfolio_id}{alias}'
        self.log_dir = f'../../portfolios/logs/{portfolio_id}{alias}/{now}'
        self.detailed_log_dir = f'../../portfolios/detailed-logs/{portfolio_id}{alias}'
        self.intermediate_dir = f'../../portfolios/intermediate/{portfolio_id}{alias}'
        self.ohlc_dir = f'../../portfolios/backtest-ohlc/{portfolio_id}{alias}'
        self.charts_dir = f'../../portfolios/charts/{portfolio_id}{alias}'
        self.ohlc_archive_dir = f'../../portfolios/ohlc-archive/{portfolio_id}'

        for d in [
            self.portfolio_dir, self.ib_dir, self.reports_dir, self.log_dir,
            self.detailed_log_dir, self.intermediate_dir, self.ohlc_dir,
            self.charts_dir, self.ohlc_archive_dir
        ]:
            os.makedirs(d, exist_ok=True)

        self.paths = DirectoryPaths(
            portfolio=self.portfolio_dir,
            ib=self.ib_dir,
            reports=self.reports_dir,
            log_dir=self.log_dir,
            detailed=self.detailed_log_dir,
            intermediate=self.intermediate_dir,
            ohlc=self.ohlc_dir,
            charts=self.charts_dir,
            ohlc_archive=self.ohlc_archive_dir
        )

    def __getattr__(self, item):
        return getattr(self.paths, item)
