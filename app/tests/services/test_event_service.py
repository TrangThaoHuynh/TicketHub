import pytest
from datetime import datetime
from decimal import Decimal
from sqlalchemy.pool import StaticPool

from app import create_app, db
from app.models.event import Event
from app.models.event_type import EventType
from app.models.ticket_type import TicketType
from app.services.event_service import get_home_events

@pytest.fixture()
def app():
    app = create_app()
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite://",  
        SQLALCHEMY_ENGINE_OPTIONS={
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool,
        },
    )
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

def test_get_home_events_filters(app):
    with app.app_context():
        et = EventType(name="Music", status=True)
        db.session.add(et); db.session.flush()

        e1 = Event(title="Rock Night", location="Hanoi", startTime=datetime(2026, 4, 10), eventTypeId=et.id)
        e2 = Event(title="Food Fair", location="Hanoi", startTime=datetime(2026, 4, 11), eventTypeId=et.id)
        db.session.add_all([e1, e2]); db.session.flush()

        db.session.add_all([
            TicketType(name="Std", price=Decimal("50.00"), eventId=e1.id),
            TicketType(name="VIP", price=Decimal("120.00"), eventId=e1.id),
        ])
        db.session.commit()

        events = get_home_events(keyword="rock")
        assert [e.title for e in events] == ["Rock Night"]
        assert str(events[0].min_price) in ("50.00", "50")  

def test_filter_by_location(app):
    with app.app_context():
        et = EventType(name="Music", status=True)
        db.session.add(et); db.session.flush()

        e1 = Event(title="A", location="HCM", eventTypeId=et.id)
        e2 = Event(title="B", location="HN", eventTypeId=et.id)
        db.session.add_all([e1, e2])
        db.session.commit()

        events = get_home_events(location="HN")

        assert len(events) == 1

def test_filter_by_date(app):
    with app.app_context():
        et = EventType(name="Music", status=True)
        db.session.add(et); db.session.flush()

        e1 = Event(title="Old", startTime=datetime(2026, 4, 10), eventTypeId=et.id)
        e2 = Event(title="New", startTime=datetime(2026, 4, 20), eventTypeId=et.id)
        db.session.add_all([e1, e2])
        db.session.commit()

        events = get_home_events(start_date="2026-04-15")

        assert len(events) == 1

def test_filter_by_price(app):
    with app.app_context():
        et = EventType(name="Music", status=True)
        db.session.add(et); db.session.flush()

        e1 = Event(title="Cheap", eventTypeId=et.id)
        e2 = Event(title="Expensive", eventTypeId=et.id)
        db.session.add_all([e1, e2]); db.session.flush()

        db.session.add_all([
            TicketType(price=50, eventId=e1.id),
            TicketType(price=200, eventId=e2.id),
        ])
        db.session.commit()

        events = get_home_events(price_min=100)

        assert len(events) == 1