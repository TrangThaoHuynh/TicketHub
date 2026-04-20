from datetime import datetime, timedelta
from sqlalchemy import desc, func

from .. import db
from ..models.search_history import SearchHistory


def save_search_history(customer_id, keyword):
    """
    Lưu từ khóa tìm kiếm vào lịch sử tìm kiếm
    
    Args:
        customer_id (int): ID của khách hàng
        keyword (str): Từ khóa tìm kiếm
    
    Returns:
        tuple: (SearchHistory object, error message) - error message là None nếu thành công
    """
    if not customer_id or not keyword:
        return None, "Customer ID and keyword are required"
    
    # Normalize keyword (strip whitespace)
    keyword = keyword.strip()
    
    if len(keyword) == 0:
        return None, "Keyword cannot be empty"
    
    if len(keyword) > 255:
        return None, "Keyword is too long (max 255 characters)"
    
    try:
        search_history = SearchHistory(
            customerId=customer_id,
            keyword=keyword,
            createdAt=datetime.now()
        )
        db.session.add(search_history)
        db.session.commit()
        return search_history, None
    except Exception as e:
        db.session.rollback()
        return None, f"Error saving search history: {str(e)}"


def get_search_history(customer_id, limit=20, days=None):
    """
    Lấy lịch sử tìm kiếm của khách hàng
    
    Args:
        customer_id (int): ID của khách hàng
        limit (int): Số lượng bản ghi cần lấy (mặc định 20)
        days (int): Số ngày gần đây cần lấy (None = tất cả)
    
    Returns:
        list: Danh sách SearchHistory objects, được sắp xếp mới nhất trước
    """
    query = SearchHistory.query.filter(SearchHistory.customerId == customer_id)
    
    if days:
        start_date = datetime.now() - timedelta(days=days)
        query = query.filter(SearchHistory.createdAt >= start_date)
    
    return query.order_by(desc(SearchHistory.createdAt)).limit(limit).all()



def delete_search_history(customer_id, search_history_id):
    """
    Xóa một bản ghi lịch sử tìm kiếm
    
    Args:
        customer_id (int): ID của khách hàng
        search_history_id (int): ID của bản ghi lịch sử tìm kiếm
    
    Returns:
        tuple: (True/False, error message)
    """
    try:
        search = SearchHistory.query.filter(
            SearchHistory.id == search_history_id,
            SearchHistory.customerId == customer_id
        ).first()
        
        if not search:
            return False, "Search history not found"
        
        db.session.delete(search)
        db.session.commit()
        return True, None
    except Exception as e:
        db.session.rollback()
        return False, f"Error deleting search history: {str(e)}"


def clear_search_history(customer_id):
    """
    Xóa toàn bộ lịch sử tìm kiếm của khách hàng
    
    Args:
        customer_id (int): ID của khách hàng
    
    Returns:
        tuple: (number of deleted records, error message)
    """
    try:
        deleted_count = SearchHistory.query.filter(
            SearchHistory.customerId == customer_id
        ).delete()
        
        db.session.commit()
        return deleted_count, None
    except Exception as e:
        db.session.rollback()
        return 0, f"Error clearing search history: {str(e)}"


