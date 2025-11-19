# trading_core/bootstrap.py

import os
import datetime
import logging
import logging.handlers
from trading_core.directory_manager import DirectoryManager
from trading_core.config_manager import ConfigManager
from trading_core.logging_manager import LoggingManager


class Boot:

    def __init__(self, portfolio_id: str, mode: str = "live"):
        self.portfolio_id = portfolio_id
        self.mode = mode

        # Directories
        self.dirs = DirectoryManager(portfolio_id, mode)

        # Config
        self.app_config = ConfigManager.load(portfolio_id)

        # Logging
        self.logger = LoggingManager.setup(
            log_dir=self.dirs.log_dir,
            portfolio_id=portfolio_id,
            logging_level=self.app_config.get("logging_level", "INFO")
        )
