import argparse
import email, smtplib, ssl
import socket
import logging
import os

from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from utils import miscutils
logger = miscutils.setup_logger(__name__, logging.WARNING)

def send_email(to_emails, subject, body):
    logger.info(f'to_emails: {to_emails} ')
    logger.info(f'body: {body} ')
    logger.info(f'subject: {subject} ')

    if to_emails == "" or to_emails == "x":
        logger.info(f'we are not sending emails ...to_emails: {to_emails} ')

        return

    if True:
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
        server_ssl.sendmail(fromMy, to_emails, message.as_string())
        # server_ssl.quit()
        server_ssl.close()
        logger.warning('successfully sent the mail')
    return
