from datetime import datetime

from app import db
from app.models.enums import OrganizerStatus
from app.models.user import Organizer, User
from app.services.organizer_approval_service import (
    list_organizers_for_approval,
    set_organizer_status,
)


def _seed_organizer_statuses():
    for value in ["PENDING", "APPROVED", "REJECTED"]:
        if db.session.get(OrganizerStatus, value) is None:
            db.session.add(OrganizerStatus(status=value))
    db.session.commit()


def test_set_organizer_status_noop_returns_error(app):
    with app.app_context():
        _seed_organizer_statuses()

        user = User(
            name="Org",
            email="org_noop@example.com",
            username="org_noop",
            password="x",
            createdAt=datetime.utcnow(),
        )
        db.session.add(user)
        db.session.flush()
        db.session.add(Organizer(id=user.id, status="APPROVED"))
        db.session.commit()

        err = set_organizer_status(organizer_id=user.id, new_status="APPROVED")
        assert err is not None


def test_list_organizers_for_approval_filters_by_status_and_query(app):
    with app.app_context():
        _seed_organizer_statuses()

        user_pending = User(
            name="Org Pending",
            email="pending@example.com",
            username="org_pending",
            password="x",
            createdAt=datetime.utcnow(),
            phoneNumber="0111111111",
        )
        user_approved = User(
            name="Org Approved",
            email="approved@example.com",
            username="org_approved",
            password="x",
            createdAt=datetime.utcnow(),
            phoneNumber="0222222222",
        )
        db.session.add_all([user_pending, user_approved])
        db.session.flush()
        db.session.add(Organizer(id=user_pending.id, status="PENDING"))
        db.session.add(Organizer(id=user_approved.id, status="APPROVED"))
        db.session.commit()

        rows_all = list_organizers_for_approval(status="all")
        assert {row.username for row in rows_all} >= {"org_pending", "org_approved"}

        rows_pending = list_organizers_for_approval(status="pending")
        assert {row.username for row in rows_pending} == {"org_pending"}

        rows_query = list_organizers_for_approval(q="022222", status="all")
        assert {row.username for row in rows_query} == {"org_approved"}
