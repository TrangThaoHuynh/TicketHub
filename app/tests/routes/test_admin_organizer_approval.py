from datetime import datetime

from app import db
from app.models.enums import OrganizerStatus
from app.models.user import Admin, Organizer, User
import app.services.organizer_approval_service as organizer_approval_service


def _seed_organizer_statuses():
    for value in ["PENDING", "APPROVED", "REJECTED"]:
        if db.session.get(OrganizerStatus, value) is None:
            db.session.add(OrganizerStatus(status=value))
    db.session.commit()


def _login_as_admin(client, admin_user_id: int):
    with client.session_transaction() as sess:
        sess["user_id"] = admin_user_id


def test_organizer_approval_requires_admin(app):
    client = app.test_client()

    res = client.get("/admin/admin_organizer_approval/", follow_redirects=False)
    assert res.status_code in {301, 302}
    assert "/login" in (res.headers.get("Location") or "")


def test_organizer_approval_lists_organizers(app):
    client = app.test_client()

    with app.app_context():
        _seed_organizer_statuses()

        admin_user = User(
            name="Admin",
            email="admin@example.com",
            username="admin",
            password="x",
            createdAt=datetime.utcnow(),
        )
        db.session.add(admin_user)
        db.session.flush()
        db.session.add(Admin(id=admin_user.id))

        org_user = User(
            name="Org A",
            email="orga@example.com",
            username="orga",
            password="x",
            phoneNumber="0123456789",
            createdAt=datetime.utcnow(),
        )
        db.session.add(org_user)
        db.session.flush()
        db.session.add(Organizer(id=org_user.id, status="PENDING"))

        db.session.commit()

        _login_as_admin(client, admin_user.id)

    res = client.get("/admin/admin_organizer_approval/", follow_redirects=False)
    assert res.status_code == 200
    assert "Duyệt nhà tổ chức".encode("utf-8") in res.data
    assert b"Org A" in res.data


def test_organizer_approval_detail_requires_admin(app):
    client = app.test_client()

    res = client.get("/admin/admin_organizer_approval/detail/1", follow_redirects=False)
    assert res.status_code in {301, 302}
    assert "/login" in (res.headers.get("Location") or "")


def test_admin_can_view_organizer_approval_detail(app):
    client = app.test_client()

    org_user_id = None

    with app.app_context():
        _seed_organizer_statuses()

        admin_user = User(
            name="Admin",
            email="admin_detail@example.com",
            username="admin_detail",
            password="x",
            createdAt=datetime.utcnow(),
        )
        db.session.add(admin_user)
        db.session.flush()
        db.session.add(Admin(id=admin_user.id))

        org_user = User(
            name="Org Detail",
            email="orgdetail@example.com",
            username="orgdetail",
            password="x",
            phoneNumber="0999999999",
            avatar="https://example.com/avatar.png",
            createdAt=datetime.utcnow(),
        )
        db.session.add(org_user)
        db.session.flush()
        db.session.add(Organizer(id=org_user.id, status="PENDING"))

        org_user_id = org_user.id

        db.session.commit()

        _login_as_admin(client, admin_user.id)

    assert org_user_id is not None
    res = client.get(f"/admin/admin_organizer_approval/detail/{org_user_id}", follow_redirects=False)
    assert res.status_code == 200
    assert "Chi tiết nhà tổ chức".encode("utf-8") in res.data
    assert b"Org Detail" in res.data
    assert b"orgdetail@example.com" in res.data
    assert b"0999999999" in res.data
    assert b"PENDING" in res.data
    assert "Mở ảnh".encode("utf-8") in res.data


def test_admin_organizer_approval_detail_404_when_missing(app):
    client = app.test_client()

    with app.app_context():
        _seed_organizer_statuses()

        admin_user = User(
            name="Admin",
            email="admin_missing@example.com",
            username="admin_missing",
            password="x",
            createdAt=datetime.utcnow(),
        )
        db.session.add(admin_user)
        db.session.flush()
        db.session.add(Admin(id=admin_user.id))
        db.session.commit()

        _login_as_admin(client, admin_user.id)

    res = client.get("/admin/admin_organizer_approval/detail/999999", follow_redirects=False)
    assert res.status_code == 404


def test_admin_can_approve_pending_organizer(app, monkeypatch):
    client = app.test_client()

    org_user_id = None
    sent = []

    def _fake_send_email(*, organizer_user, new_status):
        sent.append((organizer_user.id, new_status))
        return True

    monkeypatch.setattr(organizer_approval_service, "send_organizer_status_email", _fake_send_email)

    with app.app_context():
        _seed_organizer_statuses()

        admin_user = User(
            name="Admin",
            email="admin2@example.com",
            username="admin2",
            password="x",
            createdAt=datetime.utcnow(),
        )
        db.session.add(admin_user)
        db.session.flush()
        db.session.add(Admin(id=admin_user.id))

        org_user = User(
            name="Org B",
            email="orgb@example.com",
            username="orgb",
            password="x",
            createdAt=datetime.utcnow(),
        )
        db.session.add(org_user)
        db.session.flush()
        db.session.add(Organizer(id=org_user.id, status="PENDING"))

        org_user_id = org_user.id

        db.session.commit()

        _login_as_admin(client, admin_user.id)

    assert org_user_id is not None
    res = client.post(f"/admin/admin_organizer_approval/approve/{org_user_id}", follow_redirects=False)
    assert res.status_code in {301, 302}

    with app.app_context():
        organizer = db.session.get(Organizer, org_user_id)
        assert organizer is not None
        assert organizer.status == "APPROVED"

    assert sent == [(org_user_id, "APPROVED")]


def test_admin_can_approve_rejected_organizer(app):
    client = app.test_client()

    org_user_id = None

    with app.app_context():
        _seed_organizer_statuses()

        admin_user = User(
            name="Admin",
            email="admin3@example.com",
            username="admin3",
            password="x",
            createdAt=datetime.utcnow(),
        )
        db.session.add(admin_user)
        db.session.flush()
        db.session.add(Admin(id=admin_user.id))

        org_user = User(
            name="Org C",
            email="orgc@example.com",
            username="orgc",
            password="x",
            createdAt=datetime.utcnow(),
        )
        db.session.add(org_user)
        db.session.flush()
        db.session.add(Organizer(id=org_user.id, status="REJECTED"))

        org_user_id = org_user.id

        db.session.commit()

        _login_as_admin(client, admin_user.id)

    assert org_user_id is not None
    res = client.post(f"/admin/admin_organizer_approval/approve/{org_user_id}", follow_redirects=False)
    assert res.status_code in {301, 302}

    with app.app_context():
        organizer = db.session.get(Organizer, org_user_id)
        assert organizer is not None
        assert organizer.status == "APPROVED"


def test_admin_can_reject_pending_organizer(app, monkeypatch):
    client = app.test_client()

    org_user_id = None
    sent = []

    def _fake_send_email(*, organizer_user, new_status):
        sent.append((organizer_user.id, new_status))
        return True

    monkeypatch.setattr(organizer_approval_service, "send_organizer_status_email", _fake_send_email)

    with app.app_context():
        _seed_organizer_statuses()

        admin_user = User(
            name="Admin",
            email="admin4@example.com",
            username="admin4",
            password="x",
            createdAt=datetime.utcnow(),
        )
        db.session.add(admin_user)
        db.session.flush()
        db.session.add(Admin(id=admin_user.id))

        org_user = User(
            name="Org D",
            email="orgd@example.com",
            username="orgd",
            password="x",
            createdAt=datetime.utcnow(),
        )
        db.session.add(org_user)
        db.session.flush()
        db.session.add(Organizer(id=org_user.id, status="PENDING"))

        org_user_id = org_user.id

        db.session.commit()

        _login_as_admin(client, admin_user.id)

    assert org_user_id is not None
    res = client.post(f"/admin/admin_organizer_approval/reject/{org_user_id}", follow_redirects=False)
    assert res.status_code in {301, 302}

    with app.app_context():
        organizer = db.session.get(Organizer, org_user_id)
        assert organizer is not None
        assert organizer.status == "REJECTED"

    assert sent == [(org_user_id, "REJECTED")]
