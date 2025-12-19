"""
Pydantic schemas for prospect-related endpoints
"""
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID
from decimal import Decimal


class ProspectResponse(BaseModel):
    """Response schema for prospect"""
    id: UUID
    domain: str
    page_url: Optional[str] = None
    page_title: Optional[str] = None
    contact_email: Optional[str] = None
    contact_method: Optional[str] = None
    da_est: Optional[Decimal] = None
    score: Optional[Decimal] = None
    outreach_status: str
    last_sent: Optional[datetime] = None
    followups_sent: int
    draft_subject: Optional[str] = None
    draft_body: Optional[str] = None
    # drafted_at: Optional[datetime] = None  # REMOVED: Column doesn't exist in database
    final_body: Optional[str] = None  # Final email body (after sending)
    thread_id: Optional[UUID] = None  # Thread ID for follow-up emails
    sequence_index: Optional[int] = None  # Follow-up sequence (0 = initial, 1+ = follow-up)
    is_manual: Optional[bool] = None  # True if manually added, False otherwise
    serp_intent: Optional[str] = None  # SERP intent: service, brand, blog, media, marketplace, platform, unknown
    serp_confidence: Optional[Decimal] = None  # Confidence score (0.0-1.0)
    serp_signals: Optional[list[str]] = None  # List of signals that led to intent classification
    # Pipeline status fields - required for Leads tab filtering
    discovery_status: Optional[str] = None
    approval_status: Optional[str] = None
    scrape_status: Optional[str] = None  # Legacy: scraping step status
    verification_status: Optional[str] = None
    draft_status: Optional[str] = None
    send_status: Optional[str] = None
    stage: Optional[str] = None  # CRITICAL: Canonical pipeline stage - DISCOVERED, SCRAPED, LEAD, VERIFIED, DRAFTED, SENT
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ProspectListResponse(BaseModel):
    """Response schema for prospect list"""
    prospects: list[ProspectResponse]
    total: int
    skip: int
    limit: int


class ComposeRequest(BaseModel):
    """Request schema for composing email"""
    prospect_id: UUID


class ComposeResponse(BaseModel):
    """Response schema for compose result"""
    prospect_id: UUID
    subject: str
    body: str
    draft_saved: bool = True


class SendRequest(BaseModel):
    """Request schema for sending email"""
    prospect_id: UUID
    subject: Optional[str] = None  # Use draft if not provided
    body: Optional[str] = None  # Use draft if not provided


class SendResponse(BaseModel):
    """Response schema for send result"""
    prospect_id: UUID
    email_log_id: UUID
    sent_at: datetime
    success: bool
    message_id: Optional[str] = None

