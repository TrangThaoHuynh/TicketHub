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
import json
import math
from flask import current_app
from ..services.face_service import (
    extract_face_embedding_from_base64,
    load_embedding_vector,
    cosine_distance,
    confidence_from_distance,
)

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
    Đảm bảo Ticket.qrCode luôn là token QR hợp lệ.
    Nếu qrCode rỗng hoặc là dữ liệu cũ không hợp lệ thì sinh token mới.
    """
    if ticket.qrCode:
        is_valid, payload, _ = verify_token(ticket.qrCode)

        # Nếu qrCode hiện tại đã là token hợp lệ và đúng ticket hiện tại thì giữ nguyên
        if is_valid and payload:
            payload_ticket_id = str(payload.get("ticket_id", "")).strip()
            if payload_ticket_id == str(ticket.id):
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

    if status_norm == "VALID":
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

def _set_face_validation_payload(payload: dict, distance: float):
    """
    Cập nhật dữ liệu validation vào payload với thông tin xác nhận khuôn mặt.
    """
    # Lấy hoặc tạo mới dictionary "validation" trong payload
    validation = payload.setdefault("validation", {})
    
    # Cập nhật phương pháp xác nhận = khuôn mặt
    validation["method"] = "face"
    validation["result"] = "Khuôn mặt khớp"
    validation["distance"] = round(float(distance), 4)
    validation["confidence"] = confidence_from_distance(distance)
    
    return payload


def inspect_face_for_organizer(organizer_id: int, event_id: int, face_image_base64: str):
    """
    Kiểm tra khuôn mặt từ ảnh quét và tìm vé khớp trong sự kiện.
    """
    # Kiểm tra event có thuộc organizer này không
    organizer_event = Event.query.filter_by(id=event_id, organizerId=organizer_id).first()
    if organizer_event is None:
        return {
            "ok": False,
            "error": "event_not_found",
            "message": "Sự kiện không tồn tại hoặc bạn không có quyền quét vé cho sự kiện này.",
        }

    # Kiểm tra sự kiện này có bật check-in bằng khuôn mặt không
    if not organizer_event.hasFaceReg:
        return {
            "ok": False,
            "error": "invalid_checkin_mode",
            "message": "Sự kiện này không dùng check-in bằng khuôn mặt.",
        }

    # Bước 1: Trích xuất đặc trưng khuôn mặt từ ảnh base64
    try:
        query_embedding_json = extract_face_embedding_from_base64(face_image_base64)
    except ValueError as exc:
        return {
            "ok": False,
            "error": "invalid_face_image",
            "message": str(exc),  # Ví dụ: "Không phát hiện được khuôn mặt trong ảnh"
        }

    # Chuyển JSON vector thành numpy array để tính toán
    query_vector = load_embedding_vector(query_embedding_json)
    if query_vector is None:
        return {
            "ok": False,
            "error": "invalid_face_embedding",
            "message": "Không đọc được đặc trưng khuôn mặt từ ảnh vừa quét.",
        }

    # Bước 2: Lấy danh sách tất cả vé của sự kiện có lưu dữ liệu khuôn mặt
    candidate_tickets = (
        db.session.query(Ticket)
        .join(TicketType, TicketType.id == Ticket.ticketTypeId)
        .filter(TicketType.eventId == event_id)
        .filter(Ticket.faceEmbedding.isnot(None))  # Chỉ lấy vé có ảnh khuôn mặt
        .all()
    )

    if not candidate_tickets:
        return {
            "ok": False,
            "error": "no_face_data",
            "message": "Sự kiện này chưa có dữ liệu khuôn mặt để đối chiếu.",
        }

    # Bước 3: So sánh khuôn mặt quét với tất cả vé, tìm vé khớp nhất
    best_ticket = None
    best_distance = 999.0  # Khởi tạo với giá trị cao

    for ticket in candidate_tickets:
        # Chuyển dữ liệu khuôn mặt lưu trong DB thành vector
        stored_vector = load_embedding_vector(ticket.faceEmbedding)
        if stored_vector is None:
            continue

        # Tính khoảng cách cosine (0 = giống hệt, 1 = hoàn toàn khác)
        distance = cosine_distance(query_vector, stored_vector)
        
        # Cập nhật vé khớp nhất nếu khoảng cách nhỏ hơn
        if distance < best_distance:
            best_distance = distance
            best_ticket = ticket

    # Kiểm tra xem có tìm được vé nào không
    if best_ticket is None:
        return {
            "ok": False,
            "error": "no_face_match",
            "message": "Không tìm thấy vé có dữ liệu khuôn mặt hợp lệ.",
        }

    # Bước 4: Kiểm tra xem khoảng cách có nhỏ hơn ngưỡng (threshold) không
    # Ngưỡng mặc định: 0.35 (config qua FACE_MATCH_THRESHOLD)
    # Nếu distance <= 0.35 → khuôn mặt khớp
    # Nếu distance > 0.35 → khuôn mặt không khớp
    threshold = float(current_app.config.get("FACE_MATCH_THRESHOLD", 0.35))
    if best_distance > threshold:
        return {
            "ok": False,
            "error": "face_not_match",
            "message": "Không tìm thấy khuôn mặt khớp với vé trong sự kiện này.",
            "match": {
                "distance": round(best_distance, 4),
                "confidence": confidence_from_distance(best_distance),  # Độ tin cậy (%)
            },
        }

    # Bước 5: Nếu khuôn mặt khớp, kiểm tra xem vé có hợp lệ để check-in không
    inspect_result = _inspect_ticket_for_checkin(organizer_id, event_id, best_ticket)

    # Bước 6: Nếu vé hợp lệ, thêm thông tin validation khuôn mặt vào kết quả
    if "ticket" in inspect_result:
        _set_face_validation_payload(inspect_result, best_distance)
        inspect_result["match"] = {
            "distance": round(best_distance, 4),
            "confidence": confidence_from_distance(best_distance),
        }

    return inspect_result


def confirm_face_checkin_for_organizer(organizer_id: int, event_id: int, ticket_id: str):
    """
    Xác nhận check-in vé sau khi đã xác thực khuôn mặt thành công.Đánh dấu vé là "USED" (đã sử dụng).
    """
    # Kiểm tra event có thuộc organizer này không
    organizer_event = Event.query.filter_by(id=event_id, organizerId=organizer_id).first()
    if organizer_event is None:
        return {
            "ok": False,
            "error": "event_not_found",
            "message": "Sự kiện không tồn tại hoặc bạn không có quyền check-in.",
        }

    # Kiểm tra sự kiện có bật check-in bằng khuôn mặt không
    if not organizer_event.hasFaceReg:
        return {
            "ok": False,
            "error": "invalid_checkin_mode",
            "message": "Sự kiện này không dùng check-in bằng khuôn mặt.",
        }

    # Gọi hàm chung để confirm check-in
    return confirm_ticket_checkin_for_organizer(
        organizer_id=organizer_id,
        event_id=event_id,
        ticket_id=ticket_id,
    )