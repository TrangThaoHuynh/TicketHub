from flask import Blueprint, render_template, abort, send_file, request, jsonify
from ..models.booking import Booking
from ..services.ticket_email_service import send_ticket_email_by_booking
from flask_login import login_required, current_user
from io import BytesIO
import uuid

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
    t = Ticket.query.filter(Ticket.id == ticket_id).first()
    if not t:
        abort(404)

    if t.customerId != current_user.id:
        abort(403)

    t.ticket_type = TicketType.query.get(t.ticketTypeId)
    t.event = Event.query.get(t.ticket_type.eventId) if t.ticket_type else None

    ensure_ticket_qr_token(t)
    return render_template("ticket_detail.html", t=t)

@orders_bp.route("/ticket/<ticket_id>/qr.png")
@login_required
def ticket_qr_image(ticket_id):
    t = Ticket.query.filter(Ticket.id == ticket_id).first()
    if not t:
        abort(404)

    if t.customerId != current_user.id:
        abort(403)

    png_bytes = build_ticket_qr_png(t)
    buf = BytesIO(png_bytes)
    buf.seek(0)
    return send_file(buf, mimetype="image/png")

@orders_bp.route("/tickets")
@login_required
def my_tickets():
    """Danh sách vé của người dùng"""
    page = request.args.get('page', 1, type=int)
    tickets = Ticket.query.filter(
        Ticket.customerId == current_user.id
    ).order_by(Ticket.createdAt.desc()).paginate(page=page, per_page=12)
    
    return render_template("my_tickets.html", tickets=tickets)

@orders_bp.route("/booking/<int:booking_id>/send-email")
@login_required
def send_booking_email(booking_id):
    booking = Booking.query.get(booking_id)
    if not booking:
        abort(404)

    if booking.customerId != current_user.id:
        abort(403)

    try:
        send_ticket_email_by_booking(booking_id)
        return jsonify({
            "success": True,
            "message": f"Đã gửi email vé cho booking #{booking_id}"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 400