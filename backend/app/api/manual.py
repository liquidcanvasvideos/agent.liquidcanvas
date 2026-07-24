"""
Manual input endpoints for scraping and verification
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from typing import Optional
from pydantic import BaseModel
import logging
from urllib.parse import urlparse
import uuid

from app.db.database import get_db
from app.api.auth import get_current_user_optional
from app.models.prospect import (
    Prospect,
    DiscoveryStatus,
    ScrapeStatus,
    VerificationStatus,
    ProspectStage,
)
from app.services.enrichment import _scrape_emails_from_domain
from app.clients.snov import SnovIOClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/manual", tags=["manual"])


def normalize_domain(url_or_domain: str) -> str:
    """
    Normalize a URL or domain to just the domain name
    
    Args:
        url_or_domain: URL (e.g., "https://example.com/page") or domain (e.g., "example.com")
    
    Returns:
        Normalized domain (e.g., "example.com")
    """
    # Remove protocol if present
    if "://" in url_or_domain:
        parsed = urlparse(url_or_domain)
        domain = parsed.netloc or parsed.path.split("/")[0]
    else:
        domain = url_or_domain.split("/")[0]
    
    # Remove www. prefix
    if domain.startswith("www."):
        domain = domain[4:]
    
    # Remove port if present
    if ":" in domain:
        domain = domain.split(":")[0]
    
    return domain.lower().strip()


class ManualScrapeRequest(BaseModel):
    website_url: str


class ManualScrapeResponse(BaseModel):
    success: bool
    prospect_id: str
    message: str
    is_followup: bool


class ManualVerifyRequest(BaseModel):
    email: str


class ManualVerifyResponse(BaseModel):
    success: bool
    prospect_id: str
    message: str
    verification_status: str
    is_followup: bool


@router.post("/scrape", response_model=ManualScrapeResponse)
async def manual_scrape(
    request: ManualScrapeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Manually scrape a website for emails
    
    Behavior:
    - Normalize domain
    - If website already exists → mark as follow-up candidate
    - Else create Prospect with is_manual = "true"
    - Trigger scraping logic exactly like automated scraping
    """
    # Normalize domain
    domain = normalize_domain(request.website_url)
    
    logger.info(f"🔍 [MANUAL SCRAPE] Scraping {domain} (from URL: {request.website_url})")
    
    # Check if prospect already exists (same domain)
    existing = await db.execute(
        select(Prospect).where(Prospect.domain == domain)
    )
    existing_prospect = existing.scalar_one_or_none()
    
    is_followup = existing_prospect is not None
    
    if existing_prospect:
        # Website already exists → mark as follow-up candidate
        logger.info(f"📌 [MANUAL SCRAPE] Domain {domain} already exists (prospect_id: {existing_prospect.id}) - marking as follow-up candidate")
        prospect = existing_prospect
        
        # Set up thread tracking for follow-up
        # Use existing prospect's thread_id, or create one if it doesn't have one
        if not prospect.thread_id:
            prospect.thread_id = existing_prospect.id
        # Increment sequence_index for follow-up
        prospect.sequence_index = (existing_prospect.sequence_index or 0) + 1
        logger.info(f"📌 [MANUAL SCRAPE] Set up follow-up tracking: thread_id={prospect.thread_id}, sequence={prospect.sequence_index}")
    else:
        # Create new Prospect with is_manual = "true"
        prospect = Prospect(
            domain=domain,
            page_url=request.website_url if "://" in request.website_url else f"https://{domain}",
            discovery_status=DiscoveryStatus.DISCOVERED.value,
            scrape_status=ScrapeStatus.DISCOVERED.value,
            is_manual=True,
            stage=ProspectStage.DISCOVERED.value,
        )
        db.add(prospect)
        await db.commit()
        await db.refresh(prospect)
        logger.info(f"✅ [MANUAL SCRAPE] Created new manual prospect for {domain} (prospect_id: {prospect.id})")
    
    # Trigger scraping logic exactly like automated scraping
    try:
        emails_by_page = await _scrape_emails_from_domain(domain, prospect.page_url)
        
        # Collect all unique emails
        all_emails = []
        source_url = None
        for url, emails in emails_by_page.items():
            all_emails.extend(emails)
            if emails and not source_url:
                source_url = url
        
        if all_emails:
            # Emails found
            prospect.contact_email = all_emails[0]  # Primary email
            prospect.scrape_source_url = source_url
            prospect.scrape_payload = emails_by_page
            prospect.scrape_status = ScrapeStatus.SCRAPED.value
            prospect.stage = ProspectStage.EMAIL_FOUND.value
            
            # CRITICAL: Inherit category from discovery query if not already set
            if not prospect.discovery_category or prospect.discovery_category in ['', 'N/A', 'Unknown']:
                # First try to get category from discovery_query
                if prospect.discovery_query_id:
                    try:
                        from app.models.discovery_query import DiscoveryQuery
                        from sqlalchemy import select
                        result = await db.execute(
                            select(DiscoveryQuery.category).where(
                                DiscoveryQuery.id == prospect.discovery_query_id,
                                DiscoveryQuery.category.isnot(None),
                                DiscoveryQuery.category != '',
                                DiscoveryQuery.category != 'N/A',
                                DiscoveryQuery.category != 'Unknown'
                            )
                        )
                        query_category = result.scalar_one_or_none()
                        if query_category:
                            prospect.discovery_category = query_category
                            logger.info(f"🏷️  [MANUAL SCRAPE] Inherited category '{query_category}' from discovery query for {domain}")
                    except Exception as query_err:
                        logger.warning(f"⚠️  [MANUAL SCRAPE] Error getting category from discovery query: {query_err}")
                
                # If still no category, try auto-categorization as fallback
                if not prospect.discovery_category or prospect.discovery_category in ['', 'N/A', 'Unknown']:
                    try:
                        from app.api.pipeline import auto_categorize_prospect
                        category = await auto_categorize_prospect(prospect, db)
                        if category:
                            prospect.discovery_category = category
                            logger.info(f"🏷️  [MANUAL SCRAPE] Auto-categorized {domain} as '{category}' during scraping")
                    except Exception as cat_err:
                        logger.warning(f"⚠️  [MANUAL SCRAPE] Error during auto-categorization: {cat_err}")
            else:
                logger.debug(f"✅ [MANUAL SCRAPE] Preserving existing category '{prospect.discovery_category}' for {domain}")
            
            logger.info(f"✅ [MANUAL SCRAPE] Found {len(all_emails)} emails for {domain}")
        else:
            # No emails found
            prospect.scrape_status = ScrapeStatus.NO_EMAIL_FOUND.value
            prospect.stage = ProspectStage.SCRAPED.value
            
            # CRITICAL: Inherit category from discovery query if not already set
            if not prospect.discovery_category or prospect.discovery_category in ['', 'N/A', 'Unknown']:
                # First try to get category from discovery_query
                if prospect.discovery_query_id:
                    try:
                        from app.models.discovery_query import DiscoveryQuery
                        from sqlalchemy import select
                        result = await db.execute(
                            select(DiscoveryQuery.category).where(
                                DiscoveryQuery.id == prospect.discovery_query_id,
                                DiscoveryQuery.category.isnot(None),
                                DiscoveryQuery.category != '',
                                DiscoveryQuery.category != 'N/A',
                                DiscoveryQuery.category != 'Unknown'
                            )
                        )
                        query_category = result.scalar_one_or_none()
                        if query_category:
                            prospect.discovery_category = query_category
                            logger.info(f"🏷️  [MANUAL SCRAPE] Inherited category '{query_category}' from discovery query for {domain} (no email found)")
                    except Exception as query_err:
                        logger.warning(f"⚠️  [MANUAL SCRAPE] Error getting category from discovery query: {query_err}")
                
                # If still no category, try auto-categorization as fallback
                if not prospect.discovery_category or prospect.discovery_category in ['', 'N/A', 'Unknown']:
                    try:
                        from app.api.pipeline import auto_categorize_prospect
                        category = await auto_categorize_prospect(prospect, db)
                        if category:
                            prospect.discovery_category = category
                            logger.info(f"🏷️  [MANUAL SCRAPE] Auto-categorized {domain} as '{category}' (no email found)")
                    except Exception as cat_err:
                        logger.warning(f"⚠️  [MANUAL SCRAPE] Error during auto-categorization (no email): {cat_err}")
                else:
                    logger.debug(f"✅ [MANUAL SCRAPE] Preserving existing category '{prospect.discovery_category}' for {domain} (no email found)")
            
            logger.info(f"⚠️  [MANUAL SCRAPE] No emails found for {domain}")
        
        await db.commit()
        await db.refresh(prospect)
        
        return ManualScrapeResponse(
            success=True,
            prospect_id=str(prospect.id),
            message=f"Scraped {domain}: {'Found emails' if all_emails else 'No emails found'}",
            is_followup=is_followup
        )
    
    except Exception as e:
        logger.error(f"❌ [MANUAL SCRAPE] Failed to scrape {domain}: {e}", exc_info=True)
        prospect.scrape_status = ScrapeStatus.FAILED.value
        await db.commit()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to scrape website: {str(e)}"
        )


@router.post("/verify", response_model=ManualVerifyResponse)
async def manual_verify(
    request: ManualVerifyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Manually verify an email
    
    Behavior:
    - If email exists → verify existing Prospect email
    - If email does not exist → create Prospect with email only
    - Run Snov verification
    - Update verification_status
    """
    email = request.email.strip().lower()
    
    logger.info(f"✅ [MANUAL VERIFY] Verifying email: {email}")
    
    # Extract domain from email
    if "@" not in email:
        raise HTTPException(status_code=400, detail="Invalid email format")
    
    domain = email.split("@")[1]
    
    # Check if prospect with this email already exists
    existing = await db.execute(
        select(Prospect).where(Prospect.contact_email == email)
    )
    existing_prospect = existing.scalar_one_or_none()
    
    is_followup = existing_prospect is not None
    
    if existing_prospect:
        # Email exists → verify existing Prospect email
        logger.info(f"📌 [MANUAL VERIFY] Email {email} already exists (prospect_id: {existing_prospect.id}) - verifying")
        prospect = existing_prospect
        
        # Set up thread tracking for follow-up
        # Use existing prospect's thread_id, or create one if it doesn't have one
        if not prospect.thread_id:
            prospect.thread_id = existing_prospect.id
        # Increment sequence_index for follow-up
        prospect.sequence_index = (existing_prospect.sequence_index or 0) + 1
        logger.info(f"📌 [MANUAL VERIFY] Set up follow-up tracking: thread_id={prospect.thread_id}, sequence={prospect.sequence_index}")
    else:
        # Email does not exist → create Prospect with email only
        prospect = Prospect(
            domain=domain,
            contact_email=email,
            discovery_status=DiscoveryStatus.DISCOVERED.value,
            scrape_status=ScrapeStatus.ENRICHED.value,  # Manually added = already "enriched"
            verification_status=VerificationStatus.PENDING.value,
            is_manual=True,
            stage=ProspectStage.EMAIL_FOUND.value,
        )
        db.add(prospect)
        await db.commit()
        await db.refresh(prospect)
        logger.info(f"✅ [MANUAL VERIFY] Created new manual prospect for email {email} (prospect_id: {prospect.id})")
    
    # Run Snov verification
    try:
        snov_client = SnovIOClient()
        
        # Use domain search to verify email
        snov_result = await snov_client.domain_search(domain)
        
        if snov_result.get("success") and snov_result.get("emails"):
            # Check if email is in Snov results
            verified = False
            confidence = 0.0
            email_lower = email.lower()
            
            for email_data in snov_result.get("emails", []):
                if not isinstance(email_data, dict):
                    continue
                
                email_value = email_data.get("value", "").lower()
                if email_value == email_lower:
                    verified = True
                    confidence = float(email_data.get("confidence_score", 0) or 0)
                    break
            
            if verified:
                prospect.verification_status = VerificationStatus.VERIFIED.value
                prospect.verification_confidence = confidence
                prospect.verification_payload = snov_result
                prospect.stage = ProspectStage.LEAD.value  # Verified email = ready to be a lead
                verification_status_str = "verified"
            else:
                prospect.verification_status = VerificationStatus.UNVERIFIED.value
                prospect.verification_payload = snov_result
                verification_status_str = "unverified"
            
            await db.commit()
            await db.refresh(prospect)
            
            logger.info(f"✅ [MANUAL VERIFY] Verified email {email}: {verification_status_str}")
            
            return ManualVerifyResponse(
                success=True,
                prospect_id=str(prospect.id),
                message=f"Email verified: {verification_status_str}",
                verification_status=verification_status_str,
                is_followup=is_followup
            )
        else:
            error = snov_result.get("error", "No emails found in Snov results")
            logger.error(f"❌ [MANUAL VERIFY] Verification failed for {email}: {error}")
            prospect.verification_status = VerificationStatus.FAILED.value
            prospect.verification_payload = snov_result
            await db.commit()
            raise HTTPException(
                status_code=500,
                detail=f"Email verification failed: {error}"
            )

    except HTTPException:
        # Preserve the original HTTP status + detail (do not wrap into a generic 500)
        raise

    except Exception as e:
        logger.error(f"❌ [MANUAL VERIFY] Failed to verify {email}: {e}", exc_info=True)
        prospect.verification_status = VerificationStatus.FAILED.value
        await db.commit()
        detail = str(e) or f"{type(e).__name__}"
        raise HTTPException(
            status_code=500,
            detail=f"Failed to verify email: {detail}"
        )

