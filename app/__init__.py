import os
import cloudinary
from flask import Flask
from authlib.integrations.flask_client import OAuth
from flask_mail import Mail
from flask_sqlalchemy import SQLAlchemy
from .config import Config
from flask import session
import os
from dotenv import load_dotenv   

load_dotenv() 
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
    from .routes.organizer_orders import organizer_bp

    app.register_blueprint(event_bp)
    app.register_blueprint(login_bp)
    app.register_blueprint(main)
    app.register_blueprint(organizer_bp)

    @app.context_processor
    def inject_header_event_types():
        try:
            from .services.event_service import get_event_types
            return {"header_event_types": get_event_types(), "show_search": False}
        except Exception:
            return {"header_event_types": [], "show_search": False}
        
    @app.context_processor
    def inject_user():
        from .models.user import User
        
        user = None
        if 'user_id' in session:
            user = User.query.get(session['user_id'])
        return dict(current_user=user)

    return app