"""
Automation jobs for the 24/7 pipeline
"""
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from datetime import datetime
from db.database import SessionLocal
from db.models import ScrapedWebsite, Contact, OutreachEmail, ScrapingJob
from scraper.scraper_service import ScraperService
from extractor.contact_extraction_service import ContactExtractionService
from ai.email_generator import EmailGenerator
from emailer.outreach_email_sender import OutreachEmailSender
from jobs.website_discovery import WebsiteDiscovery
from utils.app_settings import AppSettingsManager
import logging

logger = logging.getLogger(__name__)


def is_automation_enabled(db: Session) -> bool:
    """Check if automation is enabled"""
    settings_manager = AppSettingsManager(db)
    return settings_manager.get_automation_enabled()


def log_job_to_db(job_type: str, status: str, result: Dict = None, error: str = None):
    """Log job execution to database"""
    db = SessionLocal()
    try:
        job = ScrapingJob(
            job_type=job_type,
            status=status,
            result=result,
            error_message=error,
            started_at=datetime.utcnow() if status == "running" else None,
            completed_at=datetime.utcnow() if status in ["completed", "failed"] else None
        )
        db.add(job)
        db.commit()
        return job.id
    except Exception as e:
        logger.error(f"Error logging job to DB: {str(e)}")
        db.rollback()
        return None
    finally:
        db.close()


def fetch_new_art_websites() -> Dict:
    """
    Job 1: Fetch new art websites from search engines and seed list
    
    Runs: Weekly (every Monday at 3 AM)
    """
    db = SessionLocal()
    try:
        if not is_automation_enabled(db):
            logger.info("Automation is disabled - skipping fetch_new_art_websites")
            return {"skipped": True, "reason": "automation_disabled"}
    finally:
        db.close()
    
    job_id = log_job_to_db("fetch_new_art_websites", "running")
    logger.info("Starting job: fetch_new_art_websites")
    
    try:
        db = SessionLocal()
        discovery = WebsiteDiscovery()
        logger.info("Starting website discovery...")
        
        # Get location and categories from settings
        from utils.app_settings import AppSettingsManager
        settings_manager = AppSettingsManager(db)
        search_location = settings_manager.get("search_location", None)
        search_categories = settings_manager.get("search_categories", None)
        
        logger.info(f"Starting discovery with location: {search_location}, categories: {search_categories}")
        
        # Pass db session to save discovered websites
        # This will now return ONLY new URLs that don't exist in the database
        discoveries = discovery.discover_art_websites(
            db_session=db,
            location=search_location,  # Can be comma-separated string
            categories=search_categories.split(",") if search_categories else None
        )
        urls = [d['url'] for d in discoveries]
        logger.info(f"Discovery completed. Found {len(urls)} NEW URLs (already filtered duplicates)")
        
        if len(urls) == 0:
            logger.info("No new URLs discovered. All search results already exist in database.")
            logger.info("This is normal if you've run searches before. Try:")
            logger.info("  1. Wait for new websites to appear in search results")
            logger.info("  2. Try different location/category combinations")
            logger.info("  3. Check if search queries are returning results")
        
        # Use less strict quality filtering for discovery to get more results
        scraper_service = ScraperService(db, apply_quality_filter=False)  # Disable quality filter for discovery
        
        new_websites = 0
        skipped = 0
        failed = 0
        
        logger.info(f"Processing {len(urls)} new discovered URLs...")
        
        for discovery_info in discoveries:
            url = discovery_info['url']
            try:
                # Double-check if already exists (shouldn't happen since discovery filters, but safety check)
                existing = db.query(ScrapedWebsite).filter(
                    ScrapedWebsite.url == url
                ).first()
                
                if not existing:
                    logger.info(f"Scraping new website: {url}")
                    website = scraper_service.scrape_website(url, skip_quality_check=True)  # Skip quality check
                    if website:
                        new_websites += 1
                        logger.info(f"Successfully scraped {url} (ID: {website.id})")
                        
                        # Mark discovered website as scraped
                        from db.models import DiscoveredWebsite
                        discovered = db.query(DiscoveredWebsite).filter(
                            DiscoveredWebsite.url == url
                        ).first()
                        if discovered:
                            discovered.is_scraped = True
                            discovered.scraped_website_id = website.id
                            db.commit()
                        
                        # Note: Contact extraction is now automatic in scrape_website()
                        # No need to extract separately here
                    else:
                        failed += 1
                        logger.warning(f"Failed to scrape {url}")
                else:
                    skipped += 1
                    logger.debug(f"Skipping existing website: {url} (shouldn't happen - discovery should have filtered)")
                    # Mark discovered website as scraped if it exists
                    from db.models import DiscoveredWebsite
                    discovered = db.query(DiscoveredWebsite).filter(
                        DiscoveredWebsite.url == url
                    ).first()
                    if discovered and not discovered.is_scraped:
                        discovered.is_scraped = True
                        discovered.scraped_website_id = existing.id
                        db.commit()
            except Exception as e:
                logger.error(f"Error processing URL {url}: {str(e)}", exc_info=True)
                failed += 1
        
        db.close()
        
        result = {
            "discovered": len(urls),  # This is now only NEW discoveries (filtered)
            "new_websites": new_websites,
            "skipped": skipped,
            "failed": failed,
            "message": f"Found {len(urls)} new URLs, scraped {new_websites} successfully"
        }
        
        log_job_to_db("fetch_new_art_websites", "completed", result)
        logger.info(f"Job completed: fetch_new_art_websites - {result}")
        
        return result
        
    except Exception as e:
        error_msg = str(e)
        log_job_to_db("fetch_new_art_websites", "failed", error=error_msg)
        logger.error(f"Job failed: fetch_new_art_websites - {error_msg}")
        return {"error": error_msg}


def scrape_pending_websites() -> Dict:
    """
    Job 2: Scrape websites with status 'pending'
    
    Runs: Every 6 hours
    """
    db = SessionLocal()
    try:
        if not is_automation_enabled(db):
            logger.info("Automation is disabled - skipping scrape_pending_websites")
            return {"skipped": True, "reason": "automation_disabled"}
    finally:
        db.close()
    
    job_id = log_job_to_db("scrape_pending_websites", "running")
    logger.info("Starting job: scrape_pending_websites")
    
    try:
        db = SessionLocal()
        scraper_service = ScraperService(db, apply_quality_filter=True)
        
        # Get pending websites
        pending_websites = db.query(ScrapedWebsite).filter(
            ScrapedWebsite.status == "pending"
        ).limit(50).all()  # Process 50 at a time
        
        processed = 0
        successful = 0
        failed = 0
        
        for website in pending_websites:
            try:
                # Re-scrape the website
                result = scraper_service.scrape_website(
                    website.url,
                    skip_quality_check=False
                )
                
                if result:
                    successful += 1
                else:
                    website.status = "failed"
                    failed += 1
                
                processed += 1
            except Exception as e:
                logger.error(f"Error scraping {website.url}: {str(e)}")
                website.status = "failed"
                failed += 1
                processed += 1
        
        db.commit()
        db.close()
        
        result = {
            "processed": processed,
            "successful": successful,
            "failed": failed
        }
        
        log_job_to_db("scrape_pending_websites", "completed", result)
        logger.info(f"Job completed: scrape_pending_websites - {result}")
        
        return result
        
    except Exception as e:
        error_msg = str(e)
        log_job_to_db("scrape_pending_websites", "failed", error=error_msg)
        logger.error(f"Job failed: scrape_pending_websites - {error_msg}")
        return {"error": error_msg}


def extract_and_store_contacts() -> Dict:
    """
    Job 3: Extract and store contacts from scraped websites
    
    Runs: Every 4 hours
    """
    db = SessionLocal()
    try:
        if not is_automation_enabled(db):
            logger.info("Automation is disabled - skipping extract_and_store_contacts")
            return {"skipped": True, "reason": "automation_disabled"}
    finally:
        db.close()
    
    job_id = log_job_to_db("extract_and_store_contacts", "running")
    logger.info("Starting job: extract_and_store_contacts")
    
    try:
        db = SessionLocal()
        extraction_service = ContactExtractionService(db)
        
        # Get processed websites without contacts
        # Use subquery to find websites without contacts
        from sqlalchemy import not_
        websites_with_contacts = db.query(Contact.website_id).distinct().subquery()
        websites = db.query(ScrapedWebsite).filter(
            ScrapedWebsite.status == "processed"
        ).outerjoin(
            websites_with_contacts, ScrapedWebsite.id == websites_with_contacts.c.website_id
        ).filter(
            websites_with_contacts.c.website_id.is_(None)
        ).limit(30).all()
        
        processed = 0
        emails_found = 0
        phones_found = 0
        social_found = 0
        
        for website in websites:
            try:
                if website.raw_html:
                    result = extraction_service.extract_and_save(
                        website.id,
                        website.raw_html,
                        website.url
                    )
                    
                    if result and "error" not in result:
                        emails_found += result.get("emails_extracted", 0)
                        phones_found += result.get("phones_extracted", 0)
                        social_found += result.get("social_links_extracted", 0)
                        processed += 1
            except Exception as e:
                logger.error(f"Error extracting contacts for website {website.id}: {str(e)}")
        
        db.close()
        
        result = {
            "processed": processed,
            "emails_found": emails_found,
            "phones_found": phones_found,
            "social_found": social_found
        }
        
        log_job_to_db("extract_and_store_contacts", "completed", result)
        logger.info(f"Job completed: extract_and_store_contacts - {result}")
        
        return result
        
    except Exception as e:
        error_msg = str(e)
        log_job_to_db("extract_and_store_contacts", "failed", error=error_msg)
        logger.error(f"Job failed: extract_and_store_contacts - {error_msg}")
        return {"error": error_msg}


def generate_ai_email() -> Dict:
    """
    Job 4: Generate AI emails for contacts that don't have emails yet
    
    Runs: Every 2 hours
    """
    job_id = log_job_to_db("generate_ai_email", "running")
    logger.info("Starting job: generate_ai_email")
    
    try:
        db = SessionLocal()
        email_generator = EmailGenerator(db=db)
        
        # Get contacts with emails that don't have outreach emails yet
        from sqlalchemy import not_
        contacts_with_emails = db.query(OutreachEmail.contact_id).filter(
            OutreachEmail.contact_id.isnot(None)
        ).distinct().subquery()
        
        contacts = db.query(Contact).join(ScrapedWebsite).filter(
            Contact.email.isnot(None),
            Contact.email != ""
        ).outerjoin(
            contacts_with_emails, Contact.id == contacts_with_emails.c.contact_id
        ).filter(
            contacts_with_emails.c.contact_id.is_(None)
        ).limit(20).all()
        
        generated = 0
        failed = 0
        
        for contact in contacts:
            try:
                website = contact.website
                
                # Build context
                context = {
                    "website_summary": website.description or "",
                    "art_style": website.category or website.website_type or "",
                    "category": website.category or website.website_type or "",
                    "description": website.description or "",
                    "metadata": website.metadata or {}
                }
                
                # Generate email
                business_name = contact.name or website.title or "Team"
                result = email_generator.generate_outreach_email(
                    business_name=business_name,
                    website_url=website.url,
                    context=context,
                    provider="gemini"  # or "openai"
                )
                
                if result and "error" not in result:
                    # Create outreach email record
                    outreach_email = OutreachEmail(
                        website_id=website.id,
                        contact_id=contact.id,
                        subject=result["subject"],
                        body=result["body"],
                        recipient_email=contact.email,
                        status="draft",
                        ai_model_used="gemini"
                    )
                    db.add(outreach_email)
                    generated += 1
                else:
                    failed += 1
                    
            except Exception as e:
                logger.error(f"Error generating email for contact {contact.id}: {str(e)}")
                failed += 1
        
        db.commit()
        db.close()
        
        result = {
            "generated": generated,
            "failed": failed
        }
        
        log_job_to_db("generate_ai_email", "completed", result)
        logger.info(f"Job completed: generate_ai_email - {result}")
        
        return result
        
    except Exception as e:
        error_msg = str(e)
        log_job_to_db("generate_ai_email", "failed", error=error_msg)
        logger.error(f"Job failed: generate_ai_email - {error_msg}")
        return {"error": error_msg}


def send_email_if_not_sent() -> Dict:
    """
    Job 5: Send emails that are in 'draft' status
    
    Runs: Every hour
    Only runs if email_trigger_mode is 'automatic'
    """
    db = SessionLocal()
    try:
        if not is_automation_enabled(db):
            logger.info("Automation is disabled - skipping send_email_if_not_sent")
            return {"skipped": True, "reason": "automation_disabled"}
        
        # Check email trigger mode
        settings_manager = AppSettingsManager(db)
        trigger_mode = settings_manager.get_email_trigger_mode()
        
        if trigger_mode != "automatic":
            logger.info(f"Email trigger mode is '{trigger_mode}' - skipping automatic email sending")
            return {"skipped": True, "reason": f"email_mode_{trigger_mode}"}
    finally:
        db.close()
    
    job_id = log_job_to_db("send_email_if_not_sent", "running")
    logger.info("Starting job: send_email_if_not_sent")
    
    try:
        db = SessionLocal()
        
        # Double-check automation and email trigger mode (in case it changed)
        if not is_automation_enabled(db):
            logger.info("Automation disabled during execution - stopping")
            return {"skipped": True, "reason": "automation_disabled"}
        
        settings_manager = AppSettingsManager(db)
        trigger_mode = settings_manager.get_email_trigger_mode()
        if trigger_mode != "automatic":
            logger.info(f"Email mode is '{trigger_mode}' - stopping")
            return {"skipped": True, "reason": f"email_mode_{trigger_mode}"}
        
        email_sender = OutreachEmailSender(db, use_gmail=True, max_retries=3)
        
        # Get draft emails
        draft_emails = db.query(OutreachEmail).filter(
            OutreachEmail.status == "draft"
        ).limit(10).all()  # Send 10 at a time to avoid rate limits
        
        sent = 0
        failed = 0
        
        for email in draft_emails:
            try:
                website = email.website
                result = email_sender.send_outreach_email(
                    to_email=email.recipient_email,
                    subject=email.subject,
                    body=email.body,
                    website_id=email.website_id,
                    contact_id=email.contact_id,
                    use_html=True,
                    business_name=website.title
                )
                
                if result.get("success"):
                    sent += 1
                else:
                    failed += 1
                    
            except Exception as e:
                logger.error(f"Error sending email {email.id}: {str(e)}")
                failed += 1
        
        db.close()
        
        result = {
            "sent": sent,
            "failed": failed
        }
        
        log_job_to_db("send_email_if_not_sent", "completed", result)
        logger.info(f"Job completed: send_email_if_not_sent - {result}")
        
        return result
        
    except Exception as e:
        error_msg = str(e)
        log_job_to_db("send_email_if_not_sent", "failed", error=error_msg)
        logger.error(f"Job failed: send_email_if_not_sent - {error_msg}")
        return {"error": error_msg}

