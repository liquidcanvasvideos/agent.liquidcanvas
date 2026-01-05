"""
Social Media Outreach API

REUSES Website Outreach tables - filters by source_type='social'.
All queries filter: Prospect.source_type == 'social'
"""
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from typing import List, Optional
from uuid import UUID
import logging
from pydantic import BaseModel
import csv
import io
from datetime import datetime

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

router = APIRouter(prefix="/api/social", tags=["social"])


# ============================================
# DISCOVERY
# ============================================

class SocialDiscoveryRequest(BaseModel):
    platform: str  # linkedin, instagram, tiktok
    filters: dict  # keywords, location, hashtags, etc.
    max_results: Optional[int] = 100


class SocialDiscoveryResponse(BaseModel):
    success: bool
    job_id: Optional[UUID] = None
    message: str
    profiles_count: int
    status: Optional[str] = None  # "active" | "inactive"
    reason: Optional[str] = None  # Explanation if inactive


@router.post("/discover", response_model=SocialDiscoveryResponse)
async def discover_profiles(
    request: SocialDiscoveryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Discover social media profiles using adapter pattern.
    
    REUSES prospects table - saves with source_type='social'.
    """
    # Validate platform
    platform = request.platform.lower()
    valid_platforms = ['linkedin', 'instagram', 'facebook', 'tiktok']
    if platform not in valid_platforms:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid platform. Must be one of: {valid_platforms}"
        )
    
    logger.info(f"🔍 [SOCIAL DISCOVERY] Starting discovery for {platform}")
    
    try:
        # Select adapter based on platform
        adapter_map = {
            'linkedin': LinkedInDiscoveryAdapter(),
            'instagram': InstagramDiscoveryAdapter(),
            'facebook': FacebookDiscoveryAdapter(),
            'tiktok': TikTokDiscoveryAdapter(),
        }
        
        adapter = adapter_map[platform]
        
        # Prepare adapter parameters
        adapter_params = {
            **request.filters,  # Platform-specific filters
            'max_results': request.max_results or 100
        }
        
        # Run discovery using adapter
        prospects = await adapter.discover(adapter_params, db)
        
        # Save prospects to database
        for prospect in prospects:
            prospect.source_type = 'social'
            prospect.source_platform = platform
            prospect.discovery_status = DiscoveryStatus.DISCOVERED.value
            prospect.approval_status = 'PENDING'
            prospect.scrape_status = 'DISCOVERED'
            db.add(prospect)
        
        await db.commit()
        
        logger.info(f"✅ [SOCIAL DISCOVERY] Discovered {len(prospects)} profiles for {platform}")
        
        # Create a job record (using existing Job model)
        from app.models import Job
        job = Job(
            job_type="social_discover",
            params={
                "platform": platform,
                "filters": request.filters,
                "prospects_count": len(prospects)
            },
            status="completed",
            result={"prospects_count": len(prospects)}
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        
        return SocialDiscoveryResponse(
            success=True,
            job_id=job.id,
            message=f"Discovered {len(prospects)} profiles for {platform}",
            profiles_count=len(prospects),
            status="active"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [SOCIAL DISCOVERY] Error: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to discover profiles: {str(e)}")


# ============================================
# PROFILES
# ============================================

class SocialProfileResponse(BaseModel):
    id: UUID
    platform: str
    username: str
    full_name: Optional[str]
    profile_url: str
    bio: Optional[str]
    followers_count: int
    location: Optional[str]
    category: Optional[str]
    engagement_score: float
    discovery_status: str
    outreach_status: str
    created_at: str


class SocialProfilesListResponse(BaseModel):
    data: List[dict]
    total: int
    skip: int
    limit: int
    status: Optional[str] = None  # "active" | "inactive"
    reason: Optional[str] = None  # Explanation if inactive


@router.get("/profiles")
async def list_profiles(
    skip: int = 0,
    limit: int = 50,
    platform: Optional[str] = None,
    discovery_status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    List discovered social profiles.
    
    REUSES prospects table - filters by source_type='social'.
    """
    try:
        logger.info(f"📊 [SOCIAL PROFILES] Request: skip={skip}, limit={limit}, platform={platform}, discovery_status={discovery_status}")
        
        # CRITICAL: Check if source_type column exists before using it
        column_exists = False
        try:
            from sqlalchemy import text
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
            logger.warning(f"⚠️  [SOCIAL PROFILES] Could not check for source_type column: {check_err}")
            column_exists = False
        
        if not column_exists:
            logger.warning("⚠️  [SOCIAL PROFILES] source_type column does not exist - migration not applied")
            logger.warning("⚠️  [SOCIAL PROFILES] Returning empty list - migration add_social_columns_to_prospects needs to run")
            return {
                "data": [],
                "total": 0,
                "skip": skip,
                "limit": limit,
                "status": "inactive",
                "message": "Social outreach columns not initialized. Please run migration: alembic upgrade head"
            }
        
        # Base filter: only social prospects
        query = select(Prospect).where(Prospect.source_type == 'social')
        count_query = select(func.count(Prospect.id)).where(Prospect.source_type == 'social')
        
        if platform:
            platform_lower = platform.lower()
            valid_platforms = ['linkedin', 'instagram', 'facebook', 'tiktok']
            if platform_lower not in valid_platforms:
                raise HTTPException(status_code=400, detail=f"Invalid platform: {platform}")
            query = query.where(Prospect.source_platform == platform_lower)
            count_query = count_query.where(Prospect.source_platform == platform_lower)
        
        if discovery_status:
            # Special handling for 'discovered' and 'leads' statuses
            if discovery_status.lower() == 'discovered':
                # Show only PENDING profiles (needs accept/reject)
                query = query.where(
                    and_(
                        Prospect.discovery_status == DiscoveryStatus.DISCOVERED.value,
                        Prospect.approval_status == 'PENDING'
                    )
                )
                count_query = count_query.where(
                    and_(
                        Prospect.discovery_status == DiscoveryStatus.DISCOVERED.value,
                        Prospect.approval_status == 'PENDING'
                    )
                )
            elif discovery_status.lower() == 'leads' or discovery_status.lower() == 'approved':
                # Show only approved profiles (Social Leads)
                query = query.where(
                    and_(
                        Prospect.discovery_status == DiscoveryStatus.DISCOVERED.value,
                        Prospect.approval_status == 'approved'
                    )
                )
                count_query = count_query.where(
                    and_(
                        Prospect.discovery_status == DiscoveryStatus.DISCOVERED.value,
                        Prospect.approval_status == 'approved'
                    )
                )
            else:
                # Map discovery_status to Prospect.discovery_status
                query = query.where(Prospect.discovery_status == discovery_status.upper())
                count_query = count_query.where(Prospect.discovery_status == discovery_status.upper())
        
        # Get total count
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        logger.info(f"📊 [SOCIAL PROFILES] RAW COUNT (before pagination): {total} social profiles")
        
        # Get paginated results
        query = query.order_by(Prospect.created_at.desc()).offset(skip).limit(limit)
        result = await db.execute(query)
        prospects = result.scalars().all()
        
        logger.info(f"📊 [SOCIAL PROFILES] QUERY RESULT: Found {len(prospects)} profiles from database query (total available: {total})")
        
        response_data = {
            "data": [
                {
                    "id": str(p.id),
                    "platform": p.source_platform or "",
                    "username": p.username or "",
                    "full_name": p.display_name or "",
                    "profile_url": p.profile_url or "",
                    "bio": p.page_title or "",  # Use page_title for bio
                    "followers_count": p.follower_count or 0,
                    "location": p.discovery_location or "",
                    "category": p.discovery_category or "",
                    "engagement_score": float(p.engagement_rate) if p.engagement_rate else 0.0,
                    "discovery_status": p.discovery_status or "DISCOVERED",
                    "outreach_status": p.outreach_status or "pending",
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                }
                for p in prospects
            ],
            "total": total,
            "skip": skip,
            "limit": limit,
            "status": "active"
        }
        
        logger.info(f"✅ [SOCIAL PROFILES] Returning {len(response_data['data'])} profiles (total: {total})")
        return response_data
    except HTTPException:
        raise
    except Exception as e:
        # Check if error is related to missing column
        error_str = str(e).lower()
        if 'source_type' in error_str or 'column' in error_str or 'does not exist' in error_str or 'undefinedcolumn' in error_str:
            logger.warning(f"⚠️  [SOCIAL PROFILES] Database schema error (likely missing columns): {e}")
            logger.warning("⚠️  [SOCIAL PROFILES] Returning empty list instead of 500")
            return {
                "data": [],
                "total": 0,
                "skip": skip,
                "limit": limit,
                "status": "inactive",
                "message": "Social outreach columns not initialized. Please run migration: alembic upgrade head"
            }
        else:
            # For other errors, still return safe response but log the error
            logger.error(f"❌ [SOCIAL PROFILES] Unexpected error listing profiles: {e}", exc_info=True)
            return {
                "data": [],
                "total": 0,
                "skip": skip,
                "limit": limit,
                "status": "inactive",
                "message": f"Failed to list profiles: {str(e)}. Please check backend logs."
            }


# ============================================
# STATS
# ============================================

@router.get("/stats")
async def get_social_stats(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Get social outreach statistics.
    
    Returns platform-specific counts and overall stats.
    Filters by source_type='social'.
    """
    try:
        # Check if source_type column exists
        column_exists = False
        try:
            from sqlalchemy import text
            column_check = await db.execute(
                text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'prospects' 
                    AND column_name = 'source_type'
                """)
            )
            column_exists = column_check.fetchone() is not None
        except Exception:
            column_exists = False
        
        if not column_exists:
            # Return empty stats if column doesn't exist
            return {
                "total_profiles": 0,
                "discovered": 0,
                "drafted": 0,
                "sent": 0,
                "pending": 0,
                "jobs_running": 0,
                "linkedin_total": 0,
                "linkedin_discovered": 0,
                "linkedin_drafted": 0,
                "linkedin_sent": 0,
                "instagram_total": 0,
                "instagram_discovered": 0,
                "instagram_drafted": 0,
                "instagram_sent": 0,
                "facebook_total": 0,
                "facebook_discovered": 0,
                "facebook_drafted": 0,
                "facebook_sent": 0,
                "tiktok_total": 0,
                "tiktok_discovered": 0,
                "tiktok_drafted": 0,
                "tiktok_sent": 0,
            }
        
        # Base filter: only social prospects
        social_filter = Prospect.source_type == 'social'
        
        # Overall counts
        total_profiles = await db.execute(
            select(func.count(Prospect.id)).where(social_filter)
        )
        total_profiles_count = total_profiles.scalar() or 0
        
        discovered = await db.execute(
            select(func.count(Prospect.id)).where(
                and_(social_filter, Prospect.discovery_status == DiscoveryStatus.DISCOVERED.value)
            )
        )
        discovered_count = discovered.scalar() or 0
        
        drafted = await db.execute(
            select(func.count(Prospect.id)).where(
                and_(social_filter, Prospect.draft_status == 'drafted')
            )
        )
        drafted_count = drafted.scalar() or 0
        
        sent = await db.execute(
            select(func.count(Prospect.id)).where(
                and_(social_filter, Prospect.send_status == 'sent')
            )
        )
        sent_count = sent.scalar() or 0
        
        pending = await db.execute(
            select(func.count(Prospect.id)).where(
                and_(social_filter, Prospect.outreach_status == 'pending')
            )
        )
        pending_count = pending.scalar() or 0
        
        # Platform-specific counts
        platforms = ['linkedin', 'instagram', 'facebook', 'tiktok']
        platform_stats = {}
        
        for platform in platforms:
            platform_filter = and_(
                social_filter,
                Prospect.source_platform == platform
            )
            
            platform_total = await db.execute(
                select(func.count(Prospect.id)).where(platform_filter)
            )
            platform_stats[f"{platform}_total"] = platform_total.scalar() or 0
            
            platform_discovered = await db.execute(
                select(func.count(Prospect.id)).where(
                    and_(platform_filter, Prospect.discovery_status == DiscoveryStatus.DISCOVERED.value)
                )
            )
            platform_stats[f"{platform}_discovered"] = platform_discovered.scalar() or 0
            
            platform_drafted = await db.execute(
                select(func.count(Prospect.id)).where(
                    and_(platform_filter, Prospect.draft_status == 'drafted')
                )
            )
            platform_stats[f"{platform}_drafted"] = platform_drafted.scalar() or 0
            
            platform_sent = await db.execute(
                select(func.count(Prospect.id)).where(
                    and_(platform_filter, Prospect.send_status == 'sent')
                )
            )
            platform_stats[f"{platform}_sent"] = platform_sent.scalar() or 0
        
        # Count running jobs (social-related)
        from app.models.job import Job
        running_jobs = await db.execute(
            select(func.count(Job.id)).where(
                and_(
                    Job.status.in_(['pending', 'running']),
                    Job.job_type.in_(['social_discover', 'social_draft', 'social_send'])
                )
            )
        )
        jobs_running_count = running_jobs.scalar() or 0
        
        return {
            "total_profiles": total_profiles_count,
            "discovered": discovered_count,
            "drafted": drafted_count,
            "sent": sent_count,
            "pending": pending_count,
            "jobs_running": jobs_running_count,
            **platform_stats
        }
        
    except Exception as e:
        logger.error(f"❌ [SOCIAL STATS] Error computing stats: {e}", exc_info=True)
        # Return empty stats on error
        return {
            "total_profiles": 0,
            "discovered": 0,
            "drafted": 0,
            "sent": 0,
            "pending": 0,
            "jobs_running": 0,
            "linkedin_total": 0,
            "linkedin_discovered": 0,
            "linkedin_drafted": 0,
            "linkedin_sent": 0,
            "instagram_total": 0,
            "instagram_discovered": 0,
            "instagram_drafted": 0,
            "instagram_sent": 0,
            "facebook_total": 0,
            "facebook_discovered": 0,
            "facebook_drafted": 0,
            "facebook_sent": 0,
            "tiktok_total": 0,
            "tiktok_discovered": 0,
            "tiktok_drafted": 0,
            "tiktok_sent": 0,
        }


# ============================================
# DRAFTS
# ============================================

class SocialDraftRequest(BaseModel):
    profile_ids: List[UUID]
    is_followup: bool = False


class SocialDraftResponse(BaseModel):
    success: bool
    drafts_created: int
    message: str


@router.post("/drafts", response_model=SocialDraftResponse)
async def create_drafts(
    request: SocialDraftRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Create draft messages for social profiles.
    
    REUSES website drafting logic - filters by source_type='social'.
    If is_followup=True, generates follow-up messages using Gemini.
    """
    if not request.profile_ids:
        raise HTTPException(status_code=400, detail="At least one profile ID is required")
    
    logger.info(f"📝 [SOCIAL DRAFTS] Creating drafts for {len(request.profile_ids)} profiles")
    
    # Reuse website drafting task
    from app.models import Job
    job = Job(
        job_type="social_draft",
        params={
            "prospect_ids": [str(pid) for pid in request.profile_ids],
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
    
    logger.info(f"✅ [SOCIAL DRAFTS] Drafting job {job.id} started")
    
    return SocialDraftResponse(
        success=True,
        drafts_created=0,  # Will be updated by task
        message=f"Drafting job started for {len(request.profile_ids)} profiles"
    )


# ============================================
# SEND
# ============================================

class SocialSendRequest(BaseModel):
    profile_ids: List[UUID]


class SocialSendResponse(BaseModel):
    success: bool
    messages_sent: int
    message: str


@router.post("/send", response_model=SocialSendResponse)
async def send_messages(
    request: SocialSendRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Send messages to social profiles.
    
    REUSES website sending logic - filters by source_type='social'.
    Requires draft to exist (draft_subject and draft_body).
    """
    if not request.profile_ids:
        raise HTTPException(status_code=400, detail="At least one profile ID is required")
    
    logger.info(f"📤 [SOCIAL SEND] Sending messages to {len(request.profile_ids)} profiles")
    
    # Reuse website sending task
    from app.models import Job
    job = Job(
        job_type="social_send",
        params={
            "prospect_ids": [str(pid) for pid in request.profile_ids],
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
    
    logger.info(f"✅ [SOCIAL SEND] Sending job {job.id} started")
    
    return SocialSendResponse(
        success=True,
        messages_sent=0,  # Will be updated by task
        message=f"Sending job started for {len(request.profile_ids)} profiles"
    )


# ============================================
# FOLLOW-UP
# ============================================

@router.post("/followup", response_model=SocialDraftResponse)
async def create_followups(
    request: SocialDraftRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Create follow-up drafts for social profiles that have sent messages.
    
    REUSES website follow-up logic - filters by source_type='social'.
    Automatically generates follow-up using Gemini (reuses website drafting).
    """
    if not request.profile_ids:
        raise HTTPException(status_code=400, detail="At least one profile ID is required")
    
    logger.info(f"🔄 [SOCIAL FOLLOWUP] Creating follow-ups for {len(request.profile_ids)} profiles")
    
    # Reuse website drafting task with is_followup=True
    from app.models import Job
    job = Job(
        job_type="social_draft",
        params={
            "prospect_ids": [str(pid) for pid in request.profile_ids],
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
    
    logger.info(f"✅ [SOCIAL FOLLOWUP] Follow-up drafting job {job.id} started")
    
    return SocialDraftResponse(
        success=True,
        drafts_created=0,  # Will be updated by task
        message=f"Follow-up drafting job started for {len(request.profile_ids)} profiles"
    )


# ============================================
# DRAFTED PROFILES
# ============================================

@router.get("/drafts")
async def list_drafted_profiles(
    skip: int = 0,
    limit: int = 50,
    platform: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    List drafted social profiles.
    
    REUSES prospects table - filters by source_type='social' AND draft_status='drafted'.
    """
    try:
        # Check if source_type column exists
        column_exists = False
        try:
            from sqlalchemy import text
            column_check = await db.execute(
                text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'prospects' 
                    AND column_name = 'source_type'
                """)
            )
            column_exists = column_check.fetchone() is not None
        except Exception:
            column_exists = False
        
        if not column_exists:
            return {
                "data": [],
                "total": 0,
                "skip": skip,
                "limit": limit,
                "status": "inactive",
                "message": "Social outreach columns not initialized"
            }
        
        # Base filter: social AND drafted
        query = select(Prospect).where(
            and_(
                Prospect.source_type == 'social',
                Prospect.draft_status == 'drafted',
                Prospect.draft_subject.isnot(None),
                Prospect.draft_body.isnot(None)
            )
        )
        count_query = select(func.count(Prospect.id)).where(
            and_(
                Prospect.source_type == 'social',
                Prospect.draft_status == 'drafted',
                Prospect.draft_subject.isnot(None),
                Prospect.draft_body.isnot(None)
            )
        )
        
        if platform:
            platform_lower = platform.lower()
            query = query.where(Prospect.source_platform == platform_lower)
            count_query = count_query.where(Prospect.source_platform == platform_lower)
        
        # Get total count
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        # Get paginated results
        query = query.order_by(Prospect.created_at.desc()).offset(skip).limit(limit)
        result = await db.execute(query)
        prospects = result.scalars().all()
        
        return {
            "data": [
                {
                    "id": str(p.id),
                    "platform": p.source_platform or "",
                    "username": p.username or "",
                    "full_name": p.display_name or "",
                    "profile_url": p.profile_url or "",
                    "bio": p.page_title or "",
                    "followers_count": p.follower_count or 0,
                    "location": p.discovery_location or "",
                    "category": p.discovery_category or "",
                    "engagement_score": float(p.engagement_rate) if p.engagement_rate else 0.0,
                    "draft_subject": p.draft_subject or "",
                    "draft_body": p.draft_body or "",
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                    "updated_at": p.updated_at.isoformat() if p.updated_at else None,
                }
                for p in prospects
            ],
            "total": total,
            "skip": skip,
            "limit": limit,
            "status": "active"
        }
    except Exception as e:
        logger.error(f"❌ [SOCIAL DRAFTS] Error listing drafted profiles: {e}", exc_info=True)
        return {
            "data": [],
            "total": 0,
            "skip": skip,
            "limit": limit,
            "status": "inactive",
            "message": f"Failed to list drafted profiles: {str(e)}"
        }


# ============================================
# SENT PROFILES
# ============================================

@router.get("/sent")
async def list_sent_profiles(
    skip: int = 0,
    limit: int = 50,
    platform: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    List sent social profiles.
    
    REUSES prospects table - filters by source_type='social' AND send_status='sent'.
    """
    try:
        # Check if source_type column exists
        column_exists = False
        try:
            from sqlalchemy import text
            column_check = await db.execute(
                text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'prospects' 
                    AND column_name = 'source_type'
                """)
            )
            column_exists = column_check.fetchone() is not None
        except Exception:
            column_exists = False
        
        if not column_exists:
            return {
                "data": [],
                "total": 0,
                "skip": skip,
                "limit": limit,
                "status": "inactive",
                "message": "Social outreach columns not initialized"
            }
        
        # Base filter: social AND sent
        query = select(Prospect).where(
            and_(
                Prospect.source_type == 'social',
                Prospect.send_status == 'sent'
            )
        )
        count_query = select(func.count(Prospect.id)).where(
            and_(
                Prospect.source_type == 'social',
                Prospect.send_status == 'sent'
            )
        )
        
        if platform:
            platform_lower = platform.lower()
            query = query.where(Prospect.source_platform == platform_lower)
            count_query = count_query.where(Prospect.source_platform == platform_lower)
        
        # Get total count
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        # Get paginated results
        query = query.order_by(Prospect.last_sent.desc() if hasattr(Prospect, 'last_sent') else Prospect.created_at.desc()).offset(skip).limit(limit)
        result = await db.execute(query)
        prospects = result.scalars().all()
        
        return {
            "data": [
                {
                    "id": str(p.id),
                    "platform": p.source_platform or "",
                    "username": p.username or "",
                    "full_name": p.display_name or "",
                    "profile_url": p.profile_url or "",
                    "bio": p.page_title or "",
                    "followers_count": p.follower_count or 0,
                    "location": p.discovery_location or "",
                    "category": p.discovery_category or "",
                    "engagement_score": float(p.engagement_rate) if p.engagement_rate else 0.0,
                    "draft_subject": getattr(p, 'draft_subject', None) or "",
                    "draft_body": getattr(p, 'draft_body', None) or "",
                    "last_sent": p.last_sent.isoformat() if getattr(p, 'last_sent', None) else None,
                    "followups_sent": getattr(p, 'followups_sent', 0) or 0,
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                }
                for p in prospects
            ],
            "total": total,
            "skip": skip,
            "limit": limit,
            "status": "active"
        }
    except Exception as e:
        logger.error(f"❌ [SOCIAL SENT] Error listing sent profiles: {e}", exc_info=True)
        return {
            "data": [],
            "total": 0,
            "skip": skip,
            "limit": limit,
                "status": "inactive",
                "message": f"Failed to list sent profiles: {str(e)}"
            }


# ============================================
# CSV EXPORT
# ============================================

@router.get("/profiles/export/csv")
async def export_profiles_csv(
    platform: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Export social profiles to CSV.
    
    Query params:
    - platform: Filter by platform (linkedin, instagram, facebook, tiktok)
    
    Returns CSV file with all matching profiles (no pagination limit).
    """
    try:
        # Check if source_type column exists
        column_exists = False
        try:
            from sqlalchemy import text
            column_check = await db.execute(
                text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'prospects' 
                    AND column_name = 'source_type'
                """)
            )
            column_exists = column_check.fetchone() is not None
        except Exception:
            column_exists = False
        
        if not column_exists:
            raise HTTPException(status_code=400, detail="Social outreach columns not initialized")
        
        query = select(Prospect).where(Prospect.source_type == 'social')
        
        if platform:
            platform_lower = platform.lower()
            query = query.where(Prospect.source_platform == platform_lower)
        
        result = await db.execute(query.order_by(Prospect.created_at.desc()))
        prospects = result.scalars().all()
        
        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow([
            'ID', 'Platform', 'Username', 'Display Name', 'Profile URL',
            'Bio', 'Followers', 'Location', 'Category', 'Engagement Rate',
            'Discovery Status', 'Outreach Status', 'Created At'
        ])
        
        for p in prospects:
            writer.writerow([
                str(p.id),
                p.source_platform or '',
                p.username or '',
                p.display_name or '',
                p.profile_url or '',
                p.page_title or '',
                p.follower_count or 0,
                p.discovery_location or '',
                p.discovery_category or '',
                float(p.engagement_rate) if p.engagement_rate else 0,
                p.discovery_status or 'DISCOVERED',
                p.outreach_status or 'pending',
                p.created_at.isoformat() if p.created_at else ''
            ])
        
        csv_content = output.getvalue()
        output.close()
        
        filename = f"social_profiles_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [CSV EXPORT PROFILES] Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to export profiles CSV: {str(e)}")


@router.get("/drafts/export/csv")
async def export_drafts_csv(
    platform: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Export drafted social profiles to CSV.
    """
    try:
        column_exists = False
        try:
            from sqlalchemy import text
            column_check = await db.execute(
                text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'prospects' 
                    AND column_name = 'source_type'
                """)
            )
            column_exists = column_check.fetchone() is not None
        except Exception:
            column_exists = False
        
        if not column_exists:
            raise HTTPException(status_code=400, detail="Social outreach columns not initialized")
        
        query = select(Prospect).where(
            and_(
                Prospect.source_type == 'social',
                Prospect.draft_status == 'drafted',
                Prospect.draft_subject.isnot(None),
                Prospect.draft_body.isnot(None)
            )
        )
        
        if platform:
            query = query.where(Prospect.source_platform == platform.lower())
        
        result = await db.execute(query.order_by(Prospect.created_at.desc()))
        prospects = result.scalars().all()
        
        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow([
            'ID', 'Platform', 'Username', 'Display Name', 'Profile URL',
            'Draft Subject', 'Draft Body', 'Created At', 'Updated At'
        ])
        
        for p in prospects:
            writer.writerow([
                str(p.id),
                p.source_platform or '',
                p.username or '',
                p.display_name or '',
                p.profile_url or '',
                p.draft_subject or '',
                p.draft_body or '',
                p.created_at.isoformat() if p.created_at else '',
                p.updated_at.isoformat() if p.updated_at else ''
            ])
        
        csv_content = output.getvalue()
        output.close()
        
        filename = f"social_drafts_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [CSV EXPORT DRAFTS] Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to export drafts CSV: {str(e)}")


@router.get("/sent/export/csv")
async def export_sent_csv(
    platform: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Export sent social profiles to CSV.
    """
    try:
        column_exists = False
        try:
            from sqlalchemy import text
            column_check = await db.execute(
                text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'prospects' 
                    AND column_name = 'source_type'
                """)
            )
            column_exists = column_check.fetchone() is not None
        except Exception:
            column_exists = False
        
        if not column_exists:
            raise HTTPException(status_code=400, detail="Social outreach columns not initialized")
        
        query = select(Prospect).where(
            and_(
                Prospect.source_type == 'social',
                Prospect.send_status == 'sent'
            )
        )
        
        if platform:
            query = query.where(Prospect.source_platform == platform.lower())
        
        result = await db.execute(query.order_by(Prospect.last_sent.desc() if hasattr(Prospect, 'last_sent') else Prospect.created_at.desc()))
        prospects = result.scalars().all()
        
        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow([
            'ID', 'Platform', 'Username', 'Display Name', 'Profile URL',
            'Draft Subject', 'Draft Body', 'Last Sent', 'Follow-ups Sent', 'Created At'
        ])
        
        for p in prospects:
            writer.writerow([
                str(p.id),
                p.source_platform or '',
                p.username or '',
                p.display_name or '',
                p.profile_url or '',
                getattr(p, 'draft_subject', None) or '',
                getattr(p, 'draft_body', None) or '',
                p.last_sent.isoformat() if getattr(p, 'last_sent', None) else '',
                getattr(p, 'followups_sent', 0) or 0,
                p.created_at.isoformat() if p.created_at else ''
            ])
        
        csv_content = output.getvalue()
        output.close()
        
        filename = f"social_sent_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [CSV EXPORT SENT] Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to export sent CSV: {str(e)}")


# ============================================
# DRAFT UPDATE
# ============================================

class DraftUpdateRequest(BaseModel):
    subject: Optional[str] = None
    body: Optional[str] = None


@router.put("/profiles/{profile_id}/draft")
async def update_profile_draft(
    profile_id: UUID,
    draft: DraftUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Update draft for a social profile.
    
    Allows manual editing of draft_subject and draft_body.
    """
    try:
        result = await db.execute(
            select(Prospect).where(
                and_(
                    Prospect.id == profile_id,
                    Prospect.source_type == 'social'
                )
            )
        )
        prospect = result.scalar_one_or_none()
        
        if not prospect:
            raise HTTPException(status_code=404, detail="Profile not found")
        
        if draft.subject is not None:
            prospect.draft_subject = draft.subject
        if draft.body is not None:
            prospect.draft_body = draft.body
        
        prospect.draft_status = 'drafted'
        
        await db.commit()
        
        return {
            "success": True,
            "message": "Draft updated successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [SOCIAL DRAFT UPDATE] Error: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update draft: {str(e)}")
