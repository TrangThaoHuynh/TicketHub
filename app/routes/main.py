from flask import Blueprint, render_template, request
from ..services.event_service import get_event_types, get_home_events

main = Blueprint('main', __name__)

@main.route('/')
def index():
    keyword = request.args.get("keyword")
    event_type_id = request.args.get("eventTypeId")
    event_types = get_event_types()
    events = get_home_events(keyword=keyword, event_type_id=event_type_id)
    return render_template("main.html", event_types=event_types, events=events)