# trading_core/logging_manager.py

import logging
import logging.handlers
import datetime


class LoggingManager:

    @staticmethod
    def setup(log_dir: str, portfolio_id: str, logging_level: str):

        log_file = f"{log_dir}/{portfolio_id}.log"

        handler = logging.handlers.RotatingFileHandler(
            filename=log_file,
            maxBytes=5 * 1024 * 1024,
            backupCount=200
        )

        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        handler.setFormatter(formatter)

        logging.basicConfig(
            # level=getattr(logging, logging_level),
            level=eval(logging_level),
            handlers=[handler, logging.StreamHandler()]
        )

        return logging.getLogger(portfolio_id)
