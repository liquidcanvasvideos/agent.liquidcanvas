"""
Social Integration Model

Stores encrypted OAuth tokens and connection status for social media platforms.
Designed for production use with proper security, token expiry tracking, and capability detection.

CRITICAL SECURITY NOTES:
- Access tokens and refresh tokens are encrypted at rest
- Tokens are never logged or exposed in API responses
- Token expiry is tracked and validated before use
- Scopes are stored to enable capability detection
"""
from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Index, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
from enum import Enum
from datetime import datetime, timezone
from typing import Optional

from app.db.database import Base


class Platform(str, Enum):
    """Supported social media platforms"""
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    TIKTOK = "tiktok"
    EMAIL = "email"


class ConnectionStatus(str, Enum):
    """Connection status for social integrations"""
    CONNECTED = "connected"  # Active and valid
    EXPIRED = "expired"  # Token expired, needs refresh
    REVOKED = "revoked"  # User revoked permissions
    UNSUPPORTED = "unsupported"  # Platform doesn't support required features
    ERROR = "error"  # Connection error or invalid configuration


class SocialIntegration(Base):
    """
    Social Integration Model
    
    Stores OAuth tokens and connection metadata for social media platforms.
    Supports Instagram, Facebook, TikTok, and Email (SMTP).
    
    SECURITY:
    - access_token: Encrypted at rest (use encryption utilities)
    - refresh_token: Encrypted at rest, nullable (not all platforms provide)
    - Tokens are never returned in API responses (use masked versions)
    
    CAPABILITY DETECTION:
    - scopes_granted: JSON array of granted OAuth scopes
    - Used to determine what actions are possible (e.g., can_send_dm)
    - Platform-specific validation logic checks scopes before allowing actions
    
    TOKEN MANAGEMENT:
    - token_expires_at: When access token expires (null if no expiry)
    - last_verified_at: Last time token was validated with platform API
    - connection_status: Current state (connected, expired, revoked, etc.)
    """
    __tablename__ = "social_integrations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # User association (if you have user authentication)
    # For now, using a simple string identifier - adjust based on your auth system
    user_id = Column(String, nullable=False, index=True)
    
    # Platform identification
    platform = Column(String, nullable=False, index=True)  # instagram | facebook | tiktok | email
    
    # Connection status tracking
    connection_status = Column(
        String,
        nullable=False,
        server_default=ConnectionStatus.CONNECTED.value,
        index=True
    )
    
    # OAuth metadata
    scopes_granted = Column(JSONB, nullable=True)  # Array of granted scopes: ["instagram_basic", "instagram_manage_messages"]
    account_id = Column(String, nullable=True)  # Platform account ID (Instagram Business Account ID, Facebook Page ID, etc.)
    page_id = Column(String, nullable=True)  # Facebook Page ID (if applicable)
    business_id = Column(String, nullable=True)  # Meta Business Account ID (for Instagram/Facebook)
    
    # Encrypted tokens (CRITICAL: Must be encrypted before storage)
    # These fields store encrypted values - use encryption utilities to read/write
    access_token = Column(Text, nullable=True)  # Encrypted access token
    refresh_token = Column(Text, nullable=True)  # Encrypted refresh token (nullable - not all platforms provide)
    
    # Token expiry tracking
    token_expires_at = Column(DateTime(timezone=True), nullable=True)  # When access token expires
    last_verified_at = Column(DateTime(timezone=True), nullable=True)  # Last successful token validation
    
    # Email-specific fields (for SMTP configuration)
    email_address = Column(String, nullable=True)  # Email address for SMTP
    smtp_host = Column(String, nullable=True)  # SMTP server hostname
    smtp_port = Column(Integer, nullable=True)  # SMTP port (usually 587 or 465)
    smtp_username = Column(String, nullable=True)  # SMTP username (usually email)
    smtp_password = Column(Text, nullable=True)  # Encrypted SMTP password
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Additional metadata (error messages, platform-specific data)
    # Note: Using 'platform_metadata' instead of 'metadata' because 'metadata' is reserved in SQLAlchemy Declarative API
    platform_metadata = Column(JSONB, nullable=True)  # Platform-specific metadata, error messages, etc.
    
    # Composite index for efficient lookups
    __table_args__ = (
        Index('idx_user_platform', 'user_id', 'platform', unique=True),  # One integration per user per platform
    )
    
    def is_token_expired(self) -> bool:
        """Check if access token is expired"""
        if not self.token_expires_at:
            return False  # No expiry means token doesn't expire (or unknown)
        return datetime.now(timezone.utc) >= self.token_expires_at
    
    def is_connected(self) -> bool:
        """Check if integration is currently connected and valid"""
        if self.connection_status != ConnectionStatus.CONNECTED.value:
            return False
        if self.is_token_expired():
            return False
        return True
    
    def __repr__(self):
        return f"<SocialIntegration(id={self.id}, platform={self.platform}, status={self.connection_status})>"

