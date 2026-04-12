from flask import Blueprint, render_template, request
from ..services.event_service import get_event_types, get_home_events

main = Blueprint('main', __name__)


@main.route('/account/settings')
def account_settings():
    return render_template('account_settings.html', show_search=False)

@main.route('/')
def index():
    keyword = request.args.get("keyword")
    event_type_id = request.args.get("eventTypeId")
    start_date = request.args.get("startDate")
    end_date = request.args.get("endDate")
    location = request.args.get("location")
    price_min = request.args.get("priceMin")
    price_max = request.args.get("priceMax")
    event_types = get_event_types()
    events = get_home_events(
        keyword=keyword,
        event_type_id=event_type_id,
        start_date=start_date,
        end_date=end_date,
        location=location,
        price_min=price_min,
        price_max=price_max,
    )
    return render_template("main.html", event_types=event_types, events=events, show_search=True)