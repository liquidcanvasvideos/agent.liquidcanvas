"""
Social Discovery Runner

Orchestrates discovery jobs across all platforms.
Completely separate from website discovery.
"""
from typing import Dict, Any, List
from uuid import UUID
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.social import (
    SocialDiscoveryJob,
    SocialProfile,
    SocialPlatform,
    DiscoveryStatus,
    DiscoveryJobStatus,
)
from .linkedin_discovery import LinkedInDiscoveryService
from .instagram_discovery import InstagramDiscoveryService
from .tiktok_discovery import TikTokDiscoveryService
from .facebook_discovery import FacebookDiscoveryService

logger = logging.getLogger(__name__)


class SocialDiscoveryRunner:
    """
    Runs discovery jobs for social platforms.
    
    Each platform has its own service that implements BaseDiscoveryService.
    """
    
    def __init__(self):
        self.services = {
            SocialPlatform.LINKEDIN.value: LinkedInDiscoveryService(),
            SocialPlatform.INSTAGRAM.value: InstagramDiscoveryService(),
            SocialPlatform.TIKTOK.value: TikTokDiscoveryService(),
            SocialPlatform.FACEBOOK.value: FacebookDiscoveryService(),
        }
    
    async def run_discovery_job(
        self,
        job_id: UUID,
        db: AsyncSession
    ) -> None:
        """
        Run a discovery job.
        
        Args:
            job_id: ID of the discovery job
            db: Database session
        """
        # Get job from database
        result = await db.execute(
            select(SocialDiscoveryJob).where(SocialDiscoveryJob.id == job_id)
        )
        job = result.scalar_one_or_none()
        
        if not job:
            logger.error(f"❌ [SOCIAL DISCOVERY] Job {job_id} not found")
            return
        
        # Update job status
        job.status = DiscoveryJobStatus.RUNNING.value
        await db.commit()
        
        logger.info(f"🚀 [SOCIAL DISCOVERY] Starting job {job_id} for platform {job.platform.value}")
        
        try:
            # Get platform-specific service
            service = self.services.get(job.platform.value)
            if not service:
                raise ValueError(f"Unknown platform: {job.platform.value}")
            
            # Extract search parameters
            categories = job.categories or []
            locations = job.locations or []
            keywords = job.keywords or []
            parameters = job.parameters or job.filters or {}
            
            # Run discovery
            profiles_data = await service.discover_profiles(
                categories=categories,
                locations=locations,
                keywords=keywords,
                parameters=parameters,
                max_results=100  # TODO: Make configurable
            )
            
            # Create profile records
            profiles_created = 0
            for profile_data in profiles_data:
                # Check if profile already exists
                existing = await db.execute(
                    select(SocialProfile).where(
                        SocialProfile.profile_url == profile_data["profile_url"]
                    )
                )
                if existing.scalar_one_or_none():
                    # Profile already exists - skip
                    continue
                
                # Create new profile
                profile = SocialProfile(
                    platform=job.platform,
                    username=profile_data["username"],
                    full_name=profile_data.get("full_name"),
                    profile_url=profile_data["profile_url"],
                    bio=profile_data.get("bio"),
                    location=profile_data.get("location"),
                    category=profile_data.get("category"),
                    followers_count=profile_data.get("followers_count", 0),
                    engagement_score=profile_data.get("engagement_score", 0.0),
                    discovery_status=DiscoveryStatus.DISCOVERED.value,
                    discovery_job_id=job.id,
                    is_manual=False,
                )
                
                db.add(profile)
                profiles_created += 1
            
            # Update job status
            job.status = DiscoveryJobStatus.COMPLETED.value
            job.results_count = profiles_created
            await db.commit()
            
            logger.info(f"✅ [SOCIAL DISCOVERY] Job {job_id} completed: {profiles_created} profiles created")
            
        except Exception as e:
            logger.error(f"❌ [SOCIAL DISCOVERY] Job {job_id} failed: {e}", exc_info=True)
            
            # Update job status
            job.status = DiscoveryJobStatus.FAILED.value
            job.error_message = str(e)
            await db.commit()
            
            raise

