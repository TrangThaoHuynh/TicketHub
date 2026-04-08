from .. import db

class User(db.Model):
    __tablename__ = "User"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))
    email = db.Column(db.String(255), unique=True)
    username = db.Column(db.String(255), unique=True)
    password = db.Column(db.String(255))
    provider = db.Column(db.String(20))
    createdAt = db.Column(db.DateTime)
    avatar = db.Column(db.String(255))
    phoneNumber = db.Column(db.String(20), unique=True)
    provider = db.Column(db.String(20), db.ForeignKey("AuthProvider.provider"))

class Admin(db.Model):
    __tablename__ = "Admin"
    id = db.Column(db.Integer, db.ForeignKey("User.id"), primary_key=True)

class Organizer(db.Model):
    __tablename__ = "Organizer"
    id = db.Column(db.Integer, db.ForeignKey("User.id"), primary_key=True)
    status = db.Column(db.String(20), db.ForeignKey("OrganizerStatus.status"), default="PENDING")

class Customer(db.Model):
    __tablename__ = "Customer"
    id = db.Column(db.Integer, db.ForeignKey("User.id"), primary_key=True)