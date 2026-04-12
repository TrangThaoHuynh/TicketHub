from ..models.event import Event
from ..models.event_type import EventType
from ..models.ticket_type import TicketType
from ..models.enums import EventStatus
from .. import db
from sqlalchemy import func, or_
from datetime import datetime, time

#lấy tất cả sự kiện
def get_events():
    sync_expired_events_to_finished()
    return Event.query.all()
  
def get_event_types(only_active: bool = True):
    query = EventType.query
    if only_active:
        query = query.filter(EventType.status.is_(True))
    return query.order_by(EventType.name.asc()).all()


def _resolve_finished_status_for_db():
    finished_status = db.session.get(EventStatus, "FINISHED")
    if finished_status:
        return finished_status.status
    return None


def sync_expired_events_to_finished(now_time=None, event_id=None):
    target_finished_status = _resolve_finished_status_for_db()
    if target_finished_status is None:
        return 0

    reference_time = now_time or datetime.now()

    query = Event.query.filter(
        Event.endTime.is_not(None),
        Event.endTime < reference_time,
        func.upper(Event.status) == "PUBLISHED",
    )

    if event_id is not None:
        query = query.filter(Event.id == event_id)

    try:
        updated_count = query.update({Event.status: target_finished_status}, synchronize_session=False)
        if updated_count > 0:
            db.session.commit()
        return updated_count
    except Exception:
        db.session.rollback()
        return 0


def get_home_events(
    keyword=None,
    event_type_id=None,
    start_date=None,
    end_date=None,
    location=None,
    price_min=None,
    price_max=None,
    organizer_id=None,
):
    sync_expired_events_to_finished()

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

    if location:
        query = query.filter(Event.location.ilike(f"%{location}%"))

    if start_date:
        try:
            start_dt = datetime.combine(datetime.strptime(start_date, "%Y-%m-%d").date(), time.min)
            query = query.filter(Event.startTime.is_not(None)).filter(Event.startTime >= start_dt)
        except (TypeError, ValueError):
            pass

    if end_date:
        try:
            end_dt = datetime.combine(datetime.strptime(end_date, "%Y-%m-%d").date(), time.max)
            query = query.filter(Event.startTime.is_not(None)).filter(Event.startTime <= end_dt)
        except (TypeError, ValueError):
            pass

    if price_min not in (None, "") or price_max not in (None, ""):
        try:
            min_val = float(price_min) if price_min not in (None, "") else None
        except (TypeError, ValueError):
            min_val = None

        try:
            max_val = float(price_max) if price_max not in (None, "") else None
        except (TypeError, ValueError):
            max_val = None

        if min_val is not None:
            query = query.filter(min_price_subq.c.min_price.is_not(None)).filter(min_price_subq.c.min_price >= min_val)
        if max_val is not None:
            query = query.filter(min_price_subq.c.min_price.is_not(None)).filter(min_price_subq.c.min_price <= max_val)

    if organizer_id:
        try:
            query = query.filter(Event.organizerId == int(organizer_id))
        except (TypeError, ValueError):
            pass
    else:
        query = query.filter(
            or_(
                Event.status.is_(None),
                ~func.upper(Event.status).in_(["CANCELLED", "PENDING"]),
            )
        )

    rows = query.all()
    events = []
    for event, min_price in rows:
        setattr(event, "min_price", min_price)
        events.append(event)
    return events
  
def get_event_by_id(event_id):
    sync_expired_events_to_finished(event_id=event_id)
    return Event.query.get(event_id)

def _resolve_event_status(status):
    normalized_status = (status or "").strip().upper()
    if normalized_status:
        status_candidates = {
            "PUBLISHED": ["PUBLISHED", "APPROVED"],
            "APPROVED": ["APPROVED", "PUBLISHED"],
        }.get(normalized_status, [normalized_status])

        for candidate in status_candidates:
            status_row = db.session.get(EventStatus, candidate)
            if status_row:
                return status_row.status

    pending_status = db.session.get(EventStatus, "PENDING")
    if pending_status:
        return pending_status.status

    first_status = EventStatus.query.order_by(EventStatus.status.asc()).first()
    return first_status.status if first_status else None


def create_event(data, commit=True):
    event = Event(
        title=data.get("title"),
        image=data.get("image"),
        description=data.get("description"),
        location=data.get("location"),
        startTime=data.get("startTime"),
        endTime=data.get("endTime"),
        createdAt=data.get("createdAt") or datetime.utcnow(),
        publishedAt=data.get("publishedAt"),
        hasFaceReg=data.get("hasFaceReg"),
        limitQuantity=data.get("limitQuantity"),
        status=_resolve_event_status(data.get("status")),
        eventTypeId=data.get("eventTypeId"),
        organizerId=data.get("organizerId")
    )

    db.session.add(event)
    if commit:
        db.session.commit()

    return event