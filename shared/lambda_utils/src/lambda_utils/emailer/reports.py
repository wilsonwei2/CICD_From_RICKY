import smtplib
import logging
from os.path import basename
from email.mime.application import MIMEApplication
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import COMMASPACE, formataddr
from email import encoders

logger = logging.getLogger(__name__)


def send(params, subject=None, body=None, files=None, excel_files=None):
    sender = params["email_sender"]
    # Parameters for SES SMTP
    sender_name = params.get("email_sender_name", "")
    port = int(params.get("email_port", "587"))
    host = params.get("email_host", "smtp.gmail.com")
    smtp_username = params.get("smtp_username", sender)
    smtp_password = params.get("smtp_password", params.get("email_sender_password",""))
    recipients = params.get("email_recipients", "").split(' ')
    if filter(None, recipients):
        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = formataddr((sender_name, sender)) if  sender_name else sender
        msg['To'] = COMMASPACE.join(recipients)
        msg.attach(MIMEText(body))

        # Attach files
        for f in files or []:
            for k, v in f.items():
                part = MIMEApplication(v, Name=basename(k))
                part['Content-Disposition'] = 'attachment; filename="%s"' % basename(k)
                msg.attach(part)

        # Attach Excel files
        for f in excel_files or []:
            for k, v in f.items():
                part = MIMEBase('application', "octet-stream")
                part.set_payload(v)
                encoders.encode_base64(part)
                part['Content-Disposition'] = 'attachment; filename="%s"' % basename(k)
                msg.attach(part)

        try:
            # Send the message via host
            s = smtplib.SMTP(host, port) if port else smtplib.SMTP(host)
            s.ehlo()
            s.starttls()
            #stmplib docs recommend calling ehlo() before & after starttls()
            s.ehlo()
            s.login(smtp_username, smtp_password)
            s.sendmail(sender, recipients, msg.as_string())
            s.close()
        except Exception as e:
            logger.error("Error while sending email. Error: %s" % (e), exc_info=True)
        else:
            logger.info("Email sent.")
            return True
    else:
        logger.info('No recipients specified, email %s not sent' % body)
