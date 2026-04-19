import re
import secrets
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from io import BytesIO

from flask import abort, current_app, flash, jsonify, redirect, render_template, request, session, url_for
import qrcode
from sqlalchemy import func

from .. import db
from ..models.booking import Booking
from ..models.event import Event
from ..models.payment import Payment
from ..models.ticket import Ticket
from ..models.ticket_type import TicketType
from ..models.user import Customer
from ..services.cloudinary_service import cloudinary_service
from ..services.event_service import get_event_by_id
from ..services.ticket_email_service import send_ticket_email_by_booking
from ..services.ticket_service import count_sold_by_ticket_type, get_ticket_types_by_event_id
from ..utils.qr_utils import sign_payload
from ..utils.vnpay_utils import build_payment_url, request_refund, verify_return_data
from .event_routes import event_bp


CHECKOUT_PHONE_PATTERN = re.compile(r"^(0\d{9,10}|\+84\d{9,10})$")


def _utcnow_naive() -> datetime:
	# Preserve legacy naive-UTC behavior without relying on deprecated utcnow().
	return datetime.now(UTC).replace(tzinfo=None)


def _parse_positive_int(value):
	try:
		parsed = int(value)
	except (TypeError, ValueError):
		return None

	return parsed if parsed > 0 else None


def _normalize_phone_number(phone):
	return re.sub(r"\s+", "", str(phone or ""))


def _request_client_ip():
	forwarded_for = request.headers.get("X-Forwarded-For", "")
	if forwarded_for:
		return forwarded_for.split(",", 1)[0].strip() or "127.0.0.1"

	return (request.remote_addr or "127.0.0.1").strip()


def _payment_return_url():
	return url_for("event.payment_return", _external=True)


def _build_vnpay_txn_ref(booking_id: int) -> str:
	return f"BK{booking_id}_{_utcnow_naive().strftime('%Y%m%d%H%M%S%f')}"


def _extract_booking_id_from_txn_ref(txn_ref):
	normalized = (txn_ref or "").strip()
	if not normalized:
		return None

	if normalized.startswith("BK"):
		normalized = normalized[2:].split("_", 1)[0]

	return _parse_positive_int(normalized)


def _parse_vnpay_pay_date(value):
	text = str(value or "").strip()
	if len(text) != 14 or not text.isdigit():
		return None

	try:
		return datetime.strptime(text, "%Y%m%d%H%M%S")
	except ValueError:
		return None


def _to_vnpay_datetime(value):
	if value is None:
		return ""

	if isinstance(value, datetime):
		return value.strftime("%Y%m%d%H%M%S")

	text = str(value).strip()
	return text if len(text) == 14 and text.isdigit() else ""


def _extract_transaction_no(transaction_id):
	parts = [part.strip() for part in str(transaction_id or "").split("|") if part.strip()]
	if len(parts) >= 2:
		return parts[1]
	if len(parts) == 1:
		return parts[0]
	return ""


def _generate_ticket_code():
	for _ in range(8):
		ticket_code = f"TK{secrets.token_hex(4).upper()}"
		if Ticket.query.filter(Ticket.ticketCode == ticket_code).first() is None:
			return ticket_code

	return f"TK{uuid.uuid4().hex[:8].upper()}"


def _parse_checkout_tickets(payload_tickets):
	if not isinstance(payload_tickets, list) or not payload_tickets:
		return None, "Vui lòng chọn ít nhất một loại vé."

	normalized_by_ticket_type = {}

	for ticket_index, ticket_item in enumerate(payload_tickets, start=1):
		if not isinstance(ticket_item, dict):
			return None, f"Dữ liệu vé thứ {ticket_index} không hợp lệ."

		ticket_type_id = _parse_positive_int(ticket_item.get("ticketTypeId"))
		quantity = _parse_positive_int(ticket_item.get("quantity"))
		holders = ticket_item.get("holders")

		if ticket_type_id is None:
			return None, f"Loại vé thứ {ticket_index} không hợp lệ."
		if quantity is None:
			return None, f"Số lượng của loại vé thứ {ticket_index} phải lớn hơn 0."
		if not isinstance(holders, list):
			return None, f"Danh sách người giữ vé của loại vé thứ {ticket_index} không hợp lệ."

		parsed_holders = []
		for holder_index, holder in enumerate(holders, start=1):
			if not isinstance(holder, dict):
				return None, f"Thông tin người giữ vé thứ {holder_index} của loại vé thứ {ticket_index} không hợp lệ."

			full_name = " ".join((holder.get("fullName") or "").split())
			phone_number = _normalize_phone_number(holder.get("phoneNumber"))
			face_embedding = (holder.get("faceEmbedding") or "").strip() or None

			if len(full_name) < 2:
				return None, f"Vui lòng nhập họ tên hợp lệ cho vé thứ {holder_index} của loại vé thứ {ticket_index}."
			if not CHECKOUT_PHONE_PATTERN.match(phone_number):
				return None, f"Số điện thoại của vé thứ {holder_index} của loại vé thứ {ticket_index} không hợp lệ."

			parsed_holders.append(
				{
					"fullName": full_name,
					"phoneNumber": phone_number,
					"faceEmbedding": face_embedding,
				}
			)

		bucket = normalized_by_ticket_type.setdefault(
			ticket_type_id,
			{
				"ticketTypeId": ticket_type_id,
				"quantity": 0,
				"holders": [],
			},
		)
		bucket["quantity"] += quantity
		bucket["holders"].extend(parsed_holders)

	normalized_tickets = []
	for item in normalized_by_ticket_type.values():
		if item["quantity"] != len(item["holders"]):
			return None, "Số lượng vé không khớp với số người giữ vé đã nhập."
		normalized_tickets.append(item)

	return normalized_tickets, None


def _create_and_upload_qr_url(ticket: Ticket, event_id: int):
	payload = {
		"ver": 1,
		"ticket_id": ticket.id,
		"ticket_code": ticket.ticketCode,
		"event_id": event_id,
		"customer_id": ticket.customerId,
		"booking_id": ticket.bookingId,
		"iat": _utcnow_naive().replace(microsecond=0).isoformat(),
	}

	token = sign_payload(payload)
	qr_image = qrcode.make(token)
	buffer = BytesIO()
	qr_image.save(buffer, format="PNG")

	upload_result, upload_error = cloudinary_service.upload_image_bytes(
		image_bytes=buffer.getvalue(),
		filename=f"{ticket.ticketCode or ticket.id}.png",
	)
	if upload_error:
		return None, upload_error

	qr_url = (upload_result or {}).get("url")
	if not qr_url:
		return None, "Không nhận được đường dẫn ảnh QR từ Cloudinary."

	return qr_url, None


def _restore_quantity_for_failed_booking(booking_id: int):
	tickets = Ticket.query.filter(Ticket.bookingId == booking_id).all()
	if not tickets:
		return

	restore_map = {}
	for ticket in tickets:
		restore_map[ticket.ticketTypeId] = restore_map.get(ticket.ticketTypeId, 0) + 1
		ticket.status = "CANCELLED"

	ticket_types = (
		TicketType.query
		.filter(TicketType.id.in_(list(restore_map.keys())))
		.with_for_update()
		.all()
	)

	for ticket_type in ticket_types:
		ticket_type.quantity = int(ticket_type.quantity or 0) + restore_map.get(ticket_type.id, 0)


def _get_booking_event(booking_id: int):
	ticket = (
		Ticket.query
		.filter(Ticket.bookingId == booking_id)
		.order_by(Ticket.createdAt.asc())
		.first()
	)
	if ticket is None:
		return None

	ticket_type = db.session.get(TicketType, ticket.ticketTypeId)
	if ticket_type is None:
		return None

	return db.session.get(Event, ticket_type.eventId)


def _build_retry_payment_url(booking: Booking):
	event = _get_booking_event(booking.id)
	event_title = event.title if event and event.title else booking.id

	txn_ref = _build_vnpay_txn_ref(booking.id)
	order_info = f"Thanh toan ve su kien {event_title} - booking {booking.id}"
	payment_payload = build_payment_url(
		amount=float(booking.totalAmount or 0),
		txn_ref=txn_ref,
		order_info=order_info[:255],
		ip_addr=_request_client_ip(),
		return_url=_payment_return_url(),
	)

	return payment_payload["payment_url"]


@event_bp.route("/events/<int:event_id>/confirm-ticket-info")
def confirm_ticket_info(event_id: int):
	event = get_event_by_id(event_id)
	if not event:
		abort(404)

	ticket_types = get_ticket_types_by_event_id(event_id) or []
	sold_map = count_sold_by_ticket_type([t.id for t in ticket_types])

	ticket_types_payload = []
	for ticket_type in ticket_types:
		sold = sold_map.get(ticket_type.id, 0)
		ticket_types_payload.append(
			{
				"id": ticket_type.id,
				"name": ticket_type.name or "",
				"description": ticket_type.description or "",
				"price": float(ticket_type.price or 0),
				"remaining": max(0, (ticket_type.quantity or 0) - sold),
			}
		)

	return render_template(
		"confirm_ticket_info.html",
		event=event,
		ticket_types_payload=ticket_types_payload,
		show_search=False,
	)


@event_bp.route("/events/<int:event_id>/checkout", methods=["POST"])
def checkout_event_tickets(event_id: int):
	user_id = session.get("user_id")
	if user_id is None:
		return jsonify(
			{
				"ok": False,
				"message": "Bạn cần đăng nhập để tiếp tục thanh toán.",
				"redirectUrl": url_for("login.login"),
			}
		), 401

	if db.session.get(Customer, user_id) is None:
		return jsonify(
			{
				"ok": False,
				"message": "Tài khoản hiện tại chưa có vai trò Khách hàng để mua vé.",
			}
		), 403

	event = get_event_by_id(event_id)
	if event is None:
		return jsonify({"ok": False, "message": "Sự kiện không tồn tại."}), 404

	if (event.status or "").strip().upper() != "PUBLISHED":
		return jsonify({"ok": False, "message": "Sự kiện hiện không mở bán vé."}), 400

	payload = request.get_json(silent=True) or {}
	checkout_tickets, parse_error = _parse_checkout_tickets(payload.get("tickets"))
	if parse_error:
		return jsonify({"ok": False, "message": parse_error}), 400

	ticket_type_ids = [item["ticketTypeId"] for item in checkout_tickets]
	unique_ticket_type_ids = list(set(ticket_type_ids))

	try:
		ticket_type_rows = (
			TicketType.query
			.filter(
				TicketType.eventId == event.id,
				TicketType.id.in_(unique_ticket_type_ids),
			)
			.with_for_update()
			.all()
		)
		ticket_type_map = {ticket_type.id: ticket_type for ticket_type in ticket_type_rows}

		if len(ticket_type_map) != len(unique_ticket_type_ids):
			return jsonify(
				{
					"ok": False,
					"message": "Một hoặc nhiều loại vé không còn tồn tại trong sự kiện này.",
				}
			), 400

		now = datetime.now()
		total_amount = Decimal("0")

		for selected_ticket in checkout_tickets:
			ticket_type = ticket_type_map[selected_ticket["ticketTypeId"]]

			if ticket_type.saleStart and now < ticket_type.saleStart:
				return jsonify(
					{
						"ok": False,
						"message": f"Loại vé {ticket_type.name or ticket_type.id} chưa đến thời gian mở bán.",
					}
				), 400

			if ticket_type.saleEnd and now > ticket_type.saleEnd:
				return jsonify(
					{
						"ok": False,
						"message": f"Loại vé {ticket_type.name or ticket_type.id} đã hết thời gian bán.",
					}
				), 400

			available_quantity = int(ticket_type.quantity or 0)
			selected_quantity = selected_ticket["quantity"]
			if selected_quantity > available_quantity:
				return jsonify(
					{
						"ok": False,
						"message": f"Loại vé {ticket_type.name or ticket_type.id} đã hết vé.",
					}
				), 400

			total_amount += Decimal(ticket_type.price or 0) * Decimal(selected_quantity)

		for selected_ticket in checkout_tickets:
			ticket_type = ticket_type_map[selected_ticket["ticketTypeId"]]
			ticket_type.quantity = int(ticket_type.quantity or 0) - selected_ticket["quantity"]

		booking = Booking(
			totalAmount=total_amount,
			createdAt=datetime.now(),
			status="PENDING",
			customerId=user_id,
		)
		db.session.add(booking)
		db.session.flush()

		for selected_ticket in checkout_tickets:
			ticket_type = ticket_type_map[selected_ticket["ticketTypeId"]]

			for holder in selected_ticket["holders"]:
				ticket = Ticket(
					id=str(uuid.uuid4()),
					qrCode=None,
					createdAt=datetime.now(),
					checkedIn=None,
					price=ticket_type.price,
					ticketCode=_generate_ticket_code(),
					fullName=holder["fullName"],
					phoneNumber=holder["phoneNumber"],
					faceEmbedding=holder.get("faceEmbedding"),
					status="PENDING",
					bookingId=booking.id,
					ticketTypeId=ticket_type.id,
					customerId=user_id,
				)

				if event.hasFaceReg is False:
					qr_url, qr_error = _create_and_upload_qr_url(ticket=ticket, event_id=event.id)
					if qr_error:
						raise RuntimeError(qr_error)
					ticket.qrCode = qr_url

				db.session.add(ticket)

		txn_ref = _build_vnpay_txn_ref(booking.id)
		order_info = f"Thanh toan ve su kien {event.title or event.id} - booking {booking.id}"
		payment_payload = build_payment_url(
			amount=float(total_amount),
			txn_ref=txn_ref,
			order_info=order_info[:255],
			ip_addr=_request_client_ip(),
			return_url=_payment_return_url(),
		)

		db.session.commit()
	except RuntimeError as exc:
		db.session.rollback()
		return jsonify({"ok": False, "message": str(exc)}), 500
	except Exception:
		db.session.rollback()
		current_app.logger.exception("Failed to checkout event tickets")
		return jsonify(
			{
				"ok": False,
				"message": "Không thể tạo đơn thanh toán. Vui lòng thử lại.",
			}
		), 500

	return jsonify(
		{
			"ok": True,
			"message": "Khởi tạo đơn hàng thành công.",
			"bookingId": booking.id,
			"paymentUrl": payment_payload["payment_url"],
		}
	)


@event_bp.route("/payment_return")
def payment_return():
	verify_result = verify_return_data(request.args.to_dict(flat=False))
	booking_id = _extract_booking_id_from_txn_ref(verify_result.get("txn_ref"))

	if booking_id is None:
		flash("Không xác định được đơn hàng thanh toán.", "danger")
		return redirect(url_for("main.index"))

	booking = db.session.get(Booking, booking_id)
	if booking is None:
		flash("Đơn hàng không tồn tại.", "danger")
		return redirect(url_for("main.index"))

	my_tickets_url = url_for("orders.my_tickets")
	event = _get_booking_event(booking.id)
	event_detail_url = url_for("event.event_details", event_id=event.id) if event else my_tickets_url

	booking_status = (booking.status or "").strip().upper()
	if booking_status == "SUCCESS":
		flash("Giao dịch đã được xử lý trước đó.", "info")
		return redirect(my_tickets_url)

	if booking_status == "FAILED":
		flash("Đơn hàng này đã được đánh dấu thanh toán thất bại.", "danger")
		return redirect(event_detail_url)

	if not verify_result.get("is_valid_signature"):
		flash("Chữ ký thanh toán không hợp lệ.", "danger")
		return redirect(event_detail_url)

	txn_ref = str(verify_result.get("txn_ref") or "").strip()
	transaction_no = str(verify_result.get("transaction_no") or "").strip()
	pay_date_raw = str(verify_result.get("pay_date") or "").strip()
	pay_date = _parse_vnpay_pay_date(pay_date_raw)

	if verify_result.get("is_success"):
		transaction_id = transaction_no or txn_ref or f"BK{booking.id}_SUCCESS"
	else:
		# Failed attempts should be counted by each retry payment request.
		transaction_id = txn_ref or transaction_no or f"BK{booking.id}_{_utcnow_naive().strftime('%Y%m%d%H%M%S%f')}"

	amount = booking.totalAmount if booking.totalAmount is not None else Decimal(str(verify_result.get("amount") or 0))

	send_success_email = False

	try:
		existing_payment = (
			Payment.query
			.filter(
				Payment.bookingId == booking.id,
				Payment.transactionID == transaction_id[:255],
			)
			.first()
		)

		if verify_result.get("is_success"):
			if existing_payment is None:
				payment = Payment(
					amount=amount,
					transactionID=transaction_id[:255],
					vnpTxnRef=txn_ref[:50] if txn_ref else None,
					vnpPayDate=pay_date,
					status="SUCCESS",
					bookingId=booking.id,
				)
				db.session.add(payment)
			else:
				if txn_ref and not existing_payment.vnpTxnRef:
					existing_payment.vnpTxnRef = txn_ref[:50]
				if pay_date and existing_payment.vnpPayDate is None:
					existing_payment.vnpPayDate = pay_date

			booking.status = "SUCCESS"
			Ticket.query.filter(Ticket.bookingId == booking.id).update(
				{"status": "VALID"},
				synchronize_session=False,
			)
			send_success_email = existing_payment is None
			db.session.commit()

			flash("Thanh toán thành công.", "success")
			if send_success_email:
				try:
					send_ticket_email_by_booking(booking.id)
				except Exception:
					current_app.logger.exception("Failed to send ticket email by booking")

			return redirect(my_tickets_url)

		failed_attempts = (
			Payment.query
			.filter(
				Payment.bookingId == booking.id,
				func.upper(func.coalesce(Payment.status, "")) == "FAILED",
			)
			.count()
		)

		if existing_payment is None:
			failed_payment = Payment(
				amount=amount,
				transactionID=transaction_id[:255],
				status="FAILED",
				bookingId=booking.id,
			)
			db.session.add(failed_payment)
			failed_attempts += 1

		if failed_attempts > 2:
			_restore_quantity_for_failed_booking(booking.id)
			booking.status = "FAILED"
			db.session.commit()

			flash("Thanh toán thất bại quá 2 lần. Đơn hàng đã bị hủy.", "danger")
			return redirect(event_detail_url)

		db.session.commit()

		retry_url = _build_retry_payment_url(booking)
		flash(
			f"Thanh toán không thành công. Vui lòng thử lại ({failed_attempts}/3).",
			"warning",
		)
		return redirect(retry_url)
	except Exception:
		db.session.rollback()
		current_app.logger.exception("Failed to process VNPay payment return")
		flash("Không thể cập nhật trạng thái thanh toán. Vui lòng thử lại.", "danger")
		return redirect(event_detail_url)


def _refund_booking_for_customer(booking_id: int, customer_id: int):
	booking = db.session.get(Booking, booking_id)
	if booking is None or booking.customerId != customer_id:
		flash("Không tìm thấy đơn hàng cần hủy/hoàn tiền.", "danger")
		return redirect(url_for("orders.my_tickets"))

	booking_detail_url = url_for("orders.booking_detail", booking_id=booking.id)

	tickets = (
		Ticket.query
		.filter(
			Ticket.bookingId == booking.id,
			Ticket.customerId == customer_id,
		)
		.all()
	)
	if not tickets:
		flash("Đơn hàng không có vé hợp lệ để hoàn tiền.", "danger")
		return redirect(booking_detail_url)

	statuses = [str(ticket.status or "").upper() for ticket in tickets]
	if any(status in {"USED"} for status in statuses):
		flash("Đơn hàng đã có vé được sử dụng, không thể hoàn tiền toàn bộ.", "warning")
		return redirect(booking_detail_url)

	if any(status == "CANCELLED" for status in statuses):
		flash(
			"Đơn hàng này đã có hoàn tiền trước đó, không hỗ trợ hoàn tiền độc lập từng vé.",
			"warning",
		)
		return redirect(booking_detail_url)

	valid_tickets = [ticket for ticket in tickets if str(ticket.status or "").upper() == "VALID"]
	if not valid_tickets:
		flash("Đơn hàng không còn vé hợp lệ để hoàn tiền.", "warning")
		return redirect(booking_detail_url)

	payment = (
		Payment.query
		.filter(
			Payment.bookingId == booking.id,
			func.upper(func.coalesce(Payment.status, "")) == "SUCCESS",
		)
		.order_by(Payment.id.desc())
		.first()
	)
	if payment is None:
		flash("Không tìm thấy giao dịch thanh toán thành công cho đơn hàng này.", "danger")
		return redirect(booking_detail_url)

	txn_ref = (payment.vnpTxnRef or "").strip()
	transaction_no = _extract_transaction_no(payment.transactionID)
	transaction_date = _to_vnpay_datetime(payment.vnpPayDate)
	refund_amount = Decimal(str(payment.amount or booking.totalAmount or 0)).quantize(Decimal("0.01"))

	if not txn_ref or not transaction_no or not transaction_date:
		flash("Thiếu thông tin VNPay (TxnRef/TransactionNo/PayDate) để hoàn tiền.", "danger")
		return redirect(booking_detail_url)

	if refund_amount <= 0:
		flash("Số tiền hoàn không hợp lệ.", "danger")
		return redirect(booking_detail_url)

	refund_result = request_refund(
		amount=refund_amount,
		txn_ref=txn_ref,
		transaction_no=transaction_no,
		transaction_date=transaction_date,
		order_info=f"Hoan tien booking {booking.id}",
		ip_addr=_request_client_ip(),
		transaction_type="02",
		create_by=str(customer_id),
		timeout_seconds=30,
	)

	if not refund_result.get("is_success"):
		failure_message = refund_result.get("message") or "Không xác định"
		if "too many refund count" in failure_message.lower():
			# VNPay says the transaction was already refunded.
			# Sync local state to avoid keeping tickets as VALID after a remote refund.
			try:
				restore_map = {}
				for ticket in valid_tickets:
					ticket.status = "CANCELLED"
					restore_map[ticket.ticketTypeId] = restore_map.get(ticket.ticketTypeId, 0) + 1

				ticket_types = (
					TicketType.query
					.filter(TicketType.id.in_(list(restore_map.keys())))
					.with_for_update()
					.all()
				)
				for ticket_type in ticket_types:
					ticket_type.quantity = int(ticket_type.quantity or 0) + restore_map.get(ticket_type.id, 0)

				db.session.commit()
			except Exception:
				db.session.rollback()
				current_app.logger.exception("Failed to reconcile booking after VNPay reported prior refund")
				flash(
					"VNPay báo giao dịch đã hoàn tiền trước đó, nhưng hệ thống không thể đồng bộ trạng thái vé. "
					"Vui lòng liên hệ quản trị viên.",
					"danger",
				)
				return redirect(booking_detail_url)

			flash(
				"Giao dịch đã được hoàn tiền trước đó trên VNPay. "
				"Hệ thống đã đồng bộ trạng thái tất cả vé trong đơn về CANCELLED.",
				"success",
			)
			return redirect(booking_detail_url)
		elif "timeout" in failure_message.lower() or "read timed out" in failure_message.lower():
			failure_message = (
				"VNPay đang phản hồi chậm hoặc quá tải. "
				"Vui lòng thử lại sau vài phút"
			)
		flash(f"Hoàn tiền thất bại: {failure_message}.", "danger")
		return redirect(booking_detail_url)

	try:
		restore_map = {}
		for ticket in valid_tickets:
			ticket.status = "CANCELLED"
			restore_map[ticket.ticketTypeId] = restore_map.get(ticket.ticketTypeId, 0) + 1

		ticket_types = (
			TicketType.query
			.filter(TicketType.id.in_(list(restore_map.keys())))
			.with_for_update()
			.all()
		)
		for ticket_type in ticket_types:
			ticket_type.quantity = int(ticket_type.quantity or 0) + restore_map.get(ticket_type.id, 0)

		db.session.commit()
	except Exception:
		db.session.rollback()
		current_app.logger.exception("Refund succeeded but failed to update booking tickets")
		flash("Hoàn tiền thành công nhưng cập nhật trạng thái vé thất bại.", "danger")
		return redirect(booking_detail_url)

	flash("Hoàn tiền thành công. Tất cả vé trong đơn đã được hủy.", "success")
	return redirect(booking_detail_url)


@event_bp.route("/bookings/<int:booking_id>/cancel-refund", methods=["POST"])
def cancel_booking_refund(booking_id: int):
	user_id = session.get("user_id")
	if user_id is None:
		flash("Bạn cần đăng nhập để thực hiện thao tác này.", "danger")
		return redirect(url_for("login.login"))

	return _refund_booking_for_customer(booking_id=booking_id, customer_id=user_id)


@event_bp.route("/tickets/<string:ticket_id>/cancel-refund", methods=["POST"])
def cancel_ticket_refund(ticket_id: str):
	user_id = session.get("user_id")
	if user_id is None:
		flash("Bạn cần đăng nhập để thực hiện thao tác này.", "danger")
		return redirect(url_for("login.login"))

	ticket = Ticket.query.filter(
		Ticket.id == ticket_id,
		Ticket.customerId == user_id,
	).first()
	if ticket is None:
		flash("Không tìm thấy vé cần hủy.", "danger")
		return redirect(url_for("orders.my_tickets"))

	# Backward-compatible endpoint: always process refund at booking level.
	return _refund_booking_for_customer(booking_id=ticket.bookingId, customer_id=user_id)
