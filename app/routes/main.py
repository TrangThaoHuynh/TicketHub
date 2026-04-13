from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from flask_login import login_required, current_user

from .. import db
from ..models.user import Organizer
from ..models.user import User
from ..services.cloudinary_service import cloudinary_service
from ..services.event_service import get_event_types, get_home_events
from ..services.user_service import update_user_profile, change_password

main = Blueprint(
    'main',
    __name__,
    static_folder='../templates',
    static_url_path='/main-assets'
)


@main.route('/account/settings')
@login_required
def account_settings():
    return render_template('account_settings.html', show_search=False)


@main.route('/account/settings/profile', methods=['POST'])
@login_required
def account_update_profile():
    name = request.form.get('name')
    email = request.form.get('email')
    phone_number = request.form.get('phoneNumber')

    if (getattr(current_user, 'provider', None) or '').strip().upper() == 'GOOGLE':
        # Google accounts should not be able to change email from this page.
        email = getattr(current_user, 'email', None)

    user, error = update_user_profile(current_user.id, name, email, phone_number)
    if error:
        flash(error, 'danger')
        return redirect(url_for('main.account_settings'))

    # Keep session in sync with display name changes.
    session['user_id'] = user.id
    session['username'] = user.username
    flash('Cập nhật thông tin thành công.', 'success')
    return redirect(url_for('main.account_settings'))


@main.route('/account/settings/password', methods=['POST'])
@login_required
def account_change_password():
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    _, error = change_password(current_user.id, current_password, new_password, confirm_password)
    if error:
        flash(error, 'danger')
        return redirect(url_for('main.account_settings'))

    flash('Đổi mật khẩu thành công.', 'success')
    return redirect(url_for('main.account_settings'))


@main.route('/account/settings/avatar', methods=['POST'])
@login_required
def account_update_avatar():
    if (getattr(current_user, 'provider', None) or '').strip().upper() == 'GOOGLE':
        flash('Tài khoản Google không hỗ trợ đổi ảnh đại diện tại đây.', 'danger')
        return redirect(url_for('main.account_settings'))

    avatar_file = request.files.get('avatar')
    upload_result, upload_error = cloudinary_service.upload_avatar(avatar_file)
    if upload_error:
        flash(upload_error, 'danger')
        return redirect(url_for('main.account_settings'))

    if not upload_result:
        flash('Vui lòng chọn ảnh để upload.', 'danger')
        return redirect(url_for('main.account_settings'))

    user = db.session.get(User, current_user.id)
    if user is None:
        flash('Tài khoản không tồn tại.', 'danger')
        return redirect(url_for('main.account_settings'))

    user.avatar = upload_result.get('url')
    db.session.commit()
    flash('Cập nhật ảnh đại diện thành công.', 'success')
    return redirect(url_for('main.account_settings'))

@main.route('/')
def index():
    user_id = session.get('user_id')
    organizer = db.session.get(Organizer, user_id) if user_id else None
    is_organizer = organizer is not None

    keyword = request.args.get("keyword")
    event_type_id = request.args.get("eventTypeId")
    start_date = request.args.get("startDate")
    end_date = request.args.get("endDate")
    location = request.args.get("location")
    price_min = request.args.get("priceMin")
    price_max = request.args.get("priceMax")
    event_types = get_event_types()
    events = get_home_events(
        keyword=keyword,
        event_type_id=event_type_id,
        start_date=start_date,
        end_date=end_date,
        location=location,
        price_min=price_min,
        price_max=price_max,
        organizer_id=user_id if is_organizer else None,
    )
    return render_template(
        "main.html",
        event_types=event_types,
        events=events,
        show_search=True,
        is_organizer=is_organizer,
    )
