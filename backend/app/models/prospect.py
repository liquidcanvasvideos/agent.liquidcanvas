"""
Prospect model - stores discovered websites and their contact information
STRICT PIPELINE: Each step has explicit status tracking
"""
from sqlalchemy import Column, String, Text, Numeric, Integer, DateTime, JSON, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
from enum import Enum

from app.db.database import Base


class DiscoveryStatus(str, Enum):
    """Discovery step status values."""

    NEW = "NEW"
    DISCOVERED = "DISCOVERED"


class ScrapeStatus(str, Enum):
    """Scraping step status values."""

    DISCOVERED = "DISCOVERED"
    SCRAPED = "SCRAPED"
    ENRICHED = "ENRICHED"
    NO_EMAIL_FOUND = "NO_EMAIL_FOUND"
    FAILED = "failed"


class VerificationStatus(str, Enum):
    """Verification step status values."""

    UNVERIFIED = "UNVERIFIED"
    PENDING = "pending"
    VERIFIED = "verified"
    UNVERIFIED_LOWER = "unverified"
    FAILED = "failed"


class DraftStatus(str, Enum):
    """Drafting step status values."""

    PENDING = "pending"
    DRAFTED = "drafted"
    FAILED = "failed"


class SendStatus(str, Enum):
    """Sending step status values."""

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class ProspectStage(str, Enum):
    """Canonical pipeline stage - single source of truth for prospect progression."""
    
    DISCOVERED = "DISCOVERED"  # Step 1: Website discovered
    SCRAPED = "SCRAPED"  # Step 3: Scraping completed (no email found)
    EMAIL_FOUND = "EMAIL_FOUND"  # Step 3: Scraping completed (email found, not yet promoted to lead)
    VERIFIED = "VERIFIED"  # Step 4: Email verified
    LEAD = "LEAD"  # Explicitly promoted to lead (ready for outreach)
    DRAFTED = "DRAFTED"  # Step 6: Email drafted
    SENT = "SENT"  # Step 7: Email sent


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
    
    # STRICT PIPELINE STATUS FIELDS - BULLETPROOF SCHEMA
    # These four columns are CRITICAL and MUST exist in database
    # Missing any causes /api/pipeline/status to return 500 errors
    # discovery_status: Required to enforce strict step-by-step pipeline progression
    discovery_status = Column(
        String,
        nullable=False,
        server_default=DiscoveryStatus.NEW.value,
        index=True,
    )
    # scrape_status: Tracks scraping step - required for pipeline status queries
    # Lifecycle: DISCOVERED → SCRAPED → ENRICHED → EMAILED (send_status tracks email)
    scrape_status = Column(
        String,
        nullable=False,
        server_default=ScrapeStatus.DISCOVERED.value,
        index=True,
    )  # DISCOVERED, SCRAPED, ENRICHED, NO_EMAIL_FOUND, failed
    # approval_status: Tracks human selection step - required for pipeline progression
    approval_status = Column(
        String,
        nullable=False,
        server_default="PENDING",
        index=True,
    )  # PENDING, approved, rejected, deleted
    # verification_status: Tracks email verification step - required for pipeline status queries
    verification_status = Column(
        String,
        nullable=False,
        server_default=VerificationStatus.UNVERIFIED.value,
        index=True,
    )  # PENDING, verified, unverified, UNVERIFIED, failed
    # Draft and send status - required for pipeline progression
    draft_status = Column(
        String,
        nullable=False,
        server_default=DraftStatus.PENDING.value,
        index=True,
    )  # pending, drafted, failed
    send_status = Column(
        String,
        nullable=False,
        server_default=SendStatus.PENDING.value,
        index=True,
    )  # pending, sent, failed
    # Canonical pipeline stage - single source of truth for prospect progression
    # Lifecycle: DISCOVERED → SCRAPED → LEAD → VERIFIED → DRAFTED → SENT
    stage = Column(
        String,
        nullable=False,
        server_default=ProspectStage.DISCOVERED.value,
        index=True,
    )  # DISCOVERED, SCRAPED, LEAD, VERIFIED, DRAFTED, SENT
    
    # Legacy outreach_status (kept for backward compatibility)
    outreach_status = Column(String, default="pending", index=True)  # pending/sent/replied/accepted/rejected
    
    last_sent = Column(DateTime(timezone=True))
    followups_sent = Column(Integer, default=0)
    draft_subject = Column(Text)  # Draft email subject
    draft_body = Column(Text)  # Draft email body
    # drafted_at = Column(DateTime(timezone=True))  # REMOVED: Column doesn't exist in database
    final_body = Column(Text, nullable=True)  # Final email body (after sending, moved from draft_body)
    thread_id = Column(UUID(as_uuid=True), nullable=True, index=True)  # Thread ID for follow-up emails
    sequence_index = Column(Integer, default=0, nullable=False)  # Follow-up sequence (0 = initial, 1+ = follow-up)
    is_manual = Column(Boolean, default=False, nullable=True)  # True if manually added, False otherwise
    
    # Discovery metadata
    discovery_query_id = Column(UUID(as_uuid=True), ForeignKey("discovery_queries.id"), nullable=True, index=True)
    discovery_category = Column(String)  # Category from discovery
    discovery_location = Column(String)  # Location from discovery
    discovery_keywords = Column(Text)  # Keywords from discovery
    
    # Scraping metadata
    scrape_payload = Column(JSON)  # Emails found during scraping: {url: [emails]}
    scrape_source_url = Column(Text)  # URL where email was found
    
    # Verification metadata
    verification_confidence = Column(Numeric(5, 2))  # Confidence score from Snov
    verification_payload = Column(JSON)  # Raw verification response
    
    # Raw API responses (kept for backward compatibility)
    dataforseo_payload = Column(JSON)  # Raw DataForSEO response
    snov_payload = Column(JSON)  # Raw Snov.io response
    
    # SERP intent (from previous implementation)
    serp_intent = Column(String)  # SERP intent: service, brand, blog, media, marketplace, platform, unknown
    serp_confidence = Column(Numeric(3, 2))  # Confidence score (0.0-1.0)
    serp_signals = Column(JSON)  # List of signals that led to intent classification
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships - lazy load to avoid errors if column doesn't exist yet
    discovery_query = relationship("DiscoveryQuery", back_populates="prospects", lazy="select")
    
    def __repr__(self):
        return f"<Prospect(id={self.id}, domain={self.domain}, discovery={self.discovery_status}, approval={self.approval_status})>"
    
    def can_proceed_to_scraping(self) -> bool:
        """Check if prospect can proceed to scraping step"""
        return (
            self.discovery_status == DiscoveryStatus.DISCOVERED.value
            and self.approval_status == "approved"
        )
    
    def can_proceed_to_verification(self) -> bool:
        """Check if prospect can proceed to verification step"""
        return self.scrape_status in [
            ScrapeStatus.SCRAPED.value,
            ScrapeStatus.NO_EMAIL_FOUND.value,
        ]
    
    def can_proceed_to_drafting(self) -> bool:
        """Check if prospect can proceed to drafting step"""
        return self.verification_status in [
            VerificationStatus.VERIFIED.value,
            VerificationStatus.UNVERIFIED_LOWER.value,
        ]
    
    def can_proceed_to_sending(self) -> bool:
        """Check if prospect can proceed to sending step"""
        return self.draft_status == DraftStatus.DRAFTED.value
