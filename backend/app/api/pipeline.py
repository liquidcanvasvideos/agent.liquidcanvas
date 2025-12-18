"""
STRICT PIPELINE API - Step-by-step lead acquisition with explicit progression
No auto-triggering, each step must be explicitly unlocked
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from typing import List, Optional, Dict
from uuid import UUID
import logging
from pydantic import BaseModel

from app.db.database import get_db
from app.api.auth import get_current_user_optional
from app.models.prospect import Prospect
from app.models.job import Job

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


# ============================================
# STEP 1: DISCOVERY
# ============================================

class DiscoveryRequest(BaseModel):
    categories: List[str]
    locations: List[str]
    keywords: Optional[str] = None
    max_results: Optional[int] = 100


class DiscoveryResponse(BaseModel):
    success: bool
    job_id: UUID
    message: str
    prospects_count: int


@router.post("/discover", response_model=DiscoveryResponse)
async def discover_websites(
    request: DiscoveryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    STEP 1: Discover websites using DataForSEO
    
    Requirements:
    - Categories (multi-select, required)
    - Locations (multi-select, required)
    - Keywords (optional)
    
    Saves prospects with:
    - discovery_status = "DISCOVERED"
    - NO scraping
    - NO enrichment
    - NO email guessing
    """
    if not request.categories or len(request.categories) == 0:
        raise HTTPException(status_code=400, detail="At least one category is required")
    
    if not request.locations or len(request.locations) == 0:
        raise HTTPException(status_code=400, detail="At least one location is required")
    
    logger.info(f"🔍 [PIPELINE STEP 1] Discovery request - categories: {request.categories}, locations: {request.locations}, keywords: {request.keywords}")
    
    # Create discovery job
    job = Job(
        job_type="discover",
        params={
            "categories": request.categories,
            "locations": request.locations,
            "keywords": request.keywords,
            "max_results": request.max_results or 100,
            "pipeline_mode": True,  # Flag to indicate strict pipeline mode
        },
        status="pending"
    )
    
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    # Start discovery task in background
    try:
        from app.tasks.discovery import discover_websites_async
        import asyncio
        from app.task_manager import register_task
        
        task = asyncio.create_task(discover_websites_async(str(job.id)))
        register_task(str(job.id), task)
        logger.info(f"✅ [PIPELINE STEP 1] Discovery job {job.id} started")
    except Exception as e:
        logger.error(f"❌ [PIPELINE STEP 1] Failed to start discovery job: {e}", exc_info=True)
        job.status = "failed"
        job.error_message = str(e)
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to start discovery job: {str(e)}")
    
    return DiscoveryResponse(
        success=True,
        job_id=job.id,
        message=f"Discovery job started. Finding websites in {len(request.categories)} categories and {len(request.locations)} locations.",
        prospects_count=0  # Will be updated when job completes
    )


# ============================================
# STEP 2: HUMAN SELECTION
# ============================================

class ApprovalRequest(BaseModel):
    prospect_ids: List[UUID]
    action: str  # "approve" or "reject" or "delete"


class ApprovalResponse(BaseModel):
    success: bool
    approved_count: int
    rejected_count: int
    deleted_count: int
    message: str


@router.post("/approve", response_model=ApprovalResponse)
async def approve_prospects(
    request: ApprovalRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    STEP 2: Human selection - approve/reject/delete discovered websites
    
    Requirements:
    - At least one prospect must be approved to proceed
    - Rejected/deleted prospects are blocked from further steps
    """
    if request.action not in ["approve", "reject", "delete"]:
        raise HTTPException(status_code=400, detail="Action must be 'approve', 'reject', or 'delete'")
    
    if not request.prospect_ids or len(request.prospect_ids) == 0:
        raise HTTPException(status_code=400, detail="At least one prospect ID is required")
    
    logger.info(f"👤 [PIPELINE STEP 2] {request.action.capitalize()} request for {len(request.prospect_ids)} prospects")
    
    # Get prospects
    result = await db.execute(
        select(Prospect).where(
            Prospect.id.in_(request.prospect_ids),
            Prospect.discovery_status == "DISCOVERED"  # Only allow approval of discovered prospects
        )
    )
    prospects = result.scalars().all()
    
    if len(prospects) != len(request.prospect_ids):
        raise HTTPException(status_code=404, detail="Some prospects not found or not in DISCOVERED status")
    
    approved_count = 0
    rejected_count = 0
    deleted_count = 0
    
    for prospect in prospects:
        if request.action == "approve":
            prospect.approval_status = "approved"
            approved_count += 1
        elif request.action == "reject":
            prospect.approval_status = "rejected"
            rejected_count += 1
        elif request.action == "delete":
            db.delete(prospect)
            deleted_count += 1
    
    await db.commit()
    
    logger.info(f"✅ [PIPELINE STEP 2] {request.action.capitalize()}d {len(prospects)} prospects")
    
    return ApprovalResponse(
        success=True,
        approved_count=approved_count,
        rejected_count=rejected_count,
        deleted_count=deleted_count,
        message=f"Successfully {request.action}d {len(prospects)} prospect(s)"
    )


# ============================================
# STEP 3: SCRAPING
# ============================================

class ScrapeRequest(BaseModel):
    prospect_ids: Optional[List[UUID]] = None  # If None, scrape all approved


class ScrapeResponse(BaseModel):
    success: bool
    job_id: UUID
    message: str
    prospects_count: int


@router.post("/scrape", response_model=ScrapeResponse)
async def scrape_websites(
    request: ScrapeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    STEP 3: Scrape approved websites for emails
    
    Requirements:
    - Only approved prospects can be scraped
    - Crawls homepage + contact/about pages
    - Extracts visible emails only
    - Sets scrape_status = "SCRAPED" or "NO_EMAIL_FOUND"
    """
    # Get approved prospects ready for scraping
    query = select(Prospect).where(
        Prospect.approval_status == "approved",
        Prospect.scrape_status == "pending"
    )
    
    if request.prospect_ids:
        query = query.where(Prospect.id.in_(request.prospect_ids))
    
    result = await db.execute(query)
    prospects = result.scalars().all()
    
    if len(prospects) == 0:
        raise HTTPException(
            status_code=400,
            detail="No approved prospects found ready for scraping. Ensure prospects are approved in Step 2."
        )
    
    logger.info(f"🔍 [PIPELINE STEP 3] Scraping {len(prospects)} approved prospects")
    
    # Create scraping job
    job = Job(
        job_type="scrape",
        params={
            "prospect_ids": [str(p.id) for p in prospects],
            "pipeline_mode": True,
        },
        status="pending"
    )
    
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    # Start scraping task in background
    try:
        from app.tasks.scraping import scrape_prospects_async
        import asyncio
        from app.task_manager import register_task
        
        task = asyncio.create_task(scrape_prospects_async(str(job.id)))
        register_task(str(job.id), task)
        logger.info(f"✅ [PIPELINE STEP 3] Scraping job {job.id} started")
    except Exception as e:
        logger.error(f"❌ [PIPELINE STEP 3] Failed to start scraping job: {e}", exc_info=True)
        job.status = "failed"
        job.error_message = str(e)
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to start scraping job: {str(e)}")
    
    return ScrapeResponse(
        success=True,
        job_id=job.id,
        message=f"Scraping job started for {len(prospects)} approved prospects",
        prospects_count=len(prospects)
    )


# ============================================
# STEP 4: VERIFICATION (SNOV)
# ============================================

class VerifyRequest(BaseModel):
    prospect_ids: Optional[List[UUID]] = None  # If None, verify all scraped


class VerifyResponse(BaseModel):
    success: bool
    job_id: UUID
    message: str
    prospects_count: int


@router.post("/verify", response_model=VerifyResponse)
async def verify_emails(
    request: VerifyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    STEP 4: Verify emails using Snov.io
    
    Requirements:
    - Only scraped prospects can be verified
    - If scraped emails exist → verify them
    - Else → attempt domain search via Snov
    - Sets verification_status = "verified" or "unverified"
    - Never overwrites scraped emails without confirmation
    """
    # Get scraped prospects ready for verification
    query = select(Prospect).where(
        Prospect.scrape_status.in_(["SCRAPED", "NO_EMAIL_FOUND"]),
        Prospect.verification_status == "pending"
    )
    
    if request.prospect_ids:
        query = query.where(Prospect.id.in_(request.prospect_ids))
    
    result = await db.execute(query)
    prospects = result.scalars().all()
    
    if len(prospects) == 0:
        raise HTTPException(
            status_code=400,
            detail="No scraped prospects found ready for verification. Ensure prospects are scraped in Step 3."
        )
    
    logger.info(f"✅ [PIPELINE STEP 4] Verifying {len(prospects)} scraped prospects")
    
    # Create verification job
    job = Job(
        job_type="verify",
        params={
            "prospect_ids": [str(p.id) for p in prospects],
            "pipeline_mode": True,
        },
        status="pending"
    )
    
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    # Start verification task in background
    try:
        from app.tasks.verification import verify_prospects_async
        import asyncio
        from app.task_manager import register_task
        
        task = asyncio.create_task(verify_prospects_async(str(job.id)))
        register_task(str(job.id), task)
        logger.info(f"✅ [PIPELINE STEP 4] Verification job {job.id} started")
    except Exception as e:
        logger.error(f"❌ [PIPELINE STEP 4] Failed to start verification job: {e}", exc_info=True)
        job.status = "failed"
        job.error_message = str(e)
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to start verification job: {str(e)}")
    
    return VerifyResponse(
        success=True,
        job_id=job.id,
        message=f"Verification job started for {len(prospects)} scraped prospects",
        prospects_count=len(prospects)
    )


# ============================================
# STEP 5: EMAIL REVIEW (Status check only)
# ============================================

@router.get("/review")
async def get_review_prospects(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    STEP 5: Get prospects ready for email review
    
    Returns prospects with verified emails for manual review
    """
    result = await db.execute(
        select(Prospect).where(
            Prospect.verification_status.in_(["verified", "unverified"]),
            Prospect.contact_email.isnot(None)
        )
        .offset(skip)
        .limit(limit)
    )
    prospects = result.scalars().all()
    
    total_result = await db.execute(
        select(func.count(Prospect.id)).where(
            Prospect.verification_status.in_(["verified", "unverified"]),
            Prospect.contact_email.isnot(None)
        )
    )
    total = total_result.scalar() or 0
    
    return {
        "data": [{
            "id": str(p.id),
            "domain": p.domain,
            "email": p.contact_email,
            "source": p.scrape_source_url or "Snov.io",
            "type": "generic" if p.contact_email and "@" in p.contact_email else "unknown",
            "confidence": float(p.verification_confidence) if p.verification_confidence else None,
            "verification_status": p.verification_status,
        } for p in prospects],
        "total": total,
        "skip": skip,
        "limit": limit
    }


# ============================================
# STEP 6: OUTREACH DRAFTING (GEMINI)
# ============================================

class DraftRequest(BaseModel):
    prospect_ids: List[UUID]


class DraftResponse(BaseModel):
    success: bool
    job_id: UUID
    message: str
    prospects_count: int


@router.post("/draft", response_model=DraftResponse)
async def draft_emails(
    request: DraftRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    STEP 6: Generate email drafts using Gemini
    
    Requirements:
    - Only verified prospects can be drafted
    - Gemini receives: website info, category, location, email type, outreach intent
    - Sets draft_status = "drafted"
    """
    # Get verified prospects ready for drafting
    result = await db.execute(
        select(Prospect).where(
            Prospect.id.in_(request.prospect_ids),
            Prospect.verification_status.in_(["verified", "unverified"]),
            Prospect.contact_email.isnot(None),
            Prospect.draft_status == "pending"
        )
    )
    prospects = result.scalars().all()
    
    if len(prospects) != len(request.prospect_ids):
        raise HTTPException(
            status_code=400,
            detail="Some prospects not found or not ready for drafting. Ensure they are verified and have emails."
        )
    
    logger.info(f"✍️  [PIPELINE STEP 6] Drafting emails for {len(prospects)} verified prospects")
    
    # Create drafting job
    job = Job(
        job_type="draft",
        params={
            "prospect_ids": [str(p.id) for p in prospects],
            "pipeline_mode": True,
        },
        status="pending"
    )
    
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    # Start drafting task in background
    try:
        from app.tasks.drafting import draft_prospects_async
        import asyncio
        from app.task_manager import register_task
        
        task = asyncio.create_task(draft_prospects_async(str(job.id)))
        register_task(str(job.id), task)
        logger.info(f"✅ [PIPELINE STEP 6] Drafting job {job.id} started")
    except Exception as e:
        logger.error(f"❌ [PIPELINE STEP 6] Failed to start drafting job: {e}", exc_info=True)
        job.status = "failed"
        job.error_message = str(e)
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to start drafting job: {str(e)}")
    
    return DraftResponse(
        success=True,
        job_id=job.id,
        message=f"Drafting job started for {len(prospects)} verified prospects",
        prospects_count=len(prospects)
    )


# ============================================
# STEP 7: SENDING
# ============================================

class SendRequest(BaseModel):
    prospect_ids: List[UUID]


class SendResponse(BaseModel):
    success: bool
    job_id: UUID
    message: str
    prospects_count: int


@router.post("/send", response_model=SendResponse)
async def send_emails(
    request: SendRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    STEP 7: Send emails using Gmail API
    
    Requirements:
    - Only drafted prospects can be sent
    - Uses Gmail API
    - Sets send_status = "sent" or "failed"
    - Logs success or failure
    """
    # Get drafted prospects ready for sending
    result = await db.execute(
        select(Prospect).where(
            Prospect.id.in_(request.prospect_ids),
            Prospect.draft_status == "drafted",
            Prospect.draft_subject.isnot(None),
            Prospect.draft_body.isnot(None),
            Prospect.send_status == "pending"
        )
    )
    prospects = result.scalars().all()
    
    if len(prospects) != len(request.prospect_ids):
        raise HTTPException(
            status_code=400,
            detail="Some prospects not found or not ready for sending. Ensure they are drafted with subject and body."
        )
    
    logger.info(f"📧 [PIPELINE STEP 7] Sending emails for {len(prospects)} drafted prospects")
    
    # Create sending job
    job = Job(
        job_type="send",
        params={
            "prospect_ids": [str(p.id) for p in prospects],
            "pipeline_mode": True,
        },
        status="pending"
    )
    
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    # Start sending task in background
    try:
        from app.tasks.send import send_prospects_async
        import asyncio
        from app.task_manager import register_task
        
        task = asyncio.create_task(send_prospects_async(str(job.id)))
        register_task(str(job.id), task)
        logger.info(f"✅ [PIPELINE STEP 7] Sending job {job.id} started")
    except Exception as e:
        logger.error(f"❌ [PIPELINE STEP 7] Failed to start sending job: {e}", exc_info=True)
        job.status = "failed"
        job.error_message = str(e)
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to start sending job: {str(e)}")
    
    return SendResponse(
        success=True,
        job_id=job.id,
        message=f"Sending job started for {len(prospects)} drafted prospects",
        prospects_count=len(prospects)
    )


# ============================================
# PIPELINE STATUS
# ============================================

@router.get("/status")
async def get_pipeline_status(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Get overall pipeline status - counts for each step
    BULLETPROOF: Only queries the four guaranteed columns that exist via startup hook
    Returns 200 even with zero prospects or missing optional columns
    """
    # Count prospects at each step using ONLY the four guaranteed columns
    # Step 1: DISCOVERED (canonical status for discovered websites)
    discovered = await db.execute(
        select(func.count(Prospect.id)).where(Prospect.discovery_status == "DISCOVERED")
    )
    discovered_count = discovered.scalar() or 0
    
    # Step 2: APPROVED (approval_status = "approved")
    approved = await db.execute(
        select(func.count(Prospect.id)).where(Prospect.approval_status == "approved")
    )
    approved_count = approved.scalar() or 0
    
    # Step 3: SCRAPED (scrape_status = "SCRAPED" or "ENRICHED")
    # Count both SCRAPED (emails found via scraping) and ENRICHED (emails found via enrichment)
    scraped = await db.execute(
        select(func.count(Prospect.id)).where(
            Prospect.scrape_status.in_(["SCRAPED", "ENRICHED"])
        )
    )
    scraped_count = scraped.scalar() or 0
    
    # Also count DISCOVERED (ready for scraping)
    discovered_for_scraping = await db.execute(
        select(func.count(Prospect.id)).where(Prospect.scrape_status == "DISCOVERED")
    )
    discovered_for_scraping_count = discovered_for_scraping.scalar() or 0
    
    # Step 4: VERIFIED (verification_status = "verified")
    verified = await db.execute(
        select(func.count(Prospect.id)).where(Prospect.verification_status == "verified")
    )
    verified_count = verified.scalar() or 0
    
    # Return pipeline status counts
    # scrape_status lifecycle: DISCOVERED → SCRAPED → ENRICHED → EMAILED (send_status)
    # All queries are defensive and return 0 if no rows exist
    return {
        "discovered": discovered_count,
        "approved": approved_count,
        "scraped": scraped_count,  # Includes both SCRAPED and ENRICHED
        "discovered_for_scraping": discovered_for_scraping_count,  # DISCOVERED status
        "verified": verified_count,
        "reviewed": verified_count,  # Same as verified for review step
    }


# ============================================
# WEBSITES ENDPOINT (Discovery Results)
# ============================================

@router.get("/websites")
async def get_websites(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Get discovered websites (discovery results)
    
    Returns prospects with discovery_status = "DISCOVERED"
    These are websites found during discovery, not yet scraped
    """
    result = await db.execute(
        select(Prospect).where(
            Prospect.discovery_status == "DISCOVERED"
        )
        .order_by(Prospect.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    websites = result.scalars().all()
    
    total_result = await db.execute(
        select(func.count(Prospect.id)).where(
            Prospect.discovery_status == "DISCOVERED"
        )
    )
    total = total_result.scalar() or 0
    
    return {
        "data": [{
            "id": str(p.id),
            "domain": p.domain,
            "url": p.url or f"https://{p.domain}",
            "title": p.page_title or p.domain,
            "category": p.discovery_category or "Unknown",
            "location": p.discovery_location or "Unknown",
            "discovery_job_id": str(p.discovery_query_id) if p.discovery_query_id else None,
            "discovered_at": p.created_at.isoformat() if p.created_at else None,
            "scrape_status": p.scrape_status or "DISCOVERED",
            "approval_status": p.approval_status or "PENDING",
        } for p in websites],
        "total": total,
        "skip": skip,
        "limit": limit
    }
    return {
        "discovered": discovered_count,
        "approved": approved_count,
        "scraped": scraped_count,  # Includes both SCRAPED and ENRICHED
        "discovered_for_scraping": discovered_for_scraping_count,  # DISCOVERED status (ready for scraping)
        "verified": verified_count,
        "reviewed": verified_count,  # Same as verified for review step
    }

