"""
Scraping task - STEP 3 of strict pipeline
Scrapes approved websites for emails (homepage + contact/about pages)
"""
import asyncio
import logging
from typing import List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from datetime import datetime, timezone

from app.db.database import AsyncSessionLocal
from app.models.prospect import Prospect, ScrapeStatus, ProspectStage
from app.models.job import Job
from app.services.enrichment import _scrape_emails_from_domain

logger = logging.getLogger(__name__)


async def scrape_prospects_async(job_id: str):
    """
    Scrape discovered prospects for emails
    
    STRICT MODE:
    - Scrapes discovered, non-rejected prospects (matches pipeline endpoint criteria)
    - Crawls homepage + contact/about pages
    - Extracts visible emails only
    - Sets scrape_status = "SCRAPED" or "NO_EMAIL_FOUND"
    - Commits state updates immediately after each prospect
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
            
            # Match pipeline endpoint selection criteria:
            # - discovery_status == DISCOVERED
            # - approval_status is NOT "rejected" (NULL or any other value is allowed)
            # - scrape_status == DISCOVERED (avoid re-scraping already processed prospects)
            from sqlalchemy import or_
            from app.models.prospect import DiscoveryStatus
            
            result = await db.execute(
                select(Prospect).where(
                    Prospect.id.in_([UUID(pid) for pid in prospect_ids]),
                    Prospect.discovery_status == DiscoveryStatus.DISCOVERED.value,
                    or_(
                        Prospect.approval_status.is_(None),
                        Prospect.approval_status != "rejected",
                    ),
                    Prospect.scrape_status == ScrapeStatus.DISCOVERED.value,
                )
            )
            prospects = result.scalars().all()
            
            logger.info(f"🔍 [SCRAPING] Starting scraping for {len(prospects)} discovered prospects (job selected {len(prospect_ids)} IDs)")
            
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
                        # Emails found - update prospect state and promote to LEAD stage
                        prospect.contact_email = all_emails[0]  # Primary email
                        prospect.scrape_source_url = source_url
                        prospect.scrape_payload = emails_by_page
                        prospect.scrape_status = ScrapeStatus.SCRAPED.value
                        # Promote to LEAD stage - ready for verification (defensive: check if column exists)
                        try:
                            # Check if stage column exists in database
                            column_check = await db.execute(
                                text("""
                                    SELECT column_name
                                    FROM information_schema.columns 
                                    WHERE table_name = 'prospects' 
                                    AND column_name = 'stage'
                                """)
                            )
                            if column_check.fetchone():
                                # Column exists - safe to set stage
                                prospect.stage = ProspectStage.LEAD.value
                                logger.debug(f"✅ [SCRAPING] Set stage=LEAD for prospect {prospect.id}")
                            else:
                                # Column doesn't exist yet - will be set by migration
                                logger.debug(f"⚠️  stage column not available yet, skipping stage update for {prospect.id}")
                        except Exception as stage_err:
                            # If check fails, log but continue (stage will be backfilled by migration)
                            logger.warning(f"⚠️  Could not check/set stage column: {stage_err}, will be backfilled by migration")
                        scraped_count += 1
                        logger.info(f"✅ [SCRAPING] Found {len(all_emails)} email(s) for {prospect.domain}: {all_emails[0]}")
                        logger.info(f"📝 [SCRAPING] Updated prospect {prospect.id} - scrape_status=SCRAPED, contact_email={all_emails[0]}")
                    else:
                        # No emails found - update prospect state (remain at SCRAPED stage, not promoted to LEAD)
                        prospect.scrape_status = ScrapeStatus.NO_EMAIL_FOUND.value
                        prospect.scrape_payload = {}
                        # Set stage to SCRAPED (not LEAD, since no email found)
                        try:
                            # Check if stage column exists in database
                            column_check = await db.execute(
                                text("""
                                    SELECT column_name
                                    FROM information_schema.columns 
                                    WHERE table_name = 'prospects' 
                                    AND column_name = 'stage'
                                """)
                            )
                            if column_check.fetchone():
                                # Column exists - safe to set stage
                                prospect.stage = ProspectStage.SCRAPED.value
                                logger.debug(f"✅ [SCRAPING] Set stage=SCRAPED for prospect {prospect.id}")
                            else:
                                # Column doesn't exist yet - will be set by migration
                                logger.debug(f"⚠️  stage column not available yet, skipping stage update for {prospect.id}")
                        except Exception as stage_err:
                            # If check fails, log but continue (stage will be backfilled by migration)
                            logger.warning(f"⚠️  Could not check/set stage column: {stage_err}, will be backfilled by migration")
                        no_email_count += 1
                        logger.warning(f"⚠️  [SCRAPING] No emails found for {prospect.domain}")
                        logger.info(f"📝 [SCRAPING] Updated prospect {prospect.id} - scrape_status=NO_EMAIL_FOUND, stage=SCRAPED")
                    
                    # CRITICAL: Commit state update immediately
                    await db.commit()
                    await db.refresh(prospect)
                    logger.debug(f"💾 [SCRAPING] Committed state update for prospect {prospect.id} (scrape_status={prospect.scrape_status})")
                    
                    # Rate limiting
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(
                        f"❌ [SCRAPING] Failed to scrape {prospect.domain}: {e}",
                        exc_info=True,
                    )
                    # Update prospect state to FAILED
                    prospect.scrape_status = ScrapeStatus.FAILED.value
                    # Set stage to FAILED if column exists
                    try:
                        column_check = await db.execute(
                            text("""
                                SELECT column_name
                                FROM information_schema.columns 
                                WHERE table_name = 'prospects' 
                                AND column_name = 'stage'
                            """)
                        )
                        if column_check.fetchone():
                            prospect.stage = "FAILED"  # ProspectStage doesn't have FAILED, use string directly
                            logger.debug(f"✅ [SCRAPING] Set stage=FAILED for prospect {prospect.id}")
                    except Exception as stage_err:
                        logger.warning(f"⚠️  Could not set stage=FAILED: {stage_err}")
                    failed_count += 1
                    logger.info(f"📝 [SCRAPING] Updated prospect {prospect.id} - scrape_status=FAILED")
                    # CRITICAL: Commit failed state update
                    await db.commit()
                    logger.debug(f"💾 [SCRAPING] Committed failed state for prospect {prospect.id}")
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
            
            # Summary log with state update counts
            leads_created = scraped_count  # Leads are prospects with stage=LEAD (scraped with emails)
            logger.info(f"✅ [SCRAPING] Job {job_id} completed: {scraped_count} scraped (SCRAPED), {no_email_count} no email (NO_EMAIL_FOUND), {failed_count} failed (FAILED)")
            logger.info(f"📊 [SCRAPING] State updates: {scraped_count} prospects promoted to LEAD stage (ready for verification)")
            logger.info(f"📊 [SCRAPING] Total prospects processed: {len(prospects)}, Updated: {scraped_count + no_email_count + failed_count}")
            logger.info(f"👥 [SCRAPING] {leads_created} leads created from scraping job (prospects with stage=LEAD and contact_email)")
            
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

