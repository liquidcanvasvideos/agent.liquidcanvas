"""
Social Media Outreach Models

COMPLETELY SEPARATE from Website Outreach - parallel system with no shared logic.

Targets individual people (not organizations) across LinkedIn, Facebook, Instagram, TikTok.
"""
from sqlalchemy import Column, String, Text, Integer, Boolean, JSON, DateTime, ForeignKey, Enum as SQLEnum, Float, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
from enum import Enum
from app.db.database import Base


class SocialPlatform(str, Enum):
    """Supported social media platforms"""
    LINKEDIN = "linkedin"
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"


class DiscoveryStatus(str, Enum):
    """Profile discovery status in pipeline"""
    DISCOVERED = "discovered"  # Stage 1: Just discovered
    REVIEWED = "reviewed"      # Stage 2: Manually reviewed
    QUALIFIED = "qualified"    # Stage 2: Qualified for outreach
    REJECTED = "rejected"      # Stage 2: Rejected


class OutreachStatus(str, Enum):
    """Profile outreach status in pipeline"""
    PENDING = "pending"        # Not yet drafted
    DRAFTED = "drafted"        # Stage 3: Draft created
    SENT = "sent"              # Stage 4: Message sent
    FOLLOWUP = "followup"      # Stage 5: Follow-up needed
    CLOSED = "closed"          # Conversation closed


class MessageType(str, Enum):
    """Message type"""
    INITIAL = "initial"
    FOLLOWUP = "followup"


class MessageStatus(str, Enum):
    """Message sending status"""
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    DELIVERED = "delivered"
    READ = "read"


class DiscoveryJobStatus(str, Enum):
    """Discovery job status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SocialProfile(Base):
    """
    Individual person profile discovered from social platforms.
    
    SEPARATE from Prospect model - targets people, not organizations.
    """
    __tablename__ = "social_profiles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # Platform identification
    platform = Column(SQLEnum(SocialPlatform), nullable=False, index=True)
    username = Column(String(255), nullable=False, index=True)  # @username or profile identifier
    full_name = Column(String(255), nullable=True)  # Full name of the person
    profile_url = Column(Text, nullable=False, unique=True, index=True)
    
    # Profile content
    bio = Column(Text, nullable=True)
    location = Column(String(255), nullable=True)
    category = Column(String(50), nullable=True, index=True)  # Same categories as website outreach
    
    # Metrics
    followers_count = Column(Integer, default=0, nullable=False)
    engagement_score = Column(Float, default=0.0, nullable=False)  # Computed engagement metric
    
    # Pipeline status fields
    discovery_status = Column(
        SQLEnum(DiscoveryStatus),
        nullable=False,
        server_default=DiscoveryStatus.DISCOVERED.value,
        index=True
    )
    outreach_status = Column(
        SQLEnum(OutreachStatus),
        nullable=False,
        server_default=OutreachStatus.PENDING.value,
        index=True
    )
    
    # Metadata
    is_manual = Column(Boolean, default=False, nullable=False)  # Manually added vs discovered
    last_contacted_at = Column(DateTime(timezone=True), nullable=True)
    discovery_job_id = Column(UUID(as_uuid=True), ForeignKey("social_discovery_jobs.id"), nullable=True, index=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    discovery_job = relationship("SocialDiscoveryJob", back_populates="profiles")
    drafts = relationship("SocialDraft", back_populates="profile", cascade="all, delete-orphan")
    messages = relationship("SocialMessage", back_populates="profile", cascade="all, delete-orphan")


class SocialDiscoveryJob(Base):
    """
    Discovery job for social profiles.
    
    Platform-specific parameters stored in JSONB.
    """
    __tablename__ = "social_discovery_jobs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    platform = Column(SQLEnum(SocialPlatform), nullable=False, index=True)
    
    # Search parameters
    categories = Column(ARRAY(String), nullable=True)  # Array of categories
    locations = Column(ARRAY(String), nullable=True)  # Array of locations
    keywords = Column(ARRAY(String), nullable=True)  # Array of keywords
    
    # Platform-specific parameters (JSONB for flexibility)
    parameters = Column(JSON, nullable=True)  # Platform-specific: job_title, industry, hashtags, etc.
    
    # Legacy field (kept for backward compatibility)
    filters = Column(JSON, nullable=True)  # Alias for parameters
    payload = Column(JSON, nullable=True)  # Alias for parameters
    
    # Job status
    status = Column(
        SQLEnum(DiscoveryJobStatus),
        nullable=False,
        server_default=DiscoveryJobStatus.PENDING.value,
        index=True
    )
    results_count = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    profiles = relationship("SocialProfile", back_populates="discovery_job")


class SocialDraft(Base):
    """
    Draft message for social profile.
    
    Drafts are saved but not sent until explicitly sent from Sending stage.
    """
    __tablename__ = "social_drafts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    profile_id = Column(UUID(as_uuid=True), ForeignKey("social_profiles.id"), nullable=False, index=True)
    platform = Column(SQLEnum(SocialPlatform), nullable=False)
    
    # Draft content
    draft_body = Column(Text, nullable=False)
    is_followup = Column(Boolean, default=False, nullable=False)
    sequence_index = Column(Integer, default=0, nullable=False)  # 0 = initial, 1+ = follow-up
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    profile = relationship("SocialProfile", back_populates="drafts")


class SocialMessage(Base):
    """
    Sent message to social profile.
    
    Tracks message history per profile for follow-up generation.
    """
    __tablename__ = "social_messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    profile_id = Column(UUID(as_uuid=True), ForeignKey("social_profiles.id"), nullable=False, index=True)
    platform = Column(SQLEnum(SocialPlatform), nullable=False)
    
    # Message content
    message_type = Column(
        SQLEnum(MessageType),
        nullable=False,
        server_default=MessageType.INITIAL.value,
        index=True
    )
    draft_body = Column(Text, nullable=True)  # Original draft (before sending)
    sent_body = Column(Text, nullable=False)  # Actual message sent
    
    # Message status
    status = Column(
        SQLEnum(MessageStatus),
        nullable=False,
        server_default=MessageStatus.PENDING.value,
        index=True
    )
    
    # Threading
    thread_id = Column(UUID(as_uuid=True), nullable=True, index=True)  # For conversation threading
    
    # Timestamps
    sent_at = Column(DateTime(timezone=True), nullable=True, index=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    profile = relationship("SocialProfile", back_populates="messages")
