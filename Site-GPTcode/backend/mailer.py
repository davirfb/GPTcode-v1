from __future__ import annotations

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def _config() -> tuple[str, str]:
    return (
        os.getenv("NOTIFICATION_EMAIL_FROM", "").strip(),
        os.getenv("NOTIFICATION_EMAIL_APP_PASSWORD", "").strip(),
    )


def send_notification(subject: str, body: str, recipients: list[str]) -> None:
    """Send a plain-text notification email via Gmail SMTP.

    Requires env vars:
      NOTIFICATION_EMAIL_FROM          – Gmail address used to send
      NOTIFICATION_EMAIL_APP_PASSWORD  – Google App Password (16 chars)

    Silently skips if not configured or if recipients list is empty.
    """
    email_from, app_password = _config()
    if not email_from or not app_password or not recipients:
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[GPTCode] {subject}"
    msg["From"] = email_from
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as smtp:
            smtp.login(email_from, app_password)
            smtp.sendmail(email_from, recipients, msg.as_string())
    except Exception:
        pass  # never crash the app because of email
