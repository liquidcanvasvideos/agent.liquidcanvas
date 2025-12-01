"""
Job management API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy import inspect as sqlalchemy_inspect
from typing import List, Optional, Dict, Any
from uuid import UUID
import os
from dotenv import load_dotenv
import logging

from app.db.database import get_db

logger = logging.getLogger(__name__)
from app.models.job import Job
from app.schemas.job import JobCreateRequest, JobResponse, JobStatusResponse
from app.api.auth import get_current_user  # Import auth dependency

load_dotenv()

router = APIRouter()


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


@router.post("/discover")
async def create_discovery_job(
    request: JobCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user)  # REQUIRE AUTHENTICATION
):
    """
    Create a new website discovery job
    
    This will:
    1. Create a job record in the database
    2. Queue a background task to discover websites
    3. Return the job ID for status tracking
    
    REQUIRES AUTHENTICATION: Valid JWT token must be provided in Authorization header
    """
    # Ensure we have a valid authenticated user
    if not current_user:
        logger.error("Discovery job creation attempted without authentication")
        return {
            "success": False,
            "error": "Authentication required. Please provide a valid JWT token in the Authorization header.",
            "status_code": 401
        }
    
    try:
        # Validate: require either keywords or categories
        if not request.keywords and not request.categories:
            logger.warning(f"Discovery job creation failed: Missing keywords or categories")
            return {
                "success": False,
                "error": "Please enter keywords or select at least one category",
                "status_code": 400
            }
        
        # Validate: require at least one location
        if not request.locations or len(request.locations) == 0:
            logger.warning(f"Discovery job creation failed: Missing locations")
            return {
                "success": False,
                "error": "Please select at least one location",
                "status_code": 400
            }
        
        # Check if there's already a running discovery job
        try:
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
                        return {
                            "success": False,
                            "error": f"A discovery job is already running (ID: {existing_job.id}). Please wait for it to complete or cancel it first.",
                            "status_code": 409,
                            "job_id": str(existing_job.id)
                        }
        except Exception as db_check_error:
            logger.error(f"Error checking for existing jobs: {db_check_error}", exc_info=True)
            # Continue - don't fail the request if we can't check for existing jobs
        
        # Create job record
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        try:
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
        except Exception as job_creation_error:
            logger.error(f"Error creating job record: {job_creation_error}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to create job record: {str(job_creation_error)}",
                "status_code": 500
            }
        
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
                return {
                    "success": False,
                    "error": f"Failed to start background task: {str(task_error)}",
                    "status_code": 500,
                    "job_id": str(job.id)
                }
        except Exception as e:
            logger.error(f"Failed to start discovery job {job.id}: {e}", exc_info=True)
            job.status = "failed"
            job.error_message = f"Failed to start job: {e}"
            await db.commit()
            await db.refresh(job)
            return {
                "success": False,
                "error": f"Failed to start job: {str(e)}",
                "status_code": 500,
                "job_id": str(job.id)
            }
        
        # Use helper function to avoid async SQLAlchemy attribute access issues
        try:
            job_response = job_to_response(job)
            return {
                "success": True,
                "job_id": str(job.id),
                "status": job.status,
                "message": f"Discovery job {job.id} started successfully",
                "job": {
                    "id": str(job_response.id),
                    "job_type": job_response.job_type,
                    "status": job_response.status,
                    "params": job_response.params,
                    "created_at": job_response.created_at.isoformat() if job_response.created_at else None,
                    "updated_at": job_response.updated_at.isoformat() if job_response.updated_at else None
                }
            }
        except Exception as response_error:
            logger.error(f"Error creating response for job {job.id}: {response_error}", exc_info=True)
            # Return basic response even if serialization fails
            return {
                "success": True,
                "job_id": str(job.id),
                "status": "pending",
                "message": f"Discovery job {job.id} started successfully"
            }
    
    except HTTPException:
        # Re-raise HTTP exceptions (they're already properly formatted)
        raise
    except Exception as e:
        # Catch any other unexpected errors and return structured JSON
        logger.error(f"Unexpected error in create_discovery_job: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Internal server error: {str(e)}",
            "status_code": 500
        }


@router.get("/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user)  # REQUIRE AUTHENTICATION
):
    """
    Get the status of a job
    
    REQUIRES AUTHENTICATION: Valid JWT token must be provided
    """
    if not current_user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required"
        )
    
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return JobStatusResponse(
        id=job.id,
        job_type=job.job_type,
        status=job.status,
        params=job.params,
        result=job.result,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at
    )


@router.patch("/{job_id}/cancel")
async def cancel_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user)  # REQUIRE AUTHENTICATION
):
    """
    Cancel a running or pending job
    
    REQUIRES AUTHENTICATION: Valid JWT token must be provided
    """
    if not current_user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required"
        )
    
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Only allow cancelling pending or running jobs
    if job.status not in ["pending", "running"]:
        return {
            "success": False,
            "error": f"Cannot cancel job with status '{job.status}'. Only pending or running jobs can be cancelled.",
            "status": job.status
        }
    
    # Update job status to cancelled
    job.status = "cancelled"
    job.error_message = "Job cancelled by user"
    await db.commit()
    await db.refresh(job)
    
    logger.info(f"Job {job_id} cancelled by user {current_user}")
    
    return {
        "success": True,
        "message": f"Job {job_id} has been cancelled",
        "job": job_to_response(job)
    }


@router.get("")
async def list_jobs(
    skip: int = 0,
    limit: int = 50,
    job_type: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user)  # REQUIRE AUTHENTICATION
):
    """
    List all jobs with optional filtering
    
    REQUIRES AUTHENTICATION: Valid JWT token must be provided
    """
    if not current_user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required"
        )
    
    query = select(Job)
    if job_type:
        query = query.where(Job.job_type == job_type)
    if status:
        query = query.where(Job.status == status)
    
    query = query.order_by(Job.created_at.desc()).offset(skip).limit(limit)
    
    result = await db.execute(query)
    jobs = result.scalars().all()
    
    # Convert to response format safely
    job_responses = []
    for job in jobs:
        try:
            job_responses.append(job_to_response(job))
        except Exception as e:
            logger.warning(f"Error converting job {job.id} to response: {e}")
            # Skip this job but continue with others
    
    return job_responses


@router.post("/{job_id}/cancel")
async def cancel_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user)  # REQUIRE AUTHENTICATION
):
    """
    Cancel a running or pending job
    
    REQUIRES AUTHENTICATION: Valid JWT token must be provided
    """
    if not current_user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required"
        )
    
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status in ["running", "pending"]:
        job.status = "cancelled"
        job.error_message = "Job cancelled by user"
        from datetime import datetime, timezone
        job.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(job)
        logger.info(f"Job {job_id} cancelled by user.")
        return {"message": f"Job {job_id} cancelled successfully.", "status": "cancelled"}
    else:
        raise HTTPException(status_code=400, detail=f"Job {job_id} cannot be cancelled as its status is '{job.status}'.")


@router.post("/score", response_model=JobResponse)
async def create_scoring_job(
    prospect_ids: Optional[List[UUID]] = None,
    max_prospects: int = 1000,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user)  # REQUIRE AUTHENTICATION
):
    """
    Create a scoring job (not yet implemented)
    
    REQUIRES AUTHENTICATION: Valid JWT token must be provided
    """
    if not current_user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required"
        )
    
    raise HTTPException(status_code=501, detail="Scoring job not yet implemented in backend.")


@router.post("/send", response_model=JobResponse)
async def create_send_job(
    prospect_ids: Optional[List[UUID]] = None,
    max_prospects: int = 100,
    auto_send: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user)  # REQUIRE AUTHENTICATION
):
    """
    Create a job to send emails to prospects
    
    REQUIRES AUTHENTICATION: Valid JWT token must be provided
    """
    if not current_user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required"
        )
    
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
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user)  # REQUIRE AUTHENTICATION
):
    """
    Create a follow-up job (not yet implemented)
    
    REQUIRES AUTHENTICATION: Valid JWT token must be provided
    """
    if not current_user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required"
        )
    
    raise HTTPException(status_code=501, detail="Follow-up job not yet implemented in backend.")


@router.post("/check-replies")
async def check_replies(
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user)  # REQUIRE AUTHENTICATION
):
    """
    Manually trigger a reply check job (not yet implemented)
    
    REQUIRES AUTHENTICATION: Valid JWT token must be provided
    """
    if not current_user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required"
        )
    
    raise HTTPException(status_code=501, detail="Reply check job not yet implemented in backend.")
