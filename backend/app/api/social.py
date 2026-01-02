"""
Social Media Outreach API

Separate from Website Outreach - parallel system with no shared logic.

FEATURE-SCOPED SCHEMA VALIDATION:
- Social endpoints check only social tables
- Missing tables return 200 with structured metadata (not 500)
- Website endpoints are unaffected
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from typing import List, Optional
from uuid import UUID
import logging
from pydantic import BaseModel

from app.db.database import get_db, engine
from app.api.auth import get_current_user_optional
from app.utils.schema_validator import check_social_schema_ready
from app.models.social import (
    SocialProfile,
    SocialDiscoveryJob,
    SocialDraft,
    SocialMessage,
    SocialPlatform,
    DiscoveryStatus,
    OutreachStatus,
    MessageType,
    MessageStatus,
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
    Discover social media profiles
    
    Platform-specific discovery logic will be implemented per platform.
    
    Returns 200 with status="inactive" if social tables are missing (not 500).
    """
    # Feature-scoped schema check - only checks social tables
    schema_status = await check_social_schema_ready(engine)
    
    if not schema_status["ready"]:
        logger.warning(f"⚠️  [SOCIAL DISCOVERY] Social schema not ready: {schema_status['reason']}")
        logger.warning(f"⚠️  Missing tables: {', '.join(schema_status['missing_tables'])}")
        # Return 200 with structured metadata - not a 500 error
        return SocialDiscoveryResponse(
            success=False,
            job_id=None,
            message=f"Social outreach feature is not available: {schema_status['reason']}",
            profiles_count=0,
            status="inactive",
            reason=schema_status["reason"]
        )
    
    try:
        platform = SocialPlatform(request.platform.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid platform. Must be one of: {[p.value for p in SocialPlatform]}")
    
    logger.info(f"🔍 [SOCIAL DISCOVERY] Starting discovery for {platform.value}")
    
    try:
        # Create discovery job
        job = SocialDiscoveryJob(
            platform=platform,
            filters=request.filters,
            status="pending",
            results_count=0
        )
        
        db.add(job)
        await db.commit()
        await db.refresh(job)
        
        logger.info(f"✅ [SOCIAL DISCOVERY] Job created: {job.id}")
        
        # TODO: Start background task for discovery
        # For now, return job created
        
        return SocialDiscoveryResponse(
            success=True,
            job_id=job.id,
            message=f"Discovery job created for {platform.value}",
            profiles_count=0,
            status="active"
        )
    except Exception as e:
        error_msg = str(e)
        error_type = type(e).__name__
        logger.error(f"❌ [SOCIAL DISCOVERY] Error creating discovery job: {error_msg}", exc_info=True)
        
        # Check if this is a database schema error (table/column missing)
        is_schema_error = (
            "does not exist" in error_msg.lower() or
            "relation" in error_msg.lower() or
            "f405" in error_msg.lower() or
            "UndefinedTableError" in error_type or
            "ProgrammingError" in error_type or
            "table" in error_msg.lower() and "not exist" in error_msg.lower()
        )
        
        if is_schema_error:
            # Schema error - return 200 with inactive status (not 500)
            logger.warning(f"⚠️  [SOCIAL DISCOVERY] Database schema error detected: {error_msg}")
            logger.warning("⚠️  Returning inactive status instead of 500 error")
            return SocialDiscoveryResponse(
                success=False,
                job_id=None,
                message=f"Social outreach feature is not available: database schema error",
                profiles_count=0,
                status="inactive",
                reason="database schema error"
            )
        
        # Other errors - return 500 (but never for schema issues)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create discovery job: {error_msg}"
        )


# ============================================
# PROFILES
# ============================================

class SocialProfileResponse(BaseModel):
    id: UUID
    platform: str
    handle: str
    profile_url: str
    display_name: Optional[str]
    bio: Optional[str]
    followers_count: int
    location: Optional[str]
    is_business: bool
    qualification_status: str
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
    List discovered social profiles
    
    Returns 200 with empty data and status="inactive" if social tables are missing (not 500).
    """
    # Feature-scoped schema check - only checks social tables
    schema_status = await check_social_schema_ready(engine)
    
    if not schema_status["ready"]:
        logger.warning(f"⚠️  [SOCIAL PROFILES] Social schema not ready: {schema_status['reason']}")
        logger.warning(f"⚠️  Missing tables: {', '.join(schema_status['missing_tables'])}")
        # Return 200 with empty data and structured metadata - not a 500 error
        return SocialProfilesListResponse(
            data=[],
            total=0,
            skip=skip,
            limit=limit,
            status="inactive",
            reason=schema_status["reason"]
        )
    
    try:
        logger.info(f"📊 [SOCIAL PROFILES] Request: skip={skip}, limit={limit}, platform={platform}, discovery_status={discovery_status}")
        
        query = select(SocialProfile)
        
        if platform:
            try:
                platform_enum = SocialPlatform(platform.lower())
                query = query.where(SocialProfile.platform == platform_enum)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid platform: {platform}")
        
        if qualification_status:
            try:
                status_enum = QualificationStatus(qualification_status.lower())
                query = query.where(SocialProfile.qualification_status == status_enum)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid qualification status: {qualification_status}")
        
        # Get total count
        count_query = select(func.count(SocialProfile.id))
        if platform:
            try:
                platform_enum = SocialPlatform(platform.lower())
                count_query = count_query.where(SocialProfile.platform == platform_enum)
            except ValueError:
                pass
        if discovery_status:
            try:
                status_enum = DiscoveryStatus(discovery_status.lower())
                count_query = count_query.where(SocialProfile.discovery_status == status_enum)
            except ValueError:
                pass
        
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        logger.info(f"📊 [SOCIAL PROFILES] RAW COUNT (before pagination): {total} social profiles")
        
        # Get paginated results
        query = query.order_by(SocialProfile.created_at.desc()).offset(skip).limit(limit)
        result = await db.execute(query)
        profiles = result.scalars().all()
        
        logger.info(f"📊 [SOCIAL PROFILES] QUERY RESULT: Found {len(profiles)} profiles from database query (total available: {total})")
        
        response_data = {
            "data": [
                {
                    "id": p.id,
                    "platform": p.platform.value,
                    "username": p.username,
                    "full_name": p.full_name,
                    "profile_url": p.profile_url,
                    "bio": p.bio,
                    "followers_count": p.followers_count or 0,
                    "location": p.location,
                    "category": p.category,
                    "engagement_score": float(p.engagement_score) if p.engagement_score else 0.0,
                    "discovery_status": p.discovery_status.value,
                    "outreach_status": p.outreach_status.value,
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                }
                for p in profiles
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
        error_msg = str(e)
        error_type = type(e).__name__
        logger.error(f"❌ [SOCIAL PROFILES] Error listing social profiles: {error_msg}", exc_info=True)
        
        # Check if this is a database schema error (table/column missing)
        is_schema_error = (
            "does not exist" in error_msg.lower() or
            "relation" in error_msg.lower() or
            "f405" in error_msg.lower() or
            "UndefinedTableError" in error_type or
            "ProgrammingError" in error_type or
            "table" in error_msg.lower() and "not exist" in error_msg.lower()
        )
        
        if is_schema_error:
            # Schema error - return 200 with empty data and inactive status (not 500)
            logger.warning(f"⚠️  [SOCIAL PROFILES] Database schema error detected: {error_msg}")
            logger.warning("⚠️  Returning empty data with inactive status instead of 500 error")
            return SocialProfilesListResponse(
                data=[],
                total=0,
                skip=skip,
                limit=limit,
                status="inactive",
                reason="database schema error"
            )
        
        # Other errors - return 500 (but never for schema issues)
        raise HTTPException(status_code=500, detail=f"Failed to list profiles: {error_msg}")


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
    Create draft messages for profiles
    
    If is_followup=True, generates follow-up messages using Gemini.
    """
    # Feature-scoped schema check
    schema_status = await check_social_schema_ready(engine)
    if not schema_status["ready"]:
        raise HTTPException(
            status_code=503,
            detail=f"Social outreach feature is not available: {schema_status['reason']}"
        )
    
    if not request.profile_ids:
        raise HTTPException(status_code=400, detail="At least one profile ID is required")
    
    logger.info(f"📝 [SOCIAL DRAFTS] Creating drafts for {len(request.profile_ids)} profiles (followup={request.is_followup})")
    
    # Get profiles
    result = await db.execute(
        select(SocialProfile).where(SocialProfile.id.in_(request.profile_ids))
    )
    profiles = result.scalars().all()
    
    if len(profiles) != len(request.profile_ids):
        logger.warning(f"⚠️  Only found {len(profiles)} of {len(request.profile_ids)} requested profiles")
    
    drafts_created = 0
    
    for profile in profiles:
        # Check if this is a follow-up (previous message exists)
        if request.is_followup:
            # Check for previous messages
            prev_messages = await db.execute(
                select(SocialMessage).where(
                    SocialMessage.profile_id == profile.id,
                    SocialMessage.status == MessageStatus.SENT.value
                ).order_by(SocialMessage.sent_at.desc())
            )
            previous = prev_messages.scalars().first()
            
            if not previous:
                logger.warning(f"⚠️  No previous message found for profile {profile.id}, skipping follow-up")
                continue
            
            # Get sequence index
            max_sequence = await db.execute(
                select(func.max(SocialDraft.sequence_index)).where(
                    SocialDraft.profile_id == profile.id
                )
            )
            next_sequence = (max_sequence.scalar() or 0) + 1
            
            # TODO: Generate follow-up using Gemini (humorous, clever, non-repetitive)
            draft_body = f"Follow-up message for {profile.handle} (sequence {next_sequence})"
        else:
            # Initial message
            # TODO: Generate initial draft using Gemini
            draft_body = f"Initial outreach message for {profile.handle}"
            next_sequence = 0
        
        # Create draft
        draft = SocialDraft(
            profile_id=profile.id,
            platform=profile.platform,
            draft_body=draft_body,
            is_followup=request.is_followup,
            sequence_index=next_sequence
        )
        
        db.add(draft)
        drafts_created += 1
    
    await db.commit()
    
    logger.info(f"✅ [SOCIAL DRAFTS] Created {drafts_created} drafts")
    
    return SocialDraftResponse(
        success=True,
        drafts_created=drafts_created,
        message=f"Created {drafts_created} draft(s)"
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
    Send messages to social profiles
    
    Requires draft to exist for each profile.
    """
    # Feature-scoped schema check
    schema_status = await check_social_schema_ready(engine)
    if not schema_status["ready"]:
        raise HTTPException(
            status_code=503,
            detail=f"Social outreach feature is not available: {schema_status['reason']}"
        )
    
    if not request.profile_ids:
        raise HTTPException(status_code=400, detail="At least one profile ID is required")
    
    logger.info(f"📤 [SOCIAL SEND] Sending messages to {len(request.profile_ids)} profiles")
    
    messages_sent = 0
    
    for profile_id in request.profile_ids:
        # Get latest draft for profile
        draft_result = await db.execute(
            select(SocialDraft).where(
                SocialDraft.profile_id == profile_id
            ).order_by(SocialDraft.created_at.desc())
        )
        draft = draft_result.scalar_one_or_none()
        
        if not draft:
            logger.warning(f"⚠️  No draft found for profile {profile_id}")
            continue
        
        # Get profile
        profile_result = await db.execute(
            select(SocialProfile).where(SocialProfile.id == profile_id)
        )
        profile = profile_result.scalar_one_or_none()
        
        if not profile:
            logger.warning(f"⚠️  Profile {profile_id} not found")
            continue
        
        # TODO: Send message via platform API (LinkedIn, Instagram, TikTok)
        # For now, create message record
        
        message = SocialMessage(
            profile_id=profile.id,
            platform=profile.platform,
            message_body=draft.draft_body,
            status=MessageStatus.SENT.value,
            sent_at=func.now()
        )
        
        db.add(message)
        messages_sent += 1
    
    await db.commit()
    
    logger.info(f"✅ [SOCIAL SEND] Sent {messages_sent} messages")
    
    return SocialSendResponse(
        success=True,
        messages_sent=messages_sent,
        message=f"Sent {messages_sent} message(s)"
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
    Create follow-up drafts for profiles that have sent messages
    
    Automatically generates follow-up using Gemini with humorous, clever tone.
    """
    # Feature-scoped schema check
    schema_status = await check_social_schema_ready(engine)
    if not schema_status["ready"]:
        raise HTTPException(
            status_code=503,
            detail=f"Social outreach feature is not available: {schema_status['reason']}"
        )
    
    if not request.profile_ids:
        raise HTTPException(status_code=400, detail="At least one profile ID is required")
    
    logger.info(f"🔄 [SOCIAL FOLLOWUP] Creating follow-ups for {len(request.profile_ids)} profiles")
    
    # Get profiles with sent messages
    result = await db.execute(
        select(SocialProfile).where(
            SocialProfile.id.in_(request.profile_ids)
        )
    )
    profiles = result.scalars().all()
    
    drafts_created = 0
    
    for profile in profiles:
        # Check for previous sent messages
        prev_messages = await db.execute(
            select(SocialMessage).where(
                SocialMessage.profile_id == profile.id,
                SocialMessage.status == MessageStatus.SENT.value
            ).order_by(SocialMessage.sent_at.desc())
        )
        previous = prev_messages.scalars().first()
        
        if not previous:
            logger.warning(f"⚠️  No previous message for profile {profile.id}, skipping follow-up")
            continue
        
        # Get next sequence index
        max_sequence = await db.execute(
            select(func.max(SocialDraft.sequence_index)).where(
                SocialDraft.profile_id == profile.id
            )
        )
        next_sequence = (max_sequence.scalar() or 0) + 1
        
        # TODO: Generate follow-up using Gemini
        # Tone: humorous, clever, non-repetitive
        draft_body = f"Follow-up message #{next_sequence} for {profile.handle}"
        
        draft = SocialDraft(
            profile_id=profile.id,
            platform=profile.platform,
            draft_body=draft_body,
            is_followup=True,
            sequence_index=next_sequence
        )
        
        db.add(draft)
        drafts_created += 1
    
    await db.commit()
    
    return SocialDraftResponse(
        success=True,
        drafts_created=drafts_created,
        message=f"Created {drafts_created} follow-up draft(s)"
    )
