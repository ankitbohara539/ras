from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from email.utils import formatdate, make_msgid
from html import escape
from urllib.parse import urlparse

import aiosmtplib
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger("civicgrid.email")


class EmailService(ABC):
    @abstractmethod
    async def send(self, recipient: str, subject: str, text: str, html: str) -> None: ...


class ConsoleEmailService(EmailService):
    async def send(self, recipient: str, subject: str, text: str, html: str) -> None:
        # Deliberately never log bodies: verification and reset URLs contain raw tokens.
        masked = recipient[:2] + "***@" + recipient.split("@")[-1]
        logger.info("email_development_sink", extra={"resource_id": f"{subject} -> {masked}"})


class SMTPEmailService(EmailService):
    async def send(self, recipient: str, subject: str, text: str, html: str) -> None:
        settings = get_settings()
        sender = str(settings.smtp_from_email)
        message = EmailMessage()
        message["From"] = f"{settings.smtp_from_name} <{sender}>"
        message["To"] = recipient
        message["Subject"] = subject
        message["Date"] = formatdate(localtime=False)
        message["Message-ID"] = make_msgid(domain=sender.rsplit("@", 1)[-1])
        if settings.smtp_reply_to:
            message["Reply-To"] = str(settings.smtp_reply_to)
        message.set_content(text)
        message.add_alternative(html, subtype="html")
        masked = recipient[:2] + "***@" + recipient.split("@")[-1]
        try:
            await aiosmtplib.send(
                message,
                hostname=settings.smtp_host,
                port=settings.smtp_port,
                username=settings.smtp_username,
                password=settings.smtp_password,
                use_tls=settings.smtp_security == "tls",
                start_tls=settings.smtp_security == "starttls",
                validate_certs=True,
                timeout=settings.smtp_timeout_seconds,
            )
        except Exception:
            logger.exception(
                "email_delivery_failed",
                extra={"resource_id": f"{subject} -> {masked}"},
            )
            raise
        logger.info(
            "email_delivered",
            extra={"resource_id": f"{subject} -> {masked}"},
        )


def get_email_service() -> EmailService:
    return SMTPEmailService() if get_settings().smtp_enabled else ConsoleEmailService()


def password_reset_email(reset_url: str) -> tuple[str, str, str]:
    subject = "Reset your CivicGrid password"
    text = (
        "A password reset was requested for your CivicGrid account.\n\n"
        f"Reset your password: {reset_url}\n\n"
        "This link expires in 1 hour and can only be used once. "
        "If you did not request this, you can ignore this email."
    )
    html = _action_email_html(
        title="Reset your password",
        introduction="Use the secure link below to choose a new CivicGrid password.",
        action_url=reset_url,
        action_label="Reset password",
        expiry="This link expires in 1 hour and can only be used once.",
    )
    return subject, text, html


def _action_email_html(
    *, title: str, introduction: str, action_url: str, action_label: str, expiry: str
) -> str:
    safe_url = escape(action_url, quote=True)
    display_host = escape(urlparse(action_url).netloc or "CivicGrid")
    return f"""<!doctype html>
<html lang="en">
  <body style="margin:0;background:#f3f7f5;font-family:Arial,sans-serif;color:#173532">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
      <tr><td align="center" style="padding:32px 16px">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
               style="max-width:560px;background:#ffffff;border:1px solid #dce8e4;border-radius:16px">
          <tr><td style="padding:32px">
            <p style="margin:0 0 18px;color:#0b846d;font-weight:700">CivicGrid</p>
            <h1 style="font-size:24px;margin:0 0 16px">{escape(title)}</h1>
            <p style="line-height:1.6;margin:0 0 24px">{escape(introduction)}</p>
            <p style="margin:0 0 24px">
              <a href="{safe_url}" style="display:inline-block;background:#0b695c;color:#ffffff;
                 text-decoration:none;font-weight:700;padding:13px 20px;border-radius:9px">
                {escape(action_label)}
              </a>
            </p>
            <p style="font-size:14px;line-height:1.5;color:#526965">{escape(expiry)}</p>
            <p style="font-size:13px;line-height:1.5;color:#71827f">
              If the button does not work, copy this address into your browser:<br>
              <a href="{safe_url}" style="color:#0b695c;word-break:break-all">{safe_url}</a>
            </p>
            <p style="font-size:12px;color:#8a9996">Link destination: {display_host}</p>
          </td></tr>
        </table>
      </td></tr>
    </table>
  </body>
</html>"""
