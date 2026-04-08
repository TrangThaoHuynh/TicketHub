from .. import db

class TicketType(db.Model):
    __tablename__ = "TicketType"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(10,2))
    quantity = db.Column(db.Integer)
    saleStart = db.Column(db.DateTime)
    saleEnd = db.Column(db.DateTime)

    eventId = db.Column(db.Integer, db.ForeignKey("Event.id"))