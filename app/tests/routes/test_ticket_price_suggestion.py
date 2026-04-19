from app import db
from app.models.enums import EventStatus, OrganizerStatus
from app.models.event import Event
from app.models.event_type import EventType
from app.models.user import Organizer, User


def test_suggest_price_requires_organizer_session(app):
    client = app.test_client()
    res = client.post(
        "/api/organizer/ticket-types/suggest-price",
        json={
            "event": {"eventTypeId": 1},
            "tickets": [{"ticketTypeName": "VIP", "ticketQuantity": 100}],
        },
    )
    assert res.status_code == 401


def test_suggest_price_returns_suggestions(app):
    client = app.test_client()

    et_id = None

    with app.app_context():
        if db.session.get(EventStatus, "PENDING") is None:
            db.session.add(EventStatus(status="PENDING"))
        if db.session.get(EventStatus, "PUBLISHED") is None:
            db.session.add(EventStatus(status="PUBLISHED"))
        if db.session.get(OrganizerStatus, "PENDING") is None:
            db.session.add(OrganizerStatus(status="PENDING"))
        if db.session.get(OrganizerStatus, "APPROVED") is None:
            db.session.add(OrganizerStatus(status="APPROVED"))

        et = EventType(name="Music", status=True)
        db.session.add(et)
        db.session.flush()
        et_id = et.id

        user = User(name="Org")
        db.session.add(user)
        db.session.flush()

        organizer = Organizer(id=user.id, status="APPROVED")
        db.session.add(organizer)
        db.session.commit()

        organizer_id = organizer.id

    with client.session_transaction() as sess:
        sess["user_id"] = organizer_id

    res = client.post(
        "/api/organizer/ticket-types/suggest-price",
        json={
            "event": {
                "eventTypeId": et_id,
                "location": "HCM",
                "startTime": "2026-05-01T19:00",
                "endTime": "2026-05-01T22:00",
                "hasFaceReg": True,
                "limitQuantity": 2,
            },
            "tickets": [
                {
                    "ticketTypeName": "VIP",
                    "ticketQuantity": 100,
                    "saleStart": "2026-04-01T00:00",
                    "saleEnd": "2026-05-01T18:00",
                }
            ],
        },
    )

    assert res.status_code == 200
    data = res.get_json()
    assert data["eventTypeId"] == et_id
    assert isinstance(data["suggestions"], list)
    assert len(data["suggestions"]) == 1
    assert data["suggestions"][0]["ticketTypeName"] == "VIP"
    assert isinstance(data["suggestions"][0]["suggestedPrice"], int)


def test_suggest_price_rejects_published_event_when_event_id_is_provided(app):
    client = app.test_client()

    with app.app_context():
        if db.session.get(EventStatus, "PENDING") is None:
            db.session.add(EventStatus(status="PENDING"))
        if db.session.get(EventStatus, "PUBLISHED") is None:
            db.session.add(EventStatus(status="PUBLISHED"))
        if db.session.get(OrganizerStatus, "PENDING") is None:
            db.session.add(OrganizerStatus(status="PENDING"))
        if db.session.get(OrganizerStatus, "APPROVED") is None:
            db.session.add(OrganizerStatus(status="APPROVED"))

        et = EventType(name="Music", status=True)
        db.session.add(et)
        db.session.flush()

        user = User(name="Org")
        db.session.add(user)
        db.session.flush()

        organizer = Organizer(id=user.id, status="APPROVED")
        db.session.add(organizer)
        db.session.flush()

        event = Event(
            title="Published Event",
            eventTypeId=et.id,
            organizerId=organizer.id,
            status="PUBLISHED",
        )
        db.session.add(event)
        db.session.commit()

        organizer_id = organizer.id

        event_id = event.id
        et_id = et.id

    with client.session_transaction() as sess:
        sess["user_id"] = organizer_id

    res = client.post(
        "/api/organizer/ticket-types/suggest-price",
        json={
            "event": {
                "eventId": event_id,
                "eventTypeId": et_id,
                "location": "HCM",
                "startTime": "2026-05-01T19:00",
                "endTime": "2026-05-01T22:00",
                "hasFaceReg": True,
                "limitQuantity": 2,
            },
            "tickets": [
                {
                    "ticketTypeName": "VIP",
                    "ticketQuantity": 100,
                    "saleStart": "2026-04-01T00:00",
                    "saleEnd": "2026-05-01T18:00",
                }
            ],
        },
    )

    assert res.status_code == 400
    data = res.get_json() or {}
    assert "PENDING" in (data.get("message") or "")
