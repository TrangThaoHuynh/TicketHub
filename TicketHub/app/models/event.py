from .. import db

class Event(db.Model):
    __tablename__ = "Event"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255))
    image = db.Column(db.String(255))
    description = db.Column(db.Text)
    location = db.Column(db.String(255))
    startTime = db.Column(db.DateTime)
    endTime = db.Column(db.DateTime)
    createdAt = db.Column(db.DateTime)
    publishedAt = db.Column(db.DateTime)
    hasFaceReg = db.Column(db.Boolean)
    limitQuantity = db.Column(db.Integer)

    status = db.Column(db.String(20), db.ForeignKey("EventStatus.status"))
    organizerId = db.Column(db.Integer, db.ForeignKey("Organizer.id"))
    eventTypeId = db.Column(db.Integer, db.ForeignKey("EventType.id"))
    
    eventType = db.relationship("EventType", backref="events")
    organizer = db.relationship("Organizer", backref="events")
