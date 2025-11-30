"""
Job management API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy import inspect as sqlalchemy_inspect
from typing import List, Optional
from uuid import UUID
import redis
from rq import Queue
import os
from dotenv import load_dotenv
import logging

from app.db.database import get_db

logger = logging.getLogger(__name__)
from app.models.job import Job
from app.schemas.job import JobCreateRequest, JobResponse, JobStatusResponse

load_dotenv()

router = APIRouter()

# Redis connection for RQ - lazy initialization
_redis_conn = None
_queues = {}

def get_redis_connection():
    """Get or create Redis connection (lazy initialization)"""
    global _redis_conn
    if _redis_conn is None:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        try:
            _redis_conn = redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2)
            # Test connection
            _redis_conn.ping()
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Queue operations will be disabled.")
            _redis_conn = None
    return _redis_conn

def get_queue(name: str):
    """Get or create a queue (lazy initialization)"""
    if name not in _queues:
        conn = get_redis_connection()
        if conn is None:
            return None
        _queues[name] = Queue(name, connection=conn)
    return _queues.get(name)


def job_to_response(job: Job) -> JobResponse:
    """Convert Job model to JobResponse, handling async SQLAlchemy attributes"""
    # Access attributes via __dict__ to avoid triggering async operations
    # This works because the object has been refreshed and attributes are loaded
    job_dict = job.__dict__.copy()
    # Remove SQLAlchemy internal attributes
    job_dict.pop('_sa_instance_state', None)
    
    # Get values, using created_at as fallback for updated_at if needed
    updated_at = job_dict.get('updated_at') or job_dict.get('created_at')
    if updated_at is None:
        from datetime import datetime, timezone
        updated_at = datetime.now(timezone.utc)
    
    return JobResponse(
        id=job_dict.get('id'),
        job_type=job_dict.get('job_type'),
        status=job_dict.get('status'),
        params=job_dict.get('params'),
        result=job_dict.get('result'),
        error_message=job_dict.get('error_message'),
        created_at=job_dict.get('created_at'),
        updated_at=updated_at
    )


@router.post("/discover", response_model=JobResponse)
async def create_discovery_job(
    request: JobCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new website discovery job
    
    This will:
    1. Create a job record in the database
    2. Queue a background task to discover websites
    3. Return the job ID for status tracking
    """
    # Validate: require either keywords or categories
    if not request.keywords and not request.categories:
        raise HTTPException(
            status_code=400,
            detail="Please enter keywords or select at least one category"
        )
    
    # Validate: require at least one location
    if not request.locations or len(request.locations) == 0:
        raise HTTPException(
            status_code=400,
            detail="Please select at least one location"
        )
    
    # Check if there's already a running discovery job
    running_job = await db.execute(
        select(Job).where(
            Job.job_type == "discover",
            Job.status == "running"
        ).order_by(Job.created_at.desc())
    )
    existing_job = running_job.scalar_one_or_none()
    if existing_job:
        # Check if job has been running for more than 2 hours (likely stuck)
        from datetime import datetime, timezone, timedelta
        if existing_job.updated_at:
            elapsed = datetime.now(timezone.utc) - existing_job.updated_at.replace(tzinfo=timezone.utc)
            if elapsed > timedelta(hours=2):
                logger.warning(f"Found stuck discovery job {existing_job.id}, marking as failed")
                existing_job.status = "failed"
                existing_job.error_message = "Job timed out after 2 hours"
                await db.commit()
            else:
                raise HTTPException(
                    status_code=409,
                    detail=f"A discovery job is already running (ID: {existing_job.id}). Please wait for it to complete or cancel it first."
                )
    
    # Create job record
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    job = Job(
        job_type="discover",
        params={
            "keywords": request.keywords or "",
            "locations": request.locations,
            "max_results": request.max_results,
            "categories": request.categories or []
        },
        status="pending"
    )
    
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    # Ensure updated_at is set (onupdate doesn't work well with async)
    if not job.updated_at:
        job.updated_at = now
        await db.commit()
        await db.refresh(job)
    
    # Process job directly in backend (free tier compatible - no separate worker needed)
    try:
        from app.tasks.discovery import process_discovery_job
        import asyncio
        
        # Start background task to process job
        # This runs asynchronously without blocking the API response
        try:
            task = asyncio.create_task(process_discovery_job(str(job.id)))
            logger.info(f"Discovery job {job.id} started in background (task_id: {id(task)})")
        except Exception as task_error:
            # Task creation failed - update job status immediately
            logger.error(f"Failed to create background task for job {job.id}: {task_error}", exc_info=True)
            job.status = "failed"
            job.error_message = f"Failed to create background task: {task_error}"
            await db.commit()
            await db.refresh(job)
    except Exception as e:
        logger.error(f"Failed to start discovery job {job.id}: {e}", exc_info=True)
        job.status = "failed"
        job.error_message = f"Failed to start job: {e}"
        await db.commit()
        await db.refresh(job)
    
    # Use helper function to avoid async SQLAlchemy attribute access issues
    return job_to_response(job)


@router.get("/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(
    job_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get the status of a job"""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return JobStatusResponse(
        id=job.id,
        status=job.status,
        progress=job.params,  # Can include progress info
        result=job.result,
        error_message=job.error_message
    )


@router.post("/score", response_model=JobResponse)
async def create_scoring_job(
    prospect_ids: Optional[List[UUID]] = None,
    max_prospects: int = 1000,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new scoring job to calculate prospect scores
    
    Query params:
    - prospect_ids: Optional list of specific prospect IDs to score
    - max_prospects: Maximum number of prospects to score (if no IDs specified)
    """
    # Create job record
    job = Job(
        job_type="score",
        params={
            "prospect_ids": [str(pid) for pid in prospect_ids] if prospect_ids else None,
            "max_prospects": max_prospects
        },
        status="pending"
    )
    
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    # TODO: Implement scoring task in backend/app/tasks/scoring.py
    # For now, mark as not implemented
    logger.warning("Scoring task not yet implemented in backend")
    job.status = "failed"
    job.error_message = "Scoring task not yet implemented. This feature will be available soon."
    await db.commit()
    
    return job_to_response(job)


@router.post("/send", response_model=JobResponse)
async def create_send_job(
    prospect_ids: Optional[List[UUID]] = None,
    max_prospects: int = 100,
    auto_send: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new send job to send emails to prospects
    
    Query params:
    - prospect_ids: Optional list of specific prospect IDs to send to
    - max_prospects: Maximum number of prospects to send to (if no IDs specified)
    - auto_send: Whether to send without review (uses drafts if available)
    """
    # Create job record
    job = Job(
        job_type="send",
        params={
            "prospect_ids": [str(pid) for pid in prospect_ids] if prospect_ids else None,
            "max_prospects": max_prospects,
            "auto_send": auto_send
        },
        status="pending"
    )
    
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    # Start send task in background
    try:
        from app.tasks.send import process_send_job
        import asyncio
        asyncio.create_task(process_send_job(str(job.id)))
        logger.info(f"✅ Send job {job.id} started in background")
    except Exception as e:
        logger.error(f"❌ Failed to start send job {job.id}: {e}", exc_info=True)
        job.status = "failed"
        job.error_message = f"Failed to start job: {e}"
        await db.commit()
        await db.refresh(job)
    
    return job_to_response(job)


@router.post("/followup", response_model=JobResponse)
async def create_followup_job(
    days_since_sent: int = 7,
    max_followups: int = 3,
    max_prospects: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new follow-up job to send follow-up emails
    
    Query params:
    - days_since_sent: Days since last email to send follow-up (default: 7)
    - max_followups: Maximum number of follow-ups per prospect (default: 3)
    - max_prospects: Maximum number of prospects to process (default: 100)
    """
    # Create job record
    job = Job(
        job_type="followup",
        params={
            "days_since_sent": days_since_sent,
            "max_followups": max_followups,
            "max_prospects": max_prospects
        },
        status="pending"
    )
    
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    # TODO: Implement followup task in backend/app/tasks/followup.py
    # For now, mark as not implemented
    logger.warning("Followup task not yet implemented in backend")
    job.status = "failed"
    job.error_message = "Followup task not yet implemented. This feature will be available soon."
    await db.commit()
    
    return job_to_response(job)


@router.post("/check-replies")
async def check_replies(
    db: AsyncSession = Depends(get_db)
):
    """
    Manually trigger a reply check job
    
    This will check Gmail for replies to sent emails and update prospect statuses
    """
    # Create job record
    job = Job(
        job_type="check_replies",
        params={},
        status="pending"
    )
    
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    # TODO: Implement reply handler in backend/app/tasks/reply_handler.py
    # For now, mark as not implemented
    logger.warning("Reply handler not yet implemented in backend")
    job.status = "failed"
    job.error_message = "Reply handler not yet implemented. This feature will be available soon."
    await db.commit()
    return {
        "job_id": job.id,
        "status": "failed",
        "message": "Reply handler not yet implemented. This feature will be available soon."
    }


@router.post("/{job_id}/cancel")
async def cancel_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Cancel a running job
    
    This will:
    1. Mark the job as cancelled
    2. The discovery task will check this status and stop processing
    """
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status not in ["pending", "running"]:
        raise HTTPException(
            status_code=400,
            detail=f"Job is already {job.status} and cannot be cancelled"
        )
    
    job.status = "cancelled"
    job.error_message = "Cancelled by user"
    await db.commit()
    
    logger.info(f"Job {job_id} cancelled by user")
    
    return {
        "message": "Job cancelled successfully",
        "job_id": str(job_id),
        "status": "cancelled"
    }


@router.get("", response_model=List[JobResponse])
async def list_jobs(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """List all jobs"""
    result = await db.execute(
        select(Job)
        .order_by(Job.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    jobs = result.scalars().all()
    return [job_to_response(job) for job in jobs]
