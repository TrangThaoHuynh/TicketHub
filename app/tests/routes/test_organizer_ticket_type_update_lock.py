from datetime import datetime
from decimal import Decimal

from app import db
from app.models.enums import EventStatus, OrganizerStatus
from app.models.event import Event
from app.models.event_type import EventType
from app.models.ticket_type import TicketType
from app.models.user import Organizer, User


def test_organizer_update_ticket_type_rejects_when_event_is_published(app):
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
        db.session.flush()

        sale_start = datetime(2026, 4, 1, 0, 0)
        sale_end = datetime(2026, 5, 1, 0, 0)

        ticket_type = TicketType(
            name="VIP",
            description="",
            price=Decimal("100000"),
            quantity=100,
            saleStart=sale_start,
            saleEnd=sale_end,
            eventId=event.id,
        )
        db.session.add(ticket_type)
        db.session.commit()

        event_id = event.id
        ticket_type_id = ticket_type.id
        organizer_id = organizer.id

    with client.session_transaction() as sess:
        sess["user_id"] = organizer_id

    res = client.post(
        f"/organizer/events/{event_id}/ticket-types/update",
        json={
            "ticketTypeId": ticket_type_id,
            "price": "200000",
            "remainingQuantity": 50,
            "saleStart": "2026-04-01T00:00",
            "saleEnd": "2026-05-01T00:00",
            "description": "changed",
        },
    )

    assert res.status_code == 400
    data = res.get_json() or {}
    assert "PENDING" in (data.get("message") or "")

    with app.app_context():
        reloaded = db.session.get(TicketType, ticket_type_id)
        assert Decimal(reloaded.price or 0) == Decimal("100000")
