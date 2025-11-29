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

# Add repo root to path to import worker.clients
# This allows us to import from worker.clients.dataforseo
backend_dir = Path(__file__).resolve().parents[2]
repo_root = backend_dir.parent  # Go up one more level to repo root
if repo_root.exists():
    sys.path.insert(0, str(repo_root))
    logger = logging.getLogger(__name__)
    logger.info(f"Added repo root to path: {repo_root}")
else:
    # Fallback: try adding worker directory directly
    worker_dir = backend_dir / "worker"
    if worker_dir.exists():
        sys.path.insert(0, str(worker_dir))

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
            # Import DataForSEO client
            try:
                from worker.clients.dataforseo import DataForSEOClient
            except ImportError:
                logger.error("DataForSEO client not available. Make sure worker/clients/dataforseo.py exists.")
                job.status = "failed"
                job.error_message = "DataForSEO client not available"
                await db.commit()
                return {"error": "DataForSEO client not available"}
            
            client = DataForSEOClient()
        except ValueError as e:
            logger.error(f"DataForSEO configuration error: {e}")
            job.status = "failed"
            job.error_message = f"DataForSEO configuration error: {e}"
            await db.commit()
            return {"error": str(e)}
        
        all_prospects = []
        discovered_domains = set()
        
        try:
            for loc in locations:
                location_code = client.get_location_code(loc)
                search_queries = _generate_search_queries(keywords, categories)
                
                logger.info(f"Processing location {loc} with {len(search_queries)} queries")
                
                for query in search_queries:
                    if len(all_prospects) >= max_results:
                        break
                    
                    try:
                        # Call DataForSEO API
                        serp_results = await client.serp_google_organic(query, location_code, depth=10)
                        
                        if not serp_results or not serp_results.get("success"):
                            logger.warning(f"No results for query: {query} - {serp_results.get('error', 'Unknown error')}")
                            continue
                        
                        # Process results
                        results = serp_results.get("results", [])
                        for result_item in results:
                            if len(all_prospects) >= max_results:
                                break
                            
                            url = result_item.get("url", "")
                            if not url or not url.startswith("http"):
                                continue
                            
                            # Parse and normalize URL
                            parsed = urlparse(url)
                            domain = parsed.netloc.lower().replace("www.", "")
                            normalized_url = url
                            
                            # Check if domain already discovered
                            if domain in discovered_domains:
                                continue
                            
                            # Check database for existing prospect
                            existing = await db.execute(
                                select(Prospect).where(Prospect.domain == domain)
                            )
                            if existing.scalar_one_or_none():
                                discovered_domains.add(domain)
                                continue
                            
                            # Create prospect
                            prospect = Prospect(
                                domain=domain,
                                page_url=normalized_url,
                                page_title=result_item.get("title", "")[:500],
                                page_snippet=result_item.get("description", "")[:1000],
                                country=loc,
                                outreach_status="pending"
                            )
                            
                            db.add(prospect)
                            discovered_domains.add(domain)
                            all_prospects.append(prospect)
                            
                            logger.info(f"Discovered: {domain}")
                        
                        # Small delay to respect rate limits
                        await asyncio.sleep(1)
                    
                    except Exception as e:
                        logger.error(f"Error processing query '{query}': {e}", exc_info=True)
                        continue
                
                if len(all_prospects) >= max_results:
                    break
            
            # Commit all prospects
            await db.commit()
            
            # Update job status
            job.status = "completed"
            job.result = {
                "prospects_discovered": len(all_prospects),
                "locations": locations,
                "categories": categories,
                "keywords": keywords
            }
            await db.commit()
            
            logger.info(f"✅ Discovery job {job_id} completed: {len(all_prospects)} prospects discovered")
            
            return {
                "job_id": job_id,
                "status": "completed",
                "prospects_discovered": len(all_prospects)
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

