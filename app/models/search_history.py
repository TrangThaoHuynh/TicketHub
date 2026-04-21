from .. import db
from datetime import datetime


class SearchHistory(db.Model):
    __tablename__ = "SearchHistory"

    id = db.Column(db.Integer, primary_key=True)
    customerId = db.Column(db.Integer, db.ForeignKey("Customer.id"), nullable=False)
    keyword = db.Column(db.String(255), nullable=False)
    createdAt = db.Column(db.DateTime, default=datetime.now)

    # Relationship
    customer = db.relationship("Customer", backref="search_histories")

    def __repr__(self) -> str:
        return f"<SearchHistory id={self.id!r} customerId={self.customerId!r} keyword={self.keyword!r}>"

    def to_dict(self):
        """Convert SearchHistory object to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "customerId": self.customerId,
            "keyword": self.keyword,
            "createdAt": self.createdAt.isoformat() if self.createdAt else None,
        }
