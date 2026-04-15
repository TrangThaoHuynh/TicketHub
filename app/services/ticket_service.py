from datetime import datetime, timezone
from io import BytesIO
import uuid
import qrcode

from sqlalchemy import func, or_

from .. import db
from ..models.ticket import Ticket
from ..models.ticket_type import TicketType
from ..models.event import Event
from ..utils.qr_utils import sign_payload


# Lấy danh sách loại vé của 1 sự kiện
def get_ticket_types_by_event_id(event_id: int):
    return TicketType.query.filter_by(eventId=event_id).all()


# Đếm số lượng vé đã bán theo ticket type
def count_sold_by_ticket_type(ticket_type_ids: list[int]) -> dict[int, int]:
    if not ticket_type_ids:
        return {}

    rows = (
        db.session.query(Ticket.ticketTypeId, func.count(Ticket.id))
        .filter(
            Ticket.ticketTypeId.in_(ticket_type_ids),
            Ticket.status.in_(["VALID", "USED"])
            # Nếu DB local của bạn vẫn còn dữ liệu cũ ACTIVE thì tạm dùng:
            # Ticket.status.in_(["ACTIVE", "VALID", "USED"])
        )
        .group_by(Ticket.ticketTypeId)
        .all()
    )

    return {ticket_type_id: count for ticket_type_id, count in rows}


# Lấy vé của người dùng
def get_tickets_of_user(
    user_id: int,
    q: str = "",
    status: str | None = None,
    page: int = 1,
    per_page: int = 12
):
    query = (
        Ticket.query
        .filter(Ticket.customerId == user_id)
        .order_by(Ticket.createdAt.desc())
    )

    if q:
        like_q = f"%{q.strip()}%"

        matching_ticket_type_ids = (
            db.session.query(TicketType.id)
            .filter(TicketType.name.ilike(like_q))
        )

        matching_event_ids = (
            db.session.query(Event.id)
            .filter(Event.title.ilike(like_q))
        )

        matching_ticket_type_ids_by_event = (
            db.session.query(TicketType.id)
            .filter(TicketType.eventId.in_(matching_event_ids))
        )

        query = query.filter(
            or_(
                Ticket.ticketCode.ilike(like_q),
                Ticket.fullName.ilike(like_q),
                Ticket.phoneNumber.ilike(like_q),
                Ticket.ticketTypeId.in_(matching_ticket_type_ids),
                Ticket.ticketTypeId.in_(matching_ticket_type_ids_by_event),
            )
        )

    if status:
        query = query.filter(Ticket.status == status)

    return query.paginate(page=page, per_page=per_page)


def get_ticket_by_id(ticket_id: str):
    return Ticket.query.get(ticket_id)


def get_ticket_by_qr(qr_code: str):
    return Ticket.query.filter_by(qrCode=qr_code).first()


def save_ticket_qr(ticket: Ticket, qr_code: str):
    ticket.qrCode = qr_code
    db.session.add(ticket)
    db.session.commit()


# Đánh dấu vé đã dùng
def mark_checked_in(ticket: Ticket):
    ticket.status = "USED"
    ticket.checkedIn = datetime.utcnow()
    db.session.add(ticket)
    db.session.commit()


def create_ticket(data: dict):
    ticket = Ticket(
        id=data.get("id") or str(uuid.uuid4()),
        fullName=data.get("fullName"),
        phoneNumber=data.get("phoneNumber"),
        price=data.get("price"),
        createdAt=datetime.now(),
        status=data.get("status", "PENDING"),
        bookingId=data.get("bookingId"),
        ticketTypeId=data.get("ticketTypeId"),
        customerId=data.get("customerId"),
        ticketCode=data.get("ticketCode"),
        faceEmbedding=data.get("faceEmbedding"),
    )

    db.session.add(ticket)
    db.session.commit()
    return ticket


def ensure_ticket_qr_token(ticket: Ticket):
    """
    Tạo token QR cho vé nếu chưa có.
    qrCode trong DB sẽ lưu token đã ký.
    """
    if ticket.qrCode:
        return ticket.qrCode

    ticket_type = TicketType.query.get(ticket.ticketTypeId)
    event_id = ticket_type.eventId if ticket_type else None

    iat = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    payload = {
        "ver": 1,
        "ticket_id": ticket.id,
        "ticket_code": ticket.ticketCode or ticket.id,
        "event_id": event_id,
        "customer_id": ticket.customerId,
        "booking_id": ticket.bookingId,
        "iat": iat,
    }

    ticket.qrCode = sign_payload(payload)
    db.session.add(ticket)
    db.session.commit()
    return ticket.qrCode


def build_ticket_qr_png(ticket: Ticket):
    """
    Trả về bytes PNG của mã QR từ token đã ký.
    """
    token = ensure_ticket_qr_token(ticket)
    img = qrcode.make(token)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def get_event_by_ticket(ticket: Ticket):
    ticket_type = TicketType.query.get(ticket.ticketTypeId)
    if not ticket_type:
        return None
    return Event.query.get(ticket_type.eventId)