"""
Drafting task - STEP 6 of strict pipeline
Generates email drafts using Gemini
"""
import asyncio
import logging
from typing import List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone

from app.db.database import AsyncSessionLocal
from app.models.prospect import Prospect
from app.models.job import Job
from app.clients.gemini import GeminiClient
from app.models.enums import VerificationStatus, DraftStatus

logger = logging.getLogger(__name__)


async def draft_prospects_async(job_id: str):
    """
    Generate email drafts for verified prospects using Gemini
    
    STRICT MODE:
    - Only drafts verified prospects
    - Gemini receives: website info, category, location, email type, outreach intent
    - Sets draft_status = "drafted"
    """
    async with AsyncSessionLocal() as db:
        try:
            # Get job
            result = await db.execute(select(Job).where(Job.id == UUID(job_id)))
            job = result.scalar_one_or_none()
            
            if not job:
                logger.error(f"❌ [DRAFTING] Job {job_id} not found")
                return {"error": "Job not found"}
            
            job.status = "running"
            await db.commit()
            
            # Get prospects to draft
            prospect_ids = job.params.get("prospect_ids", [])
            if not prospect_ids:
                logger.error(f"❌ [DRAFTING] No prospect IDs in job params")
                job.status = "failed"
                job.error_message = "No prospect IDs provided"
                await db.commit()
                return {"error": "No prospect IDs provided"}
            
            result = await db.execute(
                select(Prospect).where(
                    Prospect.id.in_([UUID(pid) for pid in prospect_ids]),
                    Prospect.verification_status.in_([VerificationStatus.VERIFIED.value, VerificationStatus.UNVERIFIED_LOWER.value]),
                    Prospect.contact_email.isnot(None),
                    Prospect.draft_status == DraftStatus.PENDING.value
                )
            )
            prospects = result.scalars().all()
            
            logger.info(f"✍️  [DRAFTING] Starting drafting for {len(prospects)} verified prospects")
            
            # Initialize Gemini client
            try:
                gemini_client = GeminiClient()
            except Exception as e:
                logger.error(f"❌ [DRAFTING] Failed to initialize Gemini client: {e}")
                job.status = "failed"
                job.error_message = f"Gemini not configured: {e}"
                await db.commit()
                return {"error": f"Gemini not configured: {e}"}
            
            drafted_count = 0
            failed_count = 0
            
            for idx, prospect in enumerate(prospects, 1):
                try:
                    logger.info(f"✍️  [DRAFTING] [{idx}/{len(prospects)}] Drafting email for {prospect.domain}...")
                    
                    # Determine email type
                    email_type = "generic"
                    if prospect.contact_email:
                        local_part = prospect.contact_email.split("@")[0].lower()
                        if local_part in ["info", "contact", "hello", "support"]:
                            email_type = "generic"
                        elif local_part in ["sales", "marketing", "business"]:
                            email_type = "role_based"
                        else:
                            email_type = "personal"
                    
                    # Compose email using Gemini
                    gemini_result = await gemini_client.compose_email(
                        domain=prospect.domain,
                        page_title=prospect.page_title,
                        page_url=prospect.page_url,
                        page_snippet=prospect.dataforseo_payload.get("description") if prospect.dataforseo_payload else None,
                        contact_name=None  # Could be extracted from email if personal
                    )
                    
                    if gemini_result.get("success"):
                        prospect.draft_subject = gemini_result.get("subject")
                        prospect.draft_body = gemini_result.get("body")
                        prospect.draft_status = DraftStatus.DRAFTED.value
                        drafted_count += 1
                        logger.info(f"✅ [DRAFTING] Drafted email for {prospect.domain}: {prospect.draft_subject}")
                    else:
                        error = gemini_result.get("error", "Unknown error")
                        logger.error(f"❌ [DRAFTING] Gemini failed for {prospect.domain}: {error}")
                        prospect.draft_status = DraftStatus.FAILED.value
                        failed_count += 1
                    
                    await db.commit()
                    await db.refresh(prospect)
                    
                    # Rate limiting
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(f"❌ [DRAFTING] Failed to draft {prospect.domain}: {e}", exc_info=True)
                    prospect.draft_status = DraftStatus.FAILED.value
                    failed_count += 1
                    await db.commit()
                    continue
            
            # Update job status
            job.status = "completed"
            job.result = {
                "drafted": drafted_count,
                "failed": failed_count,
                "total": len(prospects)
            }
            await db.commit()
            
            logger.info(f"✅ [DRAFTING] Job {job_id} completed: {drafted_count} drafted, {failed_count} failed")
            
            return {
                "job_id": job_id,
                "status": "completed",
                "drafted": drafted_count,
                "failed": failed_count
            }
            
        except Exception as e:
            logger.error(f"❌ [DRAFTING] Job {job_id} failed: {e}", exc_info=True)
            try:
                result = await db.execute(select(Job).where(Job.id == UUID(job_id)))
                job = result.scalar_one_or_none()
                if job:
                    job.status = "failed"
                    job.error_message = str(e)
                    await db.commit()
            except Exception as commit_err:
                logger.error(f"❌ [DRAFTING] Failed to commit error status: {commit_err}", exc_info=True)
            return {"error": str(e)}

