from __future__ import annotations

import os

from flask import current_app, render_template
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Content, Email, Mail as SendGridMail, To

from ..models.user import User

def _resolve_sendgrid_sender() -> str:
    sender = current_app.config.get("SENDGRID_FROM_EMAIL") or os.getenv("SENDGRID_FROM_EMAIL")
    if not sender:
        raise RuntimeError("SENDGRID_FROM_EMAIL is not configured")
    return sender


def _get_sendgrid_api_key() -> str | None:
    return current_app.config.get("SENDGRID_API_KEY") or os.getenv("SENDGRID_API_KEY")


def _send_organizer_status_email_sendgrid(subject: str, recipient: str, html: str) -> None:
    api_key = _get_sendgrid_api_key()
    if not api_key:
        raise RuntimeError("SENDGRID_API_KEY is not configured")

    message = SendGridMail(
        from_email=Email(_resolve_sendgrid_sender()),
        to_emails=To(recipient),
        subject=subject,
        html_content=Content("text/html", html),
    )

    client = SendGridAPIClient(api_key)
    response = client.send(message)
    if response.status_code >= 400:
        raise RuntimeError(f"SendGrid send failed: {response.status_code}")


def send_organizer_status_email(*, organizer_user: User, new_status: str) -> bool:
    """Send an email to organizer informing their approval status.

    Raises on failure; callers may choose whether to handle exceptions.
    """

    recipient = (getattr(organizer_user, "email", None) or "").strip()
    if not recipient:
        raise ValueError("Organizer does not have an email address")

    status = (new_status or "").strip().upper()
    if status == "APPROVED":
        subject = "[TicketHub] Tài khoản nhà tổ chức đã được duyệt"
    elif status == "REJECTED":
        subject = "[TicketHub] Tài khoản nhà tổ chức đã bị từ chối"
    else:
        subject = "[TicketHub] Cập nhật trạng thái tài khoản nhà tổ chức"

    organizer_name = (
        (getattr(organizer_user, "name", None) or "").strip()
        or (getattr(organizer_user, "username", None) or "").strip()
        or "Nhà tổ chức"
    )

    html = render_template(
        "organizer_approval_email.html",
        organizer_name=organizer_name,
        new_status=status,
    )

    _send_organizer_status_email_sendgrid(subject, recipient, html)

    return True
