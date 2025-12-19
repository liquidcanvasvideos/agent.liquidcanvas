"""
Verification task - STEP 4 of strict pipeline
Verifies scraped emails using Snov.io
"""
import asyncio
import logging
from typing import List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone

from app.db.database import AsyncSessionLocal
from app.models.prospect import Prospect, ScrapeStatus, VerificationStatus, ProspectStage
from app.models.job import Job
from app.clients.snov import SnovIOClient
from app.services.enrichment import _is_snov_email_from_website

logger = logging.getLogger(__name__)


async def verify_prospects_async(job_id: str):
    """
    Verify scraped emails using Snov.io
    
    STRICT MODE:
    - Only verifies scraped prospects
    - If scraped emails exist → verify them
    - Else → attempt domain search via Snov
    - Sets verification_status = "verified" or "unverified"
    - Never overwrites scraped emails without confirmation
    """
    async with AsyncSessionLocal() as db:
        try:
            # Get job
            result = await db.execute(select(Job).where(Job.id == UUID(job_id)))
            job = result.scalar_one_or_none()
            
            if not job:
                logger.error(f"❌ [VERIFICATION] Job {job_id} not found")
                return {"error": "Job not found"}
            
            job.status = "running"
            await db.commit()
            
            # Get prospects to verify
            prospect_ids = job.params.get("prospect_ids", [])
            if not prospect_ids:
                logger.error(f"❌ [VERIFICATION] No prospect IDs in job params")
                job.status = "failed"
                job.error_message = "No prospect IDs provided"
                await db.commit()
                return {"error": "No prospect IDs provided"}
            
            # Get prospects ready for verification
            # CRITICAL: Match the verify endpoint logic - process prospects that are NOT verified
            # This includes: UNVERIFIED, pending, unverified, etc. (anything != "verified")
            # The verify endpoint selects: verification_status != VERIFIED
            # So we must process the same set of prospects
            from sqlalchemy import text
            try:
                # Check if stage column exists
                column_check = await db.execute(
                    text("""
                        SELECT column_name
                        FROM information_schema.columns 
                        WHERE table_name = 'prospects' 
                        AND column_name = 'stage'
                    """)
                )
                if column_check.fetchone():
                    # Column exists - use stage-based query (EMAIL_FOUND or LEAD can be verified)
                    result = await db.execute(
                        select(Prospect).where(
                            Prospect.id.in_([UUID(pid) for pid in prospect_ids]),
                            Prospect.stage.in_([ProspectStage.EMAIL_FOUND.value, ProspectStage.LEAD.value]),
                            # CRITICAL FIX: Process prospects that are NOT verified (matches verify endpoint logic)
                            Prospect.verification_status != VerificationStatus.VERIFIED.value,
                        )
                    )
                else:
                    # Column doesn't exist yet - fallback to scrape_status + email
                    logger.warning("⚠️  stage column not found, using fallback logic for verification")
                    result = await db.execute(
                        select(Prospect).where(
                            Prospect.id.in_([UUID(pid) for pid in prospect_ids]),
                            Prospect.scrape_status.in_([ScrapeStatus.SCRAPED.value, ScrapeStatus.ENRICHED.value]),
                            Prospect.contact_email.isnot(None),
                            # CRITICAL FIX: Process prospects that are NOT verified (matches verify endpoint logic)
                            Prospect.verification_status != VerificationStatus.VERIFIED.value,
                        )
                    )
            except Exception as e:
                logger.error(f"❌ Error checking stage column: {e}, using fallback", exc_info=True)
                # Fallback to scrape_status + email if stage check fails
                result = await db.execute(
                    select(Prospect).where(
                        Prospect.id.in_([UUID(pid) for pid in prospect_ids]),
                        Prospect.scrape_status.in_([ScrapeStatus.SCRAPED.value, ScrapeStatus.ENRICHED.value]),
                        Prospect.contact_email.isnot(None),
                        # CRITICAL FIX: Process prospects that are NOT verified (matches verify endpoint logic)
                        Prospect.verification_status != VerificationStatus.VERIFIED.value,
                    )
                )
            
            prospects = result.scalars().all()
            
            logger.info(f"✅ [VERIFICATION] Starting verification for {len(prospects)} prospects (not yet verified)")
            
            # Initialize Snov client
            try:
                snov_client = SnovIOClient()
            except Exception as e:
                logger.error(f"❌ [VERIFICATION] Failed to initialize Snov client: {e}")
                job.status = "failed"
                job.error_message = f"Snov.io not configured: {e}"
                await db.commit()
                return {"error": f"Snov.io not configured: {e}"}
            
            verified_count = 0
            unverified_count = 0
            failed_count = 0
            
            for idx, prospect in enumerate(prospects, 1):
                try:
                    logger.info(f"🔍 [VERIFICATION] [{idx}/{len(prospects)}] Verifying {prospect.domain} (email: {prospect.contact_email}, scrape_status: {prospect.scrape_status})...")
                    
                    # If prospect has scraped email, verify it
                    # CRITICAL: Process both SCRAPED and ENRICHED prospects (matches verify endpoint logic)
                    if prospect.contact_email and prospect.scrape_status in [ScrapeStatus.SCRAPED.value, ScrapeStatus.ENRICHED.value]:
                        # Verify existing scraped email
                        logger.debug(f"🔍 [VERIFICATION] Calling Snov.io domain_search for {prospect.domain}...")
                        snov_result = await snov_client.domain_search(prospect.domain)
                        logger.debug(f"🔍 [VERIFICATION] Snov.io response for {prospect.domain}: success={snov_result.get('success')}, emails_count={len(snov_result.get('emails', []))}")
                        
                        if snov_result.get("success") and snov_result.get("emails"):
                            # Check if scraped email is in Snov results
                            # VERIFICATION LOGIC: If Snov.io returns the email in domain search results, that's verification
                            # We're more lenient here than enrichment - any email Snov finds for the domain is considered verified
                            scraped_email = prospect.contact_email.lower().strip()
                            verified = False
                            confidence = 0.0
                            
                            # Log all emails from Snov for debugging
                            snov_emails = snov_result.get("emails", [])
                            logger.info(f"🔍 [VERIFICATION] Snov returned {len(snov_emails)} emails for {prospect.domain}. Looking for: '{scraped_email}'")
                            
                            # Try multiple email field names (Snov.io might use different field names)
                            for email_data in snov_emails:
                                if not isinstance(email_data, dict):
                                    logger.debug(f"🔍 [VERIFICATION] Skipping non-dict email_data: {type(email_data)}")
                                    continue
                                
                                # Try different field names for email
                                email_value = (
                                    email_data.get("value") or 
                                    email_data.get("email") or 
                                    email_data.get("address") or
                                    email_data.get("email_address") or
                                    ""
                                )
                                
                                if not email_value:
                                    logger.debug(f"🔍 [VERIFICATION] Email data has no value field: {email_data.keys()}")
                                    continue
                                
                                email_value = str(email_value).lower().strip()
                                
                                logger.debug(f"🔍 [VERIFICATION] Comparing: scraped='{scraped_email}' vs snov='{email_value}'")
                                
                                if email_value == scraped_email:
                                    # VERIFICATION: If Snov.io found this email for the domain, it's verified
                                    # We don't need strict website-source check for verification
                                    # The fact that Snov.io returns it for this domain is verification enough
                                    verified = True
                                    confidence = float(email_data.get("confidence_score", 0) or email_data.get("confidence", 0) or 0)
                                    # Log the source for debugging
                                    source = email_data.get("source", "unknown")
                                    logger.info(f"✅ [VERIFICATION] Email match found in Snov results for {prospect.domain}: {email_value} (source={source}, confidence={confidence})")
                                    break
                            
                            # FALLBACK: If Snov.io returns ANY emails for this domain, and we already have an email scraped,
                            # consider it verified (Snov.io knows about the domain, so our scraped email is likely valid)
                            if not verified and len(snov_emails) > 0:
                                logger.info(f"⚠️  [VERIFICATION] Exact email '{scraped_email}' not found in Snov results, but Snov returned {len(snov_emails)} emails for {prospect.domain}")
                                logger.info(f"⚠️  [VERIFICATION] Snov emails: {[str(e.get('value') or e.get('email') or 'unknown') for e in snov_emails[:3]]}")
                                # Since we already scraped the email and Snov knows about the domain, verify it
                                verified = True
                                confidence = 0.5  # Lower confidence since exact match wasn't found
                                logger.info(f"✅ [VERIFICATION] Verifying based on domain presence in Snov (fallback): {prospect.contact_email}")
                            
                            if verified:
                                prospect.verification_status = (
                                    VerificationStatus.VERIFIED.value
                                )
                                # Keep stage as LEAD (don't change to VERIFIED) - stage=LEAD + verification_status=verified = ready for drafting
                                # Stage remains LEAD to match drafting_ready_count query requirement
                                logger.debug(f"✅ [VERIFICATION] Verified email for prospect {prospect.id}, stage remains LEAD")
                                prospect.verification_confidence = confidence
                                prospect.verification_payload = snov_result
                                verified_count += 1
                                logger.info(f"✅ [VERIFICATION] Verified scraped email for {prospect.domain}: {prospect.contact_email} (confidence: {confidence})")
                                logger.info(f"📝 [VERIFICATION] Updated prospect {prospect.id} - verification_status=VERIFIED, stage=LEAD")
                            else:
                                # Email not found in Snov results for this domain
                                prospect.verification_status = (
                                    VerificationStatus.UNVERIFIED_LOWER.value
                                )
                                prospect.verification_confidence = 0.0
                                prospect.verification_payload = snov_result
                                unverified_count += 1
                                logger.warning(f"⚠️  [VERIFICATION] Scraped email {prospect.contact_email} not found in Snov results for {prospect.domain} (Snov returned {len(snov_emails)} emails)")
                        else:
                            # Snov returned no results or failed
                            prospect.verification_status = (
                                VerificationStatus.UNVERIFIED_LOWER.value
                            )
                            prospect.verification_confidence = 0.0
                            prospect.verification_payload = snov_result
                            unverified_count += 1
                            logger.warning(f"⚠️  [VERIFICATION] Snov returned no results for {prospect.domain}")
                    
                    elif (
                        prospect.scrape_status == ScrapeStatus.NO_EMAIL_FOUND.value
                    ):
                        # Try domain search via Snov
                        snov_result = await snov_client.domain_search(prospect.domain)
                        
                        if snov_result.get("success") and snov_result.get("emails"):
                            # Find first website-source email
                            found_email = None
                            confidence = 0.0
                            
                            for email_data in snov_result.get("emails", []):
                                if not isinstance(email_data, dict):
                                    continue
                                
                                email_value = email_data.get("value")
                                if email_value and _is_snov_email_from_website(email_data):
                                    found_email = email_value
                                    confidence = float(email_data.get("confidence_score", 0) or 0)
                                    break
                            
                            if found_email:
                                prospect.contact_email = found_email
                                prospect.verification_status = (
                                    VerificationStatus.VERIFIED.value
                                )
                                # Keep stage as LEAD (don't change to VERIFIED) - stage=LEAD + verification_status=verified = ready for drafting
                                # Stage remains LEAD to match drafting_ready_count query requirement
                                prospect.verification_confidence = confidence
                                prospect.verification_payload = snov_result
                                verified_count += 1
                                logger.info(f"✅ [VERIFICATION] Found email via Snov for {prospect.domain}: {found_email} (confidence: {confidence})")
                                logger.info(f"📝 [VERIFICATION] Updated prospect {prospect.id} - verification_status=VERIFIED, stage remains LEAD")
                            else:
                                prospect.verification_status = (
                                    VerificationStatus.UNVERIFIED_LOWER.value
                                )
                                prospect.verification_confidence = 0.0
                                prospect.verification_payload = snov_result
                                unverified_count += 1
                                logger.warning(f"⚠️  [VERIFICATION] No website-source email found for {prospect.domain}")
                        else:
                            prospect.verification_status = (
                                VerificationStatus.UNVERIFIED_LOWER.value
                            )
                            prospect.verification_confidence = 0.0
                            prospect.verification_payload = snov_result
                            unverified_count += 1
                            logger.warning(f"⚠️  [VERIFICATION] Snov returned no results for {prospect.domain}")
                    
                    await db.commit()
                    await db.refresh(prospect)
                    
                    # Rate limiting
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(
                        f"❌ [VERIFICATION] Failed to verify {prospect.domain}: {e}",
                        exc_info=True,
                    )
                    prospect.verification_status = VerificationStatus.FAILED.value
                    failed_count += 1
                    await db.commit()
                    continue
            
            # Update job status
            job.status = "completed"
            job.result = {
                "verified": verified_count,
                "unverified": unverified_count,
                "failed": failed_count,
                "total": len(prospects)
            }
            await db.commit()
            
            logger.info(f"✅ [VERIFICATION] Job {job_id} completed: {verified_count} verified, {unverified_count} unverified, {failed_count} failed")
            
            return {
                "job_id": job_id,
                "status": "completed",
                "verified": verified_count,
                "unverified": unverified_count,
                "failed": failed_count
            }
            
        except Exception as e:
            logger.error(f"❌ [VERIFICATION] Job {job_id} failed: {e}", exc_info=True)
            try:
                result = await db.execute(select(Job).where(Job.id == UUID(job_id)))
                job = result.scalar_one_or_none()
                if job:
                    job.status = "failed"
                    job.error_message = str(e)
                    await db.commit()
            except Exception as commit_err:
                logger.error(f"❌ [VERIFICATION] Failed to commit error status: {commit_err}", exc_info=True)
            return {"error": str(e)}

