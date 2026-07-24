"""
Task manager to track and cancel running asyncio tasks
"""
import asyncio
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

# Global dictionary to store running tasks by job_id
_running_tasks: Dict[str, asyncio.Task] = {}


def register_task(job_id: str, task: asyncio.Task):
    """Register a running task for a job"""
    _running_tasks[job_id] = task
    logger.info(f"Registered task for job {job_id} (task_id: {id(task)})")


def cancel_task(job_id: str) -> bool:
    """
    Cancel a running task for a job
    
    Returns:
        True if task was found and cancelled, False otherwise
    """
    task = _running_tasks.get(job_id)
    if task and not task.done():
        logger.info(f"Cancelling task for job {job_id} (task_id: {id(task)})")
        task.cancel()
        return True
    elif task and task.done():
        # Task already completed, remove from tracking
        del _running_tasks[job_id]
        logger.info(f"Task for job {job_id} already completed, removed from tracking")
        return False
    else:
        logger.warning(f"No running task found for job {job_id}")
        return False


def unregister_task(job_id: str):
    """Remove a task from tracking (called when task completes)"""
    if job_id in _running_tasks:
        del _running_tasks[job_id]
        logger.debug(f"Unregistered task for job {job_id}")


def get_running_task(job_id: str) -> Optional[asyncio.Task]:
    """Get the running task for a job if it exists"""
    return _running_tasks.get(job_id)


async def process_job(job):
    if job.job_type == "send":
        result = await process_send_job(str(job.id))
    elif job.job_type == "social_send":
        from app.tasks.social_send import process_social_send_job
        result = await process_social_send_job(str(job.id))
    elif job.job_type == "discovery":
        result = await process_discovery_job(str(job.id))
    return result
