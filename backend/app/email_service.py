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


def send_welcome_email(to_email: str, client_name: str, temp_password: str, portal_url: str):
    """Send welcome email to new client with their portal credentials."""
    APP_ENV = os.environ.get("APP_ENV", "production").lower()
    if APP_ENV == "development" and TESTING_EMAIL:
        actual_to = TESTING_EMAIL
    else:
        actual_to = to_email

    subject = f"Welcome to Burghscape — Your Smart Home Portal is Ready 🏠"

    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Welcome to Burghscape</title>
</head>
<body style="margin:0; padding:0; background:#0a0a1a; font-family:'Segoe UI',Arial,sans-serif;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0a1a; padding:40px 20px;">
        <tr><td align="center">
            <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;">
                <!-- Header -->
                <tr><td style="background:linear-gradient(135deg,#8b5cf6,#6d28d9); border-radius:16px 16px 0 0; padding:40px 30px; text-align:center;">
                    <img src="https://mybeacon.co.za/static/brand/logo.png" alt="Burghscape" style="height:40px;margin:0 auto 8px;display:block">
                    <h1 style="color:#fff; margin:0; font-size:24px; letter-spacing:-0.5px;">Burghscape Pty Ltd</h1>
                    <p style="color:rgba(255,255,255,0.7); margin:8px 0 0; font-size:14px;">Smart Home Management Platform</p>
                </td></tr>
                <!-- Welcome -->
                <tr><td style="background:#12122a; padding:35px 30px 25px;">
                    <h2 style="color:#fff; margin:0 0 12px; font-size:22px;">Welcome, {client_name}! 👋</h2>
                    <p style="color:#94a3b8; margin:0; font-size:15px; line-height:1.6;">
                        Your Burghscape client portal is now live. From here you can monitor your smart home,
                        submit support tickets, and manage your account — all in one place.
                    </p>
                </td></tr>
                <!-- Login Box -->
                <tr><td style="background:#12122a; padding:0 30px 25px;">
                    <div style="background:rgba(139,92,246,0.08); border:1px solid rgba(139,92,246,0.2); border-radius:12px; padding:25px;">
                        <h3 style="color:#c4b5fd; margin:0 0 15px; font-size:14px; text-transform:uppercase; letter-spacing:1px;">Your Login Details</h3>
                        <table width="100%" cellpadding="0" cellspacing="0">
                            <tr><td style="padding:8px 0; border-bottom:1px solid rgba(139,92,246,0.1);">
                                <span style="color:#64748b; font-size:13px;">Portal URL</span><br>
                                <a href="{portal_url}" style="color:#a78bfa; font-size:15px; text-decoration:none;">{portal_url}</a>
                            </td></tr>
                            <tr><td style="padding:8px 0; border-bottom:1px solid rgba(139,92,246,0.1);">
                                <span style="color:#64748b; font-size:13px;">Email</span><br>
                                <span style="color:#e2e8f0; font-size:15px;">{to_email}</span>
                            </td></tr>
                            <tr><td style="padding:8px 0;">
                                <span style="color:#64748b; font-size:13px;">Temporary Password</span><br>
                                <code style="background:rgba(139,92,246,0.15); color:#c4b5fd; padding:6px 12px; border-radius:6px; font-size:16px; letter-spacing:2px; display:inline-block; margin-top:4px;">{temp_password}</code>
                            </td></tr>
                        </table>
                        <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:15px;">
                            <tr><td>
                                <a href="{portal_url}" style="display:block; background:linear-gradient(135deg,#8b5cf6,#6d28d9); color:#fff; text-align:center; padding:14px; border-radius:10px; text-decoration:none; font-weight:600; font-size:15px;">LOGIN TO YOUR PORTAL →</a>
                            </td></tr>
                        </table>
                    </div>
                </td></tr>
                <!-- Security Notice -->
                <tr><td style="background:#12122a; padding:0 30px 25px;">
                    <div style="background:rgba(251,191,36,0.06); border:1px solid rgba(251,191,36,0.2); border-radius:10px; padding:18px 20px;">
                        <p style="color:#fbbf24; margin:0; font-size:13px; line-height:1.6;">
                            ⚠️ <strong>Security Notice:</strong> Please change your temporary password immediately after your first login.
                            You will be prompted to set a new password automatically.
                        </p>
                    </div>
                </td></tr>
                <!-- How It Works -->
                <tr><td style="background:#12122a; padding:0 30px 25px;">
                    <h3 style="color:#fff; margin:0 0 15px; font-size:16px;">How It All Works</h3>
                    <table width="100%" cellpadding="0" cellspacing="0">
                        <tr><td style="padding:10px 0; vertical-align:top; width:36px;">
                            <span style="display:inline-block; width:28px; height:28px; background:rgba(139,92,246,0.2); border-radius:50%; text-align:center; line-height:28px; color:#a78bfa; font-size:13px; font-weight:600;">1</span>
                        </td><td style="padding:10px 0; vertical-align:top;">
                            <p style="color:#e2e8f0; margin:0; font-size:14px; line-height:1.5;"><strong>Log in to your portal</strong><br><span style="color:#64748b; font-size:13px;">Use the credentials above to access your client dashboard.</span></p>
                        </td></tr>
                        <tr><td style="padding:10px 0; vertical-align:top; width:36px;">
                            <span style="display:inline-block; width:28px; height:28px; background:rgba(139,92,246,0.2); border-radius:50%; text-align:center; line-height:28px; color:#a78bfa; font-size:13px; font-weight:600;">2</span>
                        </td><td style="padding:10px 0; vertical-align:top;">
                            <p style="color:#e2e8f0; margin:0; font-size:14px; line-height:1.5;"><strong>Access Home Assistant</strong><br><span style="color:#64748b; font-size:13px;">Click "Open Home Assistant" to reach your HA instance through a secure Cloudflare tunnel.</span></p>
                        </td></tr>
                        <tr><td style="padding:10px 0; vertical-align:top; width:36px;">
                            <span style="display:inline-block; width:28px; height:28px; background:rgba(139,92,246,0.2); border-radius:50%; text-align:center; line-height:28px; color:#a78bfa; font-size:13px; font-weight:600;">3</span>
                        </td><td style="padding:10px 0; vertical-align:top;">
                            <p style="color:#e2e8f0; margin:0; font-size:14px; line-height:1.5;"><strong>Monitor &amp; get support</strong><br><span style="color:#64748b; font-size:13px;">View system status, submit tickets, and track your monthly support hours.</span></p>
                        </td></tr>
                    </table>
                </td></tr>
                <!-- What You Can Do -->
                <tr><td style="background:#12122a; padding:0 30px 25px;">
                    <h3 style="color:#fff; margin:0 0 12px; font-size:16px;">What You Can Do</h3>
                    <table width="100%" cellpadding="0" cellspacing="0">
                        <tr><td style="padding:6px 0;"><span style="color:#8b5cf6;">●</span> <span style="color:#cbd5e1; font-size:14px;">View your HA instance status (online/offline, version, entities)</span></td></tr>
                        <tr><td style="padding:6px 0;"><span style="color:#8b5cf6;">●</span> <span style="color:#cbd5e1; font-size:14px;">Access Home Assistant securely via Cloudflare tunnel</span></td></tr>
                        <tr><td style="padding:6px 0;"><span style="color:#8b5cf6;">●</span> <span style="color:#cbd5e1; font-size:14px;">Submit and track support tickets</span></td></tr>
                        <tr><td style="padding:6px 0;"><span style="color:#8b5cf6;">●</span> <span style="color:#cbd5e1; font-size:14px;">Monitor monthly support hours used/remaining</span></td></tr>
                        <tr><td style="padding:6px 0;"><span style="color:#8b5cf6;">●</span> <span style="color:#cbd5e1; font-size:14px;">View HA release notes and breaking change alerts</span></td></tr>
                        <tr><td style="padding:6px 0;"><span style="color:#8b5cf6;">●</span> <span style="color:#cbd5e1; font-size:14px;">Manage additional portal users for your team</span></td></tr>
                    </table>
                </td></tr>
                <!-- Footer -->
                <tr><td style="background:#0a0a1a; border-radius:0 0 16px 16px; padding:25px 30px; text-align:center;">
                    <p style="color:#64748b; margin:0; font-size:13px; line-height:1.6;">
                        Need help? Submit a support ticket through your portal or reply to this email.<br>
                        <span style="color:#475569;">Burghscape Pty Ltd · mybeacon.co.za</span>
                    </p>
                </td></tr>
            </table>
        </td></tr>
    </table>
</body>
</html>
"""

    text = f"""
Welcome to Burghscape, {client_name}!

Your client portal is now live.

LOGIN DETAILS
=============
Portal URL: {portal_url}
Email: {to_email}
Temporary Password: {temp_password}

LOGIN NOW: {portal_url}

SECURITY NOTICE
===============
Please change your temporary password immediately after your first login.
You will be prompted to set a new password automatically.

HOW IT WORKS
============
1. Log in to your portal using the credentials above
2. Click "Open Home Assistant" to access your HA via secure Cloudflare tunnel
3. Monitor system status, submit tickets, and track support hours

WHAT YOU CAN DO
===============
- View your HA instance status (online/offline, version, entities)
- Access Home Assistant securely via Cloudflare tunnel
- Submit and track support tickets
- Monitor monthly support hours used/remaining
- View HA release notes and breaking change alerts
- Manage additional portal users for your team

NEED HELP?
==========
Submit a support ticket through your portal or reply to this email.
Burghscape Pty Ltd - mybeacon.co.za
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
