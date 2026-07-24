"""
Job model - tracks background job execution
"""
from sqlalchemy import Column, String, Text, DateTime, JSON, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.db.database import Base


class Job(Base):
    """Job model for tracking background tasks"""
    __tablename__ = "jobs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=True)  # For multi-user support
    job_type = Column(String, nullable=False, index=True)  # discover, enrich, compose, send, draft
    params = Column(JSON)  # Job parameters (keywords, location, etc.)
    status = Column(String, default="pending", index=True)  # pending/running/completed/failed
    result = Column(JSON)  # Job result data
    error_message = Column(Text)
    # Progress tracking fields for drafting jobs
    # Note: These may not exist in all database schemas - handled via conditional logic in API
    drafts_created = Column(Integer, default=0, nullable=True)  # Number of drafts created so far
    total_targets = Column(Integer, nullable=True)  # Total number of prospects to draft (set when job starts)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<Job(id={self.id}, type={self.job_type}, status={self.status})>"

