"""
Dashboard API routes for TypeScript/Next.js frontend
"""
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from pydantic import BaseModel, ConfigDict
from db.database import get_db
from db.models import ScrapedWebsite, Contact, OutreachEmail, ScrapingJob, DiscoveredWebsite
from utils.auth import get_current_user

router = APIRouter()


# Response models
class LeadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    email: Optional[str]
    phone_number: Optional[str]
    social_platform: Optional[str]
    social_url: Optional[str]
    name: Optional[str]
    website_id: int
    website_title: Optional[str]
    website_url: Optional[str]
    website_category: Optional[str]
    created_at: datetime


class EmailListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    subject: str
    recipient_email: str
    status: str
    website_id: int
    contact_id: Optional[int]
    website_title: Optional[str]
    sent_at: Optional[datetime]
    created_at: datetime


class StatsResponse(BaseModel):
    leads_collected: int
    emails_extracted: int
    phones_extracted: int
    social_links_extracted: int
    outreach_sent: int
    outreach_pending: int
    outreach_failed: int
    websites_scraped: int
    websites_pending: int
    websites_failed: int
    jobs_completed: int
    jobs_running: int
    jobs_failed: int
    recent_activity: Dict


class JobStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    job_type: str
    status: str
    result: Optional[Dict]
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime


@router.get("/leads", response_model=Dict)
async def get_leads(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    category: Optional[str] = None,
    has_email: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """
    Get leads/contacts with pagination and filtering
    
    Query params:
    - skip: Number of records to skip
    - limit: Number of records to return (max 200)
    - category: Filter by website category
    - has_email: Filter by whether contact has email
    """
    query = db.query(
        Contact,
        ScrapedWebsite.title,
        ScrapedWebsite.url,
        ScrapedWebsite.category
    ).join(ScrapedWebsite)
    
    # Apply filters
    if category:
        query = query.filter(ScrapedWebsite.category == category)
    
    if has_email is not None:
        if has_email:
            query = query.filter(Contact.email.isnot(None), Contact.email != "")
        else:
            query = query.filter(or_(Contact.email.is_(None), Contact.email == ""))
    
    # Get total count
    total = query.count()
    
    # Get paginated results
    results = query.offset(skip).limit(limit).all()
    
    # Format response
    leads = []
    for contact, title, url, cat in results:
        leads.append({
            "id": contact.id,
            "email": contact.email,
            "phone_number": contact.phone_number,
            "social_platform": contact.social_platform,
            "social_url": contact.social_url,
            "name": contact.name,
            "website_id": contact.website_id,
            "website_title": title,
            "website_url": url,
            "website_category": cat,
            "source": getattr(contact, 'source', 'html'),  # Email source (hunter_io, html, footer, etc.)
            "created_at": contact.created_at
        })
    
    return {
        "leads": leads,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/emails/sent", response_model=Dict)
async def get_sent_emails(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """Get sent emails with pagination"""
    query = db.query(
        OutreachEmail,
        ScrapedWebsite.title
    ).join(ScrapedWebsite).filter(OutreachEmail.status == "sent")
    
    total = query.count()
    results = query.order_by(OutreachEmail.sent_at.desc()).offset(skip).limit(limit).all()
    
    emails = []
    for email, title in results:
        emails.append({
            "id": email.id,
            "subject": email.subject,
            "recipient_email": email.recipient_email,
            "status": email.status,
            "website_id": email.website_id,
            "contact_id": email.contact_id,
            "website_title": title,
            "sent_at": email.sent_at,
            "created_at": email.created_at
        })
    
    return {
        "emails": emails,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/emails/pending", response_model=Dict)
async def get_pending_emails(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """Get pending/draft emails with pagination"""
    query = db.query(
        OutreachEmail,
        ScrapedWebsite.title
    ).join(ScrapedWebsite).filter(OutreachEmail.status == "draft")
    
    total = query.count()
    results = query.order_by(OutreachEmail.created_at.desc()).offset(skip).limit(limit).all()
    
    emails = []
    for email, title in results:
        emails.append({
            "id": email.id,
            "subject": email.subject,
            "recipient_email": email.recipient_email,
            "status": email.status,
            "website_id": email.website_id,
            "contact_id": email.contact_id,
            "website_title": title,
            "created_at": email.created_at
        })
    
    return {
        "emails": emails,
        "total": total,
        "skip": skip,
        "limit": limit
    }


def extract_contacts_for_website(website_id: int, db: Session):
    """Helper function to extract contacts for a website"""
    from extractor.contact_extraction_service import ContactExtractionService
    try:
        extraction_service = ContactExtractionService(db)
        extraction_service.extract_and_store_contacts(website_id)
    except Exception as e:
        import logging
        logging.error(f"Failed to extract contacts for website {website_id}: {e}")


@router.post("/scrape-url")
async def scrape_url(
    url: str,
    skip_quality_check: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """
    Scrape a URL and return results with contacts
    
    Query params:
    - url: URL to scrape
    - skip_quality_check: Bypass quality filtering
    """
    from scraper.scraper_service import ScraperService
    from extractor.contact_extraction_service import ContactExtractionService
    from utils.activity_logger import ActivityLogger
    
    activity_logger = ActivityLogger(db)
    
    # Log start
    activity_logger.log_scrape_start(url)
    
    scraper_service = ScraperService(db, apply_quality_filter=not skip_quality_check)
    website = scraper_service.scrape_website(url, skip_quality_check=skip_quality_check)
    
    if not website:
        activity_logger.log(
            activity_type="scrape",
            message=f"Failed to scrape: {url}",
            status="error",
            metadata={"url": url}
        )
        raise HTTPException(
            status_code=400,
            detail="Failed to scrape website or website does not meet quality requirements"
        )
    
    # Log successful scrape
    activity_logger.log_scrape_success(url, website.id, website.title, website.category)
    
    # Extract contacts synchronously and return them
    activity_logger.log_extraction_start(website.id, url)
    
    extraction_service = ContactExtractionService(db)
    extraction_result = extraction_service.extract_and_store_contacts(website.id)
    
    # Get extracted contacts
    contacts = db.query(Contact).filter(Contact.website_id == website.id).all()
    
    # Log extraction success
    emails_count = len([c for c in contacts if c.email])
    phones_count = len([c for c in contacts if c.phone_number])
    social_count = len([c for c in contacts if c.social_platform])
    
    activity_logger.log_extraction_success(website.id, emails_count, phones_count, social_count)
    
    # Format contacts for response
    contacts_data = []
    for contact in contacts:
        contacts_data.append({
            "id": contact.id,
            "email": contact.email,
            "phone_number": contact.phone_number,
            "social_platform": contact.social_platform,
            "social_url": contact.social_url,
            "name": contact.name,
            "role": contact.role
        })
    
    return {
        "id": website.id,
        "url": website.url,
        "domain": website.domain,
        "title": website.title,
        "description": website.description,
        "category": website.category,
        "website_type": website.website_type,
        "quality_score": website.quality_score,
        "is_art_related": website.is_art_related,
        "status": website.status,
        "created_at": website.created_at,
        "contacts": contacts_data,
        "extraction_stats": {
            "emails_found": emails_count,
            "phones_found": phones_count,
            "social_links_found": social_count,
            "total_contacts": len(contacts)
        }
    }


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """Get comprehensive statistics for dashboard"""
    
    # Leads/Contacts stats
    total_leads = db.query(Contact).count()
    emails_extracted = db.query(Contact).filter(
        Contact.email.isnot(None),
        Contact.email != ""
    ).count()
    phones_extracted = db.query(Contact).filter(
        Contact.phone_number.isnot(None),
        Contact.phone_number != ""
    ).count()
    social_links_extracted = db.query(Contact).filter(
        Contact.social_platform.isnot(None)
    ).count()
    
    # Email stats
    outreach_sent = db.query(OutreachEmail).filter(OutreachEmail.status == "sent").count()
    outreach_pending = db.query(OutreachEmail).filter(OutreachEmail.status == "draft").count()
    outreach_failed = db.query(OutreachEmail).filter(OutreachEmail.status == "failed").count()
    
    # Website stats
    websites_scraped = db.query(ScrapedWebsite).filter(
        ScrapedWebsite.status == "processed"
    ).count()
    websites_pending = db.query(ScrapedWebsite).filter(
        ScrapedWebsite.status == "pending"
    ).count()
    websites_failed = db.query(ScrapedWebsite).filter(
        ScrapedWebsite.status == "failed"
    ).count()
    
    # Job stats
    jobs_completed = db.query(ScrapingJob).filter(
        ScrapingJob.status == "completed"
    ).count()
    jobs_running = db.query(ScrapingJob).filter(
        ScrapingJob.status == "running"
    ).count()
    jobs_failed = db.query(ScrapingJob).filter(
        ScrapingJob.status == "failed"
    ).count()
    
    # Recent activity (last 24 hours)
    yesterday = datetime.utcnow() - timedelta(days=1)
    
    recent_leads = db.query(Contact).filter(
        Contact.created_at >= yesterday
    ).count()
    
    recent_emails_sent = db.query(OutreachEmail).filter(
        OutreachEmail.status == "sent",
        OutreachEmail.sent_at >= yesterday
    ).count()
    
    recent_websites = db.query(ScrapedWebsite).filter(
        ScrapedWebsite.created_at >= yesterday
    ).count()
    
    recent_activity = {
        "leads_last_24h": recent_leads,
        "emails_sent_last_24h": recent_emails_sent,
        "websites_scraped_last_24h": recent_websites
    }
    
    return StatsResponse(
        leads_collected=total_leads,
        emails_extracted=emails_extracted,
        phones_extracted=phones_extracted,
        social_links_extracted=social_links_extracted,
        outreach_sent=outreach_sent,
        outreach_pending=outreach_pending,
        outreach_failed=outreach_failed,
        websites_scraped=websites_scraped,
        websites_pending=websites_pending,
        websites_failed=websites_failed,
        jobs_completed=jobs_completed,
        jobs_running=jobs_running,
        jobs_failed=jobs_failed,
        recent_activity=recent_activity
    )


@router.get("/jobs/status", response_model=List[JobStatusResponse])
async def get_job_status(
    limit: int = Query(20, ge=1, le=100),
    job_type: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """
    Get status of background jobs
    
    Query params:
    - limit: Number of jobs to return
    - job_type: Filter by job type
    - status: Filter by status (pending, running, completed, failed)
    """
    query = db.query(ScrapingJob)
    
    if job_type:
        query = query.filter(ScrapingJob.job_type == job_type)
    
    if status:
        query = query.filter(ScrapingJob.status == status)
    
    jobs = query.order_by(ScrapingJob.created_at.desc()).limit(limit).all()
    
    return jobs


@router.get("/jobs/latest", response_model=Dict)
async def get_latest_jobs(
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """Get latest job execution for each job type"""
    job_types = [
        "fetch_new_art_websites",
        "scrape_pending_websites",
        "extract_and_store_contacts",
        "generate_ai_email",
        "send_email_if_not_sent"
    ]
    
    latest_jobs = {}
    
    for job_type in job_types:
        job = db.query(ScrapingJob).filter(
            ScrapingJob.job_type == job_type
        ).order_by(ScrapingJob.created_at.desc()).first()
        
        if job:
            latest_jobs[job_type] = {
                "status": job.status,
                "result": job.result,
                "error_message": job.error_message,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "created_at": job.created_at.isoformat() if job.created_at else None
            }
        else:
            latest_jobs[job_type] = {
                "status": "never_run",
                "result": None,
                "error_message": None,
                "started_at": None,
                "completed_at": None,
                "created_at": None
            }
    
    return latest_jobs


@router.get("/activity", response_model=Dict)
async def get_activity(
    limit: int = Query(50, ge=1, le=200),
    activity_type: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """
    Get real-time activity logs
    
    Query params:
    - limit: Number of activities to return
    - activity_type: Filter by type (scrape, extract, email, job)
    - status: Filter by status (info, success, warning, error)
    """
    try:
        from db.models import ActivityLog
        
        # Try to query, but handle if table doesn't exist
        try:
            query = db.query(ActivityLog)
            
            if activity_type:
                query = query.filter(ActivityLog.activity_type == activity_type)
            
            if status:
                query = query.filter(ActivityLog.status == status)
            
            activities = query.order_by(ActivityLog.created_at.desc()).limit(limit).all()
            
            activity_list = []
            for activity in activities:
                activity_list.append({
                    "id": activity.id,
                    "activity_type": activity.activity_type,
                    "message": activity.message,
                    "status": activity.status,
                    "website_id": activity.website_id,
                    "job_id": activity.job_id,
                    "metadata": activity.extra_data if hasattr(activity, 'extra_data') and activity.extra_data else {},
                    "created_at": activity.created_at.isoformat() if activity.created_at else None
                })
            
            return {
                "activities": activity_list,
                "total": len(activity_list)
            }
        except Exception as db_error:
            # Table might not exist yet - return empty
            import logging
            logging.warning(f"ActivityLog query failed (table may not exist): {db_error}")
            return {
                "activities": [],
                "total": 0
            }
    except ImportError:
        # ActivityLog model not available
        return {
            "activities": [],
            "total": 0
        }
    except Exception as e:
        # Any other error
        import logging
        logging.error(f"Error in get_activity: {e}")
        return {
            "activities": [],
            "total": 0
        }


class DiscoveredWebsiteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    url: str
    domain: Optional[str]
    title: Optional[str]
    snippet: Optional[str]
    source: str
    search_query: Optional[str]
    category: Optional[str]
    is_scraped: bool
    scraped_website_id: Optional[int]
    created_at: datetime


@router.get("/discovered", response_model=Dict)
async def get_discovered_websites(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    is_scraped: Optional[bool] = Query(None),
    source: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """
    Get list of discovered websites
    
    Query params:
    - skip: Number of records to skip
    - limit: Maximum number of records to return
    - is_scraped: Filter by scraped status (true/false)
    - source: Filter by source (duckduckgo, seed_list, etc.)
    - category: Filter by category
    """
    try:
        query = db.query(DiscoveredWebsite)
        
        # Apply filters
        if is_scraped is not None:
            query = query.filter(DiscoveredWebsite.is_scraped == is_scraped)
        if source:
            query = query.filter(DiscoveredWebsite.source == source)
        if category:
            query = query.filter(DiscoveredWebsite.category == category)
        
        # Get total count
        total = query.count()
        
        # Get paginated results
        discovered = query.order_by(DiscoveredWebsite.created_at.desc()).offset(skip).limit(limit).all()
        
        # Format response
        discovered_list = []
        for d in discovered:
            discovered_list.append({
                "id": d.id,
                "url": d.url,
                "domain": d.domain,
                "title": d.title,
                "snippet": d.snippet,
                "source": d.source,
                "search_query": d.search_query,
                "category": d.category,
                "is_scraped": d.is_scraped,
                "scraped_website_id": d.scraped_website_id,
                "created_at": d.created_at.isoformat() if d.created_at else None
            })
        
        return {
            "discovered": discovered_list,
            "total": total,
            "skip": skip,
            "limit": limit,
            "filters": {
                "is_scraped": is_scraped,
                "source": source,
                "category": category
            }
        }
    except Exception as e:
        import logging
        logging.error(f"Error in get_discovered_websites: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching discovered websites: {str(e)}")
