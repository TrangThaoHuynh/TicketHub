from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, case

from .. import db
from ..models.booking import Booking
from ..models.event import Event
from ..models.payment import Payment
from ..models.ticket import Ticket
from ..models.ticket_type import TicketType
from ..models.user import User


def _normalize_status_upper(value: Any) -> str:
    return str(value or "").strip().upper()


def _compute_order_status(booking_status: Any, payment_status: Any) -> str:
    """Chuẩn hoá trạng thái đơn theo enum trong DB.

    Rule theo yêu cầu:
    - FAILED nếu booking và payment đều FAILED
    - SUCCESS nếu booking hoặc payment SUCCESS
    - còn lại PENDING

    - BookingStatus: PENDING | SUCCESS | FAILED
    - PaymentStatus: SUCCESS | FAILED
    """
    booking_norm = _normalize_status_upper(booking_status)
    payment_norm = _normalize_status_upper(payment_status)

    if booking_norm == "SUCCESS" or payment_norm == "SUCCESS":
        return "SUCCESS"
    if booking_norm == "FAILED" and payment_norm == "FAILED":
        return "FAILED"
    return "PENDING"


ORDER_STATUS_LABELS = {
    "PENDING": "Đang chờ thanh toán",
    "SUCCESS": "Đã thanh toán",
    "FAILED": "Thanh toán thất bại",
}


def _format_dt(dt: Any) -> str:
    if isinstance(dt, datetime):
        return dt.strftime("%d/%m/%Y %H:%M")
    if dt is None:
        return ""
    return str(dt)


def _order_code(booking_id: int) -> str:
    return str(booking_id)


def get_organizer_event(organizer_id: int, event_id: int) -> Event | None:
    return Event.query.filter_by(id=event_id, organizerId=organizer_id).first()


def list_orders_for_organizer(
    organizer_id: int,
    event_id: int | None = None,
) -> list[dict[str, Any]]:
    total_amount_expr = func.coalesce(Booking.totalAmount, func.sum(Ticket.price))

    query = (
        db.session.query(
            Booking.id.label("id"),
            Booking.createdAt.label("created_at"),
            total_amount_expr.label("total_amount"),
            Booking.status.label("booking_status"),
            User.name.label("customer_name"),
            User.phoneNumber.label("customer_phone"),
            User.email.label("customer_email"),
            func.count(Ticket.id).label("ticket_count"),
            func.max(Payment.status).label("payment_status"),
            func.max(
                case(
                    (func.upper(func.coalesce(Ticket.status, "")) == "CANCELLED", 1),
                    else_=0,
                )
            ).label("has_cancelled_ticket"),
        )
        .join(User, User.id == Booking.customerId)
        .join(Ticket, Ticket.bookingId == Booking.id)
        .join(TicketType, TicketType.id == Ticket.ticketTypeId)
        .join(Event, Event.id == TicketType.eventId)
        .outerjoin(Payment, Payment.bookingId == Booking.id)
        .filter(Event.organizerId == organizer_id)
    )

    if event_id is not None:
        query = query.filter(Event.id == event_id)

    rows = (
        query.group_by(
            Booking.id,
            Booking.createdAt,
            Booking.totalAmount,
            Booking.status,
            User.name,
            User.phoneNumber,
            User.email,
        )
        .order_by(Booking.createdAt.desc(), Booking.id.desc())
        .all()
    )

    orders: list[dict[str, Any]] = []
    for row in rows:
        order_status = _compute_order_status(row.booking_status, row.payment_status)
        has_cancelled_ticket = bool(getattr(row, "has_cancelled_ticket", 0) or 0)
        orders.append(
            {
                "id": row.id,
                "code": _order_code(int(row.id)),
                "customer_name": row.customer_name,
                "customer_phone": row.customer_phone,
                "customer_email": row.customer_email,
                "ticket_count": int(row.ticket_count or 0),
                "total_amount": float(row.total_amount) if row.total_amount is not None else None,
                "booking_status": _normalize_status_upper(row.booking_status),
                "payment_status": _normalize_status_upper(row.payment_status),
                "order_status": order_status,
                "order_status_label": ORDER_STATUS_LABELS.get(order_status, order_status),
                "has_cancelled_ticket": bool(order_status == "SUCCESS" and has_cancelled_ticket),
            }
        )

    return orders


def get_order_detail_for_organizer(
    organizer_id: int,
    booking_id: int,
    event_id: int | None = None,
) -> dict[str, Any] | None:
    booking = db.session.get(Booking, booking_id)
    if booking is None:
        return None

    # Ensure this booking belongs to an event of this organizer.
    event_query = (
        db.session.query(Event)
        .join(TicketType, TicketType.eventId == Event.id)
        .join(Ticket, Ticket.ticketTypeId == TicketType.id)
        .filter(Ticket.bookingId == booking_id)
        .filter(Event.organizerId == organizer_id)
    )
    if event_id is not None:
        event_query = event_query.filter(Event.id == event_id)

    event = event_query.first()
    if event is None:
        return None

    # Booker info (customer who created booking)
    booker_user = db.session.get(User, booking.customerId) if booking.customerId else None
    booker = {
        "name": getattr(booker_user, "name", None),
        "phone": getattr(booker_user, "phoneNumber", None),
        "email": getattr(booker_user, "email", None),
    }

    # Payment info
    payment = (
        Payment.query.filter_by(bookingId=booking_id)
        .order_by(Payment.id.desc())
        .first()
    )
    order_status = _compute_order_status(getattr(booking, "status", None), getattr(payment, "status", None))

    # Tickets for this booking + event
    ticket_rows = (
        db.session.query(
            Ticket,
            TicketType.name.label("ticket_type_name"),
            TicketType.eventId.label("event_id"),
        )
        .join(TicketType, TicketType.id == Ticket.ticketTypeId)
        .filter(Ticket.bookingId == booking_id)
        .filter(TicketType.eventId == event.id)
        .order_by(Ticket.createdAt.asc(), Ticket.id.asc())
        .all()
    )

    tickets: list[dict[str, Any]] = []
    total_amount = Decimal("0")
    has_cancelled_ticket = False
    for ticket, ticket_type_name, _ in ticket_rows:
        if _normalize_status_upper(getattr(ticket, "status", None)) == "CANCELLED":
            has_cancelled_ticket = True
        price = getattr(ticket, "price", None)
        if price is not None:
            total_amount += Decimal(str(price))

        tickets.append(
            {
                "id": ticket.id,
                "code": ticket.ticketCode or ticket.id,
                "holder_name": ticket.fullName,
                "holder_phone": ticket.phoneNumber,
                "ticket_type_name": ticket_type_name,
                "price": float(price) if price is not None else None,
            }
        )

    booking_total = getattr(booking, "totalAmount", None)
    if booking_total is not None:
        total_amount = Decimal(str(booking_total))

    order = {
        "id": booking.id,
        "code": _order_code(int(booking.id)),
        "created_at": _format_dt(getattr(booking, "createdAt", None)),
        "payment_method": "VNPAY" if payment is not None else "—",
        "booking_status": _normalize_status_upper(getattr(booking, "status", None)),
        "payment_status": _normalize_status_upper(getattr(payment, "status", None)),
        "order_status": order_status,
        "order_status_label": ORDER_STATUS_LABELS.get(order_status, order_status),
        "has_cancelled_ticket": bool(order_status == "SUCCESS" and has_cancelled_ticket),
        "ticket_count": len(tickets),
        "total_amount": float(total_amount),
    }

    event_payload = {
        "id": event.id,
        "title": event.title,
        "location": event.location,
        "startTime": event.startTime,
        "endTime": event.endTime,
        "time_text": None,
    }

    if event.startTime and event.endTime:
        event_payload["time_text"] = (
            f"{event.startTime.strftime('%H:%M')} - {event.endTime.strftime('%d/%m/%Y')}"
        )
    elif event.startTime:
        event_payload["time_text"] = event.startTime.strftime("%H:%M - %d/%m/%Y")

    return {
        "order": order,
        "event": event_payload,
        "tickets": tickets,
        "booker": booker,
    }
