from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from flask import current_app
from sqlalchemy import case, func, or_

from .. import db
from ..models.enums import OrganizerStatus
from ..models.user import Organizer, User
from .organizer_approval_email_service import send_organizer_status_email


VALID_ORGANIZER_STATUSES = {"PENDING", "APPROVED", "REJECTED"}


@dataclass(frozen=True)
class OrganizerApprovalRow:
    id: int
    name: str
    username: str
    email: str
    phone: str
    status: str


@dataclass(frozen=True)
class OrganizerApprovalDetail:
    id: int
    name: str
    username: str
    email: str
    phone: str
    status: str
    created_at: str
    avatar: str | None


def _format_dt(value: datetime | None) -> str:
    if value is None:
        return "—"
    try:
        return value.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(value)


def _ensure_organizer_status_values():
    changed = False
    for value in VALID_ORGANIZER_STATUSES:
        if db.session.get(OrganizerStatus, value) is None:
            db.session.add(OrganizerStatus(status=value))
            changed = True

    if changed:
        db.session.flush()


def list_organizers_for_approval(*, q: str = "", status: str = "all") -> list[OrganizerApprovalRow]:
    normalized_q = (q or "").strip()
    normalized_status = (status or "all").strip().upper()

    query = (
        db.session.query(Organizer, User)
        .join(User, User.id == Organizer.id)
    )

    if normalized_status != "ALL":
        if normalized_status not in VALID_ORGANIZER_STATUSES:
            normalized_status = "ALL"
        else:
            query = query.filter(Organizer.status == normalized_status)

    if normalized_q:
        like = f"%{normalized_q}%"
        query = query.filter(
            or_(
                User.name.ilike(like),
                User.username.ilike(like),
                User.email.ilike(like),
                User.phoneNumber.ilike(like),
            )
        )

    status_sort_key = case(
        (Organizer.status == "PENDING", 0),
        (Organizer.status == "APPROVED", 1),
        else_=2,
    )

    query = query.order_by(status_sort_key.asc(), func.coalesce(User.createdAt, func.now()).desc(), Organizer.id.desc())

    rows: list[OrganizerApprovalRow] = []
    for organizer, user in query.all():
        rows.append(
            OrganizerApprovalRow(
                id=int(user.id),
                name=(user.name or "").strip() or "—",
                username=(user.username or "").strip() or "—",
                email=(user.email or "").strip() or "—",
                phone=(user.phoneNumber or "").strip() or "—",
                status=(organizer.status or "PENDING").strip().upper(),
            )
        )

    return rows


def get_organizer_approval_detail(*, organizer_id: int) -> OrganizerApprovalDetail | None:
    try:
        organizer_id_int = int(organizer_id)
    except (TypeError, ValueError):
        return None

    result = (
        db.session.query(Organizer, User)
        .join(User, User.id == Organizer.id)
        .filter(Organizer.id == organizer_id_int)
        .first()
    )
    if not result:
        return None

    organizer, user = result
    return OrganizerApprovalDetail(
        id=int(user.id),
        name=(user.name or "").strip() or "—",
        username=(user.username or "").strip() or "—",
        email=(user.email or "").strip() or "—",
        phone=(user.phoneNumber or "").strip() or "—",
        status=(organizer.status or "PENDING").strip().upper(),
        created_at=_format_dt(getattr(user, "createdAt", None)),
        avatar=(getattr(user, "avatar", None) or None),
    )


def set_organizer_status(*, organizer_id: int, new_status: str) -> str | None:
    try:
        organizer_id_int = int(organizer_id)
    except (TypeError, ValueError):
        return "Organizer ID không hợp lệ."

    normalized_status = (new_status or "").strip().upper()
    if normalized_status not in VALID_ORGANIZER_STATUSES:
        return "Trạng thái cập nhật không hợp lệ."

    organizer = db.session.get(Organizer, organizer_id_int)
    if organizer is None:
        return "Organizer không tồn tại."

    current_status = (organizer.status or "PENDING").strip().upper()
    if current_status == normalized_status:
        return "Trạng thái không thay đổi."

    _ensure_organizer_status_values()

    organizer.status = normalized_status
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return "Không thể cập nhật trạng thái nhà tổ chức. Vui lòng thử lại."
    if normalized_status in {"APPROVED", "REJECTED"}:
        organizer_user = db.session.get(User, organizer_id_int)
        if organizer_user is not None:
            try:
                send_organizer_status_email(organizer_user=organizer_user, new_status=normalized_status)
            except Exception:
                current_app.logger.exception(
                    "Failed to send organizer approval email (organizer_id=%s, status=%s)",
                    organizer_id_int,
                    normalized_status,
                )
    return None
