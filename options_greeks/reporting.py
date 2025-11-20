import os
from datetime import datetime
from alerts import send_email_alert, send_telegram_alert


def export_portfolio(df, export_dir, timestamp):
    """Save ES portfolio to CSV with fixed 6-decimal numeric precision."""
    filename = os.path.join(export_dir, f"ES_FOP_Portfolio_{timestamp}.csv")
    df.to_csv(filename, index=False, float_format="%.6f")
    return filename


def send_alerts(df, filepath, email_enabled, telegram_enabled):
    """Send summary alert via email and/or Telegram."""
    total_delta = df["DeltaExposure"].sum()
    total_gamma = df["GammaExposure"].sum()
    total_vega = df["VegaExposure"].sum()
    total_theta = df["ThetaExposure"].sum()
    total_pnl = df["UnrealizedPnL"].sum()
    hedge = round(-total_delta / 50.0, 2)

    msg = (
        f"✅ ES Options Snapshot Complete\n"
        f"File: {filepath}\n"
        f"Rows: {len(df)}\n"
        f"Δ: {total_delta:+,.2f} | Γ: {total_gamma:+,.2f} | "
        f"V: {total_vega:+,.2f} | Θ: {total_theta:+,.2f}\n"
        f"PnL: {total_pnl:+,.2f} | Hedge: {hedge:+,.2f} ES\n"
        f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )

    if email_enabled:
        try:
            send_email_alert("ES Options Report", msg, filepath)
        except Exception as e:
            print(f"⚠️ Email alert failed: {e}")
    if telegram_enabled:
        try:
            send_telegram_alert(msg, filepath)
        except Exception as e:
            print(f"⚠️ Telegram alert failed: {e}")
