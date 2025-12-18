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
from app.models.prospect import Prospect
from app.models.job import Job
from app.clients.snov import SnovIOClient
from app.services.enrichment import _is_snov_email_from_website
from app.models.enums import ScrapeStatus, VerificationStatus

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
            
            result = await db.execute(
                select(Prospect).where(
                    Prospect.id.in_([UUID(pid) for pid in prospect_ids]),
                    Prospect.scrape_status.in_([ScrapeStatus.SCRAPED.value, ScrapeStatus.NO_EMAIL_FOUND.value]),
                    Prospect.verification_status == VerificationStatus.PENDING.value
                )
            )
            prospects = result.scalars().all()
            
            logger.info(f"✅ [VERIFICATION] Starting verification for {len(prospects)} scraped prospects")
            
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
                    logger.info(f"✅ [VERIFICATION] [{idx}/{len(prospects)}] Verifying {prospect.domain}...")
                    
                    # If prospect has scraped email, verify it
                    if prospect.contact_email and prospect.scrape_status == ScrapeStatus.SCRAPED.value:
                        # Verify existing scraped email
                        snov_result = await snov_client.domain_search(prospect.domain)
                        
                        if snov_result.get("success") and snov_result.get("emails"):
                            # Check if scraped email is in Snov results and from website
                            scraped_email = prospect.contact_email.lower()
                            verified = False
                            confidence = 0.0
                            
                            for email_data in snov_result.get("emails", []):
                                if not isinstance(email_data, dict):
                                    continue
                                
                                email_value = email_data.get("value", "").lower()
                                if email_value == scraped_email:
                                    # Check if from website
                                if _is_snov_email_from_website(email_data):
                                        verified = True
                                        confidence = float(email_data.get("confidence_score", 0) or 0)
                                        break
                            
                            if verified:
                                prospect.verification_status = VerificationStatus.VERIFIED.value
                                prospect.verification_confidence = confidence
                                prospect.verification_payload = snov_result
                                verified_count += 1
                                logger.info(f"✅ [VERIFICATION] Verified scraped email for {prospect.domain}: {prospect.contact_email} (confidence: {confidence})")
                            else:
                                prospect.verification_status = VerificationStatus.UNVERIFIED_LOWER.value
                                prospect.verification_confidence = 0.0
                                prospect.verification_payload = snov_result
                                unverified_count += 1
                                logger.warning(f"⚠️  [VERIFICATION] Scraped email not verified for {prospect.domain}: {prospect.contact_email}")
                        else:
                            # Snov returned no results or failed
                            prospect.verification_status = VerificationStatus.UNVERIFIED_LOWER.value
                            prospect.verification_confidence = 0.0
                            prospect.verification_payload = snov_result
                            unverified_count += 1
                            logger.warning(f"⚠️  [VERIFICATION] Snov returned no results for {prospect.domain}")
                    
                    elif prospect.scrape_status == ScrapeStatus.NO_EMAIL_FOUND.value:
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
                                prospect.verification_status = VerificationStatus.VERIFIED.value
                                prospect.verification_confidence = confidence
                                prospect.verification_payload = snov_result
                                verified_count += 1
                                logger.info(f"✅ [VERIFICATION] Found email via Snov for {prospect.domain}: {found_email} (confidence: {confidence})")
                            else:
                                prospect.verification_status = VerificationStatus.UNVERIFIED_LOWER.value
                                prospect.verification_confidence = 0.0
                                prospect.verification_payload = snov_result
                                unverified_count += 1
                                logger.warning(f"⚠️  [VERIFICATION] No website-source email found for {prospect.domain}")
                        else:
                            prospect.verification_status = VerificationStatus.UNVERIFIED_LOWER.value
                            prospect.verification_confidence = 0.0
                            prospect.verification_payload = snov_result
                            unverified_count += 1
                            logger.warning(f"⚠️  [VERIFICATION] Snov returned no results for {prospect.domain}")
                    
                    await db.commit()
                    await db.refresh(prospect)
                    
                    # Rate limiting
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(f"❌ [VERIFICATION] Failed to verify {prospect.domain}: {e}", exc_info=True)
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

