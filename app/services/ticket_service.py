from ..models.ticket import Ticket
from ..models.ticket_type import TicketType 
from .. import db
import uuid
from sqlalchemy import func
from datetime import datetime

#Lay danh sach loai ve cua 1 su kien
def get_ticket_types_by_event_id(event_id):
    return TicketType.query.filter_by(eventId=event_id).all()

#dem so luong ve da bán
def count_sold_by_ticket_type(ticket_type_ids: list[int])-> dict[int, int]:
    if not ticket_type_ids:
        return {}

    rows = (
    db.session.query(Ticket.ticketTypeId, func.count(Ticket.id)) 
    .filter(
        Ticket.ticketTypeId.in_(ticket_type_ids), 
        Ticket.status.in_(["ACTIVE", "USED"])
    )
    .group_by(Ticket.ticketTypeId)
    .all()
)
    return {tid: cnt for tid, cnt in rows}

def create_ticket(data):
    ticket = Ticket(
        id=str(uuid.uuid4()),
        fullName=data.get("fullName"),
        phoneNumber=data.get("phoneNumber"),
        price=data.get("price"),
        createdAt=datetime.now(),
        status="PENDING",
        bookingId=data.get("bookingId"),
        ticketTypeId=data.get("ticketTypeId"),
        customerId=data.get("customerId")
    )

    db.session.add(ticket)
    db.session.commit()

    return ticket