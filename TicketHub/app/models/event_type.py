from .. import db

class EventType(db.Model):
    __tablename__ = "EventType"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))
    status = db.Column(db.Boolean)