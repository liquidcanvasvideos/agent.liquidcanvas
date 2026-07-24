"""
Social Send Task - processes social outreach sending jobs.
"""
import asyncio
import logging
import os
from typing import Dict, Any, List
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy import select
from app.db.database import AsyncSessionLocal
from app.models.prospect import Prospect, SendStatus
from app.models.job import Job
from app.services.social.sending import SocialSendingService
from app.task_manager import unregister_task

logger = logging.getLogger(__name__)


def _append_job_event(job: Job, message: str, *, level: str = "info", max_events: int = 50):
    result = job.result if isinstance(job.result, dict) else {}
    events = result.get("events")
    if not isinstance(events, list):
        events = []
    events.append({"level": level, "message": message})
    if len(events) > max_events:
        events = events[-max_events:]
    result["events"] = events
    result["current_action"] = message
    if level in {"error", "warning"}:
        result["last_error"] = message
    job.result = result

async def process_social_send_job(job_id: str) -> Dict[str, Any]:
    """
    Process social send job to send messages via platform-specific adapters.
    """
    async with AsyncSessionLocal() as db:
        job: Job | None = None
        try:
            # Get job
            result = await db.execute(select(Job).where(Job.id == UUID(job_id)))
            job = result.scalar_one_or_none()
            
            if not job:
                logger.error(f"❌ Social send job {job_id} not found")
                return {"error": "Job not found"}
            
            job.status = "running"
            job.result = {
                "sent": 0,
                "failed": 0,
                "total": 0,
                "current": 0,
                "current_username": None,
                "current_platform": None,
                "current_action": "Starting social send",
                "last_error": None,
                "events": [{"level": "info", "message": "Job started"}],
            }
            await db.commit()
            
            logger.info(f"📧 [SOCIAL SEND] Starting social send job {job_id}...")
            
            # Get job parameters
            params = job.params or {}
            prospect_ids = params.get("prospect_ids")
            max_prospects = params.get("max_prospects", 100)

            _append_job_event(job, "Loading send targets")
            await db.commit()
            
            # Build query for social prospects ready for sending
            query = select(Prospect).where(
                Prospect.source_type == 'social',
                Prospect.draft_subject.isnot(None),
                Prospect.draft_body.isnot(None),
                Prospect.send_status != SendStatus.SENT.value
            )
            
            if prospect_ids:
                query = query.where(Prospect.id.in_([UUID(pid) for pid in prospect_ids]))
            
            query = query.limit(max_prospects)
            
            result = await db.execute(query)
            prospects = result.scalars().all()

            _append_job_event(job, f"Loaded {len(prospects)} send targets")
            job.result = {**(job.result or {}), "total": len(prospects)}
            await db.commit()
            
            logger.info(f"📧 Found {len(prospects)} social prospects to send messages to...")
            
            if len(prospects) == 0:
                job.status = "completed"
                job.result = {
                    "sent": 0,
                    "failed": 0,
                    "message": "No social prospects found with pending drafts"
                }
                await db.commit()
                return job.result

            # Initialize Social Sending Service
            sending_service = SocialSendingService()
            
            sent_count = 0
            failed_count = 0
            per_prospect_timeout_seconds = int(os.getenv("SOCIAL_SEND_PER_PROSPECT_TIMEOUT_SECONDS", "0"))
            overall_timeout_seconds = int(os.getenv("SOCIAL_SEND_OVERALL_TIMEOUT_SECONDS", "0"))
            started_monotonic = asyncio.get_running_loop().time()

            _append_job_event(job, "Beginning send loop")
            await db.commit()
            
            for idx, prospect in enumerate(prospects, 1):
                try:
                    # Overall timeout guard (protects against endless running jobs)
                    elapsed = asyncio.get_running_loop().time() - started_monotonic
                    if overall_timeout_seconds > 0 and elapsed > overall_timeout_seconds:
                        raise asyncio.TimeoutError(
                            f"Overall social send job timed out after {overall_timeout_seconds}s"
                        )

                    logger.info(f"📧 [SOCIAL SEND] [{idx}/{len(prospects)}] Sending to @{prospect.username} on {prospect.source_platform}")

                    _append_job_event(job, f"Sending to @{prospect.username} on {prospect.source_platform}")

                    if job:
                        job.result = {
                            "sent": sent_count,
                            "failed": failed_count,
                            "total": len(prospects),
                            "current": idx,
                            "current_username": prospect.username,
                            "current_platform": prospect.source_platform,
                            "current_action": (job.result or {}).get("current_action"),
                            "last_error": (job.result or {}).get("last_error"),
                            "events": (job.result or {}).get("events"),
                        }
                        await db.commit()
                    
                    # Convert Prospect to SocialProfile-like object for the service
                    # Since we are reusing the Prospect table, we pass it directly
                    # but the service expects SocialProfile fields. 
                    # Our current DB setup uses Prospect table for social too.
                    
                    # Call sending service
                    # Note: We need to adapt the service to handle Prospect model 
                    # if it's currently hardcoded for SocialProfile
                    send_coro = sending_service.send_message(
                        profile=prospect,
                        draft_body=prospect.draft_body,
                        db=db,
                    )
                    if per_prospect_timeout_seconds > 0:
                        result = await asyncio.wait_for(
                            send_coro,
                            timeout=per_prospect_timeout_seconds,
                        )
                    else:
                        result = await send_coro
                    
                    if result.get("success"):
                        sent_count += 1
                        prospect.send_status = SendStatus.SENT.value
                        prospect.last_sent = datetime.now(timezone.utc)
                        _append_job_event(job, f"Sent to @{prospect.username} on {prospect.source_platform}")
                    else:
                        failed_count += 1
                        logger.warning(f"⚠️ [SOCIAL SEND] Failed to send to @{prospect.username}: {result.get('error')}")
                        _append_job_event(
                            job,
                            f"Failed to send to @{prospect.username} on {prospect.source_platform}: {result.get('error')}",
                            level="error",
                        )
                    
                    if job:
                        job.result = {
                            "sent": sent_count,
                            "failed": failed_count,
                            "total": len(prospects),
                            "current": idx,
                            "current_username": prospect.username,
                            "current_platform": prospect.source_platform,
                            "current_action": (job.result or {}).get("current_action"),
                            "last_error": (job.result or {}).get("last_error"),
                            "events": (job.result or {}).get("events"),
                        }
                    await db.commit()
                    
                except asyncio.TimeoutError:
                    logger.error(
                        f"⏱️  [SOCIAL SEND] Timeout sending to @{prospect.username} on {prospect.source_platform}"
                    )
                    failed_count += 1
                    if job:
                        job.error_message = (
                            f"Timeout sending to @{prospect.username} on {prospect.source_platform}"
                        )
                        _append_job_event(job, job.error_message, level="error")
                        job.result = {
                            "sent": sent_count,
                            "failed": failed_count,
                            "total": len(prospects),
                            "current": idx,
                            "current_username": prospect.username,
                            "current_platform": prospect.source_platform,
                            "current_action": (job.result or {}).get("current_action"),
                            "last_error": (job.result or {}).get("last_error"),
                            "events": (job.result or {}).get("events"),
                        }
                    await db.commit()
                except Exception as e:
                    logger.error(f"❌ [SOCIAL SEND] Error processing @{prospect.username}: {e}")
                    failed_count += 1
                    if job:
                        _append_job_event(
                            job,
                            f"Exception sending to @{prospect.username} on {prospect.source_platform}: {str(e)}",
                            level="error",
                        )
                        await db.commit()
                    continue
            
            job.status = "completed"
            job.result = {
                "sent": sent_count,
                "failed": failed_count,
                "total": len(prospects),
                "current": len(prospects),
                "current_username": None,
                "current_platform": None,
                "current_action": "Completed",
                "last_error": (job.result or {}).get("last_error"),
                "events": (job.result or {}).get("events"),
            }
            await db.commit()
            
            logger.info(f"✅ [SOCIAL SEND] Job {job_id} complete. Sent: {sent_count}, Failed: {failed_count}")
            return job.result
            
        except Exception as e:
            logger.error(f"❌ Social send job {job_id} failed: {e}", exc_info=True)
            if job:
                job.status = "failed"
                job.error_message = str(e)
                job.result = job.result or {
                    "sent": 0,
                    "failed": 0,
                    "total": 0,
                    "current": 0,
                    "current_username": None,
                    "current_platform": None,
                }
                await db.commit()
            return {"error": str(e)}
        finally:
            try:
                unregister_task(job_id)
            except Exception:
                # best-effort cleanup
                pass
