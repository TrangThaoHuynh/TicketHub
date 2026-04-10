from datetime import datetime

import pytest
from sqlalchemy.pool import StaticPool
from werkzeug.security import check_password_hash

from app import create_app, db
from app.config import Config
from app.models.enums import AuthProvider, OrganizerStatus
from app.models.user import Customer, User
from app.services.user_service import (
    authenticate_user,
    create_user,
    issue_verify_code,
    login_or_create_google_user,
    reset_password_by_user_id,
    verify_forgot_password_code,
)


@pytest.fixture()
def app(monkeypatch):
    monkeypatch.setattr(Config, "TESTING", True, raising=False)
    monkeypatch.setattr(Config, "SQLALCHEMY_DATABASE_URI", "sqlite://", raising=False)
    monkeypatch.setattr(
        Config,
        "SQLALCHEMY_ENGINE_OPTIONS",
        {
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool,
        },
        raising=False,
    )

    app = create_app()
    app.config.update(TESTING=True)

    with app.app_context():
        db.create_all()
        if db.session.get(OrganizerStatus, "PENDING") is None:
            db.session.add(OrganizerStatus(status="PENDING"))
        db.session.commit()

        yield app

        db.session.remove()
        db.drop_all()


def _signup_payload(
    *,
    display_name="Nguyen Van A",
    email="demo@example.com",
    username="demo_user",
    phone="0912345678",
    account_type="customer",
    password="Strong@123",
    confirm_password="Strong@123",
):
    return {
        "displayName": display_name,
        "email": email,
        "username": username,
        "phone": phone,
        "accountType": account_type,
        "password": password,
        "confirmPassword": confirm_password,
    }


# ================= CREATE USER =================
def test_create_user_sets_local_provider_and_customer(app):
    with app.app_context():
        user, error = create_user(_signup_payload())

        assert error is None
        assert user is not None
        assert user.provider == "LOCAL"
        assert user.googleID is None
        assert check_password_hash(user.password, "Strong@123")
        assert db.session.get(Customer, user.id) is not None
        assert db.session.get(AuthProvider, "LOCAL") is not None


def test_create_user_rejects_duplicate_email(app):
    with app.app_context():
        user_1, error_1 = create_user(_signup_payload())
        assert error_1 is None

        user_2, error_2 = create_user(
            _signup_payload(
                username="another_user",
                phone="0987654321",
            )
        )

        assert user_2 is None
        assert error_2 is not None
        assert "đã được sử dụng" in error_2.lower()


# ================= AUTH =================
def test_authenticate_user_with_email_and_password(app):
    with app.app_context():
        created_user, _ = create_user(_signup_payload())

        user, error = authenticate_user(created_user.email, "Strong@123")

        assert error is None
        assert user.id == created_user.id


def test_authenticate_user_supports_legacy_plain_text_password(app):
    with app.app_context():
        db.session.add(AuthProvider(provider="LOCAL"))
        db.session.flush()

        user = User(
            name="Legacy User",
            email="legacy@example.com",
            username="legacy_user",
            password="Legacy@123",
            createdAt=datetime.now(),
            provider="LOCAL",
        )
        db.session.add(user)
        db.session.flush()
        db.session.add(Customer(id=user.id))
        db.session.commit()

        authenticated_user, error = authenticate_user("legacy_user", "Legacy@123")

        assert error is None
        assert authenticated_user.id == user.id


# ================= GOOGLE LOGIN =================
def test_login_or_create_google_user_creates_customer_on_first_login(app):
    with app.app_context():
        profile = {
            "sub": "google-sub-001",
            "email": "google.user@example.com",
            "name": "Google User",
            "picture": "https://image.example.com/avatar-1.png",
        }

        user, error = login_or_create_google_user(profile)

        assert error is None
        assert user.provider == "GOOGLE"
        assert user.googleID == "google-sub-001"
        assert db.session.get(Customer, user.id) is not None
        assert db.session.get(AuthProvider, "GOOGLE") is not None


def test_login_or_create_google_user_reuses_existing_google_account(app):
    with app.app_context():
        profile = {
            "sub": "google-sub-002",
            "email": "repeat.google@example.com",
            "name": "Repeat Google",
            "picture": "https://image.example.com/avatar-old.png",
        }

        first_user, _ = login_or_create_google_user(profile)

        profile["picture"] = "https://image.example.com/avatar-new.png"
        second_user, _ = login_or_create_google_user(profile)

        assert second_user.id == first_user.id
        assert User.query.count() == 1
        assert second_user.avatar == "https://image.example.com/avatar-new.png"


def test_login_or_create_google_user_links_by_existing_email(app):
    with app.app_context():
        local_user, _ = create_user(
            _signup_payload(
                email="linked.email@example.com",
                username="linked_email_user",
                phone="0933333333",
            )
        )

        profile = {
            "sub": "google-sub-linked",
            "email": "linked.email@example.com",
            "name": "Linked Account",
            "picture": "https://image.example.com/avatar-link.png",
        }

        linked_user, error = login_or_create_google_user(profile)

        assert error is None
        assert linked_user.id == local_user.id
        assert linked_user.googleID == "google-sub-linked"
        assert linked_user.provider == "LOCAL"


# ================= VERIFY CODE =================
def test_issue_and_verify_code_flow(app):
    with app.app_context():
        user, _ = create_user(
            _signup_payload(
                email="verify.flow@example.com",
                username="verify_flow_user",
                phone="0944444444",
            )
        )

        issued_user, code, _ = issue_verify_code(user.email)

        assert issued_user.id == user.id
        assert len(code) == 6
        assert code.isdigit()

        verified_user, error = verify_forgot_password_code(user.email, code)

        assert error is None
        assert verified_user.id == user.id

        reloaded = db.session.get(User, user.id)
        assert reloaded.verifyCode is None


# ================= RESET PASSWORD =================
def test_reset_password_by_user_id_updates_password_hash(app):
    with app.app_context():
        user, _ = create_user(
            _signup_payload(
                email="reset.pass@example.com",
                username="reset_pass_user",
                phone="0955555555",
            )
        )

        old_hash = user.password

        updated_user, error = reset_password_by_user_id(
            user.id,
            "NewStrong@123",
            "NewStrong@123",
        )

        assert error is None
        assert updated_user.password != old_hash
        assert check_password_hash(updated_user.password, "NewStrong@123")

        # verify code should be cleared
        assert updated_user.verifyCode is None