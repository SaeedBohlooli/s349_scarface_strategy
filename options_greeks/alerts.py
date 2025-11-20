import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import requests
from config import (
    ENABLE_EMAIL_ALERT, ENABLE_TELEGRAM_ALERT,
    SMTP_SERVER, SMTP_PORT, EMAIL_USER, EMAIL_PASS, EMAIL_TO,
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
)

def send_email_alert(subject, body, attachment_path=None):
    """Send email alert (optionally with file attachment)."""
    if not ENABLE_EMAIL_ALERT:
        return

    try:
        msg = MIMEMultipart()
        msg["Subject"] = subject
        msg["From"] = EMAIL_USER
        msg["To"] = EMAIL_TO
        msg.attach(MIMEText(body, "plain"))

        if attachment_path:
            with open(attachment_path, "rb") as f:
                part = MIMEApplication(f.read(), Name=attachment_path.split("/")[-1])
                part['Content-Disposition'] = f'attachment; filename="{attachment_path.split("/")[-1]}"'
                msg.attach(part)

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASS)
            server.send_message(msg)
        print("📧 Email alert sent successfully.")
    except Exception as e:
        print(f"⚠️ Email alert failed: {e}")

def send_telegram_alert(message, attachment_path=None):
    """Send Telegram message (optionally with CSV attachment)."""
    if not ENABLE_TELEGRAM_ALERT:
        return

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            print("💬 Telegram alert sent successfully.")
        else:
            print(f"⚠️ Telegram alert failed: {r.text}")

        if attachment_path:
            url_file = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
            with open(attachment_path, "rb") as f:
                files = {"document": f}
                data = {"chat_id": TELEGRAM_CHAT_ID, "caption": "📎 CSV file attached"}
                rf = requests.post(url_file, data=data, files=files, timeout=20)
                if rf.status_code == 200:
                    print("📂 Telegram CSV uploaded successfully.")
                else:
                    print(f"⚠️ Telegram file upload failed: {rf.text}")

    except Exception as e:
        print(f"⚠️ Telegram alert error: {e}")
