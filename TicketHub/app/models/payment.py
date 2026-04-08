from .. import db

class Payment(db.Model):
    __tablename__ = "Payment"

    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Numeric(10,2))
    transactionID = db.Column(db.String(255))
    status = db.Column(db.String(20), db.ForeignKey("PaymentStatus.status"))
    bookingId = db.Column(db.Integer, db.ForeignKey("Booking.id"))