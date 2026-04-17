from flask import Blueprint, render_template, abort, send_file, request, jsonify, url_for
from ..models.booking import Booking
from ..services.ticket_email_service import send_ticket_email_by_booking
from flask_login import login_required, current_user
from io import BytesIO
import uuid
from sqlalchemy import func
from sqlalchemy.orm import aliased
from sqlalchemy.exc import ProgrammingError

from .. import db
from ..models.booking import Booking
from ..models.payment import Payment
from ..models.ticket import Ticket
from ..models.ticket_type import TicketType
from ..models.event import Event
from ..services.ticket_service import (
    count_sold_by_ticket_type,
    ensure_ticket_qr_token,
    build_ticket_qr_png,
)
orders_bp = Blueprint('orders', __name__, url_prefix='/orders')

def _gen_ticket_code():
    """Tạo mã vé duy nhất"""
    return f"TKT-{uuid.uuid4().hex[:12].upper()}"

@orders_bp.route("/ticket/<ticket_id>")
@login_required
def ticket_detail(ticket_id):
    """Chi tiết một vé."""
    t = Ticket.query.filter(Ticket.id == ticket_id).first()
    if not t:
        abort(404)

    if t.customerId != current_user.id:
        abort(403)

    t.ticket_type = TicketType.query.get(t.ticketTypeId)
    t.event = Event.query.get(t.ticket_type.eventId) if t.ticket_type else None

    booking = db.session.get(Booking, t.bookingId) if t.bookingId else None
    payment = (
        Payment.query.filter_by(bookingId=t.bookingId)
        .order_by(Payment.id.desc())
        .first()
    ) if t.bookingId else None

    booking_status = str(getattr(booking, "status", "") or "").upper()
    payment_status = str(getattr(payment, "status", "") or "").upper()
    show_qr = (
        (booking_status == "SUCCESS" or payment_status == "SUCCESS")
        and booking_status != "FAILED"
        and payment_status != "FAILED"
    )

    if show_qr:
        ensure_ticket_qr_token(t)

    return render_template("ticket_detail.html", t=t, show_qr=show_qr)

@orders_bp.route("/ticket/<ticket_id>/qr.png")
@login_required
def ticket_qr_image(ticket_id):
    """Xuất ảnh QR PNG của vé."""
    t = Ticket.query.filter(Ticket.id == ticket_id).first()
    if not t:
        abort(404)

    if t.customerId != current_user.id:
        abort(403)

    booking = db.session.get(Booking, t.bookingId) if t.bookingId else None
    payment = (
        Payment.query.filter_by(bookingId=t.bookingId)
        .order_by(Payment.id.desc())
        .first()
    ) if t.bookingId else None

    booking_status = str(getattr(booking, "status", "") or "").upper()
    payment_status = str(getattr(payment, "status", "") or "").upper()
    show_qr = (
        (booking_status == "SUCCESS" or payment_status == "SUCCESS")
        and booking_status != "FAILED"
        and payment_status != "FAILED"
    )

    if not show_qr:
        abort(403)

    png_bytes = build_ticket_qr_png(t)
    buf = BytesIO(png_bytes)
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


@orders_bp.route("/tickets")
@login_required
def my_tickets():
    """Danh sách vé đã mua, group theo booking + event."""
    page = request.args.get('page', 1, type=int)

    try:
        total_amount_expr = func.coalesce(Booking.totalAmount, func.sum(Ticket.price))

        # Lấy trạng thái thanh toán của lần thanh toán mới nhất (theo Payment.id lớn nhất)
        latest_payment_id_subq = (
            db.session.query(
                Payment.bookingId.label("booking_id"),
                func.max(Payment.id).label("max_payment_id"),
            )
            .group_by(Payment.bookingId)
            .subquery()
        )
        LatestPayment = aliased(Payment)

        query = (
            db.session.query(
                Booking.id.label('booking_id'),
                Booking.createdAt.label('created_at'),
                Booking.status.label('booking_status'),
                Event.id.label('event_id'),
                Event.title.label('event_title'),
                Event.image.label('event_image'),
                func.count(Ticket.id).label('quantity'),
                total_amount_expr.label('total_amount'),
                LatestPayment.status.label('payment_status'),
            )
            .join(Ticket, Ticket.bookingId == Booking.id)
            .join(TicketType, TicketType.id == Ticket.ticketTypeId)
            .join(Event, Event.id == TicketType.eventId)
            .outerjoin(latest_payment_id_subq, latest_payment_id_subq.c.booking_id == Booking.id)
            .outerjoin(LatestPayment, LatestPayment.id == latest_payment_id_subq.c.max_payment_id)
            .filter(Booking.customerId == current_user.id)
            .group_by(
                Booking.id,
                Booking.createdAt,
                Booking.totalAmount,
                Booking.status,
                Event.id,
                Event.title,
                Event.image,
                LatestPayment.status,
            )
            .order_by(Booking.createdAt.desc(), Booking.id.desc())
        )

        bookings = query.paginate(page=page, per_page=8, error_out=False)

        orders = []
        for row in bookings.items:
            booking_status = str(row.booking_status or '').upper()
            payment_status = str(row.payment_status or '').upper()

            is_failed = booking_status == 'FAILED' or payment_status == 'FAILED'
            is_paid = (booking_status == 'SUCCESS' or payment_status == 'SUCCESS') and not is_failed

            orders.append(
                {
                    'booking_id': int(row.booking_id),
                    'event_id': int(row.event_id),
                    'event_title': row.event_title,
                    'event_image': row.event_image,
                    'created_at': row.created_at.strftime('%d-%m-%Y') if row.created_at else '',
                    'quantity': int(row.quantity or 0),
                    'total_amount': float(row.total_amount) if row.total_amount is not None else 0,
                    'status': 'failed' if is_failed else 'paid' if is_paid else 'pending',
                }
            )

        return render_template(
            'my_tickets.html',
            orders=orders,
            bookings=bookings,
            show_search=False,
        )

    except ProgrammingError:
        # Fallback nếu DB local chưa đủ bảng/quan hệ phục vụ query group.
        tickets = (
            Ticket.query
            .filter(Ticket.customerId == current_user.id)
            .order_by(Ticket.createdAt.desc())
            .paginate(page=page, per_page=12, error_out=False)
        )

        return render_template(
            'my_tickets.html',
            tickets=tickets,
            show_search=False,
        )


@orders_bp.route('/booking/<int:booking_id>')
@login_required
def booking_detail(booking_id: int):
    """Chi tiết vé đã mua theo đơn (booking) + sự kiện."""
    try:
        booking = db.session.get(Booking, booking_id)
        if not booking:
            abort(404)

        if booking.customerId != current_user.id:
            abort(403)

        payment = (
            Payment.query
            .filter_by(bookingId=booking_id)
            .order_by(Payment.id.desc())
            .first()
        )

        booking_status = str(getattr(booking, 'status', '') or '').upper()
        payment_status = str(getattr(payment, 'status', '') or '').upper()

        # Nếu lần thanh toán mới nhất FAILED thì xem như chưa thanh toán thành công
        paid = (booking_status == 'SUCCESS' or payment_status == 'SUCCESS') and booking_status != 'FAILED' and payment_status != 'FAILED'

        ticket_rows = (
            db.session.query(Ticket, TicketType, Event)
            .join(TicketType, TicketType.id == Ticket.ticketTypeId)
            .join(Event, Event.id == TicketType.eventId)
            .filter(Ticket.bookingId == booking_id)
            .order_by(TicketType.id.asc(), Ticket.createdAt.asc())
            .all()
        )

        if not ticket_rows:
            abort(404)

        event = ticket_rows[0][2]

        groups = {}
        total = 0.0

        for t, tt, _event in ticket_rows:
            code = t.ticketCode or t.id

            if t.price is not None:
                total += float(t.price)

            groups.setdefault(
                tt.name or f"Vé loại {tt.id}",
                []
            ).append(
                {
                    'ticket_id': t.id,
                    'holder_name': t.fullName,
                    'ticket_code': code,
                    'qr_url': url_for('orders.ticket_qr_image', ticket_id=t.id),
                }
            )

        total_amount = float(booking.totalAmount) if booking.totalAmount is not None else total
        booking_code = str(booking.id)

        return render_template(
            'my_ticket_order_detail.html',
            booking=booking,
            booking_code=booking_code,
            event=event,
            paid=paid,
            payment=payment,
            total_amount=total_amount,
            quantity=len(ticket_rows),
            representative_name=(current_user.name or current_user.username),
            groups=groups,
            show_search=False,
        )

    except ProgrammingError:
        abort(
            500,
            description='Database chưa có bảng cần thiết (Booking/Ticket/...). Hãy chạy script tạo database trước.'
        )