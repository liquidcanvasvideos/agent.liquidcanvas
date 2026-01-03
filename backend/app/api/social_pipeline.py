"""
Social Outreach Pipeline API

COMPLETELY SEPARATE from Website Outreach Pipeline.
Stage-based progression for social media outreach.

Pipeline Stages:
1. Discovery - Always unlocked
2. Profile Review - Unlocked when discovered_count > 0
3. Drafting - Unlocked when qualified_count > 0
4. Sending - Unlocked when drafted_count > 0
5. Follow-ups - Unlocked when sent_count > 0
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
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
    DiscoveryJobStatus,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/social/pipeline", tags=["social-pipeline"])


# ============================================
# PIPELINE STATUS
# ============================================

@router.get("/status")
async def get_social_pipeline_status(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Get social pipeline status.
    
    Computes counts from social tables ONLY.
    Completely separate from website pipeline status.
    
    Returns:
        {
            "discovered": int,      # discovery_status = 'discovered'
            "reviewed": int,        # discovery_status = 'reviewed'
            "qualified": int,       # discovery_status = 'qualified'
            "drafted": int,         # outreach_status = 'drafted'
            "sent": int,            # outreach_status = 'sent'
            "followup_ready": int,  # sent AND last_contacted_at < threshold
        }
    """
    # Feature-scoped schema check
    schema_status = await check_social_schema_ready(engine)
    if not schema_status["ready"]:
        logger.warning("⚠️  [SOCIAL PIPELINE] Social schema not ready - returning empty status")
        return {
            "discovered": 0,
            "reviewed": 0,
            "qualified": 0,
            "drafted": 0,
            "sent": 0,
            "followup_ready": 0,
            "status": "inactive",
            "reason": schema_status["reason"]
        }
    
    try:
        # Count discovered profiles
        discovered_result = await db.execute(
            select(func.count(SocialProfile.id)).where(
                SocialProfile.discovery_status == DiscoveryStatus.DISCOVERED.value
            )
        )
        discovered_count = discovered_result.scalar() or 0
        
        # Count reviewed profiles
        reviewed_result = await db.execute(
            select(func.count(SocialProfile.id)).where(
                SocialProfile.discovery_status == DiscoveryStatus.REVIEWED.value
            )
        )
        reviewed_count = reviewed_result.scalar() or 0
        
        # Count qualified profiles
        qualified_result = await db.execute(
            select(func.count(SocialProfile.id)).where(
                SocialProfile.discovery_status == DiscoveryStatus.QUALIFIED.value
            )
        )
        qualified_count = qualified_result.scalar() or 0
        
        # Count drafted profiles
        drafted_result = await db.execute(
            select(func.count(SocialProfile.id)).where(
                SocialProfile.outreach_status == OutreachStatus.DRAFTED.value
            )
        )
        drafted_count = drafted_result.scalar() or 0
        
        # Count sent profiles
        sent_result = await db.execute(
            select(func.count(SocialProfile.id)).where(
                SocialProfile.outreach_status == OutreachStatus.SENT.value
            )
        )
        sent_count = sent_result.scalar() or 0
        
        # Count follow-up ready profiles (sent AND last_contacted_at > 7 days ago)
        from datetime import datetime, timezone, timedelta
        followup_threshold = datetime.now(timezone.utc) - timedelta(days=7)
        
        followup_ready_result = await db.execute(
            select(func.count(SocialProfile.id)).where(
                and_(
                    SocialProfile.outreach_status == OutreachStatus.SENT.value,
                    or_(
                        SocialProfile.last_contacted_at.is_(None),
                        SocialProfile.last_contacted_at < followup_threshold
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
            "status": "active"
        }
        
    except Exception as e:
        logger.error(f"❌ [SOCIAL PIPELINE] Error computing status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to compute pipeline status: {str(e)}")


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
    STAGE 1: Discover social profiles.
    
    Always unlocked - this is the entry point.
    Creates a discovery job and starts background processing.
    """
    # Feature-scoped schema check
    schema_status = await check_social_schema_ready(engine)
    if not schema_status["ready"]:
        raise HTTPException(
            status_code=503,
            detail=f"Social outreach feature is not available: {schema_status['reason']}"
        )
    
    # Validate platform
    try:
        platform = SocialPlatform(request.platform.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid platform. Must be one of: {[p.value for p in SocialPlatform]}"
        )
    
    # Validate required fields
    if not request.categories:
        raise HTTPException(status_code=400, detail="At least one category is required")
    if not request.locations:
        raise HTTPException(status_code=400, detail="At least one location is required")
    
    logger.info(f"🔍 [SOCIAL PIPELINE STAGE 1] Discovery request for {platform.value}")
    
    try:
        # Create discovery job
        job = SocialDiscoveryJob(
            platform=platform,
            categories=request.categories,
            locations=request.locations,
            keywords=request.keywords,
            parameters=request.parameters,
            status=DiscoveryJobStatus.PENDING.value,
            results_count=0
        )
        
        db.add(job)
        await db.commit()
        await db.refresh(job)
        
        logger.info(f"✅ [SOCIAL PIPELINE STAGE 1] Discovery job created: {job.id}")
        
        # Start background task
        from fastapi import BackgroundTasks
        from app.tasks.social_discovery import process_social_discovery_job
        
        # Note: BackgroundTasks needs to be injected, but we'll handle it in the API call
        # For now, we'll use asyncio.create_task
        import asyncio
        asyncio.create_task(process_social_discovery_job(str(job.id)))
        
        return SocialDiscoveryResponse(
            success=True,
            job_id=job.id,
            message=f"Discovery job created for {platform.value}",
            profiles_count=0
        )
        
    except Exception as e:
        logger.error(f"❌ [SOCIAL PIPELINE STAGE 1] Error: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create discovery job: {str(e)}")


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
    STAGE 2: Review and qualify/reject profiles.
    
    Unlocked when discovered_count > 0.
    Manual review step - user decides which profiles to qualify.
    """
    # Feature-scoped schema check
    schema_status = await check_social_schema_ready(engine)
    if not schema_status["ready"]:
        raise HTTPException(
            status_code=503,
            detail=f"Social outreach feature is not available: {schema_status['reason']}"
        )
    
    if request.action not in ["qualify", "reject"]:
        raise HTTPException(status_code=400, detail="Action must be 'qualify' or 'reject'")
    
    if not request.profile_ids:
        raise HTTPException(status_code=400, detail="At least one profile ID is required")
    
    logger.info(f"📋 [SOCIAL PIPELINE STAGE 2] Reviewing {len(request.profile_ids)} profiles: {request.action}")
    
    try:
        # Get profiles
        result = await db.execute(
            select(SocialProfile).where(SocialProfile.id.in_(request.profile_ids))
        )
        profiles = result.scalars().all()
        
        if len(profiles) != len(request.profile_ids):
            logger.warning(f"⚠️  Only found {len(profiles)} of {len(request.profile_ids)} requested profiles")
        
        updated_count = 0
        new_status = DiscoveryStatus.QUALIFIED.value if request.action == "qualify" else DiscoveryStatus.REJECTED.value
        
        for profile in profiles:
            profile.discovery_status = new_status
            updated_count += 1
        
        await db.commit()
        
        logger.info(f"✅ [SOCIAL PIPELINE STAGE 2] Updated {updated_count} profiles to {new_status}")
        
        return {
            "success": True,
            "updated": updated_count,
            "action": request.action,
            "message": f"Updated {updated_count} profile(s) to {new_status}"
        }
        
    except Exception as e:
        logger.error(f"❌ [SOCIAL PIPELINE STAGE 2] Error: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to review profiles: {str(e)}")


# ============================================
# STAGE 3: DRAFTING
# ============================================

class DraftRequest(BaseModel):
    profile_ids: List[UUID]
    is_followup: bool = False


@router.post("/draft")
async def create_drafts(
    request: DraftRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    STAGE 3: Create drafts for qualified profiles.
    
    Unlocked when qualified_count > 0.
    Drafts are saved but not sent.
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
    
    logger.info(f"📝 [SOCIAL PIPELINE STAGE 3] Creating drafts for {len(request.profile_ids)} profiles")
    
    try:
        # Get qualified profiles
        result = await db.execute(
            select(SocialProfile).where(
                and_(
                    SocialProfile.id.in_(request.profile_ids),
                    SocialProfile.discovery_status == DiscoveryStatus.QUALIFIED.value
                )
            )
        )
        profiles = result.scalars().all()
        
        if len(profiles) == 0:
            raise HTTPException(
                status_code=400,
                detail="No qualified profiles found. Profiles must be qualified before drafting."
            )
        
        drafts_created = 0
        
        for profile in profiles:
            # Check if this is a follow-up
            if request.is_followup:
                # Check for previous messages
                prev_messages = await db.execute(
                    select(SocialMessage).where(
                        and_(
                            SocialMessage.profile_id == profile.id,
                            SocialMessage.status == MessageStatus.SENT.value
                        )
                    ).order_by(SocialMessage.sent_at.desc())
                )
                previous = prev_messages.scalar_one_or_none()
                
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
            
            # Generate follow-up using AI drafting service
            from app.services.social.drafting import SocialDraftingService
            drafting_service = SocialDraftingService()
            
            draft_result = await drafting_service.compose_followup_message(profile, db)
            
            if draft_result.get("success"):
                draft_body = draft_result.get("body", "")
            else:
                error = draft_result.get("error", "Unknown error")
                logger.warning(f"⚠️  Failed to generate follow-up draft for {profile.username}: {error}")
                # Fallback to simple message
                draft_body = f"Follow-up message #{next_sequence} for {profile.username}"
            else:
                # Initial message
                # Generate initial draft using AI drafting service
                from app.services.social.drafting import SocialDraftingService
                drafting_service = SocialDraftingService()
                
                draft_result = await drafting_service.compose_initial_message(profile, db)
                
                if draft_result.get("success"):
                    draft_body = draft_result.get("body", "")
                else:
                    error = draft_result.get("error", "Unknown error")
                    logger.warning(f"⚠️  Failed to generate initial draft for {profile.username}: {error}")
                    # Fallback to simple message
                    draft_body = f"Initial outreach message for {profile.username}"
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
            
            # Update profile outreach status
            profile.outreach_status = OutreachStatus.DRAFTED.value
            
            drafts_created += 1
        
        await db.commit()
        
        logger.info(f"✅ [SOCIAL PIPELINE STAGE 3] Created {drafts_created} drafts")
        
        return {
            "success": True,
            "drafts_created": drafts_created,
            "message": f"Created {drafts_created} draft(s)"
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
    profile_ids: List[UUID]


@router.post("/send")
async def send_messages(
    request: SendRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    STAGE 4: Send messages to profiles.
    
    Unlocked when drafted_count > 0.
    Requires draft to exist for each profile.
    Sending happens only from this stage.
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
    
    logger.info(f"📤 [SOCIAL PIPELINE STAGE 4] Sending messages to {len(request.profile_ids)} profiles")
    
    try:
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
            
            # Send message via platform API using sending service
            from app.services.social.sending import SocialSendingService
            
            sending_service = SocialSendingService()
            send_result = await sending_service.send_message(profile, draft.draft_body, db)
            
            if send_result.get("success"):
                messages_sent += 1
                logger.info(f"✅ [SOCIAL PIPELINE STAGE 4] Message sent to @{profile.username}")
            else:
                error = send_result.get("error", "Unknown error")
                logger.warning(f"⚠️  [SOCIAL PIPELINE STAGE 4] Failed to send to @{profile.username}: {error}")
                # Message record already created by sending service with FAILED status
        
        await db.commit()
        
        logger.info(f"✅ [SOCIAL PIPELINE STAGE 4] Sent {messages_sent} messages")
        
        return {
            "success": True,
            "messages_sent": messages_sent,
            "message": f"Sent {messages_sent} message(s)"
        }
        
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
    STAGE 5: Create follow-up drafts for profiles that have sent messages.
    
    Unlocked when sent_count > 0.
    Automatically generates follow-up using Gemini (humorous, clever, non-repetitive).
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
    
    logger.info(f"🔄 [SOCIAL PIPELINE STAGE 5] Creating follow-ups for {len(request.profile_ids)} profiles")
    
    try:
        # Get profiles with sent messages
        result = await db.execute(
            select(SocialProfile).where(
                and_(
                    SocialProfile.id.in_(request.profile_ids),
                    SocialProfile.outreach_status == OutreachStatus.SENT.value
                )
            )
        )
        profiles = result.scalars().all()
        
        if len(profiles) == 0:
            raise HTTPException(
                status_code=400,
                detail="No profiles with sent messages found. Profiles must have sent messages before follow-ups."
            )
        
        drafts_created = 0
        
        for profile in profiles:
            # Check for previous sent messages
            prev_messages = await db.execute(
                select(SocialMessage).where(
                    and_(
                        SocialMessage.profile_id == profile.id,
                        SocialMessage.status == MessageStatus.SENT.value
                    )
                ).order_by(SocialMessage.sent_at.desc())
            )
            previous = prev_messages.scalar_one_or_none()
            
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
            
            # Generate follow-up using AI drafting service
            from app.services.social.drafting import SocialDraftingService
            drafting_service = SocialDraftingService()
            
            draft_result = await drafting_service.compose_followup_message(profile, db)
            
            if draft_result.get("success"):
                draft_body = draft_result.get("body", "")
            else:
                error = draft_result.get("error", "Unknown error")
                logger.warning(f"⚠️  Failed to generate follow-up draft for {profile.username}: {error}")
                # Fallback to simple message
                draft_body = f"Follow-up message #{next_sequence} for {profile.username}"
            
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
        
        logger.info(f"✅ [SOCIAL PIPELINE STAGE 5] Created {drafts_created} follow-up drafts")
        
        return {
            "success": True,
            "drafts_created": drafts_created,
            "message": f"Created {drafts_created} follow-up draft(s)"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [SOCIAL PIPELINE STAGE 5] Error: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create follow-ups: {str(e)}")

