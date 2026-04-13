from ..models.ticket_type import TicketType
from .. import db

def create_ticket_type(data, commit=True):
    ticket = TicketType(
        name=data.get("name"),
        description=data.get("description"),
        price=data.get("price"),
        quantity=data.get("quantity"),
        saleStart=data.get("saleStart"),
        saleEnd=data.get("saleEnd"),
        eventId=data.get("eventId")
    )

    db.session.add(ticket)
    if commit:
        db.session.commit()

    return ticket