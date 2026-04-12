"""Email notification service.

Primary:  Resend HTTP API (port 443 — works everywhere including Render)
Fallback: Gmail SMTP (port 587 — works locally, blocked on Render)

Selection logic:
  - If RESEND_API_KEY is set → use Resend
  - Else if SMTP_PASSWORD is set → use Gmail SMTP
  - Else → raise error
"""

import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"


# ─────────────────────────────────────────────────────────────────────────────
async def _send_via_resend(to: str, subject: str, html_body: str) -> dict:
    settings = get_settings()
    payload = {
        "from": settings.EMAIL_FROM,
        "to": [to],
        "subject": subject,
        "html": html_body,
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                RESEND_API_URL,
                json=payload,
                headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
            )
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        logger.error("Resend API connection error: %s", e)
        raise RuntimeError(f"Cannot reach email service: {e}")

    if resp.status_code == 403:
        body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        msg = body.get("message", resp.text)
        if "testing emails" in msg:
            logger.error("Resend domain not verified — can only send to account owner")
            raise RuntimeError(
                "Email domain not verified. Verify a domain at resend.com/domains "
                "to send emails to candidates, or send test emails to the account owner only."
            )
        raise RuntimeError(f"Email delivery forbidden: {msg}")

    if resp.status_code >= 400:
        logger.error("Resend API error %d: %s", resp.status_code, resp.text)
        raise RuntimeError(f"Email delivery failed ({resp.status_code}): {resp.text}")

    data = resp.json()
    logger.info("Email sent to %s via Resend — id=%s", to, data.get("id"))
    return data


# ─────────────────────────────────────────────────────────────────────────────
def _send_smtp_blocking(to: str, subject: str, html_body: str) -> None:
    """Blocking SMTP send — called via asyncio.to_thread."""
    settings = get_settings()
    msg = MIMEMultipart("alternative")
    msg["From"] = settings.EMAIL_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
        server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.EMAIL_FROM, [to], msg.as_string())


async def _send_via_smtp(to: str, subject: str, html_body: str) -> dict:
    settings = get_settings()
    try:
        await asyncio.to_thread(_send_smtp_blocking, to, subject, html_body)
    except smtplib.SMTPAuthenticationError as e:
        logger.error("SMTP auth failed: %s", e)
        raise RuntimeError("Gmail authentication failed. Check SMTP_USER and SMTP_PASSWORD.")
    except OSError as e:
        logger.error("SMTP connection error: %s", e)
        raise RuntimeError(f"SMTP connection failed: {e}")
    except smtplib.SMTPException as e:
        logger.error("SMTP error sending to %s: %s", to, e)
        raise RuntimeError(f"Email delivery failed: {e}")

    logger.info("Email sent to %s via Gmail SMTP", to)
    return {"to": to, "status": "sent"}


# ─────────────────────────────────────────────────────────────────────────────
async def send_email(
    to: str,
    subject: str,
    html_body: str,
) -> dict:
    """Send email — Resend (primary) with SMTP fallback."""
    settings = get_settings()

    if settings.RESEND_API_KEY:
        return await _send_via_resend(to, subject, html_body)

    if settings.SMTP_PASSWORD:
        return await _send_via_smtp(to, subject, html_body)

    logger.error("No email provider configured — set RESEND_API_KEY or SMTP_PASSWORD")
    raise RuntimeError(
        "Email service not configured. Set RESEND_API_KEY (production) or SMTP_PASSWORD (local)."
    )


def build_shortlisted_email(
    candidate_name: str,
    job_title: str,
    custom_message: str | None = None,
) -> tuple[str, str]:
    """Build subject and HTML body for a shortlisted notification."""
    subject = f"Great news! You've been shortlisted — {job_title}"

    greeting = candidate_name or "there"
    message_block = custom_message or (
        "After careful review of your application, we are pleased to inform you that "
        "you have been <strong>shortlisted</strong> for the next stage of our selection process. "
        "A member of our hiring team will be reaching out to you shortly to schedule a conversation."
    )

    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 32px 24px; color: #1e293b;">
      <div style="text-align: center; margin-bottom: 24px;">
        <div style="display: inline-block; width: 40px; height: 40px; line-height: 40px; border-radius: 10px; background: #4f46e5; color: white; font-weight: bold; font-size: 18px;">R</div>
      </div>
      <h2 style="color: #1e293b; margin-bottom: 8px;">Congratulations, {greeting}!</h2>
      <p style="color: #475569; line-height: 1.6;">{message_block}</p>
      <div style="background: #f0fdf4; border-left: 4px solid #22c55e; padding: 16px; border-radius: 8px; margin: 24px 0;">
        <strong style="color: #166534;">Position:</strong> {job_title}
      </div>
      <p style="color: #475569; line-height: 1.6;">We look forward to speaking with you soon.</p>
      <p style="color: #94a3b8; font-size: 13px; margin-top: 32px;">— RAX Resume Analysis eXpert</p>
    </div>
    """
    return subject, html


def build_rejected_email(
    candidate_name: str,
    job_title: str,
    gaps: list | None = None,
    strengths: list | None = None,
    custom_message: str | None = None,
) -> tuple[str, str]:
    """Build subject and HTML body for a rejection notification with constructive feedback."""
    subject = f"Update on your application — {job_title}"

    greeting = candidate_name or "there"
    message_block = custom_message or (
        "Thank you for your interest and the time you invested in applying. "
        "After careful evaluation, we have decided to move forward with other candidates "
        "whose experience more closely matches the current requirements."
    )

    # Build feedback sections from analysis data
    gaps_html = ""
    if gaps and len(gaps) > 0:
        top_gaps = gaps[:3]
        items = "".join(f"<li style='margin-bottom: 6px; color: #475569;'>{g}</li>" for g in top_gaps)
        gaps_html = f"""
        <div style="background: #fff7ed; border-left: 4px solid #f97316; padding: 16px; border-radius: 8px; margin: 16px 0;">
          <strong style="color: #9a3412;">Areas for growth:</strong>
          <ul style="margin: 8px 0 0 0; padding-left: 20px;">{items}</ul>
        </div>
        """

    strengths_html = ""
    if strengths and len(strengths) > 0:
        top_strengths = strengths[:3]
        items = "".join(f"<li style='margin-bottom: 6px; color: #475569;'>{s}</li>" for s in top_strengths)
        strengths_html = f"""
        <div style="background: #f0fdf4; border-left: 4px solid #22c55e; padding: 16px; border-radius: 8px; margin: 16px 0;">
          <strong style="color: #166534;">What stood out:</strong>
          <ul style="margin: 8px 0 0 0; padding-left: 20px;">{items}</ul>
        </div>
        """

    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 32px 24px; color: #1e293b;">
      <div style="text-align: center; margin-bottom: 24px;">
        <div style="display: inline-block; width: 40px; height: 40px; line-height: 40px; border-radius: 10px; background: #4f46e5; color: white; font-weight: bold; font-size: 18px;">R</div>
      </div>
      <h2 style="color: #1e293b; margin-bottom: 8px;">Hi {greeting},</h2>
      <p style="color: #475569; line-height: 1.6;">{message_block}</p>
      <div style="background: #f8fafc; border-left: 4px solid #6366f1; padding: 16px; border-radius: 8px; margin: 24px 0;">
        <strong style="color: #4338ca;">Position:</strong> {job_title}
      </div>
      {strengths_html}
      {gaps_html}
      <p style="color: #475569; line-height: 1.6;">
        We encourage you to continue developing in these areas. We wish you the very best in your career journey, 
        and we hope you'll consider applying for future opportunities with us.
      </p>
      <p style="color: #94a3b8; font-size: 13px; margin-top: 32px;">— RAX Resume Analysis eXpert</p>
    </div>
    """
    return subject, html
