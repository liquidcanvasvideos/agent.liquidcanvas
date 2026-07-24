"""
Social Discovery Task

Processes social discovery jobs directly in backend.
Completely separate from website discovery task.
Uses adapter pattern to discover profiles from different platforms.
"""
import asyncio
import logging
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import AsyncSessionLocal
from app.adapters.social_discovery import (
    LinkedInDiscoveryAdapter,
    InstagramDiscoveryAdapter,
    FacebookDiscoveryAdapter,
    TikTokDiscoveryAdapter
)
from app.models.prospect import Prospect, DiscoveryStatus

logger = logging.getLogger(__name__)


async def discover_social_profiles_async(job_id: str) -> dict:
    """
    Async function to discover social profiles for a job.
    
    This runs directly in the backend without needing a separate worker.
    Uses adapter pattern to discover profiles from different platforms.
    
    Args:
        job_id: UUID string of the discovery job
    
    Returns:
        Dict with success status and results
    """
    from app.models.job import Job
    
    async with AsyncSessionLocal() as db:
        try:
            job_uuid = UUID(job_id)
        except ValueError:
            logger.error(f"❌ [SOCIAL DISCOVERY] Invalid job ID format: {job_id}")
            return {"error": "Invalid job ID format"}
        
        # Fetch job
        result = await db.execute(select(Job).where(Job.id == job_uuid))
        job = result.scalar_one_or_none()
        
        if not job:
            logger.error(f"❌ [SOCIAL DISCOVERY] Job {job_id} not found")
            return {"error": "Job not found"}
        
        # Check if job was cancelled
        if job.status == "cancelled":
            logger.info(f"⚠️  [SOCIAL DISCOVERY] Job {job_id} was cancelled, skipping")
            return {"error": "Job was cancelled"}
        
        # Update job status to running
        job.status = "running"
        start_time = datetime.now(timezone.utc)
        await db.commit()
        
        params = job.params or {}
        platform = params.get("platform", "").lower()
        categories = params.get("categories", [])
        locations = params.get("locations", [])
        keywords = params.get("keywords", [])
        max_results = params.get("max_results", 100)
        
        logger.info(f"🚀 [SOCIAL DISCOVERY] Starting discovery job {job_id} for platform {platform}")
        logger.info(f"📋 [SOCIAL DISCOVERY] Categories: {categories}, Locations: {locations}, Keywords: {keywords}")
        
        try:
            # Select adapter based on platform
            adapter_map = {
                'linkedin': LinkedInDiscoveryAdapter(),
                'instagram': InstagramDiscoveryAdapter(),
                'facebook': FacebookDiscoveryAdapter(),
                'tiktok': TikTokDiscoveryAdapter(),
            }
            
            if platform not in adapter_map:
                raise ValueError(f"Invalid platform: {platform}")
            
            adapter = adapter_map[platform]
            
            # Prepare adapter parameters
            adapter_params = {
                'categories': categories,
                'locations': locations,
                'keywords': keywords if isinstance(keywords, list) else [],
                'max_results': max_results,
            }
            
            # Run discovery using adapter (this will take time)
            logger.info(f"🚀 [SOCIAL DISCOVERY] Starting adapter.discover() for platform {platform}")
            logger.info(f"📋 [SOCIAL DISCOVERY] Adapter params: {adapter_params}")
            
            prospects = await adapter.discover(adapter_params, db)
            
            logger.info(f"📊 [SOCIAL DISCOVERY] Adapter returned {len(prospects)} prospects")
            if len(prospects) == 0:
                logger.warning(f"⚠️  [SOCIAL DISCOVERY] Adapter returned ZERO prospects! This may indicate:")
                logger.warning(f"   1. No results found for the search criteria")
                logger.warning(f"   2. DataForSEO API issues")
                logger.warning(f"   3. Query execution problems")
                logger.warning(f"   4. URL filtering too strict")
            else:
                logger.info(f"✅ [SOCIAL DISCOVERY] Adapter successfully found {len(prospects)} prospects")
            
            # ACCEPTANCE & FILTERING RULES
            # Requirements for eligibility (not for saving):
            # - follower_count >= 1000 OR engagement_rate >= 1000 (if calculable)
            # All profiles are saved, but eligibility controls pipeline actions
            MIN_FOLLOWERS = 1000
            MIN_ENGAGEMENT = 1000  # For engagement-based eligibility
            
            qualified_count = 0
            ineligible_count = 0
            
            # Save ALL profiles to database (do not filter out)
            # Eligibility is checked at API/UI level, not at discovery time
            saved_count = 0
            for prospect in prospects:
                # Check eligibility (for reporting only, not filtering)
                follower_count = prospect.follower_count or 0
                engagement_rate = float(prospect.engagement_rate) if prospect.engagement_rate else 0.0
                
                is_eligible = (follower_count >= MIN_FOLLOWERS) or (engagement_rate >= MIN_ENGAGEMENT)
                
                if is_eligible:
                    qualified_count += 1
                else:
                    ineligible_count += 1
                    logger.debug(f"⚠️  [SOCIAL DISCOVERY] Profile {prospect.username} ineligible: {follower_count} followers, {engagement_rate}% engagement")
                
                # Save ALL profiles regardless of eligibility
                # Ensure source_type is set
                prospect.source_type = 'social'
                prospect.source_platform = platform
                prospect.discovery_status = DiscoveryStatus.DISCOVERED.value
                prospect.approval_status = 'PENDING'  # Needs manual accept/reject
                prospect.scrape_status = 'DISCOVERED'
                
                # CRITICAL: Clear fields that may not exist in database yet (from add_realtime_scraping_fields migration)
                # These are only set during scraping, not discovery
                # Setting them to None explicitly prevents SQLAlchemy from trying to insert them if columns don't exist
                if hasattr(prospect, 'bio_text'):
                    prospect.bio_text = None
                if hasattr(prospect, 'external_links'):
                    prospect.external_links = None
                if hasattr(prospect, 'scraped_at'):
                    prospect.scraped_at = None
                
                db.add(prospect)
                saved_count += 1
            
            logger.info(f"📊 [SOCIAL DISCOVERY] Eligibility results: {qualified_count} eligible, {ineligible_count} ineligible out of {saved_count} saved profiles")
            
            await db.commit()
            
            # Update job status and result
            job.status = "completed"
            job.result = {
                "prospects_count": saved_count,
                "qualified_count": qualified_count,
                "disqualified_count": ineligible_count,  # Fixed: use ineligible_count instead of undefined disqualified_count
                "platform": platform,
                "categories": categories,
                "locations": locations
            }
            await db.commit()
            
            logger.info(f"✅ [SOCIAL DISCOVERY] Job {job_id} completed successfully - discovered {saved_count} profiles")
            
            # Trigger refresh event
            if saved_count > 0:
                # Dispatch event to refresh frontend
                import sys
                if 'asyncio' in sys.modules:
                    # In async context, we can't easily dispatch events, but the frontend polls
                    pass
            
            return {
                "success": True,
                "job_id": job_id,
                "prospects_count": saved_count,
                "status": "completed"
            }
            
        except Exception as e:
            logger.error(f"❌ [SOCIAL DISCOVERY] Job {job_id} failed: {e}", exc_info=True)
            
            # Update job status
            job.status = "failed"
            job.error_message = str(e)
            await db.commit()
            
            return {
                "success": False,
                "job_id": job_id,
                "error": str(e)
            }


async def process_social_discovery_job(job_id: str):
    """
    Wrapper to process social discovery job in background.
    
    This can be called from FastAPI BackgroundTasks or asyncio.
    """
    try:
        await discover_social_profiles_async(job_id)
    except asyncio.CancelledError:
        logger.info(f"⚠️  [SOCIAL DISCOVERY] Job {job_id} was cancelled")
        raise
    except Exception as e:
        logger.error(f"❌ [SOCIAL DISCOVERY] Error processing job {job_id}: {e}", exc_info=True)

