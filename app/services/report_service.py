from __future__ import annotations
from collections import defaultdict
from datetime import datetime
from typing import Any
from sqlalchemy import func, or_
from .. import db
from ..models.booking import Booking
from ..models.event import Event
from ..models.payment import Payment
from ..models.ticket import Ticket
from ..models.ticket_type import TicketType
from ..models.user import Organizer, User


PAID_BOOKING_STATUSES = {"success"}
PAID_PAYMENT_STATUSES = {"success"}

def _to_float(value: Any) -> float:
    """Chuyển đổi giá trị từ database sang float (mặc định 0 nếu None)"""
    if value is None:
        return 0.0
    return float(value)

def _paid_condition():
    """
    Tạo điều kiện lọc để tìm booking/payment đã thanh toán thành công
    Dùng cho WHERE clause trong query
    """
    return or_(
        func.lower(func.coalesce(Booking.status, "")).in_(list(PAID_BOOKING_STATUSES)),
        func.lower(func.coalesce(Payment.status, "")).in_(list(PAID_PAYMENT_STATUSES)),
    )

def _period_label(dt: datetime | None, group_by: str) -> str:
    """
    Đổi ngày tháng thành nhãn để vẽ chart
    """
    if dt is None:
        return "Không rõ"
    if group_by == "month":
        return dt.strftime("%m/%Y")
    return dt.strftime("%d/%m")

def _event_state(event: Event) -> tuple[str, str]:
    """
    Xác định trạng thái hiển thị của event + màu badge bootstrap tương ứng
    """
    status = (event.status or "").upper()
    now = datetime.now()
    if status == "CANCELLED":
        return "Đã hủy", "danger"

    if status == "FINISHED":
        return "Đã kết thúc", "secondary"

    if status == "PENDING":
        return "Chờ duyệt", "dark"

    if status == "PUBLISHED":
        if event.startTime and event.endTime:
            # Kiểm tra: đang diễn ra hay chưa bắt đầu hay đã kết thúc
            if event.startTime <= now <= event.endTime:
                return "Đang diễn ra", "primary"
            if now < event.startTime:
                return "Sắp diễn ra", "warning"
            if now > event.endTime:
                return "Đã kết thúc", "secondary"
        return "Đã xuất bản", "info"
    return "Chưa xác định", "dark"

def _build_event_capacity_map(event_ids: list[int]) -> dict[int, int]:
    """
    Tính tổng số vé mở bán của từng event
    """
    if not event_ids:
        return {}

    rows = (
        db.session.query(
            TicketType.eventId,  # Nhóm theo event
            func.coalesce(func.sum(TicketType.quantity), 0).label("total_quantity"),  # Tổng số vé
        )
        .filter(TicketType.eventId.in_(event_ids))
        .group_by(TicketType.eventId)
        .all()
    )

    return {
        int(event_id): int(total_quantity or 0)
        for event_id, total_quantity in rows
    }


def _build_event_sales_map(event_ids: list[int],organizer_id: int,start_date: datetime | None = None,end_date: datetime | None = None,) -> dict[int, dict[str, float]]:
    """
    Tính số vé đã bán + doanh thu của từng event
    Có thể lọc theo khoảng ngày mua vé
    """
    if not event_ids:
        return {}

    query = (
        db.session.query(
            TicketType.eventId.label("event_id"),
            func.count(Ticket.id).label("sold_tickets"),
            func.coalesce(func.sum(Ticket.price), 0).label("revenue"),
        )
        .select_from(Ticket)
        .join(Booking, Booking.id == Ticket.bookingId)
        .outerjoin(Payment, Payment.bookingId == Booking.id)
        .join(TicketType, TicketType.id == Ticket.ticketTypeId)
        .join(Event, Event.id == TicketType.eventId)
        .filter(Event.organizerId == organizer_id)
        .filter(TicketType.eventId.in_(event_ids))
        .filter(_paid_condition())
    )

    if start_date:
        query = query.filter(Booking.createdAt >= start_date)
    if end_date:
        query = query.filter(Booking.createdAt <= end_date)

    rows = query.group_by(TicketType.eventId).all()

    result: dict[int, dict[str, float]] = {}
    for event_id, sold_tickets, revenue in rows:
        result[int(event_id)] = {
            "sold_tickets": int(sold_tickets or 0),
            "revenue": _to_float(revenue),
        }
    return result


# ============ HÀM LẤY DỮ LIỆU DASHBOARD CHO ORGANIZER ============
def get_organizer_report_dashboard(
    organizer_id: int,
    event_id: int | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> dict[str, Any]:
    """
    Lấy dữ liệu dashboard báo cáo cho nhà tổ chức
    Có lọc theo event và khoảng ngày mua vé
    """
    events = (
        Event.query
        .filter_by(organizerId=organizer_id)
        .order_by(Event.startTime.desc(), Event.id.desc())
        .all()
    )

    event_options = [{"id": e.id, "title": e.title} for e in events]
    event_ids = [e.id for e in events]

    capacity_map = _build_event_capacity_map(event_ids)
    sales_map = _build_event_sales_map(
        event_ids,
        organizer_id,
        start_date=start_date,
        end_date=end_date,
    )

    rows = []
    total_revenue = 0.0
    ongoing_count = 0

    for event in events:
        total_tickets = capacity_map.get(event.id, 0)
        sold_tickets = int(sales_map.get(event.id, {}).get("sold_tickets", 0))
        revenue = float(sales_map.get(event.id, {}).get("revenue", 0.0))
        status_label, status_badge = _event_state(event)

        if status_label == "Đang diễn ra":
            ongoing_count += 1

        total_revenue += revenue

        rows.append({
            "id": event.id,
            "title": event.title,
            "start_date_text": event.startTime.strftime("%d/%m/%Y") if event.startTime else "",
            "total_tickets": total_tickets,
            "sold_tickets": sold_tickets,
            "remaining_tickets": max(total_tickets - sold_tickets, 0),
            "revenue": revenue,
            "status_label": status_label,
            "status_badge": status_badge,
        })

    selected_event_id = event_id if event_id in event_ids else None

    chart_query = (
        db.session.query(
            Booking.createdAt.label("created_at"),
            Ticket.price.label("ticket_price"),
        )
        .select_from(Ticket)
        .join(Booking, Booking.id == Ticket.bookingId)
        .outerjoin(Payment, Payment.bookingId == Booking.id)
        .join(TicketType, TicketType.id == Ticket.ticketTypeId)
        .join(Event, Event.id == TicketType.eventId)
        .filter(Event.organizerId == organizer_id)
        .filter(_paid_condition())
        .order_by(Booking.createdAt.asc())
    )

    if selected_event_id is not None:
        chart_query = chart_query.filter(Event.id == selected_event_id)

    if start_date:
        chart_query = chart_query.filter(Booking.createdAt >= start_date)
    if end_date:
        chart_query = chart_query.filter(Booking.createdAt <= end_date)

    revenue_by_period: dict[str, float] = defaultdict(float)
    for created_at, ticket_price in chart_query.all():
        revenue_by_period[_period_label(created_at, "day")] += _to_float(ticket_price)

    return {
        "filters": {
            "event_id": selected_event_id,
            "start_date": start_date.strftime("%Y-%m-%d") if start_date else "",
            "end_date": end_date.strftime("%Y-%m-%d") if end_date else "",
        },
        "event_options": event_options,
        "cards": {
            "total_events": len(events),
            "total_revenue": total_revenue,
            "ongoing_events": ongoing_count,
        },
        "chart": {
            "labels": list(revenue_by_period.keys()),
            "values": [round(v, 2) for v in revenue_by_period.values()],
        },
        "rows": rows,
    }


# ============ HÀM CHO ADMIN DASHBOARD ============

def _apply_common_scope(query, organizer_id=None, start_date=None, end_date=None):
    """
    Thêm các filter chung vào query admin (lọc theo organizer, ngày)
    """
    if organizer_id:
        query = query.filter(Event.organizerId == organizer_id)
    if start_date:
        query = query.filter(Booking.createdAt >= start_date)
    if end_date:
        query = query.filter(Booking.createdAt <= end_date)
    return query

def _build_status_payload(counter: dict[str, int], mapping: dict[str, str]) -> dict[str, list]:
    """
    Chuyển dữ liệu đếm status thành labels + values cho chart
    """
    labels = []
    values = []

    # Duyệt qua từng status và số lượng
    for raw_status, count in counter.items():
        # Lấy tên tiếng Việt từ mapping (nếu không có → dùng raw_status)
        label = mapping.get(raw_status.upper(), raw_status)
        labels.append(label)
        values.append(count)

    return {
        "labels": labels,  # ["Thành công", "Thất bại", "Chờ xử lý"]
        "values": values,  # [800, 50, 10]
    }

# ============ HÀM LẤY DỮ LIỆU DASHBOARD CHO ADMIN ============
def get_admin_report_dashboard(
    organizer_id: int | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    group_by: str = "day",
) -> dict[str, Any]:
    """
    Lấy dữ liệu dashboard báo cáo toàn hệ thống cho admin
    """
    # Chuẩn hóa group_by
    group_by = "month" if group_by == "month" else "day"
    organizer_options = (
        db.session.query(
            Organizer.id.label("id"),  
            User.name.label("name"),  
        )
        .join(User, User.id == Organizer.id) 
        .order_by(User.name.asc(), Organizer.id.asc())  
        .all()
    )
    # ==========  Tính tổng doanh thu + tổng vé đã bán ==========
    summary_query = (
        db.session.query(
            func.coalesce(func.sum(Ticket.price), 0).label("total_revenue"),  # Tổng doanh thu
            func.count(Ticket.id).label("total_tickets"),  # Tổng số vé
        )
        .select_from(Ticket)
        .join(Booking, Booking.id == Ticket.bookingId)
        .outerjoin(Payment, Payment.bookingId == Booking.id)
        .join(TicketType, TicketType.id == Ticket.ticketTypeId)
        .join(Event, Event.id == TicketType.eventId)
        .filter(_paid_condition())  # Chỉ lấy đơn đã thanh toán
    )
    # Áp dụng các filter (organizer, ngày)
    summary_query = _apply_common_scope(summary_query, organizer_id, start_date, end_date)
    summary_row = summary_query.one()  # Lấy 1 dòng kết quả

    total_revenue = _to_float(summary_row.total_revenue)  # KPI: Tổng doanh thu
    total_tickets_sold = int(summary_row.total_tickets or 0)  # KPI: Tổng vé bán

    # ==========  Lấy dữ liệu chart doanh thu theo thời gian ==========
    time_query = (
        db.session.query(
            Booking.createdAt.label("created_at"),  # Lấy ngày tạo booking
            Ticket.price.label("ticket_price"),  # Lấy giá vé
        )
        .select_from(Ticket)
        .join(Booking, Booking.id == Ticket.bookingId)
        .outerjoin(Payment, Payment.bookingId == Booking.id)
        .join(TicketType, TicketType.id == Ticket.ticketTypeId)
        .join(Event, Event.id == TicketType.eventId)
        .filter(_paid_condition())
        .order_by(Booking.createdAt.asc())
    )
    time_query = _apply_common_scope(time_query, organizer_id, start_date, end_date)

    # Gom doanh thu theo ngày/tháng
    revenue_by_period: dict[str, float] = defaultdict(float)
    for created_at, ticket_price in time_query.all():
        period = _period_label(created_at, group_by)
        revenue_by_period[period] += _to_float(ticket_price)

    # ========== Lấy dữ liệu chart doanh thu theo sự kiện ==========
    event_revenue_query = (
        db.session.query(
            Event.id.label("event_id"),  # ID event
            Event.title.label("event_title"),  # Tên event
            func.coalesce(func.sum(Ticket.price), 0).label("revenue"),  # Doanh thu
            func.count(Ticket.id).label("sold_tickets"),  # Vé bán
        )
        .select_from(Ticket)
        .join(Booking, Booking.id == Ticket.bookingId)
        .outerjoin(Payment, Payment.bookingId == Booking.id)
        .join(TicketType, TicketType.id == Ticket.ticketTypeId)
        .join(Event, Event.id == TicketType.eventId)
        .filter(_paid_condition())
        .group_by(Event.id, Event.title)  # Nhóm theo sự kiện
        .order_by(func.coalesce(func.sum(Ticket.price), 0).desc(), Event.id.asc())  # Sắp xếp theo doanh thu giảm dần
    )
    event_revenue_query = _apply_common_scope(event_revenue_query, organizer_id, start_date, end_date)

    # Xây dựng bảng doanh thu theo event
    event_revenue_rows = []
    for event_id_value, event_title, revenue, sold_tickets in event_revenue_query.all():
        event_revenue_rows.append({
            "event_id": int(event_id_value),
            "event_title": event_title,
            "revenue": _to_float(revenue),
            "sold_tickets": int(sold_tickets or 0),
        })

    # ==========  Đếm booking theo trạng thái ==========
    booking_rows = (
        db.session.query(
            Booking.id.label("booking_id"),
            Booking.status.label("booking_status"),
        )
        .join(Ticket, Ticket.bookingId == Booking.id)
        .join(TicketType, TicketType.id == Ticket.ticketTypeId)
        .join(Event, Event.id == TicketType.eventId)
        .group_by(Booking.id, Booking.status)  # Nhóm để đếm
    )

    # Áp dụng các filter
    if organizer_id:
        booking_rows = booking_rows.filter(Event.organizerId == organizer_id)
    if start_date:
        booking_rows = booking_rows.filter(Booking.createdAt >= start_date)
    if end_date:
        booking_rows = booking_rows.filter(Booking.createdAt <= end_date)

    # Đếm số lượng booking theo status
    booking_counter: dict[str, int] = defaultdict(int)
    for _, booking_status in booking_rows.all():
        booking_counter[(booking_status or "UNKNOWN").upper()] += 1

    # ==========  Đếm event theo trạng thái ==========
    event_status_query = (
        db.session.query(
            Event.status,  # Trạng thái event
            func.count(Event.id)  # Số lượng
        )
        .group_by(Event.status)  # Nhóm theo status
    )

    # Áp dụng các filter
    if organizer_id:
        event_status_query = event_status_query.filter(Event.organizerId == organizer_id)
    if start_date:
        event_status_query = event_status_query.filter(Event.startTime >= start_date)
    if end_date:
        event_status_query = event_status_query.filter(Event.startTime <= end_date)

    # Đếm số lượng event theo status
    event_counter: dict[str, int] = defaultdict(int)
    for event_status, count in event_status_query.all():
        event_counter[(event_status or "UNKNOWN").upper()] += int(count or 0)

    # ========== Đếm ticket theo trạng thái ==========
    ticket_status_query = (
        db.session.query(
            Ticket.status,  # Trạng thái vé
            func.count(Ticket.id)  # Số lượng
        )
        .select_from(Ticket)
        .join(Booking, Booking.id == Ticket.bookingId)
        .join(TicketType, TicketType.id == Ticket.ticketTypeId)
        .join(Event, Event.id == TicketType.eventId)
        .group_by(Ticket.status)  # Nhóm theo status
    )

    # Áp dụng các filter
    if organizer_id:
        ticket_status_query = ticket_status_query.filter(Event.organizerId == organizer_id)
    if start_date:
        ticket_status_query = ticket_status_query.filter(Booking.createdAt >= start_date)
    if end_date:
        ticket_status_query = ticket_status_query.filter(Booking.createdAt <= end_date)

    # Đếm số lượng ticket theo status
    ticket_counter: dict[str, int] = defaultdict(int)
    for ticket_status, count in ticket_status_query.all():
        ticket_counter[(ticket_status or "UNKNOWN").upper()] += int(count or 0)

    # Đổi "SUCCESS" → "Thành công", "FAILED" → "Thất bại"
    booking_status_map = {
        "SUCCESS": "Thành công",
        "FAILED": "Thất bại",
        "PENDING": "Chờ xử lý"
    }

    event_status_map = {
        "PENDING": "Chờ duyệt",
        "PUBLISHED": "Đã xuất bản",
        "FINISHED": "Đã kết thúc",
        "CANCELLED": "Đã hủy"
    }

    ticket_status_map = {
        "PENDING": "Chờ xử lý",
        "VALID": "Hợp lệ",
        "USED": "Đã dùng",
        "CANCELLED": "Đã hủy"
    }
    return {
        "filters": {
            "organizer_id": organizer_id,  # Organizer được chọn
            "start_date": start_date.strftime("%Y-%m-%d") if start_date else "",  # Ngày bắt đầu
            "end_date": end_date.strftime("%Y-%m-%d") if end_date else "",  # Ngày kết thúc
            "group_by": group_by,  # Nhóm theo "day" hoặc "month"
        },
        "organizer_options": [
            {"id": row.id, "name": row.name or f"Organizer #{row.id}"}
            for row in organizer_options
        ],
        "cards": {
            "total_revenue": total_revenue,  # KPI: Tổng doanh thu
            "total_tickets_sold": total_tickets_sold,  # KPI: Tổng vé bán
        },
        "charts": {
            "time_revenue": {
                "labels": list(revenue_by_period.keys()),  # Nhãn: ["14/04", "13/04"]
                "values": [round(v, 2) for v in revenue_by_period.values()],  # Giá trị
            },
            "event_revenue": {
                "labels": [row["event_title"] for row in event_revenue_rows],  # Tên sự kiện
                "values": [row["revenue"] for row in event_revenue_rows],  # Doanh thu
            },
            "booking_status": _build_status_payload(booking_counter, booking_status_map),  # Chart trạng thái booking
            "event_status": _build_status_payload(event_counter, event_status_map),  # Chart trạng thái event
            "ticket_status": _build_status_payload(ticket_counter, ticket_status_map),  # Chart trạng thái vé
        },
        "event_revenue_rows": event_revenue_rows,  # Bảng doanh thu chi tiết
    }