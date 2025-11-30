"""
Prospect model - stores discovered websites and their contact information
"""
from sqlalchemy import Column, String, Text, Numeric, Integer, DateTime, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
from app.db.database import Base


class Prospect(Base):
    """Prospect model for storing discovered websites and contacts"""
    __tablename__ = "prospects"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    domain = Column(String, nullable=False, index=True)
    page_url = Column(Text)
    page_title = Column(Text)
    contact_email = Column(String, index=True)
    contact_method = Column(String)  # email, form, social, etc.
    da_est = Column(Numeric(5, 2))  # Domain Authority estimate (0-100)
    score = Column(Numeric(5, 2), default=0)  # Overall prospect score
    outreach_status = Column(String, default="pending", index=True)  # pending/sent/replied/accepted/rejected
    last_sent = Column(DateTime(timezone=True))
    followups_sent = Column(Integer, default=0)
    draft_subject = Column(Text)  # Draft email subject
    draft_body = Column(Text)  # Draft email body
    dataforseo_payload = Column(JSON)  # Raw DataForSEO response
    hunter_payload = Column(JSON)  # Raw Hunter.io response
    discovery_query_id = Column(UUID(as_uuid=True), ForeignKey("discovery_queries.id"), nullable=True, index=True)  # Link to discovery query
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships - lazy load to avoid errors if column doesn't exist yet
    discovery_query = relationship("DiscoveryQuery", back_populates="prospects", lazy="select")
    
    def __repr__(self):
        return f"<Prospect(id={self.id}, domain={self.domain}, status={self.outreach_status})>"

