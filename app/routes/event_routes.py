from flask import Blueprint, jsonify
from ..services import get_events
event_bp = Blueprint('event', __name__)

@event_bp.route('/events')
def get_events_route():
    events = get_events()

    result = []
    for e in events:
        print(e.id, e.title, e.location)

        result.append({
            "id": e.id,
            "title": e.title,
            "location": e.location
        })

    return jsonify(result)