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
                    
                    # Call enrichment service (which handles Snov.io + local scraping)
                    try:
                        from app.services.enrichment import enrich_prospect_email
                        enrich_result = await enrich_prospect_email(domain, None, prospect.page_url)
                        
                        # Convert enrichment result to snov_result format for compatibility
                        if enrich_result and enrich_result.get("email"):
                            snov_result = {
                                "success": True,
                                "emails": [{
                                    "value": enrich_result["email"],
                                    "confidence_score": enrich_result.get("confidence", 50.0),
                                    "first_name": None,
                                    "last_name": None,
                                    "company": enrich_result.get("company")
                                }]
                            }
                        else:
                            snov_result = {"success": False, "emails": []}
                        snov_time = (time.time() - prospect_start_time) * 1000
                        logger.info(f"⏱️  [ENRICHMENT] Snov.io API call completed in {snov_time:.0f}ms")
                    except RateLimitError as rate_err:
                        # Handle rate limit errors - log and continue with local scraping
                        snov_time = (time.time() - prospect_start_time) * 1000
                        logger.warning(f"⚠️  [ENRICHMENT] Rate limit error after {snov_time:.0f}ms: {rate_err.message}")
                        if rate_err.error_id == "restricted_account":
                            logger.error(f"🚫 [ENRICHMENT] Snov.io account restricted. Please check Snov account.")
                        snov_result = {"success": False, "error": rate_err.message, "domain": domain, "status": rate_err.error_id}
                    except Exception as snov_err:
                        snov_time = (time.time() - prospect_start_time) * 1000
                        logger.error(f"❌ [ENRICHMENT] Enrichment failed after {snov_time:.0f}ms: {snov_err}", exc_info=True)
                        snov_result = {"success": False, "error": str(snov_err), "domain": domain}
                    
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

                    # Decide whether to update existing email
                    if new_email:
                        # Normalize confidence numbers
                        new_conf_val = float(new_confidence or 0)
                        old_conf_val = float(previous_confidence or 0)

                        should_update = False
                        reason = ""

                        if not (prospect.contact_email and str(prospect.contact_email).strip()):
                            should_update = True
                            reason = "no_previous_email"
                        elif prospect.contact_method != "snov_io" and provider_source == "snov_io":
                            # Provider match beats guessed / unknown sources
                            should_update = True
                            reason = f"provider_preferred_over_{prospect.contact_method or 'unknown'}"
                        elif new_conf_val > old_conf_val:
                            should_update = True
                            reason = f"higher_confidence ({new_conf_val} > {old_conf_val})"

                        if should_update:
                            # Final validation before saving
                            if not is_plausible_email(new_email):
                                logger.warning(f"🚫 [ENRICHMENT] Rejecting implausible email before save: {new_email}")
                                no_email_count += 1
                                continue
                            
                            old_email_log = str(prospect.contact_email) if prospect.contact_email else None
                            logger.info(
                                f"✅ [ENRICHMENT] [{idx}/{len(prospects)}] Updating email for {domain}: "
                                f"{old_email_log or 'None'} (conf={old_conf_val}) "
                                f"-> {new_email} (conf={new_conf_val}), source={provider_source}, reason={reason}"
                            )
                            prospect.contact_email = new_email
                            prospect.contact_method = provider_source
                            prospect.snov_payload = snov_result
                            enriched_count += 1
                        else:
                            logger.info(
                                f"ℹ️  [ENRICHMENT] [{idx}/{len(prospects)}] Keeping existing email for {domain}: "
                                f"{prospect.contact_email} (conf={old_conf_val}) over "
                                f"candidate {new_email} (conf={new_conf_val}), source={provider_source}"
                            )
                            # Still store latest payload for debugging / future improvements
                            prospect.snov_payload = snov_result
                    else:
                        # Nothing usable, just persist payload for diagnostics
                        logger.info(
                            f"⚠️  [ENRICHMENT] [{idx}/{len(prospects)}] No usable email or fallback for {domain}"
                        )
                        # Store snov_result for diagnostics (no hunter_payload - Hunter.io removed)
                        prospect.snov_payload = snov_result
                    
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

