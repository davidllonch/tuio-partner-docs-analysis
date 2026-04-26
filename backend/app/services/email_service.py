import asyncio
import html
import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.services.ai_analysis import PROVIDER_TYPE_DISPLAY

logger = logging.getLogger(__name__)


def _send_smtp(
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    from_address: str,
    recipient: str,
    msg_string: str,
) -> None:
    """
    Synchronous SMTP send. Runs in a thread pool via asyncio.to_thread()
    so it does not block the async event loop.
    """
    # Use the system's trusted CA bundle to verify the SMTP server certificate.
    # Without this, a network attacker could intercept SMTP credentials via MITM.
    tls_context = ssl.create_default_context()
    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.ehlo()
        server.starttls(context=tls_context)
        server.login(smtp_user, smtp_password)
        server.sendmail(from_address, [recipient], msg_string)


async def send_submission_notification(
    provider_name: str,
    provider_type: str,
    recipient: str,
    from_address: str,
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    dashboard_url: str = "https://tuiopartnersdocs.42labs.es",
) -> None:
    """
    Send a brief notification email when a new partner submission arrives.

    Does NOT include the full AI analysis — analysts read that in the dashboard.
    Keeping the email small avoids SMTP size rejections and keeps notifications clean.
    """
    provider_display = PROVIDER_TYPE_DISPLAY.get(provider_type, provider_type)

    # Escape all values before embedding in HTML to prevent injection
    safe_name = html.escape(provider_name)
    safe_display = html.escape(provider_display)
    safe_dashboard_url = html.escape(dashboard_url)
    # Strip newlines to prevent email header injection — a malicious provider name
    # containing "\r\n" could otherwise inject extra headers into the email envelope.
    safe_subject_name = provider_name.replace("\r", "").replace("\n", "").strip()[:200]

    subject = f"Nueva documentación recibida – {safe_subject_name}"

    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #1a1a2e;">Nueva documentación de partner recibida</h2>
        <table style="border-collapse: collapse; width: 100%; margin-bottom: 20px;">
            <tr>
                <td style="padding: 8px 0; color: #555; width: 160px;"><strong>Partner:</strong></td>
                <td style="padding: 8px 0; color: #333;">{safe_name}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0; color: #555;"><strong>Tipo de proveedor:</strong></td>
                <td style="padding: 8px 0; color: #333;">{safe_display}</td>
            </tr>
        </table>
        <p style="color: #555;">
            La documentación ha sido recibida y el análisis KYC/KYB está disponible en el dashboard.
        </p>
        <p style="margin-top: 24px;">
            <a href="{safe_dashboard_url}"
               style="display: inline-block; background-color: #4f46e5; color: white; padding: 12px 24px;
                      text-decoration: none; border-radius: 6px; font-weight: bold; font-size: 14px;">
                Ver análisis en el Dashboard →
            </a>
        </p>
        <hr style="border: none; border-top: 1px solid #ddd; margin: 24px 0;" />
        <p style="font-size: 12px; color: #999;">
            Sistema de gestión documental KYC/KYB — Tuio
        </p>
    </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_address
    msg["To"] = recipient
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    msg_string = msg.as_string()

    try:
        # Run the blocking SMTP call in a thread pool so it does not freeze
        # the async event loop (and delay other concurrent requests)
        await asyncio.to_thread(
            _send_smtp,
            smtp_host,
            smtp_port,
            smtp_user,
            smtp_password,
            from_address,
            recipient,
            msg_string,
        )
        logger.info(
            "Submission notification email sent for provider '%s' to '%s'",
            provider_name,
            recipient,
        )
    except Exception as exc:
        logger.error(
            "Failed to send notification email for provider '%s': %s", provider_name, exc
        )
        raise
