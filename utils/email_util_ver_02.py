import email, smtplib, ssl
import logging

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from utils import miscutils

logger = logging.getLogger(__name__)


def send_email(to_emails, subject, body):
    logger.info(f'to_emails: {to_emails} ')
    logger.info(f'body: {body} ')
    logger.info(f'subject: {subject} ')

    if to_emails == "" or to_emails == "x":
        logger.info(f'we are not sending emails ...to_emails: {to_emails} ')
        return
    try:

        if isinstance(to_emails, str):
            # split by comma or semicolon and strip whitespace
            to_list = [e.strip() for e in to_emails.replace(";", ",").split(",") if e.strip()]
        else:
            to_list = to_emails

        logger.info(f"Resolved recipients: {to_list}")

        username = 'sambob1020@gmail.com'
        password = 'qkbj tgfj osuj nged'
        fromMy = 'Samo App<sambob1020@gmail.com>'

        message = MIMEMultipart()
        message["From"] = fromMy
        message["To"] = to_emails
        message["Subject"] = subject
        # Add body to email
        message.attach(MIMEText(body, "html"))

        # SMTP_SSL Example
        server_ssl = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server_ssl.ehlo()  # optional, called by login()
        server_ssl.login(username, password)
        # ssl server doesn't support or need tls, so don't call server_ssl.starttls()
        server_ssl.sendmail(fromMy, to_list, message.as_string())
        # server_ssl.quit()
        server_ssl.close()
        logger.warning('successfully sent the mail')
    except Exception as e:
        logger.error(f"{e}")

    return

if __name__ == "__main__":
   send_email('saeed.bx1@yahoo.com,bs24680@gmail.com', 'This is for App using list  ', "Hi <br> you may come ... <br>")
