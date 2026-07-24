"""
Scraper history model - tracks automatic scraper job runs
"""
from sqlalchemy import Column, String, Integer, DateTime, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.db.database import Base


class ScraperHistory(Base):
    """Scraper history model for tracking automatic scraper runs"""
    __tablename__ = "scraper_history"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    triggered_at = Column(DateTime(timezone=True), nullable=False, index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    success_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    duration_seconds = Column(Numeric(10, 2), nullable=True)  # Duration in seconds
    status = Column(String, default="running", index=True)  # running, completed, failed
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    def __repr__(self):
        return f"<ScraperHistory(id={self.id}, status={self.status}, triggered_at={self.triggered_at})>"

