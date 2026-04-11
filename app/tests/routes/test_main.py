from app import db
from app.models.event import Event
from app.models.event_type import EventType
from app.models.ticket_type import TicketType

def test_homepage_route(app):
    client = app.test_client()

    with app.app_context():
        et = EventType(name="Music", status=True)
        db.session.add(et)
        db.session.flush()

        e1 = Event(title="Rock Night", eventTypeId=et.id)
        db.session.add(e1)
        db.session.commit()

    res = client.get("/")
    assert res.status_code == 200
    assert b"Rock Night" in res.data

def test_homepage_filter_by_event_type(app):
    client = app.test_client()

    with app.app_context():
        et1 = EventType(name="Music", status=True)
        et2 = EventType(name="Sport", status=True)
        db.session.add_all([et1, et2])
        db.session.flush()

        e1 = Event(title="Rock", eventTypeId=et1.id)
        e2 = Event(title="Football", eventTypeId=et2.id)
        db.session.add_all([e1, e2])
        db.session.commit()

        res = client.get(f"/?eventTypeId={et1.id}")

        assert res.status_code == 200
        assert b"Rock" in res.data
        assert b"Football" not in res.data

def test_event_detail_route(app):
    client = app.test_client()

    with app.app_context():
        et = EventType(name="Music", status=True)
        db.session.add(et); db.session.flush()

        e = Event(title="Rock Night", eventTypeId=et.id)
        db.session.add(e)
        db.session.commit()

        res = client.get(f"/events/{e.id}")

        assert res.status_code == 200
        assert b"Rock Night" in res.data

def test_event_types_loaded(app):
    client = app.test_client()

    with app.app_context():
        et = EventType(name="Music", status=True)
        db.session.add(et)
        db.session.commit()

        res = client.get("/")

        assert res.status_code == 200
        assert b"Music" in res.data