from flask import Blueprint, render_template, request, session

from .. import db
from ..models.user import Organizer
from ..services.event_service import get_event_types, get_home_events

main = Blueprint(
    'main',
    __name__,
    static_folder='../templates',
    static_url_path='/main-assets'
)


@main.route('/account/settings')
def account_settings():
    return render_template('account_settings.html', show_search=False)

@main.route('/')
def index():
    user_id = session.get('user_id')
    organizer = db.session.get(Organizer, user_id) if user_id else None
    is_organizer = organizer is not None

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
        organizer_id=user_id if is_organizer else None,
    )
    return render_template(
        "main.html",
        event_types=event_types,
        events=events,
        show_search=True,
        is_organizer=is_organizer,
    )
