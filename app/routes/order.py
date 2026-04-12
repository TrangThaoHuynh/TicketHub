from flask import Blueprint, render_template, abort, send_file, request
from flask_login import login_required, current_user
from datetime import datetime, timezone
from io import BytesIO
import qrcode
import uuid

from .. import db
from ..models.ticket import Ticket
from ..models.ticket_type import TicketType
from ..models.event import Event
from ..models.enums import TicketStatus
from ..utils.qr_utils import sign_payload
from ..services.ticket_service import count_sold_by_ticket_type

orders_bp = Blueprint('orders', __name__, url_prefix='/orders')

def _gen_ticket_code():
    """Tạo mã vé duy nhất"""
    return f"TKT-{uuid.uuid4().hex[:12].upper()}"

def _ensure_ticket_qr(ticket: Ticket):
    """Phát hành token QR nếu vé chưa có"""
    if ticket.qrCode:
        return
    
    iat = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    payload = {
        "ver": 1,
        "code": ticket.ticketCode,
        "event_id": ticket.id,
        "iat": iat,
    }
    ticket.qrCode = sign_payload(payload)
    db.session.commit()

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

    _ensure_ticket_qr(t)
    return render_template("ticket_detail.html", t=t)
@orders_bp.route("/ticket/<ticket_id>/qr.png")
@login_required
def ticket_qr_image(ticket_id):
    t = Ticket.query.filter(Ticket.id == ticket_id).first()
    if not t:
        abort(404)

    if t.customerId != current_user.id:
        abort(403)

    _ensure_ticket_qr(t)

    img = qrcode.make(t.qrCode)
    buf = BytesIO()
    img.save(buf, format="PNG")
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