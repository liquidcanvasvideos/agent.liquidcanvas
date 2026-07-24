"""
Email log model - tracks sent emails
"""
from sqlalchemy import Column, String, Text, DateTime, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
from app.db.database import Base


class EmailLog(Base):
    """Email log model for tracking sent emails"""
    __tablename__ = "email_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    prospect_id = Column(UUID(as_uuid=True), ForeignKey("prospects.id"), nullable=False, index=True)
    subject = Column(Text)
    body = Column(Text)
    response = Column(JSON)  # Gmail API response
    sent_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationship
    prospect = relationship("Prospect", backref="email_logs")
    
    def __repr__(self):
        return f"<EmailLog(id={self.id}, prospect_id={self.prospect_id}, sent_at={self.sent_at})>"

