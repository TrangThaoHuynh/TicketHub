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


def get_ticket_type_by_event(ticket_type_id, event_id):
    return TicketType.query.filter_by(id=ticket_type_id, eventId=event_id).first()


def update_ticket_type(ticket, data, commit=True):
    if ticket is None:
        return None

    if "name" in data:
        ticket.name = data.get("name")
    if "description" in data:
        ticket.description = data.get("description")
    if "price" in data:
        ticket.price = data.get("price")
    if "quantity" in data:
        ticket.quantity = data.get("quantity")
    if "saleStart" in data:
        ticket.saleStart = data.get("saleStart")
    if "saleEnd" in data:
        ticket.saleEnd = data.get("saleEnd")

    if "eventId" in data:
        ticket.eventId = data.get("eventId")

    if commit:
        db.session.commit()

    return ticket