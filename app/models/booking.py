from .. import db

class Booking(db.Model):
    __tablename__ = "Booking"

    id = db.Column(db.Integer, primary_key=True)
    totalAmount = db.Column(db.Numeric(10,2))
    createdAt = db.Column(db.DateTime)

    status = db.Column(
        db.String(20),
        db.ForeignKey("BookingStatus.status")
    )

    customerId = db.Column(
        db.Integer,
        db.ForeignKey("Customer.id")
    )

    # relationship
    payments = db.relationship("Payment", backref="booking")
    tickets = db.relationship("Ticket", backref="booking")