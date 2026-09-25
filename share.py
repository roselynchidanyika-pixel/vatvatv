"""share.py — Send the final management report by email (SMTP) and by WhatsApp
(deep link). Credentials are read from Streamlit secrets — NEVER from the
repository. Nothing secret is logged or committed.
"""

from __future__ import annotations

import os
import urllib.parse
from email.message import EmailMessage
from smtplib import SMTP_SSL, SMTP

import streamlit as st


def _smtp_config():
    """Read SMTP config from Streamlit secrets, then environment variables.
    Locally this may also be an .env exported by the user (never committed)."""
    s = st.secrets.get("smtp", {}) or {}
    cfg = {
        "host": s.get("host") or os.environ.get("SMTP_HOST", ""),
        "port": int(s.get("port") or os.environ.get("SMTP_PORT", 465)),
        "user": s.get("user") or os.environ.get("SMTP_USER", ""),
        "password": s.get("password") or os.environ.get("SMTP_PASSWORD", ""),
        "sender": s.get("sender") or os.environ.get("SMTP_SENDER", ""),
        "use_ssl": bool(s.get("use_ssl", True)),
    }
    return cfg


def smtp_configured():
    cfg = _smtp_config()
    return all([cfg["host"], cfg["user"], cfg["password"], cfg["sender"]])


def send_email(subject, body_markdown, recipients):
    """Send the management report via SMTP.

    Returns (ok: bool, message: str). Never raises: failures are returned as a
    clear user-facing message.
    """
    if isinstance(recipients, str):
        recipients = [r.strip() for r in recipients.split(",") if r.strip()]
    if not recipients:
        return False, "No recipient email addresses were provided."
    cfg = _smtp_config()
    if not all([cfg["host"], cfg["user"], cfg["password"], cfg["sender"]]):
        return False, ("SMTP is not configured. Add an [smtp] section to the "
                       "Streamlit secrets (host, port, user, password, sender).")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg["sender"]
    msg["To"] = ", ".join(recipients)
    from report_generator import md_to_text
    msg.set_content(md_to_text(body_markdown))

    try:
        if cfg.get("use_ssl", True):
            with SMTP_SSL(cfg["host"], cfg["port"], timeout=20) as server:
                server.login(cfg["user"], cfg["password"])
                server.send_message(msg)
        else:
            with SMTP(cfg["host"], cfg["port"], timeout=20) as server:
                server.ehlo()
                if int(cfg["port"]) != 25:
                    server.starttls(context=None)
                    server.ehlo()
                server.login(cfg["user"], cfg["password"])
                server.send_message(msg)
        return True, f"Email sent to {', '.join(recipients)}."
    except Exception as exc:
        return False, f"Email could not be sent: {type(exc).__name__}: {exc}"


def whatsapp_link(phone, text):
    """Build a wa.me deep-link so the user can share the report in WhatsApp.
    No API key required. phone should be digits (international format)."""
    if not phone:
        phone = "263000000000"
    phone = "".join(ch for ch in phone if ch.isdigit())
    return f"https://wa.me/{phone}?text={urllib.parse.quote(text)}"