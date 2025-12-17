"""
Job management API endpoints
"""
import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional, Dict
from uuid import UUID
from datetime import datetime, timezone

from app.db.database import get_db
from app.api.auth import get_current_user_optional
from app.models.job import Job
from app.schemas.job import JobResponse, JobCreate, JobListResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=JobListResponse)
async def list_jobs(
    skip: int = 0,
    limit: int = 50,
    job_type: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    List all jobs with optional filtering
    """
    try:
        query = select(Job)
        
        # Apply filters
        if job_type:
            query = query.where(Job.job_type == job_type)
        if status:
            query = query.where(Job.status == status)
        
        # Get total count
        count_query = select(func.count()).select_from(Job)
        if job_type:
            count_query = count_query.where(Job.job_type == job_type)
        if status:
            count_query = count_query.where(Job.status == status)
        
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        # Apply pagination
        query = query.order_by(Job.created_at.desc())
        query = query.offset(skip).limit(limit)
        
        result = await db.execute(query)
        jobs = result.scalars().all()
        
        return {
            "data": [JobResponse.model_validate(job) for job in jobs],
            "total": total,
            "skip": skip,
            "limit": limit
        }
    except Exception as e:
        logger.error(f"Error listing jobs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list jobs: {str(e)}")


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Get a specific job by ID
    """
    try:
        result = await db.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return JobResponse.model_validate(job)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get job: {str(e)}")


@router.post("/cancel/{job_id}")
async def cancel_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Cancel a running or pending job
    """
    try:
        result = await db.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        if job.status not in ["pending", "running"]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot cancel job with status '{job.status}'. Only pending or running jobs can be cancelled."
            )
        
        # Cancel the background task if it exists
        try:
            from app.task_manager import unregister_task, get_task
            task = get_task(str(job.id))
            if task:
                task.cancel()
                unregister_task(str(job.id))
                logger.info(f"Cancelled background task for job {job.id}")
        except Exception as task_err:
            logger.warning(f"Error cancelling background task for job {job.id}: {task_err}")
        
        # Update job status
        job.status = "cancelled"
        job.error_message = "Job cancelled by user"
        await db.commit()
        await db.refresh(job)
        
        return {
            "success": True,
            "message": f"Job {job_id} cancelled successfully",
            "job": JobResponse.model_validate(job)
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error cancelling job {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to cancel job: {str(e)}")


@router.post("", response_model=JobResponse)
async def create_job(
    job: JobCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Create a new discovery job
    """
    try:
        # Create job record
        new_job = Job(
            job_type=job.job_type,
            params=job.params,
            status="pending"
        )
        db.add(new_job)
        await db.commit()
        await db.refresh(new_job)
        
        logger.info(f"Created {job.job_type} job {new_job.id} with params: {job.params}")
        
        # Import task processing function based on job type
        if job.job_type == "discover":
            try:
                from app.tasks.discovery import discover_websites_async
                process_discovery_job = discover_websites_async
            except ImportError as import_err:
                logger.error(f"Failed to import discovery task: {import_err}", exc_info=True)
                new_job.status = "failed"
                new_job.error_message = f"Unable to import discovery task module: {import_err}"
                await db.commit()
                await db.refresh(new_job)
                return {
                    "success": False,
                    "error": "Unable to import discovery task module. Please contact support.",
                    "status_code": 500,
                    "job_id": str(new_job.id)
                }
            
            # Start background task to process job
            # This runs asynchronously without blocking the API response
            try:
                from app.task_manager import register_task, unregister_task
                from app.db.database import AsyncSessionLocal
                
                async def task_wrapper():
                    """Wrapper to register/unregister task and handle cancellation"""
                    task = asyncio.create_task(process_discovery_job(str(new_job.id)))
                    register_task(str(new_job.id), task)
                    try:
                        await task
                    except asyncio.CancelledError:
                        logger.info(f"Discovery job {new_job.id} task was cancelled")
                        # Update job status in database
                        async with AsyncSessionLocal() as task_db:
                            result = await task_db.execute(select(Job).where(Job.id == new_job.id))
                            task_job = result.scalar_one_or_none()
                            if task_job:
                                task_job.status = "cancelled"
                                task_job.error_message = "Job cancelled by user"
                                await task_db.commit()
                    finally:
                        unregister_task(str(new_job.id))
                
                asyncio.create_task(task_wrapper())
                logger.info(f"Discovery job {new_job.id} started in background")
            except Exception as task_error:
                # Task creation failed - update job status immediately
                logger.error(f"Failed to create background task for job {new_job.id}: {task_error}", exc_info=True)
                new_job.status = "failed"
                new_job.error_message = f"Failed to start background task: {task_error}"
                await db.commit()
                await db.refresh(new_job)
        elif job.job_type == "enrich":
            try:
                from app.tasks.enrichment import process_enrichment_job
                # Start enrichment task in background
                asyncio.create_task(process_enrichment_job(str(new_job.id)))
                logger.info(f"Enrichment job {new_job.id} started in background")
            except Exception as task_error:
                logger.error(f"Failed to create enrichment task for job {new_job.id}: {task_error}", exc_info=True)
                new_job.status = "failed"
                new_job.error_message = f"Failed to start enrichment task: {task_error}"
                await db.commit()
                await db.refresh(new_job)
        elif job.job_type == "send":
            try:
                from app.tasks.send import process_send_job
                # Start send task in background
                asyncio.create_task(process_send_job(str(new_job.id)))
                logger.info(f"Send job {new_job.id} started in background")
            except Exception as task_error:
                logger.error(f"Failed to create send task for job {new_job.id}: {task_error}", exc_info=True)
                new_job.status = "failed"
                new_job.error_message = f"Failed to start send task: {task_error}"
                await db.commit()
                await db.refresh(new_job)
        
        return JobResponse.model_validate(new_job)
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create job: {str(e)}")
