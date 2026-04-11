import os
import cloudinary
from flask import Flask
from authlib.integrations.flask_client import OAuth
from flask_mail import Mail
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import SQLAlchemyError
from .config import Config

# Configure Cloudinary if credentials exist in .env.
cloudinary_url = os.getenv("CLOUDINARY_URL")
cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME") or os.getenv("CLOUD_NAME")
api_key = os.getenv("CLOUDINARY_API_KEY") or os.getenv("API_KEY")
api_secret = os.getenv("CLOUDINARY_API_SECRET") or os.getenv("API_SECRET")

if cloudinary_url:
    cloudinary.config(
        cloudinary_url=cloudinary_url,
        secure=True,
    )
elif cloud_name and api_key and api_secret:
    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
        secure=True,
    )

db = SQLAlchemy()
mail = Mail()
oauth = OAuth()


def _seed_lookup_tables():
    from .models.enums import (
        AuthProvider,
        BookingStatus,
        EventStatus,
        OrganizerStatus,
        PaymentStatus,
        TicketStatus,
    )

    status_defaults = {
        BookingStatus: ["PENDING"],
        OrganizerStatus: ["PENDING", "APPROVED", "REJECTED"],
        PaymentStatus: ["PENDING", "SUCCESS", "FAILED"],
        TicketStatus: ["PENDING", "ACTIVE", "USED", "CANCELLED"],
        EventStatus: ["DRAFT", "PUBLISHED", "CANCELLED"],
    }

    changed = False

    for model, values in status_defaults.items():
        for value in values:
            if db.session.get(model, value) is None:
                db.session.add(model(status=value))
                changed = True

    for provider in ["LOCAL", "GOOGLE"]:
        if db.session.get(AuthProvider, provider) is None:
            db.session.add(AuthProvider(provider=provider))
            changed = True

    if changed:
        db.session.commit()


def _bootstrap_database(app):
    with app.app_context():
        db.create_all()
        _seed_lookup_tables()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    mail.init_app(app)
    oauth.init_app(app)

    from . import models
    from .routes.event_routes import event_bp
    from .routes.auth_routes import login_bp
    from .routes.main import main

    app.register_blueprint(event_bp)
    app.register_blueprint(login_bp)
    app.register_blueprint(main)

    if app.config.get("DB_AUTO_INIT", True):
        try:
            _bootstrap_database(app)
        except SQLAlchemyError:
            app.logger.exception("Database bootstrap failed")

    @app.context_processor
    def inject_header_event_types():
        try:
            from .services.event_service import get_event_types
            return {"header_event_types": get_event_types(), "show_search": False}
        except Exception:
            return {"header_event_types": [], "show_search": False}

    return app