from ..models.booking import Booking
from .. import db
from datetime import datetime

def create_booking(data):
    booking = Booking(
        totalAmount=data.get("totalAmount"),
        createdAt=datetime.now(),
        status="PENDING",
        customerId=data.get("customerId")
    )

    db.session.add(booking)
    db.session.commit()

    return booking