"""
API routes for website discovery and manual job triggers
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Dict
from db.database import get_db
from jobs.automation_jobs import fetch_new_art_websites
from jobs.website_discovery import WebsiteDiscovery
from utils.auth import get_current_user
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/discovery/search-now")
async def trigger_website_discovery(
    background_tasks: BackgroundTasks,
    location: str = None,
    categories: str = None,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """
    Manually trigger website discovery and scraping
    
    Query params:
    - location: Optional location filter (usa, canada, uk_london, germany, france, europe)
    - categories: Optional comma-separated category list (home_decor, holiday, parenting, etc.)
    
    This will:
    1. Search DuckDuckGo for websites in specified location/categories
    2. Load URLs from seed_websites.txt
    3. Scrape discovered websites
    4. Extract contacts
    
    Returns immediately, runs in background
    """
    try:
        # Check if automation is enabled
        from utils.app_settings import AppSettingsManager
        settings_manager = AppSettingsManager(db)
        if not settings_manager.get_automation_enabled():
            raise HTTPException(
                status_code=400,
                detail="Automation is disabled. Please enable the Master Switch first."
            )
        
        # Check if at least one location is provided
        if not location:
            raise HTTPException(
                status_code=400,
                detail="Location selection is required. Please select at least one location first."
            )
        
        # Check if a job is already running
        from db.models import ScrapingJob
        running_job = db.query(ScrapingJob).filter(
            ScrapingJob.job_type == "fetch_new_art_websites",
            ScrapingJob.status == "running"
        ).first()
        
        if running_job:
            raise HTTPException(
                status_code=400,
                detail="A discovery job is already running. Please stop it first."
            )
        
        # Save location and categories to settings for the job
        if location:
            # Location can be comma-separated, save as-is
            settings_manager.set("search_location", location)
            logger.info(f"Saved search location: {location}")
        if categories:
            settings_manager.set("search_categories", categories)
            logger.info(f"Saved search categories: {categories}")
        
        db.commit()  # Ensure settings are saved before job runs
        
        # Run in background
        background_tasks.add_task(fetch_new_art_websites)
        
        logger.info(f"Started discovery job with location={location}, categories={categories}")
        
        return {
            "message": "Website discovery started in background",
            "status": "running",
            "location": location or "all",
            "categories": categories or "all",
            "note": "Check the Activity Feed for progress updates"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering discovery: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start discovery: {str(e)}"
        )


@router.get("/discovery/test-search")
async def test_search(
    query: str = "home decor blog",
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """
    Test search functionality without scraping
    
    Query params:
    - query: Search query to test
    """
    try:
        discovery = WebsiteDiscovery()
        
        # Test DuckDuckGo search
        results = discovery.search_duckduckgo(query, num_results=5)
        
        # Test seed file
        seed_urls = discovery.fetch_from_seed_list()
        
        return {
            "query": query,
            "duckduckgo_results": results,
            "seed_file_urls": seed_urls,
            "total_found": len(results) + len(seed_urls)
        }
    except Exception as e:
        logger.error(f"Error testing search: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Search test failed: {str(e)}"
        )


@router.get("/discovery/locations")
async def get_locations(
    current_user: str = Depends(get_current_user)
):
    """Get all available search locations"""
    from utils.location_search import get_all_locations
    return {"locations": get_all_locations()}


@router.get("/discovery/categories")
async def get_categories(
    current_user: str = Depends(get_current_user)
):
    """Get all available search categories"""
    from utils.location_search import get_all_categories
    return {"categories": get_all_categories()}


@router.get("/discovery/status")
async def get_discovery_status(
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """
    Get status of website discovery with search source information
    """
    from db.models import ScrapingJob, DiscoveredWebsite
    from sqlalchemy import func, desc
    
    # Get latest discovery job
    latest_job = db.query(ScrapingJob).filter(
        ScrapingJob.job_type == "fetch_new_art_websites"
    ).order_by(desc(ScrapingJob.created_at)).first()
    
    if not latest_job:
        return {
            "status": "never_run",
            "message": "Discovery has never been run",
            "last_run": None
        }
    
    # Check if job is stuck in "running" status for more than 30 minutes
    from datetime import datetime, timedelta
    if latest_job.status == "running" and latest_job.started_at:
        time_since_start = datetime.utcnow() - latest_job.started_at
        if time_since_start > timedelta(minutes=30):
            logger.warning(f"Job {latest_job.id} has been running for {time_since_start}, marking as failed")
            latest_job.status = "failed"
            latest_job.error_message = f"Job timed out after {time_since_start}"
            latest_job.completed_at = datetime.utcnow()
            db.commit()
    
    # Get search source breakdown from recent discoveries (last hour)
    recent_discoveries = db.query(
        DiscoveredWebsite.source,
        func.count(DiscoveredWebsite.id).label('count')
    ).filter(
        DiscoveredWebsite.created_at >= func.datetime('now', '-1 hour')
    ).group_by(DiscoveredWebsite.source).all()
    
    source_breakdown = {source: count for source, count in recent_discoveries}
    
    # Get search queries used in last hour
    recent_queries = db.query(
        DiscoveredWebsite.search_query,
        func.count(DiscoveredWebsite.id).label('count')
    ).filter(
        DiscoveredWebsite.created_at >= func.datetime('now', '-1 hour'),
        DiscoveredWebsite.search_query.isnot(None),
        DiscoveredWebsite.search_query != ''
    ).group_by(DiscoveredWebsite.search_query).order_by(desc('count')).limit(10).all()
    
    return {
        "status": latest_job.status,
        "last_run": latest_job.created_at.isoformat() if latest_job.created_at else None,
        "result": latest_job.result,
        "error": latest_job.error_message,
        "started_at": latest_job.started_at.isoformat() if latest_job.started_at else None,
        "completed_at": latest_job.completed_at.isoformat() if latest_job.completed_at else None,
        "search_sources": source_breakdown,
        "recent_queries": [{"query": q, "count": c} for q, c in recent_queries]
    }


@router.post("/discovery/stop")
async def stop_discovery(
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """
    Stop a running discovery job
    """
    from db.models import ScrapingJob
    from jobs.scheduler import scheduler
    from datetime import datetime
    
    # Get latest running job
    latest_job = db.query(ScrapingJob).filter(
        ScrapingJob.job_type == "fetch_new_art_websites",
        ScrapingJob.status == "running"
    ).order_by(ScrapingJob.created_at.desc()).first()
    
    if not latest_job:
        raise HTTPException(
            status_code=404,
            detail="No running discovery job found"
        )
    
    # Mark job as cancelled
    latest_job.status = "cancelled"
    latest_job.error_message = "Cancelled by user"
    latest_job.completed_at = datetime.utcnow()
    db.commit()
    
    # Try to remove job from scheduler if it exists
    if scheduler and scheduler.running:
        try:
            job = scheduler.get_job('fetch_new_art_websites')
            if job:
                scheduler.remove_job('fetch_new_art_websites')
        except Exception as e:
            logger.warning(f"Could not remove job from scheduler: {e}")
    
    logger.info(f"Discovery job {latest_job.id} cancelled by user")
    
    return {
        "message": "Discovery job stopped",
        "job_id": latest_job.id,
        "status": "cancelled"
    }

