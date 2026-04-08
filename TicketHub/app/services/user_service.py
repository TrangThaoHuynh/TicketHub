from ..models.user import User
from .. import db
from datetime import datetime

def create_user(data):
    user = User(
        name=data.get("name"),
        email=data.get("email"),
        username=data.get("username"),
        password=data.get("password"),
        provider="LOCAL",
        createdAt=datetime.now()
    )

    db.session.add(user)
    db.session.commit()

    return user