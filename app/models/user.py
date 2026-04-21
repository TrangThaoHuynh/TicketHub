from flask_login import UserMixin
from .. import db


class User(db.Model, UserMixin):
    __tablename__ = "User"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))
    email = db.Column(db.String(255), unique=True)
    username = db.Column(db.String(255), unique=True)
    password = db.Column(db.String(255))
    createdAt = db.Column(db.DateTime)
    avatar = db.Column(db.String(255))
    phoneNumber = db.Column(db.String(20), unique=True)
    verifyCode = db.Column(db.String(10))
    provider = db.Column(db.String(20), db.ForeignKey("AuthProvider.provider"))
    googleID = db.Column(db.String(200), unique=True)
 

class Admin(db.Model):
    __tablename__ = "Admin"
    id = db.Column(db.Integer, db.ForeignKey("User.id"), primary_key=True)


class Organizer(db.Model):
    __tablename__ = "Organizer"
    id = db.Column(db.Integer, db.ForeignKey("User.id"), primary_key=True)
    status = db.Column(db.String(20), db.ForeignKey("OrganizerStatus.status"), default="PENDING")

    user = db.relationship(
        "User",
        primaryjoin="Organizer.id==User.id",
        uselist=False,
        viewonly=True,
    )

    def __str__(self) -> str:
        user = getattr(self, "user", None)
        if user is not None:
            name = (getattr(user, "name", None) or "").strip()
            email = (getattr(user, "email", None) or "").strip()
            base = name or email or f"Organizer #{self.id}"
            return f"{base} (#{self.id})" if self.id is not None else base
        return f"Organizer #{self.id}" if self.id is not None else "Organizer"

    def __repr__(self) -> str:
        return f"<Organizer id={self.id!r} status={self.status!r}>"


class Customer(db.Model):
    __tablename__ = "Customer"
    id = db.Column(db.Integer, db.ForeignKey("User.id"), primary_key=True)