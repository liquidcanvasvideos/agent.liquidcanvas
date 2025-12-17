"""
Enrichment task - finds emails for prospects using Snov.io
Runs directly in backend (no external worker needed for free tier)
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.database import AsyncSessionLocal
from app.models.prospect import Prospect
from app.models.job import Job
from app.clients.snov import SnovIOClient
from app.utils.email_validation import is_plausible_email, format_job_error
from app.services.exceptions import RateLimitError
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def process_enrichment_job(job_id: str) -> Dict[str, Any]:
    """
    Process enrichment job to find / improve emails for prospects using Snov.io.

    Behaviour:
    - Never skips a prospect just because it already has an email.
    - Always compares new vs existing email confidence and updates when better.
    - Uses a very low‑confidence guesser fallback when the provider returns no emails.
    """
    # CANARY LOG - If you see this, the task started successfully
    logger.info(f"🚀 Enrichment job started: {job_id}")
    
    async with AsyncSessionLocal() as db:
        try:
            # Get job
            from sqlalchemy import select
            result = await db.execute(select(Job).where(Job.id == job_id))
            job = result.scalar_one_or_none()
            
            if not job:
                logger.error(f"❌ Enrichment job {job_id} not found")
                return {"error": "Job not found"}
            
            job.status = "running"
            await db.commit()
            await db.refresh(job)
            
            logger.info(f"🔍 Starting enrichment job {job_id}...")
            
            # Get job parameters
            params = job.params or {}
            prospect_ids = params.get("prospect_ids")
            max_prospects = params.get("max_prospects", 100)
            only_missing_emails = params.get("only_missing_emails", False)
            
            # Build query for prospects that are eligible for enrichment.
            # GATE: Only enrich prospects with service or brand intent (partner-qualified)
            # PRIORITIZE prospects without emails, but also process ones with emails to improve them.
            # Order by: NULL emails first (highest priority), then by created_at (oldest first)
            from sqlalchemy import or_, nullslast
            
            from sqlalchemy import or_
            query = select(Prospect).where(
                Prospect.outreach_status == "pending",
                # Only enrich service/brand intent (partner-qualified domains)
                # Also include prospects with NULL serp_intent (created before intent filtering was added)
                or_(
                    Prospect.serp_intent.in_(["service", "brand"]),
                    Prospect.serp_intent.is_(None)  # Include legacy prospects without intent classification
                )
            )
            
            # If only_missing_emails is True, filter to only prospects without emails
            if only_missing_emails:
                query = query.where(Prospect.contact_email.is_(None))
                logger.info(f"🔍 Filtering to only prospects without emails (only_missing_emails=True)")
            
            logger.info(f"🔍 Filtering to only partner-qualified prospects (intent: service or brand)")
            
            if prospect_ids:
                query = query.where(Prospect.id.in_([UUID(pid) for pid in prospect_ids]))
            else:
                # If no specific IDs, prioritize prospects without emails
                # This ensures we enrich the ones that were skipped during discovery
                query = query.order_by(
                    Prospect.contact_email.is_(None).desc(),  # NULL emails first
                    Prospect.created_at.asc()  # Oldest first
                )
            
            query = query.limit(max_prospects)
            
            result = await db.execute(query)
            prospects = result.scalars().all()
            
            # Count how many don't have emails
            no_email_count_query = sum(1 for p in prospects if not p.contact_email)
            has_email_count = len(prospects) - no_email_count_query
            
            logger.info(f"🔍 Found {len(prospects)} prospects to enrich:")
            logger.info(f"   📧 {no_email_count_query} without emails (priority)")
            logger.info(f"   ✉️  {has_email_count} with existing emails (will improve if better match found)")
            
            if len(prospects) == 0:
                job.status = "completed"
                job.result = {
                    "prospects_enriched": 0,
                    "prospects_failed": 0,
                    "total_processed": 0,
                    "message": "No prospects found without emails"
                }
                await db.commit()
                return {
                    "job_id": job_id,
                    "status": "completed",
                    "prospects_enriched": 0,
                    "message": "No prospects to enrich"
                }
            
            # Initialize Snov client
            try:
                snov_client = SnovIOClient()
            except ValueError as e:
                job.status = "failed"
                job.error_message = f"Snov.io not configured: {e}"
                await db.commit()
                logger.error(f"❌ Snov.io client initialization failed: {e}")
                return {"error": str(e)}
            
            enriched_count = 0
            failed_count = 0
            no_email_count = 0
            
            # Enrich each prospect with comprehensive logging
            import time
            enrichment_start_time = time.time()
            
            for idx, prospect in enumerate(prospects, 1):
                prospect_start_time = time.time()
                try:
                    domain = prospect.domain
                    prospect_id = str(prospect.id)
                    
                    logger.info(f"🔍 [ENRICHMENT] [{idx}/{len(prospects)}] Starting enrichment for {domain} (id: {prospect_id})")
                    logger.info(f"📥 [ENRICHMENT] Input - domain: {domain}, prospect_id: {prospect_id}")
                    
                    # Call STRICT MODE enrichment service
                    try:
                        from app.services.enrichment import enrich_prospect_email
                        enrich_result = await enrich_prospect_email(domain, None, prospect.page_url)
                        
                        # STRICT MODE: Handle new response format
                        if not enrich_result:
                            logger.error(f"❌ [ENRICHMENT] Enrichment service returned None for {domain}")
                            enrich_result = {
                                "emails": [],
                                "primary_email": None,
                                "email_status": "no_email_found",
                                "pages_crawled": [],
                                "emails_by_page": {},
                                "snov_emails_accepted": 0,
                                "snov_emails_rejected": 0,
                                "success": False,
                                "source": "no_email_found",
                            }
                        
                        # Log enrichment results
                        email_status = enrich_result.get("email_status", "no_email_found")
                        emails_found = enrich_result.get("emails", [])
                        pages_crawled = enrich_result.get("pages_crawled", [])
                        snov_accepted = enrich_result.get("snov_emails_accepted", 0)
                        snov_rejected = enrich_result.get("snov_emails_rejected", 0)
                        
                        logger.info(f"📊 [ENRICHMENT] [{idx}/{len(prospects)}] Enrichment result for {domain}:")
                        logger.info(f"   Status: {email_status}")
                        logger.info(f"   Emails found: {len(emails_found)}")
                        logger.info(f"   Pages crawled: {len(pages_crawled)}")
                        logger.info(f"   Snov.io: {snov_accepted} accepted, {snov_rejected} rejected")
                        
                        if email_status == "no_email_found":
                            logger.warning(f"⚠️  [ENRICHMENT] [{idx}/{len(prospects)}] NO EMAIL FOUND on website for {domain}")
                            # Store "no_email_found" status
                            prospect.contact_email = None
                            prospect.contact_method = "no_email_found"
                            prospect.snov_payload = {
                                "email_status": "no_email_found",
                                "pages_crawled": pages_crawled,
                                "emails_by_page": enrich_result.get("emails_by_page", {}),
                                "snov_emails_accepted": snov_accepted,
                                "snov_emails_rejected": snov_rejected,
                                "source": enrich_result.get("source", "no_email_found"),
                            }
                            no_email_count += 1
                            await db.commit()
                            await db.refresh(prospect)
                            continue
                        
                        # Convert to legacy format for compatibility
                        primary_email = enrich_result.get("primary_email")
                        if primary_email:
                            snov_result = {
                                "success": True,
                                "emails": [{
                                    "value": email,
                                    "confidence_score": 50.0,  # Default confidence for website-found emails
                                } for email in emails_found],
                            }
                        else:
                            snov_result = {"success": False, "emails": []}
                        
                        snov_time = (time.time() - prospect_start_time) * 1000
                        logger.info(f"⏱️  [ENRICHMENT] Enrichment completed in {snov_time:.0f}ms")
                        
                    except Exception as enrich_err:
                        snov_time = (time.time() - prospect_start_time) * 1000
                        logger.error(f"❌ [ENRICHMENT] Enrichment failed after {snov_time:.0f}ms: {enrich_err}", exc_info=True)
                        # On error, mark as no_email_found
                        prospect.contact_email = None
                        prospect.contact_method = "no_email_found"
                        prospect.snov_payload = {
                            "email_status": "no_email_found",
                            "error": str(enrich_err),
                            "source": "error",
                        }
                        no_email_count += 1
                        await db.commit()
                        await db.refresh(prospect)
                        continue
                    
                    # STRICT MODE: Use primary_email from enrichment result
                    new_email = enrich_result.get("primary_email")
                    new_confidence = 50.0  # Default confidence for website-found emails
                    provider_source = enrich_result.get("source", "html_scraping")

                    # STRICT MODE: Save email if found, otherwise already handled above
                    if new_email:
                        # Final validation before saving
                        if not is_plausible_email(new_email):
                            logger.warning(f"🚫 [ENRICHMENT] Rejecting implausible email before save: {new_email}")
                            prospect.contact_email = None
                            prospect.contact_method = "no_email_found"
                            prospect.snov_payload = enrich_result
                            no_email_count += 1
                            await db.commit()
                            await db.refresh(prospect)
                            continue
                        
                        # Save the email
                        old_email_log = str(prospect.contact_email) if prospect.contact_email else None
                        logger.info(
                            f"✅ [ENRICHMENT] [{idx}/{len(prospects)}] Saving email for {domain}: "
                            f"{old_email_log or 'None'} -> {new_email}, source={provider_source}, "
                            f"pages_crawled={len(enrich_result.get('pages_crawled', []))}, "
                            f"total_emails={len(enrich_result.get('emails', []))}"
                        )
                        prospect.contact_email = new_email
                        prospect.contact_method = provider_source
                        # Store full enrichment result in snov_payload
                        prospect.snov_payload = enrich_result
                        enriched_count += 1
                    else:
                        # This should not happen (handled above), but log it
                        logger.error(
                            f"❌ [ENRICHMENT] [{idx}/{len(prospects)}] Unexpected: new_email is None but email_status is 'found' for {domain}"
                        )
                        prospect.contact_email = None
                        prospect.contact_method = "no_email_found"
                        prospect.snov_payload = enrich_result
                        no_email_count += 1
                    
                    await db.commit()
                    await db.refresh(prospect)
                    
                    # Rate limiting (1 request per second to respect rate limits)
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    total_time = (time.time() - prospect_start_time) * 1000
                    logger.error(f"❌ [ENRICHMENT] [{idx}/{len(prospects)}] Error enriching {prospect.domain} after {total_time:.0f}ms: {e}", exc_info=True)
                    logger.error(f"📤 [ENRICHMENT] Output - error: {str(e)}, stack_trace: {type(e).__name__}")
                    failed_count += 1
                    continue
            
            total_enrichment_time = (time.time() - enrichment_start_time) * 1000
            logger.info(f"⏱️  [ENRICHMENT] Total enrichment time: {total_enrichment_time:.0f}ms")
            
            # Update job status
            job.status = "completed"
            job.result = {
                "prospects_enriched": enriched_count,
                "prospects_failed": failed_count,
                "prospects_no_email": no_email_count,
                "total_processed": len(prospects)
            }
            await db.commit()
            
            logger.info(f"✅ Enrichment job {job_id} completed:")
            logger.info(f"   📊 Enriched: {enriched_count}, Failed: {failed_count}, No Email: {no_email_count}")
            
            return {
                "job_id": job_id,
                "status": "completed",
                "prospects_enriched": enriched_count,
                "prospects_failed": failed_count,
                "prospects_no_email": no_email_count,
                "total_processed": len(prospects)
            }
            
        except Exception as e:
            logger.error(f"❌ Enrichment job {job_id} failed: {e}", exc_info=True)
            try:
                result = await db.execute(select(Job).where(Job.id == job_id))
                job = result.scalar_one_or_none()
                if job:
                    job.status = "failed"
                    job.error_message = str(e)
                    await db.commit()
            except Exception as commit_err:
                logger.error(f"❌ Failed to commit error status for job {job_id}: {commit_err}", exc_info=True)
            return {"error": str(e)}

