from app import db
from app.models.enums import AuthProvider, OrganizerStatus
from app.models.user import Organizer, User
from app.services.user_service import create_user, login_or_create_google_user


def _seed_organizer_statuses():
    for value in ["PENDING", "APPROVED", "REJECTED"]:
        if db.session.get(OrganizerStatus, value) is None:
            db.session.add(OrganizerStatus(status=value))

    for provider in ["LOCAL", "GOOGLE"]:
        if db.session.get(AuthProvider, provider) is None:
            db.session.add(AuthProvider(provider=provider))

    db.session.commit()


def _signup_payload(*, display_name, email, username, phone, account_type="organizer"):
    return {
        "displayName": display_name,
        "email": email,
        "username": username,
        "phone": phone,
        "accountType": account_type,
        "password": "Strong@123",
        "confirmPassword": "Strong@123",
    }


class _FakeGoogleClient:
    server_metadata = {}

    def authorize_access_token(self):
        return {
            "userinfo": {
                "sub": "fake-google-sub",
                "email": "fake-google@example.com",
                "email_verified": True,
            }
        }


def test_local_login_blocks_pending_organizer(app):
    client = app.test_client()

    with app.app_context():
        _seed_organizer_statuses()
        user, error = create_user(
            _signup_payload(
                display_name="Pending Organizer",
                email="pending.local@example.com",
                username="pending_local_org",
                phone="0911111111",
            )
        )
        assert error is None
        assert user is not None

    response = client.post(
        "/login",
        data={"username": "pending_local_org", "password": "Strong@123"},
        follow_redirects=False,
    )

    assert response.status_code == 403
    assert "Vui lòng chờ xét duyệt thông tin từ quản trị viên.".encode("utf-8") in response.data


def test_local_login_blocks_rejected_organizer(app):
    client = app.test_client()

    with app.app_context():
        _seed_organizer_statuses()
        user, error = create_user(
            _signup_payload(
                display_name="Rejected Organizer",
                email="rejected.local@example.com",
                username="rejected_local_org",
                phone="0922222222",
            )
        )
        assert error is None
        assert user is not None

        organizer = db.session.get(Organizer, user.id)
        assert organizer is not None
        organizer.status = "REJECTED"
        db.session.commit()

    response = client.post(
        "/login",
        data={"username": "rejected_local_org", "password": "Strong@123"},
        follow_redirects=False,
    )

    assert response.status_code == 403
    assert "Tài khoản này đã bị từ chối, hãy phản hồi qua email quản trị viên để biết thêm thông tin chi tiết.".encode("utf-8") in response.data


def test_google_callback_blocks_pending_organizer(monkeypatch, app):
    client = app.test_client()

    with app.app_context():
        _seed_organizer_statuses()
        user, error = create_user(
            {
                "displayName": "Pending Google Organizer",
                "email": "pending.google@example.com",
                "username": "pending_google_org",
                "phone": "0933333333",
                "accountType": "organizer",
                "googleId": "pending-google-sub",
                "provider": "GOOGLE",
            }
        )
        assert error is None
        assert user is not None
        user_id = user.id

    import app.routes.auth_routes as auth_routes

    monkeypatch.setattr(auth_routes, "_validate_google_settings", lambda: None)
    monkeypatch.setattr(auth_routes, "_get_google_client", lambda: _FakeGoogleClient())
    monkeypatch.setattr(
        auth_routes,
        "login_or_create_google_user",
        lambda _profile: (db.session.get(User, user_id), None),
    )

    response = client.get("/login/google/callback", follow_redirects=True)

    assert response.status_code == 200
    assert "Vui lòng chờ xét duyệt thông tin từ quản trị viên.".encode("utf-8") in response.data

    with client.session_transaction() as session_data:
        assert session_data.get("user_id") is None


def test_google_callback_blocks_rejected_organizer(monkeypatch, app):
    client = app.test_client()

    with app.app_context():
        _seed_organizer_statuses()
        user, error = create_user(
            {
                "displayName": "Rejected Google Organizer",
                "email": "rejected.google@example.com",
                "username": "rejected_google_org",
                "phone": "0944444444",
                "accountType": "organizer",
                "googleId": "rejected-google-sub",
                "provider": "GOOGLE",
            }
        )
        assert error is None
        assert user is not None

        organizer = db.session.get(Organizer, user.id)
        assert organizer is not None
        organizer.status = "REJECTED"
        db.session.commit()

        user_id = user.id

    import app.routes.auth_routes as auth_routes

    monkeypatch.setattr(auth_routes, "_validate_google_settings", lambda: None)
    monkeypatch.setattr(auth_routes, "_get_google_client", lambda: _FakeGoogleClient())
    monkeypatch.setattr(
        auth_routes,
        "login_or_create_google_user",
        lambda _profile: (db.session.get(User, user_id), None),
    )

    response = client.get("/login/google/callback", follow_redirects=True)

    assert response.status_code == 200
    assert "Tài khoản này đã bị từ chối, hãy phản hồi qua email quản trị viên để biết thêm thông tin chi tiết.".encode("utf-8") in response.data

    with client.session_transaction() as session_data:
        assert session_data.get("user_id") is None


def test_google_first_time_choose_organizer_redirects_to_login_with_pending_notice(app):
    client = app.test_client()

    with app.app_context():
        _seed_organizer_statuses()
        user, error = login_or_create_google_user(
            {
                "sub": "choose-role-google-sub",
                "email": "choose.role.google@example.com",
                "name": "Choose Role Google",
            }
        )
        assert error is None
        assert user is not None
        user_id = user.id

    with client.session_transaction() as session_data:
        session_data["user_id"] = user_id
        session_data["google_role_user_id"] = user_id
        session_data["_user_id"] = str(user_id)

    response = client.post(
        "/login/google/choose-role",
        data={"role": "organizer"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Vui lòng chờ xét duyệt thông tin từ quản trị viên.".encode("utf-8") in response.data

    with client.session_transaction() as session_data:
        assert session_data.get("user_id") is None
        assert session_data.get("google_role_user_id") is None

    with app.app_context():
        organizer = db.session.get(Organizer, user_id)
        assert organizer is not None
        assert organizer.status == "PENDING"
