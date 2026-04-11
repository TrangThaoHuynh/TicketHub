from ..models.ticket import Ticket
from ..models.ticket_type import TicketType 
from ..models.event import Event                    
from ..models.enums import TicketStatus             
from .. import db
from sqlalchemy import func
from sqlalchemy.orm import joinedload              
from datetime import datetime

#Lay danh sach loai ve cua 1 su kien
def get_ticket_types_by_event_id(event_id):
    return TicketType.query.filter_by(eventId=event_id).all()

#dem so luong ve da bán
def count_sold_by_ticket_type(ticket_type_ids: list[int])-> dict[int, int]:
    if not ticket_type_ids:
        return {}

    rows = (
    db.session.query(Ticket.ticketTypeId, func.count(Ticket.id)) 
    .filter(
        Ticket.ticketTypeId.in_(ticket_type_ids), 
        Ticket.status.in_(["ACTIVE", "USED"])
    )
    .group_by(Ticket.ticketTypeId)
    .all()
)
    return {tid: cnt for tid, cnt in rows}
#Lay ve cua nguoi dung
def get_tickets_of_user(user_id: int, q: str = "", status: str = None, page: int = 1, per_page: int = 12):
    query = (
        db.session.query(Ticket)
        .filter(Ticket.customer_id == user_id)
        .options(
            joinedload(Ticket.event),
            joinedload(Ticket.ticket_type)
        )
        .order_by(Ticket.created_at.desc())
    )

    if q:
        like_q = f"%{q.strip()}%"
        query = query.filter(
            db.or_(
                Ticket.ticket_code.ilike(like_q),
                Ticket.ticket_type.has(TicketType.name.ilike(like_q)),
                Ticket.event.has(Event.name.ilike(like_q))
            )
        )

    if status:
        query = query.filter(Ticket.status == status)

    return query.paginate(page=page, per_page=per_page)
def get_ticket_by_id(ticket_id: int):
    return Ticket.query.get(ticket_id)

def get_ticket_by_qr(qr_data: str):
    return Ticket.query.filter_by(qr_data=qr_data).first()

def save_ticket_qr(ticket: Ticket, qr_data: str):
    ticket.qr_data = qr_data
    ticket.issued_at = datetime.utcnow()
    db.session.add(ticket)
    db.session.commit()

# Đánh dấu vé đã dùng
def mark_checked_in(ticket: Ticket):
    from app.models import TicketStatus
    ticket.status = TicketStatus.USED
    ticket.use_at = datetime.utcnow()
    db.session.add(ticket)
    db.session.commit()
def create_ticket(data):
    ticket = Ticket(
        id=str(uuid.uuid4()),
        fullName=data.get("fullName"),
        phoneNumber=data.get("phoneNumber"),
        price=data.get("price"),
        createdAt=datetime.now(),
        status="PENDING",
        bookingId=data.get("bookingId"),
        ticketTypeId=data.get("ticketTypeId"),
        customerId=data.get("customerId")
    )

    db.session.add(ticket)
    db.session.commit()

    return ticket
