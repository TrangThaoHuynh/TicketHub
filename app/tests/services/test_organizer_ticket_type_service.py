from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy.pool import StaticPool

from app import create_app, db
from app.config import Config
from app.models.enums import EventStatus, OrganizerStatus
from app.models.event import Event
from app.models.event_type import EventType
from app.models.ticket_type import TicketType
from app.models.user import Organizer, User
from app.services.ticket_type_service import (
	create_ticket_type,
	get_ticket_type_by_event,
	update_ticket_type,
)


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

	app = create_app()
	app.config.update(TESTING=True)

	with app.app_context():
		db.create_all()

		for status in ("PENDING", "PUBLISHED", "FINISHED", "CANCELLED"):
			if db.session.get(EventStatus, status) is None:
				db.session.add(EventStatus(status=status))

		if db.session.get(OrganizerStatus, "PENDING") is None:
			db.session.add(OrganizerStatus(status="PENDING"))

		db.session.commit()

		yield app

		db.session.remove()
		db.drop_all()


def _create_organizer(index=1):
	user = User(
		name=f"Organizer {index}",
		email=f"organizer.ticket.{index}@example.com",
		username=f"organizer_ticket_{index}",
		password="Strong@123",
		createdAt=datetime.now(),
	)
	db.session.add(user)
	db.session.flush()

	organizer = Organizer(id=user.id, status="PENDING")
	db.session.add(organizer)
	db.session.commit()
	return organizer


def _create_event_type(index=1, status=True):
	event_type = EventType(name=f"Event Type {index}", status=status)
	db.session.add(event_type)
	db.session.commit()
	return event_type


def _create_event(index=1):
	organizer = _create_organizer(index=index)
	event_type = _create_event_type(index=index)

	event = Event(
		title=f"Event {index}",
		location="HCM",
		startTime=datetime(2026, 6, 1, 19, 0),
		endTime=datetime(2026, 6, 1, 21, 0),
		status="PENDING",
		eventTypeId=event_type.id,
		organizerId=organizer.id,
	)
	db.session.add(event)
	db.session.commit()
	return event


# ================= CREATE TICKET TYPE =================
def test_create_ticket_type_persists_with_commit_true(app):
	with app.app_context():
		event = _create_event(index=1)

		ticket = create_ticket_type(
			{
				"name": "Standard",
				"description": "Standard area",
				"price": Decimal("150000"),
				"quantity": 100,
				"saleStart": datetime(2026, 5, 1, 8, 0),
				"saleEnd": datetime(2026, 5, 30, 23, 59),
				"eventId": event.id,
			}
		)

		assert ticket.id is not None

		saved_ticket = db.session.get(TicketType, ticket.id)
		assert saved_ticket is not None
		assert saved_ticket.name == "Standard"
		assert float(saved_ticket.price) == 150000.0
		assert saved_ticket.quantity == 100
		assert saved_ticket.eventId == event.id


def test_create_ticket_type_supports_commit_false(app):
	with app.app_context():
		event = _create_event(index=2)

		ticket = create_ticket_type(
			{
				"name": "VIP",
				"description": "Front seat",
				"price": Decimal("300000"),
				"quantity": 50,
				"saleStart": datetime(2026, 5, 1, 8, 0),
				"saleEnd": datetime(2026, 5, 30, 23, 59),
				"eventId": event.id,
			},
			commit=False,
		)

		assert ticket in db.session.new
		assert ticket.id is None

		db.session.flush()
		assert ticket.id is not None


# ================= GET TICKET TYPE =================
def test_get_ticket_type_by_event_returns_matching_ticket(app):
	with app.app_context():
		event = _create_event(index=3)
		ticket = create_ticket_type(
			{
				"name": "Standard",
				"description": "Area A",
				"price": Decimal("120000"),
				"quantity": 200,
				"saleStart": datetime(2026, 5, 1, 8, 0),
				"saleEnd": datetime(2026, 5, 30, 23, 59),
				"eventId": event.id,
			}
		)

		loaded_ticket = get_ticket_type_by_event(ticket.id, event.id)

		assert loaded_ticket is not None
		assert loaded_ticket.id == ticket.id


def test_get_ticket_type_by_event_returns_none_for_wrong_event(app):
	with app.app_context():
		first_event = _create_event(index=4)
		second_event = _create_event(index=5)

		ticket = create_ticket_type(
			{
				"name": "Zone B",
				"description": "Area B",
				"price": Decimal("100000"),
				"quantity": 80,
				"saleStart": datetime(2026, 5, 1, 8, 0),
				"saleEnd": datetime(2026, 5, 30, 23, 59),
				"eventId": first_event.id,
			}
		)

		loaded_ticket = get_ticket_type_by_event(ticket.id, second_event.id)

		assert loaded_ticket is None


# ================= UPDATE TICKET TYPE =================
def test_update_ticket_type_returns_none_when_ticket_missing(app):
	with app.app_context():
		result = update_ticket_type(None, {"name": "New Name"})
		assert result is None


def test_update_ticket_type_updates_fields_and_commits(app):
	with app.app_context():
		first_event = _create_event(index=6)
		second_event = _create_event(index=7)

		ticket = create_ticket_type(
			{
				"name": "Starter",
				"description": "Starter area",
				"price": Decimal("90000"),
				"quantity": 120,
				"saleStart": datetime(2026, 5, 1, 8, 0),
				"saleEnd": datetime(2026, 5, 30, 23, 59),
				"eventId": first_event.id,
			}
		)

		update_ticket_type(
			ticket,
			{
				"name": "Premium",
				"description": "Premium area",
				"price": Decimal("210000"),
				"quantity": 75,
				"saleStart": datetime(2026, 5, 5, 9, 0),
				"saleEnd": datetime(2026, 5, 29, 22, 0),
				"eventId": second_event.id,
			},
		)

		reloaded = db.session.get(TicketType, ticket.id)
		assert reloaded is not None
		assert reloaded.name == "Premium"
		assert reloaded.description == "Premium area"
		assert float(reloaded.price) == 210000.0
		assert reloaded.quantity == 75
		assert reloaded.eventId == second_event.id


def test_update_ticket_type_preserves_unspecified_fields(app):
	with app.app_context():
		event = _create_event(index=8)

		original_sale_start = datetime(2026, 5, 1, 8, 0)
		original_sale_end = datetime(2026, 5, 30, 23, 59)
		ticket = create_ticket_type(
			{
				"name": "Basic",
				"description": "Basic area",
				"price": Decimal("70000"),
				"quantity": 90,
				"saleStart": original_sale_start,
				"saleEnd": original_sale_end,
				"eventId": event.id,
			}
		)

		update_ticket_type(ticket, {"description": "Updated description"})

		reloaded = db.session.get(TicketType, ticket.id)
		assert reloaded is not None
		assert reloaded.name == "Basic"
		assert reloaded.description == "Updated description"
		assert float(reloaded.price) == 70000.0
		assert reloaded.quantity == 90
		assert reloaded.saleStart == original_sale_start
		assert reloaded.saleEnd == original_sale_end
		assert reloaded.eventId == event.id


def test_update_ticket_type_supports_commit_false(app):
	with app.app_context():
		event = _create_event(index=9)

		ticket = create_ticket_type(
			{
				"name": "No Commit",
				"description": "Before rollback",
				"price": Decimal("65000"),
				"quantity": 70,
				"saleStart": datetime(2026, 5, 1, 8, 0),
				"saleEnd": datetime(2026, 5, 30, 23, 59),
				"eventId": event.id,
			}
		)
		ticket_id = ticket.id

		update_ticket_type(ticket, {"name": "Changed In Session"}, commit=False)

		assert ticket in db.session.dirty
		assert ticket.name == "Changed In Session"

		db.session.rollback()
		reloaded = db.session.get(TicketType, ticket_id)
		assert reloaded is not None
		assert reloaded.name == "No Commit"
