import os
import cloudinary
from dotenv import load_dotenv
from flask import Flask, app
from flask_sqlalchemy import SQLAlchemy
from .config import Config

#Load biến môi trường từ file .env
load_dotenv()

# cấu hình Cloudinary
cloudinary.config(
    cloud_name=os.getenv("CLOUD_NAME"),
    api_key=os.getenv("API_KEY"),
    api_secret=os.getenv("API_SECRET"),
    secure=True
)

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    from . import models
    from .routes.event_routes import event_bp
    from .routes.login_routes import login_bp
    from .routes.main import main
    from .routes.order import orders_bp

    app.register_blueprint(event_bp)
    app.register_blueprint(login_bp)
    app.register_blueprint(main)
    app.register_blueprint(orders_bp)
    @app.context_processor
    def inject_header_event_types():
        try:
            from .services.event_service import get_event_types
            return {"header_event_types": get_event_types(), "show_search": False}
        except Exception:
            return {"header_event_types": [], "show_search": False}

    return app