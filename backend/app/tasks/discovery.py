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
    from app.models.discovery_query import DiscoveryQuery
    from uuid import UUID
    from datetime import datetime, timezone, timedelta
    
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
        
        # Check if job was cancelled
        if job.status == "cancelled":
            logger.info(f"Job {job_id} was cancelled, stopping execution")
            return {"error": "Job was cancelled"}
        
        # Update job status and record start time
        job.status = "running"
        start_time = datetime.now(timezone.utc)
        await db.commit()
        
        # Maximum execution time: 2 hours
        MAX_EXECUTION_TIME = timedelta(hours=2)
        
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
                # Check for timeout or cancellation
                elapsed_time = datetime.now(timezone.utc) - start_time
                if elapsed_time > MAX_EXECUTION_TIME:
                    logger.warning(f"⏱️  Job {job_id} exceeded maximum execution time ({MAX_EXECUTION_TIME}), stopping")
                    job.status = "failed"
                    job.error_message = f"Job exceeded maximum execution time of {MAX_EXECUTION_TIME}"
                    await db.commit()
                    return {"error": "Job exceeded maximum execution time"}
                
                # Re-check job status in case it was cancelled
                await db.refresh(job)
                if job.status == "cancelled":
                    logger.info(f"Job {job_id} was cancelled during execution")
                    return {"error": "Job was cancelled"}
                
                location_code = client.get_location_code(loc)
                search_queries = _generate_search_queries(keywords, categories)
                search_stats["total_queries"] += len(search_queries)
                
                logger.info(f"📍 Processing location '{loc}' (code: {location_code}) with {len(search_queries)} queries")
                
                for query in search_queries:
                    # Check for timeout or cancellation before each query
                    elapsed_time = datetime.now(timezone.utc) - start_time
                    if elapsed_time > MAX_EXECUTION_TIME:
                        logger.warning(f"⏱️  Job {job_id} exceeded maximum execution time, stopping")
                        job.status = "failed"
                        job.error_message = f"Job exceeded maximum execution time of {MAX_EXECUTION_TIME}"
                        await db.commit()
                        return {"error": "Job exceeded maximum execution time"}
                    
                    # Re-check job status
                    await db.refresh(job)
                    if job.status == "cancelled":
                        logger.info(f"Job {job_id} was cancelled during execution")
                        return {"error": "Job was cancelled"}
                    if len(all_prospects) >= max_results:
                        logger.info(f"⏹️  Reached max_results limit ({max_results}), stopping search")
                        break
                    
                    # Determine category for this query
                    query_category = None
                    for cat in categories:
                        category_keywords = {
                            "home_decor": ["home decor", "interior design", "furniture"],
                            "holiday": ["holiday", "seasonal", "christmas"],
                            "parenting": ["parenting", "mom", "family"],
                            "audio_visuals": ["audio visual", "sound engineering", "video editing"],
                            "gift_guides": ["gift", "present"],
                            "tech_innovation": ["tech", "startup", "innovation", "gadget"]
                        }
                        if cat in category_keywords:
                            if any(kw in query.lower() for kw in category_keywords[cat]):
                                query_category = cat
                                break
                    
                    # Create DiscoveryQuery record
                    discovery_query = DiscoveryQuery(
                        job_id=job.id,
                        keyword=query,
                        location=loc,
                        location_code=location_code,
                        category=query_category,
                        status="pending"
                    )
                    db.add(discovery_query)
                    await db.flush()  # Flush to get the ID
                    
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
                            
                            # Update DiscoveryQuery record
                            discovery_query.status = "failed"
                            discovery_query.error_message = error_msg
                            await db.commit()
                            continue
                        
                        search_stats["queries_successful"] += 1
                        query_stats["status"] = "success"
                        discovery_query.status = "success"
                        
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
                        discovery_query.results_found = len(results)
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
                                discovery_query.results_skipped_duplicate += 1
                                logger.debug(f"⏭️  Skipping duplicate domain in this job: {domain}")
                                continue
                            
                            # Check database for existing prospect
                            existing = await db.execute(
                                select(Prospect).where(Prospect.domain == domain)
                            )
                            if existing.scalar_one_or_none():
                                discovered_domains.add(domain)
                                search_stats["results_skipped_existing"] += 1
                                discovery_query.results_skipped_existing += 1
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
                            
                            # OPTIONAL: Try to extract email immediately using Hunter.io
                            # This is optional - if it fails, enrichment job will handle it later
                            contact_email = None
                            hunter_payload = None
                            
                            try:
                                from app.clients.hunter import HunterIOClient
                                hunter_client = HunterIOClient()
                                hunter_result = await hunter_client.domain_search(domain)
                                
                                if hunter_result.get("success") and hunter_result.get("emails"):
                                    emails = hunter_result["emails"]
                                    if emails and len(emails) > 0:
                                        first_email = emails[0]
                                        email_value = first_email.get("value")
                                        if email_value:
                                            contact_email = email_value
                                            hunter_payload = hunter_result
                                            logger.info(f"📧 Found email during discovery for {domain}: {email_value}")
                            except Exception as e:
                                # Don't fail discovery if Hunter.io fails - enrichment will handle it
                                logger.debug(f"⚠️  Could not extract email during discovery for {domain}: {e}")
                            
                            prospect = Prospect(
                                domain=domain,
                                page_url=normalized_url,
                                page_title=title,
                                contact_email=contact_email,  # May be None, enrichment will fix
                                outreach_status="pending",
                                discovery_query_id=discovery_query.id,  # Link to discovery query
                                hunter_payload=hunter_payload,  # May be None
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
                            
                            # Update query counters
                            discovery_query.results_saved += 1
                            
                            # Safely get title for logging
                            log_title = result_item.get("title") or ""
                            log_title = log_title[:50] if log_title else "No title"
                            email_status = f" (email: {contact_email})" if contact_email else " (no email)"
                            logger.info(f"💾 Saved new prospect: {domain} - {log_title}{email_status}")
                        
                        search_stats["queries_detail"].append(query_stats)
                        
                        # Small delay to respect rate limits
                        await asyncio.sleep(1)
                    
                    except Exception as e:
                        logger.error(f"❌ Error processing query '{query}' in {loc}: {e}", exc_info=True)
                        query_stats["status"] = "error"
                        query_stats["error"] = str(e)
                        search_stats["queries_failed"] += 1
                        search_stats["queries_detail"].append(query_stats)
                        
                        # Update DiscoveryQuery record
                        discovery_query.status = "failed"
                        discovery_query.error_message = str(e)
                        await db.commit()
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
            
            # Auto-trigger enrichment if prospects were discovered
            if len(all_prospects) > 0:
                try:
                    from app.tasks.enrichment import process_enrichment_job
                    import asyncio
                    
                    # Create enrichment job
                    enrichment_job = Job(
                        job_type="enrich",
                        params={
                            "prospect_ids": None,  # Enrich all newly discovered
                            "max_prospects": len(all_prospects)
                        },
                        status="pending"
                    )
                    db.add(enrichment_job)
                    await db.commit()
                    await db.refresh(enrichment_job)
                    
                    # Start enrichment in background
                    asyncio.create_task(process_enrichment_job(str(enrichment_job.id)))
                    logger.info(f"🔄 Auto-triggered enrichment job {enrichment_job.id} for {len(all_prospects)} prospects")
                except Exception as e:
                    logger.warning(f"⚠️  Failed to auto-trigger enrichment: {e}")
                    # Don't fail discovery job if enrichment trigger fails
            
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

