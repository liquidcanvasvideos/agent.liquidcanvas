"""
STRICT PIPELINE API - Step-by-step lead acquisition with explicit progression
No auto-triggering, each step must be explicitly unlocked
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_, func, text
from typing import List, Optional
from uuid import UUID
import logging
from pydantic import BaseModel

from app.db.database import get_db
from app.api.auth import get_current_user_optional
from app.api.scraper import check_master_switch
from app.models.prospect import (
    Prospect,
    DiscoveryStatus,
    ScrapeStatus,
    VerificationStatus,
    DraftStatus,
    SendStatus,
    ProspectStage,
)
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
    
    # Check master switch
    master_enabled = await check_master_switch(db)
    if not master_enabled:
        raise HTTPException(
            status_code=403,
            detail="Master switch is disabled. Please enable it in Automation Control to run pipeline activities."
        )
    
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
        try:
            await db.rollback()  # Rollback on exception to prevent transaction poisoning
            job.status = "failed"
            job.error_message = str(e)
            await db.commit()
        except Exception as rollback_err:
            logger.error(f"❌ [PIPELINE STEP 1] Error during rollback: {rollback_err}", exc_info=True)
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


@router.post("/approve_all", response_model=ApprovalResponse)
async def approve_all_prospects(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional),
):
    """
    Bulk-approve ALL discovered websites in one action.

    This is used by the pipeline UI "Approve All Websites" CTA to avoid
    deadlocking users when they have discovered websites but none are approved yet.
    """
    # Check master switch
    master_enabled = await check_master_switch(db)
    if not master_enabled:
        raise HTTPException(
            status_code=403,
            detail="Master switch is disabled. Please enable it in Automation Control to run pipeline activities."
        )
    
    # Find all discovered WEBSITE prospects that are not yet approved
    # CRITICAL: Filter by source_type='website' to separate from social outreach
    website_filter = or_(
        Prospect.source_type == 'website',
        Prospect.source_type.is_(None)  # Legacy prospects (default to website)
    )
    
    result = await db.execute(
        select(Prospect).where(
            and_(
                Prospect.discovery_status == DiscoveryStatus.DISCOVERED.value,
                Prospect.approval_status != "approved",
                website_filter
            )
        )
    )
    prospects = result.scalars().all()

    if not prospects:
        raise HTTPException(
            status_code=400,
            detail="No discovered prospects found to approve.",
        )

    approved_count = 0
    for prospect in prospects:
        prospect.approval_status = "approved"
        approved_count += 1

    await db.commit()

    logger.info(
        f"✅ [PIPELINE STEP 2] Bulk-approved {approved_count} discovered prospects"
    )

    return ApprovalResponse(
        success=True,
        approved_count=approved_count,
        rejected_count=0,
        deleted_count=0,
        message=f"Successfully approved {approved_count} discovered prospect(s)",
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
    - Any discovered prospect can be scraped
    - Explicitly rejected prospects are excluded
    - Crawls homepage + contact/about pages
    - Extracts visible emails only
    - Sets scrape_status = "SCRAPED" or "NO_EMAIL_FOUND"
    """
    # Check master switch
    master_enabled = await check_master_switch(db)
    if not master_enabled:
        raise HTTPException(
            status_code=403,
            detail="Master switch is disabled. Please enable it in Automation Control to run pipeline activities."
        )
    
    # CRITICAL: Filter by source_type='website' to separate from social outreach
    website_filter = or_(
        Prospect.source_type == 'website',
        Prospect.source_type.is_(None)  # Legacy prospects (default to website)
    )
    
    # Get discovered, non-rejected WEBSITE prospects ready for scraping
    # Scrape eligibility:
    # - discovery_status == DISCOVERED
    # - approval_status is NOT "rejected" (NULL or any other value is allowed)
    # - scrape_status == DISCOVERED (avoid re-scraping already processed prospects)
    # - source_type='website' (only website prospects)
    query = select(Prospect).where(
        and_(
            Prospect.discovery_status == DiscoveryStatus.DISCOVERED.value,
            or_(
                Prospect.approval_status.is_(None),
                Prospect.approval_status != "rejected",
            ),
            Prospect.scrape_status == ScrapeStatus.DISCOVERED.value,
            website_filter  # Only website prospects
        )
    )
    
    if request.prospect_ids:
        query = query.where(Prospect.id.in_(request.prospect_ids))
    
    try:
        result = await db.execute(query)
        prospects = result.scalars().all()
    except Exception as query_err:
        logger.error(f"❌ [PIPELINE STEP 3] Query error: {query_err}", exc_info=True)
        await db.rollback()  # Rollback on query failure
        raise HTTPException(status_code=500, detail=f"Database query failed: {str(query_err)}")
    
    if len(prospects) == 0:
        raise HTTPException(
            status_code=400,
            detail="No discovered prospects available for scraping."
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
    
    try:
        db.add(job)
        await db.commit()
        await db.refresh(job)
    except Exception as commit_err:
        logger.error(f"❌ [PIPELINE STEP 3] Commit error: {commit_err}", exc_info=True)
        await db.rollback()  # Rollback on commit failure
        raise HTTPException(status_code=500, detail=f"Failed to create scraping job: {str(commit_err)}")
    
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
        try:
            await db.rollback()  # Rollback on exception
            job.status = "failed"
            job.error_message = str(e)
            await db.commit()
        except Exception as rollback_err:
            logger.error(f"❌ [PIPELINE STEP 3] Error during rollback: {rollback_err}", exc_info=True)
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
    # Check master switch
    master_enabled = await check_master_switch(db)
    if not master_enabled:
        raise HTTPException(
            status_code=403,
            detail="Master switch is disabled. Please enable it in Automation Control to run pipeline activities."
        )
    
    # CRITICAL: Filter by source_type='website' to separate from social outreach
    website_filter = or_(
        Prospect.source_type == 'website',
        Prospect.source_type.is_(None)  # Legacy prospects (default to website)
    )
    
    # Get WEBSITE prospects ready for verification
    # REMOVED: Hard stage filtering (stage = LEAD)
    # Use status flags instead: scraped + email + not already verified + source_type='website'
    # Note: Default verification_status is "UNVERIFIED", not "pending"
    try:
        query = select(Prospect).where(
            and_(
                Prospect.scrape_status.in_([ScrapeStatus.SCRAPED.value, ScrapeStatus.ENRICHED.value]),
                Prospect.contact_email.isnot(None),
                # Include prospects that are NOT already verified
                # Default status is "UNVERIFIED", but also check for "pending" and "unverified"
                Prospect.verification_status != VerificationStatus.VERIFIED.value,
                website_filter  # Only website prospects
            )
        )
        if request.prospect_ids:
            query = query.where(Prospect.id.in_(request.prospect_ids))
        
        result = await db.execute(query)
        prospects = result.scalars().all()
    except Exception as e:
        logger.error(f"❌ [PIPELINE STEP 4] Query error: {e}", exc_info=True)
        await db.rollback()  # Rollback on query failure
        raise HTTPException(status_code=500, detail=f"Database query failed: {str(e)}")
    
    if len(prospects) == 0:
        raise HTTPException(
            status_code=400,
            detail="No scraped prospects with emails found ready for verification. Ensure prospects are scraped and have emails in Step 3."
        )
    
    logger.info(f"✅ [PIPELINE STEP 4] Verifying {len(prospects)} scraped prospects with emails")
    
    # Create verification job
    job = Job(
        job_type="verify",
        params={
            "prospect_ids": [str(p.id) for p in prospects],
            "pipeline_mode": True,
        },
        status="pending"
    )
    
    try:
        db.add(job)
        await db.commit()
        await db.refresh(job)
    except Exception as commit_err:
        logger.error(f"❌ [PIPELINE STEP 4] Commit error: {commit_err}", exc_info=True)
        await db.rollback()  # Rollback on commit failure
        raise HTTPException(status_code=500, detail=f"Failed to create verification job: {str(commit_err)}")
    
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
        try:
            await db.rollback()  # Rollback on exception
            job.status = "failed"
            job.error_message = str(e)
            await db.commit()
        except Exception as rollback_err:
            logger.error(f"❌ [PIPELINE STEP 4] Error during rollback: {rollback_err}", exc_info=True)
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
    prospect_ids: Optional[List[UUID]] = None


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
    
    Requirements (DATA-DRIVEN):
    - verification_status = 'verified'
    - contact_email IS NOT NULL
    - draft_status = 'pending' (not already drafted)
    
    If prospect_ids provided, use those (manual selection).
    If prospect_ids empty or not provided, query all draft-ready prospects automatically.
    """
    # Check master switch
    master_enabled = await check_master_switch(db)
    if not master_enabled:
        raise HTTPException(
            status_code=403,
            detail="Master switch is disabled. Please enable it in Automation Control to run pipeline activities."
        )
    
    # DATA-DRIVEN: Query draft-ready prospects directly from database
    # Draft-ready = verified + email + (draft_status = 'pending' OR draft_status IS NULL)
    # Accept NULL for existing prospects created before draft_status column was added
    prospects = []  # Initialize prospects list
    
    # CRITICAL: Filter by source_type='website' to separate from social outreach
    website_filter = or_(
        Prospect.source_type == 'website',
        Prospect.source_type.is_(None)  # Legacy prospects (default to website)
    )
    
    if request.prospect_ids is not None and len(request.prospect_ids) > 0:
        # Manual selection: use provided prospect_ids but validate they meet draft-ready criteria
        result = await db.execute(
            select(Prospect).where(
                and_(
                    Prospect.id.in_(request.prospect_ids),
                    Prospect.verification_status == VerificationStatus.VERIFIED.value,
                    Prospect.contact_email.isnot(None),
                    or_(
                        Prospect.draft_status == DraftStatus.PENDING.value,
                        Prospect.draft_status.is_(None)
                    ),
                    website_filter  # Only website prospects
                )
        )
    )
    prospects = result.scalars().all()
    
    if len(prospects) != len(request.prospect_ids):
        raise HTTPException(
                status_code=422,
                detail=f"Some prospects not found or not ready for drafting. Found {len(prospects)} ready out of {len(request.prospect_ids)} requested. Ensure they are verified, have emails, and draft_status is 'pending' or NULL."
            )
    else:
        # Automatic: query all draft-ready WEBSITE prospects
        # First, let's check what we have in the database for debugging
        debug_verified = await db.execute(
            select(func.count(Prospect.id)).where(
                and_(
                    Prospect.verification_status == VerificationStatus.VERIFIED.value,
                    website_filter
                )
            )
        )
        verified_total = debug_verified.scalar() or 0
        
        debug_with_email = await db.execute(
            select(func.count(Prospect.id)).where(
                and_(
                    Prospect.verification_status == VerificationStatus.VERIFIED.value,
                    Prospect.contact_email.isnot(None),
                    website_filter
                )
            )
        )
        verified_with_email = debug_with_email.scalar() or 0
        
        debug_draft_status = await db.execute(
            select(func.count(Prospect.id)).where(
                Prospect.verification_status == VerificationStatus.VERIFIED.value,
                Prospect.contact_email.isnot(None),
                Prospect.draft_status == DraftStatus.PENDING.value
            )
        )
        verified_pending = debug_draft_status.scalar() or 0
        
        debug_draft_null = await db.execute(
            select(func.count(Prospect.id)).where(
                Prospect.verification_status == VerificationStatus.VERIFIED.value,
                Prospect.contact_email.isnot(None),
                Prospect.draft_status.is_(None)
            )
        )
        verified_null = debug_draft_null.scalar() or 0
        
        # Check what draft_status values actually exist
        debug_draft_statuses = await db.execute(
            select(Prospect.draft_status, func.count(Prospect.id)).where(
                Prospect.verification_status == VerificationStatus.VERIFIED.value,
                Prospect.contact_email.isnot(None)
            ).group_by(Prospect.draft_status)
        )
        draft_status_counts = {row[0]: row[1] for row in debug_draft_statuses.fetchall()}
        
        logger.info(f"🔍 [DRAFT DEBUG] Verified total: {verified_total}, With email: {verified_with_email}, Draft pending: {verified_pending}, Draft NULL: {verified_null}")
        logger.info(f"🔍 [DRAFT DEBUG] Draft status breakdown: {draft_status_counts}")
        
        # Query draft-ready prospects
        # SIMPLIFIED: Accept ALL verified prospects with emails, regardless of draft_status
        # The drafting task will handle setting draft_status correctly
        # This allows re-drafting if needed and handles any edge cases
        result = await db.execute(
            select(Prospect).where(
                Prospect.verification_status == VerificationStatus.VERIFIED.value,
                Prospect.contact_email.isnot(None)
                # No draft_status filter - accept all verified prospects with emails
            )
        )
        prospects = result.scalars().all()
        
        if len(prospects) == 0:
            error_detail = (
                f"No prospects ready for drafting. "
                f"Debug: verified_total={verified_total}, verified_with_email={verified_with_email}, "
                f"draft_pending={verified_pending}, draft_null={verified_null}. "
                f"Ensure prospects have verification_status='verified', contact_email IS NOT NULL, "
                f"and draft_status is 'pending' or NULL."
            )
            logger.warning(f"⚠️  [DRAFT] {error_detail}")
            raise HTTPException(
                status_code=422,
                detail=error_detail
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
    prospect_ids: Optional[List[UUID]] = None  # If None or empty, query all send-ready prospects automatically


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
    
    Requirements (DATA-DRIVEN):
    - contact_email IS NOT NULL
    - verification_status = 'verified'
    - draft_subject IS NOT NULL
    - draft_body IS NOT NULL
    - send_status != 'sent'
    
    If prospect_ids provided, use those (manual selection).
    If prospect_ids empty or not provided, query all send-ready prospects automatically.
    """
    # Check master switch
    master_enabled = await check_master_switch(db)
    if not master_enabled:
        raise HTTPException(
            status_code=403,
            detail="Master switch is disabled. Please enable it in Automation Control to run pipeline activities."
        )
    
    # DATA-DRIVEN: Query send-ready prospects directly from database
    # Redefine send-ready as: verified + drafted + not sent
    prospects = []  # Initialize prospects list
    
    # CRITICAL: Filter by source_type='website' to separate from social outreach
    website_filter = or_(
        Prospect.source_type == 'website',
        Prospect.source_type.is_(None)  # Legacy prospects (default to website)
    )
    
    if request.prospect_ids is not None and len(request.prospect_ids) > 0:
        # Manual selection: use provided prospect_ids but validate they meet send-ready criteria
        result = await db.execute(
            select(Prospect).where(
                and_(
                    Prospect.id.in_(request.prospect_ids),
                    Prospect.contact_email.isnot(None),
                    Prospect.verification_status == VerificationStatus.VERIFIED.value,
                    Prospect.draft_subject.isnot(None),
                    Prospect.draft_body.isnot(None),
                    Prospect.send_status != SendStatus.SENT.value,
                    website_filter  # Only website prospects
                )
        )
    )
    prospects = result.scalars().all()
    
    if len(prospects) != len(request.prospect_ids):
        raise HTTPException(
                status_code=422,
                detail=f"Some prospects not found or not ready for sending. Found {len(prospects)} ready out of {len(request.prospect_ids)} requested. Ensure they have verified email, draft subject, and draft body."
            )
    else:
        # Automatic: query all send-ready WEBSITE prospects
        result = await db.execute(
            select(Prospect).where(
                and_(
                    Prospect.contact_email.isnot(None),
                    Prospect.verification_status == VerificationStatus.VERIFIED.value,
                    Prospect.draft_subject.isnot(None),
                    Prospect.draft_body.isnot(None),
                    Prospect.send_status != SendStatus.SENT.value,
                    website_filter  # Only website prospects
                )
            )
        )
        prospects = result.scalars().all()
        
        if len(prospects) == 0:
            raise HTTPException(
                status_code=422,
                detail="No prospects ready for sending. Ensure prospects have verified email, draft subject, and draft body."
        )
    
    logger.info(f"📧 [PIPELINE STEP 7] Sending emails for {len(prospects)} send-ready prospects (data-driven)")
    
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
        from app.tasks.send import process_send_job
        import asyncio
        from app.task_manager import register_task
        
        task = asyncio.create_task(process_send_job(str(job.id)))
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
    DATA-DRIVEN: All counts derived ONLY from Prospect state, NOT from jobs
    This is the single source of truth for pipeline state.
    
    OPTIMIZED: Fast, read-only, idempotent. Minimal logging for performance.
    
    SINGLE SOURCE OF TRUTH MAPPING:
    - DISCOVERED → discovery_status = "DISCOVERED"
    - SCRAPED → scrape_status IN ("SCRAPED", "ENRICHED")
    - VERIFIED → verification_status = "VERIFIED"
    - DRAFTED → draft_status = "DRAFTED"
    - SENT → send_status = "SENT"
    """
    
    # Wrap entire endpoint in try-catch to handle transaction errors
    try:
        # CRITICAL: Filter by source_type='website' to separate from social outreach
        # Website outreach only shows website prospects
        website_filter = or_(
            Prospect.source_type == 'website',
            Prospect.source_type.is_(None)  # Legacy prospects (default to website)
        )
        
        # Step 1: DISCOVERED (canonical status for discovered websites)
        # SINGLE SOURCE OF TRUTH: discovery_status = "DISCOVERED" AND source_type='website'
        discovered = await db.execute(
            select(func.count(Prospect.id)).where(
                and_(
                    Prospect.discovery_status == DiscoveryStatus.DISCOVERED.value,
                    website_filter
                )
            )
        )
        discovered_count = discovered.scalar() or 0
        
        # Step 2: APPROVED (approval_status = "approved" AND source_type='website')
        approved = await db.execute(
            select(func.count(Prospect.id)).where(
                and_(
                    Prospect.approval_status == "approved",
                    website_filter
                )
            )
        )
        approved_count = approved.scalar() or 0
        
        # Step 3: SCRAPED = Prospects with scrape_status IN ("SCRAPED", "ENRICHED") AND source_type='website'
        # SINGLE SOURCE OF TRUTH: scrape_status IN ("SCRAPED", "ENRICHED") AND source_type='website'
        scraped = await db.execute(
            select(func.count(Prospect.id)).where(
                and_(
                    Prospect.scrape_status.in_([
                        ScrapeStatus.SCRAPED.value,
                        ScrapeStatus.ENRICHED.value
                    ]),
                    website_filter
                )
            )
        )
        scraped_count = scraped.scalar() or 0
        
        # Scrape-ready: any DISCOVERED prospect that has NOT been explicitly rejected AND source_type='website'
        # This unlocks scraping as soon as at least one website has been discovered,
        # while still allowing optional manual rejection to exclude sites.
        scrape_ready = await db.execute(
            select(func.count(Prospect.id)).where(
                and_(
                    Prospect.discovery_status == DiscoveryStatus.DISCOVERED.value,
                    Prospect.approval_status != "rejected",
                    website_filter
                )
            )
        )
        scrape_ready_count = scrape_ready.scalar() or 0
        
        # Stage-based counts (defensive: check if stage column exists)
        email_found_count = 0
        leads_count = 0
        verified_stage_count = 0
        
        try:
            # Check if stage column exists using raw SQL
            column_check = await db.execute(
                text("""
                    SELECT column_name
                    FROM information_schema.columns 
                    WHERE table_name = 'prospects' 
                    AND column_name = 'stage'
                """)
            )
            if column_check.fetchone():
                # Column exists - use raw SQL to query safely
                # EMAIL_FOUND: prospects with emails found but not yet promoted to LEAD AND source_type='website'
                email_found_result = await db.execute(
                    text("""
                        SELECT COUNT(*) 
                        FROM prospects 
                        WHERE stage = :stage_value
                        AND (source_type = 'website' OR source_type IS NULL)
                    """),
                    {"stage_value": ProspectStage.EMAIL_FOUND.value}
                )
                email_found_count = email_found_result.scalar() or 0
                
                # LEAD: explicitly promoted leads (ready for outreach) AND source_type='website'
                leads_result = await db.execute(
                    text("""
                        SELECT COUNT(*) 
                        FROM prospects 
                        WHERE stage = :stage_value
                        AND (source_type = 'website' OR source_type IS NULL)
                    """),
                    {"stage_value": ProspectStage.LEAD.value}
                )
                leads_count = leads_result.scalar() or 0
                
                # VERIFIED: prospects with verified emails AND source_type='website'
                verified_stage_result = await db.execute(
                    text("""
                        SELECT COUNT(*) 
                        FROM prospects 
                        WHERE stage = :stage_value
                        AND (source_type = 'website' OR source_type IS NULL)
                    """),
                    {"stage_value": ProspectStage.VERIFIED.value}
                )
                verified_stage_count = verified_stage_result.scalar() or 0
            else:
                # Column doesn't exist yet - fallback to scrape_status + email
                logger.warning("⚠️  stage column not found, using fallback logic for stage counts")
                # Fallback: count website prospects with emails as EMAIL_FOUND
                email_found_fallback = await db.execute(
                    select(func.count(Prospect.id)).where(
                        and_(
                            Prospect.scrape_status.in_([ScrapeStatus.SCRAPED.value, ScrapeStatus.ENRICHED.value]),
                            Prospect.contact_email.isnot(None),
                            website_filter
                        )
                    )
                )
                email_found_count = email_found_fallback.scalar() or 0
                leads_count = 0  # No leads without stage column
        except Exception as e:
            logger.error(f"❌ Error counting stage-based prospects: {e}", exc_info=True)
            # Fallback to scrape_status + email if stage query fails
            try:
                email_found_fallback = await db.execute(
                    select(func.count(Prospect.id)).where(
                        Prospect.scrape_status.in_([ScrapeStatus.SCRAPED.value, ScrapeStatus.ENRICHED.value]),
                        Prospect.contact_email.isnot(None)
                    )
                )
                email_found_count = email_found_fallback.scalar() or 0
            except Exception as fallback_err:
                logger.error(f"❌ Fallback stage count also failed: {fallback_err}", exc_info=True)
                email_found_count = 0
                leads_count = 0
        
        # Step 3.5: EMAILS FOUND (contact_email IS NOT NULL AND source_type='website')
        # Count all website prospects with emails (regardless of verification status)
        emails_found = await db.execute(
            select(func.count(Prospect.id)).where(
                and_(
                    Prospect.contact_email.isnot(None),
                    website_filter
                )
            )
        )
        emails_found_count = emails_found.scalar() or 0
        
        # Step 4: VERIFIED = Prospects where verification_status == "verified" AND source_type='website'
        # SINGLE SOURCE OF TRUTH: verification_status = "verified" AND source_type='website'
        verified = await db.execute(
            select(func.count(Prospect.id)).where(
                and_(
                    Prospect.verification_status == VerificationStatus.VERIFIED.value,
                    website_filter
                )
            )
        )
        verified_count = verified.scalar() or 0
        
        # Also count verified with email (for backwards compatibility)
        emails_verified = await db.execute(
            select(func.count(Prospect.id)).where(
                and_(
                    Prospect.verification_status == VerificationStatus.VERIFIED.value,
                    Prospect.contact_email.isnot(None),
                    website_filter
                )
            )
        )
        emails_verified_count = emails_verified.scalar() or 0
        
        # Step 5: DRAFT-READY = Prospects where verification_status == "verified" AND email IS NOT NULL AND source_type='website'
        # SINGLE SOURCE OF TRUTH: verification_status = "verified" AND contact_email IS NOT NULL AND source_type='website'
        draft_ready = await db.execute(
            select(func.count(Prospect.id)).where(
                and_(
                    Prospect.verification_status == VerificationStatus.VERIFIED.value,
                    Prospect.contact_email.isnot(None),
                    website_filter
                )
            )
        )
        draft_ready_count = draft_ready.scalar() or 0
        
        # Backwards compatibility alias
        drafting_ready = draft_ready_count
        drafting_ready_count = draft_ready_count
        
        # Step 6: DRAFTED = Prospects where draft_status = "drafted" AND source_type='website'
        # SINGLE SOURCE OF TRUTH: draft_status = "drafted" AND source_type='website'
        drafted_count = 0
        try:
            drafted = await db.execute(
                select(func.count(Prospect.id)).where(
                    and_(
                        Prospect.draft_status == DraftStatus.DRAFTED.value,
                        website_filter
                    )
                )
            )
            drafted_count = drafted.scalar() or 0
        except Exception as e:
            logger.error(f"❌ Error counting drafted prospects: {e}", exc_info=True)
            drafted_count = 0
        
        # Step 7: SENT = Prospects where send_status = "sent" AND source_type='website'
        # SINGLE SOURCE OF TRUTH: send_status = "sent" AND source_type='website'
        sent_count = 0
        try:
            sent = await db.execute(
                select(func.count(Prospect.id)).where(
                    and_(
                        Prospect.send_status == SendStatus.SENT.value,
                        website_filter
                    )
                )
            )
            sent_count = sent.scalar() or 0
        except Exception as e:
            logger.error(f"❌ Error counting sent prospects: {e}", exc_info=True)
            sent_count = 0
        
        # SEND READY = verified + drafted + not sent AND source_type='website'
        # SINGLE SOURCE OF TRUTH: verification_status = "verified" AND draft_status = "drafted" AND send_status != "sent" AND source_type='website'
        send_ready_count = 0
        try:
            send_ready = await db.execute(
                select(func.count(Prospect.id)).where(
                    and_(
                        Prospect.contact_email.isnot(None),
                        Prospect.verification_status == VerificationStatus.VERIFIED.value,
                        Prospect.draft_status == DraftStatus.DRAFTED.value,
                        Prospect.send_status != SendStatus.SENT.value,
                        website_filter
                    )
                )
            )
            send_ready_count = send_ready.scalar() or 0
        except Exception as e:
            logger.error(f"❌ Error counting send-ready prospects: {e}", exc_info=True)
            send_ready_count = 0
        
        # Return pipeline status counts
        # DATA-DRIVEN: All counts derived from Prospect state only, NOT from jobs
        # Unlock logic (DATA-DRIVEN from database state):
        # - Verification card is COMPLETE if verified_count > 0
        # - Drafting card is UNLOCKED if verified_count > 0 (draft_ready_count > 0)
        # - Sending card is UNLOCKED if send_ready_count > 0 (verified + drafted + not sent)
        return {
            "discovered": discovered_count,
            "approved": approved_count,
            "scraped": scraped_count,  # USER RULE: Prospects where email IS NOT NULL
            "discovered_for_scraping": scrape_ready_count,
            "scrape_ready_count": scrape_ready_count,
            "email_found": email_found_count,  # Backwards-compatible (stage-based)
            "emails_found": emails_found_count,  # All prospects with emails (contact_email IS NOT NULL)
            "leads": leads_count,  # Backwards-compatible (stage-based)
            "verified": verified_count,  # USER RULE: Prospects where verification_status == "verified"
            "verified_email_count": emails_verified_count,  # Backwards-compatible: verified AND email IS NOT NULL
            "verified_count": verified_count,  # Primary: verification_status == "verified"
            "emails_verified": emails_verified_count,  # Backwards-compatible: verified AND email IS NOT NULL
            "verified_stage": verified_stage_count,  # Backwards-compatible (stage-based)
            "reviewed": emails_verified_count,  # Backwards-compatible
            "drafting_ready": draft_ready_count,  # USER RULE: verified AND email IS NOT NULL
            "drafting_ready_count": draft_ready_count,  # Primary: draft-ready count
            "drafted": drafted_count,  # USER RULE: Prospects where draft_subject IS NOT NULL
            "drafted_count": drafted_count,  # Primary: drafted count
            "sent": sent_count,  # USER RULE: Prospects where last_sent IS NOT NULL
            "send_ready": send_ready_count,  # verified + drafted + not sent
            "send_ready_count": send_ready_count,  # Primary: send-ready count
        }
    except Exception as e:
        # Rollback transaction on error to prevent "transaction aborted" errors
        try:
            await db.rollback()
        except Exception:
            pass
        logger.error(f"❌ [PIPELINE STATUS] Error computing pipeline status: {e}", exc_info=True)
        # Return safe defaults instead of 500 error
        return {
            "discovered": 0,
            "approved": 0,
            "scraped": 0,
            "discovered_for_scraping": 0,
            "scrape_ready_count": 0,
            "email_found": 0,
            "emails_found": 0,
            "leads": 0,
            "verified": 0,
            "verified_email_count": 0,
            "verified_count": 0,
            "emails_verified": 0,
            "verified_stage": 0,
            "reviewed": 0,
            "drafting_ready": 0,
            "drafting_ready_count": 0,
            "drafted": 0,
            "drafted_count": 0,
            "sent": 0,
            "send_ready": 0,
            "send_ready_count": 0,
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
    Get discovered websites (matches pipeline "Discovered" card count)
    
    SINGLE SOURCE OF TRUTH: Returns prospects where discovery_status = "DISCOVERED"
    This matches the pipeline status "discovered" count exactly.
    """
    try:
        # SINGLE SOURCE OF TRUTH: Match pipeline status query exactly
        # Pipeline counts: discovery_status = "DISCOVERED"
        logger.info(f"🔍 [WEBSITES] Querying prospects with discovery_status = 'DISCOVERED' (skip={skip}, limit={limit})")
        
        # Get total count FIRST (before pagination)
        try:
            total_result = await db.execute(
                select(func.count(Prospect.id)).where(
                    Prospect.discovery_status == DiscoveryStatus.DISCOVERED.value
                )
            )
            total = total_result.scalar() or 0
            logger.info(f"📊 [WEBSITES] RAW COUNT (before pagination): {total} prospects with discovery_status = 'DISCOVERED'")
        except Exception as count_err:
            logger.error(f"❌ [WEBSITES] Failed to get total count: {count_err}", exc_info=True)
            total = 0
        
        # Get paginated results
        # SCHEMA MUST BE CORRECT - migrations run on startup ensure all columns exist
        # If this fails, it indicates a critical schema mismatch that must be fixed
        result = await db.execute(
            select(Prospect).where(
                Prospect.discovery_status == DiscoveryStatus.DISCOVERED.value
            )
            .order_by(Prospect.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        websites = result.scalars().all()
        logger.info(f"📊 [WEBSITES] QUERY RESULT: Found {len(websites)} websites from database query (total available: {total})")
        
        # CRITICAL: Verify data integrity - total must match actual data
        if total > 0 and len(websites) == 0:
            logger.error(f"❌ [WEBSITES] DATA INTEGRITY VIOLATION: total={total} but query returned 0 rows")
            await db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Data integrity violation: COUNT query returned {total} but SELECT query returned 0 rows. This indicates a schema mismatch or query error. Ensure migrations have run successfully."
            )
        
        # Safely build response data with error handling
        data = []
        for p in websites:
            try:
                data.append({
                    "id": str(p.id) if p.id else "",
                    "domain": p.domain or "",
                    "url": p.page_url or (f"https://{p.domain}" if p.domain else ""),
                    "title": p.page_title or p.domain or "",
            "category": p.discovery_category or "Unknown",
            "location": p.discovery_location or "Unknown",
            "discovery_job_id": str(p.discovery_query_id) if p.discovery_query_id else None,
            "discovered_at": p.created_at.isoformat() if p.created_at else None,
            "scrape_status": p.scrape_status or "DISCOVERED",
            "approval_status": p.approval_status or "PENDING",
                })
            except Exception as e:
                logger.error(f"❌ Error processing website {getattr(p, 'id', 'unknown')}: {e}", exc_info=True)
                # Skip this prospect but continue with others
                continue
        
        # CRITICAL: If we have websites but no data after conversion, set total=0
        if len(websites) > 0 and len(data) == 0:
            logger.error(f"❌ [WEBSITES] CRITICAL: Query returned {len(websites)} websites but all conversions failed! This indicates a schema mismatch. Setting total=0 to prevent data integrity violation.")
            total = 0
        
        logger.info(f"✅ [WEBSITES] Returning {len(data)} websites (total: {total})")
        logger.info(f"📊 [WEBSITES] Response structure: data length={len(data)}, total={total}, skip={skip}, limit={limit}")
        
        # Ensure we always return a valid response structure
        response = {
            "data": data,
        "total": total,
        "skip": skip,
        "limit": limit
    }
        
        # CRITICAL: Guard against data integrity violation
        from app.utils.response_guard import validate_list_response
        response = validate_list_response(response, "get_websites")
        
        # Log first few items for debugging
        if len(data) > 0:
            logger.info(f"📊 [WEBSITES] First website sample: {data[0] if data else 'N/A'}")
        
        return response
    except HTTPException:
        # Re-raise HTTP exceptions (already handled)
        raise
    except Exception as e:
        # CRITICAL: Do NOT return empty array - raise error instead
        logger.error(f"❌ [WEBSITES] Unexpected error: {e}", exc_info=True)
        try:
            await db.rollback()  # Rollback on exception to prevent transaction poisoning
        except Exception as rollback_err:
            logger.error(f"❌ Error during rollback: {rollback_err}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}. Check logs for details."
        )


# ============================================
# CATEGORY MANAGEMENT
# ============================================

class UpdateCategoryRequest(BaseModel):
    prospect_ids: List[UUID]
    category: str


class UpdateCategoryResponse(BaseModel):
    success: bool
    updated_count: int
    message: str


@router.post("/update_category", response_model=UpdateCategoryResponse)
async def update_prospect_category(
    request: UpdateCategoryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Update category for existing prospects.
    Useful for categorizing records that were created before categories were properly set.
    """
    if not request.prospect_ids or len(request.prospect_ids) == 0:
        raise HTTPException(status_code=400, detail="At least one prospect ID is required")
    
    if not request.category or not request.category.strip():
        raise HTTPException(status_code=400, detail="Category is required")
    
    logger.info(f"🏷️  [CATEGORY UPDATE] Updating {len(request.prospect_ids)} prospects to category '{request.category}'")
    
    # Get prospects
    result = await db.execute(
        select(Prospect).where(Prospect.id.in_(request.prospect_ids))
    )
    prospects = result.scalars().all()
    
    if len(prospects) != len(request.prospect_ids):
        logger.warning(f"⚠️  [CATEGORY UPDATE] Only found {len(prospects)} of {len(request.prospect_ids)} requested prospects")
    
    # Update category for each prospect
    updated_count = 0
    for prospect in prospects:
        prospect.discovery_category = request.category.strip()
        updated_count += 1
    
    await db.commit()
    
    logger.info(f"✅ [CATEGORY UPDATE] Updated {updated_count} prospects to category '{request.category}'")
    
    return UpdateCategoryResponse(
        success=True,
        updated_count=updated_count,
        message=f"Successfully updated {updated_count} prospect(s) to category '{request.category}'"
    )


class AutoCategorizeResponse(BaseModel):
    success: bool
    categorized_count: int
    message: str


async def auto_categorize_prospect(prospect: Prospect, db: AsyncSession) -> Optional[str]:
    """
    Automatically determine category for a prospect based on:
    1. Existing category (if already set, preserve it)
    2. Same-domain prospects (inherit from other prospects with same domain)
    3. Pattern matching (domain, title, URL analysis)
    
    Returns the category name or None if no match found.
    """
    # Priority 1: If prospect already has a category, preserve it
    if prospect.discovery_category and prospect.discovery_category.strip() and prospect.discovery_category not in ['N/A', 'Unknown', '']:
        logger.debug(f"✅ [AUTO CATEGORIZE] Prospect {prospect.id} already has category: {prospect.discovery_category}")
        return prospect.discovery_category
    
    # Priority 2: Check if other prospects with the same domain have a category
    if prospect.domain:
        try:
            result = await db.execute(
                select(Prospect.discovery_category).where(
                    Prospect.domain == prospect.domain,
                    Prospect.discovery_category.isnot(None),
                    Prospect.discovery_category != '',
                    Prospect.discovery_category != 'N/A',
                    Prospect.discovery_category != 'Unknown',
                    Prospect.id != prospect.id  # Exclude self
                ).limit(1)
            )
            same_domain_category = result.scalar_one_or_none()
            if same_domain_category:
                logger.info(f"✅ [AUTO CATEGORIZE] Inherited category '{same_domain_category}' from same-domain prospect for {prospect.domain}")
                return same_domain_category
        except Exception as e:
            logger.warning(f"⚠️  [AUTO CATEGORIZE] Error checking same-domain prospects: {e}")
    
    # Priority 3: Pattern matching based on domain, title, and URL
    domain_lower = (prospect.domain or '').lower()
    title_lower = (prospect.page_title or '').lower()
    url_lower = (prospect.page_url or '').lower()
    combined_text = f"{domain_lower} {title_lower} {url_lower}"
    
    # Extract domain without TLD for better matching
    domain_parts = domain_lower.replace('www.', '').split('.')
    domain_base = domain_parts[0] if domain_parts else domain_lower
    
    # Comprehensive category detection patterns
    # Order matters - more specific patterns first
    category_patterns = {
        'Museums': [
            # Domain patterns
            'museum', 'museums', 'museo', 'museu', 'muse', 'museet',
            # Title/URL patterns
            'art museum', 'gallery museum', 'contemporary museum', 'modern museum',
            'museum of art', 'art collection', 'permanent collection'
        ],
        'Art Gallery': [
            # Domain patterns
            'gallery', 'galleries', 'galerie', 'galeria', 'galerija',
            # Title/URL patterns
            'art gallery', 'contemporary art', 'fine art gallery', 'art space',
            'exhibition space', 'art showroom', 'gallery space', 'art room',
            'contemporary gallery', 'modern gallery', 'fine art', 'art display'
        ],
        'Art Studio': [
            # Domain patterns
            'studio', 'studios', 'atelier', 'ateliers',
            # Title/URL patterns
            'art studio', 'artist studio', 'creative studio', 'painting studio',
            'sculpture studio', 'artists studio', 'working studio', 'art workshop'
        ],
        'Art School': [
            # Domain patterns
            'school', 'academy', 'academie', 'academia', 'institute', 'institution',
            'college', 'university', 'univ', 'edu',
            # Title/URL patterns
            'art school', 'art academy', 'art institute', 'art education',
            'art college', 'art program', 'art courses', 'art classes',
            'art training', 'art degree', 'fine arts', 'visual arts school'
        ],
        'Art Fair': [
            # Domain patterns
            'fair', 'fairs', 'expo', 'exhibition', 'exhibitions', 'show', 'shows',
            # Title/URL patterns
            'art fair', 'art exhibition', 'art show', 'art expo', 'art market',
            'art event', 'art festival', 'biennale', 'biennial', 'art week'
        ],
        'Art Dealer': [
            # Domain patterns
            'dealer', 'dealers', 'broker', 'brokers', 'trader', 'traders',
            'auction', 'auctions', 'sotheby', 'christie', 'bonham',
            # Title/URL patterns
            'art dealer', 'art broker', 'art trader', 'art sales', 'art buying',
            'art selling', 'art investment', 'art collector', 'art collection'
        ],
        'Art Consultant': [
            # Domain patterns
            'consultant', 'consultants', 'advisor', 'advisors', 'advisory',
            'curator', 'curators', 'curation',
            # Title/URL patterns
            'art consultant', 'art advisor', 'art advisory', 'art curation',
            'art curating', 'art management', 'art services'
        ],
        'Art Publisher': [
            # Domain patterns
            'publisher', 'publishers', 'publishing', 'press', 'books', 'book',
            'edition', 'editions', 'print', 'prints',
            # Title/URL patterns
            'art publisher', 'art publishing', 'art press', 'art book',
            'art books', 'art print', 'art prints', 'art edition'
        ],
        'Art Magazine': [
            # Domain patterns
            'magazine', 'magazines', 'journal', 'journals', 'review', 'reviews',
            'publication', 'publications', 'media', 'news', 'blog',
            # Title/URL patterns
            'art magazine', 'art journal', 'art publication', 'art review',
            'art news', 'art media', 'art blog', 'art writing', 'art critic'
        ]
    }
    
    # Check domain base first (most reliable indicator)
    for category, patterns in category_patterns.items():
        for pattern in patterns:
            # Check domain base (without TLD)
            if pattern in domain_base:
                logger.info(f"✅ [AUTO CATEGORIZE] Detected category '{category}' from domain base '{domain_base}' (pattern: '{pattern}') for {prospect.domain}")
                return category
            # Check full domain
            if pattern in domain_lower:
                logger.info(f"✅ [AUTO CATEGORIZE] Detected category '{category}' from domain '{domain_lower}' (pattern: '{pattern}') for {prospect.domain}")
                return category
    
    # Then check title and URL (less reliable but still useful)
    for category, patterns in category_patterns.items():
        for pattern in patterns:
            if pattern in title_lower or pattern in url_lower:
                logger.info(f"✅ [AUTO CATEGORIZE] Detected category '{category}' from title/URL (pattern: '{pattern}') for {prospect.domain}")
                return category
    
    # Finally check combined text as fallback
    for category, patterns in category_patterns.items():
        for pattern in patterns:
            if pattern in combined_text:
                logger.info(f"✅ [AUTO CATEGORIZE] Detected category '{category}' from combined text (pattern: '{pattern}') for {prospect.domain}")
                return category
    
    logger.debug(f"⚠️  [AUTO CATEGORIZE] Could not determine category for {prospect.domain} (domain: {domain_lower}, title: {title_lower[:50] if title_lower else 'N/A'})")
    return None


@router.post("/auto_categorize", response_model=AutoCategorizeResponse)
async def auto_categorize_all(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Automatically categorize all prospects that don't have a category.
    Uses heuristics based on domain, title, and URL to determine category.
    """
    logger.info("🤖 [AUTO CATEGORIZE] Starting automatic categorization of all uncategorized prospects")
    
    # Get all prospects without categories
    result = await db.execute(
        select(Prospect).where(
            or_(
                Prospect.discovery_category.is_(None),
                Prospect.discovery_category == '',
                Prospect.discovery_category == 'N/A',
                Prospect.discovery_category == 'Unknown'
            )
        )
    )
    prospects = result.scalars().all()
    
    logger.info(f"📊 [AUTO CATEGORIZE] Found {len(prospects)} uncategorized prospects")
    
    categorized_count = 0
    for prospect in prospects:
        category = await auto_categorize_prospect(prospect, db)
        if category:
            prospect.discovery_category = category
            categorized_count += 1
    
    await db.commit()
    
    logger.info(f"✅ [AUTO CATEGORIZE] Automatically categorized {categorized_count} of {len(prospects)} prospects")
    
    return AutoCategorizeResponse(
        success=True,
        categorized_count=categorized_count,
        message=f"Successfully auto-categorized {categorized_count} prospect(s) based on their content"
    )


@router.get("/debug/counts")
async def debug_counts(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Debug endpoint to check raw database counts
    Helps diagnose empty tabs issue
    """
    try:
        from sqlalchemy import text
        
        # Get total prospects count
        total_result = await db.execute(text("SELECT COUNT(*) FROM prospects"))
        total = total_result.scalar() or 0
        
        # Get prospects with domain
        domain_result = await db.execute(
            text("SELECT COUNT(*) FROM prospects WHERE domain IS NOT NULL")
        )
        domain_count = domain_result.scalar() or 0
        
        # Get prospects with email
        email_result = await db.execute(
            text("SELECT COUNT(*) FROM prospects WHERE contact_email IS NOT NULL")
        )
        email_count = email_result.scalar() or 0
        
        # Get prospects with domain AND email
        both_result = await db.execute(
            text("""
                SELECT COUNT(*) FROM prospects 
                WHERE domain IS NOT NULL AND contact_email IS NOT NULL
            """)
        )
        both_count = both_result.scalar() or 0
        
        logger.info(f"🔍 [DEBUG] Total prospects: {total}, with domain: {domain_count}, with email: {email_count}, with both: {both_count}")
        
        return {
            "total_prospects": total,
            "with_domain": domain_count,
            "with_email": email_count,
            "with_both": both_count
        }
    except Exception as e:
        logger.error(f"❌ Error in debug_counts endpoint: {e}", exc_info=True)
        try:
            await db.rollback()
        except Exception:
            pass
        return {
            "error": str(e),
            "total_prospects": 0,
            "with_domain": 0,
            "with_email": 0,
            "with_both": 0
    }

