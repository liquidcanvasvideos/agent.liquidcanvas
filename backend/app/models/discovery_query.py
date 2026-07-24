"""
DiscoveryQuery model - stores individual search queries executed during discovery jobs
"""
from sqlalchemy import Column, String, Text, Integer, DateTime, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
from app.db.database import Base


class DiscoveryQuery(Base):
    """DiscoveryQuery model for storing individual search queries and their results"""
    __tablename__ = "discovery_queries"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False, index=True)
    keyword = Column(String, nullable=False, index=True)  # The search keyword/query
    location = Column(String, nullable=False, index=True)  # Location code or name
    location_code = Column(Integer)  # DataForSEO location code
    category = Column(String, index=True)  # Category if applicable
    status = Column(String, default="pending", index=True)  # pending/success/failed
    results_found = Column(Integer, default=0)  # Number of results found
    results_saved = Column(Integer, default=0)  # Number of results saved as prospects
    results_skipped_duplicate = Column(Integer, default=0)  # Skipped due to duplicates
    results_skipped_existing = Column(Integer, default=0)  # Skipped due to existing in DB
    error_message = Column(Text)  # Error message if failed
    query_metadata = Column(JSON)  # Additional metadata (query details, etc.) - renamed from 'metadata' (reserved in SQLAlchemy)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    job = relationship("Job", backref="discovery_queries")
    prospects = relationship("Prospect", back_populates="discovery_query")
    
    def __repr__(self):
        return f"<DiscoveryQuery(id={self.id}, keyword='{self.keyword}', status={self.status})>"

