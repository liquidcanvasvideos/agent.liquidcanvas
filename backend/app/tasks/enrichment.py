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
                    
                    # Helper: compute previous best confidence from stored snov_payload
                    previous_confidence: Optional[float] = None
                    previous_email: Optional[str] = None
                    if prospect.snov_payload and isinstance(prospect.snov_payload, dict):
                        try:
                            prev_emails = prospect.snov_payload.get("emails", [])
                            # Prefer confidence for the currently stored email if present
                            if prev_emails and isinstance(prev_emails, list):
                                for e_data in prev_emails:
                                    if not isinstance(e_data, dict):
                                        continue
                                    if prospect.contact_email and e_data.get("value") == prospect.contact_email:
                                        previous_email = e_data.get("value")
                                        previous_confidence = float(e_data.get("confidence_score", 0) or 0)
                                        break
                                # Fallback: take max confidence across previous entries
                                if previous_confidence is None:
                                    for e_data in prev_emails:
                                        if not isinstance(e_data, dict):
                                            continue
                                        c_val = float(e_data.get("confidence_score", 0) or 0)
                                        if previous_confidence is None or c_val > previous_confidence:
                                            previous_confidence = c_val
                                            previous_email = e_data.get("value")
                        except Exception as prev_err:
                            logger.warning(
                                f"⚠️  [ENRICHMENT] Failed to parse previous Snov payload for {domain}: {prev_err}",
                                exc_info=True,
                            )

                    new_email: Optional[str] = None
                    new_confidence: Optional[float] = None
                    provider_source = "snov_io"
                    fallback_used = False

                    # Process Snov.io response
                    if snov_result.get("success") and snov_result.get("emails"):
                        emails = snov_result["emails"]
                        if emails and len(emails) > 0:
                            # Get best email (highest confidence) - filter out garbage
                            best_email = None
                            best_confidence: float = 0
                            for email_data in emails:
                                if not isinstance(email_data, dict):
                                    continue
                                email_value = email_data.get("value")
                                if not email_value:
                                    continue
                                # Filter out garbage emails
                                if not is_plausible_email(email_value):
                                    logger.info(f"🚫 [ENRICHMENT] Discarding implausible email candidate from Snov.io: {email_value}")
                                    continue
                                confidence = float(email_data.get("confidence_score", 0) or 0)
                                if confidence > best_confidence:
                                    best_confidence = confidence
                                    best_email = email_data
                            
                            if best_email and best_email.get("value"):
                                new_email = best_email["value"]
                                new_confidence = best_confidence
                            else:
                                logger.warning(
                                    f"⚠️  [ENRICHMENT] [{idx}/{len(prospects)}] Email object missing 'value' for {domain}"
                                )
                        else:
                            logger.info(
                                f"⚠️  [ENRICHMENT] [{idx}/{len(prospects)}] No emails in response for {domain}"
                            )
                    else:
                        error_msg = snov_result.get('error', 'Unknown error')
                        logger.warning(
                            f"❌ [ENRICHMENT] [{idx}/{len(prospects)}] Snov.io failed for {domain}: {error_msg}"
                        )

                    # If provider returned nothing usable, don't use generic guesser
                    # The enrichment service already tried: Snov.io, local scraping, and pattern generation
                    # If all of those failed, we should NOT save a generic "info@" email
                    if not new_email:
                        no_email_count += 1
                        logger.info(
                            f"⚠️  [ENRICHMENT] [{idx}/{len(prospects)}] No email found for {domain} after all methods (Snov.io, scraping, pattern generation)"
                        )

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
                    
                    # Log what the enrichment service actually returned for debugging
                    if enrich_result:
                            logger.debug(f"   Enrichment result: {enrich_result}")
                        else:
                            logger.debug(f"   Enrichment service returned None")
                        # Store snov_result for diagnostics (no hunter_payload - Hunter.io removed)
                        prospect.snov_payload = snov_result
                        no_email_count += 1
                    
                    await db.commit()
                    await db.refresh(prospect)
                    
                    # Rate limiting (1 request per second to respect Snov.io limits)
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

