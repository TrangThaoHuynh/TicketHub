from flask import render_template
from flask_mail import Message

from .. import mail
from ..models.booking import Booking
from ..models.ticket import Ticket
from ..models.ticket_type import TicketType
from ..models.event import Event
from ..models.user import User
from .ticket_service import build_ticket_qr_png


def _format_money(amount):
    try:
        return f"{int(amount):,}".replace(",", ".")
    except Exception:
        return str(amount)


def send_ticket_email_by_booking(booking_id: int):
    booking = Booking.query.get(booking_id)
    if not booking:
        raise ValueError("Không tìm thấy booking")

    if booking.status != "SUCCESS":
        raise ValueError("Chỉ gửi email cho booking đã thanh toán thành công")

    customer = User.query.get(booking.customerId)
    if not customer:
        raise ValueError("Không tìm thấy khách hàng")

    if not customer.email:
        raise ValueError("Khách hàng chưa có email")

    tickets = Ticket.query.filter_by(
        bookingId=booking.id,
        customerId=booking.customerId
    ).all()

    if not tickets:
        raise ValueError("Booking chưa có vé")

    payment = booking.payments[0] if booking.payments else None

    msg = Message(
        subject=f"[TicketHub] Vé điện tử cho đơn hàng #{booking.id}",
        recipients=[customer.email]
    )

    ticket_items = []

    for idx, ticket in enumerate(tickets):
        ticket_type = TicketType.query.get(ticket.ticketTypeId)
        event = Event.query.get(ticket_type.eventId) if ticket_type else None

        if not ticket_type or not event:
            continue

        qr_png = build_ticket_qr_png(ticket)
        cid = f"ticket_qr_{idx}"

        msg.attach(
        filename=f"{ticket.ticketCode or ticket.id}.png",
        content_type="image/png",
        data=qr_png,
        disposition="inline",
        headers={"Content-ID": f"<{cid}>"}
)

        ticket_items.append({
            "ticket_code": ticket.ticketCode or ticket.id,
            "full_name": ticket.fullName,
            "phone_number": ticket.phoneNumber,
            "ticket_price": _format_money(ticket.price),
            "ticket_type_name": ticket_type.name,
            "event_title": event.title,
            "event_location": event.location,
            "event_start": event.startTime.strftime("%H:%M %d/%m/%Y") if event.startTime else "",
            "event_end": event.endTime.strftime("%H:%M %d/%m/%Y") if event.endTime else "",
            "has_face_reg": bool(event.hasFaceReg),
            "qr_cid": cid,
        })

    if not ticket_items:
        raise ValueError("Không có dữ liệu vé hợp lệ để gửi mail")

    msg.html = render_template(
        "ticket_email.html",
        customer_name=customer.name or "Khách hàng",
        booking_id=booking.id,
        booking_created_at=booking.createdAt.strftime("%H:%M %d/%m/%Y") if booking.createdAt else "",
        total_amount=_format_money(booking.totalAmount),
        transaction_id=payment.transactionID if payment else "",
        tickets=ticket_items
    )

    mail.send(msg)
    return True