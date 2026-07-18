"""
SMTP email sending for SLM Studio.

Covers four transactional emails:
  - welcome email, right after successful registration
  - login notification, right after a successful login
  - password reset code, as part of the forgot-password flow
  - verification email, for account activation
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger(__name__)


def _get_html_template(title: str, content_html: str) -> str:
    """Centralized layout featuring premium typography and responsive structural spacing."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title}</title>
    </head>
    <body style="margin: 0; padding: 0; background-color: #fafafa; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; -webkit-font-smoothing: antialiased;">
        <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #fafafa; padding: 48px 20px;">
            <tr>
                <td align="center">
                    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 520px; background-color: #ffffff; border: 1px solid #e5e7eb; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.06);">
                        
                        <!-- Header / Branding -->
                        <tr>
                            <td align="left" style="padding: 32px 40px 24px 40px; border-bottom: 1px solid #f3f4f6;">
                                <span style="font-size: 20px; font-weight: 700; letter-spacing: -0.3px; color: #111827;">
                                    SLM <span style="color: #10b981;">Studio</span>
                                </span>
                            </td>
                        </tr>
                        
                        <!-- Content Body -->
                        <tr>
                            <td style="padding: 40px 40px 32px 40px; color: #374151; font-size: 15px; line-height: 1.6;">
                                {content_html}
                            </td>
                        </tr>
                        
                        <!-- Corporate Footer -->
                        <tr>
                            <td align="left" style="padding: 0 40px 32px 40px;">
                                <table border="0" cellpadding="0" cellspacing="0" width="100%" style="border-top: 1px solid #f3f4f6; padding-top: 24px;">
                                    <tr>
                                        <td style="color: #9ca3af; font-size: 12px; line-height: 1.5;">
                                            This is an automated operational message from SLM Studio.<br>
                                            &copy; 2026 SLM Studio. All rights reserved.
                                        </td>
                                    </tr>
                                </table>
                            </td>
                        </tr>
                        
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """


def _send_email(to_email: str, subject: str, html_body: str, text_body: str | None = None) -> bool:
    if not settings.SMTP_HOST or not settings.SMTP_USERNAME or not settings.SMTP_PASSWORD:
        logger.warning(f"SMTP not configured — skipping email '{subject}' to {to_email}")
        return False

    from_addr = settings.SMTP_FROM_EMAIL or settings.SMTP_USERNAME
    from_name = getattr(settings, "SMTP_FROM_NAME", "SLM Studio")
    formatted_from = f"{from_name} <{from_addr}>"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formatted_from
    msg["To"] = to_email

    if text_body:
        msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        if settings.SMTP_USE_TLS:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)
        try:
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.sendmail(from_addr, [to_email], msg.as_string())
        finally:
            server.quit()
        return True
    except Exception as e:
        logger.error(f"Failed to send email ({type(e).__name__}): {subject}")
        return False


def send_welcome_email(to_email: str, full_name: str) -> bool:
    subject = "Welcome to SLM Studio"
    
    body_html = f"""
    <h2 style="color: #111827; font-size: 22px; font-weight: 600; margin-top: 0; margin-bottom: 16px;">Welcome to SLM Studio</h2>
    <p style="margin-bottom: 12px;">Hello {full_name},</p>
    <p style="margin-bottom: 24px;">Your account has been successfully created. SLM Studio provides a streamlined interface for organizing your custom datasets, structuring workflows, and monitoring small language model fine-tuning processes.</p>
    
    <table border="0" cellpadding="0" cellspacing="0" style="margin-bottom: 32px;">
        <tr>
            <td align="center" bgcolor="#10b981" style="border-radius: 6px;">
                <a href="{settings.FRONTEND_BASE_URL}/dashboard" target="_blank" style="display: inline-block; padding: 12px 24px; color: #ffffff; font-weight: 500; text-decoration: none; font-size: 14px;">Open Dashboard</a>
            </td>
        </tr>
    </table>
    
    <p style="color: #6b7280; font-size: 13px; margin: 0;">If you have any questions or require assistance setting up your environment, please refer to the documentation links within your workspace platform.</p>
    """
    
    html = _get_html_template(subject, body_html)
    text = f"Hello {full_name}, welcome to SLM Studio. Your account is active. Access your workspace at {settings.FRONTEND_BASE_URL}/dashboard"
    return _send_email(to_email, subject, html, text)


def send_login_notification_email(to_email: str, full_name: str) -> bool:
    subject = "New sign-in detected for your SLM Studio account"
    
    body_html = f"""
    <h2 style="color: #111827; font-size: 20px; font-weight: 600; margin-top: 0; margin-bottom: 16px;">Security Notification</h2>
    <p style="margin-bottom: 12px;">Hello {full_name},</p>
    <p style="margin-bottom: 24px;">We detected a new sign-in to your SLM Studio account. If this activity was initiated by you, no further action is required.</p>
    
    <div style="background-color: #fffbeb; border-left: 4px solid #f59e0b; padding: 16px; border-radius: 6px; margin-bottom: 24px;">
        <p style="margin: 0; font-size: 13px; color: #78350f; line-height: 1.5;">
            <strong>Important:</strong> If you do not recognize this sign-in attempt, please update your security credentials immediately to safeguard your project data and compute settings.
        </p>
    </div>
    
    <p style="margin-bottom: 0;"><a href="{settings.FRONTEND_BASE_URL}/forgot-password" target="_blank" style="color: #10b981; font-weight: 500; text-decoration: none;">Reset your password &rarr;</a></p>
    """
    
    html = _get_html_template(subject, body_html)
    text = f"Hello {full_name}, a new sign-in was detected. If this wasn't you, reset your password at {settings.FRONTEND_BASE_URL}/forgot-password"
    return _send_email(to_email, subject, html, text)


def send_password_reset_code_email(to_email: str, code: str) -> bool:
    subject = "Your SLM Studio verification code"
    
    body_html = f"""
    <h2 style="color: #111827; font-size: 20px; font-weight: 600; margin-top: 0; margin-bottom: 16px;">Password Reset Request</h2>
    <p style="margin-bottom: 24px;">We received a request to reset the password for your SLM Studio account. Use the secure authorization code below to complete the modification. This code will expire in 15 minutes.</p>
    
    <div style="font-size: 28px; font-weight: 700; letter-spacing: 6px; text-align: center; padding: 18px; background-color: #f9fafb; color: #111827; border: 1px solid #e5e7eb; border-radius: 8px; margin-bottom: 24px; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;">
        {code}
    </div>
    
    <p style="color: #6b7280; font-size: 13px; margin: 0;">If you did not make this request, you can safely ignore this email. Your account security has not been compromised.</p>
    """
    
    html = _get_html_template(subject, body_html)
    text = f"Your SLM Studio password reset code is: {code}. It expires in 15 minutes."
    return _send_email(to_email, subject, html, text)


def send_verification_email(to_email: str, token: str) -> bool:
    subject = "Verify your SLM Studio email address"
    verify_url = f"{settings.FRONTEND_BASE_URL}/verify-email?token={token}"
    
    body_html = f"""
    <h2 style="color: #111827; font-size: 20px; font-weight: 600; margin-top: 0; margin-bottom: 16px;">Verify Email Address</h2>
    <p style="margin-bottom: 24px;">Thank you for registering with SLM Studio. Please verify your email address to activate your workspace access. This invitation link will expire in 24 hours.</p>
    
    <table border="0" cellpadding="0" cellspacing="0" style="margin-bottom: 32px;">
        <tr>
            <td align="center" bgcolor="#10b981" style="border-radius: 6px;">
                <a href="{verify_url}" target="_blank" style="display: inline-block; padding: 12px 24px; color: #ffffff; font-weight: 500; text-decoration: none; font-size: 14px;">Verify Email Address</a>
            </td>
        </tr>
    </table>
    
    <p style="color: #6b7280; font-size: 13px; margin: 0; border-top: 1px solid #f3f4f6; padding-top: 20px;">If the button above does not work, copy and paste the following URL into your browser address bar:<br>
    <a href="{verify_url}" style="color: #10b981; word-break: break-all; font-size: 13px;">{verify_url}</a></p>
    """
    
    html = _get_html_template(subject, body_html)
    text = f"Verify your email address by visiting: {verify_url}"
    return _send_email(to_email, subject, html, text)