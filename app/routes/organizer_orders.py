from flask import Blueprint, abort, redirect, render_template, request, session, url_for
from sqlalchemy.exc import ProgrammingError

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
        # Common in dev environments when the database schema hasn't been applied.
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

    # Ensure organizer owns this event.
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