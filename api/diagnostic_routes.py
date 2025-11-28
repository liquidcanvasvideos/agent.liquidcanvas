"""
Diagnostic routes to troubleshoot scraping issues
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from db.database import get_db
from jobs.website_discovery import WebsiteDiscovery
from scraper.scraper_service import ScraperService
from db.models import ScrapedWebsite, Contact, ScrapingJob
from sqlalchemy import desc, func
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/diagnostic/search-test")
async def test_search_functionality():
    """Test if DuckDuckGo search is working"""
    try:
        discovery = WebsiteDiscovery()
        
        # Test 1: Simple search
        print("Testing DuckDuckGo search...")
        results = discovery.search_duckduckgo("art gallery", num_results=3)
        
        # Test 2: Seed file
        seed_urls = discovery.fetch_from_seed_list()
        
        return {
            "status": "success",
            "duckduckgo_working": len(results) > 0,
            "duckduckgo_results_count": len(results),
            "duckduckgo_sample": results[:3] if results else [],
            "seed_file_count": len(seed_urls),
            "seed_file_urls": seed_urls[:5],
            "total_discoverable": len(results) + len(seed_urls),
            "message": "Search functionality is working" if len(results) > 0 or len(seed_urls) > 0 else "WARNING: No URLs found! Check network connection and DuckDuckGo access."
        }
    except Exception as e:
        logger.error(f"Search test failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "message": "Search test failed - check logs for details"
        }


@router.get("/diagnostic/scrape-test")
async def test_scrape_functionality(
    url: str = "https://www.behance.net",
    db: Session = Depends(get_db)
):
    """Test if scraping is working"""
    try:
        scraper_service = ScraperService(db, apply_quality_filter=False)
        website = scraper_service.scrape_website(url, skip_quality_check=True)
        
        if website:
            contacts = db.query(Contact).filter(Contact.website_id == website.id).count()
            return {
                "status": "success",
                "website_id": website.id,
                "url": website.url,
                "title": website.title,
                "has_html": bool(website.raw_html),
                "html_length": len(website.raw_html) if website.raw_html else 0,
                "contacts_extracted": contacts,
                "message": "Scraping is working correctly"
            }
        else:
            return {
                "status": "failed",
                "message": "Failed to scrape website - check logs for errors"
            }
    except Exception as e:
        logger.error(f"Scrape test failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "message": "Scrape test failed - check logs for details"
        }


@router.get("/diagnostic/api-status")
async def check_api_status(db: Session = Depends(get_db)):
    """
    Check status of all configured APIs (Hunter.io, DataForSEO)
    """
    from utils.config import settings
    from extractor.hunter_io_client import HunterIOClient
    from extractor.dataforseo_client import DataForSEOClient
    
    results = {
        "hunter_io": {
            "configured": False,
            "working": False,
            "test_result": None,
            "error": None
        },
        "dataforseo": {
            "configured": False,
            "working": False,
            "test_result": None,
            "error": None
        }
    }
    
    # Test Hunter.io
    try:
        api_key = getattr(settings, 'HUNTER_IO_API_KEY', None)
        if api_key and api_key.strip():
            results["hunter_io"]["configured"] = True
            client = HunterIOClient(api_key)
            if client.is_configured():
                # Quick test
                test_result = client.domain_search("liquidcanvas.art")
                results["hunter_io"]["working"] = True
                results["hunter_io"]["test_result"] = {
                    "emails_found": len(test_result.get("emails", [])) if test_result else 0,
                    "domain": "liquidcanvas.art"
                }
            else:
                results["hunter_io"]["error"] = "Client not properly initialized"
        else:
            results["hunter_io"]["error"] = "API key not configured"
    except Exception as e:
        results["hunter_io"]["error"] = str(e)
    
    # Test DataForSEO
    try:
        login = getattr(settings, 'DATAFORSEO_LOGIN', None)
        password = getattr(settings, 'DATAFORSEO_PASSWORD', None)
        if login and password and login.strip() and password.strip():
            results["dataforseo"]["configured"] = True
            client = DataForSEOClient(login, password)
            if client.is_configured():
                # Quick test
                test_result = client.serp_google_organic(
                    keyword="home decor blog",
                    location_code=2840,
                    depth=3
                )
                if test_result and test_result.get("success"):
                    results["dataforseo"]["working"] = True
                    results["dataforseo"]["test_result"] = {
                        "results_found": len(test_result.get("results", [])),
                        "query": "home decor blog"
                    }
                else:
                    results["dataforseo"]["error"] = test_result.get("error", "API call failed")
            else:
                results["dataforseo"]["error"] = "Client not properly initialized"
        else:
            results["dataforseo"]["error"] = "Credentials not configured"
    except Exception as e:
        results["dataforseo"]["error"] = str(e)
    
    return results


@router.get("/diagnostic/full-check")
async def full_diagnostic_check(db: Session = Depends(get_db)):
    """Run full diagnostic check"""
    results = {
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {}
    }
    
    # Check 1: Search functionality
    try:
        discovery = WebsiteDiscovery()
        search_results = discovery.search_duckduckgo("art gallery", num_results=3)
        seed_urls = discovery.fetch_from_seed_list()
        results["checks"]["search"] = {
            "status": "ok" if (len(search_results) > 0 or len(seed_urls) > 0) else "warning",
            "duckduckgo_results": len(search_results),
            "seed_urls": len(seed_urls),
            "message": "Search working" if (len(search_results) > 0 or len(seed_urls) > 0) else "No URLs found - check network"
        }
    except Exception as e:
        results["checks"]["search"] = {
            "status": "error",
            "error": str(e)
        }
    
    # Check 2: Database
    try:
        total_websites = db.query(ScrapedWebsite).count()
        total_contacts = db.query(Contact).count()
        recent_websites = db.query(ScrapedWebsite).filter(
            ScrapedWebsite.created_at >= datetime.utcnow() - timedelta(hours=24)
        ).count()
        results["checks"]["database"] = {
            "status": "ok",
            "total_websites": total_websites,
            "total_contacts": total_contacts,
            "websites_last_24h": recent_websites
        }
    except Exception as e:
        results["checks"]["database"] = {
            "status": "error",
            "error": str(e)
        }
    
    # Check 3: Recent jobs
    try:
        recent_jobs = db.query(ScrapingJob).filter(
            ScrapingJob.job_type == "fetch_new_art_websites"
        ).order_by(desc(ScrapingJob.created_at)).limit(3).all()
        
        jobs_info = []
        for job in recent_jobs:
            jobs_info.append({
                "status": job.status,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "result": job.result,
                "error": job.error_message
            })
        
        results["checks"]["jobs"] = {
            "status": "ok",
            "recent_jobs": jobs_info,
            "latest_status": recent_jobs[0].status if recent_jobs else "never_run"
        }
    except Exception as e:
        results["checks"]["jobs"] = {
            "status": "error",
            "error": str(e)
        }
    
    # Check 4: Test scrape
    try:
        scraper_service = ScraperService(db, apply_quality_filter=False)
        test_website = scraper_service.scrape_website("https://www.behance.net", skip_quality_check=True)
        results["checks"]["scraping"] = {
            "status": "ok" if test_website else "warning",
            "test_scrape_success": test_website is not None,
            "message": "Scraping works" if test_website else "Test scrape failed"
        }
    except Exception as e:
        results["checks"]["scraping"] = {
            "status": "error",
            "error": str(e)
        }
    
    # Overall status
    all_ok = all(
        check.get("status") == "ok" 
        for check in results["checks"].values()
    )
    results["overall_status"] = "ok" if all_ok else "issues_found"
    
    return results

