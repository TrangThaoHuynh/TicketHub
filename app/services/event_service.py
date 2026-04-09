from ..models.event import Event
from ..models.event_type import EventType
from ..models.ticket_type import TicketType
from .. import db
from sqlalchemy import func

#lấy tất cả sự kiện
def get_events():
    return Event.query.all()
  
def get_event_types(only_active: bool = True):
    query = EventType.query
    if only_active:
        query = query.filter(EventType.status.is_(True))
    return query.order_by(EventType.name.asc()).all()


def get_home_events(keyword=None, event_type_id=None):
    min_price_subq = (
        db.session.query(
            TicketType.eventId.label("event_id"),
            func.min(TicketType.price).label("min_price"),
        )
        .group_by(TicketType.eventId)
        .subquery()
    )

    query = (
        db.session.query(Event, min_price_subq.c.min_price)
        .outerjoin(min_price_subq, min_price_subq.c.event_id == Event.id)
        .order_by(Event.startTime.is_(None).asc(), Event.startTime.asc(), Event.id.desc())
    )

    if keyword:
        query = query.filter(Event.title.ilike(f"%{keyword}%"))

    if event_type_id:
        try:
            query = query.filter(Event.eventTypeId == int(event_type_id))
        except (TypeError, ValueError):
            pass

    rows = query.all()
    events = []
    for event, min_price in rows:
        setattr(event, "min_price", min_price)
        events.append(event)
    return events
  
def get_event_by_id(event_id):
    return Event.query.get(event_id)

def create_event(data):
    event = Event(
        title=data.get("title"),
        location=data.get("location"),
        status=data.get("status"),
        eventTypeId=data.get("eventTypeId"),
        organizerId=data.get("organizerId")
    )

    db.session.add(event)
    db.session.commit()

    return event