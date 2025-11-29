"""
Prospect management API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from typing import List, Optional
from uuid import UUID
import redis
from rq import Queue
import os
from dotenv import load_dotenv
import logging

from app.db.database import get_db

logger = logging.getLogger(__name__)
from app.models.prospect import Prospect
from app.models.job import Job
from app.schemas.prospect import (
    ProspectResponse,
    ProspectListResponse,
    ComposeRequest,
    ComposeResponse,
    SendRequest,
    SendResponse
)

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


@router.post("/enrich")
async def create_enrichment_job(
    prospect_ids: Optional[List[UUID]] = None,
    max_prospects: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new enrichment job to find emails for prospects
    
    Query params:
    - prospect_ids: Optional list of specific prospect IDs to enrich
    - max_prospects: Maximum number of prospects to enrich (if no IDs specified)
    """
    # Create job record
    job = Job(
        job_type="enrich",
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
        from worker.tasks.enrichment import enrich_prospects_task
        queue = get_queue("enrichment")
        if queue:
            queue.enqueue(enrich_prospects_task, str(job.id))
        else:
            logger.warning("Redis not available - enrichment job not queued")
        return {
            "job_id": job.id,
            "status": "queued",
            "message": "Enrichment job queued"
        }
    except ImportError:
        logger.warning("Worker tasks not available - enrichment job not queued.")
        job.status = "failed"
        job.error_message = "Worker service not available"
        await db.commit()
        return {
            "job_id": job.id,
            "status": "failed",
            "message": "Worker service not available"
        }


@router.get("", response_model=ProspectListResponse)
async def list_prospects(
    skip: int = 0,
    limit: int = 50,
    status: Optional[str] = None,
    min_score: Optional[float] = None,
    has_email: Optional[bool] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    List prospects with filtering
    
    Query params:
    - skip: Pagination offset
    - limit: Number of results (max 200)
    - status: Filter by outreach_status
    - min_score: Minimum score threshold
    - has_email: Filter by whether prospect has email
    """
    query = select(Prospect)
    
    # Apply filters
    if status:
        query = query.where(Prospect.outreach_status == status)
    if min_score is not None:
        query = query.where(Prospect.score >= min_score)
    if has_email is not None:
        if has_email:
            query = query.where(Prospect.contact_email.isnot(None))
        else:
            query = query.where(Prospect.contact_email.is_(None))
    
    # Get total count
    count_query = select(func.count()).select_from(Prospect)
    if status:
        count_query = count_query.where(Prospect.outreach_status == status)
    if min_score is not None:
        count_query = count_query.where(Prospect.score >= min_score)
    if has_email is not None:
        if has_email:
            count_query = count_query.where(Prospect.contact_email.isnot(None))
        else:
            count_query = count_query.where(Prospect.contact_email.is_(None))
    
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Get paginated results
    query = query.order_by(Prospect.score.desc(), Prospect.created_at.desc())
    query = query.offset(skip).limit(min(limit, 200))
    
    result = await db.execute(query)
    prospects = result.scalars().all()
    
    return ProspectListResponse(
        prospects=[ProspectResponse.model_validate(p) for p in prospects],
        total=total,
        skip=skip,
        limit=limit
    )


@router.get("/{prospect_id}", response_model=ProspectResponse)
async def get_prospect(
    prospect_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get a single prospect by ID"""
    result = await db.execute(select(Prospect).where(Prospect.id == prospect_id))
    prospect = result.scalar_one_or_none()
    
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")
    
    return ProspectResponse.model_validate(prospect)


@router.post("/{prospect_id}/compose", response_model=ComposeResponse)
async def compose_email(
    prospect_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Compose an email for a prospect using Gemini
    
    This will:
    1. Fetch prospect details
    2. Call Gemini API to generate email
    3. Save draft to prospect record
    """
    result = await db.execute(select(Prospect).where(Prospect.id == prospect_id))
    prospect = result.scalar_one_or_none()
    
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")
    
    # Import Gemini client
    try:
        from worker.clients.gemini import GeminiClient
        client = GeminiClient()
    except ImportError:
        raise HTTPException(status_code=500, detail="Worker clients not available. Ensure worker service is running.")
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"Gemini API not configured: {str(e)}")
    
    # Extract snippet from DataForSEO payload
    page_snippet = None
    if prospect.dataforseo_payload:
        page_snippet = prospect.dataforseo_payload.get("description") or prospect.dataforseo_payload.get("snippet")
    
    # Extract contact name from Hunter.io payload
    contact_name = None
    if prospect.hunter_payload and prospect.hunter_payload.get("emails"):
        emails = prospect.hunter_payload["emails"]
        if emails:
            first_email = emails[0]
            first_name = first_email.get("first_name")
            last_name = first_email.get("last_name")
            if first_name or last_name:
                contact_name = f"{first_name or ''} {last_name or ''}".strip()
    
    # Call Gemini to compose email
    import asyncio
    gemini_result = asyncio.run(client.compose_email(
        domain=prospect.domain,
        page_title=prospect.page_title,
        page_url=prospect.page_url,
        page_snippet=page_snippet,
        contact_name=contact_name
    ))
    
    if not gemini_result.get("success"):
        error = gemini_result.get("error", "Unknown error")
        raise HTTPException(status_code=500, detail=f"Failed to compose email: {error}")
    
    # Save draft to prospect
    prospect.draft_subject = gemini_result.get("subject")
    prospect.draft_body = gemini_result.get("body")
    
    await db.commit()
    await db.refresh(prospect)
    
    return ComposeResponse(
        prospect_id=prospect.id,
        subject=prospect.draft_subject,
        body=prospect.draft_body,
        draft_saved=True
    )


@router.post("/{prospect_id}/send", response_model=SendResponse)
async def send_email(
    prospect_id: UUID,
    request: SendRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Send an email to a prospect via Gmail API
    
    This will:
    1. Fetch prospect details
    2. Use provided subject/body or draft
    3. Send via Gmail API (will be implemented in Phase 6)
    4. Create email log entry
    5. Update prospect status
    """
    result = await db.execute(select(Prospect).where(Prospect.id == prospect_id))
    prospect = result.scalar_one_or_none()
    
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")
    
    if not prospect.contact_email:
        raise HTTPException(status_code=400, detail="Prospect has no contact email")
    
    # Use draft if subject/body not provided
    subject = request.subject or prospect.draft_subject
    body = request.body or prospect.draft_body
    
    if not subject or not body:
        raise HTTPException(
            status_code=400,
            detail="Email subject and body required. Either provide in request or compose email first."
        )
    
    # Send email via Gmail API
    from datetime import datetime
    from app.models.email_log import EmailLog
    import asyncio
    
    try:
        from worker.clients.gmail import GmailClient
        gmail_client = GmailClient()
    except ImportError:
        raise HTTPException(status_code=500, detail="Worker clients not available. Ensure worker service is running.")
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"Gmail not configured: {str(e)}")
    
    # Send email
    send_result = asyncio.run(gmail_client.send_email(
        to_email=prospect.contact_email,
        subject=subject,
        body=body
    ))
    
    if not send_result.get("success"):
        error = send_result.get("error", "Unknown error")
        raise HTTPException(status_code=500, detail=f"Failed to send email: {error}")
    
    # Create email log entry
    email_log = EmailLog(
        prospect_id=prospect.id,
        subject=subject,
        body=body,
        response=send_result
    )
    db.add(email_log)
    
    # Update prospect
    prospect.outreach_status = "sent"
    prospect.last_sent = datetime.utcnow()
    
    await db.commit()
    await db.refresh(email_log)
    
    return SendResponse(
        prospect_id=prospect.id,
        email_log_id=email_log.id,
        sent_at=email_log.sent_at,
        success=True,
        message_id=send_result.get("message_id")
    )
