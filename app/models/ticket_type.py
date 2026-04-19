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

    event = db.relationship("Event", backref="ticket_types")

    @property
    def event_title(self) -> str:
        event = getattr(self, "event", None)
        title = (getattr(event, "title", None) or "").strip() if event else ""
        if title:
            return title
        return f"Event #{self.eventId}" if self.eventId else "—"

    @property
    def event_type_name(self) -> str:
        event = getattr(self, "event", None)
        event_type = getattr(event, "eventType", None) if event else None
        name = (getattr(event_type, "name", None) or "").strip() if event_type else ""
        return name or "—"

    @property
    def organizer_display(self) -> str:
        event = getattr(self, "event", None)
        organizer = getattr(event, "organizer", None) if event else None
        organizer_user = getattr(organizer, "user", None) if organizer else None

        name = (getattr(organizer_user, "name", None) or "").strip() if organizer_user else ""
        email = (getattr(organizer_user, "email", None) or "").strip() if organizer_user else ""
        base = name or email
        if base:
            return base
        organizer_id = getattr(organizer, "id", None)
        return f"Organizer #{organizer_id}" if organizer_id else "—"

    def __str__(self) -> str:
        name = (self.name or "").strip() or "(Chưa đặt tên loại vé)"
        return f"{name} · {self.event_title} (#{self.id})" if self.id is not None else f"{name} · {self.event_title}"

    def __repr__(self) -> str:
        return f"<TicketType id={self.id!r} name={self.name!r} eventId={self.eventId!r}>"