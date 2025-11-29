"""
Job management API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
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
    # Create job record
    job = Job(
        job_type="discover",
        params={
            "keywords": request.keywords,
            "location": request.location,
            "max_results": request.max_results,
            "categories": request.categories
        },
        status="pending"
    )
    
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    # Queue RQ task
    try:
        from worker.tasks.discovery import discover_websites_task
        queue = get_queue("discovery")
        if queue:
            queue.enqueue(discover_websites_task, str(job.id))
        else:
            logger.warning("Redis not available - discovery job not queued")
    except ImportError:
        logger.warning("Worker tasks not available - discovery job not queued. Ensure worker service is running.")
        job.status = "failed"
        job.error_message = "Worker service not available"
        await db.commit()
    
    return JobResponse.model_validate(job)


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
    
    # Queue RQ task
    try:
        from worker.tasks.scoring import score_prospects_task
        queue = get_queue("scoring")
        if queue:
            queue.enqueue(score_prospects_task, str(job.id))
        else:
            logger.warning("Redis not available - scoring job not queued")
    except ImportError:
        logger.warning("Worker tasks not available - scoring job not queued.")
        job.status = "failed"
        job.error_message = "Worker service not available"
        await db.commit()
    
    return JobResponse.model_validate(job)


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
    
    # Queue RQ task
    try:
        from worker.tasks.send import send_emails_task
        queue = get_queue("send")
        if queue:
            queue.enqueue(send_emails_task, str(job.id))
        else:
            logger.warning("Redis not available - send job not queued")
    except ImportError:
        logger.warning("Worker tasks not available - send job not queued.")
        job.status = "failed"
        job.error_message = "Worker service not available"
        await db.commit()
    
    return JobResponse.model_validate(job)


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
    
    # Queue RQ task
    try:
        from worker.tasks.followup import send_followups_task
        queue = get_queue("followup")
        if queue:
            queue.enqueue(send_followups_task, str(job.id))
        else:
            logger.warning("Redis not available - followup job not queued")
    except ImportError:
        logger.warning("Worker tasks not available - followup job not queued.")
        job.status = "failed"
        job.error_message = "Worker service not available"
        await db.commit()
    
    return JobResponse.model_validate(job)


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
    
    # Queue RQ task
    try:
        from worker.tasks.reply_handler import check_replies_task
        queue = get_queue("followup")
        if queue:
            queue.enqueue(check_replies_task)
        else:
            logger.warning("Redis not available - reply check job not queued")
        return {
            "job_id": job.id,
            "status": "queued",
            "message": "Reply check job queued"
        }
    except ImportError:
        logger.warning("Worker tasks not available - reply check job not queued.")
        job.status = "failed"
        job.error_message = "Worker service not available"
        await db.commit()
        return {
            "job_id": job.id,
            "status": "failed",
            "message": "Worker service not available"
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
    return [JobResponse.model_validate(job) for job in jobs]
