import json
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, abort, render_template, request, session, redirect, url_for, flash, current_app, jsonify

from .. import db
from ..models.enums import EventStatus
from ..models.event_type import EventType
from ..models.ticket import Ticket
from ..models.ticket_type import TicketType
from ..models.user import Organizer
from ..services import create_event, create_ticket_type
from ..services.cloudinary_service import cloudinary_service
from ..services.event_service import get_event_by_id, get_event_types
from ..services.ticket_service import get_ticket_types_by_event_id, count_sold_by_ticket_type

event_bp = Blueprint('event', __name__)

ALLOWED_EVENT_STATUSES = {"PENDING", "PUBLISHED"}


def _parse_datetime_local(value):
    text = (value or "").strip()
    if not text:
        return None

    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _parse_positive_int(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None

    return parsed if parsed > 0 else None


def _parse_non_negative_int(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None

    return parsed if parsed >= 0 else None


def _parse_tickets_payload(raw_tickets_json):
    try:
        payload = json.loads(raw_tickets_json or "[]")
    except (TypeError, ValueError):
        return None, "Danh sach loai ve khong hop le."

    if not isinstance(payload, list) or not payload:
        return None, "Vui long tao it nhat mot loai ve."

    normalized_tickets = []
    for index, ticket in enumerate(payload, start=1):
        if not isinstance(ticket, dict):
            return None, f"Loai ve thu {index} khong hop le."

        ticket_id = ticket.get("id")
        normalized_ticket_id = None
        if ticket_id not in (None, ""):
            normalized_ticket_id = _parse_positive_int(ticket_id)
            if normalized_ticket_id is None:
                return None, f"ID loai ve thu {index} khong hop le."

        ticket_name = (ticket.get("name") or "").strip()
        if not ticket_name:
            return None, f"Vui long nhap ten loai ve thu {index}."

        quantity = _parse_positive_int(ticket.get("quantity"))
        if quantity is None:
            return None, f"So luong loai ve thu {index} phai lon hon 0."

        sale_start = _parse_datetime_local(ticket.get("saleStart"))
        sale_end = _parse_datetime_local(ticket.get("saleEnd"))
        if sale_start is None or sale_end is None:
            return None, f"Thoi gian ban ve cua loai ve thu {index} khong hop le."
        if sale_end < sale_start:
            return None, f"Thoi gian ket thuc ban ve cua loai ve thu {index} phai sau thoi gian bat dau."

        try:
            price = Decimal(str(ticket.get("price", 0)))
        except (InvalidOperation, ValueError, TypeError):
            return None, f"Gia loai ve thu {index} khong hop le."

        if price < 0:
            return None, f"Gia loai ve thu {index} khong duoc am."

        is_free = bool(ticket.get("isFree"))
        if is_free:
            price = Decimal("0")

        normalized_tickets.append(
            {
                "id": normalized_ticket_id,
                "name": ticket_name,
                "description": (ticket.get("description") or "").strip(),
                "price": price,
                "quantity": quantity,
                "saleStart": sale_start,
                "saleEnd": sale_end,
            }
        )

    return normalized_tickets, None


def _sanitize_rich_html(value):
    html = (value or "").strip()
    if not html:
        return ""

    html = re.sub(r"(?is)<(script|style|iframe|object|embed)[^>]*>.*?</\1>", "", html)
    html = re.sub(r"(?is)\s+on[a-z]+\s*=\s*(['\"]).*?\1", "", html)
    html = re.sub(r"(?is)\s+on[a-z]+\s*=\s*[^\s>]+", "", html)
    html = re.sub(r"(?is)(href|src)\s*=\s*(['\"])\s*javascript:[^'\"]*\2", r"\1=\2#\2", html)
    return html


def _normalize_event_status(value):
    normalized = (value or "PENDING").strip().upper()
    return normalized if normalized in ALLOWED_EVENT_STATUSES else "PENDING"


def _resolve_event_status_for_db(value):
    normalized_status = _normalize_event_status(value)
    status_candidates = {
        "PUBLISHED": ["PUBLISHED", "APPROVED"],
        "PENDING": ["PENDING"],
    }.get(normalized_status, [normalized_status])

    for candidate in status_candidates:
        status_row = db.session.get(EventStatus, candidate)
        if status_row:
            return status_row.status

    pending_status = db.session.get(EventStatus, "PENDING")
    if pending_status:
        return pending_status.status

    first_status = EventStatus.query.order_by(EventStatus.status.asc()).first()
    return first_status.status if first_status else None


def _resolve_cancelled_status_for_db():
    cancelled_status = db.session.get(EventStatus, "CANCELLED")
    if cancelled_status:
        return cancelled_status.status

    # Fallback for environments that have not seeded CANCELLED yet.
    finished_status = db.session.get(EventStatus, "FINISHED")
    if finished_status:
        return finished_status.status

    first_status = EventStatus.query.order_by(EventStatus.status.asc()).first()
    return first_status.status if first_status else None


def _map_event_status_for_form(status):
    normalized = (status or "").strip().upper()
    return "PUBLISHED" if normalized in {"PUBLISHED", "APPROVED"} else "PENDING"


def _format_datetime_for_input(value):
    if value is None:
        return ""
    return value.strftime("%Y-%m-%dT%H:%M")


def _serialize_ticket_type_for_modal(ticket, sold_count=0):
    price = Decimal(ticket.price or 0)
    remaining_quantity = max(0, (ticket.quantity or 0) - sold_count)
    return {
        "id": ticket.id,
        "name": ticket.name or "",
        "description": ticket.description or "",
        "price": str(price),
        "remainingQuantity": remaining_quantity,
        "soldQuantity": sold_count,
        "saleStart": _format_datetime_for_input(ticket.saleStart),
        "saleEnd": _format_datetime_for_input(ticket.saleEnd),
    }


def _build_edit_event_initial_data(event, ticket_types, selected_status=None):
    resolved_status = _normalize_event_status(selected_status or _map_event_status_for_form(event.status))

    limit_quantity = event.limitQuantity if isinstance(event.limitQuantity, int) and event.limitQuantity > 0 else ""
    limit_mode = "limited" if event.limitQuantity else "unlimited"
    verify_method = "qr" if event.hasFaceReg is False else "face"

    image_url = (event.image or "").strip()
    image_name = ""
    if image_url:
        image_name = image_url.split("?")[0].rstrip("/").split("/")[-1]

    tickets = []
    for ticket in ticket_types or []:
        price = Decimal(ticket.price or 0)
        tickets.append(
            {
                "id": ticket.id,
                "name": ticket.name or "",
                "description": ticket.description or "",
                "price": str(price),
                "quantity": ticket.quantity or 0,
                "saleStart": _format_datetime_for_input(ticket.saleStart),
                "saleEnd": _format_datetime_for_input(ticket.saleEnd),
                "isFree": price <= 0,
            }
        )

    return {
        "title": event.title or "",
        "location": event.location or "",
        "eventTypeId": event.eventTypeId,
        "eventStatus": resolved_status,
        "description": event.description or "",
        "startTime": _format_datetime_for_input(event.startTime),
        "endTime": _format_datetime_for_input(event.endTime),
        "limitMode": limit_mode,
        "limitQuantity": limit_quantity,
        "verifyMethod": verify_method,
        "imageUrl": image_url,
        "imageName": image_name,
        "tickets": tickets,
    }


def _render_create_event_page(event_types, selected_status="PENDING"):
    return render_template(
        "organizer_create_event.html",
        event_types=event_types,
        show_search=False,
        selected_event_status=selected_status,
    )


def _render_edit_event_page(event, event_types, ticket_types, selected_status=None):
    initial_event_data = _build_edit_event_initial_data(event, ticket_types, selected_status=selected_status)
    return render_template(
        "organizer_edit_event.html",
        event=event,
        event_types=event_types,
        show_search=False,
        selected_event_status=initial_event_data["eventStatus"],
        initial_event_data=initial_event_data,
    )


@event_bp.route('/organizer/events/create', methods=['GET', 'POST'])
def organizer_create_event():
    user_id = session.get('user_id')
    organizer = db.session.get(Organizer, user_id) if user_id else None
    if organizer is None:
        return redirect(url_for('main.index'))

    event_types = get_event_types()
    if request.method == 'GET':
        return _render_create_event_page(event_types, "PENDING")

    title = (request.form.get("title") or "").strip()
    location = (request.form.get("location") or "").strip()
    description = _sanitize_rich_html(request.form.get("description"))
    selected_status = _normalize_event_status(request.form.get("eventStatus"))

    if not title:
        flash("Vui long nhap ten su kien.", "danger")
        return _render_create_event_page(event_types, selected_status), 400

    if not location:
        flash("Vui long nhap dia diem to chuc.", "danger")
        return _render_create_event_page(event_types, selected_status), 400

    if not description:
        flash("Vui long nhap thong tin su kien.", "danger")
        return _render_create_event_page(event_types, selected_status), 400

    event_type_id = _parse_positive_int(request.form.get("eventTypeId"))
    if event_type_id is None or db.session.get(EventType, event_type_id) is None:
        flash("Vui long chon the loai su kien hop le.", "danger")
        return _render_create_event_page(event_types, selected_status), 400

    start_time = _parse_datetime_local(request.form.get("startTime"))
    end_time = _parse_datetime_local(request.form.get("endTime"))
    if start_time is None or end_time is None:
        flash("Vui long nhap day du thoi gian bat dau va ket thuc.", "danger")
        return _render_create_event_page(event_types, selected_status), 400
    if end_time < start_time:
        flash("Thoi gian ket thuc phai lon hon hoac bang thoi gian bat dau.", "danger")
        return _render_create_event_page(event_types, selected_status), 400

    limit_mode = (request.form.get("limitMode") or "limited").strip().lower()
    limit_quantity = None
    if limit_mode != "unlimited":
        limit_quantity = _parse_positive_int(request.form.get("limitQuantity"))
        if limit_quantity is None:
            flash("Gioi han so luong ve tren moi tai khoan phai lon hon 0.", "danger")
            return _render_create_event_page(event_types, selected_status), 400

    verify_method = (request.form.get("verifyMethod") or "face").strip().lower()
    has_face_reg = verify_method == "face"

    event_image_result, event_image_error = cloudinary_service.upload_event_image(request.files.get("eventImage"))
    if event_image_error:
        flash(event_image_error, "danger")
        return _render_create_event_page(event_types, selected_status), 400

    ticket_payload, ticket_error = _parse_tickets_payload(request.form.get("tickets_json"))
    if ticket_error:
        flash(ticket_error, "danger")
        return _render_create_event_page(event_types, selected_status), 400

    try:
        event = create_event(
            {
                "title": title,
                "image": event_image_result.get("url") if event_image_result else None,
                "description": description,
                "location": location,
                "startTime": start_time,
                "endTime": end_time,
                "publishedAt": datetime.utcnow() if selected_status == "PUBLISHED" else None,
                "hasFaceReg": has_face_reg,
                "limitQuantity": limit_quantity,
                "status": selected_status,
                "eventTypeId": event_type_id,
                "organizerId": organizer.id,
            },
            commit=False,
        )
        db.session.flush()

        for ticket in ticket_payload:
            create_ticket_type(
                {
                    "name": ticket["name"],
                    "description": ticket["description"],
                    "price": ticket["price"],
                    "quantity": ticket["quantity"],
                    "saleStart": ticket["saleStart"],
                    "saleEnd": ticket["saleEnd"],
                    "eventId": event.id,
                },
                commit=False,
            )

        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to create event")
        flash("Khong the tao su kien. Vui long thu lai.", "danger")
        return _render_create_event_page(event_types, selected_status), 500

    flash("Tao su kien thanh cong.", "success")
    return redirect(url_for('main.index'))


@event_bp.route('/organizer/events/<int:event_id>/edit', methods=['GET', 'POST'])
def organizer_edit_event(event_id: int):
    user_id = session.get('user_id')
    organizer = db.session.get(Organizer, user_id) if user_id else None
    if organizer is None:
        return redirect(url_for('main.index'))

    event = get_event_by_id(event_id)
    if event is None:
        abort(404)

    if event.organizerId != organizer.id:
        flash("Ban khong co quyen chinh sua su kien nay.", "danger")
        return redirect(url_for('main.index'))

    normalized_event_status = (event.status or "").strip().upper()
    if normalized_event_status != "PENDING":
        flash("Chi co the chinh sua su kien dang xu ly.", "danger")
        return redirect(url_for('event.organizer_event_detail', event_id=event_id))

    event_types = get_event_types()
    ticket_types = get_ticket_types_by_event_id(event_id) or []

    if request.method == 'GET':
        return _render_edit_event_page(event, event_types, ticket_types)

    title = (request.form.get("title") or "").strip()
    location = (request.form.get("location") or "").strip()
    description = _sanitize_rich_html(request.form.get("description"))
    selected_status = _normalize_event_status(request.form.get("eventStatus"))

    if not title:
        flash("Vui long nhap ten su kien.", "danger")
        return _render_edit_event_page(event, event_types, ticket_types, selected_status), 400

    if not location:
        flash("Vui long nhap dia diem to chuc.", "danger")
        return _render_edit_event_page(event, event_types, ticket_types, selected_status), 400

    if not description:
        flash("Vui long nhap thong tin su kien.", "danger")
        return _render_edit_event_page(event, event_types, ticket_types, selected_status), 400

    event_type_id = _parse_positive_int(request.form.get("eventTypeId"))
    if event_type_id is None or db.session.get(EventType, event_type_id) is None:
        flash("Vui long chon the loai su kien hop le.", "danger")
        return _render_edit_event_page(event, event_types, ticket_types, selected_status), 400

    start_time = _parse_datetime_local(request.form.get("startTime"))
    end_time = _parse_datetime_local(request.form.get("endTime"))
    if start_time is None or end_time is None:
        flash("Vui long nhap day du thoi gian bat dau va ket thuc.", "danger")
        return _render_edit_event_page(event, event_types, ticket_types, selected_status), 400
    if end_time < start_time:
        flash("Thoi gian ket thuc phai lon hon hoac bang thoi gian bat dau.", "danger")
        return _render_edit_event_page(event, event_types, ticket_types, selected_status), 400

    limit_mode = (request.form.get("limitMode") or "limited").strip().lower()
    limit_quantity = None
    if limit_mode != "unlimited":
        limit_quantity = _parse_positive_int(request.form.get("limitQuantity"))
        if limit_quantity is None:
            flash("Gioi han so luong ve tren moi tai khoan phai lon hon 0.", "danger")
            return _render_edit_event_page(event, event_types, ticket_types, selected_status), 400

    verify_method = (request.form.get("verifyMethod") or "face").strip().lower()
    has_face_reg = verify_method == "face"

    event_image_result, event_image_error = cloudinary_service.upload_event_image(request.files.get("eventImage"))
    if event_image_error:
        flash(event_image_error, "danger")
        return _render_edit_event_page(event, event_types, ticket_types, selected_status), 400

    ticket_payload, ticket_error = _parse_tickets_payload(request.form.get("tickets_json"))
    if ticket_error:
        flash(ticket_error, "danger")
        return _render_edit_event_page(event, event_types, ticket_types, selected_status), 400

    existing_ticket_by_id = {ticket.id: ticket for ticket in ticket_types}
    incoming_existing_ids = set()
    for index, ticket in enumerate(ticket_payload, start=1):
        ticket_id = ticket.get("id")
        if ticket_id is None:
            continue

        if ticket_id not in existing_ticket_by_id:
            flash(f"Loai ve thu {index} khong ton tai hoac khong thuoc su kien nay.", "danger")
            return _render_edit_event_page(event, event_types, ticket_types, selected_status), 400

        if ticket_id in incoming_existing_ids:
            flash("Danh sach loai ve bi trung ID.", "danger")
            return _render_edit_event_page(event, event_types, ticket_types, selected_status), 400

        incoming_existing_ids.add(ticket_id)

    removed_ticket_ids = [ticket_id for ticket_id in existing_ticket_by_id if ticket_id not in incoming_existing_ids]
    if removed_ticket_ids:
        has_issued_tickets = (
            db.session.query(Ticket.id)
            .filter(Ticket.ticketTypeId.in_(removed_ticket_ids))
            .first()
        )
        if has_issued_tickets:
            flash("Khong the xoa loai ve da phat sinh giao dich.", "danger")
            return _render_edit_event_page(event, event_types, ticket_types, selected_status), 400

    try:
        event.title = title
        event.location = location
        event.description = description
        event.startTime = start_time
        event.endTime = end_time
        event.hasFaceReg = has_face_reg
        event.limitQuantity = limit_quantity
        event.status = _resolve_event_status_for_db(selected_status)
        event.eventTypeId = event_type_id
        event.publishedAt = datetime.utcnow() if selected_status == "PUBLISHED" else None

        if event_image_result and event_image_result.get("url"):
            event.image = event_image_result.get("url")

        for ticket in ticket_payload:
            ticket_id = ticket.get("id")
            if ticket_id is None:
                target_ticket = TicketType(eventId=event.id)
                db.session.add(target_ticket)
            else:
                target_ticket = existing_ticket_by_id[ticket_id]

            target_ticket.name = ticket["name"]
            target_ticket.description = ticket["description"]
            target_ticket.price = ticket["price"]
            target_ticket.quantity = ticket["quantity"]
            target_ticket.saleStart = ticket["saleStart"]
            target_ticket.saleEnd = ticket["saleEnd"]

        for ticket_id in removed_ticket_ids:
            db.session.delete(existing_ticket_by_id[ticket_id])

        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to update event")
        flash("Khong the cap nhat su kien. Vui long thu lai.", "danger")
        return _render_edit_event_page(event, event_types, ticket_types, selected_status), 500

    flash("Cap nhat su kien thanh cong.", "success")
    return redirect(url_for('event.organizer_event_detail', event_id=event_id))


@event_bp.route('/organizer/events/<int:event_id>')
def organizer_event_detail(event_id: int):
    user_id = session.get('user_id')
    organizer = db.session.get(Organizer, user_id) if user_id else None
    if organizer is None:
        return redirect(url_for('event.event_details', event_id=event_id))

    event = get_event_by_id(event_id)
    if not event:
        abort(404)

    if event.organizerId != organizer.id:
        flash("Ban khong co quyen xem chi tiet su kien nay.", "danger")
        return redirect(url_for('main.index'))

    ticket_types = get_ticket_types_by_event_id(event_id) or []
    sold_map = count_sold_by_ticket_type([t.id for t in ticket_types])
    for t in ticket_types:
        sold = sold_map.get(t.id, 0)
        t.remaining = max(0, (t.quantity or 0) - sold)

    return render_template(
        "organizer_event_detail.html",
        event=event,
        ticket_types=ticket_types,
        ticket_types_payload=[_serialize_ticket_type_for_modal(t, sold_map.get(t.id, 0)) for t in ticket_types],
        ticket_adjust_update_url=url_for('event.organizer_update_ticket_type', event_id=event_id),
        show_search=False,
        header_show_create_event=True,
    )


@event_bp.route('/organizer/events/<int:event_id>/ticket-types/update', methods=['POST'])
def organizer_update_ticket_type(event_id: int):
    user_id = session.get('user_id')
    organizer = db.session.get(Organizer, user_id) if user_id else None
    if organizer is None:
        return jsonify({"message": "Ban can dang nhap de thuc hien thao tac nay."}), 401

    event = get_event_by_id(event_id)
    if event is None:
        return jsonify({"message": "Su kien khong ton tai."}), 404

    if event.organizerId != organizer.id:
        return jsonify({"message": "Ban khong co quyen cap nhat loai ve cua su kien nay."}), 403

    payload = request.get_json(silent=True) or {}
    ticket_type_id = _parse_positive_int(payload.get("ticketTypeId"))
    if ticket_type_id is None:
        return jsonify({"message": "ID loai ve khong hop le."}), 400

    ticket_type = TicketType.query.filter_by(id=ticket_type_id, eventId=event.id).first()
    if ticket_type is None:
        return jsonify({"message": "Loai ve khong ton tai hoac khong thuoc su kien nay."}), 404

    try:
        price = Decimal(str(payload.get("price", "0")))
    except (InvalidOperation, ValueError, TypeError):
        return jsonify({"message": "Gia ve khong hop le."}), 400

    if price < 0:
        return jsonify({"message": "Gia ve khong duoc am."}), 400

    remaining_quantity = _parse_non_negative_int(payload.get("remainingQuantity"))
    if remaining_quantity is None:
        return jsonify({"message": "So luong ve con lai khong hop le."}), 400

    sale_start = _parse_datetime_local(payload.get("saleStart"))
    sale_end = _parse_datetime_local(payload.get("saleEnd"))
    if sale_start is None or sale_end is None:
        return jsonify({"message": "Thoi gian bat dau/ket thuc ban ve khong hop le."}), 400
    if sale_end < sale_start:
        return jsonify({"message": "Thoi gian ket thuc ban ve phai sau thoi gian bat dau."}), 400

    sold_count = count_sold_by_ticket_type([ticket_type.id]).get(ticket_type.id, 0)

    ticket_type.price = price
    ticket_type.quantity = sold_count + remaining_quantity
    ticket_type.saleStart = sale_start
    ticket_type.saleEnd = sale_end
    ticket_type.description = (payload.get("description") or "").strip()

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to update ticket type from organizer detail modal")
        return jsonify({"message": "Khong the cap nhat loai ve. Vui long thu lai."}), 500

    return jsonify(
        {
            "message": "Cap nhat loai ve thanh cong.",
            "ticket": _serialize_ticket_type_for_modal(ticket_type, sold_count=sold_count),
        }
    )


@event_bp.route('/organizer/events/<int:event_id>/delete-or-hide', methods=['POST'])
def organizer_delete_or_hide_event(event_id: int):
    user_id = session.get('user_id')
    organizer = db.session.get(Organizer, user_id) if user_id else None
    if organizer is None:
        return jsonify({"message": "Ban can dang nhap de thuc hien thao tac nay."}), 401

    event = get_event_by_id(event_id)
    if event is None:
        return jsonify({"message": "Su kien khong ton tai."}), 404

    if event.organizerId != organizer.id:
        return jsonify({"message": "Ban khong co quyen thuc hien thao tac voi su kien nay."}), 403

    normalized_status = (event.status or "").strip().upper()

    if normalized_status == "PENDING":
        ticket_types = get_ticket_types_by_event_id(event.id) or []
        ticket_type_ids = [ticket.id for ticket in ticket_types]

        try:
            if ticket_type_ids:
                Ticket.query.filter(Ticket.ticketTypeId.in_(ticket_type_ids)).delete(synchronize_session=False)
                TicketType.query.filter(TicketType.id.in_(ticket_type_ids)).delete(synchronize_session=False)

            db.session.delete(event)
            db.session.commit()
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Failed to permanently delete pending event")
            return jsonify({"message": "Khong the xoa su kien. Vui long thu lai."}), 500

        flash("Xoa su kien thanh cong.", "success")

        return jsonify(
            {
                "message": "Xoa su kien thanh cong.",
                "action": "deleted",
                "redirectUrl": url_for('main.index'),
            }
        )

    if normalized_status in {"PUBLISHED", "APPROVED", "FINISHED"}:
        target_cancelled_status = _resolve_cancelled_status_for_db()
        if target_cancelled_status is None:
            return jsonify({"message": "Khong tim thay trang thai CANCELLED de cap nhat."}), 500

        try:
            event.status = target_cancelled_status
            db.session.commit()
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Failed to set event status to CANCELLED")
            return jsonify({"message": "Khong the an su kien. Vui long thu lai."}), 500

        flash("An su kien thanh cong.", "success")

        return jsonify(
            {
                "message": "An su kien thanh cong.",
                "action": "cancelled",
                "redirectUrl": url_for('main.index'),
            }
        )

    return jsonify({"message": "Su kien o trang thai nay khong the xoa/an."}), 400

@event_bp.route("/events/<int:event_id>")
def event_details(event_id: int):
    # Load event
    event = get_event_by_id(event_id)
    if not event:
        abort(404)

    # Load ticket types
    ticket_types = get_ticket_types_by_event_id(event_id) or []
    sold_map = count_sold_by_ticket_type([t.id for t in ticket_types])

    # Tính remaining cho từng loại vé (nếu có DAO đếm số vé đã phát hành)
    # count_sold_by_ticket_type trả về dict {ticket_type_id: sold_count}
    for t in ticket_types:
        sold = sold_map.get(t.id, 0)
        t.remaining = max(0, (t.quantity or 0) - sold)

    return render_template("event_detail.html", event=event, ticket_types=ticket_types)
