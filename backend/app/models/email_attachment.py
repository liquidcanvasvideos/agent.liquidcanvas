"""
Email attachment model - stores global and per-prospect attachments
"""
import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, LargeBinary, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.db.database import Base


class EmailAttachment(Base):
    """Attachment for outbound emails"""

    __tablename__ = "email_attachments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    prospect_id = Column(UUID(as_uuid=True), ForeignKey("prospects.id"), nullable=True, index=True)
    filename = Column(String, nullable=False)
    content_type = Column(String, nullable=False)
    size_bytes = Column(Integer, nullable=False)
    scope = Column(String, nullable=False, server_default="global")  # global or prospect
    data = Column(LargeBinary, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
