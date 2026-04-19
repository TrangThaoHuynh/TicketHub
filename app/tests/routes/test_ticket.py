from datetime import datetime, timedelta
from decimal import Decimal
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy.pool import StaticPool

from app import create_app, db
from app.config import Config
from app.models.booking import Booking
from app.models.enums import (
	AuthProvider,
	BookingStatus,
	EventStatus,
	OrganizerStatus,
	PaymentStatus,
	TicketStatus,
)
from app.models.event import Event
from app.models.payment import Payment
from app.models.ticket import Ticket
from app.models.ticket_type import TicketType
from app.models.user import Customer, User
from app.routes import ticket_routes


@pytest.fixture()
def app(monkeypatch):
	monkeypatch.setattr(Config, "TESTING", True, raising=False)
	monkeypatch.setattr(Config, "SQLALCHEMY_DATABASE_URI", "sqlite://", raising=False)
	monkeypatch.setattr(
		Config,
		"SQLALCHEMY_ENGINE_OPTIONS",
		{
			"connect_args": {"check_same_thread": False},
			"poolclass": StaticPool,
		},
		raising=False,
	)
	monkeypatch.setattr(Config, "DB_AUTO_INIT", True, raising=False)

	app = create_app()
	app.config.update(TESTING=True)

	with app.app_context():
		db.create_all()

		for status in ["PENDING", "SUCCESS", "FAILED"]:
			if db.session.get(BookingStatus, status) is None:
				db.session.add(BookingStatus(status=status))

		for status in ["PENDING", "APPROVED", "REJECTED"]:
			if db.session.get(OrganizerStatus, status) is None:
				db.session.add(OrganizerStatus(status=status))

		for status in ["SUCCESS", "FAILED"]:
			if db.session.get(PaymentStatus, status) is None:
				db.session.add(PaymentStatus(status=status))

		for status in ["PENDING", "VALID", "USED", "CANCELLED"]:
			if db.session.get(TicketStatus, status) is None:
				db.session.add(TicketStatus(status=status))

		for status in ["PENDING", "PUBLISHED", "FINISHED", "CANCELLED"]:
			if db.session.get(EventStatus, status) is None:
				db.session.add(EventStatus(status=status))

		for provider in ["LOCAL", "GOOGLE"]:
			if db.session.get(AuthProvider, provider) is None:
				db.session.add(AuthProvider(provider=provider))

		db.session.commit()

		yield app

		db.session.remove()
		db.drop_all()


@pytest.fixture()
def client(app):
	return app.test_client()


def _new_user(*, make_customer=True):
	suffix = str(uuid.uuid4().int % 10**8).zfill(8)
	user = User(
		name=f"User {suffix}",
		email=f"user_{suffix}@example.com",
		username=f"user_{suffix}",
		password="Strong@123",
		createdAt=datetime.now(),
		phoneNumber=f"09{suffix}",
		provider="LOCAL",
	)
	db.session.add(user)
	db.session.flush()
	user_id = user.id

	if make_customer:
		db.session.add(Customer(id=user_id))

	db.session.commit()
	return user_id


def _new_event_and_ticket_type(
	*,
	event_status="PUBLISHED",
	quantity=5,
	price=Decimal("120000.00"),
	has_face_reg=True,
):
	event = Event(
		title="Demo Event",
		description="Demo",
		location="HCM",
		createdAt=datetime.now(),
		startTime=datetime.now() + timedelta(days=1),
		endTime=datetime.now() + timedelta(days=2),
		hasFaceReg=has_face_reg,
		status=event_status,
	)
	db.session.add(event)
	db.session.flush()
	event_id = event.id

	ticket_type = TicketType(
		name="Standard",
		description="Standard ticket",
		price=price,
		quantity=quantity,
		saleStart=datetime.now() - timedelta(days=1),
		saleEnd=datetime.now() + timedelta(days=1),
		eventId=event.id,
	)
	db.session.add(ticket_type)
	db.session.flush()
	ticket_type_id = ticket_type.id
	db.session.commit()

	return event_id, ticket_type_id


def _new_booking_with_ticket(
	*,
	customer_id,
	ticket_type_id,
	booking_status="PENDING",
	ticket_status="PENDING",
	ticket_price=Decimal("120000.00"),
):
	booking = Booking(
		totalAmount=ticket_price,
		createdAt=datetime.now(),
		status=booking_status,
		customerId=customer_id,
	)
	db.session.add(booking)
	db.session.flush()
	booking_id = booking.id

	ticket = Ticket(
		id=str(uuid.uuid4()),
		qrCode="https://example.com/qr.png",
		createdAt=datetime.now(),
		checkedIn=None,
		price=ticket_price,
		ticketCode=f"TK{uuid.uuid4().hex[:8].upper()}",
		fullName="Ticket Holder",
		phoneNumber="0912345678",
		faceEmbedding=None,
		status=ticket_status,
		bookingId=booking.id,
		ticketTypeId=ticket_type_id,
		customerId=customer_id,
	)
	db.session.add(ticket)
	ticket_id = ticket.id
	db.session.commit()

	return booking_id, ticket_id


# ================= HELPER FUNCTIONS =================
def test_parse_positive_int():
	assert ticket_routes._parse_positive_int("5") == 5
	assert ticket_routes._parse_positive_int(10) == 10
	assert ticket_routes._parse_positive_int("0") is None
	assert ticket_routes._parse_positive_int("abc") is None


def test_normalize_phone_number():
	assert ticket_routes._normalize_phone_number(" 0912 345 678 ") == "0912345678"
	assert ticket_routes._normalize_phone_number(None) == ""


def test_build_and_extract_vnpay_txn_ref():
	txn_ref = ticket_routes._build_vnpay_txn_ref(123)

	assert txn_ref.startswith("BK123_")
	assert ticket_routes._extract_booking_id_from_txn_ref(txn_ref) == 123
	assert ticket_routes._extract_booking_id_from_txn_ref("321") == 321
	assert ticket_routes._extract_booking_id_from_txn_ref("   ") is None


def test_parse_vnpay_pay_date_and_to_vnpay_datetime():
	parsed = ticket_routes._parse_vnpay_pay_date("20260418124530")
	assert parsed is not None
	assert parsed.year == 2026
	assert ticket_routes._parse_vnpay_pay_date("20260418") is None

	dt = datetime(2026, 4, 18, 12, 45, 30)
	assert ticket_routes._to_vnpay_datetime(dt) == "20260418124530"
	assert ticket_routes._to_vnpay_datetime("20260418124530") == "20260418124530"
	assert ticket_routes._to_vnpay_datetime("not-a-date") == ""
	assert ticket_routes._to_vnpay_datetime(None) == ""


def test_extract_transaction_no():
	assert ticket_routes._extract_transaction_no("abc|trans-001") == "trans-001"
	assert ticket_routes._extract_transaction_no("trans-001") == "trans-001"
	assert ticket_routes._extract_transaction_no("") == ""


def test_parse_checkout_tickets_merges_same_ticket_type():
	payload = [
		{
			"ticketTypeId": 11,
			"quantity": 1,
			"holders": [
				{
					"fullName": " Nguyen Van A ",
					"phoneNumber": "0912 345 678",
					"faceEmbedding": "",
				}
			],
		},
		{
			"ticketTypeId": "11",
			"quantity": "1",
			"holders": [
				{
					"fullName": "Tran Thi B",
					"phoneNumber": "+849123456789",
					"faceEmbedding": "embedding-data",
				}
			],
		},
	]

	normalized, error = ticket_routes._parse_checkout_tickets(payload)

	assert error is None
	assert normalized is not None
	assert len(normalized) == 1
	assert normalized[0]["ticketTypeId"] == 11
	assert normalized[0]["quantity"] == 2
	assert len(normalized[0]["holders"]) == 2
	assert normalized[0]["holders"][0]["phoneNumber"] == "0912345678"


def test_parse_checkout_tickets_rejects_invalid_payload():
	normalized, error = ticket_routes._parse_checkout_tickets([])
	assert normalized is None
	assert error is not None

	normalized, error = ticket_routes._parse_checkout_tickets(
		[
			{
				"ticketTypeId": 1,
				"quantity": 2,
				"holders": [{"fullName": "Nguyen Van A", "phoneNumber": "0912345678"}],
			}
		]
	)
	assert normalized is None
	assert error is not None


def test_request_client_ip_prefers_forwarded_header(app):
	with app.test_request_context(
		"/events/1/checkout",
		headers={"X-Forwarded-For": "10.10.10.10, 192.168.1.1"},
		environ_base={"REMOTE_ADDR": "127.0.0.1"},
	):
		assert ticket_routes._request_client_ip() == "10.10.10.10"


def test_request_client_ip_falls_back_remote_addr(app):
	with app.test_request_context("/events/1/checkout", environ_base={"REMOTE_ADDR": "10.0.0.5"}):
		assert ticket_routes._request_client_ip() == "10.0.0.5"


# ================= CHECKOUT ROUTE =================
def test_checkout_event_tickets_requires_login(client):
	response = client.post("/events/1/checkout", json={"tickets": []})
	body = response.get_json()

	assert response.status_code == 401
	assert body["ok"] is False
	assert "redirectUrl" in body


def test_checkout_event_tickets_rejects_non_customer(app, client):
	with app.app_context():
		user_id = _new_user(make_customer=False)

	with client.session_transaction() as sess:
		sess["user_id"] = user_id

	response = client.post("/events/1/checkout", json={"tickets": []})

	assert response.status_code == 403
	assert response.get_json()["ok"] is False


def test_checkout_event_tickets_rejects_non_published_event(app, client):
	with app.app_context():
		customer_id = _new_user(make_customer=True)
		event_id, _ = _new_event_and_ticket_type(event_status="PENDING")

	with client.session_transaction() as sess:
		sess["user_id"] = customer_id

	response = client.post(f"/events/{event_id}/checkout", json={"tickets": []})

	assert response.status_code == 400
	assert response.get_json()["ok"] is False


def test_checkout_event_tickets_success_creates_booking_and_tickets(app, client):
	with app.app_context():
		customer_id = _new_user(make_customer=True)
		event_id, ticket_type_id = _new_event_and_ticket_type(
			event_status="PUBLISHED",
			quantity=5,
			price=Decimal("150000.00"),
			has_face_reg=True,
		)

	with client.session_transaction() as sess:
		sess["user_id"] = customer_id

	payload = {
		"tickets": [
			{
				"ticketTypeId": ticket_type_id,
				"quantity": 2,
				"holders": [
					{"fullName": "Nguyen Van A", "phoneNumber": "0912345678"},
					{"fullName": "Tran Thi B", "phoneNumber": "0912345679"},
				],
			}
		]
	}

	with patch(
		"app.routes.ticket_routes.build_payment_url",
		return_value={"payment_url": "https://payment.local/checkout"},
	) as mock_build_payment:
		response = client.post(f"/events/{event_id}/checkout", json=payload)

	assert response.status_code == 200
	body = response.get_json()
	assert body["ok"] is True
	assert body["paymentUrl"] == "https://payment.local/checkout"
	mock_build_payment.assert_called_once()

	with app.app_context():
		booking = db.session.get(Booking, body["bookingId"])
		assert booking is not None
		assert booking.status == "PENDING"
		assert float(booking.totalAmount) == 300000.0

		booking_tickets = Ticket.query.filter(Ticket.bookingId == booking.id).all()
		assert len(booking_tickets) == 2
		assert all(ticket.status == "PENDING" for ticket in booking_tickets)

		reloaded_ticket_type = db.session.get(TicketType, ticket_type_id)
		assert reloaded_ticket_type.quantity == 3


# ================= PAYMENT RETURN ROUTE =================
def test_payment_return_redirects_home_when_booking_id_missing(client):
	with patch(
		"app.routes.ticket_routes.verify_return_data",
		return_value={
			"txn_ref": "",
			"is_valid_signature": False,
			"is_success": False,
		},
	):
		response = client.get("/payment_return")

	assert response.status_code == 302
	assert response.headers["Location"].endswith("/")


def test_payment_return_success_updates_booking_and_ticket_status(app, client):
	with app.app_context():
		customer_id = _new_user(make_customer=True)
		event_id, ticket_type_id = _new_event_and_ticket_type(
			event_status="PUBLISHED",
			quantity=0,
			price=Decimal("120000.00"),
		)
		booking_id, _ = _new_booking_with_ticket(
			customer_id=customer_id,
			ticket_type_id=ticket_type_id,
			booking_status="PENDING",
			ticket_status="PENDING",
			ticket_price=Decimal("120000.00"),
		)

	txn_ref = f"BK{booking_id}_20260418120000000"
	verify_payload = {
		"txn_ref": txn_ref,
		"transaction_no": "VNP-TRANS-001",
		"pay_date": "20260418153030",
		"is_valid_signature": True,
		"is_success": True,
		"amount": 120000,
	}

	with patch("app.routes.ticket_routes.verify_return_data", return_value=verify_payload), patch(
		"app.routes.ticket_routes.send_ticket_email_by_booking"
	) as mock_send_email:
		response = client.get("/payment_return")

	assert response.status_code == 302
	assert "/orders/tickets" in response.headers["Location"]
	mock_send_email.assert_called_once_with(booking_id)

	with app.app_context():
		reloaded_booking = db.session.get(Booking, booking_id)
		assert reloaded_booking.status == "SUCCESS"

		payment = Payment.query.filter(Payment.bookingId == booking_id).one()
		assert payment.status == "SUCCESS"
		assert payment.transactionID == "VNP-TRANS-001"
		assert payment.vnpTxnRef == txn_ref
		assert payment.vnpPayDate.strftime("%Y%m%d%H%M%S") == "20260418153030"

		tickets = Ticket.query.filter(Ticket.bookingId == booking_id).all()
		assert len(tickets) == 1
		assert all(ticket.status == "VALID" for ticket in tickets)

		related_event = db.session.get(Event, event_id)
		assert related_event is not None


def test_payment_return_failed_third_attempt_marks_booking_failed(app, client):
	with app.app_context():
		customer_id = _new_user(make_customer=True)
		event_id, ticket_type_id = _new_event_and_ticket_type(
			event_status="PUBLISHED",
			quantity=0,
			price=Decimal("90000.00"),
		)
		booking_id, ticket_id = _new_booking_with_ticket(
			customer_id=customer_id,
			ticket_type_id=ticket_type_id,
			booking_status="PENDING",
			ticket_status="PENDING",
			ticket_price=Decimal("90000.00"),
		)

		db.session.add_all(
			[
				Payment(
					amount=Decimal("90000.00"),
					transactionID="FAILED-ATTEMPT-1",
					status="FAILED",
					bookingId=booking_id,
				),
				Payment(
					amount=Decimal("90000.00"),
					transactionID="FAILED-ATTEMPT-2",
					status="FAILED",
					bookingId=booking_id,
				),
			]
		)
		db.session.commit()

	with patch(
		"app.routes.ticket_routes.verify_return_data",
		return_value={
			"txn_ref": f"BK{booking_id}_RETRY3",
			"transaction_no": "",
			"pay_date": "",
			"is_valid_signature": True,
			"is_success": False,
			"amount": 90000,
		},
	):
		response = client.get("/payment_return")

	assert response.status_code == 302
	assert f"/events/{event_id}" in response.headers["Location"]

	with app.app_context():
		reloaded_booking = db.session.get(Booking, booking_id)
		reloaded_ticket = db.session.get(Ticket, ticket_id)
		reloaded_ticket_type = db.session.get(TicketType, ticket_type_id)

		assert reloaded_booking.status == "FAILED"
		assert reloaded_ticket.status == "CANCELLED"
		assert reloaded_ticket_type.quantity == 1

		failed_count = (
			Payment.query
			.filter(
				Payment.bookingId == booking_id,
				Payment.status == "FAILED",
			)
			.count()
		)
		assert failed_count == 3


# ================= REFUND ROUTES =================
def test_cancel_booking_refund_requires_login(client):
	response = client.post("/bookings/1/cancel-refund")

	assert response.status_code == 302
	assert "/login" in response.headers["Location"]


def test_cancel_booking_refund_success_cancels_valid_tickets(app, client):
	with app.app_context():
		customer_id = _new_user(make_customer=True)
		_, ticket_type_id = _new_event_and_ticket_type(
			event_status="PUBLISHED",
			quantity=0,
			price=Decimal("50000.00"),
		)
		booking_id, ticket_id = _new_booking_with_ticket(
			customer_id=customer_id,
			ticket_type_id=ticket_type_id,
			booking_status="SUCCESS",
			ticket_status="VALID",
			ticket_price=Decimal("50000.00"),
		)

		payment = Payment(
			amount=Decimal("50000.00"),
			transactionID="VNP-TRANS-REFUND-001",
			vnpTxnRef=f"BK{booking_id}_TXN",
			vnpPayDate=datetime(2026, 4, 18, 9, 30, 0),
			status="SUCCESS",
			bookingId=booking_id,
		)
		db.session.add(payment)
		db.session.commit()

	with client.session_transaction() as sess:
		sess["user_id"] = customer_id

	with patch(
		"app.routes.ticket_routes.request_refund",
		return_value={"is_success": True, "message": "refund success"},
	) as mock_request_refund:
		response = client.post(f"/bookings/{booking_id}/cancel-refund")

	assert response.status_code == 302
	assert f"/orders/booking/{booking_id}" in response.headers["Location"]
	mock_request_refund.assert_called_once()

	with app.app_context():
		reloaded_ticket = db.session.get(Ticket, ticket_id)
		reloaded_ticket_type = db.session.get(TicketType, ticket_type_id)

		assert reloaded_ticket.status == "CANCELLED"
		assert reloaded_ticket_type.quantity == 1
