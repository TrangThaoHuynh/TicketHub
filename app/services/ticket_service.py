from ..models.ticket import Ticket
from .. import db
import uuid
from datetime import datetime

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