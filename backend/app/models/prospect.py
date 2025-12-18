"""
Prospect model - stores discovered websites and their contact information
STRICT PIPELINE: Each step has explicit status tracking
"""
from sqlalchemy import Column, String, Text, Numeric, Integer, DateTime, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
from app.db.database import Base
from app.models.enums import DiscoveryStatus, ScrapeStatus, VerificationStatus, DraftStatus, SendStatus


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
    discovery_status = Column(String, nullable=False, server_default=DiscoveryStatus.NEW.value, index=True)
    # scrape_status: Tracks scraping step - required for pipeline status queries
    # Lifecycle: DISCOVERED → SCRAPED → ENRICHED → EMAILED (send_status tracks email)
    scrape_status = Column(String, nullable=False, server_default=ScrapeStatus.DISCOVERED.value, index=True)  # DISCOVERED, SCRAPED, ENRICHED, NO_EMAIL_FOUND, failed
    # approval_status: Tracks human selection step - required for pipeline progression
    approval_status = Column(String, nullable=False, server_default='PENDING', index=True)  # PENDING, approved, rejected, deleted
    # verification_status: Tracks email verification step - required for pipeline status queries
    verification_status = Column(String, nullable=False, server_default=VerificationStatus.UNVERIFIED.value, index=True)  # PENDING, verified, unverified, UNVERIFIED, failed
    # Draft and send status - required for pipeline progression
    draft_status = Column(String, nullable=False, server_default=DraftStatus.PENDING.value, index=True)  # pending, drafted, failed
    send_status = Column(String, nullable=False, server_default=SendStatus.PENDING.value, index=True)  # pending, sent, failed
    
    # Legacy outreach_status (kept for backward compatibility)
    outreach_status = Column(String, default="pending", index=True)  # pending/sent/replied/accepted/rejected
    
    last_sent = Column(DateTime(timezone=True))
    followups_sent = Column(Integer, default=0)
    draft_subject = Column(Text)  # Draft email subject
    draft_body = Column(Text)  # Draft email body
    
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
        return self.discovery_status == DiscoveryStatus.DISCOVERED.value and self.approval_status == "approved"
    
    def can_proceed_to_verification(self) -> bool:
        """Check if prospect can proceed to verification step"""
        return self.scrape_status in [ScrapeStatus.SCRAPED.value, ScrapeStatus.NO_EMAIL_FOUND.value]
    
    def can_proceed_to_drafting(self) -> bool:
        """Check if prospect can proceed to drafting step"""
        return self.verification_status in [VerificationStatus.VERIFIED.value, VerificationStatus.UNVERIFIED_LOWER.value]
    
    def can_proceed_to_sending(self) -> bool:
        """Check if prospect can proceed to sending step"""
        return self.draft_status == DraftStatus.DRAFTED.value
