import smtplib
from urllib.parse import urlparse

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_mail import Message
from flask_login import login_user
from .. import mail, oauth
from ..services.cloudinary_service import cloudinary_service
from ..services import (
    assign_user_role,
    authenticate_user,
    clear_verify_code,
    create_user,
    get_user_role,
    issue_verify_code,
    login_or_create_google_user,
    reset_password_by_user_id,
    verify_forgot_password_code,
)

from ..models.user import Admin as AdminRole

login_bp = Blueprint(
    'login',
    __name__,
    static_folder='../templates',
    static_url_path='/assets'
)

FORGOT_PASSWORD_SESSION_KEY = 'forgot_password_user_id'
FORGOT_PASSWORD_SUBJECT = 'Ma xac nhan dat lai mat khau TicketHub'
GOOGLE_OAUTH_SCOPE = 'openid email profile'
GOOGLE_ROLE_SESSION_KEY = 'google_role_user_id'


def _request_payload():
    return request.get_json(silent=True) or request.form


def _json_error(message, status_code):
    return jsonify({'ok': False, 'message': message}), status_code


def _json_success(message, **extra):
    payload = {'ok': True, 'message': message}
    payload.update(extra)
    return jsonify(payload)


def _build_smtp_auth_error_message(exc):
    smtp_code = getattr(exc, 'smtp_code', None)
    smtp_error = getattr(exc, 'smtp_error', b'')
    if isinstance(smtp_error, bytes):
        smtp_error = smtp_error.decode('utf-8', errors='ignore').strip()
    else:
        smtp_error = str(smtp_error).strip()

    message = 'Sai MAIL_USERNAME hoac MAIL_PASSWORD SMTP (hoac chua dung App Password).'
    if smtp_code:
        message = f'{message} SMTP code: {smtp_code}.'
    if current_app.debug and smtp_error:
        message = f'{message} Detail: {smtp_error}'

    return message


def _safe_next_path(next_value: str | None) -> str | None:
    if not next_value:
        return None
    next_value = str(next_value).strip()
    if not next_value:
        return None
    parsed = urlparse(next_value)
    if parsed.scheme or parsed.netloc:
        return None
    if not next_value.startswith("/"):
        return None
    return next_value


def _validate_mail_settings():
    def _is_placeholder(value):
        text = (value or "").strip().lower()
        if not text:
            return False
        return text.startswith("your_") or "example" in text

    mail_server = (current_app.config.get('MAIL_SERVER') or '').strip()
    mail_port = current_app.config.get('MAIL_PORT')
    mail_username = (current_app.config.get('MAIL_USERNAME') or '').strip()
    mail_password = current_app.config.get('MAIL_PASSWORD') or ''
    default_sender = (current_app.config.get('MAIL_DEFAULT_SENDER') or '').strip()

    if not mail_server or not mail_port:
        return 'Chua cau hinh MAIL_SERVER hoac MAIL_PORT.'

    if not default_sender and mail_username:
        default_sender = mail_username
        current_app.config['MAIL_DEFAULT_SENDER'] = default_sender

    if _is_placeholder(mail_username) or _is_placeholder(mail_password) or _is_placeholder(default_sender):
        return 'Ban dang dung gia tri mau trong .env. Hay cap nhat MAIL_USERNAME, MAIL_PASSWORD va MAIL_DEFAULT_SENDER bang thong tin that.'

    if 'gmail' in mail_server.lower() and (not mail_username or not mail_password):
        return 'Chua cau hinh MAIL_USERNAME/MAIL_PASSWORD cho Gmail SMTP (nen dung App Password).'

    if bool(mail_username) != bool(mail_password):
        return 'Can cau hinh day du ca MAIL_USERNAME va MAIL_PASSWORD.'

    if current_app.config.get('MAIL_USE_TLS') and current_app.config.get('MAIL_USE_SSL'):
        return 'Khong the bat dong thoi MAIL_USE_TLS va MAIL_USE_SSL.'

    if 'gmail' in mail_server.lower() and mail_password:
        normalized_password = ''.join(str(mail_password).split())
        if len(normalized_password) != 16:
            return 'MAIL_PASSWORD Gmail phai la App Password gom dung 16 ky tu (co the bo khoang trang).'
        if normalized_password != str(mail_password):
            current_app.config['MAIL_PASSWORD'] = normalized_password

    if not default_sender:
        return 'Chua cau hinh MAIL_DEFAULT_SENDER (hoac MAIL_USERNAME).'

    return None


def _validate_google_settings():
    client_id = (current_app.config.get('GOOGLE_CLIENT_ID') or '').strip()
    client_secret = (current_app.config.get('GOOGLE_CLIENT_SECRET') or '').strip()
    discovery_url = (current_app.config.get('GOOGLE_DISCOVERY_URL') or '').strip()

    if not client_id or not client_secret:
        return 'Chua cau hinh GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET trong .env.'
    if not discovery_url:
        return 'Chua cau hinh GOOGLE_DISCOVERY_URL.'

    return None


def _get_google_client():
    google = oauth.create_client('google')
    if google is None:
        google = oauth.register(
            name='google',
            server_metadata_url=current_app.config['GOOGLE_DISCOVERY_URL'],
            client_id=current_app.config['GOOGLE_CLIENT_ID'],
            client_secret=current_app.config['GOOGLE_CLIENT_SECRET'],
            client_kwargs={'scope': GOOGLE_OAUTH_SCOPE},
        )

    return google


@login_bp.route('/login/google')
def login_google():
    config_error = _validate_google_settings()
    if config_error:
        flash(config_error, 'danger')
        return redirect(url_for('login.login'))

    google = _get_google_client()
    redirect_uri = (
        current_app.config.get('GOOGLE_REDIRECT_URI')
        or url_for('login.login_google_callback', _external=True)
    )

    try:
        return google.authorize_redirect(redirect_uri)
    except Exception:
        current_app.logger.exception('Failed to start Google OAuth flow')
        flash('Khong the bat dau dang nhap Google. Vui long thu lai.', 'danger')
        return redirect(url_for('login.login'))


@login_bp.route('/callback')
@login_bp.route('/login/google/callback')
def login_google_callback():
    if request.args.get('error'):
        flash('Dang nhap Google da bi huy hoac that bai.', 'danger')
        return redirect(url_for('login.login'))

    config_error = _validate_google_settings()
    if config_error:
        flash(config_error, 'danger')
        return redirect(url_for('login.login'))

    google = _get_google_client()

    try:
        token = google.authorize_access_token()
    except Exception:
        current_app.logger.exception('Failed to exchange Google OAuth token')
        flash('Không thể xác thực với Google. Vui lòng thử lại.', 'danger')
        return redirect(url_for('login.login'))

    user_info = token.get('userinfo') if isinstance(token, dict) else None
    if not user_info:
        try:
            userinfo_endpoint = (
                google.server_metadata.get('userinfo_endpoint')
                or 'https://openidconnect.googleapis.com/v1/userinfo'
            )
            user_info_response = google.get(userinfo_endpoint)
            if not user_info_response.ok:
                raise ValueError('Google userinfo endpoint returned a non-success status.')
            user_info = user_info_response.json()
        except Exception:
            current_app.logger.exception('Failed to fetch Google user profile')
            flash('Không lấy được thông tin tài khoản Google.', 'danger')
            return redirect(url_for('login.login'))

    if not isinstance(user_info, dict):
        flash('Thông tin Google trả về không hợp lệ.', 'danger')
        return redirect(url_for('login.login'))

    if user_info.get('email_verified') is False:
        flash('Email Google chưa được xác minh.', 'danger')
        return redirect(url_for('login.login'))

    user, error = login_or_create_google_user(user_info)
    if error:
        flash(error, 'danger')
        return redirect(url_for('login.login'))

    login_user(user)
    session['user_id'] = user.id
    session['username'] = user.username
    role = get_user_role(user.id)
    if role is None:
        session[GOOGLE_ROLE_SESSION_KEY] = user.id
        flash('Đăng nhập Google thành công. Vui lòng chọn vai trò sử dụng.', 'success')
        return redirect(url_for('login.google_choose_role'))

    session.pop(GOOGLE_ROLE_SESSION_KEY, None)
    flash('Đăng nhập Google thành công.', 'success')
    if AdminRole.query.get(user.id) is not None:
        return redirect(url_for('admin.index'))
    return redirect(url_for('main.index'))

@login_bp.route('/login/google/choose-role', methods=['GET', 'POST'])
def google_choose_role():
    pending_user_id = session.get(GOOGLE_ROLE_SESSION_KEY)
    current_user_id = session.get('user_id')

    if not pending_user_id or not current_user_id or pending_user_id != current_user_id:
        session.pop(GOOGLE_ROLE_SESSION_KEY, None)
        flash('Phiên chọn vai trò đã hết hạn. Vui lòng đăng nhập Google lại.', 'danger')
        return redirect(url_for('login.login'))

    existing_role = get_user_role(pending_user_id)
    if existing_role:
        session.pop(GOOGLE_ROLE_SESSION_KEY, None)
        flash('Tài khoản đã có vai trò sử dụng.', 'success')
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        selected_role = (request.form.get('role') or '').strip().lower()
        assigned_role, error = assign_user_role(pending_user_id, selected_role)
        if error:
            flash(error, 'danger')
            return render_template('Google_choose_role.html', selected_role=selected_role), 400

        session.pop(GOOGLE_ROLE_SESSION_KEY, None)
        if assigned_role == 'organizer':
            flash('Bạn đã đăng ký vai trò Người tổ chức. Tài khoản sẽ ở trạng thái chờ duyệt.', 'success')
        else:
            flash('Bạn đã đăng ký vai trò Khách hàng thành công.', 'success')

        return redirect(url_for('main.index'))

    return render_template('Google_choose_role.html')

@login_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identity = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user, error = authenticate_user(identity, password)
        if error:
            flash(error, 'danger')
            return render_template('login.html'), 401

        login_user(user)
        session['user_id'] = user.id
        session['username'] = user.username
        flash('Đăng nhập thành công.', 'success')

        next_path = _safe_next_path(request.args.get('next')) or _safe_next_path(request.form.get('next'))
        if next_path:
            return redirect(next_path)

        if AdminRole.query.get(user.id) is not None:
            return redirect(url_for('admin.index'))

        return redirect(url_for('main.index'))

    return render_template('login.html')

@login_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    form_data = {}

    if request.method == 'POST':
        avatar_url = None

        form_data = {
            'displayName': request.form.get('displayName', '').strip(),
            'email': request.form.get('email', '').strip(),
            'phone': request.form.get('phone', '').strip(),
            'accountType': request.form.get('accountType', '').strip(),
            'username': request.form.get('username', '').strip(),
        }

        avatar_file = request.files.get('avatar')
        upload_result, upload_error = cloudinary_service.upload_avatar(avatar_file)
        if upload_error:
            flash(upload_error, 'danger')
            return render_template('signUp.html', form_data=form_data), 400
        if upload_result:
            avatar_url = upload_result.get('url')

        user, error = create_user(
            {
                'displayName': form_data['displayName'],
                'email': form_data['email'],
                'phone': form_data['phone'],
                'accountType': form_data['accountType'],
                'username': form_data['username'],
                'password': request.form.get('password', ''),
                'confirmPassword': request.form.get('confirmPassword', ''),
                'avatar': avatar_url,
            }
        )

        if error:
            flash(error, 'danger')
            return render_template('signUp.html', form_data=form_data), 400

        flash('Đăng ký thành công. Vui lòng đăng nhập.', 'success')
        return redirect(url_for('login.login'))

    return render_template('signUp.html', form_data=form_data)

@login_bp.route('/forgot-password')
def forgot_password():
    session.pop(FORGOT_PASSWORD_SESSION_KEY, None)
    return render_template('forgotPassword.html')


@login_bp.route('/forgot-password/request-code', methods=['POST'])
def request_forgot_password_code():
    payload = _request_payload()
    email = (payload.get('email') or '').strip()

    mail_error = _validate_mail_settings()
    if mail_error:
        return _json_error(mail_error, 500)

    user, code, error = issue_verify_code(email)
    if error:
        return _json_error(error, 400)

    try:
        mail.send(
            Message(
                subject=FORGOT_PASSWORD_SUBJECT,
                recipients=[user.email],
                sender=current_app.config.get('MAIL_DEFAULT_SENDER'),
                body=(
                    f'Xin chào {user.name or user.username},\n\n'
                    f'Mã xác nhận của bạn là: {code}\n\n'
                    'Nhập mã này để xác nhận yêu cầu đổi mật khẩu.'
                ),
            )
        )
    except smtplib.SMTPAuthenticationError as exc:
        clear_verify_code(user.id)
        return _json_error(_build_smtp_auth_error_message(exc), 500)
    except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected):
        clear_verify_code(user.id)
        return _json_error('Không kết nối được máy chủ SMTP. Vui lòng kiểm tra MAIL_SERVER/MAIL_PORT.', 500)
    except Exception as exc:
        clear_verify_code(user.id)

        current_app.logger.exception('Failed to send forgot-password verification email')
        detail = str(exc).strip()
        if current_app.debug and detail:
            return _json_error(f'Không thể gửi email: {detail}', 500)

        return _json_error('Không thể gửi email lúc này. Vui lòng thử lại sau.', 500)

    return _json_success('Mã xác nhận đã được gửi qua email.')


@login_bp.route('/forgot-password/verify-code', methods=['POST'])
def verify_forgot_password():
    payload = _request_payload()
    email = (payload.get('email') or '').strip()
    code = (payload.get('code') or '').strip()

    user, error = verify_forgot_password_code(email, code)
    if error:
        return _json_error(error, 400)

    session[FORGOT_PASSWORD_SESSION_KEY] = user.id
    return _json_success('Xác nhận mã thành công.')


@login_bp.route('/forgot-password/reset-password', methods=['POST'])
def reset_forgot_password():
    user_id = session.get(FORGOT_PASSWORD_SESSION_KEY)
    if not user_id:
        return _json_error('Vui lòng xác nhận mã trước khi đặt mật khẩu mới.', 403)

    payload = _request_payload()
    password = payload.get('password') or payload.get('newPassword') or ''
    confirm_password = payload.get('confirmPassword') or payload.get('confirm_password') or ''

    user, error = reset_password_by_user_id(user_id, password, confirm_password)
    if error:
        return _json_error(error, 400)

    session.pop(FORGOT_PASSWORD_SESSION_KEY, None)
    return _json_success(
        'Đổi mật khẩu thành công. Vui lòng đăng nhập lại.',
        redirect=url_for('login.login'),
        username=user.username,
    )

@login_bp.route('/logout')
def logout():
    session.clear()
    flash('Đã đăng xuất.', 'success')
    return redirect(url_for('main.index'))