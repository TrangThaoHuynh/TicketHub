import pytest
from app import create_app, db
from sqlalchemy.pool import StaticPool


@pytest.fixture()
def app():
    app = create_app()
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite://",
        SQLALCHEMY_ENGINE_OPTIONS={
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool,
        },
    )

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()