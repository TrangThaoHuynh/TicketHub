from .. import db

class EventType(db.Model):
    __tablename__ = "EventType"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))
    status = db.Column(db.Boolean)

    def __str__(self) -> str:
        label = (self.name or "").strip() or "(Chưa đặt tên)"
        return f"{label} (#{self.id})" if self.id is not None else label

    def __repr__(self) -> str:
        return f"<EventType id={self.id!r} name={self.name!r}>"