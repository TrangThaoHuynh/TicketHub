from datetime import datetime, timedelta

import pytest
from sqlalchemy.pool import StaticPool

from app import create_app, db
from app.config import Config
from app.models.enums import EventStatus, OrganizerStatus
from app.models.event import Event
from app.models.event_type import EventType
from app.models.user import Organizer, User
from app.services.event_service import (
	create_event,
	get_event_by_id,
	get_event_types,
	sync_expired_events_to_finished,
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
		email=f"organizer{index}@example.com",
		username=f"organizer_{index}",
		password="Strong@123",
		createdAt=datetime.now(),
	)
	db.session.add(user)
	db.session.flush()

	organizer = Organizer(id=user.id, status="PENDING")
	db.session.add(organizer)
	db.session.commit()
	return organizer


def _create_event_type(name="Music", status=True):
	event_type = EventType(name=name, status=status)
	db.session.add(event_type)
	db.session.commit()
	return event_type


def _build_event_payload(event_type_id, organizer_id, status="PENDING"):
	start_time = datetime(2026, 5, 1, 19, 0)
	end_time = datetime(2026, 5, 1, 21, 0)
	return {
		"title": "Organizer Event",
		"image": "https://example.com/event.jpg",
		"description": "Event description",
		"location": "HCM",
		"startTime": start_time,
		"endTime": end_time,
		"publishedAt": None,
		"hasFaceReg": True,
		"limitQuantity": 2,
		"status": status,
		"eventTypeId": event_type_id,
		"organizerId": organizer_id,
	}


# ================= GET EVENT TYPES =================
def test_get_event_types_returns_only_active_by_default(app):
	with app.app_context():
		db.session.add_all(
			[
				EventType(name="Zeta", status=True),
				EventType(name="Alpha", status=True),
				EventType(name="Hidden", status=False),
			]
		)
		db.session.commit()

		event_types = get_event_types()

		assert [event_type.name for event_type in event_types] == ["Alpha", "Zeta"]


def test_get_event_types_supports_returning_all_types(app):
	with app.app_context():
		db.session.add_all(
			[
				EventType(name="Zeta", status=True),
				EventType(name="Alpha", status=True),
				EventType(name="Hidden", status=False),
			]
		)
		db.session.commit()

		event_types = get_event_types(only_active=False)

		assert [event_type.name for event_type in event_types] == ["Alpha", "Hidden", "Zeta"]


# ================= CREATE EVENT =================
def test_create_event_persists_with_published_status(app):
	with app.app_context():
		organizer = _create_organizer(index=1)
		event_type = _create_event_type(name="Concert")

		payload = _build_event_payload(event_type.id, organizer.id, status="PUBLISHED")
		event = create_event(payload)

		assert event.id is not None

		saved_event = db.session.get(Event, event.id)
		assert saved_event is not None
		assert saved_event.status == "PUBLISHED"
		assert saved_event.organizerId == organizer.id
		assert saved_event.eventTypeId == event_type.id
		assert saved_event.createdAt is not None


def test_create_event_defaults_to_pending_when_status_invalid(app):
	with app.app_context():
		organizer = _create_organizer(index=2)
		event_type = _create_event_type(name="Workshop")

		payload = _build_event_payload(event_type.id, organizer.id, status="INVALID_STATUS")
		event = create_event(payload)

		assert event.status == "PENDING"


def test_create_event_supports_commit_false_for_route_transaction(app):
	with app.app_context():
		organizer = _create_organizer(index=3)
		event_type = _create_event_type(name="Expo")

		payload = _build_event_payload(event_type.id, organizer.id, status="PENDING")
		event = create_event(payload, commit=False)

		assert event in db.session.new
		assert event.id is None

		db.session.flush()
		assert event.id is not None


def test_create_event_falls_back_to_first_status_when_pending_missing(app):
	with app.app_context():
		pending_status = db.session.get(EventStatus, "PENDING")
		db.session.delete(pending_status)
		db.session.commit()

		organizer = _create_organizer(index=4)
		event_type = _create_event_type(name="Festival")

		first_status = EventStatus.query.order_by(EventStatus.status.asc()).first()
		payload = _build_event_payload(event_type.id, organizer.id, status="INVALID_STATUS")
		event = create_event(payload)

		assert first_status is not None
		assert event.status == first_status.status


# ================= GET EVENT BY ID / SYNC STATUS =================
def test_get_event_by_id_syncs_expired_published_event_to_finished(app):
	with app.app_context():
		organizer = _create_organizer(index=5)
		event_type = _create_event_type(name="Talk")

		expired_event = Event(
			title="Expired Event",
			location="HCM",
			startTime=datetime.now() - timedelta(days=2),
			endTime=datetime.now() - timedelta(days=1),
			status="PUBLISHED",
			eventTypeId=event_type.id,
			organizerId=organizer.id,
		)
		db.session.add(expired_event)
		db.session.commit()

		event_id = expired_event.id
		db.session.expunge_all()

		loaded_event = get_event_by_id(event_id)

		assert loaded_event is not None
		assert loaded_event.status == "FINISHED"


def test_get_event_by_id_only_syncs_requested_event_id(app):
	with app.app_context():
		organizer = _create_organizer(index=6)
		event_type = _create_event_type(name="Conference")

		first_event = Event(
			title="Expired 1",
			location="HCM",
			startTime=datetime.now() - timedelta(days=3),
			endTime=datetime.now() - timedelta(days=2),
			status="PUBLISHED",
			eventTypeId=event_type.id,
			organizerId=organizer.id,
		)
		second_event = Event(
			title="Expired 2",
			location="HCM",
			startTime=datetime.now() - timedelta(days=3),
			endTime=datetime.now() - timedelta(days=2),
			status="PUBLISHED",
			eventTypeId=event_type.id,
			organizerId=organizer.id,
		)
		db.session.add_all([first_event, second_event])
		db.session.commit()

		first_event_id = first_event.id
		second_event_id = second_event.id
		db.session.expunge_all()

		loaded_event = get_event_by_id(first_event_id)
		untouched_event = db.session.get(Event, second_event_id)

		assert loaded_event is not None
		assert loaded_event.status == "FINISHED"
		assert untouched_event is not None
		assert untouched_event.status == "PUBLISHED"


def test_sync_expired_events_to_finished_returns_zero_when_finished_status_missing(app):
	with app.app_context():
		finished_status = db.session.get(EventStatus, "FINISHED")
		db.session.delete(finished_status)
		db.session.commit()

		organizer = _create_organizer(index=7)
		event_type = _create_event_type(name="Seminar")

		event = Event(
			title="Should Stay Published",
			location="HCM",
			startTime=datetime.now() - timedelta(days=3),
			endTime=datetime.now() - timedelta(days=2),
			status="PUBLISHED",
			eventTypeId=event_type.id,
			organizerId=organizer.id,
		)
		db.session.add(event)
		db.session.commit()

		updated_count = sync_expired_events_to_finished()
		reloaded_event = db.session.get(Event, event.id)

		assert updated_count == 0
		assert reloaded_event is not None
		assert reloaded_event.status == "PUBLISHED"
