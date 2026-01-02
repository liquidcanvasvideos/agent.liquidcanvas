"""
Social Discovery Task

Processes social discovery jobs directly in backend.
Completely separate from website discovery task.
"""
import asyncio
import logging
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import AsyncSessionLocal
from app.services.social.discovery_runner import SocialDiscoveryRunner

logger = logging.getLogger(__name__)


async def discover_social_profiles_async(job_id: str) -> dict:
    """
    Async function to discover social profiles for a job.
    
    This runs directly in the backend without needing a separate worker.
    Completely separate from website discovery.
    
    Args:
        job_id: UUID string of the discovery job
    
    Returns:
        Dict with success status and results
    """
    from app.models.social import SocialDiscoveryJob, DiscoveryJobStatus
    from sqlalchemy import select
    from datetime import datetime, timezone
    
    async with AsyncSessionLocal() as db:
        try:
            job_uuid = UUID(job_id)
        except ValueError:
            logger.error(f"❌ [SOCIAL DISCOVERY] Invalid job ID format: {job_id}")
            return {"error": "Invalid job ID format"}
        
        # Fetch job
        result = await db.execute(
            select(SocialDiscoveryJob).where(SocialDiscoveryJob.id == job_uuid)
        )
        job = result.scalar_one_or_none()
        
        if not job:
            logger.error(f"❌ [SOCIAL DISCOVERY] Job {job_id} not found")
            return {"error": "Job not found"}
        
        # Check if job was cancelled
        if job.status == DiscoveryJobStatus.FAILED.value:
            logger.info(f"⚠️  [SOCIAL DISCOVERY] Job {job_id} already failed, skipping")
            return {"error": "Job already failed"}
        
        logger.info(f"🚀 [SOCIAL DISCOVERY] Starting discovery job {job_id} for platform {job.platform.value}")
        
        try:
            # Run discovery using platform-specific service
            runner = SocialDiscoveryRunner()
            await runner.run_discovery_job(job_uuid, db)
            
            # Refresh job to get updated status
            await db.refresh(job)
            
            logger.info(f"✅ [SOCIAL DISCOVERY] Job {job_id} completed successfully")
            return {
                "success": True,
                "job_id": job_id,
                "results_count": job.results_count,
                "status": job.status
            }
            
        except Exception as e:
            logger.error(f"❌ [SOCIAL DISCOVERY] Job {job_id} failed: {e}", exc_info=True)
            
            # Update job status
            job.status = DiscoveryJobStatus.FAILED.value
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

