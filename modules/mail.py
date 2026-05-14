"""Outbound email (SMTP). Used for application lifecycle and issued credentials."""

from __future__ import annotations

import logging
import os
import smtplib
from email.mime.text import MIMEText


def is_mail_configured() -> bool:
    return bool(os.environ.get("MAIL_SERVER") and os.environ.get("MAIL_FROM"))


def public_base_url() -> str:
    return os.environ.get("PUBLIC_BASE_URL", "http://127.0.0.1:5001").rstrip("/")


def _send_smtp(to_address: str, subject: str, body: str) -> None:
    if not is_mail_configured():
        return
    mail_from = os.environ["MAIL_FROM"]
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = mail_from
    msg["To"] = to_address

    server = os.environ["MAIL_SERVER"]
    port = int(os.environ.get("MAIL_PORT", "587"))
    user = os.environ.get("MAIL_USERNAME") or ""
    password = os.environ.get("MAIL_PASSWORD") or ""
    use_tls = os.environ.get("MAIL_USE_TLS", "1").strip().lower() in ("1", "true", "yes")

    if use_tls:
        with smtplib.SMTP(server, port, timeout=30) as smtp:
            smtp.starttls()
            if user:
                smtp.login(user, password)
            smtp.sendmail(mail_from, [to_address], msg.as_string())
    else:
        with smtplib.SMTP(server, port, timeout=30) as smtp:
            if user:
                smtp.login(user, password)
            smtp.sendmail(mail_from, [to_address], msg.as_string())


def send_mail_safe(to_address: str, subject: str, body: str) -> None:
    if not is_mail_configured():
        return
    try:
        _send_smtp(to_address, subject, body)
    except Exception:
        logging.exception("Failed to send email to %s", to_address)


def send_application_received_email(to_address: str, status_url: str) -> None:
    body = (
        "Your College0 application has been received.\n\n"
        f"You can check its status at:\n{status_url}\n\n"
        "You will receive another email if the registrar approves or rejects your application.\n"
    )
    send_mail_safe(to_address, "College0 — Application received", body)


def build_application_submit_credentials_body(
    username: str,
    temp_password: str,
    login_url: str,
    status_url: str,
) -> str:
    return (
        "Your College0 application has been received and is pending registrar review.\n\n"
        "You can sign in now with the credentials below to change your temporary password "
        "and check your application status. Full access to courses and the rest of the "
        "portal is granted after the registrar approves your application.\n\n"
        f"Username: {username}\n"
        f"Temporary password: {temp_password}\n\n"
        f"Sign in at: {login_url}\n\n"
        "On first sign-in you must choose a new password before continuing.\n\n"
        "Check application status (also available without logging in) at:\n"
        f"{status_url}\n"
    )


def send_application_credentials_email_strict(
    to_address: str,
    username: str,
    temp_password: str,
    login_url: str,
    status_url: str,
) -> None:
    """Email username + temp password when an application is submitted; raises on failure."""
    if not is_mail_configured():
        raise RuntimeError("Mail is not configured (MAIL_SERVER and MAIL_FROM).")
    body = build_application_submit_credentials_body(
        username, temp_password, login_url, status_url
    )
    _send_smtp(to_address, "College0 — Application received and your login", body)


def build_approval_credentials_body(
    username: str,
    temp_password: str,
    login_url: str,
    *,
    status_url: str | None = None,
    user_id: int | None = None,
) -> str:
    status_block = ""
    if status_url:
        status_block = (
            "\n"
            "View your application status (no login required) at:\n"
            f"{status_url}\n"
        )
    support_block = ""
    if user_id is not None:
        support_block = (
            "\n---\n"
            "Your account details (save for support):\n"
            f"User ID: {user_id}\n"
            f"Username: {username}\n"
            f"Temporary password: {temp_password}\n"
        )
    return (
        "Your College0 application was approved.\n\n"
        "A new temporary password has been set for your account (use it even if you "
        "signed in before approval).\n\n"
        f"Username: {username}\n"
        f"Temporary password: {temp_password}\n\n"
        f"Sign in at: {login_url}\n\n"
        "On next sign-in you must choose a new password before using the full portal.\n"
        f"{status_block}"
        f"{support_block}"
    )


def send_approval_credentials_email(
    to_address: str,
    username: str,
    temp_password: str,
    login_url: str,
    *,
    status_url: str | None = None,
    user_id: int | None = None,
) -> None:
    body = build_approval_credentials_body(
        username, temp_password, login_url, status_url=status_url, user_id=user_id
    )
    send_mail_safe(to_address, "College0 — Your account is ready", body)


def send_approval_credentials_email_strict(
    to_address: str,
    username: str,
    temp_password: str,
    login_url: str,
    *,
    status_url: str | None = None,
    user_id: int | None = None,
) -> None:
    """Send approval email; raises if SMTP is not configured or delivery fails."""
    if not is_mail_configured():
        raise RuntimeError("Mail is not configured (MAIL_SERVER and MAIL_FROM).")
    body = build_approval_credentials_body(
        username, temp_password, login_url, status_url=status_url, user_id=user_id
    )
    _send_smtp(to_address, "College0 — Your account is ready", body)
    logging.info(
        "Approval credentials email sent to %s (user_id=%s)",
        to_address,
        user_id if user_id is not None else "?",
    )


def send_application_rejected_email(to_address: str) -> None:
    body = (
        "Your College0 application was not approved by the registrar.\n\n"
        "If you think this is a mistake, contact the registrar office.\n"
    )
    send_mail_safe(to_address, "College0 — Application update", body)
