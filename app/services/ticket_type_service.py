from ..models.ticket_type import TicketType
from .. import db

def create_ticket_type(data):
    ticket = TicketType(
        name=data.get("name"),
        price=data.get("price"),
        quantity=data.get("quantity"),
        eventId=data.get("eventId")
    )

    db.session.add(ticket)
    db.session.commit()

    return ticket