from flask import Blueprint, render_template
from ..services import get_events

main = Blueprint('main', __name__)

@main.route('/')
def index():
    return render_template("index.html")