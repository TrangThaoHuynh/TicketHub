from .. import db


class BookingStatus(db.Model):
    __tablename__ = "BookingStatus"
    status = db.Column(db.String(20), primary_key=True)


class OrganizerStatus(db.Model):
    __tablename__ = "OrganizerStatus"
    status = db.Column(db.String(20), primary_key=True)


class PaymentStatus(db.Model):
    __tablename__ = "PaymentStatus"
    status = db.Column(db.String(20), primary_key=True)


class TicketStatus(db.Model):
    __tablename__ = "TicketStatus"
    status = db.Column(db.String(20), primary_key=True)


class EventStatus(db.Model):
    __tablename__ = "EventStatus"
    status = db.Column(db.String(20), primary_key=True)


class AuthProvider(db.Model):
    __tablename__ = "AuthProvider"
    provider = db.Column(db.String(20), primary_key=True)