from flask import Blueprint, abort, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy.exc import ProgrammingError

from ..services.ticket_service import (
    confirm_ticket_checkin_for_organizer,
    inspect_ticket_code_for_organizer,
    inspect_qr_for_organizer,
)
from ..services.organizer_order_service import (
    get_order_detail_for_organizer,
    get_organizer_event,
    list_orders_for_organizer,
)

organizer_bp = Blueprint('organizer', __name__)


@organizer_bp.route('/organizer/events/<int:event_id>/orders')
def organizer_event_orders(event_id: int):
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login.login'))

    organizer_id = int(user_id)

    event = get_organizer_event(organizer_id, event_id)
    if event is None:
        abort(404)

    try:
        orders = list_orders_for_organizer(organizer_id, event_id=event_id)
    except ProgrammingError as exc:
        if getattr(getattr(exc, 'orig', None), 'args', None) and '1146' in str(exc.orig.args[0]):
            abort(500, description="Database chưa có bảng cần thiết (Booking/Ticket/...). Hãy chạy script tạo database ticketdb trước.")
        raise

    return render_template(
        'organizer_orders.html',
        orders=orders,
        event=event,
        show_search=False,
    )


@organizer_bp.route('/organizer/events/<int:event_id>/orders/<int:order_id>')
def organizer_event_order_detail(event_id: int, order_id: int):
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login.login'))

    organizer_id = int(user_id)

    event = get_organizer_event(organizer_id, event_id)
    if event is None:
        abort(404)

    try:
        detail = get_order_detail_for_organizer(
            organizer_id,
            booking_id=order_id,
            event_id=event_id,
        )
    except ProgrammingError as exc:
        if getattr(getattr(exc, 'orig', None), 'args', None) and '1146' in str(exc.orig.args[0]):
            abort(500, description="Database chưa có bảng cần thiết (Booking/Ticket/...). Hãy chạy script tạo database ticketdb trước.")
        raise

    if detail is None:
        abort(404)

    return render_template(
        'organizer_order_detail.html',
        order=detail['order'],
        event=detail['event'],
        tickets=detail['tickets'],
        booker=detail['booker'],
        show_search=False,
    )


@organizer_bp.route('/organizer/orders')
def organizer_orders():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login.login'))

    organizer_id = int(user_id)

    event_id = request.args.get('eventId')
    try:
        event_id_int = int(event_id) if event_id not in (None, "") else None
    except ValueError:
        event_id_int = None

    if event_id_int is None:
        abort(404)

    return redirect(url_for('organizer.organizer_event_orders', event_id=event_id_int))


@organizer_bp.route('/organizer/orders/<int:order_id>')
def organizer_order_detail(order_id: int):
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login.login'))

    organizer_id = int(user_id)

    event_id = request.args.get('eventId')
    try:
        event_id_int = int(event_id) if event_id not in (None, "") else None
    except ValueError:
        event_id_int = None

    if event_id_int is None:
        abort(404)

    return redirect(
        url_for(
            'organizer.organizer_event_order_detail',
            event_id=event_id_int,
            order_id=order_id,
        )
    )


# Vé quét tại cổng
@organizer_bp.route('/organizer/events/<int:event_id>/scan')
def organizer_event_scan(event_id: int):
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login.login'))

    organizer_id = int(user_id)
    event = get_organizer_event(organizer_id, event_id)
    if event is None:
        abort(404)

    return render_template(
        'organizer_qr_scan.html',
        event=event,
        show_search=False,
    )


# API KIỂM TRA QR / MÃ VÉ
@organizer_bp.route('/api/qr/validate', methods=['POST'])
def organizer_validate_qr():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({
            "ok": False,
            "error": "unauthorized",
            "message": "Bạn chưa đăng nhập.",
        })

    organizer_id = int(user_id)
    payload = request.get_json(silent=True) or request.form

    raw_event_id = payload.get("event_id")
    qr_token = payload.get("qr", "")
    ticket_code = payload.get("ticket_code", "")

    try:
        event_id = int(raw_event_id)
    except (TypeError, ValueError):
        return jsonify({
            "ok": False,
            "error": "invalid_event_id",
            "message": "event_id không hợp lệ.",
        })

    if str(qr_token).strip():
        result = inspect_qr_for_organizer(
            organizer_id=organizer_id,
            event_id=event_id,
            qr_token=qr_token,
        )
        return jsonify(result)

    result = inspect_ticket_code_for_organizer(
        organizer_id=organizer_id,
        event_id=event_id,
        ticket_code=ticket_code,
    )
    return jsonify(result)


# API XÁC NHẬN CHECK-IN
@organizer_bp.route('/api/qr/check-in', methods=['POST'])
def organizer_confirm_checkin():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({
            "ok": False,
            "error": "unauthorized",
            "message": "Bạn chưa đăng nhập.",
        })

    organizer_id = int(user_id)
    payload = request.get_json(silent=True) or request.form

    raw_event_id = payload.get("event_id")
    ticket_id = payload.get("ticket_id", "")

    try:
        event_id = int(raw_event_id)
    except (TypeError, ValueError):
        return jsonify({
            "ok": False,
            "error": "invalid_event_id",
            "message": "event_id không hợp lệ.",
        })

    result = confirm_ticket_checkin_for_organizer(
        organizer_id=organizer_id,
        event_id=event_id,
        ticket_id=ticket_id,
    )
    return jsonify(result)