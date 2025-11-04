from typing import Optional
from app.settings import get_settings
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.utils.logger import logger

# Get settings instance
settings = get_settings()

def send_organization_invite_email(
    email_to: str,
    organization_name: str,
    invite_token: str
) -> None:
    """Send organization invite email"""
    if not all([settings.SMTP_HOST, settings.SMTP_PORT, settings.SMTP_USER, settings.SMTP_PASSWORD]):
        logger.warning("Email settings not configured. Skipping email send.")
        return

    try:
        msg = MIMEMultipart()
        msg["From"] = settings.EMAILS_FROM_EMAIL
        msg["To"] = email_to
        msg["Subject"] = f"Invitation to join {organization_name}"

        body = f"""
        You have been invited to join {organization_name}.
        
        Click the following link to accept the invitation:
        {settings.FRONTEND_URL}/accept-invite?token={invite_token}
        
        This invitation will expire in {settings.INVITE_TOKEN_EXPIRE_HOURS} hours.
        """

        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            if settings.SMTP_TLS:
                server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
            
        logger.info(f"Invite email sent to {email_to}")
    except Exception as e:
        logger.error(f"Failed to send invite email: {str(e)}")
        raise 