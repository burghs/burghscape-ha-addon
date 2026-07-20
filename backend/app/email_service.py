"""Email service for Burghscape Pty Ltd — uses SMTP or logs to console if SMTP not configured."""
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import secrets

# SMTP Configuration (set via environment variables)
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "noreply@mybeacon.co.za")
SMTP_TLS = os.environ.get("SMTP_TLS", "true").lower() == "true"

# Testing override: redirect all emails to this address
TESTING_EMAIL = os.environ.get("TESTING_EMAIL", "")


def _log_email(to: str, subject: str, body: str):
    """Log email to console when SMTP is not configured."""
    print(f"\n{'='*60}")
    print(f"📧 EMAIL TO: {to}")
    print(f"📋 SUBJECT: {subject}")
    print(f"{'='*60}")
    print(body)
    print(f"{'='*60}\n")


def send_email(to: str, subject: str, html_body: str, text_body: str = "") -> bool:
    """Send an email. Falls back to console logging if SMTP not configured."""
    if not SMTP_HOST:
        _log_email(to, subject, text_body or html_body)
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = SMTP_FROM
        msg["To"] = to
        msg["Subject"] = subject

        if text_body:
            msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            if SMTP_TLS:
                server.starttls()
            if SMTP_USER and SMTP_PASS:
                server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_FROM, to, msg.as_string())

        return True
    except Exception as e:
        print(f"Email send failed: {e}")
        # Fall back to logging
        _log_email(to, subject, text_body or html_body)
        return False


def generate_temp_password(length: int = 10) -> str:
    """Generate a secure temporary password."""
    alphabet = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def send_welcome_email(to_email: str, client_name: str, temp_password: str, client_portal_url: str, ha_external_url: str = None):
    """Send welcome email to new client with their portal credentials."""
    APP_ENV = os.environ.get("APP_ENV", "production").lower()
    if APP_ENV == "development" and TESTING_EMAIL:
        actual_to = TESTING_EMAIL
    else:
        actual_to = to_email

    portal_url = client_portal_url.rstrip("/")
    getting_started_url = f"{portal_url}/portal/getting-started"
    remote_url = ha_external_url or "Your Burghscape Remote URL will activate after the Burghscape Agent connects."
    subject = "Welcome to Burghscape Home Cloud"

    password_row = ""
    password_text = ""
    if temp_password:
        password_row = f"""
                            <tr><td style="padding:10px 0;">
                                <span style="color:#94a3b8; font-size:13px;">Temporary Password</span><br>
                                <code style="background:rgba(139,92,246,0.16); color:#ddd6fe; padding:8px 12px; border-radius:8px; font-size:15px; letter-spacing:1.5px; display:inline-block; margin-top:5px;">{temp_password}</code>
                            </td></tr>"""
        password_text = f"Temporary Password: {temp_password}\n"

    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Welcome to Burghscape Home Cloud</title>
</head>
<body style="margin:0; padding:0; background:#070817; font-family:'Segoe UI',Arial,sans-serif; color:#e5e7eb;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background:#070817; padding:36px 16px;">
        <tr><td align="center">
            <table width="600" cellpadding="0" cellspacing="0" style="width:100%; max-width:600px; border-collapse:separate; border-spacing:0;">
                <tr><td style="background:#0f1024; border:1px solid rgba(139,92,246,0.25); border-bottom:none; border-radius:18px 18px 0 0; padding:34px 28px 26px; text-align:center;">
                    <img src="https://mybeacon.co.za/static/brand/burghscape-shield-email.png" alt="Burghscape" style="height:56px; width:auto; max-width:92px; object-fit:contain; display:block; margin:0 auto 14px;">
                    <h1 style="color:#ffffff; margin:0; font-size:25px; line-height:1.25;">Welcome to Burghscape Home Cloud</h1>
                    <p style="color:#a78bfa; margin:8px 0 0; font-size:13px; letter-spacing:1.6px; text-transform:uppercase;">Secure smart home access and monitoring</p>
                </td></tr>

                <tr><td style="background:#111327; border-left:1px solid rgba(139,92,246,0.25); border-right:1px solid rgba(139,92,246,0.25); padding:30px 28px 8px;">
                    <h2 style="color:#ffffff; margin:0 0 12px; font-size:21px;">Hello {client_name},</h2>
                    <p style="color:#cbd5e1; margin:0 0 18px; font-size:15px; line-height:1.65;">
                        Your Burghscape Client Portal is ready. It gives you one place to access your Home Assistant remotely,
                        follow system health, and request support from Burghscape.
                    </p>
                </td></tr>

                <tr><td style="background:#111327; border-left:1px solid rgba(139,92,246,0.25); border-right:1px solid rgba(139,92,246,0.25); padding:10px 28px 22px;">
                    <div style="background:rgba(255,255,255,0.045); border:1px solid rgba(255,255,255,0.10); border-radius:14px; padding:22px;">
                        <h3 style="color:#ddd6fe; margin:0 0 12px; font-size:13px; text-transform:uppercase; letter-spacing:1.4px;">Your portal details</h3>
                        <table width="100%" cellpadding="0" cellspacing="0">
                            <tr><td style="padding:10px 0; border-bottom:1px solid rgba(255,255,255,0.08);">
                                <span style="color:#94a3b8; font-size:13px;">Client Portal</span><br>
                                <a href="{portal_url}" style="color:#c4b5fd; font-size:15px; text-decoration:none;">{portal_url}</a>
                            </td></tr>
                            <tr><td style="padding:10px 0; border-bottom:1px solid rgba(255,255,255,0.08);">
                                <span style="color:#94a3b8; font-size:13px;">Login Email</span><br>
                                <span style="color:#f8fafc; font-size:15px;">{to_email}</span>
                            </td></tr>
                            {password_row}
                        </table>
                        <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:18px;">
                            <tr>
                                <td style="padding:0 0 10px;"><a href="{portal_url}" style="display:block; background:linear-gradient(135deg,#8b5cf6,#6d28d9); color:#ffffff; text-align:center; padding:14px 16px; border-radius:11px; text-decoration:none; font-weight:700; font-size:14px;">Login to Your Portal</a></td>
                            </tr>
                            <tr>
                                <td><a href="{getting_started_url}" style="display:block; background:rgba(139,92,246,0.12); border:1px solid rgba(167,139,250,0.34); color:#ddd6fe; text-align:center; padding:13px 16px; border-radius:11px; text-decoration:none; font-weight:600; font-size:14px;">Open Getting Started Guide</a></td>
                            </tr>
                        </table>
                    </div>
                </td></tr>

                <tr><td style="background:#111327; border-left:1px solid rgba(139,92,246,0.25); border-right:1px solid rgba(139,92,246,0.25); padding:0 28px 22px;">
                    <h3 style="color:#ffffff; margin:0 0 12px; font-size:16px;">What happens next</h3>
                    <table width="100%" cellpadding="0" cellspacing="0">
                        <tr><td style="padding:8px 0; color:#cbd5e1; font-size:14px; line-height:1.55;"><strong style="color:#ffffff;">1. Sign in</strong><br><span style="color:#94a3b8;">Use the details above and change your temporary password when prompted.</span></td></tr>
                        <tr><td style="padding:8px 0; color:#cbd5e1; font-size:14px; line-height:1.55;"><strong style="color:#ffffff;">2. Follow Getting Started</strong><br><span style="color:#94a3b8;">The guide walks you through the Burghscape Agent, Home Assistant token, and mobile app setup.</span></td></tr>
                        <tr><td style="padding:8px 0; color:#cbd5e1; font-size:14px; line-height:1.55;"><strong style="color:#ffffff;">3. Use your Remote URL</strong><br><span style="color:#94a3b8;">{remote_url}</span></td></tr>
                    </table>
                </td></tr>

                <tr><td style="background:#111327; border-left:1px solid rgba(139,92,246,0.25); border-right:1px solid rgba(139,92,246,0.25); padding:0 28px 24px;">
                    <div style="background:rgba(251,191,36,0.08); border:1px solid rgba(251,191,36,0.24); border-radius:12px; padding:16px 18px;">
                        <p style="color:#fbbf24; margin:0; font-size:13px; line-height:1.6;"><strong>Security note:</strong> Burghscape will never ask you to email your Home Assistant password or full access tokens. Keep tokens private and share them only inside the approved setup fields.</p>
                    </div>
                </td></tr>

                <tr><td style="background:#080917; border:1px solid rgba(139,92,246,0.25); border-top:none; border-radius:0 0 18px 18px; padding:24px 28px; text-align:center;">
                    <p style="color:#94a3b8; margin:0; font-size:13px; line-height:1.6;">Need help? Reply to this email or open a support ticket from the Burghscape Client Portal.<br><span style="color:#64748b;">Powered by Burghscape Pty Ltd · MyBeacon platform</span></p>
                </td></tr>
            </table>
        </td></tr>
    </table>
</body>
</html>
"""

    text = f"""
Welcome to Burghscape Home Cloud, {client_name}.

Your Burghscape Client Portal is ready.

Portal URL: {portal_url}
Login Email: {to_email}
{password_text}Getting Started Guide: {getting_started_url}
Remote URL: {remote_url}

What happens next:
1. Sign in to your portal and change your temporary password if prompted.
2. Follow the Getting Started Guide to install and configure the Burghscape Agent.
3. Use your Burghscape Remote URL after the secure connection is active.

Security note: Burghscape will never ask you to email your Home Assistant password or full access tokens.

Need help? Reply to this email or open a support ticket from the Burghscape Client Portal.
Burghscape Pty Ltd - MyBeacon platform
"""

    return send_email(actual_to, subject, html, text)

def send_password_reset_email(to_email: str, client_name: str, reset_token: str, portal_url: str):
    """Send password reset email."""
    APP_ENV = os.environ.get("APP_ENV", "production").lower()
    if APP_ENV == "development" and TESTING_EMAIL:
        actual_to = TESTING_EMAIL
    else:
        actual_to = to_email
    subject = "Burghscape — Password Reset Request"

    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #333;">
        <div style="background: #1e293b; padding: 20px; border-radius: 8px 8px 0 0; text-align: center;">
            <h1 style="color: #fff; margin: 0;">Burghscape</h1>
        </div>
        <div style="background: #fff; padding: 30px; border: 1px solid #e2e8f0; border-top: none;">
            <h2 style="color: #1e293b;">Password Reset</h2>
            <p>Hi {client_name},</p>
            <p>We received a request to reset your portal password. Use the code below to set a new password:</p>
            <div style="background: #f1f5f9; padding: 20px; border-radius: 6px; text-align: center; margin: 20px 0;">
                <code style="font-size: 24px; letter-spacing: 4px; color: #1e293b;">{reset_token}</code>
            </div>
            <p style="color: #777; font-size: 13px;">This code will expire in 1 hour. If you did not request this, please ignore this email.</p>
            <p style="margin-top: 20px;"><a href="{portal_url}/reset?token={reset_token}" style="background: #3b82f6; color: #fff; padding: 10px 20px; border-radius: 5px; text-decoration: none;">Reset Password Online</a></p>
        </div>
    </div>
    """

    text = f"""
Hi {client_name},

Password reset requested for your Burghscape portal.

Reset code: {reset_token}

This code expires in 1 hour.

Reset online: {portal_url}/reset?token={reset_token}

If you did not request this, ignore this email.
"""

    return send_email(actual_to, subject, html, text)
