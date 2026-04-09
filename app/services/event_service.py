from ..models.event import Event
from .. import db

#lấy tất cả sự kiện
def get_events():
    return Event.query.all()
#lấy theo id
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