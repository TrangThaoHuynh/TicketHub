from datetime import datetime, timezone
from io import BytesIO
import uuid
import qrcode

from sqlalchemy import func, or_

from .. import db
from ..models.ticket import Ticket
from ..models.ticket_type import TicketType
from ..models.event import Event
from ..models.booking import Booking
from ..models.payment import Payment
from ..utils.qr_utils import sign_payload, verify_token


# Lấy danh sách loại vé của 1 sự kiện
def get_ticket_types_by_event_id(event_id: int):
    return TicketType.query.filter_by(eventId=event_id).all()


# Đếm số lượng vé đã bán / đã dùng theo ticket type
def count_sold_by_ticket_type(ticket_type_ids: list[int]) -> dict[int, int]:
    if not ticket_type_ids:
        return {}

    rows = (
        db.session.query(Ticket.ticketTypeId, func.count(Ticket.id))
        .filter(
            Ticket.ticketTypeId.in_(ticket_type_ids),
            Ticket.status.in_(["VALID", "USED"])
        )
        .group_by(Ticket.ticketTypeId)
        .all()
    )
    return {ticket_type_id: count for ticket_type_id, count in rows}


# Lấy danh sách vé của người dùng
def get_tickets_of_user(user_id: int, q: str = "", status: str = None, page: int = 1, per_page: int = 12):
    query = (
        db.session.query(Ticket)
        .filter(Ticket.customerId == user_id)
        .order_by(Ticket.createdAt.desc())
    )

    if q:
        like_q = f"%{q.strip()}%"
        matching_ticket_type_ids = db.session.query(TicketType.id).filter(
            TicketType.name.ilike(like_q)
        )
        matching_event_ids = db.session.query(Event.id).filter(
            Event.title.ilike(like_q)
        )
        matching_ticket_type_ids_by_event = db.session.query(TicketType.id).filter(
            TicketType.eventId.in_(matching_event_ids)
        )

        query = query.filter(
            or_(
                Ticket.ticketCode.ilike(like_q),
                Ticket.fullName.ilike(like_q),
                Ticket.ticketTypeId.in_(matching_ticket_type_ids),
                Ticket.ticketTypeId.in_(matching_ticket_type_ids_by_event)
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
        "ticket_code": ticket.ticketCode,
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

PAID_BOOKING_STATUSES = {"SUCCESS"}
PAID_PAYMENT_STATUSES = {"SUCCESS"}

def _normalize_status(value):
    return str(value or "").strip().upper()

def _is_paid_booking(booking: Booking | None, payment: Payment | None) -> bool:
    booking_status = _normalize_status(getattr(booking, "status", None))
    payment_status = _normalize_status(getattr(payment, "status", None))
    return booking_status in PAID_BOOKING_STATUSES or payment_status in PAID_PAYMENT_STATUSES

def _format_dt(dt: datetime | None) -> str:
    if not dt:
        return ""
    return dt.strftime("%H:%M %d/%m/%Y")


def _ticket_status_label(status: str | None) -> str:
    status_norm = _normalize_status(status)

    if status_norm in {"VALID", "ACTIVE"}:
        return "chưa sử dụng"
    if status_norm == "USED":
        return "đã sử dụng"
    if status_norm == "CANCELLED":
        return "đã hủy"
    if status_norm == "PENDING":
        return "chờ xử lý"
    return "không xác định"


def _build_scan_payload(ticket: Ticket):
    ticket_type = TicketType.query.get(ticket.ticketTypeId) if ticket.ticketTypeId else None
    event = Event.query.get(ticket_type.eventId) if ticket_type else None
    booking = Booking.query.get(ticket.bookingId) if ticket.bookingId else None
    payment = (
        Payment.query.filter_by(bookingId=ticket.bookingId).order_by(Payment.id.desc()).first()
        if ticket.bookingId else None
    )

    event_time_text = ""
    if event and event.startTime:
        event_time_text = event.startTime.strftime("%H:%M | %d/%m/%Y")

    return {
        "ticket": {
            "id": ticket.id,
            "ticket_code": ticket.ticketCode or ticket.id,
            "full_name": ticket.fullName or "",
            "phone_number": ticket.phoneNumber or "",
            "status": ticket.status or "",
            "status_label": _ticket_status_label(ticket.status),
            "checked_in_at": _format_dt(ticket.checkedIn),
        },
        "ticket_type": {
            "id": ticket_type.id if ticket_type else None,
            "name": ticket_type.name if ticket_type else "",
        },
        "event": {
            "id": event.id if event else None,
            "title": event.title if event else "",
            "location": event.location if event else "",
            "time_text": event_time_text,
        },
        "booking": {
            "id": booking.id if booking else None,
            "status": getattr(booking, "status", None),
        },
        "payment": {
            "status": getattr(payment, "status", None),
        },
        "validation": {
            "method": "QR code",
            "result": "QR hợp lệ",
        },
    }


def _inspect_ticket_for_checkin(organizer_id: int, event_id: int, ticket: Ticket | None):
    # Kiểm tra event có thuộc organizer không
    organizer_event = Event.query.filter_by(id=event_id, organizerId=organizer_id).first()
    if organizer_event is None:
        return {
            "ok": False,
            "error": "event_not_found",
            "message": "Sự kiện không tồn tại hoặc bạn không có quyền quét vé cho sự kiện này.",
        }

    if ticket is None:
        return {
            "ok": False,
            "error": "ticket_not_found",
            "message": "Không tìm thấy vé.",
        }

    ticket_type = TicketType.query.get(ticket.ticketTypeId) if ticket.ticketTypeId else None
    if ticket_type is None:
        return {
            "ok": False,
            "error": "ticket_type_not_found",
            "message": "Vé không có loại vé hợp lệ.",
        }

    real_event = Event.query.get(ticket_type.eventId)
    if real_event is None or real_event.id != event_id or real_event.organizerId != organizer_id:
        return {
            "ok": False,
            "error": "event_mismatch",
            "message": "Vé này không thuộc sự kiện đang quét.",
        }

    booking = Booking.query.get(ticket.bookingId) if ticket.bookingId else None
    payment = (
        Payment.query.filter_by(bookingId=ticket.bookingId).order_by(Payment.id.desc()).first()
        if ticket.bookingId else None
    )

    status_norm = _normalize_status(ticket.status)
    paid = _is_paid_booking(booking, payment)

    payload = _build_scan_payload(ticket)

    if status_norm == "USED":
        return {
            "ok": False,
            "error": "already_checked_in",
            "message": "Vé này đã được check-in trước đó.",
            **payload,
        }

    if status_norm == "CANCELLED":
        return {
            "ok": False,
            "error": "ticket_cancelled",
            "message": "Vé đã bị hủy nên không thể check-in.",
            **payload,
        }

    if status_norm == "PENDING" and not paid:
        return {
            "ok": False,
            "error": "ticket_unpaid",
            "message": "Vé chưa thanh toán thành công nên không thể check-in.",
            **payload,
        }

    return {
        "ok": True,
        "message": "Vé hợp lệ. Có thể xác nhận check-in.",
        "can_checkin": True,
        **payload,
    }


def inspect_qr_for_organizer(organizer_id: int, event_id: int, qr_token: str):
    qr_token = (qr_token or "").strip()
    if not qr_token:
        return {
            "ok": False,
            "error": "empty_qr",
            "message": "QR code trống.",
        }

    is_valid, payload, message = verify_token(qr_token)
    if not is_valid:
        return {
            "ok": False,
            "error": "invalid_qr",
            "message": f"QR không hợp lệ: {message}",
        }

    ticket_id = payload.get("ticket_id")
    payload_event_id = payload.get("event_id")

    if not ticket_id:
        return {
            "ok": False,
            "error": "invalid_payload",
            "message": "QR không chứa ticket_id hợp lệ.",
        }

    try:
        if payload_event_id is not None and int(payload_event_id) != int(event_id):
            return {
                "ok": False,
                "error": "event_mismatch",
                "message": "QR này không thuộc sự kiện đang quét.",
            }
    except (TypeError, ValueError):
        return {
            "ok": False,
            "error": "invalid_payload",
            "message": "QR chứa event_id không hợp lệ.",
        }

    ticket = Ticket.query.get(ticket_id)
    if ticket and ticket.qrCode and ticket.qrCode != qr_token:
        return {
            "ok": False,
            "error": "invalid_qr",
            "message": "QR không khớp với dữ liệu vé hiện tại.",
        }

    return _inspect_ticket_for_checkin(organizer_id, event_id, ticket)


def inspect_ticket_code_for_organizer(organizer_id: int, event_id: int, ticket_code: str):
    ticket_code = (ticket_code or "").strip()
    if not ticket_code:
        return {
            "ok": False,
            "error": "empty_ticket_code",
            "message": "Bạn chưa nhập mã vé.",
        }

    ticket = Ticket.query.filter_by(ticketCode=ticket_code).first()
    return _inspect_ticket_for_checkin(organizer_id, event_id, ticket)


def confirm_ticket_checkin_for_organizer(organizer_id: int, event_id: int, ticket_id: str):
    ticket_id = (ticket_id or "").strip()
    if not ticket_id:
        return {
            "ok": False,
            "error": "empty_ticket_id",
            "message": "Thiếu ticket_id để xác nhận check-in.",
        }

    ticket = Ticket.query.get(ticket_id)
    inspect_result = _inspect_ticket_for_checkin(organizer_id, event_id, ticket)

    if not inspect_result.get("ok"):
        return inspect_result

    mark_checked_in(ticket)
    payload = _build_scan_payload(ticket)

    return {
        "ok": True,
        "message": "Check-in thành công.",
        **payload,
    }