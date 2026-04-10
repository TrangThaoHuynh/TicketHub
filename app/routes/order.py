
from flask import Blueprint, render_template, abort
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from datetime import datetime, timezone

from .. import db
from ..models.ticket import Ticket
from ..models.ticket_type import TicketType
from ..models.enums import TicketStatus
from ..services.ticket_service import count_sold_by_ticket_type

# TODO: Import these when created
# from ..models.order import Order, OrderDetail
# from ..services.order_service import _gen_ticket_code, sign_payload

orders_bp = Blueprint('orders', __name__, url_prefix='/orders')

@orders_bp.route("/ticket/<int:ticket_id>")
@login_required
def ticket_detail(ticket_id):
    # nạp đầy đủ quan hệ để render template
    t = (
        Ticket.query.options(
            joinedload(Ticket.event),
            joinedload(Ticket.ticket_type),
            joinedload(Ticket.order).joinedload("customer"),
        )
        .filter(Ticket.id == ticket_id)
        .first()
    )
    if not t:
        abort(404)

    #kiểm tra chủ sở hữu qua Order.customer_id
    if not t.order or t.order.customer_id != current_user.id:
        abort(403)

    _ensure_ticket_qr(t)
    return render_template("ticket_detail.html", t=t)
# @orders_bp.route("/ticket/<int:ticket_id>/qr.png")
# @login_required
# def ticket_qr_image(ticket_id):
#     t = (
#         Ticket.query.options(joinedload(Ticket.order))
#         .filter(Ticket.id == ticket_id)
#         .first()
#     )
#     if not t:
#         abort(404)
#     if not t.order or t.order.customer_id != current_user.id:
#         abort(403)

#     _ensure_ticket_qr(t)

#     # render QR PNG từ token
#     img = qrcode.make(t.qr_data)
#     buf = BytesIO()
#     img.save(buf, format="PNG")
#     buf.seek(0)
#     return send_file(buf, mimetype="image/png")