import sys
sys.path.insert(0, f'../')

from trading_utils import ib_offline_miscs


if __name__ == "__main__":
    ib_offline_miscs.orchestrate(portfolio_id='p250')