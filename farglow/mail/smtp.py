"""SMTP sending with STARTTLS (default), implicit TLS or plain (LAN relays only)."""
from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import make_msgid

from ..config import Settings


class MailDisabled(RuntimeError):
    pass


def build_message(settings: Settings, to: str, subject: str, text: str, html: str | None = None) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = settings.mail_from or f"Farglow <farglow@{settings.domain}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid(domain=settings.domain or None)
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")
    return msg


def send(settings: Settings, to: str, subject: str, text: str, html: str | None = None, timeout: int = 30) -> str:
    if not settings.mail_enabled:
        raise MailDisabled("SMTP is not configured (SMTP_HOST is empty)")
    msg = build_message(settings, to, subject, text, html)
    context = ssl.create_default_context()
    if settings.smtp_security == "ssl":
        client = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=timeout, context=context)
    else:
        client = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=timeout)
    with client:
        client.ehlo()
        if settings.smtp_security == "starttls":
            client.starttls(context=context)
            client.ehlo()
        if settings.smtp_user:
            client.login(settings.smtp_user, settings.smtp_password)
        client.send_message(msg)
    return msg["Message-ID"]
