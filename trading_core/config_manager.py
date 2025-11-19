# trading_core/config_manager.py

from trading_utils import config_utils


class ConfigManager:

    @staticmethod
    def load(portfolio_id: str):
        return config_utils.load_app_config(portfolio_id)
