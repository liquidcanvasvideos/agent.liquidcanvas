"""
Discovery task - processes website discovery jobs directly in backend
This allows us to run without a separate worker service (free tier compatible)
"""
import os
import sys
import asyncio
import logging
from typing import Dict, Any, List
from pathlib import Path
from urllib.parse import urlparse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from dotenv import load_dotenv

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

# Configure logger after path setup
if 'logger' not in locals():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

# Import database session from backend
from app.db.database import AsyncSessionLocal


def _generate_search_queries(keywords: str, categories: List[str]) -> List[str]:
    """
    Generate search queries from keywords and categories
    """
    queries = []
    base_keywords = [kw.strip() for kw in keywords.split(',') if kw.strip()] if keywords else []

    # Add category-specific keywords
    category_map = {
        "home_decor": ["home decor blog", "interior design website", "furniture store online"],
        "holiday": ["holiday gift guide", "seasonal decor shop", "christmas crafts blog"],
        "parenting": ["parenting blog", "mom influencer", "family lifestyle website"],
        "audio_visuals": ["audio visual production", "sound engineering blog", "video editing services"],
        "gift_guides": ["unique gift ideas", "present inspiration", "curated gifts"],
        "tech_innovation": ["tech startup blog", "innovation news", "gadget review site"]
    }

    if not base_keywords and not categories:
        return ["art blog", "creative agency", "design studio"]  # Default if nothing specified

    if base_keywords:
        for bk in base_keywords:
            queries.append(bk)
            for cat in categories:
                if cat in category_map:
                    for ck in category_map[cat]:
                        queries.append(f"{bk} {ck}")
    else:  # Only categories selected
        for cat in categories:
            if cat in category_map:
                for ck in category_map[cat]:
                    queries.append(ck)

    # Ensure uniqueness and limit
    unique_queries = list(dict.fromkeys(queries))
    return unique_queries[:20]


async def discover_websites_async(job_id: str) -> Dict[str, Any]:
    """
    Async function to discover websites for a job
    This runs directly in the backend without needing a separate worker
    """
    from app.models.job import Job
    from app.models.prospect import Prospect
    from uuid import UUID
    
    async with AsyncSessionLocal() as db:
        # Fetch job
        try:
            job_uuid = UUID(job_id)
        except ValueError:
            logger.error(f"Invalid job ID format: {job_id}")
            return {"error": "Invalid job ID format"}
        
        result = await db.execute(select(Job).where(Job.id == job_uuid))
        job = result.scalar_one_or_none()
        
        if not job:
            logger.error(f"Job {job_id} not found")
            return {"error": "Job not found"}
        
        # Update job status
        job.status = "running"
        await db.commit()
        
        params = job.params or {}
        keywords = params.get("keywords", "")
        locations = params.get("locations", ["usa"])
        max_results = params.get("max_results", 100)
        categories = params.get("categories", [])
        
        logger.info(f"Starting discovery job {job_id}: keywords='{keywords}', locations={locations}, categories={categories}")
        
        try:
            # Import DataForSEO client from backend (self-contained)
            try:
                from app.clients.dataforseo import DataForSEOClient
                logger.info("✅ Successfully imported DataForSEO client from backend")
            except ImportError as import_err:
                logger.error(f"❌ Failed to import DataForSEO client: {import_err}")
                job.status = "failed"
                job.error_message = f"DataForSEO client not available: {import_err}"
                await db.commit()
                return {"error": f"DataForSEO client not available: {import_err}"}
            
            # Initialize client (will check credentials)
            try:
                client = DataForSEOClient()
                logger.info("✅ DataForSEO client initialized successfully")
            except ValueError as cred_err:
                logger.error(f"❌ DataForSEO credentials error: {cred_err}")
                logger.error(f"DATAFORSEO_LOGIN is set: {bool(os.getenv('DATAFORSEO_LOGIN'))}")
                logger.error(f"DATAFORSEO_PASSWORD is set: {bool(os.getenv('DATAFORSEO_PASSWORD'))}")
                job.status = "failed"
                job.error_message = f"DataForSEO credentials not configured: {cred_err}"
                await db.commit()
                return {"error": f"DataForSEO credentials not configured: {cred_err}"}
        except Exception as e:
            logger.error(f"Unexpected error initializing DataForSEO client: {e}", exc_info=True)
            job.status = "failed"
            job.error_message = f"Failed to initialize DataForSEO client: {e}"
            await db.commit()
            return {"error": str(e)}
        
        all_prospects = []
        discovered_domains = set()
        
        # Detailed tracking
        search_stats = {
            "total_queries": 0,
            "queries_executed": 0,
            "queries_successful": 0,
            "queries_failed": 0,
            "total_results_found": 0,
            "results_processed": 0,
            "results_skipped_duplicate": 0,
            "results_skipped_existing": 0,
            "results_saved": 0,
            "queries_detail": []
        }
        
        try:
            for loc in locations:
                location_code = client.get_location_code(loc)
                search_queries = _generate_search_queries(keywords, categories)
                search_stats["total_queries"] += len(search_queries)
                
                logger.info(f"📍 Processing location '{loc}' (code: {location_code}) with {len(search_queries)} queries")
                
                for query in search_queries:
                    if len(all_prospects) >= max_results:
                        logger.info(f"⏹️  Reached max_results limit ({max_results}), stopping search")
                        break
                    
                    query_stats = {
                        "query": query,
                        "location": loc,
                        "status": "pending",
                        "results_found": 0,
                        "results_saved": 0,
                        "error": None
                    }
                    search_stats["queries_executed"] += 1
                    
                    try:
                        logger.info(f"🔍 Searching: '{query}' in {loc} (location_code: {location_code})...")
                        # Call DataForSEO API with explicit parameters
                        serp_results = await client.serp_google_organic(
                            keyword=query,
                            location_code=location_code,
                            language_code="en",
                            depth=10,
                            device="desktop"
                        )
                        
                        if not serp_results or not serp_results.get("success"):
                            error_msg = serp_results.get('error', 'Unknown error') if serp_results else 'No response'
                            logger.warning(f"❌ No results for query '{query}' in {loc}: {error_msg}")
                            query_stats["status"] = "failed"
                            query_stats["error"] = error_msg
                            search_stats["queries_failed"] += 1
                            search_stats["queries_detail"].append(query_stats)
                            continue
                        
                        search_stats["queries_successful"] += 1
                        query_stats["status"] = "success"
                        
                        # Process results (defensive check)
                        results = serp_results.get("results")
                        if results is None:
                            logger.warning(f"⚠️  No 'results' key in serp_results for query '{query}'")
                            results = []
                        elif not isinstance(results, list):
                            logger.warning(f"⚠️  'results' is not a list for query '{query}': {type(results)}")
                            results = []
                        
                        query_stats["results_found"] = len(results)
                        search_stats["total_results_found"] += len(results)
                        logger.info(f"✅ Found {len(results)} results for '{query}' in {loc}")
                        
                        for result_item in results:
                            # Defensive check: ensure result_item is a dict
                            if not isinstance(result_item, dict):
                                logger.warning(f"⚠️  Skipping invalid result_item (not a dict): {type(result_item)}")
                                search_stats["results_skipped_duplicate"] += 1
                                continue
                            if len(all_prospects) >= max_results:
                                break
                            
                            search_stats["results_processed"] += 1
                            
                            url = result_item.get("url", "")
                            if not url or not url.startswith("http"):
                                search_stats["results_skipped_duplicate"] += 1
                                continue
                            
                            # Parse and normalize URL (defensive check)
                            parsed = urlparse(url)
                            domain = (parsed.netloc or "").lower().replace("www.", "")
                            if not domain:
                                search_stats["results_skipped_duplicate"] += 1
                                logger.warning(f"⏭️  Skipping invalid URL (no domain): {url}")
                                continue
                            normalized_url = url
                            
                            # Check if domain already discovered in this job
                            if domain in discovered_domains:
                                search_stats["results_skipped_duplicate"] += 1
                                logger.debug(f"⏭️  Skipping duplicate domain in this job: {domain}")
                                continue
                            
                            # Check database for existing prospect
                            existing = await db.execute(
                                select(Prospect).where(Prospect.domain == domain)
                            )
                            if existing.scalar_one_or_none():
                                discovered_domains.add(domain)
                                search_stats["results_skipped_existing"] += 1
                                logger.debug(f"⏭️  Skipping existing domain in database: {domain}")
                                continue
                            
                            # Create prospect
                            # NOTE: Prospect model doesn't have page_snippet or country fields
                            # Store description in dataforseo_payload if needed
                            # Safely get description - handle None values
                            description = result_item.get("description") or ""
                            description = description[:1000] if description else ""
                            
                            # Safely get title - handle None values
                            title = result_item.get("title") or ""
                            title = title[:500] if title else ""
                            
                            prospect = Prospect(
                                domain=domain,
                                page_url=normalized_url,
                                page_title=title,
                                outreach_status="pending",
                                dataforseo_payload={
                                    "description": description,
                                    "location": loc,
                                    "url": normalized_url,
                                    "title": title
                                }
                            )
                            
                            db.add(prospect)
                            discovered_domains.add(domain)
                            all_prospects.append(prospect)
                            query_stats["results_saved"] += 1
                            search_stats["results_saved"] += 1
                            
                            logger.info(f"💾 Saved new prospect: {domain} - {result_item.get('title', '')[:50]}")
                        
                        search_stats["queries_detail"].append(query_stats)
                        
                        # Small delay to respect rate limits
                        await asyncio.sleep(1)
                    
                    except Exception as e:
                        logger.error(f"❌ Error processing query '{query}' in {loc}: {e}", exc_info=True)
                        query_stats["status"] = "error"
                        query_stats["error"] = str(e)
                        search_stats["queries_failed"] += 1
                        search_stats["queries_detail"].append(query_stats)
                        continue
                
                if len(all_prospects) >= max_results:
                    break
            
            # Commit all prospects
            await db.commit()
            logger.info(f"💾 Committed {len(all_prospects)} new prospects to database")
            
            # Update job status with detailed results
            job.status = "completed"
            job.result = {
                "prospects_discovered": len(all_prospects),
                "locations": locations,
                "categories": categories,
                "keywords": keywords,
                "search_statistics": {
                    "total_queries": search_stats["total_queries"],
                    "queries_executed": search_stats["queries_executed"],
                    "queries_successful": search_stats["queries_successful"],
                    "queries_failed": search_stats["queries_failed"],
                    "total_results_found": search_stats["total_results_found"],
                    "results_processed": search_stats["results_processed"],
                    "results_saved": search_stats["results_saved"],
                    "results_skipped_duplicate": search_stats["results_skipped_duplicate"],
                    "results_skipped_existing": search_stats["results_skipped_existing"]
                },
                "queries_detail": search_stats["queries_detail"][:20]  # Limit to first 20 for size
            }
            await db.commit()
            
            logger.info(f"✅ Discovery job {job_id} completed:")
            logger.info(f"   📊 Queries: {search_stats['queries_executed']} executed, {search_stats['queries_successful']} successful, {search_stats['queries_failed']} failed")
            logger.info(f"   🔍 Results: {search_stats['total_results_found']} found, {search_stats['results_saved']} saved")
            logger.info(f"   ⏭️  Skipped: {search_stats['results_skipped_duplicate']} duplicates, {search_stats['results_skipped_existing']} existing")
            
            return {
                "job_id": job_id,
                "status": "completed",
                "prospects_discovered": len(all_prospects),
                "search_statistics": job.result["search_statistics"]
            }
        
        except Exception as e:
            logger.error(f"Discovery job {job_id} failed: {e}", exc_info=True)
            job.status = "failed"
            job.error_message = str(e)
            await db.commit()
            return {"error": str(e)}


async def process_discovery_job(job_id: str):
    """
    Wrapper to process discovery job in background
    This can be called from FastAPI BackgroundTasks or asyncio
    """
    try:
        await discover_websites_async(job_id)
    except Exception as e:
        logger.error(f"Error processing discovery job {job_id}: {e}", exc_info=True)

