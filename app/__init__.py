from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from .config import Config

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    from . import models
    from .routes.event_routes import event_bp
    from .routes.login_routes import login_bp

    app.register_blueprint(event_bp)
    app.register_blueprint(login_bp)

    return app