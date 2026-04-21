from __future__ import annotations

from flask import render_template
from flask_mail import Message

from .. import mail
from ..models.user import User


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

    msg = Message(subject=subject, recipients=[recipient])
    msg.html = render_template(
        "organizer_approval_email.html",
        organizer_name=organizer_name,
        new_status=status,
    )

    mail.send(msg)
    return True
