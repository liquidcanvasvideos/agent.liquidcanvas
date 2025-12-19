"""
STRICT PIPELINE API - Step-by-step lead acquisition with explicit progression
No auto-triggering, each step must be explicitly unlocked
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, text
from typing import List, Optional, Dict
from uuid import UUID
import logging
from pydantic import BaseModel

from app.db.database import get_db
from app.api.auth import get_current_user_optional
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
    # Find all discovered prospects that are not yet approved
    result = await db.execute(
        select(Prospect).where(
            Prospect.discovery_status == DiscoveryStatus.DISCOVERED.value,
            Prospect.approval_status != "approved",
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
    # Get discovered, non-rejected prospects ready for scraping
    # Scrape eligibility:
    # - discovery_status == DISCOVERED
    # - approval_status is NOT "rejected" (NULL or any other value is allowed)
    # - scrape_status == DISCOVERED (avoid re-scraping already processed prospects)
    query = select(Prospect).where(
        Prospect.discovery_status == DiscoveryStatus.DISCOVERED.value,
        or_(
            Prospect.approval_status.is_(None),
            Prospect.approval_status != "rejected",
        ),
        Prospect.scrape_status == ScrapeStatus.DISCOVERED.value,
    )
    
    if request.prospect_ids:
        query = query.where(Prospect.id.in_(request.prospect_ids))
    
    result = await db.execute(query)
    prospects = result.scalars().all()
    
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
    # Get LEAD prospects ready for verification (canonical stage-based query)
    # LEAD stage = scraped prospects with emails, ready to be verified
    # Defensive: Check if stage column exists, fallback to scrape_status + email
    try:
        # Check if stage column exists
        column_check = await db.execute(
            text("""
                SELECT column_name
                FROM information_schema.columns 
                WHERE table_name = 'prospects' 
                AND column_name = 'stage'
            """)
        )
        column_exists = column_check.fetchone() is not None
        if column_exists:
            # Column exists - use raw SQL to build query safely (avoid ORM attribute access)
            # Build WHERE clause conditions
            where_clause = "stage = :stage_value AND verification_status = :verification_status"
            params = {
                "stage_value": ProspectStage.LEAD.value,
                "verification_status": VerificationStatus.PENDING.value
            }
            
            # If prospect_ids specified, add to WHERE clause
            if request.prospect_ids:
                where_clause += " AND id = ANY(:prospect_ids)"
                params["prospect_ids"] = [str(pid) for pid in request.prospect_ids]
            
            # Use raw SQL to fetch prospect IDs, then load as ORM objects
            raw_query = text(f"""
                SELECT id FROM prospects 
                WHERE {where_clause}
            """)
            result = await db.execute(raw_query, params)
            rows = result.fetchall()
            
            # Convert rows to Prospect objects by ID (safe - doesn't use stage attribute)
            prospects = []
            for row in rows:
                # Extract ID from row (SQLAlchemy Row object)
                prospect_id = row.id if hasattr(row, 'id') else row[0]
                prospect = await db.get(Prospect, prospect_id)
                if prospect:
                    prospects.append(prospect)
        else:
            # Column doesn't exist yet - fallback to scrape_status + email
            logger.warning("⚠️  stage column not found, using fallback logic for verification")
            query = select(Prospect).where(
                Prospect.scrape_status.in_([ScrapeStatus.SCRAPED.value, ScrapeStatus.ENRICHED.value]),
                Prospect.contact_email.isnot(None),
                Prospect.verification_status == VerificationStatus.PENDING.value,
            )
            if request.prospect_ids:
                query = query.where(Prospect.id.in_(request.prospect_ids))
            
            result = await db.execute(query)
            prospects = result.scalars().all()
    except Exception as e:
        logger.error(f"❌ Error checking stage column: {e}, using fallback", exc_info=True)
        # Fallback to scrape_status + email if stage check fails
        query = select(Prospect).where(
            Prospect.scrape_status.in_([ScrapeStatus.SCRAPED.value, ScrapeStatus.ENRICHED.value]),
            Prospect.contact_email.isnot(None),
            Prospect.verification_status == VerificationStatus.PENDING.value,
        )
        if request.prospect_ids:
            query = query.where(Prospect.id.in_(request.prospect_ids))
        
        result = await db.execute(query)
        prospects = result.scalars().all()
    
    if len(prospects) == 0:
        raise HTTPException(
            status_code=400,
            detail="No leads found ready for verification. Ensure prospects are scraped and have emails (stage=LEAD) in Step 3."
        )
    
    logger.info(f"✅ [PIPELINE STEP 4] Verifying {len(prospects)} leads (stage=LEAD)")
    
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
    # Get verified LEAD prospects ready for drafting
    # Requirements: stage = LEAD, email IS NOT NULL, verification_status = verified
    # Defensive: Check if stage column exists
    from sqlalchemy import text
    prospects = []
    try:
        column_check = await db.execute(
            text("""
                SELECT column_name
                FROM information_schema.columns 
                WHERE table_name = 'prospects' 
                AND column_name = 'stage'
            """)
        )
        if column_check.fetchone():
            # Column exists - use stage-based query
            # Check for VERIFIED stage (after verification, stage becomes VERIFIED, not LEAD)
            # OR LEAD stage with verified status (in case verification didn't update stage yet)
            result = await db.execute(
                select(Prospect).where(
                    Prospect.id.in_(request.prospect_ids),
                    Prospect.stage.in_([ProspectStage.VERIFIED.value, ProspectStage.LEAD.value]),
                    Prospect.verification_status == VerificationStatus.VERIFIED.value,
                    Prospect.contact_email.isnot(None),
                    Prospect.draft_status == "pending"
                )
            )
            prospects = result.scalars().all()
        else:
            # Column doesn't exist yet - fallback to verification_status + email
            logger.warning("⚠️  stage column not found, using fallback logic for drafting")
            result = await db.execute(
                select(Prospect).where(
                    Prospect.id.in_(request.prospect_ids),
                    Prospect.verification_status == VerificationStatus.VERIFIED.value,
                    Prospect.contact_email.isnot(None),
                    Prospect.draft_status == "pending"
                )
            )
            prospects = result.scalars().all()
    except Exception as e:
        logger.error(f"❌ Error checking stage column or querying prospects for drafting: {e}", exc_info=True)
        # Fallback to verification_status + email if stage check/query fails
        result = await db.execute(
            select(Prospect).where(
                Prospect.id.in_(request.prospect_ids),
                Prospect.verification_status == VerificationStatus.VERIFIED.value,
                Prospect.contact_email.isnot(None),
                Prospect.draft_status == "pending"
            )
        )
        prospects = result.scalars().all()
    
    if len(prospects) != len(request.prospect_ids):
        raise HTTPException(
            status_code=400,
            detail="Some prospects not found or not ready for drafting. Ensure they are LEAD stage, verified, and have emails."
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
    # DATA-DRIVEN: Query send-ready prospects directly from database
    # Redefine send-ready as: verified + drafted + not sent
    if request.prospect_ids is not None and len(request.prospect_ids) > 0:
        # Manual selection: use provided prospect_ids but validate they meet send-ready criteria
        result = await db.execute(
            select(Prospect).where(
                Prospect.id.in_(request.prospect_ids),
                Prospect.contact_email.isnot(None),
                Prospect.verification_status == VerificationStatus.VERIFIED.value,
                Prospect.draft_subject.isnot(None),
                Prospect.draft_body.isnot(None),
                Prospect.send_status != SendStatus.SENT.value
            )
        )
        prospects = result.scalars().all()
        
        if len(prospects) != len(request.prospect_ids):
            raise HTTPException(
                status_code=422,
                detail=f"Some prospects not found or not ready for sending. Found {len(prospects)} ready out of {len(request.prospect_ids)} requested. Ensure they have verified email, draft subject, and draft body."
            )
    else:
        # Automatic: query all send-ready prospects
        result = await db.execute(
            select(Prospect).where(
                Prospect.contact_email.isnot(None),
                Prospect.verification_status == VerificationStatus.VERIFIED.value,
                Prospect.draft_subject.isnot(None),
                Prospect.draft_body.isnot(None),
                Prospect.send_status != SendStatus.SENT.value
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
    """
    logger.info("📊 [PIPELINE STATUS] Computing data-driven counts from Prospect table")
    
    # Wrap entire endpoint in try-catch to handle transaction errors
    try:
        # Step 1: DISCOVERED (canonical status for discovered websites)
        discovered = await db.execute(
        select(func.count(Prospect.id)).where(
            Prospect.discovery_status == DiscoveryStatus.DISCOVERED.value
        )
        )
        discovered_count = discovered.scalar() or 0
        
        # Step 2: APPROVED (approval_status = "approved")
        approved = await db.execute(
            select(func.count(Prospect.id)).where(Prospect.approval_status == "approved")
        )
        approved_count = approved.scalar() or 0
        
        # Step 3: SCRAPED = Prospects where email IS NOT NULL
        # USER RULE: Scraped count = Prospects where email IS NOT NULL
        scraped = await db.execute(
            select(func.count(Prospect.id)).where(
                Prospect.contact_email.isnot(None)
            )
        )
        scraped_count = scraped.scalar() or 0
        
        # Scrape-ready: any DISCOVERED prospect that has NOT been explicitly rejected.
        # This unlocks scraping as soon as at least one website has been discovered,
        # while still allowing optional manual rejection to exclude sites.
        scrape_ready = await db.execute(
            select(func.count(Prospect.id)).where(
                Prospect.discovery_status == DiscoveryStatus.DISCOVERED.value,
                Prospect.approval_status != "rejected",
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
                # EMAIL_FOUND: prospects with emails found but not yet promoted to LEAD
                email_found_result = await db.execute(
                    text("""
                        SELECT COUNT(*) 
                        FROM prospects 
                        WHERE stage = :stage_value
                    """),
                    {"stage_value": ProspectStage.EMAIL_FOUND.value}
                )
                email_found_count = email_found_result.scalar() or 0
                
                # LEAD: explicitly promoted leads (ready for outreach)
                leads_result = await db.execute(
                    text("""
                        SELECT COUNT(*) 
                        FROM prospects 
                        WHERE stage = :stage_value
                    """),
                    {"stage_value": ProspectStage.LEAD.value}
                )
                leads_count = leads_result.scalar() or 0
                
                # VERIFIED: prospects with verified emails
                verified_stage_result = await db.execute(
                    text("""
                        SELECT COUNT(*) 
                        FROM prospects 
                        WHERE stage = :stage_value
                    """),
                    {"stage_value": ProspectStage.VERIFIED.value}
                )
                verified_stage_count = verified_stage_result.scalar() or 0
            else:
                # Column doesn't exist yet - fallback to scrape_status + email
                logger.warning("⚠️  stage column not found, using fallback logic for stage counts")
                # Fallback: count prospects with emails as EMAIL_FOUND
                email_found_fallback = await db.execute(
                    select(func.count(Prospect.id)).where(
                        Prospect.scrape_status.in_([ScrapeStatus.SCRAPED.value, ScrapeStatus.ENRICHED.value]),
                        Prospect.contact_email.isnot(None)
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
        
        # Step 3.5: EMAILS FOUND (contact_email IS NOT NULL)
        # Count all prospects with emails (regardless of verification status)
        emails_found = await db.execute(
            select(func.count(Prospect.id)).where(
                Prospect.contact_email.isnot(None)
            )
        )
        emails_found_count = emails_found.scalar() or 0
        
        # Step 4: VERIFIED = Prospects where verification_status == "verified"
        # USER RULE: Verified count = Prospects where verification_status == "verified"
        verified = await db.execute(
            select(func.count(Prospect.id)).where(
                Prospect.verification_status == VerificationStatus.VERIFIED.value
            )
        )
        verified_count = verified.scalar() or 0
        
        # Also count verified with email (for backwards compatibility)
        emails_verified = await db.execute(
            select(func.count(Prospect.id)).where(
                Prospect.verification_status == VerificationStatus.VERIFIED.value,
                Prospect.contact_email.isnot(None)
            )
        )
        emails_verified_count = emails_verified.scalar() or 0
        
        # Step 5: DRAFT-READY = Prospects where verification_status == "verified" AND email IS NOT NULL
        # USER RULE: Draft-ready count = Prospects where verification_status == "verified" AND email IS NOT NULL
        draft_ready = await db.execute(
            select(func.count(Prospect.id)).where(
                Prospect.verification_status == VerificationStatus.VERIFIED.value,
                Prospect.contact_email.isnot(None)
            )
        )
        draft_ready_count = draft_ready.scalar() or 0
        
        # Backwards compatibility alias
        drafting_ready = draft_ready_count
        drafting_ready_count = draft_ready_count
        
        # Step 6: DRAFTED = Prospects where drafted_at IS NOT NULL
        # USER RULE: Drafted count = Prospects where drafted_at IS NOT NULL
        # This indicates a draft has been created (regardless of draft_subject/draft_body)
        # Defensive: Check if drafted_at column exists before querying
        drafted_count = 0
        try:
            from sqlalchemy import text
            column_check = await db.execute(
                text("""
                    SELECT column_name
                    FROM information_schema.columns 
                    WHERE table_name = 'prospects' 
                    AND column_name = 'drafted_at'
                """)
            )
            if column_check.fetchone():
            # Column exists - use raw SQL to query safely
            drafted_result = await db.execute(
                text("""
                    SELECT COUNT(*) 
                    FROM prospects 
                    WHERE drafted_at IS NOT NULL
                """)
            )
            drafted_count = drafted_result.scalar() or 0
        else:
            # Column doesn't exist - fallback to draft_subject
            logger.warning("⚠️  drafted_at column not found, using draft_subject fallback")
            drafted = await db.execute(
                select(func.count(Prospect.id)).where(
                    Prospect.draft_subject.isnot(None)
                )
            )
            drafted_count = drafted.scalar() or 0
    except Exception as e:
        # If anything fails, try draft_subject as fallback
        logger.warning(f"⚠️  Error checking drafted_at, using draft_subject fallback: {e}")
        try:
            drafted = await db.execute(
                select(func.count(Prospect.id)).where(
                    Prospect.draft_subject.isnot(None)
                )
            )
            drafted_count = drafted.scalar() or 0
        except Exception as fallback_err:
            logger.error(f"❌ Both drafted_at and draft_subject queries failed: {fallback_err}", exc_info=True)
            drafted_count = 0
        
        # Step 7: SENT = Prospects where last_sent IS NOT NULL
        # USER RULE: Sent count = Prospects where last_sent IS NOT NULL
        # Defensive: Use raw SQL to avoid transaction errors
        sent_count = 0
        try:
            sent_result = await db.execute(
                text("""
                    SELECT COUNT(*) 
                    FROM prospects 
                    WHERE last_sent IS NOT NULL
                """)
            )
            sent_count = sent_result.scalar() or 0
        except Exception as e:
            logger.error(f"❌ Error counting sent prospects: {e}", exc_info=True)
            sent_count = 0
        
        # SEND READY = verified + drafted + not sent
        # Defensive: Use raw SQL to avoid transaction errors
        send_ready_count = 0
        try:
            # Check if drafted_at column exists
            column_check = await db.execute(
                text("""
                    SELECT column_name
                    FROM information_schema.columns 
                    WHERE table_name = 'prospects' 
                    AND column_name = 'drafted_at'
                """)
            )
            has_drafted_at = column_check.fetchone() is not None
            
            if has_drafted_at:
                # Use drafted_at if available
                send_ready_result = await db.execute(
                    text("""
                        SELECT COUNT(*) 
                        FROM prospects 
                        WHERE contact_email IS NOT NULL
                        AND verification_status = :verified_status
                        AND drafted_at IS NOT NULL
                        AND last_sent IS NULL
                    """),
                    {"verified_status": VerificationStatus.VERIFIED.value}
                )
            else:
                # Fallback to draft_subject
                send_ready_result = await db.execute(
                    text("""
                        SELECT COUNT(*) 
                        FROM prospects 
                        WHERE contact_email IS NOT NULL
                        AND verification_status = :verified_status
                        AND draft_subject IS NOT NULL
                        AND last_sent IS NULL
                    """),
                    {"verified_status": VerificationStatus.VERIFIED.value}
                )
            send_ready_count = send_ready_result.scalar() or 0
        except Exception as e:
            logger.error(f"❌ Error counting send-ready prospects: {e}", exc_info=True)
            send_ready_count = 0
        
        # Defensive logging: Log all counts for debugging
        logger.info(f"📊 [PIPELINE STATUS] Counts computed: discovered={discovered_count}, approved={approved_count}, "
                    f"scraped={scraped_count}, verified={verified_count}, draft_ready={draft_ready_count}, "
                    f"drafted={drafted_count}, sent={sent_count}, send_ready={send_ready_count}")
        
        # Return pipeline status counts
        # DATA-DRIVEN: All counts derived from Prospect state only, NOT from jobs
        # Unlock logic:
        # - Verification card is COMPLETE if verified_count > 0
        # - Drafting card is UNLOCKED if verified_count > 0 (draft_ready_count > 0)
        # - Sending card is UNLOCKED if drafted_count > 0
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
        await db.rollback()
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
    Get discovered websites (discovery results)
    
    Returns prospects with discovery_status = "DISCOVERED"
    These are websites found during discovery, not yet scraped
    """
    try:
        result = await db.execute(
            select(Prospect).where(
                Prospect.discovery_status == DiscoveryStatus.DISCOVERED.value
            )
            .order_by(Prospect.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        websites = result.scalars().all()
        
        total_result = await db.execute(
            select(func.count(Prospect.id)).where(
                Prospect.discovery_status == DiscoveryStatus.DISCOVERED.value
            )
        )
        total = total_result.scalar() or 0
        
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
        
        return {
            "data": data,
            "total": total,
            "skip": skip,
            "limit": limit
        }
    except Exception as e:
        logger.error(f"❌ Error in get_websites endpoint: {e}", exc_info=True)
        # Return empty result instead of 500 error
        return {
            "data": [],
            "total": 0,
            "skip": skip,
            "limit": limit
        }

