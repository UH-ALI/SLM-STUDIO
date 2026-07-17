"""
backend/app/core/email.py

Gmail SMTP email service for SLM Studio.
Sends verification and password-reset emails using Python built-in smtplib.
No extra pip dependencies needed.

If SMTP_USER is empty (not configured), sending is silently skipped and the
token is logged at WARNING level so development still works without a mailbox.
"""

import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger(__name__)


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _send(to_email: str, subject: str, html_body: str) -> None:
    """
    Low-level SMTP sender.  Connects to Gmail over STARTTLS on port 587,
    authenticates, sends, and closes.
    """
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        logger.warning(
            "[Email] SMTP not configured. Would have sent '%s' to <%s>.",
            subject,
            to_email,
        )
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_USER}>"
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        smtp.sendmail(settings.SMTP_USER, to_email, msg.as_string())

    logger.info("[Email] Sent '%s' to <%s>.", subject, to_email)


def _base_template(title: str, heading: str, body_html: str, cta_url: str, cta_label: str) -> str:
    """Shared branded HTML wrapper for all SLM Studio emails."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title}</title>
  <style>
    body {{ margin: 0; padding: 0; background: #0d1117; font-family: 'Segoe UI', Arial, sans-serif; color: #c9d1d9; }}
    .wrapper {{ max-width: 520px; margin: 40px auto; background: #161b22; border: 1px solid #30363d; border-radius: 12px; overflow: hidden; }}
    .header {{ background: linear-gradient(135deg, #1a2e1e 0%, #0d1117 100%); padding: 32px 40px 24px; text-align: center; }}
    .logo {{ font-size: 22px; font-weight: 700; color: #d4a843; letter-spacing: 0.5px; }}
    .logo span {{ color: #6ec37a; }}
    .body {{ padding: 32px 40px; }}
    h1 {{ font-size: 20px; font-weight: 600; color: #e6edf3; margin: 0 0 12px; }}
    p {{ font-size: 14px; line-height: 1.6; color: #8b949e; margin: 0 0 20px; }}
    .cta {{ display: block; width: fit-content; margin: 0 auto 24px; padding: 12px 28px; background: #d4a843; color: #0d1117; text-decoration: none; border-radius: 8px; font-weight: 700; font-size: 14px; }}
    .divider {{ border: none; border-top: 1px solid #21262d; margin: 24px 0; }}
    .small {{ font-size: 12px; color: #6e7681; }}
    .footer {{ padding: 16px 40px; background: #0d1117; text-align: center; font-size: 11px; color: #484f58; }}
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="header">
      <div class="logo">SLM <span>Studio</span></div>
    </div>
    <div class="body">
      <h1>{heading}</h1>
      {body_html}
      <a class="cta" href="{cta_url}">{cta_label}</a>
      <hr class="divider" />
      <p class="small">
        If you did not request this, you can safely ignore this email.
        This link expires automatically.
      </p>
    </div>
    <div class="footer">
      &copy; 2026 SLM Studio &mdash; AI Fine-Tuning Platform
    </div>
  </div>
</body>
</html>"""


# ─── Public API ───────────────────────────────────────────────────────────────

def send_verification_email(to_email: str, token: str) -> None:
    """Send account email-verification link. Valid 24 hours."""
    verify_url = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    body_html = """
      <p>Thanks for signing up! To activate your SLM Studio account, please
      verify your email address by clicking the button below.</p>
      <p>This link is valid for <strong>24 hours</strong>.</p>
    """
    html = _base_template(
        title="Verify your SLM Studio email",
        heading="Verify your email address",
        body_html=body_html,
        cta_url=verify_url,
        cta_label="Verify Email Address",
    )
    _send(to_email, "Verify your SLM Studio email", html)


def send_password_reset_email(to_email: str, token: str) -> None:
    """Send password-reset link. Single-use, valid 15 minutes."""
    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    body_html = """
      <p>We received a request to reset your SLM Studio password.</p>
      <p>Click the button below to choose a new password.
      This link is valid for <strong>15 minutes</strong> and can only be used once.</p>
    """
    html = _base_template(
        title="Reset your SLM Studio password",
        heading="Reset your password",
        body_html=body_html,
        cta_url=reset_url,
        cta_label="Reset Password",
    )
    _send(to_email, "Reset your SLM Studio password", html)
