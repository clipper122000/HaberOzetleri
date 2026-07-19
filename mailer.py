import os
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def send_report_email(pdf_path: str, recipient_email: str = None) -> bool:
    """
    Sends the generated news summary PDF report via Gmail SMTP using
    credentials read securely from environment variables.
    """
    # 1. Retrieve and validate credentials
    gmail_user = os.environ.get("GMAIL_USER")
    gmail_app_password = os.environ.get("GMAIL_APP_PASSWORD")
    
    if not gmail_user or not gmail_app_password:
        logger.error(
            "SMTP credentials not found. Make sure GMAIL_USER and "
            "GMAIL_APP_PASSWORD are set in the environment variables."
        )
        return False
        
    # Default to sending the email to oneself if no recipient is explicitly set
    if not recipient_email:
        recipient_email = gmail_user
        
    today_str = datetime.now().strftime("%d.%m.%Y")
    pdf_filename = os.path.basename(pdf_path)
    
    logger.info(f"Preparing to send email to {recipient_email} with attachment {pdf_filename}")
    
    # 2. Build email headers
    msg = MIMEMultipart()
    msg["From"] = gmail_user
    msg["To"] = recipient_email
    msg["Subject"] = f"Günlük Haber Gündem Raporu - {today_str}"
    
    # 3. Build email body message
    body_text = f"""Merhaba,

Günün öne çıkan Türkiye ve Dünya basını gelişmelerini içeren derlenmiş haber özeti raporu ekte PDF olarak tarafınıza sunulmuştur.

İyi sabahlar ve verimli bir gün dileriz.

-- 
Otonom Haber Özetleyici Raporlama Sistemi
TSİ {datetime.now().strftime('%H:%M')}
"""
    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    
    # 4. Attach PDF document
    try:
        if not os.path.exists(pdf_path):
            logger.error(f"PDF file not found at path: {pdf_path}")
            return False
            
        with open(pdf_path, "rb") as attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())
            
        # Encode file to Base64
        encoders.encode_base64(part)
        
        # Add headers for the attachment
        part.add_header(
            "Content-Disposition",
            f"attachment; filename= {pdf_filename}",
        )
        msg.attach(part)
        
    except Exception as e:
        logger.error(f"Error preparing PDF attachment: {e}")
        return False
        
    # 5. Connect and send mail securely via Gmail SMTP (SSL Port 465)
    try:
        logger.info("Connecting to Gmail SMTP server on port 465...")
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            logger.info("Logging in...")
            server.login(gmail_user, gmail_app_password)
            
            logger.info("Sending email...")
            server.send_message(msg)
            
        logger.info("Email sent successfully!")
        return True
        
    except smtplib.SMTPAuthenticationError:
        logger.error("Authentication failed. Please verify your GMAIL_USER and GMAIL_APP_PASSWORD (App Password).")
    except Exception as e:
        logger.error(f"Failed to send email via SMTP: {e}")
        
    return False

if __name__ == "__main__":
    # Smoke test execution check
    print("Testing mailer module load structure...")
    import sys
    if len(sys.argv) > 1:
        test_pdf = sys.argv[1]
        print(f"Sending test mail with file {test_pdf}...")
        send_report_email(test_pdf)
    else:
        print("Provide a path to a PDF file to run actual mail sending test.")
