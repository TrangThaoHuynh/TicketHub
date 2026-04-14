# app/routes/report_routes.py

from datetime import datetime, time

from flask import Blueprint, abort, redirect, render_template, request, session, url_for

from ..models.user import Admin, Organizer
from ..services.report_service import (
    get_admin_report_dashboard,
    get_organizer_report_dashboard,
)

report_bp = Blueprint("reports", __name__)


# ============ CHUYỂN ĐỔI NGÀY THÁNG ============

def _parse_start_date(value: str | None):
    """
    Chuyển đổi chuỗi ngày từ request thành datetime object
    Đặt thời gian = 00:00:00 (đầu ngày)
    """
    if not value:
        return None
    try:
        dt = datetime.strptime(value, "%Y-%m-%d")
        return datetime.combine(dt.date(), time.min)
    except ValueError:
        return None


def _parse_end_date(value: str | None):
    """
    Chuyển đổi chuỗi ngày từ request thành datetime object
    Đặt thời gian = 23:59:59 (cuối ngày)
    """
    if not value:
        return None
    try:
        dt = datetime.strptime(value, "%Y-%m-%d")
        return datetime.combine(dt.date(), time.max)
    except ValueError:
        return None


# ============  DASHBOARD BÁO CÁO CHO NHÀ TỔ CHỨC ============

@report_bp.route("/organizer/reports")
def organizer_reports():
    """
    Trang báo cáo thống kê cho nhà tổ chức (organizer)
    Hiển thị: KPI, chart doanh thu, bảng sự kiện
    """
    # Kiểm tra người dùng đã login hay chưa
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login.login"))

    # Kiểm tra người dùng là organizer hay không
    organizer = Organizer.query.get(int(user_id))
    if organizer is None:
        abort(403)

    #  Lấy và xử lý tham số eventId
    raw_event_id = request.args.get("eventId", "")  # Lấy từ query string
    try:
        event_id = int(raw_event_id) if raw_event_id else None
    except ValueError:
        event_id = None

    # Lấy khoảng ngày lọc
    start_date = _parse_start_date(request.args.get("startDate"))
    end_date = _parse_end_date(request.args.get("endDate"))

    dashboard = get_organizer_report_dashboard(
        organizer_id=int(user_id),
        event_id=event_id,
        start_date=start_date,
        end_date=end_date,
    )

    return render_template(
        "organizer_dashboard.html",
        dashboard=dashboard,
        show_search=False,
    )


# ============  DASHBOARD BÁO CÁO CHO ADMIN ============

@report_bp.route("/admin/reports")
def admin_reports():
    """
    Trang báo cáo thống kê cho admin (quản trị viên)
    Hiển thị: Thống kê toàn hệ thống, doanh thu tất cả organizer
    """
    
    #  Kiểm tra người dùng đã login hay chưa
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login.login"))

    # Kiểm tra người dùng là admin hay không 
    admin = Admin.query.get(int(user_id))
    if admin is None:
        abort(403)

    # Lấy và xử lý tham số organizerId 
    raw_organizer_id = request.args.get("organizerId", "")  # Lấy từ query string
    try:
        organizer_id = int(raw_organizer_id) if raw_organizer_id else None
    except ValueError:
        organizer_id = None

    #  Lấy và xử lý tham số startDate 
    start_date = _parse_start_date(request.args.get("startDate"))

    #  Lấy và xử lý tham số endDate
    end_date = _parse_end_date(request.args.get("endDate"))

    # Lấy tham số groupBy
    group_by = request.args.get("groupBy", "day")  # Mặc định: "day"

    #  Gọi service để lấy dữ liệu dashboard toàn hệ thống
    dashboard = get_admin_report_dashboard(
        organizer_id=organizer_id,  # Lọc theo organizer (None = tất cả)
        start_date=start_date,  # Ngày bắt đầu (None = không lọc)
        end_date=end_date,  # Ngày kết thúc (None = không lọc)
        group_by=group_by,  # Nhóm chart
    )
    return render_template(
        "admin_dashboard.html",
        dashboard=dashboard, 
        show_search=False, 
    )