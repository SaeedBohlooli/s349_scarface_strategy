

from trading_core.bootstrap import Boot

boot = Boot(portfolio_id="p250", mode="live")

logger = boot.logger
app_config = boot.app_config
dirs = boot.dirs

intermediate_dir = dirs.intermediate
application_state_file_path = f"{intermediate_dir}/84-application_state.csv"

print(application_state_file_path)
