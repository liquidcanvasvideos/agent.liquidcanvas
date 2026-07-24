"""
Social Profile Scraping Task

Scrapes social media profiles to extract:
- Real follower counts
- Engagement rates
- Email addresses

Runs as a background job that appears in the job log.
"""
import asyncio
import logging
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import AsyncSessionLocal
from app.models.prospect import Prospect
from app.models.job import Job
from app.services.social_profile_scraper import scrape_social_profile
from app.services.realtime_social_scraper import scrape_social_profile_realtime

logger = logging.getLogger(__name__)


async def scrape_social_profiles_async(job_id: str) -> dict:
    """
    Async function to scrape social profiles for a job.
    
    This runs as a background job and appears in the job log.
    
    Args:
        job_id: UUID string of the scraping job
    
    Returns:
        Dict with success status and results
    """
    async with AsyncSessionLocal() as db:
        try:
            job_uuid = UUID(job_id)
        except ValueError:
            logger.error(f"❌ [SOCIAL SCRAPING] Invalid job ID format: {job_id}")
            return {"error": "Invalid job ID format"}
        
        # Fetch job
        result = await db.execute(select(Job).where(Job.id == job_uuid))
        job = result.scalar_one_or_none()
        
        if not job:
            logger.error(f"❌ [SOCIAL SCRAPING] Job {job_id} not found")
            return {"error": "Job not found"}
        
        # Check if job was cancelled
        if job.status == "cancelled":
            logger.info(f"⚠️  [SOCIAL SCRAPING] Job {job_id} was cancelled, skipping")
            return {"error": "Job was cancelled"}
        
        # Update job status to running
        job.status = "running"
        start_time = datetime.now(timezone.utc)
        await db.commit()
        
        params = job.params or {}
        profile_ids = params.get("profile_ids", [])
        
        logger.info(f"🚀 [SOCIAL SCRAPING] Starting scraping job {job_id} for {len(profile_ids)} profiles")
        
        try:
            # Get profiles to scrape
            # If profile_ids provided, scrape those specific profiles regardless of scrape_status
            # This allows re-scraping profiles that were already scraped
            if profile_ids:
                result = await db.execute(
                    select(Prospect).where(
                        Prospect.id.in_([UUID(pid) for pid in profile_ids]),
                        Prospect.source_type == 'social',
                        Prospect.approval_status == 'approved'
                    )
                )
                prospects = result.scalars().all()
                logger.info(f"📋 [SOCIAL SCRAPING] Found {len(prospects)} profiles to scrape (manual selection, ignoring scrape_status)")
            else:
                # Auto-query: get all approved social profiles that haven't been scraped yet
                result = await db.execute(
                    select(Prospect).where(
                        Prospect.source_type == 'social',
                        Prospect.approval_status == 'approved',
                        Prospect.scrape_status.in_(['DISCOVERED', 'NO_EMAIL_FOUND'])
                    )
                )
                prospects = result.scalars().all()
            
            if not prospects:
                logger.warning(f"⚠️  [SOCIAL SCRAPING] No profiles found to scrape")
                job.status = "completed"
                job.result = {
                    "profiles_scraped": 0,
                    "profiles_with_emails": 0,
                    "profiles_without_emails": 0,
                    "errors": []
                }
                await db.commit()
                return {
                    "success": True,
                    "profiles_scraped": 0,
                    "message": "No profiles found to scrape"
                }
            
            logger.info(f"📋 [SOCIAL SCRAPING] Found {len(prospects)} profiles to scrape")
            
            profiles_scraped = 0
            profiles_with_emails = 0
            profiles_without_emails = 0
            errors = []
            
            # Scrape each profile
            for prospect in prospects:
                try:
                    if not prospect.profile_url or not prospect.source_platform:
                        logger.warning(f"⚠️  [SOCIAL SCRAPING] Profile {prospect.id} missing profile_url or source_platform")
                        errors.append(f"Profile {prospect.id}: Missing profile_url or source_platform")
                        continue
                    
                    logger.info(f"🔍 [SOCIAL SCRAPING] Scraping {prospect.source_platform} profile: {prospect.profile_url}")
                    
                    # Use real-time scraping for better accuracy
                    scrape_result = await scrape_social_profile_realtime(
                        prospect.profile_url,
                        prospect.source_platform,
                        use_proxy=False  # Set to True if proxy list is configured
                    )
                    
                    # ENHANCEMENT: If no email found in bio, but external links exist, crawl them
                    if scrape_result.get("success") and not scrape_result.get("email") and scrape_result.get("external_links"):
                        logger.info(f"🔗 [SOCIAL SCRAPING] No email in bio, crawling {len(scrape_result['external_links'])} external links for {prospect.id}")
                        for link_url in scrape_result["external_links"][:3]: # Crawl up to 3 links
                            try:
                                # Simple search for emails on the linked page
                                async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                                    link_resp = await client.get(link_url, headers={'User-Agent': 'Mozilla/5.0'})
                                    if link_resp.status_code == 200:
                                        found_emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', link_resp.text)
                                        for email in found_emails:
                                            email_lower = email.lower().strip()
                                            if is_plausible_email(email_lower) and not any(p in email_lower for p in ['instagram.com', 'facebook.com', 'tiktok.com', 'linkedin.com']):
                                                scrape_result["email"] = email_lower
                                                logger.info(f"✅ [SOCIAL SCRAPING] Found email on external site {link_url}: {email_lower}")
                                                break
                            except Exception as e:
                                logger.debug(f"⚠️ [SOCIAL SCRAPING] Failed to crawl link {link_url}: {e}")
                            if scrape_result.get("email"):
                                break
                    
                    # Fallback to basic scraping if real-time fails
                    if not scrape_result.get("success"):
                        logger.warning(f"⚠️  [SOCIAL SCRAPING] Real-time scraping failed, falling back to basic scraping")
                        scrape_result = await scrape_social_profile(
                            prospect.profile_url,
                            prospect.source_platform
                        )
                    
                    if scrape_result.get("success"):
                        # Update prospect with real-time scraped data
                        updated = False
                        
                        # Update follower_count
                        if scrape_result.get("follower_count"):
                            prospect.follower_count = scrape_result["follower_count"]
                            updated = True
                        
                        # Update engagement_rate
                        if scrape_result.get("engagement_rate") is not None:
                            prospect.engagement_rate = scrape_result["engagement_rate"]
                            updated = True
                        elif prospect.engagement_rate is None:
                            # Set default engagement rate if not set
                            platform_defaults = {
                                'linkedin': 1.5,
                                'instagram': 2.5,
                                'facebook': 2.0,
                                'tiktok': 3.5
                            }
                            default_rate = platform_defaults.get(prospect.source_platform.lower(), 2.0)
                            prospect.engagement_rate = default_rate
                            updated = True
                        
                        # Update bio_text
                        if scrape_result.get("bio_text"):
                            prospect.bio_text = scrape_result["bio_text"]
                            updated = True
                        
                        # Update external_links
                        if scrape_result.get("external_links"):
                            prospect.external_links = scrape_result["external_links"]
                            updated = True
                        
                        # Update email if found
                        if scrape_result.get("email"):
                            prospect.contact_email = scrape_result["email"]
                            prospect.contact_method = "profile_scraping"
                            prospect.scrape_status = "SCRAPED"
                            profiles_with_emails += 1
                            updated = True
                        else:
                            # Mark as scraped even if no email found
                            if prospect.scrape_status in ['DISCOVERED', None]:
                                prospect.scrape_status = "NO_EMAIL_FOUND"
                            profiles_without_emails += 1
                            updated = True
                        
                        # Update scraped_at timestamp
                        from datetime import datetime, timezone
                        prospect.scraped_at = datetime.now(timezone.utc)
                        updated = True
                        
                        if updated:
                            await db.commit()
                            profiles_scraped += 1
                            logger.info(
                                f"✅ [SOCIAL SCRAPING] Updated profile {prospect.id}: "
                                f"followers={prospect.follower_count or 'N/A'}, "
                                f"engagement={prospect.engagement_rate or 'N/A'}%, "
                                f"email={'found' if prospect.contact_email else 'not found'}, "
                                f"bio={'found' if prospect.bio_text else 'not found'}, "
                                f"links={len(prospect.external_links or [])}"
                            )
                    else:
                        error_msg = scrape_result.get("error", "Unknown error")
                        logger.warning(f"⚠️  [SOCIAL SCRAPING] Failed to scrape {prospect.profile_url}: {error_msg}")
                        errors.append(f"Profile {prospect.id}: {error_msg}")
                        prospect.scrape_status = "NO_EMAIL_FOUND"
                        await db.commit()
                        
                except Exception as scrape_err:
                    logger.error(f"❌ [SOCIAL SCRAPING] Error scraping profile {prospect.id}: {scrape_err}", exc_info=True)
                    errors.append(f"Profile {prospect.id}: {str(scrape_err)}")
                    continue
            
            # Update job status and result
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()
            
            job.status = "completed"
            job.result = {
                "profiles_scraped": profiles_scraped,
                "profiles_with_emails": profiles_with_emails,
                "profiles_without_emails": profiles_without_emails,
                "errors": errors,
                "duration_seconds": duration
            }
            await db.commit()
            
            logger.info(
                f"✅ [SOCIAL SCRAPING] Job {job_id} completed successfully - "
                f"scraped {profiles_scraped} profiles, "
                f"{profiles_with_emails} with emails, "
                f"{profiles_without_emails} without emails"
            )
            
            # Trigger refresh event
            if profiles_scraped > 0:
                import sys
                if 'asyncio' in sys.modules:
                    # In async context, we can't easily dispatch events, but the frontend polls
                    pass
            
            return {
                "success": True,
                "job_id": job_id,
                "profiles_scraped": profiles_scraped,
                "profiles_with_emails": profiles_with_emails,
                "profiles_without_emails": profiles_without_emails,
                "errors": errors,
                "status": "completed"
            }
            
        except Exception as e:
            logger.error(f"❌ [SOCIAL SCRAPING] Job {job_id} failed: {e}", exc_info=True)
            
            # Update job status
            job.status = "failed"
            job.error_message = str(e)
            await db.commit()
            
            return {
                "success": False,
                "job_id": job_id,
                "error": str(e)
            }

