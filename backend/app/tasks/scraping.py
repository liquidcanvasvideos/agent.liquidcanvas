"""
Scraping task - STEP 3 of strict pipeline
Scrapes approved websites for emails (homepage + contact/about pages)
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
from app.services.enrichment import _scrape_emails_from_domain
from app.models.enums import ScrapeStatus

logger = logging.getLogger(__name__)


async def scrape_prospects_async(job_id: str):
    """
    Scrape approved prospects for emails
    
    STRICT MODE:
    - Only scrapes approved prospects
    - Crawls homepage + contact/about pages
    - Extracts visible emails only
    - Sets scrape_status = "SCRAPED" or "NO_EMAIL_FOUND"
    """
    async with AsyncSessionLocal() as db:
        try:
            # Get job
            result = await db.execute(select(Job).where(Job.id == UUID(job_id)))
            job = result.scalar_one_or_none()
            
            if not job:
                logger.error(f"❌ [SCRAPING] Job {job_id} not found")
                return {"error": "Job not found"}
            
            job.status = "running"
            await db.commit()
            
            # Get prospects to scrape
            prospect_ids = job.params.get("prospect_ids", [])
            if not prospect_ids:
                logger.error(f"❌ [SCRAPING] No prospect IDs in job params")
                job.status = "failed"
                job.error_message = "No prospect IDs provided"
                await db.commit()
                return {"error": "No prospect IDs provided"}
            
            result = await db.execute(
                select(Prospect).where(
                    Prospect.id.in_([UUID(pid) for pid in prospect_ids]),
                    Prospect.approval_status == "approved",
                    Prospect.scrape_status == ScrapeStatus.DISCOVERED.value
                )
            )
            prospects = result.scalars().all()
            
            logger.info(f"🔍 [SCRAPING] Starting scraping for {len(prospects)} approved prospects")
            
            scraped_count = 0
            no_email_count = 0
            failed_count = 0
            
            for idx, prospect in enumerate(prospects, 1):
                try:
                    logger.info(f"🔍 [SCRAPING] [{idx}/{len(prospects)}] Scraping {prospect.domain}...")
                    
                    # Scrape emails from domain
                    emails_by_page = await _scrape_emails_from_domain(prospect.domain, prospect.page_url)
                    
                    # Collect all unique emails
                    all_emails = []
                    source_url = None
                    for url, emails in emails_by_page.items():
                        all_emails.extend(emails)
                        if emails and not source_url:
                            source_url = url
                    
                    if all_emails:
                        # Emails found
                        prospect.contact_email = all_emails[0]  # Primary email
                        prospect.scrape_source_url = source_url
                        prospect.scrape_payload = emails_by_page
                        prospect.scrape_status = ScrapeStatus.SCRAPED.value
                        scraped_count += 1
                        logger.info(f"✅ [SCRAPING] Found {len(all_emails)} email(s) for {prospect.domain}: {all_emails[0]}")
                    else:
                        # No emails found
                        prospect.scrape_status = ScrapeStatus.NO_EMAIL_FOUND.value
                        prospect.scrape_payload = {}
                        no_email_count += 1
                        logger.warning(f"⚠️  [SCRAPING] No emails found for {prospect.domain}")
                    
                    await db.commit()
                    await db.refresh(prospect)
                    
                    # Rate limiting
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(f"❌ [SCRAPING] Failed to scrape {prospect.domain}: {e}", exc_info=True)
                    prospect.scrape_status = ScrapeStatus.FAILED.value
                    failed_count += 1
                    await db.commit()
                    continue
            
            # Update job status
            job.status = "completed"
            job.result = {
                "scraped": scraped_count,
                "no_email": no_email_count,
                "failed": failed_count,
                "total": len(prospects)
            }
            await db.commit()
            
            logger.info(f"✅ [SCRAPING] Job {job_id} completed: {scraped_count} scraped, {no_email_count} no email, {failed_count} failed")
            
            return {
                "job_id": job_id,
                "status": "completed",
                "scraped": scraped_count,
                "no_email": no_email_count,
                "failed": failed_count
            }
            
        except Exception as e:
            logger.error(f"❌ [SCRAPING] Job {job_id} failed: {e}", exc_info=True)
            try:
                result = await db.execute(select(Job).where(Job.id == UUID(job_id)))
                job = result.scalar_one_or_none()
                if job:
                    job.status = "failed"
                    job.error_message = str(e)
                    await db.commit()
            except Exception as commit_err:
                logger.error(f"❌ [SCRAPING] Failed to commit error status: {commit_err}", exc_info=True)
            return {"error": str(e)}

