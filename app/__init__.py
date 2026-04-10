from flask import Flask
from authlib.integrations.flask_client import OAuth
from flask_mail import Mail
from flask_sqlalchemy import SQLAlchemy
from .config import Config

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

    app.register_blueprint(event_bp)
    app.register_blueprint(login_bp)
    app.register_blueprint(main)

    return app