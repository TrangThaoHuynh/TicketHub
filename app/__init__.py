import os
import cloudinary
from dotenv import load_dotenv
from flask import Flask
from authlib.integrations.flask_client import OAuth
from flask_mail import Mail
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from sqlalchemy.exc import SQLAlchemyError
from .config import Config
from flask import session

# Load biến môi trường
load_dotenv()

# Configure Cloudinary
cloudinary_url = os.getenv("CLOUDINARY_URL")
cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME") or os.getenv("CLOUD_NAME")
api_key = os.getenv("CLOUDINARY_API_KEY") or os.getenv("API_KEY")
api_secret = os.getenv("CLOUDINARY_API_SECRET") or os.getenv("API_SECRET")

if cloudinary_url:
    cloudinary.config(cloudinary_url=cloudinary_url, secure=True)
elif cloud_name and api_key and api_secret:
    cloudinary.config(cloud_name=cloud_name, api_key=api_key, api_secret=api_secret, secure=True)

db = SQLAlchemy()
mail = Mail()
oauth = OAuth()
login_manager = LoginManager()

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
        BookingStatus: ["PENDING", "SUCCESS", "FAILED"],
        OrganizerStatus: ["PENDING", "APPROVED", "REJECTED"],
        PaymentStatus: ["SUCCESS", "FAILED"],
        TicketStatus: ["PENDING", "VALID", "USED", "CANCELLED"],
        EventStatus: ["PENDING", "PUBLISHED", "FINISHED", "CANCELLED"],
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
    login_manager.init_app(app) 
    login_manager.login_view = 'login.login'
    
    @login_manager.user_loader
    def load_user(user_id: str):
        from .models.user import User
        return User.query.get(int(user_id))
    
    from . import models
    from .routes.event_routes import event_bp
    from .routes.auth_routes import login_bp
    from .routes.main import main
    from .routes.organizer_orders import organizer_bp
    from .routes.order import orders_bp
    from .routes.report_routes import report_bp

    app.register_blueprint(event_bp)
    app.register_blueprint(login_bp)
    app.register_blueprint(main)
    app.register_blueprint(organizer_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(report_bp)
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
        
    @app.context_processor
    def inject_user():
        from .models.user import User, Admin, Organizer, Customer

        # Mặc định chưa có user đăng nhập
        user = None

        # Cờ kiểm tra role để dùng trong template
        is_admin = False
        is_organizer = False
        is_customer = False

        # Nếu session có user_id thì lấy user hiện tại
        if 'user_id' in session:
            user = User.query.get(session['user_id'])

            # Nếu tìm thấy user thì kiểm tra user thuộc role nào
            if user:
                is_admin = Admin.query.get(user.id) is not None
                is_organizer = Organizer.query.get(user.id) is not None
                is_customer = Customer.query.get(user.id) is not None

        # Trả biến ra toàn bộ template
        return dict(
            current_user=user,
            is_admin=is_admin,
            is_organizer=is_organizer,
            is_customer=is_customer,
        )
    return app