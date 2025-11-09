
# X Project 

### Checkout code
TBD

## Adding submodule
go to the project root and run below command  
git submodule add https://github.com/SaeedBohlooli/trading_utils.git

### volume ratio:

    df['volume_sma10'] = df['volume'].rolling(window=10).mean()
    df['VR'] = df['volume'] / df['volume_sma10']
    cap = df['VR'].quantile(0.95)  # 95th percentile
    df['VR'] = df['VR'].clip(upper=cap)
    df['VR_sma10'] = df['VR'].rolling(window=10).mean()

### RS relative 

    merged['stock_pct'] = merged['close_stock'] / stock_open - 1
    merged['qqq_pct'] = merged['close_qqq'] / qqq_open - 1
    merged['qqq_930'] = qqq_open
    merged['stock_930'] = stock_open

    # --- Relative performance ---

    merged['rs_rel'] = np.where(
        merged['qqq_pct'].abs() > 0.0005,
        merged['stock_pct'] / merged['qqq_pct'],
        np.nan
    ).clip(-10, 10)


### RS Delta 

    merged['rs_delta'] = merged['stock_pct'] - merged['qqq_pct']


## Run
TBD


