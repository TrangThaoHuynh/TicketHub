import re
import secrets
from datetime import datetime

from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from .. import db
from ..models.enums import AuthProvider, OrganizerStatus
from ..models.user import Customer, Organizer, User


EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_]{4,20}$")
PHONE_PATTERN = re.compile(r"^0\d{9,10}$")
PASSWORD_PATTERN = re.compile(r"^(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$")
VERIFY_CODE_PATTERN = re.compile(r"^\d{6}$")


def _is_valid_name(name):
    normalized_name = " ".join((name or "").split())
    if len(normalized_name) < 3:
        return False

    return all(char.isalpha() or char.isspace() for char in normalized_name)


def _verify_password(raw_password, stored_password):
    if not stored_password:
        return False

    # Support both hashed passwords (new users) and plain text (legacy data).
    if stored_password.startswith(("pbkdf2:", "scrypt:")):
        try:
            return check_password_hash(stored_password, raw_password)
        except ValueError:
            return False

    return stored_password == raw_password


def _ensure_auth_provider(provider):
    if not provider:
        return

    existing_provider = db.session.get(AuthProvider, provider)
    if existing_provider is not None:
        return

    db.session.add(AuthProvider(provider=provider))
    db.session.flush()


def _ensure_organizer_pending_status():
    if db.session.get(OrganizerStatus, "PENDING") is not None:
        return

    db.session.add(OrganizerStatus(status="PENDING"))
    db.session.flush()


def _generate_available_username(email, fallback_name=None):
    local_part = ""
    if email and "@" in email:
        local_part = email.split("@", 1)[0]

    seed = local_part or fallback_name or "google_user"
    seed = re.sub(r"[^a-zA-Z0-9_]", "_", seed).strip("_").lower()

    if not seed:
        seed = "google_user"

    if len(seed) < 4:
        seed = (seed + "user")[:4]
    if len(seed) > 20:
        seed = seed[:20]

    candidate = seed
    suffix = 1
    while User.query.filter(func.lower(User.username) == candidate.lower()).first():
        suffix_text = str(suffix)
        base = seed[: max(4, 20 - len(suffix_text))]
        candidate = f"{base}{suffix_text}"
        suffix += 1

    return candidate


def _normalize_google_profile(data):
    normalized_name = " ".join((data.get("name") or "").split())
    return {
        "google_id": (
            data.get("sub")
            or data.get("googleID")
            or data.get("googleId")
            or data.get("google_id")
            or ""
        ).strip(),
        "email": (data.get("email") or "").strip(),
        "name": normalized_name,
        "avatar": (data.get("picture") or data.get("avatar") or "").strip() or None,
    }


def authenticate_user(identity, password):
    identity = (identity or "").strip()
    password = password or ""

    if not identity or not password:
        return None, "Vui lòng nhập tài khoản và mật khẩu."

    user = User.query.filter(or_(User.username == identity, User.email == identity)).first()
    if user is None or not _verify_password(password, user.password or ""):
        return None, "Tài khoản hoặc mật khẩu không chính xác."

    return user, None

def get_user_role(user_id):
    if db.session.get(Customer, user_id) is not None:
        return "customer"
    if db.session.get(Organizer, user_id) is not None:
        return "organizer"

    return None


def assign_user_role(user_id, role):
    normalized_role = (role or "").strip().lower()
    if normalized_role not in {"customer", "organizer"}:
        return None, "Vai trò không hợp lệ. Vui lòng chọn Khách hàng hoặc Nhà tổ chức."

    user = db.session.get(User, user_id)
    if user is None:
        return None, "Tài khoản không tồn tại."

    current_role = get_user_role(user_id)
    if current_role:
        if current_role == normalized_role:
            return current_role, None
        return None, "Tài khoản đã có vai trò khác, không thể cập nhật lại."

    try:
        if normalized_role == "organizer":
            _ensure_organizer_pending_status()
            db.session.add(Organizer(id=user_id))
        else:
            db.session.add(Customer(id=user_id))

        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return None, "Không thể cập nhật vai trò tài khoản. Vui lòng thử lại."

    return normalized_role, None


def _normalize_signup_data(data):
    account_type = (data.get("account_type") or data.get("accountType") or "").strip().lower()
    google_id = (
        data.get("google_id")
        or data.get("googleID")
        or data.get("googleId")
        or ""
    ).strip() or None

    if not account_type and google_id:
        account_type = "customer"

    return {
        "name": (data.get("name") or data.get("displayName") or "").strip(),
        "email": (data.get("email") or "").strip(),
        "username": (data.get("username") or "").strip(),
        "phone": (data.get("phone") or data.get("phoneNumber") or "").strip(),
        "account_type": account_type,
        "password": data.get("password") or "",
        "confirm_password": data.get("confirm_password") or data.get("confirmPassword") or "",
        "provider": (data.get("provider") or "").strip() or None,
        "google_id": google_id,
        "avatar": (data.get("avatar") or "").strip() or None,
    }


def _validate_signup_data(payload):
    is_google_signup = bool(payload["google_id"])

    if not payload["name"]:
        return "Vui lòng nhập họ tên hoặc tên tổ chức."
    if not _is_valid_name(payload["name"]):
        return "Tên không được chứa số hoặc ký tự đặc biệt."

    if not payload["email"]:
        return "Vui lòng nhập email."
    if not EMAIL_PATTERN.match(payload["email"]):
        return "Email không đúng định dạng."

    if not payload["username"]:
        return "Vui lòng nhập tài khoản."
    if not USERNAME_PATTERN.match(payload["username"]):
        return "Tài khoản phải từ 4-20 ký tự, chỉ gồm chữ, số hoặc _."

    if payload["phone"] and not PHONE_PATTERN.match(payload["phone"]):
        return "Số điện thoại phải bắt đầu bằng 0 và có 10-11 chữ số."

    if payload["account_type"] not in {"customer", "organizer"}:
        return "Vui lòng chọn loại tài khoản: Khách hàng hoặc Nhà tổ chức."

    if not is_google_signup:
        if not payload["password"]:
            return "Vui lòng nhập mật khẩu."
        if not PASSWORD_PATTERN.match(payload["password"]):
            return "Mật khẩu phải có tối thiểu 8 ký tự, gồm chữ hoa, số và ký tự đặc biệt."

        if payload["password"] != payload["confirm_password"]:
            return "Mật khẩu nhập lại chưa khớp."

    return None


def _validate_signup_uniqueness(payload):
    email_exists = User.query.filter(func.lower(User.email) == payload["email"].lower()).first()
    if email_exists:
        return "Email đã được sử dụng."

    username_exists = User.query.filter(func.lower(User.username) == payload["username"].lower()).first()
    if username_exists:
        return "Tài khoản đã tồn tại."

    if payload["phone"]:
        phone_exists = User.query.filter(User.phoneNumber == payload["phone"]).first()
        if phone_exists:
            return "Số điện thoại đã được sử dụng."

    if payload["google_id"]:
        google_exists = User.query.filter(User.googleID == payload["google_id"]).first()
        if google_exists:
            return "Tài khoản Google đã được liên kết."

    return None


def create_user(data):
    payload = _normalize_signup_data(data or {})

    validation_error = _validate_signup_data(payload)
    if validation_error:
        return None, validation_error

    unique_error = _validate_signup_uniqueness(payload)
    if unique_error:
        return None, unique_error

    provider = payload["provider"] or ("GOOGLE" if payload["google_id"] else "LOCAL")
    password_source = payload["password"] or secrets.token_urlsafe(24)

    if provider:
        _ensure_auth_provider(provider)

    user = User(
        name=payload["name"],
        email=payload["email"],
        username=payload["username"],
        phoneNumber=payload["phone"] or None,
        password=generate_password_hash(password_source),
        avatar=payload["avatar"],
        provider=provider,
        googleID=payload["google_id"],
        createdAt=datetime.now(),
    )

    try:
        db.session.add(user)
        db.session.flush()

        if payload["account_type"] == "organizer":
            _ensure_organizer_pending_status()
            db.session.add(Organizer(id=user.id))
        else:
            db.session.add(Customer(id=user.id))

        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return None, "Thông tin đăng ký đã tồn tại. Vui lòng thử lại."

    return user, None


def login_or_create_google_user(google_profile):
    profile = _normalize_google_profile(google_profile or {})

    if not profile["google_id"]:
        return None, "Không lấy được Google ID từ phiên đăng nhập."
    if not profile["email"]:
        return None, "Không lấy được email từ Google."

    user_by_google_id = User.query.filter(User.googleID == profile["google_id"]).first()
    if user_by_google_id:
        if profile["avatar"]:
            user_by_google_id.avatar = profile["avatar"]
        if profile["name"] and not user_by_google_id.name:
            user_by_google_id.name = profile["name"]

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return None, "Không thể cập nhật thông tin tài khoản Google."

        return user_by_google_id, None

    user_by_email = User.query.filter(func.lower(User.email) == profile["email"].lower()).first()
    if user_by_email:
        user_by_email.googleID = profile["google_id"]
        if not user_by_email.provider:
            _ensure_auth_provider("GOOGLE")
            user_by_email.provider = "GOOGLE"
        if profile["avatar"]:
            user_by_email.avatar = profile["avatar"]
        if profile["name"] and not user_by_email.name:
            user_by_email.name = profile["name"]

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return None, "Không thể liên kết tài khoản Google. Vui lòng thử lại."

        return user_by_email, None

    username = _generate_available_username(profile["email"], profile["name"])
    generated_password = secrets.token_urlsafe(24)

    user = User(
        name=profile["name"] or username,
        email=profile["email"],
        username=username,
        phoneNumber=None,
        password=generate_password_hash(generated_password),
        avatar=profile["avatar"],
        provider="GOOGLE",
        googleID=profile["google_id"],
        createdAt=datetime.now(),
    )

    try:
        _ensure_auth_provider("GOOGLE")

        db.session.add(user)
        db.session.flush()
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return None, "Không thể tạo tài khoản từ Google. Vui lòng thử lại."

    return user, None


def issue_verify_code(email):
    normalized_email = (email or "").strip()

    if not normalized_email:
        return None, None, "Vui lòng nhập email."
    if not EMAIL_PATTERN.match(normalized_email):
        return None, None, "Email không đúng định dạng."

    user = User.query.filter(func.lower(User.email) == normalized_email.lower()).first()
    if user is None:
        return None, None, "Email này chưa đăng ký tài khoản."

    code = "".join(secrets.choice("0123456789") for _ in range(6))
    user.verifyCode = code

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return None, None, "Không thể tạo mã xác nhận. Vui lòng thử lại."

    return user, code, None


def clear_verify_code(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        return

    user.verifyCode = None
    db.session.commit()


def verify_forgot_password_code(email, code):
    normalized_email = (email or "").strip()
    normalized_code = (code or "").strip()

    if not normalized_email:
        return None, "Vui lòng nhập email."
    if not EMAIL_PATTERN.match(normalized_email):
        return None, "Email không đúng định dạng."

    if not normalized_code:
        return None, "Vui lòng nhập mã xác nhận."
    if not VERIFY_CODE_PATTERN.match(normalized_code):
        return None, "Mã xác nhận phải gồm 6 chữ số."

    user = User.query.filter(func.lower(User.email) == normalized_email.lower()).first()
    if user is None:
        return None, "Email này chưa đăng ký tài khoản."

    if not user.verifyCode or user.verifyCode != normalized_code:
        return None, "Mã xác nhận không chính xác."

    user.verifyCode = None
    db.session.commit()

    return user, None


def reset_password_by_user_id(user_id, password, confirm_password):
    user = db.session.get(User, user_id)
    if user is None:
        return None, "Tài khoản không tồn tại."

    password = password or ""
    confirm_password = confirm_password or ""

    if not password:
        return None, "Vui lòng nhập mật khẩu mới."
    if not PASSWORD_PATTERN.match(password):
        return None, "Mật khẩu phải có tối thiểu 8 ký tự, gồm chữ hoa, số và ký tự đặc biệt."
    if password != confirm_password:
        return None, "Nhập lại mật khẩu chưa khớp."

    user.password = generate_password_hash(password)
    user.verifyCode = None

    db.session.commit()
    return user, None