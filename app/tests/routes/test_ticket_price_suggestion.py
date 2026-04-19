from app import db
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
        et = EventType(name="Music", status=True)
        db.session.add(et)
        db.session.flush()
        et_id = et.id

        user = User(id=1, name="Org")
        db.session.add(user)
        db.session.flush()

        organizer = Organizer(id=user.id, status="APPROVED")
        db.session.add(organizer)
        db.session.commit()

    with client.session_transaction() as sess:
        sess["user_id"] = 1

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
