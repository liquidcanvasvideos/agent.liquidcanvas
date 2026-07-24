"""
STRICT PIPELINE API - Step-by-step lead acquisition with explicit progression
No auto-triggering, each step must be explicitly unlocked
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_, func, text, true
from typing import List, Optional, Dict
from uuid import UUID
import logging
import json
from datetime import datetime, timezone
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
from app.models.email_log import EmailLog
from app.models.discovery_query import DiscoveryQuery

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
    # Some deployments may not have source_type column yet; fall back safely.
    column_check = await db.execute(
        text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'prospects'
            AND column_name = 'source_type'
            """
        )
    )
    has_source_type = column_check.fetchone() is not None
    if has_source_type:
        website_filter = or_(
            Prospect.source_type == 'website',
            Prospect.source_type.is_(None)  # Legacy prospects (default to website)
        )
    else:
        website_filter = true()
    
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


class ScrapeFilters(BaseModel):
    category: Optional[str] = None


# ============================================
# STEP 3: SCRAPING
# ============================================

class ScrapeRequest(BaseModel):
    prospect_ids: Optional[List[UUID]] = None  # If None, scrape all approved
    filters: Optional[ScrapeFilters] = None



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
    # Some deployments may not have source_type column yet; fall back safely.
    column_check = await db.execute(
        text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'prospects'
            AND column_name = 'source_type'
            """
        )
    )
    has_source_type = column_check.fetchone() is not None
    if has_source_type:
        website_filter = or_(
            Prospect.source_type == 'website',
            Prospect.source_type.is_(None)  # Legacy prospects (default to website)
        )
    else:
        website_filter = true()
    
    normalized_category: Optional[str] = None
    if getattr(request, "filters", None) and request.filters and request.filters.category:
        if request.filters.category.strip() and request.filters.category.strip().lower() != 'all':
            normalized_category = request.filters.category.strip()
            logger.info(
                f"🔍 [PIPELINE STEP 3] Category filter applied: '{normalized_category}' (exact match, case-insensitive)"
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

    if normalized_category:
        query = query.where(
            and_(
                Prospect.discovery_category.isnot(None),
                Prospect.discovery_category.ilike(normalized_category),
            )
        )
    
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
    # WORKAROUND: Check if progress columns exist before creating job
    # If columns don't exist, use raw SQL to insert without them
    from sqlalchemy import text
    
    # Check if drafts_created column exists
    column_check = await db.execute(
        text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'jobs' 
            AND column_name IN ('drafts_created', 'total_targets')
        """)
    )
    existing_columns = {row[0] for row in column_check.fetchall()}
    has_progress_columns = 'drafts_created' in existing_columns and 'total_targets' in existing_columns
    
    if has_progress_columns:
        # Normal path: create job with progress columns
        job = Job(
            job_type="verify",
            params={
                "prospect_ids": [str(p.id) for p in prospects],
                "pipeline_mode": True,
            },
            status="pending",
            drafts_created=0,  # Will be updated by verification task
            total_targets=len(prospects)
        )
        
        try:
            db.add(job)
            await db.commit()
            await db.refresh(job)
        except Exception as commit_err:
            logger.error(f"❌ [PIPELINE STEP 4] Commit error: {commit_err}", exc_info=True)
            await db.rollback()  # Rollback on commit failure
            raise HTTPException(status_code=500, detail=f"Failed to create verification job: {str(commit_err)}")
    else:
        # Fallback: use raw SQL to insert job without progress columns
        import uuid
        job_id = str(uuid.uuid4())
        
        try:
            await db.execute(
                text("""
                    INSERT INTO jobs (id, user_id, job_type, params, status, error_message, created_at, updated_at)
                    VALUES (:id, :user_id, :job_type, :params, :status, :error_message, NOW(), NOW())
                """),
                {
                    "id": job_id,
                    "user_id": None,
                    "job_type": "verify",
                    "params": {
                        "prospect_ids": [str(p.id) for p in prospects],
                        "pipeline_mode": True,
                    },
                    "status": "pending",
                    "error_message": None
                }
            )
            await db.commit()
            
            # Create a minimal job object for response
            job = type('Job', (), {
                'id': job_id,
                'job_type': 'verify',
                'status': 'pending'
            })()
            
        except Exception as commit_err:
            logger.error(f"❌ [PIPELINE STEP 4] Raw SQL commit error: {commit_err}", exc_info=True)
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to create verification job: {str(commit_err)}")
    
    # Start verification task in background
    try:
        from app.tasks.verification import verify_prospects_async
        import asyncio
        from app.task_manager import register_task
        
        task = asyncio.create_task(verify_prospects_async(str(job.id)))
        register_task(str(job.id), task)
        logger.info(f"✅ [PIPELINE STEP 4] Verification job {job.id} started - DEPLOYMENT FIX v2")
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


class DraftCategoryFilters(BaseModel):
    category: Optional[str] = None


class DraftCategoryTemplateRequest(BaseModel):
    category: str
    notes: Optional[str] = None


class DraftCategoryTemplateResponse(BaseModel):
    success: bool
    category: str
    concept: str
    subject_template: str
    body_template: str


class DraftCategoryRequest(BaseModel):
    prospect_ids: Optional[List[UUID]] = None
    filters: Optional[DraftCategoryFilters] = None
    category: str
    concept: str
    subject_template: str
    body_template: str


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
    
    BACKGROUND JOB MODE:
    - Creates job immediately and returns
    - Eligibility check happens in background task
    - Progress tracked via job.drafts_created and job.total_targets
    - Status available via GET /api/pipeline/draft/jobs/{job_id}
    
    If prospect_ids provided, use those (manual selection).
    If prospect_ids empty or not provided, background task will query all draft-ready prospects.
    """
    job_id: Optional[UUID] = None
    
    try:
        # Check master switch
        try:
            master_enabled = await check_master_switch(db)
        except Exception as e:
            logger.error(f"❌ [DRAFT] Failed to check master switch: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="Failed to check automation settings. Please try again."
            )
        
        if not master_enabled:
            logger.warning("⚠️  [DRAFT] Master switch disabled")
            raise HTTPException(
                status_code=403,
                detail="Master switch is disabled. Please enable it in Automation Control to run pipeline activities."
            )
        
        # Create drafting job IMMEDIATELY - do NOT query prospects here
        # Eligibility check and prospect querying happens in background task
        try:
            # WORKAROUND: Check if progress columns exist before creating job
            # If columns don't exist, use raw SQL to insert without them
            from sqlalchemy import text
            
            # Check if drafts_created column exists
            column_check = await db.execute(
                text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'jobs' 
                    AND column_name IN ('drafts_created', 'total_targets')
                """)
            )
            existing_columns = {row[0] for row in column_check.fetchall()}
            has_progress_columns = 'drafts_created' in existing_columns and 'total_targets' in existing_columns
            
            if has_progress_columns:
                # Columns exist - use normal ORM
                job = Job(
                    job_type="draft",
                    params={
                        "prospect_ids": [str(pid) for pid in request.prospect_ids] if request.prospect_ids else None,
                        "pipeline_mode": True,
                        "auto_mode": request.prospect_ids is None or len(request.prospect_ids) == 0,
                    },
                    status="pending",
                )
                db.add(job)
                await db.commit()
                await db.refresh(job)
                job_id = job.id
            else:
                # Columns don't exist - use raw SQL
                import uuid
                import json
                job_id = uuid.uuid4()
                params_dict = {
                    "prospect_ids": [str(pid) for pid in request.prospect_ids] if request.prospect_ids else None,
                    "pipeline_mode": True,
                    "auto_mode": request.prospect_ids is None or len(request.prospect_ids) == 0,
                }
                
                await db.execute(
                    text("""
                        INSERT INTO jobs (id, job_type, params, status, created_at, updated_at)
                        VALUES (:id, :job_type, :params, :status, NOW(), NOW())
                    """),
                    {
                        "id": str(job_id),
                        "job_type": "draft",
                        "params": json.dumps(params_dict),
                        "status": "pending"
                    }
                )
                await db.commit()
                logger.warning("⚠️  [DRAFT] Created job without progress columns (columns missing)")
            
            logger.info(f"✅ [DRAFT] Created job {job_id} - status: pending (background task will start)")
        except Exception as e:
            logger.error(f"❌ [DRAFT] Failed to create job: {e}", exc_info=True)
            try:
                await db.rollback()
            except Exception as rollback_err:
                logger.error(f"❌ [DRAFT] Rollback failed: {rollback_err}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create drafting job: {str(e)}"
            )
        
        # Start drafting task in background (non-blocking)
        try:
            from app.tasks.drafting import draft_prospects_async
            import asyncio
            from app.task_manager import register_task
            
            task = asyncio.create_task(draft_prospects_async(str(job_id)))
            register_task(str(job_id), task)
            logger.info(f"✅ [DRAFT] Drafting job {job_id} started in background")
        except ImportError as import_err:
            logger.error(f"❌ [DRAFT] Failed to import drafting module: {import_err}", exc_info=True)
            try:
                job.status = "failed"
                job.error_message = f"Unable to import drafting task module: {import_err}"
                await db.commit()
            except Exception as commit_err:
                logger.error(f"❌ [DRAFT] Failed to update job status: {commit_err}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="Unable to import drafting task module. Please contact support."
            )
        except Exception as e:
            logger.error(f"❌ [DRAFT] Failed to start drafting job {job_id}: {e}", exc_info=True)
            try:
                job.status = "failed"
                job.error_message = str(e)
                await db.commit()
            except Exception as commit_err:
                logger.error(f"❌ [DRAFT] Failed to update job status: {commit_err}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to start drafting job: {str(e)}"
            )
    
        # Return immediately - do NOT wait for drafting to complete
        return DraftResponse(
            success=True,
            job_id=job_id,
            message="Drafting job queued. Check status endpoint for progress.",
            prospects_count=0  # Unknown until background task queries prospects
        )
    
    except HTTPException:
        # Re-raise HTTPExceptions as-is (they're already properly formatted)
        raise
    except Exception as e:
        # Catch-all for unexpected errors
        logger.error(
            f"❌ [DRAFT] Unexpected error - job_id={job_id}: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )


@router.post("/draft/category/template", response_model=DraftCategoryTemplateResponse)
async def generate_draft_category_template(
    request: DraftCategoryTemplateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional),
):
    master_enabled = await check_master_switch(db)
    if not master_enabled:
        raise HTTPException(
            status_code=403,
            detail=(
                "Master switch is disabled. Please enable it in Automation Control to run pipeline activities."
            ),
        )

    try:
        from app.clients.gemini import GeminiClient

        client = GeminiClient()
        result = await client.generate_category_template(
            category=request.category,
            notes=request.notes,
        )
        if not result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=result.get("error") or "Failed to generate template",
            )

        return DraftCategoryTemplateResponse(
            success=True,
            category=request.category,
            concept=(result.get("concept") or "").strip(),
            subject_template=(result.get("subject_template") or "").strip(),
            body_template=(result.get("body_template") or "").strip(),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [DRAFT TEMPLATE] Failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate template: {str(e)}")


@router.post("/draft/category", response_model=DraftResponse)
async def draft_emails_for_category(
    request: DraftCategoryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional),
):
    job_id: Optional[UUID] = None

    master_enabled = await check_master_switch(db)
    if not master_enabled:
        raise HTTPException(
            status_code=403,
            detail=(
                "Master switch is disabled. Please enable it in Automation Control to run pipeline activities."
            ),
        )

    if not (request.prospect_ids and len(request.prospect_ids) > 0) and not (
        request.filters and (request.filters.category is not None)
    ):
        raise HTTPException(
            status_code=400,
            detail="Provide either prospect_ids (manual selection) or filters (select all filtered).",
        )

    try:
        from sqlalchemy import text

        column_check = await db.execute(
            text(
                """
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'jobs' 
                AND column_name IN ('drafts_created', 'total_targets')
                """
            )
        )
        existing_columns = {row[0] for row in column_check.fetchall()}
        has_progress_columns = "drafts_created" in existing_columns and "total_targets" in existing_columns

        params_dict = {
            "mode": "category",
            "pipeline_mode": True,
            "auto_mode": False,
            "prospect_ids": [str(pid) for pid in request.prospect_ids] if request.prospect_ids else None,
            "filters": request.filters.dict() if request.filters else None,
            "category": request.category,
            "concept": request.concept,
            "subject_template": request.subject_template,
            "body_template": request.body_template,
        }

        if has_progress_columns:
            job = Job(
                job_type="draft",
                params=params_dict,
                status="pending",
            )
            db.add(job)
            await db.commit()
            await db.refresh(job)
            job_id = job.id
        else:
            import uuid
            import json

            job_id = uuid.uuid4()
            await db.execute(
                text(
                    """
                    INSERT INTO jobs (id, job_type, params, status, created_at, updated_at)
                    VALUES (:id, :job_type, :params, :status, NOW(), NOW())
                    """
                ),
                {
                    "id": str(job_id),
                    "job_type": "draft",
                    "params": json.dumps(params_dict),
                    "status": "pending",
                },
            )
            await db.commit()

        try:
            from app.tasks.drafting import draft_prospects_async
            import asyncio
            from app.task_manager import register_task

            task = asyncio.create_task(draft_prospects_async(str(job_id)))
            register_task(str(job_id), task)
        except Exception as e:
            logger.error(f"❌ [DRAFT CATEGORY] Failed to start drafting job {job_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to start drafting job: {str(e)}")

        return DraftResponse(
            success=True,
            job_id=job_id,
            message="Category drafting job queued. Check status endpoint for progress.",
            prospects_count=0,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [DRAFT CATEGORY] Failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to start category drafting: {str(e)}")


# ============================================
# DRAFT JOB STATUS ENDPOINT
# ============================================

class DraftJobStatusResponse(BaseModel):
    job_id: UUID
    status: str  # pending/running/completed/failed
    total_targets: Optional[int] = None
    drafts_created: int
    started_at: Optional[str] = None
    updated_at: Optional[str] = None
    error_message: Optional[str] = None


@router.get("/draft/jobs/{job_id}", response_model=DraftJobStatusResponse)
async def get_draft_job_status(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Get status of a drafting job with progress tracking.
    
    Returns:
    - job_id: The job identifier
    - status: pending/running/completed/failed
    - total_targets: Total number of prospects to draft (set when job starts running)
    - drafts_created: Number of drafts created so far (incremented during execution)
    - started_at: When job transitioned to running
    - updated_at: Last update time
    - error_message: Error details if status is failed
    """
    try:
        # WORKAROUND: Use raw SQL to query only columns that exist
        # This prevents UndefinedColumnError if drafts_created/total_targets don't exist yet
        from sqlalchemy import text
        
        # Check if progress columns exist
        column_check = await db.execute(
            text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'jobs' 
                AND column_name IN ('drafts_created', 'total_targets')
            """)
        )
        existing_columns = {row[0] for row in column_check.fetchall()}
        has_progress_columns = 'drafts_created' in existing_columns and 'total_targets' in existing_columns
        
        if has_progress_columns:
            # Columns exist - use ORM query
            result = await db.execute(select(Job).where(Job.id == job_id, Job.job_type == "draft"))
            job = result.scalar_one_or_none()
            
            if not job:
                raise HTTPException(status_code=404, detail=f"Draft job {job_id} not found")
            
            total_targets = getattr(job, 'total_targets', None)
            drafts_created = getattr(job, 'drafts_created', 0) or 0
        else:
            # Columns don't exist - use raw SQL to query without them
            logger.warning("⚠️  [DRAFT STATUS] Progress columns missing, using raw SQL query")
            result = await db.execute(
                text("""
                    SELECT id, job_type, params, status, result, error_message, created_at, updated_at
                    FROM jobs
                    WHERE id = :job_id AND job_type = 'draft'
                """),
                {"job_id": str(job_id)}
            )
            row = result.fetchone()
            
            if not row:
                raise HTTPException(status_code=404, detail=f"Draft job {job_id} not found")
            
            # Parse row manually
            total_targets = None
            drafts_created = 0

            result_payload = row[4] if len(row) > 4 else None
            result_data = {}
            if isinstance(result_payload, dict):
                result_data = result_payload
            elif isinstance(result_payload, str):
                try:
                    result_data = json.loads(result_payload)
                except Exception:
                    result_data = {}

            if result_data:
                drafts_created = (
                    result_data.get("drafts_created")
                    or result_data.get("drafted")
                    or 0
                )
                total_targets = result_data.get("total_targets")
                if total_targets is None:
                    total_targets = result_data.get("total")
            
            # Try to get status from row
            job_status = row[3]  # status column
            error_message = row[5] if len(row) > 5 else None
            updated_at = row[7] if len(row) > 7 else None
            
            # Create a minimal job-like object for compatibility
            class MinimalJob:
                def __init__(self, id, status, error_message, updated_at):
                    self.id = id
                    self.status = status
                    self.error_message = error_message
                    self.updated_at = updated_at
            
            job = MinimalJob(
                id=row[0],
                status=job_status,
                error_message=error_message,
                updated_at=updated_at
            )
        
        return DraftJobStatusResponse(
            job_id=job.id,
            status=job.status,
            total_targets=total_targets,
            drafts_created=drafts_created,
            started_at=job.updated_at.isoformat() if job.status != "pending" and job.updated_at else None,
            updated_at=job.updated_at.isoformat() if job.updated_at else None,
            error_message=job.error_message
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [DRAFT STATUS] Failed to get job status {job_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get job status: {str(e)}"
        )


# ============================================
# STEP 7: SENDING
# ============================================

class SendRequest(BaseModel):
    prospect_ids: Optional[List[UUID]] = None  # If None or empty, query all send-ready prospects automatically
    cc_map: Optional[Dict[UUID, str]] = None


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

    # Exclude social outreach prospects; Drafts UI includes drafts from multiple non-social sources.
    # Some deployments may not have source_type column yet; fall back safely.
    column_check = await db.execute(
        text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'prospects'
            AND column_name = 'source_type'
            """
        )
    )
    has_source_type = column_check.fetchone() is not None
    if has_source_type:
        non_social_filter = or_(
            Prospect.source_type != 'social',
            Prospect.source_type.is_(None),
        )
    else:
        non_social_filter = true()
    
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
                    non_social_filter,
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
        # Automatic: query all send-ready NON-SOCIAL prospects
        result = await db.execute(
            select(Prospect).where(
                and_(
                    Prospect.contact_email.isnot(None),
                    Prospect.verification_status == VerificationStatus.VERIFIED.value,
                    Prospect.draft_subject.isnot(None),
                    Prospect.draft_body.isnot(None),
                    Prospect.send_status != SendStatus.SENT.value,
                    non_social_filter,
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
    
    # Check if 'drafts_created' and 'total_targets' columns exist in the 'jobs' table
    # This is a workaround for schema drift between local dev and deployed environments
    column_check = await db.execute(
        text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'jobs'
            AND column_name IN ('drafts_created', 'total_targets')
        """)
    )
    existing_columns = {row[0] for row in column_check.fetchall()}
    has_progress_columns = 'drafts_created' in existing_columns and 'total_targets' in existing_columns

    # Create sending job
    if has_progress_columns:
        job = Job(
            job_type="send",
            params={
                "prospect_ids": [str(p.id) for p in prospects],
                "cc_map": {str(k): v for k, v in (request.cc_map or {}).items()},
                "pipeline_mode": True,
            },
            status="pending"
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
    else:
        # Fallback for older schema without progress columns
        # Use raw SQL to insert to avoid SQLAlchemy trying to insert non-existent columns
        import uuid
        job_id = uuid.uuid4()
        params_dict = {
            "prospect_ids": [str(p.id) for p in prospects],
            "cc_map": {str(k): v for k, v in (request.cc_map or {}).items()},
            "pipeline_mode": True,
        }
        
        await db.execute(
            text("""
                INSERT INTO jobs (id, user_id, job_type, params, status, created_at, updated_at)
                VALUES (:id, :user_id, :job_type, :params, :status, NOW(), NOW())
            """),
            {
                "id": str(job_id),
                "user_id": current_user if current_user else None,
                "job_type": "send",
                "params": json.dumps(params_dict),
                "status": "pending",
            }
        )
        await db.commit()
        logger.warning("⚠️  [SEND] Created job without progress columns (columns missing)")
        
        # Create a minimal Job object for response as it's not loaded via ORM
        job = Job(
            id=job_id,
            user_id=current_user if current_user else None,
            job_type="send",
            params=params_dict,
            status="pending",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
    
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
# SCHEMA FIX
# ============================================

@router.post("/cancel-job/{job_id}")
async def cancel_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Cancel a stuck job by marking it as failed
    """
    try:
        from sqlalchemy import select, update
        from app.models.job import Job
        import uuid

        # Validate UUID
        try:
            uuid.UUID(job_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid job ID format")

        # Get job
        result = await db.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()

        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        # Only allow canceling running jobs
        if job.status != "running":
            raise HTTPException(status_code=400, detail=f"Job is not running (status: {job.status})")

        # Mark as failed
        await db.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(
                status="failed",
                error_message="Job cancelled by user",
                updated_at=datetime.now(timezone.utc)
            )
        )
        await db.commit()

        return {"success": True, "message": f"Job {job_id} marked as failed"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel job: {str(e)}")


@router.post("/fix-jobs-schema")
async def fix_jobs_schema(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Fix jobs table schema - add missing columns for drafting
    This endpoint adds drafts_created and total_targets columns if they don't exist
    """
    try:
        # Check current columns
        result = await db.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'jobs' 
            ORDER BY ordinal_position
        """))
        existing_columns = [row[0] for row in result.fetchall()]
        logger.info(f"Current jobs table columns: {existing_columns}")
        
        changes_made = []
        
        # Add drafts_created column if missing
        if 'drafts_created' not in existing_columns:
            await db.execute(text("""
                ALTER TABLE jobs ADD COLUMN drafts_created INTEGER DEFAULT 0 NOT NULL
            """))
            changes_made.append("Added drafts_created column")
            logger.info("✅ Added drafts_created column")
        else:
            logger.info("ℹ️  drafts_created column already exists")
        
        # Add total_targets column if missing
        if 'total_targets' not in existing_columns:
            await db.execute(text("""
                ALTER TABLE jobs ADD COLUMN total_targets INTEGER NULL
            """))
            changes_made.append("Added total_targets column")
            logger.info("✅ Added total_targets column")
        else:
            logger.info("ℹ️  total_targets column already exists")
        
        # Update existing jobs to have default value
        await db.execute(text("""
            UPDATE jobs SET drafts_created = 0 WHERE drafts_created IS NULL
        """))
        
        # Create index for better performance
        await db.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_jobs_drafts_created ON jobs(drafts_created)
        """))
        
        await db.commit()
        
        # Verify the fix
        result = await db.execute(text("""
            SELECT column_name, data_type, is_nullable, column_default 
            FROM information_schema.columns 
            WHERE table_name = 'jobs' 
            ORDER BY ordinal_position
        """))
        columns = result.fetchall()
        
        return {
            "success": True,
            "message": "Jobs schema fix completed successfully",
            "changes_made": changes_made,
            "current_columns": [
                {
                    "name": col[0],
                    "type": col[1], 
                    "nullable": col[2],
                    "default": col[3]
                }
                for col in columns
            ]
        }
        
    except Exception as e:
        logger.error(f"❌ Error fixing jobs schema: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fix jobs schema: {str(e)}"
        )


@router.post("/configure-gmail")
async def configure_gmail(
    request: dict,
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Configure Gmail API credentials
    This endpoint sets the Gmail OAuth credentials for sending emails
    """
    try:
        import os
        from dotenv import load_dotenv
        
        # Get credentials from request
        client_id = request.get('client_id')
        client_secret = request.get('client_secret')
        access_token = request.get('access_token')
        refresh_token = request.get('refresh_token')
        
        if not client_id or not client_secret:
            raise HTTPException(
                status_code=400,
                detail="client_id and client_secret are required"
            )
        
        if not access_token and not refresh_token:
            raise HTTPException(
                status_code=400,
                detail="Either access_token or refresh_token is required"
            )
        
        # Set environment variables (in production, these should be set via Render dashboard)
        os.environ["GMAIL_CLIENT_ID"] = client_id
        os.environ["GMAIL_CLIENT_SECRET"] = client_secret
        if access_token:
            os.environ["GMAIL_ACCESS_TOKEN"] = access_token
        if refresh_token:
            os.environ["GMAIL_REFRESH_TOKEN"] = refresh_token
        
        return {
            "success": True,
            "message": "Gmail credentials configured successfully",
            "configured": {
                "client_id": bool(client_id),
                "client_secret": bool(client_secret),
                "access_token": bool(access_token),
                "refresh_token": bool(refresh_token)
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to configure Gmail: {str(e)}"
        )


@router.get("/test-gmail-debug")
async def test_gmail_debug():
    """
    Detailed Gmail debug - shows exact OAuth error without exposing secrets
    """
    try:
        from app.clients.gmail import GmailClient
        import httpx
        
        gmail_client = GmailClient()
        
        if not gmail_client.is_configured():
            return {
                "success": False,
                "error": "Gmail client not configured",
                "details": "Missing refresh_token, client_id, or client_secret"
            }
        
        # Test refresh token directly against Google OAuth
        url = "https://oauth2.googleapis.com/token"
        payload = {
            "client_id": gmail_client.client_id,
            "client_secret": gmail_client.client_secret,
            "refresh_token": gmail_client.refresh_token,
            "grant_type": "refresh_token"
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, data=payload)
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "message": "Refresh token is valid",
                    "access_token_received": bool(result.get("access_token")),
                    "expires_in": result.get("expires_in"),
                    "token_type": result.get("token_type")
                }
            else:
                error_text = response.text
                try:
                    error_json = response.json()
                    error_code = error_json.get("error", "unknown")
                    error_desc = error_json.get("error_description", error_text)
                except:
                    error_code = "parse_error"
                    error_desc = error_text
                
                return {
                    "success": False,
                    "error": "Refresh token failed",
                    "status_code": response.status_code,
                    "error_code": error_code,
                    "error_description": error_desc,
                    "fix_suggestions": {
                        "invalid_grant": "Generate new refresh token with access_type=offline and prompt=consent",
                        "invalid_client": "Check GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET",
                        "redirect_uri_mismatch": "Ensure OAuth Playground redirect URI matches your client config"
                    }
                }
        
    except Exception as e:
        return {
            "success": False,
            "error": "Debug failed",
            "details": str(e)
        }


@router.get("/gmail-debug-info")
async def gmail_debug_info():
    """
    Safe Gmail debug info: shows presence and fingerprints only (no secrets).
    """
    import os
    import hashlib

    def fingerprint(value: str) -> str:
        if not value:
            return "missing"
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
        return f"len:{len(value)} sha256:{digest[:10]}"

    refresh_token = os.getenv("GMAIL_REFRESH_TOKEN", "")
    client_id = os.getenv("GMAIL_CLIENT_ID", "")
    client_secret = os.getenv("GMAIL_CLIENT_SECRET", "")
    access_token = os.getenv("GMAIL_ACCESS_TOKEN", "")

    return {
        "configured": all([refresh_token, client_id, client_secret]) or bool(access_token),
        "refresh_token": fingerprint(refresh_token),
        "client_id": fingerprint(client_id),
        "client_secret": fingerprint(client_secret),
        "access_token": fingerprint(access_token),
    }


@router.get("/test-smtp")
async def test_smtp():
    """
    Test SMTP configuration (connect + auth) without sending an email.
    """
    import os
    import smtplib

    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() != "false"

    if not all([host, username, password]):
        return {
            "success": False,
            "error": "SMTP not configured",
            "details": "Set SMTP_HOST, SMTP_USER, SMTP_PASSWORD (and optionally SMTP_PORT, SMTP_USE_TLS)."
        }

    try:
        with smtplib.SMTP(host, port, timeout=20) as server:
            if use_tls:
                server.starttls()
            server.login(username, password)
        return {"success": True, "message": "SMTP auth successful"}
    except Exception as e:
        return {"success": False, "error": "SMTP auth failed", "details": str(e)}


@router.get("/smtp-debug-info")
async def smtp_debug_info():
    """
    Safe SMTP debug info: shows presence and fingerprints only (no secrets).
    """
    import os
    import hashlib

    def fingerprint(value: str) -> str:
        if not value:
            return "missing"
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
        return f"len:{len(value)} sha256:{digest[:10]}"

    host = os.getenv("SMTP_HOST", "")
    port = os.getenv("SMTP_PORT", "")
    user = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASSWORD", "")
    from_email = os.getenv("SMTP_FROM", "")
    use_tls = os.getenv("SMTP_USE_TLS", "")

    return {
        "smtp_host": fingerprint(host),
        "smtp_port": fingerprint(port),
        "smtp_user": fingerprint(user),
        "smtp_password": fingerprint(password),
        "smtp_from": fingerprint(from_email),
        "smtp_use_tls": fingerprint(use_tls),
    }


@router.get("/test-gmail")
async def test_gmail():
    """
    Test Gmail API configuration and return success/failure with error details
    No secrets are exposed in the response
    """
    try:
        from app.clients.gmail import GmailClient
        
        # Initialize Gmail client
        gmail_client = GmailClient()
        
        # Check if configured
        if not gmail_client.is_configured():
            return {
                "success": False,
                "error": "Gmail client is not configured",
                "details": "Set GMAIL_ACCESS_TOKEN or (GMAIL_REFRESH_TOKEN + GMAIL_CLIENT_ID + GMAIL_CLIENT_SECRET) environment variables"
            }
        
        # If using refresh token, test that it works
        if gmail_client.refresh_token and not gmail_client.access_token:
            try:
                import asyncio
                refreshed = await asyncio.wait_for(gmail_client.refresh_access_token(), timeout=10)
                if not refreshed:
                    return {
                        "success": False,
                        "error": "Gmail refresh token is invalid or expired",
                        "details": "Please generate a new refresh token from Google OAuth Playground or re-authenticate"
                    }
            except Exception as e:
                return {
                    "success": False,
                    "error": "Failed to refresh Gmail access token",
                    "details": str(e)
                }
        
        # Test Gmail API by fetching user profile
        try:
            import asyncio
            profile = await asyncio.wait_for(gmail_client.get_user_profile(), timeout=10)
            if profile and profile.get("emailAddress"):
                return {
                    "success": True,
                    "message": "Gmail API is working",
                    "details": f"Connected to: {profile['emailAddress']}"
                }
            else:
                return {
                    "success": False,
                    "error": "Gmail API returned invalid profile",
                    "details": "Profile response missing email address"
                }
        except Exception as api_err:
            return {
                "success": False,
                "error": "Gmail API call failed",
                "details": str(api_err)
            }
        
    except Exception as e:
        return {
            "success": False,
            "error": "Failed to initialize Gmail client",
            "details": str(e)
        }


@router.get("/check-gmail-config")
async def check_gmail_config():
    """
    Check Gmail API configuration status
    """
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    config = {
        "gmail_access_token": bool(os.getenv("GMAIL_ACCESS_TOKEN")),
        "gmail_refresh_token": bool(os.getenv("GMAIL_REFRESH_TOKEN")),
        "gmail_client_id": bool(os.getenv("GMAIL_CLIENT_ID")),
        "gmail_client_secret": bool(os.getenv("GMAIL_CLIENT_SECRET")),
    }
    
    is_configured = bool(
        os.getenv("GMAIL_ACCESS_TOKEN") or 
        (os.getenv("GMAIL_REFRESH_TOKEN") and os.getenv("GMAIL_CLIENT_ID") and os.getenv("GMAIL_CLIENT_SECRET"))
    )
    
    return {
        "configured": is_configured,
        "config": config,
        "message": "Gmail API is configured for sending emails" if is_configured else "Gmail API is not configured - emails cannot be sent"
    }


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
        
        # Step 5: DRAFT-READY = Leads/scraped emails with contact_email present and missing drafts
        # SINGLE SOURCE OF TRUTH: scrape_status IN (SCRAPED, ENRICHED) AND contact_email present AND source_type='website' AND no draft yet
        draft_ready = await db.execute(
            select(func.count(Prospect.id)).where(
                and_(
                    Prospect.contact_email.isnot(None),
                    func.length(func.trim(Prospect.contact_email)) > 0,
                    Prospect.scrape_status.in_([
                        ScrapeStatus.SCRAPED.value,
                        ScrapeStatus.ENRICHED.value
                    ]),
                    website_filter,
                    or_(
                        Prospect.draft_subject.is_(None),
                        func.length(func.trim(Prospect.draft_subject)) == 0,
                        Prospect.draft_body.is_(None),
                        func.length(func.trim(Prospect.draft_body)) == 0
                    )
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
    category: Optional[str] = None,
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

        # CRITICAL: Website outreach must never show social prospects.
        # Some deployments may not have source_type column yet; fall back safely.
        column_check = await db.execute(
            text(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'prospects'
                AND column_name = 'source_type'
                """
            )
        )
        has_source_type = column_check.fetchone() is not None
        if has_source_type:
            website_filter = or_(
                Prospect.source_type == 'website',
                Prospect.source_type.is_(None),
            )
        else:
            website_filter = true()

        # Only show items that still need action in Websites tab.
        # Once approved/rejected, they should disappear from Websites.
        pending_approval_filter = or_(
            Prospect.approval_status.is_(None),
            and_(
                Prospect.approval_status != "approved",
                Prospect.approval_status != "rejected",
            ),
        )
        
        normalized_category: Optional[str] = None
        if category and category.strip() and category.strip().lower() != 'all':
            normalized_category = category.strip()
            logger.info(f"🔍 [WEBSITES] Category filter applied: '{normalized_category}' (exact match, case-insensitive)")

        filters = [
            Prospect.discovery_status == DiscoveryStatus.DISCOVERED.value,
            pending_approval_filter,
            website_filter,
        ]
        if normalized_category:
            filters.append(Prospect.discovery_category.isnot(None))
            filters.append(Prospect.discovery_category.ilike(normalized_category))

        # Get total count FIRST (before pagination)
        try:
            total_result = await db.execute(
                select(func.count(Prospect.id)).where(
                    and_(*filters)
                )
            )
            total = total_result.scalar() or 0
            logger.info(f"📊 [WEBSITES] RAW COUNT (before pagination): {total} prospects with discovery_status = 'DISCOVERED'")
        except Exception as count_err:
            logger.error(f"❌ [WEBSITES] Failed to get total count: {count_err}", exc_info=True)
            total = 0
        
        # Get paginated results
        # SCHEMA MUST BE CORRECT - migrations must be run manually at deploy time
        # If this fails with UndefinedColumnError, migrations need to be run
        try:
            result = await db.execute(
                select(Prospect).where(and_(*filters))
                .order_by(Prospect.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
            websites = result.scalars().all()
        except Exception as query_err:
            error_str = str(query_err).lower()
            if "undefinedcolumn" in error_str or "does not exist" in error_str or "bio_text" in error_str:
                logger.error(f"❌ [WEBSITES] Schema mismatch detected: {query_err}")
                await db.rollback()
                raise HTTPException(
                    status_code=500,
                    detail=f"Database schema mismatch: Missing required columns. Please run migrations: 'alembic upgrade head' or use the /api/health/migrate endpoint. Error: {str(query_err)}"
                )
            raise  # Re-raise other errors
        logger.info(f"📊 [WEBSITES] QUERY RESULT: Found {len(websites)} websites from database query (total available: {total})")
        
        # If pagination skip is beyond total, it's valid to return an empty page.
        # Only treat this as an integrity violation if the requested page is within range.
        if total > 0 and len(websites) == 0 and skip < total:
            logger.error(
                f"❌ [WEBSITES] DATA INTEGRITY VIOLATION: total={total}, skip={skip} but query returned 0 rows"
            )
            await db.rollback()
            raise HTTPException(
                status_code=500,
                detail=(
                    f"Data integrity violation: COUNT query returned {total} but SELECT query returned 0 rows "
                    f"for skip={skip}. This indicates a schema mismatch or query error. Ensure migrations have run successfully."
                ),
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
    # Categories must match frontend available categories
    category_patterns = {
        'Museum': [
            # Domain patterns
            'museum', 'museums', 'museo', 'museu', 'muse', 'museet',
            # Title/URL patterns
            'art museum', 'gallery museum', 'contemporary museum', 'modern museum',
            'museum of art', 'art collection', 'permanent collection'
        ],
        'Art Lovers': [
            # Domain patterns
            'gallery', 'galleries', 'galerie', 'galeria', 'galerija',
            'studio', 'studios', 'atelier', 'ateliers',
            'art', 'arts', 'artwork', 'artworks',
            # Title/URL patterns
            'art gallery', 'contemporary art', 'fine art gallery', 'art space',
            'exhibition space', 'art showroom', 'gallery space', 'art room',
            'contemporary gallery', 'modern gallery', 'fine art', 'art display',
            'art studio', 'artist studio', 'creative studio', 'painting studio',
            'sculpture studio', 'artists studio', 'working studio', 'art workshop',
            'art fair', 'art exhibition', 'art show', 'art expo', 'art market',
            'art event', 'art festival', 'biennale', 'biennial', 'art week',
            'art lover', 'art lovers', 'art enthusiast', 'art enthusiasts'
        ],
        'Interior Design': [
            # Domain patterns
            'interior', 'interiors', 'design', 'designer', 'designers',
            # Title/URL patterns
            'interior design', 'interior designer', 'home design', 'space design',
            'interior decorator', 'interior decoration', 'home styling'
        ],
        'Interior Decor': [
            # Domain patterns
            'decor', 'decoration', 'decorator', 'decorators',
            # Title/URL patterns
            'interior decor', 'home decor', 'decorating', 'home decoration'
        ],
        'Home Decor': [
            # Domain patterns
            'home', 'homedecor', 'homedecoration',
            # Title/URL patterns
            'home decor', 'home decoration', 'home accessories', 'home furnishings'
        ],
        'Holiday Decor': [
            # Domain patterns
            'holiday', 'holidays', 'christmas', 'halloween', 'thanksgiving',
            # Title/URL patterns
            'holiday decor', 'holiday decoration', 'seasonal decor', 'holiday decorating'
        ],
        'Holidays': [
            # Domain patterns
            'holiday', 'holidays', 'festival', 'festivals', 'celebration',
            # Title/URL patterns
            'holiday', 'holidays', 'festival', 'celebration', 'seasonal'
        ],
        'Pet Lovers': [
            # Domain patterns - combined dog and cat patterns
            'dog', 'dogs', 'puppy', 'puppies', 'canine', 'canines',
            'cat', 'cats', 'kitten', 'kittens', 'feline', 'felines',
            'pet', 'pets', 'petlover', 'petlovers', 'pet-lover', 'pet-lovers',
            'doglover', 'doglovers', 'dog-lover', 'dog-lovers',
            'catlover', 'catlovers', 'cat-lover', 'cat-lovers',
            # Title/URL patterns
            'dog', 'dogs', 'puppy', 'canine', 'dog training', 'dog care',
            'cat', 'cats', 'kitten', 'feline', 'cat care', 'cat training',
            'pet lover', 'pet lovers', 'pet owner', 'pet owners',
            'dog lover', 'dog lovers', 'dog owner', 'dog owners',
            'cat lover', 'cat lovers', 'cat owner', 'cat owners'
        ],
        'Dogs and Cat Owners - Fur Parent': [
            # Domain patterns
            'furparent', 'furparents', 'fur-parent', 'fur-parents',
            'furmom', 'furdad', 'furmommy', 'furdaddy',
            # Title/URL patterns
            'fur parent', 'fur parents', 'fur mom', 'fur dad',
            'fur mommy', 'fur daddy', 'pet parent', 'pet parents',
            'dog and cat owner', 'dogs and cats owner', 'dog and cat owners',
            'dogs and cats owners', 'multi pet owner', 'multi pet owners'
        ],
        'Parenting': [
            # Domain patterns
            'parent', 'parents', 'parenting', 'mom', 'moms', 'dad', 'dads',
            'family', 'families', 'children', 'kids', 'child',
            # Title/URL patterns
            'parenting', 'parent', 'family', 'children', 'kids', 'child care'
        ],
        'Childhood Development': [
            # Domain patterns
            'child', 'children', 'childhood', 'development', 'early', 'education',
            # Title/URL patterns
            'child development', 'childhood development', 'early childhood', 'child education'
        ],
        'Home Tech': [
            # Domain patterns
            'tech', 'technology', 'smart', 'automation', 'iot', 'homeautomation',
            # Title/URL patterns
            'home tech', 'smart home', 'home automation', 'home technology'
        ],
        'Audio Visual': [
            # Domain patterns
            'audio', 'visual', 'av', 'audiovisual', 'sound', 'video',
            # Title/URL patterns
            'audio visual', 'audiovisual', 'sound system', 'home theater'
        ],
        'NFTs': [
            # Domain patterns
            'nft', 'nfts', 'crypto', 'blockchain', 'web3',
            # Title/URL patterns
            'nft', 'nfts', 'non-fungible token', 'crypto art', 'digital art'
        ],
        'Famous Quotes': [
            # Domain patterns
            'quote', 'quotes', 'quotation', 'quotations', 'inspirational',
            # Title/URL patterns
            'quote', 'quotes', 'famous quote', 'inspirational quote'
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
    logger.info("🤖 [AUTO CATEGORIZE] Starting automatic categorization - updating from discovery queries and pattern matching")
    
    # First, check how many total prospects exist and their category status
    total_result = await db.execute(select(func.count(Prospect.id)))
    total_prospects = total_result.scalar_one()
    
    # Check category distribution
    category_dist = await db.execute(
        select(Prospect.discovery_category, func.count(Prospect.id)).group_by(Prospect.discovery_category)
    )
    category_counts = {cat or 'NULL': count for cat, count in category_dist.all()}
    logger.info(f"📊 [AUTO CATEGORIZE] Total prospects: {total_prospects}, Category distribution: {category_counts}")
    
    # Strategy 1: Get prospects with discovery_query_id that need category updates
    # This ensures all prospects inherit their discovery query category
    from app.models.discovery_query import DiscoveryQuery
    
    prospects_with_query = await db.execute(
        select(Prospect).where(
            Prospect.discovery_query_id.isnot(None)
        ).limit(1000)  # Limit to avoid memory issues
    )
    prospects = prospects_with_query.scalars().all()
    logger.info(f"📊 [AUTO CATEGORIZE] Found {len(prospects)} prospects with discovery_query_id")
    
    # Strategy 2: Also get uncategorized prospects without discovery_query_id
    uncategorized_result = await db.execute(
        select(Prospect).where(
            and_(
                Prospect.discovery_query_id.is_(None),
            or_(
                Prospect.discovery_category.is_(None),
                Prospect.discovery_category == '',
                    func.lower(Prospect.discovery_category) == 'n/a',
                Prospect.discovery_category == 'N/A',
                    func.lower(Prospect.discovery_category) == 'unknown',
                    Prospect.discovery_category == 'Unknown',
                    func.trim(Prospect.discovery_category) == ''  # Also catch whitespace-only
                )
            )
        ).limit(1000)
    )
    uncategorized = uncategorized_result.scalars().all()
    logger.info(f"📊 [AUTO CATEGORIZE] Found {len(uncategorized)} uncategorized prospects without discovery_query_id")
    
    # Combine both lists (avoid duplicates)
    prospect_ids = {p.id for p in prospects}
    for p in uncategorized:
        if p.id not in prospect_ids:
            prospects.append(p)
            prospect_ids.add(p.id)
    
    logger.info(f"📊 [AUTO CATEGORIZE] Processing {len(prospects)} total prospects")
    
    categorized_count = 0
    
    for prospect in prospects:
        original_category = prospect.discovery_category
        new_category = None
        
        # First try to get category from discovery_query
        if prospect.discovery_query_id:
            try:
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
                    new_category = query_category
                    logger.info(f"✅ [AUTO CATEGORIZE] Prospect {prospect.id} ({prospect.domain}): Inherited category '{query_category}' from discovery query")
                else:
                    logger.debug(f"⚠️  [AUTO CATEGORIZE] Prospect {prospect.id} ({prospect.domain}): discovery_query_id exists but query has no category")
            except Exception as query_err:
                logger.warning(f"⚠️  [AUTO CATEGORIZE] Error getting category from discovery query for prospect {prospect.id} ({prospect.domain}): {query_err}")
        else:
            logger.debug(f"⚠️  [AUTO CATEGORIZE] Prospect {prospect.id} ({prospect.domain}): No discovery_query_id")
        
        # If no category from discovery_query, try auto-categorization
        if not new_category:
            new_category = await auto_categorize_prospect(prospect, db)
            if new_category:
                logger.info(f"✅ [AUTO CATEGORIZE] Prospect {prospect.id} ({prospect.domain}): Auto-categorized as '{new_category}'")
            else:
                logger.warning(f"⚠️  [AUTO CATEGORIZE] Prospect {prospect.id} ({prospect.domain}): Could not determine category (domain: {prospect.domain}, title: {prospect.page_title or 'N/A'})")
        
        # Update category if we found one
        if new_category and new_category != original_category:
            prospect.discovery_category = new_category
            categorized_count += 1
            # Explicitly mark as modified
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(prospect, 'discovery_category')
    
    # Commit all changes
    try:
        await db.commit()
        logger.info(f"✅ [AUTO CATEGORIZE] Committed {categorized_count} category updates to database")
    except Exception as commit_err:
        logger.error(f"❌ [AUTO CATEGORIZE] Failed to commit changes: {commit_err}")
        await db.rollback()
        raise
    
    logger.info(f"✅ [AUTO CATEGORIZE] Automatically categorized {categorized_count} of {len(prospects)} prospects")
    
    return AutoCategorizeResponse(
        success=True,
        categorized_count=categorized_count,
        message=f"Successfully auto-categorized {categorized_count} prospect(s) based on their content"
    )


class MigrateCategoriesResponse(BaseModel):
    success: bool
    migrated_count: int
    category_mapping: dict
    message: str


class BackfillDraftsMetadataResponse(BaseModel):
    success: bool
    sent_marked: int
    drafts_cleared: int
    categories_filled: int
    locations_filled: int
    message: str


@router.post("/migrate_categories", response_model=MigrateCategoriesResponse)
async def migrate_categories(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Migrate old category values to new standardized categories.
    Maps old categories (like "art", "interior_design", "tech_blog") to new ones
    (like "Art", "Interior Design", "Home Tech").
    
    This helps fix filtering issues where old records have categories that don't match
    the new category list used in the frontend.
    """
    logger.info("🔄 [MIGRATE CATEGORIES] Starting category migration")
    
    # Define mapping from old categories to new ones
    # Handles various formats: lowercase, snake_case, variations
    category_mapping = {
        # Old lowercase/snake_case formats
        'art': 'Art Lovers',
        'Art': 'Art Lovers',  # Updated to new category name
        'art lovers': 'Art Lovers',
        'Art Lovers': 'Art Lovers',
        'art enthusiast': 'Art Lovers',
        'art enthusiasts': 'Art Lovers',
        'interior_design': 'Interior Design',
        'interior design': 'Interior Design',
        'Interior Design': 'Interior Design',
        'interior_decor': 'Interior Decor',
        'interior decor': 'Interior Decor',
        'Interior Decor': 'Interior Decor',
        'home_decor': 'Home Decor',
        'home decor': 'Home Decor',
        'Home Decor': 'Home Decor',
        'home_tech': 'Home Tech',
        'home tech': 'Home Tech',
        'Home Tech': 'Home Tech',
        'tech_blog': 'Home Tech',  # Map tech_blog to Home Tech
        'tech blog': 'Home Tech',
        'mothers_tech': 'Parenting',  # Map mothers_tech to Parenting
        'mothers tech': 'Parenting',
        'mom_blog': 'Parenting',
        'mom blog': 'Parenting',
        'nft': 'NFTs',
        'NFT': 'NFTs',
        'NFTs': 'NFTs',
        'nft_tech': 'NFTs',
        'museum': 'Museum',
        'Museum': 'Museum',
        'museums': 'Museum',
        'Museums': 'Museum',
        'art_gallery': 'Art',
        'art gallery': 'Art',
        'Art Gallery': 'Art',
        'gallery': 'Art',
        'holiday': 'Holidays',
        'Holiday': 'Holidays',
        'Holidays': 'Holidays',
        'holiday_decor': 'Holiday Decor',
        'holiday decor': 'Holiday Decor',
        'Holiday Decor': 'Holiday Decor',
        'holiday/family': 'Holidays',
        'Holiday/Family': 'Holidays',
        'editorial_media': 'Art Lovers',  # Map editorial to Art Lovers (closest match)
        'editorial media': 'Art Lovers',
        'Editorial Media': 'Art Lovers',
        # Old pet categories mapped to new combined categories
        'dog': 'Pet Lovers',
        'Dogs': 'Pet Lovers',
        'dog_lover': 'Pet Lovers',
        'dog lover': 'Dog Lovers',  # Keep for backward compatibility, but map to Pet Lovers
        'Dog Lovers': 'Pet Lovers',
        'cat': 'Pet Lovers',
        'Cats': 'Pet Lovers',
        'cat_lover': 'Pet Lovers',
        'cat lover': 'Cat Lovers',  # Keep for backward compatibility, but map to Pet Lovers
        'Cat Lovers': 'Pet Lovers',
        # New category names
        'Pet Lovers': 'Pet Lovers',
        'pet_lovers': 'Pet Lovers',
        'pet lovers': 'Pet Lovers',
        'pet': 'Pet Lovers',
        'pets': 'Pet Lovers',
        'Dogs and Cat Owners - Fur Parent': 'Dogs and Cat Owners - Fur Parent',
        'dogs and cat owners - fur parent': 'Dogs and Cat Owners - Fur Parent',
        'fur parent': 'Dogs and Cat Owners - Fur Parent',
        'fur parents': 'Dogs and Cat Owners - Fur Parent',
        'fur_parent': 'Dogs and Cat Owners - Fur Parent',
        'fur_parents': 'Dogs and Cat Owners - Fur Parent',
        'parenting': 'Parenting',
        'Parenting': 'Parenting',
        'childhood_development': 'Childhood Development',
        'childhood development': 'Childhood Development',
        'Childhood Development': 'Childhood Development',
        'audio_visual': 'Audio Visual',
        'audio visual': 'Audio Visual',
        'Audio Visual': 'Audio Visual',
        'famous_quotes': 'Famous Quotes',
        'famous quotes': 'Famous Quotes',
        'Famous Quotes': 'Famous Quotes',
        # Handle unknown/null values - will be handled by auto-categorize
        'unknown': None,  # Will trigger auto-categorization
        'Unknown': None,
        'n/a': None,
        'N/A': None,
        '': None,
        None: None
    }
    
    # Get all prospects with categories that need migration
    all_prospects_result = await db.execute(
        select(Prospect).where(
            Prospect.discovery_category.isnot(None)
        )
    )
    all_prospects = all_prospects_result.scalars().all()
    
    logger.info(f"📊 [MIGRATE CATEGORIES] Found {len(all_prospects)} prospects with categories")
    
    # Get current category distribution before migration
    category_dist_before = await db.execute(
        select(Prospect.discovery_category, func.count(Prospect.id)).group_by(Prospect.discovery_category)
    )
    categories_before = {cat or 'NULL': count for cat, count in category_dist_before.all()}
    logger.info(f"📊 [MIGRATE CATEGORIES] Categories before migration: {categories_before}")
    
    migrated_count = 0
    migration_details = {}
    
    for prospect in all_prospects:
        old_category = prospect.discovery_category
        if not old_category:
            continue
            
        # Normalize the category (strip whitespace, handle case variations)
        normalized_old = old_category.strip() if old_category else None
        
        # Check if this category needs migration
        new_category = category_mapping.get(normalized_old)
        
        # If not in mapping, try case-insensitive lookup
        if new_category is None and normalized_old:
            # Try case-insensitive match
            for old_cat, new_cat in category_mapping.items():
                if old_cat and normalized_old.lower() == old_cat.lower():
                    new_category = new_cat
                    break
        
        # If still no match, check if it's already a valid new category
        valid_categories = [
            'Art Lovers', 'Interior Design', 'Pet Lovers', 'Dogs and Cat Owners - Fur Parent', 'Childhood Development',
            'Holidays', 'Famous Quotes', 'Home Decor',
            'Audio Visual', 'Interior Decor', 'Holiday Decor', 'Home Tech',
            'Parenting', 'NFTs', 'Museum'
        ]
        if normalized_old in valid_categories:
            # Already a valid category, skip
            continue
        
        # If we found a mapping, update the prospect
        if new_category is not None:
            if new_category != old_category:
                prospect.discovery_category = new_category
                migrated_count += 1
                
                # Track migration details
                if old_category not in migration_details:
                    migration_details[old_category] = {'to': new_category, 'count': 0}
                migration_details[old_category]['count'] += 1
                
                logger.debug(f"🔄 [MIGRATE CATEGORIES] Prospect {prospect.id}: '{old_category}' → '{new_category}'")
        else:
            # Category not in mapping and not valid - try auto-categorization
            logger.debug(f"⚠️  [MIGRATE CATEGORIES] Prospect {prospect.id}: Unknown category '{old_category}', attempting auto-categorization")
            auto_category = await auto_categorize_prospect(prospect, db)
            if auto_category and auto_category != old_category:
                prospect.discovery_category = auto_category
                migrated_count += 1
                
                if old_category not in migration_details:
                    migration_details[old_category] = {'to': auto_category, 'count': 0}
                migration_details[old_category]['count'] += 1
                
                logger.info(f"✅ [MIGRATE CATEGORIES] Prospect {prospect.id}: Auto-categorized '{old_category}' → '{auto_category}'")
    
    # Commit all changes
    try:
        await db.commit()
        logger.info(f"✅ [MIGRATE CATEGORIES] Committed {migrated_count} category migrations to database")
    except Exception as commit_err:
        logger.error(f"❌ [MIGRATE CATEGORIES] Failed to commit changes: {commit_err}")
        await db.rollback()
        raise
    
    # Get category distribution after migration
    category_dist_after = await db.execute(
        select(Prospect.discovery_category, func.count(Prospect.id)).group_by(Prospect.discovery_category)
    )
    categories_after = {cat or 'NULL': count for cat, count in category_dist_after.all()}
    logger.info(f"📊 [MIGRATE CATEGORIES] Categories after migration: {categories_after}")
    
    return MigrateCategoriesResponse(
        success=True,
        migrated_count=migrated_count,
        category_mapping=migration_details,
        message=f"Successfully migrated {migrated_count} prospect(s) to new category format"
    )


@router.post("/backfill_drafts_metadata", response_model=BackfillDraftsMetadataResponse)
async def backfill_drafts_metadata(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """Backfill metadata for existing prospects so Drafts filtering works reliably.

    - Mark prospects as sent based on EmailLog and clear drafts (so sent items drop out of Drafts)
    - Fill missing discovery_category/discovery_location from DiscoveryQuery or same-domain inheritance
    """
    sent_marked = 0
    drafts_cleared = 0
    categories_filled = 0
    locations_filled = 0

    try:
        # 1) Sent cleanup based on EmailLog
        sent_rows = await db.execute(
            select(
                Prospect,
                func.max(EmailLog.sent_at).label("max_sent_at")
            )
            .join(EmailLog, EmailLog.prospect_id == Prospect.id)
            .group_by(Prospect.id)
        )

        for prospect, max_sent_at in sent_rows.all():
            if prospect.send_status != SendStatus.SENT.value:
                prospect.send_status = SendStatus.SENT.value
                prospect.outreach_status = "sent"
                sent_marked += 1

            if max_sent_at and (not prospect.last_sent or max_sent_at > prospect.last_sent):
                prospect.last_sent = max_sent_at

            if prospect.draft_subject is not None or prospect.draft_body is not None:
                prospect.draft_subject = None
                prospect.draft_body = None
                drafts_cleared += 1

        # 2) Fill missing discovery_category/discovery_location
        def _needs_value(v: Optional[str]) -> bool:
            if v is None:
                return True
            vv = str(v).strip()
            if not vv:
                return True
            return vv.lower() in {"unknown", "n/a"}

        missing_meta_result = await db.execute(
            select(Prospect).where(
                or_(
                    Prospect.discovery_category.is_(None),
                    func.trim(Prospect.discovery_category) == '',
                    func.lower(Prospect.discovery_category) == 'unknown',
                    func.lower(Prospect.discovery_category) == 'n/a',
                    Prospect.discovery_location.is_(None),
                    func.trim(Prospect.discovery_location) == '',
                    func.lower(Prospect.discovery_location) == 'unknown',
                    func.lower(Prospect.discovery_location) == 'n/a',
                )
            )
        )
        missing_meta = missing_meta_result.scalars().all()

        for prospect in missing_meta:
            # Try DiscoveryQuery inheritance first
            if prospect.discovery_query_id:
                if _needs_value(prospect.discovery_category):
                    result = await db.execute(
                        select(DiscoveryQuery.category).where(
                            DiscoveryQuery.id == prospect.discovery_query_id,
                            DiscoveryQuery.category.isnot(None),
                            DiscoveryQuery.category != ''
                        )
                    )
                    cat = result.scalar_one_or_none()
                    if cat and cat != prospect.discovery_category:
                        prospect.discovery_category = cat
                        categories_filled += 1

                if _needs_value(prospect.discovery_location):
                    result = await db.execute(
                        select(DiscoveryQuery.location).where(
                            DiscoveryQuery.id == prospect.discovery_query_id,
                            DiscoveryQuery.location.isnot(None),
                            DiscoveryQuery.location != ''
                        )
                    )
                    loc = result.scalar_one_or_none()
                    if loc and loc != prospect.discovery_location:
                        prospect.discovery_location = loc
                        locations_filled += 1

            # Same-domain inheritance as second-best
            if prospect.domain:
                if _needs_value(prospect.discovery_category):
                    result = await db.execute(
                        select(Prospect.discovery_category).where(
                            Prospect.domain == prospect.domain,
                            Prospect.id != prospect.id,
                            Prospect.discovery_category.isnot(None),
                            func.trim(Prospect.discovery_category) != '',
                            func.lower(Prospect.discovery_category) != 'unknown',
                            func.lower(Prospect.discovery_category) != 'n/a',
                        ).limit(1)
                    )
                    cat = result.scalar_one_or_none()
                    if cat and cat != prospect.discovery_category:
                        prospect.discovery_category = cat
                        categories_filled += 1

                if _needs_value(prospect.discovery_location):
                    result = await db.execute(
                        select(Prospect.discovery_location).where(
                            Prospect.domain == prospect.domain,
                            Prospect.id != prospect.id,
                            Prospect.discovery_location.isnot(None),
                            func.trim(Prospect.discovery_location) != '',
                            func.lower(Prospect.discovery_location) != 'unknown',
                            func.lower(Prospect.discovery_location) != 'n/a',
                        ).limit(1)
                    )
                    loc = result.scalar_one_or_none()
                    if loc and loc != prospect.discovery_location:
                        prospect.discovery_location = loc
                        locations_filled += 1

            # Fallback: auto-categorize (category only)
            if _needs_value(prospect.discovery_category):
                auto_cat = await auto_categorize_prospect(prospect, db)
                if auto_cat and auto_cat != prospect.discovery_category:
                    prospect.discovery_category = auto_cat
                    categories_filled += 1

        missing_category_count = await db.execute(
            select(func.count(Prospect.id)).where(
                or_(
                    Prospect.discovery_category.is_(None),
                    func.trim(Prospect.discovery_category) == '',
                    func.lower(Prospect.discovery_category) == 'unknown',
                    func.lower(Prospect.discovery_category) == 'n/a',
                )
            )
        )
        still_missing_category = missing_category_count.scalar() or 0

        await db.commit()
    except Exception as e:
        logger.error(f"❌ [BACKFILL DRAFTS METADATA] Failed: {e}", exc_info=True)
        try:
            await db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Backfill failed: {str(e)}")

    return BackfillDraftsMetadataResponse(
        success=True,
        sent_marked=sent_marked,
        drafts_cleared=drafts_cleared,
        categories_filled=categories_filled,
        locations_filled=locations_filled,
        message=(
            "Backfill completed. "
            f"Marked sent: {sent_marked}, cleared drafts: {drafts_cleared}, "
            f"locations filled: {locations_filled}. "
            f"Still missing category: {still_missing_category}."
        )
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

