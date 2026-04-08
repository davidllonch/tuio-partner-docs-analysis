import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.services.ai_analysis import PROVIDER_TYPE_DISPLAY

logger = logging.getLogger(__name__)


async def send_kyc_report(
    provider_name: str,
    provider_type: str,
    ai_response: str,
    recipient: str,
    from_address: str,
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
) -> None:
    """
    Send the KYC/KYB analysis report by email using Google Workspace SMTP.

    Uses Python's built-in smtplib — no external service or API key required.
    The sending account must have a Google App Password configured.
    """
    provider_display = PROVIDER_TYPE_DISPLAY.get(provider_type, provider_type)
    subject = f"Revisión KYC/KYB – {provider_name} – {provider_display}"

    # Wrap the AI response in a minimal HTML layout.
    # We use <pre> with white-space: pre-wrap to preserve the AI's formatting
    # (line breaks, spacing) without requiring Markdown parsing.
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #1a1a2e;">Revisión KYC/KYB – {provider_name}</h2>
        <p style="color: #555;">
            <strong>Tipo de proveedor:</strong> {provider_display}
        </p>
        <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;" />
        <pre style="white-space: pre-wrap; font-family: Arial, sans-serif; font-size: 14px; color: #333;">{ai_response}</pre>
        <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;" />
        <p style="font-size: 12px; color: #999;">
            Este informe ha sido generado automáticamente por el sistema de gestión documental KYC/KYB.
        </p>
    </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_address
    msg["To"] = recipient
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(from_address, [recipient], msg.as_string())
        logger.info(
            "KYC report email sent for provider '%s' to '%s'", provider_name, recipient
        )
    except Exception as exc:
        logger.error(
            "Failed to send KYC report email for provider '%s': %s", provider_name, exc
        )
        raise
