"""
Social Outreach Pipeline API

REUSES Website Outreach Pipeline - filters by source_type='social'.
Stage-based progression for social media outreach.

Pipeline Stages (same as website):
1. Discovery - Always unlocked
2. Profile Review - Unlocked when discovered_count > 0
3. Drafting - Unlocked when qualified_count > 0
4. Sending - Unlocked when drafted_count > 0
5. Follow-ups - Unlocked when sent_count > 0

All queries filter: source_type='social'
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timezone, timedelta
import logging
from pydantic import BaseModel

from app.db.database import get_db
from app.api.auth import get_current_user_optional
from app.models.prospect import Prospect, DiscoveryStatus
from app.adapters.social_discovery import (
    LinkedInDiscoveryAdapter,
    InstagramDiscoveryAdapter,
    TikTokDiscoveryAdapter,
    FacebookDiscoveryAdapter
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/social/pipeline", tags=["social-pipeline"])


# ============================================
# PIPELINE STATUS
# ============================================

@router.get("/status")
async def get_social_pipeline_status(
    platform: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Get social pipeline status.
    
    REUSES prospects table - filters by source_type='social'.
    Same pipeline stages as website outreach.
    
    Returns:
        {
            "discovered": int,      # discovery_status = 'DISCOVERED' AND source_type='social'
            "reviewed": int,        # approval_status = 'approved' AND source_type='social'
            "qualified": int,       # scrape_status = 'SCRAPED' AND source_type='social'
            "drafted": int,         # draft_status = 'drafted' AND source_type='social'
            "sent": int,            # send_status = 'sent' AND source_type='social'
            "followup_ready": int,  # sent AND last_sent < threshold AND source_type='social'
        }
    """
    # CRITICAL: Wrap entire function to prevent ANY 500 errors
    # Always return 200 with status="inactive" if schema is missing
    try:
        # CRITICAL: Check if source_type column exists
        # If migration hasn't run, return empty status instead of crashing
        column_exists = False
        try:
            from sqlalchemy import text
            # Check if column exists using raw SQL
            column_check = await db.execute(
                text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'prospects' 
                    AND column_name = 'source_type'
                """)
            )
            column_exists = column_check.fetchone() is not None
        except Exception as check_err:
            # If checking for column fails, assume it doesn't exist
            logger.warning(f"⚠️  [SOCIAL PIPELINE] Could not check for source_type column: {check_err}")
            column_exists = False
        
        if not column_exists:
            logger.warning("⚠️  [SOCIAL PIPELINE] source_type column does not exist - migration not applied")
            logger.warning("⚠️  [SOCIAL PIPELINE] Returning empty status - migration add_social_columns_to_prospects needs to run")
            return {
                "discovered": 0,
                "reviewed": 0,
                "qualified": 0,
                "drafted": 0,
                "sent": 0,
                "followup_ready": 0,
                "status": "inactive",
                "message": "Social outreach columns not initialized. Please run migration: alembic upgrade head"
            }
        
        # Base filter: only social prospects
        # Wrap in try-catch in case the column access itself fails
        try:
            social_filter = Prospect.source_type == 'social'
            
            # Add platform filter if specified
            if platform:
                platform_lower = platform.lower()
                valid_platforms = ['linkedin', 'instagram', 'facebook', 'tiktok']
                if platform_lower not in valid_platforms:
                    return {
                        "discovered": 0,
                        "reviewed": 0,
                        "qualified": 0,
                        "drafted": 0,
                        "sent": 0,
                        "followup_ready": 0,
                        "status": "inactive",
                        "message": f"Invalid platform: {platform}"
                    }
                social_filter = and_(social_filter, Prospect.source_platform == platform_lower)
        except Exception as filter_err:
            # If accessing source_type fails, return safe response
            logger.error(f"❌ [SOCIAL PIPELINE] Error accessing source_type column: {filter_err}")
            return {
                "discovered": 0,
                "reviewed": 0,
                "qualified": 0,
                "drafted": 0,
                "sent": 0,
                "followup_ready": 0,
                "status": "inactive",
                "message": "Social outreach columns not initialized. Please run migration: alembic upgrade head"
            }
        
        # Count discovered profiles
        discovered_result = await db.execute(
            select(func.count(Prospect.id)).where(
                and_(
                    social_filter,
                    Prospect.discovery_status == DiscoveryStatus.DISCOVERED.value
                )
            )
        )
        discovered_count = discovered_result.scalar() or 0
        
        # Count reviewed/approved profiles
        reviewed_result = await db.execute(
            select(func.count(Prospect.id)).where(
                and_(
                    social_filter,
                    Prospect.approval_status == 'approved'
                )
            )
        )
        reviewed_count = reviewed_result.scalar() or 0
        
        # Count qualified profiles (scraped with emails or enriched)
        qualified_result = await db.execute(
            select(func.count(Prospect.id)).where(
                and_(
                    social_filter,
                    Prospect.scrape_status.in_(['SCRAPED', 'ENRICHED'])
                )
            )
        )
        qualified_count = qualified_result.scalar() or 0
        
        # Count drafted profiles
        drafted_result = await db.execute(
            select(func.count(Prospect.id)).where(
                and_(
                    social_filter,
                    Prospect.draft_status == 'drafted'
                )
            )
        )
        drafted_count = drafted_result.scalar() or 0
        
        # Count sent profiles
        sent_result = await db.execute(
            select(func.count(Prospect.id)).where(
                and_(
                    social_filter,
                    Prospect.send_status == 'sent'
                )
            )
        )
        sent_count = sent_result.scalar() or 0
        
        # Count follow-up ready profiles (sent AND last_sent > 7 days ago or NULL)
        followup_threshold = datetime.now(timezone.utc) - timedelta(days=7)
        followup_ready_result = await db.execute(
            select(func.count(Prospect.id)).where(
                and_(
                    social_filter,
                    Prospect.send_status == 'sent',
                    or_(
                        Prospect.last_sent.is_(None),
                        Prospect.last_sent < followup_threshold
                    )
                )
            )
        )
        followup_ready_count = followup_ready_result.scalar() or 0
        
        logger.info(
            f"📊 [SOCIAL PIPELINE] Status: "
            f"discovered={discovered_count}, reviewed={reviewed_count}, "
            f"qualified={qualified_count}, drafted={drafted_count}, "
            f"sent={sent_count}, followup_ready={followup_ready_count}"
        )
        
        return {
            "discovered": discovered_count,
            "reviewed": reviewed_count,
            "qualified": qualified_count,
            "drafted": drafted_count,
            "sent": sent_count,
            "followup_ready": followup_ready_count,
            "status": "active",
            "platform": platform  # Include platform in response
        }
        
    except Exception as e:
        # CRITICAL: Never return 500 - always return safe response
        # Check if error is related to missing column
        error_str = str(e).lower()
        if 'source_type' in error_str or 'column' in error_str or 'does not exist' in error_str or 'undefinedcolumn' in error_str:
            logger.warning(f"⚠️  [SOCIAL PIPELINE] Database schema error (likely missing columns): {e}")
            logger.warning("⚠️  [SOCIAL PIPELINE] Returning safe empty status instead of 500")
            return {
                "discovered": 0,
                "reviewed": 0,
                "qualified": 0,
                "drafted": 0,
                "sent": 0,
                "followup_ready": 0,
                "status": "inactive",
                "message": "Social outreach columns not initialized. Please run migration: alembic upgrade head"
            }
        else:
            # For other errors, still return safe response but log the error
            logger.error(f"❌ [SOCIAL PIPELINE] Unexpected error computing status: {e}", exc_info=True)
            return {
                "discovered": 0,
                "reviewed": 0,
                "qualified": 0,
                "drafted": 0,
                "sent": 0,
                "followup_ready": 0,
                "status": "inactive",
                "message": f"Error computing pipeline status: {str(e)}"
            }


# ============================================
# STAGE 1: DISCOVERY
# ============================================

class SocialDiscoveryRequest(BaseModel):
    platform: str  # linkedin, facebook, instagram, tiktok
    categories: List[str]
    locations: List[str]
    keywords: List[str] = []
    parameters: dict = {}  # Platform-specific parameters
    max_results: Optional[int] = 100


class SocialDiscoveryResponse(BaseModel):
    success: bool
    job_id: UUID
    message: str
    profiles_count: int


@router.post("/discover", response_model=SocialDiscoveryResponse)
async def discover_profiles(
    request: SocialDiscoveryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    STAGE 1: Discover social profiles using adapter pattern.
    
    Always unlocked - this is the entry point.
    Uses platform-specific adapters to normalize results into Prospect objects.
    """
    # Validate platform
    platform = request.platform.lower()
    valid_platforms = ['linkedin', 'instagram', 'facebook', 'tiktok']
    if platform not in valid_platforms:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid platform. Must be one of: {valid_platforms}"
        )
    
    # Validate required fields
    if not request.categories:
        raise HTTPException(status_code=400, detail="At least one category is required")
    if not request.locations:
        raise HTTPException(status_code=400, detail="At least one location is required")
    
    logger.info(f"🔍 [SOCIAL PIPELINE STAGE 1] Discovery request for {platform}")
    
    try:
        # Create discovery job with status "pending" (will be processed in background)
        from app.models import Job
        job = Job(
            job_type="social_discover",
            params={
                "platform": platform,
                "categories": request.categories,
                "locations": request.locations,
                "keywords": request.keywords,
                "max_results": request.max_results or 100,
                **request.parameters
            },
            status="pending"
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        
        # Start discovery task in background (like website discovery)
        try:
            from app.tasks.social_discovery import process_social_discovery_job
            import asyncio
            from app.task_manager import register_task
            
            task = asyncio.create_task(process_social_discovery_job(str(job.id)))
            register_task(str(job.id), task)
            logger.info(f"✅ [SOCIAL PIPELINE STAGE 1] Discovery job {job.id} started in background")
        except Exception as e:
            logger.error(f"❌ [SOCIAL PIPELINE STAGE 1] Failed to start discovery job: {e}", exc_info=True)
            job.status = "failed"
            job.error_message = str(e)
            await db.commit()
            raise HTTPException(status_code=500, detail=f"Failed to start discovery job: {str(e)}")
        
        return SocialDiscoveryResponse(
            success=True,
            job_id=job.id,
            message=f"Discovery job started. Finding {platform} profiles in {len(request.categories)} categories and {len(request.locations)} locations.",
            profiles_count=0  # Will be updated when job completes
        )
        
    except Exception as e:
        logger.error(f"❌ [SOCIAL PIPELINE STAGE 1] Error: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to discover profiles: {str(e)}")


# ============================================
# STAGE 2: PROFILE REVIEW
# ============================================

class ProfileReviewRequest(BaseModel):
    profile_ids: List[UUID]
    action: str  # "qualify" or "reject"


@router.post("/review")
async def review_profiles(
    request: ProfileReviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    STAGE 2: Review and approve/reject social profiles.
    
    REUSES website approval logic - filters by source_type='social'.
    Unlocked when discovered_count > 0.
    """
    if request.action not in ["qualify", "reject"]:
        raise HTTPException(status_code=400, detail="Action must be 'qualify' or 'reject'")
    
    if not request.profile_ids:
        raise HTTPException(status_code=400, detail="At least one profile ID is required")
    
    logger.info(f"📋 [SOCIAL PIPELINE STAGE 2] Reviewing {len(request.profile_ids)} profiles: {request.action}")
    
    try:
        # Get social prospects
        result = await db.execute(
            select(Prospect).where(
                and_(
                    Prospect.id.in_(request.profile_ids),
                    Prospect.source_type == 'social'
                )
            )
        )
        prospects = result.scalars().all()
        
        if len(prospects) != len(request.profile_ids):
            logger.warning(f"⚠️  Only found {len(prospects)} of {len(request.profile_ids)} requested profiles")
        
        updated_count = 0
        
        # Map action to approval_status (reuse website logic)
        if request.action == "qualify":
            # Qualify = approve (same as website outreach)
            # When qualifying, trigger scraping to get real follower counts, engagement rates, and emails
            for prospect in prospects:
                prospect.approval_status = "approved"
                updated_count += 1
                logger.info(f"🔍 [SOCIAL PIPELINE STAGE 2] Qualifying profile {prospect.id}, will trigger scraping")
        else:
            # Reject = rejected
            for prospect in prospects:
                prospect.approval_status = "rejected"
                updated_count += 1
        
        await db.commit()
        
        # If qualifying, trigger scraping in background to get real data
        if request.action == "qualify":
            # Import here to avoid circular imports
            from app.services.social_profile_scraper import scrape_social_profile
            import asyncio
            
            async def scrape_profiles_background():
                """Scrape profiles in background to get real follower counts, engagement rates, and emails"""
                from app.db.database import AsyncSessionLocal
                async with AsyncSessionLocal() as scrape_db:
                    try:
                        for prospect in prospects:
                            if prospect.approval_status == "approved" and prospect.profile_url and prospect.source_platform:
                                try:
                                    # Re-fetch prospect in new session
                                    result = await scrape_db.execute(
                                        select(Prospect).where(Prospect.id == prospect.id)
                                    )
                                    prospect_to_update = result.scalar_one_or_none()
                                    if not prospect_to_update:
                                        continue
                                    
                                    logger.info(f"🔍 [SOCIAL SCRAPE] Scraping {prospect_to_update.source_platform} profile: {prospect_to_update.profile_url}")
                                    scrape_result = await scrape_social_profile(
                                        prospect_to_update.profile_url,
                                        prospect_to_update.source_platform
                                    )
                                    
                                    if scrape_result.get("success"):
                                        # Update prospect with real data
                                        if scrape_result.get("follower_count"):
                                            prospect_to_update.follower_count = scrape_result["follower_count"]
                                        if scrape_result.get("engagement_rate"):
                                            prospect_to_update.engagement_rate = scrape_result["engagement_rate"]
                                        if scrape_result.get("email"):
                                            prospect_to_update.contact_email = scrape_result["email"]
                                            prospect_to_update.contact_method = "profile_scraping"
                                        
                                        # Update scrape status
                                        if scrape_result.get("email"):
                                            prospect_to_update.scrape_status = "SCRAPED"
                                        else:
                                            prospect_to_update.scrape_status = "NO_EMAIL_FOUND"
                                        
                                        await scrape_db.commit()
                                        logger.info(f"✅ [SOCIAL SCRAPE] Updated profile {prospect_to_update.id} with real data: followers={prospect_to_update.follower_count}, engagement={prospect_to_update.engagement_rate}, email={prospect_to_update.contact_email}")
                                    else:
                                        logger.warning(f"⚠️  [SOCIAL SCRAPE] Failed to scrape {prospect_to_update.profile_url}: {scrape_result.get('error')}")
                                        # Mark as attempted but failed
                                        prospect_to_update.scrape_status = "NO_EMAIL_FOUND"
                                        await scrape_db.commit()
                                except Exception as scrape_err:
                                    logger.error(f"❌ [SOCIAL SCRAPE] Error scraping profile {prospect.id}: {scrape_err}", exc_info=True)
                                    continue
                    except Exception as bg_err:
                        logger.error(f"❌ [SOCIAL SCRAPE] Background scraping error: {bg_err}", exc_info=True)
            
            # Start background scraping task
            from app.db.database import AsyncSessionLocal
            asyncio.create_task(scrape_profiles_background())
            logger.info(f"🚀 [SOCIAL PIPELINE STAGE 2] Started background scraping for {len(prospects)} profiles")
        
        logger.info(f"✅ [SOCIAL PIPELINE STAGE 2] Updated {updated_count} profiles: {request.action}")
        
        return {
            "success": True,
            "updated": updated_count,
            "action": request.action,
            "message": f"Updated {updated_count} profile(s) - {request.action}" + (" (scraping started in background)" if request.action == "qualify" else "")
        }
        
    except Exception as e:
        logger.error(f"❌ [SOCIAL PIPELINE STAGE 2] Error: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to review profiles: {str(e)}")


# ============================================
# STAGE 3: DRAFTING
# ============================================

class DraftRequest(BaseModel):
    profile_ids: Optional[List[UUID]] = None  # If None, auto-query all qualified profiles
    is_followup: bool = False


@router.post("/draft")
async def create_drafts(
    request: DraftRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    STAGE 3: Create drafts for social profiles.
    
    REUSES website drafting logic - filters by source_type='social'.
    Unlocked when qualified_count > 0.
    Drafts are saved to prospect.draft_body and prospect.draft_subject.
    
    If profile_ids provided, use those (manual selection).
    If profile_ids empty or not provided, query all qualified profiles automatically.
    """
    # Check master switch
    from app.api.scraper import check_master_switch
    master_enabled = await check_master_switch(db)
    if not master_enabled:
        raise HTTPException(
            status_code=403,
            detail="Master switch is disabled. Please enable it in Automation Control to run pipeline activities."
        )
    
    # Auto-query qualified profiles if profile_ids not provided
    social_filter = Prospect.source_type == 'social'
    
    if request.profile_ids is not None and len(request.profile_ids) > 0:
        # Manual selection: use provided profile_ids
        logger.info(f"📝 [SOCIAL PIPELINE STAGE 3] Creating drafts for {len(request.profile_ids)} manually selected profiles")
        result = await db.execute(
            select(Prospect).where(
                and_(
                    Prospect.id.in_(request.profile_ids),
                    social_filter,
                    Prospect.approval_status == 'approved'
                )
            )
        )
        prospects = result.scalars().all()
    else:
        # Auto-query: get all qualified (approved) social profiles that need drafting
        logger.info(f"📝 [SOCIAL PIPELINE STAGE 3] Auto-querying qualified profiles for drafting")
        result = await db.execute(
            select(Prospect).where(
                and_(
                    social_filter,
                    Prospect.approval_status == 'approved',
                    or_(
                        Prospect.draft_status.is_(None),
                        Prospect.draft_status == 'pending'
                    )
                )
            )
        )
        prospects = result.scalars().all()
    
    if len(prospects) == 0:
        raise HTTPException(
            status_code=400,
            detail="No qualified social profiles found. Profiles must be reviewed and approved before drafting."
        )
    
    logger.info(f"📝 [SOCIAL PIPELINE STAGE 3] Creating drafts for {len(prospects)} profiles")
    
    try:
        
        # Reuse website drafting task
        # Create a job for drafting
        from app.models import Job
        job = Job(
            job_type="social_draft",
            params={
                "prospect_ids": [str(p.id) for p in prospects],
                "is_followup": request.is_followup,
                "pipeline_mode": True
            },
            status="pending"
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        
        # Start drafting task (reuse existing drafting logic)
        from app.tasks.drafting import draft_prospects_async
        import asyncio
        from app.task_manager import register_task
        
        task = asyncio.create_task(draft_prospects_async(str(job.id)))
        register_task(str(job.id), task)
        
        logger.info(f"✅ [SOCIAL PIPELINE STAGE 3] Drafting job {job.id} started for {len(prospects)} profiles")
        
        return {
            "success": True,
            "job_id": job.id,
            "drafts_created": 0,  # Will be updated by task
            "message": f"Drafting job started for {len(prospects)} profiles"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [SOCIAL PIPELINE STAGE 3] Error: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create drafts: {str(e)}")


# ============================================
# STAGE 4: SENDING
# ============================================

class SendRequest(BaseModel):
    profile_ids: Optional[List[UUID]] = None  # If None, auto-query all send-ready profiles


@router.post("/send")
async def send_messages(
    request: SendRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    STAGE 4: Send messages to social profiles.
    
    REUSES website sending logic - filters by source_type='social'.
    Unlocked when drafted_count > 0.
    Requires draft to exist (draft_subject and draft_body).
    
    If profile_ids provided, use those (manual selection).
    If profile_ids empty or not provided, query all send-ready profiles automatically.
    """
    # Check master switch
    from app.api.scraper import check_master_switch
    master_enabled = await check_master_switch(db)
    if not master_enabled:
        raise HTTPException(
            status_code=403,
            detail="Master switch is disabled. Please enable it in Automation Control to run pipeline activities."
        )
    
    # Auto-query send-ready profiles if profile_ids not provided
    social_filter = Prospect.source_type == 'social'
    
    if request.profile_ids is not None and len(request.profile_ids) > 0:
        # Manual selection: use provided profile_ids
        logger.info(f"📧 [SOCIAL PIPELINE STAGE 4] Sending messages to {len(request.profile_ids)} manually selected profiles")
        result = await db.execute(
            select(Prospect).where(
                and_(
                    Prospect.id.in_(request.profile_ids),
                    social_filter,
                    Prospect.draft_status == 'drafted',
                    Prospect.draft_subject.isnot(None),
                    Prospect.draft_body.isnot(None)
                )
            )
        )
        prospects = result.scalars().all()
    else:
        # Auto-query: get all send-ready social profiles
        logger.info(f"📧 [SOCIAL PIPELINE STAGE 4] Auto-querying send-ready profiles")
        result = await db.execute(
            select(Prospect).where(
                and_(
                    social_filter,
                    Prospect.draft_status == 'drafted',
                    Prospect.draft_subject.isnot(None),
                    Prospect.draft_body.isnot(None),
                    or_(
                        Prospect.send_status.is_(None),
                        Prospect.send_status != 'sent'
                    )
                )
            )
        )
        prospects = result.scalars().all()
    
    if len(prospects) == 0:
        raise HTTPException(
            status_code=400,
            detail="No send-ready social profiles found. Profiles must be drafted before sending."
        )
    
    logger.info(f"📧 [SOCIAL PIPELINE STAGE 4] Sending messages to {len(prospects)} profiles")
    
    try:
        
        # Reuse website sending task
        from app.models import Job
        job = Job(
            job_type="social_send",
            params={
                "prospect_ids": [str(p.id) for p in prospects],
                "pipeline_mode": True
            },
            status="pending"
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        
        # Start sending task (reuse existing sending logic)
        from app.tasks.send import process_send_job
        import asyncio
        from app.task_manager import register_task
        
        task = asyncio.create_task(process_send_job(str(job.id)))
        register_task(str(job.id), task)
        
        logger.info(f"✅ [SOCIAL PIPELINE STAGE 4] Sending job {job.id} started for {len(prospects)} profiles")
        
        return {
            "success": True,
            "job_id": job.id,
            "messages_sent": 0,  # Will be updated by task
            "message": f"Sending job started for {len(prospects)} profiles"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [SOCIAL PIPELINE STAGE 4] Error: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to send messages: {str(e)}")


# ============================================
# STAGE 5: FOLLOW-UPS
# ============================================

@router.post("/followup")
async def create_followups(
    request: DraftRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    STAGE 5: Create follow-up drafts for social profiles that have sent messages.
    
    REUSES website follow-up logic - filters by source_type='social'.
    Unlocked when sent_count > 0.
    Automatically generates follow-up using Gemini (reuses website drafting).
    
    If profile_ids provided, use those (manual selection).
    If profile_ids empty or not provided, query all follow-up-ready profiles automatically.
    """
    # Check master switch
    from app.api.scraper import check_master_switch
    master_enabled = await check_master_switch(db)
    if not master_enabled:
        raise HTTPException(
            status_code=403,
            detail="Master switch is disabled. Please enable it in Automation Control to run pipeline activities."
        )
    
    # Auto-query follow-up-ready profiles if profile_ids not provided
    social_filter = Prospect.source_type == 'social'
    
    if request.profile_ids is not None and len(request.profile_ids) > 0:
        # Manual selection: use provided profile_ids
        logger.info(f"🔄 [SOCIAL PIPELINE STAGE 5] Creating follow-ups for {len(request.profile_ids)} manually selected profiles")
        result = await db.execute(
            select(Prospect).where(
                and_(
                    Prospect.id.in_(request.profile_ids),
                    social_filter,
                    Prospect.send_status == 'sent',
                    Prospect.last_sent.isnot(None)
                )
            )
        )
        prospects = result.scalars().all()
    else:
        # Auto-query: get all sent social profiles ready for follow-up
        logger.info(f"🔄 [SOCIAL PIPELINE STAGE 5] Auto-querying follow-up-ready profiles")
        result = await db.execute(
            select(Prospect).where(
                and_(
                    social_filter,
                    Prospect.send_status == 'sent',
                    Prospect.last_sent.isnot(None)
                )
            )
        )
        prospects = result.scalars().all()
    
    if len(prospects) == 0:
        raise HTTPException(
            status_code=400,
            detail="No sent social profiles found. Profiles must have sent messages before follow-ups."
        )
    
    logger.info(f"🔄 [SOCIAL PIPELINE STAGE 5] Creating follow-ups for {len(prospects)} profiles")
    
    try:
        
        # Reuse website drafting task with is_followup=True
        from app.models import Job
        job = Job(
            job_type="social_draft",
            params={
                "prospect_ids": [str(p.id) for p in prospects],
                "is_followup": True,
                "pipeline_mode": True
            },
            status="pending"
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        
        # Start drafting task (reuse existing drafting logic with follow-up mode)
        from app.tasks.drafting import draft_prospects_async
        import asyncio
        from app.task_manager import register_task
        
        task = asyncio.create_task(draft_prospects_async(str(job.id)))
        register_task(str(job.id), task)
        
        logger.info(f"✅ [SOCIAL PIPELINE STAGE 5] Follow-up drafting job {job.id} started for {len(prospects)} profiles")
        
        return {
            "success": True,
            "job_id": job.id,
            "followups_created": 0,  # Will be updated by task
            "message": f"Follow-up drafting job started for {len(prospects)} profiles"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [SOCIAL PIPELINE STAGE 5] Error: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create follow-ups: {str(e)}")

