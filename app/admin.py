from __future__ import annotations

from typing import Any

from flask import abort, flash, redirect, request, session, url_for
from flask_admin import Admin, AdminIndexView, BaseView, expose
from flask_admin.contrib.sqla import ModelView
from flask_admin.contrib.sqla.filters import BaseSQLAFilter
from markupsafe import Markup
from sqlalchemy import func
from wtforms import ValidationError
from wtforms.fields import FileField

from . import db
from .models.booking import Booking
from .models.event import Event
from .models.event_type import EventType
from .models.payment import Payment
from .models.ticket import Ticket
from .models.ticket_type import TicketType
from .models.user import Admin as AdminRole
from .models.user import Customer, Organizer, User
from .services.cloudinary_service import cloudinary_service
from .services.organizer_approval_service import (
    get_organizer_approval_detail,
    list_organizers_for_approval,
    set_organizer_status,
)


def _is_admin() -> bool:
    user_id = session.get("user_id")
    if not user_id:
        return False
    try:
        user_id_int = int(user_id)
    except (TypeError, ValueError):
        return False
    return AdminRole.query.get(user_id_int) is not None


class SecureAdminIndexView(AdminIndexView):
    extra_css = ["/static/css/admin_theme.css"]

    def is_accessible(self) -> bool:
        return _is_admin()

    def inaccessible_callback(self, name: str, **kwargs: Any):
        return redirect(url_for("login.login", next=request.full_path))


class SecureModelView(ModelView):
    extra_css = ["/static/css/admin_theme.css"]

    def is_accessible(self) -> bool:
        return _is_admin()

    def inaccessible_callback(self, name: str, **kwargs: Any):
        return redirect(url_for("login.login", next=request.full_path))


class ReadOnlyModelView(SecureModelView):
    can_create = False
    can_edit = False
    can_delete = False


class BookingAdminView(ReadOnlyModelView):
    column_list = [
        "id",
        "createdAt",
        "status",
        "customerId",
        "totalAmount",
        "tickets",
        "payments",
    ]

    column_labels = {
        "id": "ID",
        "createdAt": "Thời gian đặt",
        "status": "Trạng thái",
        "customerId": "Khách hàng",
        "totalAmount": "Tổng tiền",
        "tickets": "Số vé",
        "payments": "Thanh toán",
    }

    column_default_sort = ("id", True)
    can_view_details = True

    column_filters = [
        "status",
        "customerId",
        "createdAt",
        "totalAmount",
    ]

    column_searchable_list = [
        "id",
        "customerId",
    ]

    def _fmt_dt(self, value):
        if value is None:
            return "—"
        try:
            return value.strftime("%d/%m/%Y %H:%M")
        except Exception:
            return str(value)

    def _fmt_money(self, value):
        if value is None:
            return "—"
        try:
            return f"{float(value):,.0f}".replace(",", ".") + " đ"
        except Exception:
            return str(value)

    def _fmt_customer(self, customer_id):
        if not customer_id:
            return "—"

        try:
            customer_id_int = int(customer_id)
        except (TypeError, ValueError):
            return str(customer_id)

        user = User.query.get(customer_id_int)
        if not user:
            return str(customer_id)

        name = user.name or user.username or "—"
        email = user.email or "—"
        phone = user.phoneNumber or "—"
        return f"{customer_id_int} • {name} • {phone} • {email}"

    def _ticket_count(self, booking_id: int) -> int:
        return int(db.session.query(func.count(Ticket.id)).filter(Ticket.bookingId == booking_id).scalar() or 0)

    def _payment_summary(self, booking_id: int) -> str:
        last_payment = (
            Payment.query
            .filter(Payment.bookingId == booking_id)
            .order_by(Payment.id.desc())
            .first()
        )
        count = int(db.session.query(func.count(Payment.id)).filter(Payment.bookingId == booking_id).scalar() or 0)
        if not last_payment:
            return f"0 giao dịch"
        status = getattr(last_payment, "status", None) or "—"
        amount = self._fmt_money(getattr(last_payment, "amount", None))
        tx = getattr(last_payment, "transactionID", None) or ""
        tx_short = (tx[:10] + "…") if len(tx) > 11 else tx
        return f"{count} giao dịch • {status} • {amount}" + (f" • {tx_short}" if tx_short else "")

    column_formatters = {
        "createdAt": lambda v, _c, m, _p: v._fmt_dt(getattr(m, "createdAt", None)),
        "totalAmount": lambda v, _c, m, _p: v._fmt_money(getattr(m, "totalAmount", None)),
        "customerId": lambda v, _c, m, _p: v._fmt_customer(getattr(m, "customerId", None)),
        "tickets": lambda v, _c, m, _p: f"{v._ticket_count(int(getattr(m, 'id', 0) or 0))} vé",
        "payments": lambda v, _c, m, _p: v._payment_summary(int(getattr(m, 'id', 0) or 0)),
    }


class PaymentAdminView(ReadOnlyModelView):
    column_list = [
        "id",
        "bookingId",
        "status",
        "amount",
        "transactionID",
        "booking",
    ]

    column_labels = {
        "id": "ID",
        "bookingId": "Đơn mua",
        "status": "Trạng thái",
        "amount": "Số tiền",
        "transactionID": "Mã giao dịch",
        "booking": "Thông tin đơn",
    }

    column_default_sort = ("id", True)
    can_view_details = True

    column_filters = [
        "status",
        "bookingId",
        "amount",
    ]

    column_searchable_list = [
        "transactionID",
        "bookingId",
        "status",
    ]

    def _fmt_money(self, value):
        if value is None:
            return "—"
        try:
            return f"{float(value):,.0f}".replace(",", ".") + " đ"
        except Exception:
            return str(value)

    def _fmt_booking_id(self, payment: Payment) -> str:
        booking_id = getattr(payment, "bookingId", None)
        if not booking_id:
            return "—"

        booking = getattr(payment, "booking", None)
        if booking is None:
            return str(booking_id)

        customer_id = getattr(booking, "customerId", None)
        user = None
        if customer_id is not None:
            try:
                user = User.query.get(int(customer_id))
            except (TypeError, ValueError):
                user = None

        name = (user.name or user.username) if user else (str(customer_id) if customer_id else "—")
        phone = (user.phoneNumber or "—") if user else "—"
        return f"{booking_id} • {name} • {phone}"

    def _fmt_booking(self, booking: Booking | None):
        if booking is None:
            return "—"

        created_at = getattr(booking, "createdAt", None)
        created_txt = "—"
        if created_at is not None:
            try:
                created_txt = created_at.strftime("%d/%m/%Y %H:%M")
            except Exception:
                created_txt = str(created_at)

        status = getattr(booking, "status", None) or "—"
        total_txt = self._fmt_money(getattr(booking, "totalAmount", None))
        return f"{created_txt} • {status} • {total_txt}"

    column_formatters = {
        "amount": lambda v, _c, m, _p: v._fmt_money(getattr(m, "amount", None)),
        "bookingId": lambda v, _c, m, _p: v._fmt_booking_id(m),
        "booking": lambda v, _c, m, _p: v._fmt_booking(getattr(m, "booking", None)),
        "transactionID": lambda v, _c, m, _p: ((getattr(m, "transactionID", None) or "—")[:64] + ("…" if getattr(m, "transactionID", None) and len(getattr(m, "transactionID")) > 64 else "")),
    }


class AdminReportsView(BaseView):
    extra_css = ["/static/css/admin_theme.css"]

    @expose("/")
    def index(self):
        return redirect(url_for("reports.admin_reports"))

    def is_accessible(self) -> bool:
        return _is_admin()

    def inaccessible_callback(self, name: str, **kwargs: Any):
        return redirect(url_for("login.login", next=request.full_path))


class AdminLogoutView(BaseView):
    extra_css = ["/static/css/admin_theme.css"]

    @expose("/")
    def index(self):
        return redirect(url_for("login.logout"))

    def is_accessible(self) -> bool:
        return _is_admin()

    def inaccessible_callback(self, name: str, **kwargs: Any):
        return redirect(url_for("login.login", next=request.full_path))


class OrganizerApprovalView(BaseView):
    @expose("/")
    def index(self):
        filters = {
            "q": (request.args.get("q", "") or "").strip(),
            "status": (request.args.get("status", "all") or "all").strip().lower(),
        }

        rows = list_organizers_for_approval(q=filters["q"], status=filters["status"])
        return self.render("admin_organizer_approval.html", rows=rows, filters=filters)

    @expose("/detail/<int:organizer_id>")
    def detail(self, organizer_id: int):
        detail = get_organizer_approval_detail(organizer_id=organizer_id)
        if detail is None:
            abort(404)
        return self.render("admin_organizer_approval_detail.html", organizer=detail)

    @expose("/approve/<int:organizer_id>", methods=["POST"])
    def approve(self, organizer_id: int):
        error = set_organizer_status(organizer_id=organizer_id, new_status="APPROVED")
        if error:
            flash(error, "error")
        else:
            flash("Duyệt nhà tổ chức thành công.", "success")

        return redirect(request.referrer or url_for("admin_organizer_approval.index"))

    @expose("/reject/<int:organizer_id>", methods=["POST"])
    def reject(self, organizer_id: int):
        error = set_organizer_status(organizer_id=organizer_id, new_status="REJECTED")
        if error:
            flash(error, "error")
        else:
            flash("Từ chối nhà tổ chức thành công.", "success")

        return redirect(request.referrer or url_for("admin_organizer_approval.index"))

    def is_accessible(self) -> bool:
        return _is_admin()

    def inaccessible_callback(self, name: str, **kwargs: Any):
        return redirect(url_for("login.login", next=request.full_path))


class UserRoleFilter(BaseSQLAFilter):
    def operation(self):
        return "is"

    def validate(self, value):
        return value in {"admin", "organizer", "customer"}

    def apply(self, query, value, alias=None):
        if value == "admin":
            return query.filter(db.session.query(AdminRole.id).filter(AdminRole.id == User.id).exists())
        if value == "organizer":
            return query.filter(db.session.query(Organizer.id).filter(Organizer.id == User.id).exists())
        if value == "customer":
            return query.filter(db.session.query(Customer.id).filter(Customer.id == User.id).exists())
        return query


class UserAdminView(SecureModelView):
    column_list = [
        "id",
        "name",
        "email",
        "username",
        "provider",
        "phoneNumber",
        "createdAt",
        "role",
    ]

    column_exclude_list = [
        "password",
        "verifyCode",
        "googleID",
    ]
    form_excluded_columns = [
        "password",
        "verifyCode",
        "googleID",
    ]

    column_filters = [
        UserRoleFilter(
            User.id,
            "Loại tài khoản",
            options=[
                ("admin", "Admin"),
                ("organizer", "Organizer"),
                ("customer", "Customer"),
            ],
            data_type="select2-tags",
        )
    ]

    def _role_of_user(self, user: User) -> str:
        if AdminRole.query.get(user.id) is not None:
            return "Admin"
        if Organizer.query.get(user.id) is not None:
            return "Organizer"
        if Customer.query.get(user.id) is not None:
            return "Customer"
        return "—"

    column_formatters = {
        "role": lambda _v, context, model, name: Markup.escape(UserAdminView._role_of_user(UserAdminView, model)),
    }


class TicketAdminView(ReadOnlyModelView):
    column_exclude_list = [
        "qrCode",
        "faceEmbedding",
    ]
    form_excluded_columns = [
        "qrCode",
        "faceEmbedding",
    ]


class AdminDashboardIndexView(SecureAdminIndexView):
    def is_visible(self):
        return False

    @expose("/")
    def index(self):
        stats = {
            "user_count": db.session.query(func.count(User.id)).scalar() or 0,
            "ticket_count": db.session.query(func.count(Ticket.id)).scalar() or 0,
            "event_count": db.session.query(func.count(Event.id)).scalar() or 0,
        }

        links = {
            "users_url": url_for("admin_users.index_view"),
            "events_url": url_for("admin_events.index_view"),
            "reports_url": url_for("reports.admin_reports"),
        }

        return self.render("admin_home.html", stats=stats, links=links)


class EventAdminView(SecureModelView):
    form_extra_fields = {
        "image_file": FileField("Ảnh sự kiện (upload)"),
    }

    column_list = [
        "id",
        "title",
        "location",
        "startTime",
        "endTime",
        "status",
        "organizerId",
        "eventTypeId",
        "image",
    ]

    form_columns = [
        "title",
        "location",
        "startTime",
        "endTime",
        "status",
        "organizerId",
        "eventTypeId",
        "image_file",
        "image",
        "description",
        "hasFaceReg",
        "limitQuantity",
        "createdAt",
        "publishedAt",
    ]

    column_searchable_list = [
        "title",
        "location",
    ]

    column_default_sort = ("id", True)
    can_view_details = True

    def _fmt_dt(self, value):
        if value is None:
            return "—"
        try:
            return value.strftime("%d/%m/%Y %H:%M")
        except Exception:
            return str(value)

    def _fmt_image(self, url: str | None):
        if not url:
            return "—"
        safe_url = Markup.escape(url)
        return Markup(
            f"<img src='{safe_url}' style='height:36px;width:64px;object-fit:cover;border-radius:6px;border:1px solid rgba(0,0,0,.08)'/>"
        )

    column_formatters = {
        "startTime": lambda v, c, m, p: EventAdminView._fmt_dt(EventAdminView, getattr(m, "startTime", None)),
        "endTime": lambda v, c, m, p: EventAdminView._fmt_dt(EventAdminView, getattr(m, "endTime", None)),
        "image": lambda v, c, m, p: EventAdminView._fmt_image(EventAdminView, getattr(m, "image", None)),
    }

    def on_model_change(self, form, model, is_created):
        file_storage = getattr(form, "image_file", None)
        file_storage = getattr(file_storage, "data", None)

        if file_storage is not None and getattr(file_storage, "filename", ""):
            uploaded, error = cloudinary_service.upload_event_image(file_storage)
            if error:
                raise ValidationError(error)
            if uploaded and uploaded.get("url"):
                model.image = uploaded.get("url")

        return super().on_model_change(form, model, is_created)


class TicketTypeAdminView(SecureModelView):
    column_auto_select_related = True

    column_list = [
        "id",
        "name",
        "event_title",
        "event_type_name",
        "organizer_display",
        "price",
        "quantity",
        "saleStart",
        "saleEnd",
    ]

    column_labels = {
        "id": "ID",
        "name": "Tên loại vé",
        "event_title": "Sự kiện",
        "event_type_name": "Thể loại sự kiện",
        "organizer_display": "Nhà tổ chức",
        "price": "Giá",
        "quantity": "Số lượng",
        "saleStart": "Mở bán",
        "saleEnd": "Kết thúc bán",
    }

    column_searchable_list = [
        "name",
        "description",
    ]

    column_default_sort = ("id", True)
    can_view_details = True

    form_columns = [
        "name",
        "description",
        "price",
        "quantity",
        "saleStart",
        "saleEnd",
        "event",
    ]

    form_excluded_columns = [
        "eventId",
    ]

    def _fmt_dt(self, value):
        if value is None:
            return "—"
        try:
            return value.strftime("%d/%m/%Y %H:%M")
        except Exception:
            return str(value)

    def _fmt_money(self, value):
        if value is None:
            return "—"
        try:
            return f"{float(value):,.0f}".replace(",", ".") + " đ"
        except Exception:
            return str(value)

    column_formatters = {
        "saleStart": lambda v, c, m, p: TicketTypeAdminView._fmt_dt(TicketTypeAdminView, getattr(m, "saleStart", None)),
        "saleEnd": lambda v, c, m, p: TicketTypeAdminView._fmt_dt(TicketTypeAdminView, getattr(m, "saleEnd", None)),
        "price": lambda v, c, m, p: TicketTypeAdminView._fmt_money(TicketTypeAdminView, getattr(m, "price", None)),
    }


def init_admin(app):
    """Initialize Flask-Admin at /admin and secure it to Admin users."""

    admin = Admin(
        app,
        name="TicketHub Admin",
        url="/admin",
        index_view=AdminDashboardIndexView(url="/admin"),
    )

    admin.add_view(UserAdminView(User, db.session, name="Người dùng", endpoint="admin_users"))

    admin.add_view(
        OrganizerApprovalView(name="Duyệt nhà tổ chức", endpoint="admin_organizer_approval")
    )

    admin.add_view(EventAdminView(Event, db.session, name="Sự kiện", endpoint="admin_events"))
    admin.add_view(SecureModelView(EventType, db.session, name="Thể loại sự kiện", endpoint="admin_event_types"))
    admin.add_view(TicketTypeAdminView(TicketType, db.session, name="Loại vé", endpoint="admin_ticket_types"))

    admin.add_view(BookingAdminView(Booking, db.session, name="Đơn mua", endpoint="admin_bookings"))
    admin.add_view(PaymentAdminView(Payment, db.session, name="Thanh toán", endpoint="admin_payments"))
    admin.add_view(TicketAdminView(Ticket, db.session, name="Vé", endpoint="admin_tickets"))

    admin.add_view(AdminReportsView(name="Thống kê", endpoint="reports_admin"))
    # Keep logout as the last menu item
    admin.add_view(AdminLogoutView(name="Đăng xuất", endpoint="admin_logout"))

    return admin
