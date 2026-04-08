from .. import db

class Ticket(db.Model):
    __tablename__ = "Ticket"

    id = db.Column(db.String(50), primary_key=True)
    qrCode = db.Column(db.String(255))
    createdAt = db.Column(db.DateTime)
    checkedIn = db.Column(db.DateTime)
    price = db.Column(db.Numeric(10,2))
    ticketCode = db.Column(db.String(50))
    fullName = db.Column(db.String(255))
    phoneNumber = db.Column(db.String(20))
    faceEmbedding = db.Column(db.Text)
    status = db.Column(db.String(20), db.ForeignKey("TicketStatus.status"))

    bookingId = db.Column(db.Integer, db.ForeignKey("Booking.id"))
    ticketTypeId = db.Column(db.Integer, db.ForeignKey("TicketType.id"))
    customerId = db.Column(db.Integer, db.ForeignKey("Customer.id"))