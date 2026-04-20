import os
import pickle
from pathlib import Path

from .. import db
from ..models.search_history import SearchHistory
from ..models.event import Event
from ..models.event_type import EventType
from ..models.ticket_type import TicketType
from ..models.enums import EventStatus
from .event_service import sync_expired_events_to_finished
from sqlalchemy import func, or_, case

# Cache model
_model_cache = None
_vectorizer_cache = None
_label_encoder_cache = None
_model_loaded = False

def _get_project_root():
    """Lấy đường dẫn thư mục gốc"""
    return Path(__file__).parent.parent.parent

def _load_ml_model():
    
    global _model_cache, _vectorizer_cache, _label_encoder_cache, _model_loaded
    
    if _model_loaded:
        return _model_cache, _vectorizer_cache, _label_encoder_cache
    
    try:
        root = _get_project_root()
        
        model_path = root / 'model.pkl'
        vectorizer_path = root / 'vectorizer.pkl'
        label_encoder_path = root / 'label_encoder.pkl'
        
        if not model_path.exists():
            return None, None, None
        
        with open(model_path, 'rb') as f:
            _model_cache = pickle.load(f)
        
        with open(vectorizer_path, 'rb') as f:
            _vectorizer_cache = pickle.load(f)
        
        with open(label_encoder_path, 'rb') as f:
            _label_encoder_cache = pickle.load(f)
        
        _model_loaded = True
        return _model_cache, _vectorizer_cache, _label_encoder_cache
    except Exception as e:
        print(f"Error loading ML model: {str(e)}")
        return None, None, None
    
def predict_event_type(keyword):
    """Dự đoán loại sự kiện từ từ khóa"""
    if not keyword or not keyword.strip():
        return None
    
    model, vectorizer, label_encoder = _load_ml_model()
    
    if not all([model, vectorizer, label_encoder]):
        return None
    
    try:
        keyword_vector = vectorizer.transform([keyword.strip()])
        prediction_idx = model.predict(keyword_vector)[0]
        event_type_name = label_encoder.inverse_transform([prediction_idx])[0]
        return event_type_name
    except Exception as e:
        print(f"Error predicting event type: {str(e)}")
        return None
    
def get_recommended_events(customer_id, limit=4):
    sync_expired_events_to_finished()
    
    # Lấy 5 từ khóa tìm kiếm gần nhất
    recent_keywords = (
        SearchHistory.query
        .filter(SearchHistory.customerId == customer_id)
        .order_by(SearchHistory.createdAt.desc())
        .limit(5)
        .all()
    )
    
    print(f"[RECOMMEND] Customer {customer_id}, Found {len(recent_keywords)} search keywords")
    if recent_keywords:
        for kw in recent_keywords:
            print(f"  - Keyword: {kw.keyword}")
    
    if not recent_keywords:
        print(f"[RECOMMEND] No search history found for customer {customer_id}")
        return []
    
    # Dự đoán loại sự kiện từ các từ khóa và lưu thứ tự
    predicted_types_ordered = []  # [(event_type, index), ...]
    type_count = {}  # {event_type: count}
    
    for idx, search in enumerate(recent_keywords):
        event_type = predict_event_type(search.keyword)
        if event_type:
            predicted_types_ordered.append((event_type, idx))
            type_count[event_type] = type_count.get(event_type, 0) + 1
    
    if not predicted_types_ordered:
        return []
    
    # Sắp xếp: theo tần suất (descending), nếu bằng nhau thì theo index (ascending - gần đây nhất)
    predicted_types_ordered.sort(
        key=lambda x: (-type_count[x[0]], x[1])
    )
    
    # Lấy danh sách event_types đã sắp xếp (bỏ duplicate)
    sorted_event_types = []
    seen = set()
    for event_type, _ in predicted_types_ordered:
        if event_type not in seen:
            sorted_event_types.append(event_type)
            seen.add(event_type)

    print(f"[RECOMMEND] Predicted types: {sorted_event_types}")
    print(f"[RECOMMEND] Type count: {type_count}")
    
    if not sorted_event_types:
        return []
    
    try:
        # Subquery để lấy min price
        min_price_subq = (
            db.session.query(
                TicketType.eventId.label("event_id"),
                func.min(TicketType.price).label("min_price"),
            )
            .group_by(TicketType.eventId)
            .subquery()
        )
        
        # Tạo priority case để ưu tiên theo thứ tự sorted_event_types
        priority_case = case(
            {event_type: idx for idx, event_type in enumerate(sorted_event_types)},
            value=EventType.name,
            else_=len(sorted_event_types)  # Events không match được thứ tự sẽ xếp cuối
        )
        
        # Query events từ sorted event_types, ưu tiên theo priority
        query = (
            db.session.query(Event, min_price_subq.c.min_price)
            .join(EventType, Event.eventTypeId == EventType.id)
            .outerjoin(min_price_subq, min_price_subq.c.event_id == Event.id)
            .filter(EventType.name.in_(sorted_event_types))
            .filter(
                or_(
                    Event.status.is_(None),
                    ~func.upper(Event.status).in_(["CANCELLED", "PENDING"]),
                )
            )
            .order_by(priority_case, Event.startTime.asc())
            .limit(limit)
        )
        
        rows = query.all()
        events = []
        for event, min_price in rows:
            setattr(event, "min_price", min_price)
            events.append(event)
        print(f"[RECOMMEND] Found {len(events)} events to recommend")
        return events
    except Exception as e:
        print(f"Error getting recommended events: {str(e)}")
        return []