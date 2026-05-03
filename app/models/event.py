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

    def __str__(self) -> str:
        title = (self.title or "").strip() or "(Chưa đặt tên sự kiện)"
        parts = [title]

        event_type = getattr(self, "eventType", None)
        if event_type is not None:
            event_type_name = (getattr(event_type, "name", None) or "").strip()
            if event_type_name:
                parts.append(event_type_name)

        organizer = getattr(self, "organizer", None)
        if organizer is not None:
            organizer_user = getattr(organizer, "user", None)
            organizer_name = (getattr(organizer_user, "name", None) or "").strip() if organizer_user else ""
            if organizer_name:
                parts.append(organizer_name)

        suffix = " · ".join(parts)
        return f"{suffix} (#{self.id})" if self.id is not None else suffix

    def __repr__(self) -> str:
        return f"<Event id={self.id!r} title={self.title!r}>"
