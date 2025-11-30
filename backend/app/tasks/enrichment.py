"""
Enrichment task - finds emails for prospects using Hunter.io
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
from app.clients.hunter import HunterIOClient

logger = logging.getLogger(__name__)


async def process_enrichment_job(job_id: str) -> Dict[str, Any]:
    """
    Process enrichment job to find emails for prospects using Hunter.io
    
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
            
            # Build query for prospects without emails
            query = select(Prospect).where(
                Prospect.contact_email.is_(None),
                Prospect.outreach_status == "pending"
            )
            
            if prospect_ids:
                query = query.where(Prospect.id.in_([UUID(pid) for pid in prospect_ids]))
            
            query = query.limit(max_prospects)
            
            result = await db.execute(query)
            prospects = result.scalars().all()
            
            logger.info(f"🔍 Found {len(prospects)} prospects to enrich...")
            
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
            
            # Initialize Hunter client
            try:
                hunter_client = HunterIOClient()
            except ValueError as e:
                job.status = "failed"
                job.error_message = f"Hunter.io not configured: {e}"
                await db.commit()
                logger.error(f"❌ Hunter.io client initialization failed: {e}")
                return {"error": str(e)}
            
            enriched_count = 0
            failed_count = 0
            no_email_count = 0
            
            # Enrich each prospect
            for idx, prospect in enumerate(prospects, 1):
                try:
                    domain = prospect.domain
                    logger.info(f"🔍 [{idx}/{len(prospects)}] Searching emails for {domain}...")
                    
                    # Call Hunter.io
                    hunter_result = await hunter_client.domain_search(domain)
                    
                    if hunter_result.get("success") and hunter_result.get("emails"):
                        emails = hunter_result["emails"]
                        if emails and len(emails) > 0:
                            # Get first email (best match)
                            first_email = emails[0]
                            email_value = first_email.get("value")
                            
                            if email_value:
                                prospect.contact_email = email_value
                                prospect.contact_method = "email"
                                prospect.hunter_payload = hunter_result
                                enriched_count += 1
                                logger.info(f"✅ [{idx}/{len(prospects)}] Found email for {domain}: {email_value}")
                            else:
                                logger.warning(f"⚠️  [{idx}/{len(prospects)}] Email object missing 'value' for {domain}")
                                prospect.hunter_payload = hunter_result
                                no_email_count += 1
                        else:
                            logger.info(f"⚠️  [{idx}/{len(prospects)}] No emails in response for {domain}")
                            prospect.hunter_payload = hunter_result
                            no_email_count += 1
                    else:
                        error_msg = hunter_result.get('error', 'Unknown error')
                        logger.warning(f"❌ [{idx}/{len(prospects)}] Hunter.io failed for {domain}: {error_msg}")
                        prospect.hunter_payload = hunter_result
                        failed_count += 1
                    
                    await db.commit()
                    await db.refresh(prospect)
                    
                    # Rate limiting (1 request per second to respect Hunter.io limits)
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(f"❌ [{idx}/{len(prospects)}] Error enriching {prospect.domain}: {e}", exc_info=True)
                    failed_count += 1
                    continue
            
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
            except:
                pass
            return {"error": str(e)}

