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
            
            logger.info(f"📧 Starting send job {job_id}...")
            
            # Get job parameters
            params = job.params or {}
            prospect_ids = params.get("prospect_ids")
            max_prospects = params.get("max_prospects", 100)
            auto_send = params.get("auto_send", False)
            
            # Build query for prospects with emails that haven't been sent
            query = select(Prospect).where(
                Prospect.contact_email.isnot(None),
                Prospect.outreach_status == "pending"
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
            
            # Send to each prospect
            for idx, prospect in enumerate(prospects, 1):
                try:
                    # Get or compose email
                    subject = prospect.draft_subject
                    body = prospect.draft_body
                    
                    # If no draft and auto_send is enabled, compose email
                    if (not subject or not body) and gemini_client:
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
                            subject = gemini_result.get("subject")
                            body = gemini_result.get("body")
                            prospect.draft_subject = subject
                            prospect.draft_body = body
                            logger.info(f"✅ [{idx}/{len(prospects)}] Email composed for {prospect.domain}")
                        else:
                            error_msg = gemini_result.get('error', 'Unknown error')
                            logger.warning(f"⚠️  [{idx}/{len(prospects)}] Failed to compose email for {prospect.domain}: {error_msg}")
                            failed_count += 1
                            continue
                    elif not subject or not body:
                        logger.warning(f"⚠️  [{idx}/{len(prospects)}] No draft email for {prospect.domain} and auto_send is False")
                        skipped_count += 1
                        continue
                    
                    # Send email
                    logger.info(f"📧 [{idx}/{len(prospects)}] Sending email to {prospect.contact_email}...")
                    send_result = await gmail_client.send_email(
                        to_email=prospect.contact_email,
                        subject=subject,
                        body=body
                    )
                    
                    if send_result.get("success"):
                        # Create email log
                        email_log = EmailLog(
                            prospect_id=prospect.id,
                            subject=subject,
                            body=body,
                            response=send_result
                        )
                        db.add(email_log)
                        
                        # Update prospect
                        prospect.outreach_status = "sent"
                        prospect.last_sent = datetime.now(timezone.utc)
                        sent_count += 1
                        logger.info(f"✅ [{idx}/{len(prospects)}] Email sent to {prospect.contact_email}")
                    else:
                        error_msg = send_result.get('error', 'Unknown error')
                        logger.error(f"❌ [{idx}/{len(prospects)}] Failed to send email to {prospect.contact_email}: {error_msg}")
                        failed_count += 1
                    
                    await db.commit()
                    await db.refresh(prospect)
                    
                    # Rate limiting (1 email per 2 seconds to avoid Gmail rate limits)
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    logger.error(f"❌ [{idx}/{len(prospects)}] Error sending to {prospect.contact_email}: {e}", exc_info=True)
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
            
            logger.info(f"✅ Send job {job_id} completed:")
            logger.info(f"   📊 Sent: {sent_count}, Failed: {failed_count}, Skipped: {skipped_count}")
            
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

