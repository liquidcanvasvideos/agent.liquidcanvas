"""
Send task - sends emails to prospects via Gmail API
Runs directly in backend (no external worker needed for free tier)
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.database import AsyncSessionLocal
from app.models.prospect import Prospect
from app.models.job import Job
from app.models.email_log import EmailLog
from app.clients.gmail import GmailClient
from app.clients.gemini import GeminiClient

logger = logging.getLogger(__name__)


async def process_send_job(job_id: str) -> Dict[str, Any]:
    """
    Process send job to send emails to prospects via Gmail API
    
    Args:
        job_id: UUID of the job to process
        
    Returns:
        Dict with job results or error
    """
    async with AsyncSessionLocal() as db:
        try:
            # Get job
            from sqlalchemy import select
            result = await db.execute(select(Job).where(Job.id == job_id))
            job = result.scalar_one_or_none()
            
            if not job:
                logger.error(f"❌ Send job {job_id} not found")
                return {"error": "Job not found"}
            
            job.status = "running"
            await db.commit()
            await db.refresh(job)
            
            import time
            send_start_time = time.time()
            
            logger.info(f"📧 [SEND] Starting send job {job_id}...")
            
            # Get job parameters
            params = job.params or {}
            prospect_ids = params.get("prospect_ids")
            cc_map = params.get("cc_map") or {}
            max_prospects = params.get("max_prospects", 100)
            auto_send = params.get("auto_send", False)
            
            logger.info(f"📥 [SEND] Input - prospect_ids: {prospect_ids}, max_prospects: {max_prospects}, auto_send: {auto_send}")
            
            # Build query for prospects ready for sending (matches pipeline endpoint criteria)
            from app.models.prospect import VerificationStatus, SendStatus
            query = select(Prospect).where(
                Prospect.contact_email.isnot(None),
                Prospect.verification_status == VerificationStatus.VERIFIED.value,
                Prospect.draft_subject.isnot(None),
                Prospect.draft_body.isnot(None),
                Prospect.send_status != SendStatus.SENT.value
            )
            
            if prospect_ids:
                query = query.where(Prospect.id.in_([UUID(pid) for pid in prospect_ids]))
            
            query = query.limit(max_prospects)
            
            result = await db.execute(query)
            prospects = result.scalars().all()
            
            logger.info(f"📧 Found {len(prospects)} prospects to send emails to...")
            
            if len(prospects) == 0:
                job.status = "completed"
                job.result = {
                    "emails_sent": 0,
                    "emails_failed": 0,
                    "total_processed": 0,
                    "message": "No prospects found with emails and pending status"
                }
                await db.commit()
                return {
                    "job_id": job_id,
                    "status": "completed",
                    "emails_sent": 0,
                    "message": "No prospects to send"
                }
            
            # Initialize Gmail client (required)
            try:
                gmail_client = GmailClient()
            except ValueError as e:
                job.status = "failed"
                job.error_message = f"Gmail not configured: {e}"
                await db.commit()
                logger.error(f"❌ Gmail client initialization failed: {e}")
                return {"error": str(e)}
            
            # Initialize Gemini client (optional, only if auto_send)
            gemini_client = None
            if auto_send:
                try:
                    gemini_client = GeminiClient()
                except ValueError as e:
                    logger.warning(f"⚠️  Gemini not configured, will use draft emails only: {e}")
                    # Don't fail job if Gemini is not configured - can still use drafts
            
            sent_count = 0
            failed_count = 0
            skipped_count = 0
            
            # Send to each prospect with comprehensive logging
            for idx, prospect in enumerate(prospects, 1):
                prospect_start_time = time.time()
                try:
                    logger.info(f"📧 [SEND] [{idx}/{len(prospects)}] Processing {prospect.domain} ({prospect.contact_email})")
                    logger.info(f"📥 [SEND] Input - prospect_id: {prospect.id}, email: {prospect.contact_email}, has_draft: {bool(prospect.draft_subject and prospect.draft_body)}")
                    
                    # Validate prospect has draft before sending
                    # The shared send service will validate draft_subject and draft_body exist
                    # If no draft and auto_send is enabled, compose email first
                    if (not prospect.draft_subject or not prospect.draft_body) and gemini_client:
                        logger.info(f"📝 [{idx}/{len(prospects)}] Composing email for {prospect.domain}...")
                        
                        # Extract context for email composition
                        page_snippet = None
                        if prospect.dataforseo_payload:
                            page_snippet = prospect.dataforseo_payload.get("description") or prospect.dataforseo_payload.get("snippet")
                        
                        contact_name = None
                        if prospect.hunter_payload and prospect.hunter_payload.get("emails"):
                            emails = prospect.hunter_payload["emails"]
                            if emails and len(emails) > 0:
                                first_email = emails[0]
                                first_name = first_email.get("first_name")
                                last_name = first_email.get("last_name")
                                if first_name or last_name:
                                    contact_name = f"{first_name or ''} {last_name or ''}".strip()
                        
                        # Compose email using Gemini
                        gemini_result = await gemini_client.compose_email(
                            domain=prospect.domain,
                            page_title=prospect.page_title,
                            page_url=prospect.page_url,
                            page_snippet=page_snippet,
                            contact_name=contact_name
                        )
                        
                        if gemini_result.get("success"):
                            prospect.draft_subject = gemini_result.get("subject")
                            prospect.draft_body = gemini_result.get("body")
                            await db.commit()
                            await db.refresh(prospect)
                            logger.info(f"✅ [{idx}/{len(prospects)}] Email composed for {prospect.domain}")
                        else:
                            error_msg = gemini_result.get('error', 'Unknown error')
                            logger.warning(f"⚠️  [{idx}/{len(prospects)}] Failed to compose email for {prospect.domain}: {error_msg}")
                            failed_count += 1
                            continue
                    elif not prospect.draft_subject or not prospect.draft_body:
                        logger.warning(f"⚠️  [{idx}/{len(prospects)}] No draft email for {prospect.domain} and auto_send is False")
                        skipped_count += 1
                        continue
                    
                    # Send email using shared service (same logic as manual send)
                    send_start = time.time()
                    logger.info(f"📧 [SEND] [{idx}/{len(prospects)}] Sending email to {prospect.contact_email}...")
                    
                    try:
                        from app.services.email_sender import send_prospect_email
                        cc_value = None
                        try:
                            cc_value = cc_map.get(str(prospect.id))
                        except Exception:
                            cc_value = None

                        send_result = await send_prospect_email(prospect, db, gmail_client, cc=cc_value)
                        send_time = (time.time() - send_start) * 1000
                        logger.info(f"⏱️  [SEND] Gmail API call completed in {send_time:.0f}ms")
                        
                        sent_count += 1
                        total_time = (time.time() - prospect_start_time) * 1000
                        logger.info(f"✅ [SEND] [{idx}/{len(prospects)}] Email sent to {prospect.contact_email} in {total_time:.0f}ms")
                        logger.info(f"📤 [SEND] Output - status: sent, message_id: {send_result.get('message_id', 'N/A')}")
                    except ValueError as val_err:
                        # Validation errors (prospect not sendable)
                        send_time = (time.time() - send_start) * 1000
                        total_time = (time.time() - prospect_start_time) * 1000
                        logger.warning(f"⚠️  [SEND] [{idx}/{len(prospects)}] Skipping {prospect.contact_email} after {total_time:.0f}ms: {val_err}")
                        skipped_count += 1
                        continue
                    except Exception as send_err:
                        send_time = (time.time() - send_start) * 1000
                        total_time = (time.time() - prospect_start_time) * 1000
                        logger.error(f"❌ [SEND] [{idx}/{len(prospects)}] Failed to send email to {prospect.contact_email} after {total_time:.0f}ms: {send_err}", exc_info=True)
                        logger.error(f"📤 [SEND] Output - error: {str(send_err)}")
                        failed_count += 1
                        continue
                    
                    # Note: send_prospect_email already commits and refreshes prospect
                    
                    # Rate limiting (1 email per 2 seconds to avoid Gmail rate limits)
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    total_time = (time.time() - prospect_start_time) * 1000
                    logger.error(f"❌ [SEND] [{idx}/{len(prospects)}] Error sending to {prospect.contact_email} after {total_time:.0f}ms: {e}", exc_info=True)
                    logger.error(f"📤 [SEND] Output - error: {str(e)}, stack_trace: {type(e).__name__}")
                    failed_count += 1
                    continue
            
            # Update job status
            job.status = "completed"
            job.result = {
                "emails_sent": sent_count,
                "emails_failed": failed_count,
                "emails_skipped": skipped_count,
                "total_processed": len(prospects)
            }
            await db.commit()
            
            total_time = (time.time() - send_start_time) / 60
            logger.info(f"✅ [SEND] Job {job_id} completed in {total_time:.1f} minutes")
            logger.info(f"📤 [SEND] Output - Sent: {sent_count}, Failed: {failed_count}, Skipped: {skipped_count}, Total: {len(prospects)}")
            
            return {
                "job_id": job_id,
                "status": "completed",
                "emails_sent": sent_count,
                "emails_failed": failed_count,
                "emails_skipped": skipped_count,
                "total_processed": len(prospects)
            }
            
        except Exception as e:
            logger.error(f"❌ Send job {job_id} failed: {e}", exc_info=True)
            try:
                result = await db.execute(select(Job).where(Job.id == job_id))
                job = result.scalar_one_or_none()
                if job:
                    job.status = "failed"
                    job.error_message = str(e)
                    await db.commit()
            except:
                pass
            return {"error": str(e)}

