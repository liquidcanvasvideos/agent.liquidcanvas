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
from app.db.transaction_helpers import safe_commit, safe_flush


def _generate_search_queries(keywords: str, categories: List[str], locations: List[str]) -> List[str]:
    """
    Generate search queries from keywords, categories, and locations.
    Creates queries by combining categories/keywords with locations.
    
    Examples:
    - "Art Gallery" + "United States" -> "Art Gallery United States"
    - "contemporary art" + "United Kingdom" -> "contemporary art United Kingdom"
    - "Art Gallery" + "contemporary art" + "United States" -> "Art Gallery contemporary art United States"
    """
    queries = []
    
    # Parse keywords into list
    base_keywords = [kw.strip() for kw in keywords.split(',') if kw.strip()] if keywords else []
    
    # Category to search term mapping (use category names directly as they're user-friendly)
    # Categories come from frontend as: "Art Gallery", "Museum", "Art Studio", etc.
    category_terms = [cat.strip() for cat in categories if cat and cat.strip()] if categories else []
    
    # If no inputs provided, return empty list (will be caught and job will fail)
    if not base_keywords and not category_terms and not locations:
        return []
    
    # Generate queries: category/keyword × location combinations
    search_terms = []
    
    # Add categories as search terms
    search_terms.extend(category_terms)
    
    # Add keywords as search terms
    search_terms.extend(base_keywords)
    
    # If no search terms but locations exist, use generic art-related terms
    if not search_terms and locations:
        search_terms = ["art gallery", "art studio", "creative agency"]
    
    # Generate all combinations: search_term × location
    for term in search_terms:
        if locations:
            for location in locations:
                # Create query: "{term} {location}"
                query = f"{term} {location}".strip()
                if query:  # Only add non-empty queries
                    queries.append(query)
        else:
            # No locations, just use the term
            if term:
                queries.append(term)
    
    # Also add keyword + category combinations if both exist
    if base_keywords and category_terms:
        for keyword in base_keywords:
            for category in category_terms:
                if locations:
                    for location in locations:
                        query = f"{keyword} {category} {location}".strip()
                        if query:
                            queries.append(query)
                else:
                    query = f"{keyword} {category}".strip()
                    if query:
                        queries.append(query)
    
    # Ensure uniqueness and limit to reasonable number
    unique_queries = list(dict.fromkeys(queries))
    
    # Limit to 50 queries max to avoid excessive API calls
    return unique_queries[:50]


async def discover_websites_async(job_id: str) -> Dict[str, Any]:
    """
    Async function to discover websites for a job
    This runs directly in the backend without needing a separate worker
    """
    from app.models.job import Job
    from app.models.prospect import (
        Prospect,
        DiscoveryStatus,
        ScrapeStatus,
        VerificationStatus,
        DraftStatus,
        SendStatus,
        ProspectStage,
    )
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
        if not await safe_commit(db, f"starting job {job_id}"):
            logger.error(f"❌ [DISCOVERY] Failed to commit job start status for {job_id}")
            return {"error": "Failed to update job status"}
        
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
                await safe_commit(db, f"marking job {job_id} as failed (import error)")
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
                await safe_commit(db, f"marking job {job_id} as failed (credentials error)")
                return {"error": f"DataForSEO credentials not configured: {cred_err}"}
        except Exception as e:
            logger.error(f"Unexpected error initializing DataForSEO client: {e}", exc_info=True)
            job.status = "failed"
            job.error_message = f"Failed to initialize DataForSEO client: {e}"
            await safe_commit(db, f"marking job {job_id} as failed (init error)")
            return {"error": str(e)}
        
        all_prospects = []
        discovered_domains = set()
        
        # Detailed tracking with comprehensive logging
        search_stats = {
            "total_queries": 0,
            "queries_executed": 0,
            "queries_successful": 0,
            "queries_failed": 0,
            "total_results_found": 0,
            "results_processed": 0,
            "results_skipped_duplicate": 0,
            "results_skipped_existing": 0,
            "results_skipped_no_email": 0,  # Track prospects skipped due to no email
            "results_saved": 0,
            "queries_detail": [],
            # Intent-based metrics
            "intent_distribution": {
                "service": 0,
                "brand": 0,
                "blog": 0,
                "media": 0,
                "marketplace": 0,
                "platform": 0,
                "unknown": 0
            },
            "snov_calls_made": 0,
            "snov_calls_skipped": 0,
            "partner_qualified": 0
        }
        
        logger.info(f"🚀 [DISCOVERY] Starting job {job_id}")
        logger.info(f"📋 [DISCOVERY] Inputs - keywords: '{keywords}', locations: {locations}, categories: {categories}, max_results: {max_results}")
        
        try:
            for loc in locations:
                # Check for timeout or cancellation
                elapsed_time = datetime.now(timezone.utc) - start_time
                if elapsed_time > MAX_EXECUTION_TIME:
                    logger.warning(f"⏱️  Job {job_id} exceeded maximum execution time ({MAX_EXECUTION_TIME}), stopping")
                    job.status = "failed"
                    job.error_message = f"Job exceeded maximum execution time of {MAX_EXECUTION_TIME}"
                    await safe_commit(db, f"marking job {job_id} as failed (timeout)")
                    return {"error": "Job exceeded maximum execution time"}
                
                # Re-check job status in case it was cancelled
                await db.refresh(job)
                if job.status == "cancelled":
                    logger.info(f"Job {job_id} was cancelled during execution")
                    return {"error": "Job was cancelled"}
                
                location_code = client.get_location_code(loc)
                
                # Generate search queries for THIS location
                # Pass single location list to generate location-specific queries
                search_queries = _generate_search_queries(keywords, categories, [loc])
                
                # CRITICAL: Fail job if no queries generated for this location
                if not search_queries or len(search_queries) == 0:
                    error_msg = f"No valid search queries generated from keywords='{keywords}', categories={categories}, location='{loc}'"
                    logger.error(f"❌ {error_msg}")
                    job.status = "failed"
                    job.error_message = error_msg
                    await safe_commit(db, f"marking job {job_id} as failed (no queries generated)")
                    return {"error": error_msg}
                
                search_stats["total_queries"] += len(search_queries)
                
                logger.info(f"📍 Processing location '{loc}' (code: {location_code}) with {len(search_queries)} queries")
                logger.info(f"📝 Generated queries for {loc}: {search_queries[:5]}{'...' if len(search_queries) > 5 else ''}")
                
                for query in search_queries:
                    # Check for timeout or cancellation before each query
                    elapsed_time = datetime.now(timezone.utc) - start_time
                    if elapsed_time > MAX_EXECUTION_TIME:
                        logger.warning(f"⏱️  Job {job_id} exceeded maximum execution time, stopping")
                        job.status = "failed"
                        job.error_message = f"Job exceeded maximum execution time of {MAX_EXECUTION_TIME}"
                        await safe_commit(db, f"marking job {job_id} as failed (timeout in query loop)")
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
                    # Categories come from frontend as: "Art Gallery", "Museum", "Museums", "Art Studio", etc.
                    query_category = None
                    query_lower = query.lower()
                    
                    # Try to match categories directly from the query
                    for cat in categories:
                        cat_lower = cat.lower()
                        # Check if category name appears in the query
                        if cat_lower in query_lower:
                            query_category = cat  # Use the original category name (preserves case)
                            break
                    
                    # If no direct match, try to infer from keywords
                    if not query_category:
                        category_keywords = {
                            "Art Gallery": ["art gallery", "gallery", "art exhibition"],
                            "Museum": ["museum", "museums", "art museum"],
                            "Museums": ["museum", "museums", "art museum"],
                            "Art Studio": ["art studio", "studio", "artist studio"],
                            "Art School": ["art school", "art academy", "art institute"],
                            "Art Fair": ["art fair", "art exhibition", "art show"],
                            "Art Dealer": ["art dealer", "art dealer", "art broker"],
                            "Art Consultant": ["art consultant", "art advisor", "art advisory"],
                            "Art Publisher": ["art publisher", "art publishing", "art press"],
                            "Art Magazine": ["art magazine", "art publication", "art journal"]
                        }
                        for cat in categories:
                            if cat in category_keywords:
                                if any(kw in query_lower for kw in category_keywords[cat]):
                                    query_category = cat
                                    break
                    
                    # Fallback: use first category if no match found
                    if not query_category and categories:
                        query_category = categories[0]
                    
                    # Check if job was cancelled before starting new query
                    await db.refresh(job)
                    if job.status == "cancelled":
                        logger.info(f"Job {job_id} was cancelled, stopping query execution")
                        return {"error": "Job was cancelled"}
                    
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
                    if not await safe_flush(db, f"creating discovery_query for {query} in {loc}"):
                        logger.error(f"❌ [DISCOVERY] Failed to flush discovery_query, skipping query")
                        continue
                    
                    query_stats = {
                        "query": query,
                        "location": loc,
                        "status": "pending",
                        "results_found": 0,
                        "results_saved": 0,
                        "error": None
                    }
                    
                    try:
                        # Check for cancellation before making API call
                        await db.refresh(job)
                        if job.status == "cancelled":
                            logger.info(f"Job {job_id} was cancelled before API call")
                            return {"error": "Job was cancelled"}
                        
                        logger.info(f"🔍 Searching: '{query}' in {loc} (location_code: {location_code})...")
                        # Call DataForSEO API with explicit parameters
                        # CRITICAL: Only increment queries_executed AFTER making the API call
                        serp_results = await client.serp_google_organic(
                            keyword=query,
                            location_code=location_code,
                            language_code="en",
                            depth=10,
                            device="desktop"
                        )
                        
                        # Increment queries_executed AFTER successful API call
                        search_stats["queries_executed"] += 1
                        
                        # Check for cancellation after API call
                        await db.refresh(job)
                        if job.status == "cancelled":
                            logger.info(f"Job {job_id} was cancelled after API call")
                            return {"error": "Job was cancelled"}
                        
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
                            await safe_commit(db, f"updating discovery_query {discovery_query.id} status to failed")
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
                            # Check if job was cancelled before processing each result
                            await db.refresh(job)
                            if job.status == "cancelled":
                                logger.info(f"Job {job_id} was cancelled, stopping result processing")
                                return {"error": "Job was cancelled"}
                            
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
                            
                            # Parse and normalize URL using utility function
                            from app.utils.domain import normalize_domain
                            domain = normalize_domain(url)
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
                            
                            # Step 1: Infer SERP intent BEFORE enrichment
                            from app.services.serp_intent import infer_serp_intent
                            intent_result = infer_serp_intent(
                                url=normalized_url,
                                title=title,
                                snippet=description,
                                category=query_category or ""
                            )
                            serp_intent = intent_result.get("intent", "unknown")
                            serp_confidence = float(intent_result.get("confidence", 0.0))
                            serp_signals = intent_result.get("signals", [])
                            
                            logger.info(f"🎯 [DISCOVERY] Intent for {domain}: {serp_intent} (confidence: {serp_confidence:.2f}, signals: {len(serp_signals)})")
                            
                            # Track intent distribution
                            if serp_intent in search_stats["intent_distribution"]:
                                search_stats["intent_distribution"][serp_intent] += 1
                            
                            # Step 2: Gate enrichment - only enrich service/brand intent
                            # Blogs, media, marketplaces, platforms are skipped early
                            should_enrich = serp_intent in ["service", "brand"]
                            
                            if should_enrich:
                                search_stats["partner_qualified"] += 1
                            else:
                                search_stats["snov_calls_skipped"] += 1
                                logger.info(f"⏭️  [DISCOVERY] Skipping enrichment for {domain} (intent: {serp_intent} - not a business partner candidate)")
                            
                            # MANDATORY: Enrich email before saving prospect (only if partner-qualified)
                            # Discovery MUST NOT save prospects without emails
                            # DEFENSIVE: Enrichment failures should NOT break the entire discovery pipeline
                            from app.services.enrichment import enrich_prospect_email
                            
                            enrich_result = None
                            contact_email = None
                            snov_payload = None
                            
                            # Only enrich if intent qualifies as business partner
                            if should_enrich:
                                search_stats["snov_calls_made"] += 1
                                try:
                                    logger.info(f"🔍 [DISCOVERY] Enriching {domain} before saving (intent: {serp_intent})...")
                                    # STRICT MODE: Pass page_url to enrichment
                                    enrich_result = await enrich_prospect_email(domain, None, normalized_url)
                                    
                                    if enrich_result:
                                        email_status = enrich_result.get("email_status", "no_email_found")
                                        
                                        if email_status == "found":
                                            # Email found on website
                                            contact_email = enrich_result.get("primary_email")
                                            snov_payload = enrich_result  # Store full result
                                            logger.info(f"✅ [DISCOVERY] Enriched {domain}: {contact_email} (pages crawled: {len(enrich_result.get('pages_crawled', []))})")
                                        else:
                                            # No email found on website
                                            contact_email = None
                                            snov_payload = enrich_result  # Store full result with "no_email_found" status
                                            logger.warning(f"⚠️  [DISCOVERY] No email found on website for {domain} (pages crawled: {len(enrich_result.get('pages_crawled', []))})")
                                    else:
                                        # Enrichment service returned None (should not happen)
                                        logger.error(f"❌ [DISCOVERY] Enrichment service returned None for {domain}")
                                        contact_email = None
                                        snov_payload = {
                                            "email_status": "no_email_found",
                                            "error": "Enrichment service returned None",
                                            "source": "error",
                                        }
                                        
                                except Exception as e:
                                    # DEFENSIVE: Log error but DO NOT skip - save prospect without email
                                    logger.error(f"❌ [DISCOVERY] Enrichment failed for {domain}: {e}", exc_info=True)
                                    contact_email = None
                                    snov_payload = {
                                        "email_status": "no_email_found",
                                        "error": str(e),
                                        "source": "error",
                                    }
                            else:
                                # Intent doesn't qualify - skip enrichment, save without email
                                logger.info(f"⏭️  [DISCOVERY] Skipping enrichment for {domain} (intent: {serp_intent})")
                                contact_email = None
                                snov_payload = {
                                    "status": "skipped_intent",
                                    "intent": serp_intent,
                                    "reason": f"Intent '{serp_intent}' does not qualify as business partner"
                                }
                            
                            # Save prospect (with or without email)
                            # Non-partner intents are saved but marked as skipped
                            if contact_email:
                                logger.info(f"💾 [DISCOVERY] Saving prospect {domain} with email {contact_email} (intent: {serp_intent})")
                            else:
                                if should_enrich:
                                    logger.info(f"💾 [DISCOVERY] Saving prospect {domain} without email (retry pending, intent: {serp_intent})")
                                else:
                                    logger.info(f"💾 [DISCOVERY] Saving prospect {domain} without email (intent: {serp_intent} - skipped)")
                            
                            # Check if this is pipeline mode (strict step-by-step)
                            job_params = job.params if job else {}
                            pipeline_mode = job_params.get("pipeline_mode", False)
                            
                            prospect = Prospect(
                                domain=domain,
                                page_url=normalized_url,
                                page_title=title,
                                contact_email=contact_email,  # May be None if skipped or retry needed
                                contact_method="snov_io" if contact_email else ("pending_retry" if should_enrich else "skipped_intent"),
                                outreach_status="pending",
                                discovery_query_id=discovery_query.id,
                                snov_payload=snov_payload,
                                serp_intent=serp_intent,
                                serp_confidence=serp_confidence,
                                serp_signals=serp_signals,
                                dataforseo_payload={
                                    "description": description,
                                    "location": loc,
                                    "url": normalized_url,
                                    "title": title
                                },
                                # PIPELINE MODE: Set discovery status, store metadata, NO enrichment
                                # Canonical status: DISCOVERED (pipeline mode) or NEW (legacy mode)
                                discovery_status=DiscoveryStatus.DISCOVERED.value
                                if pipeline_mode
                                else DiscoveryStatus.NEW.value,
                                discovery_category=query_category if pipeline_mode else None,
                                discovery_location=loc if pipeline_mode else None,
                                discovery_keywords=keywords if pipeline_mode else None,
                                approval_status="pending" if pipeline_mode else None,
                                # Always DISCOVERED on discovery
                                scrape_status=ScrapeStatus.DISCOVERED.value,
                                verification_status=VerificationStatus.PENDING.value
                                if pipeline_mode
                                else None,
                                draft_status=DraftStatus.PENDING.value
                                if pipeline_mode
                                else None,
                                send_status=SendStatus.PENDING.value
                                if pipeline_mode
                                else None,
                                # Canonical pipeline stage - set to DISCOVERED on creation
                                # Defensive: Only set if stage column exists (handled by model default)
                                stage=ProspectStage.DISCOVERED.value,
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
                        await safe_commit(db, f"updating discovery_query {discovery_query.id} status to failed (exception)")
                        continue
                
                if len(all_prospects) >= max_results:
                    break
            
            # Commit all prospects
            if not await safe_commit(db, f"committing {len(all_prospects)} prospects for job {job_id}"):
                logger.error(f"❌ [DISCOVERY] Failed to commit prospects for job {job_id}")
                job.status = "failed"
                job.error_message = "Failed to commit prospects to database"
                await safe_commit(db, f"marking job {job_id} as failed (commit error)")
                return {"error": "Failed to commit prospects to database"}
            logger.info(f"💾 Committed {len(all_prospects)} new prospects to database")
            
            # CRITICAL: Fail job if zero queries were executed
            if search_stats["queries_executed"] == 0:
                error_msg = f"No queries were executed. Generated {search_stats['total_queries']} queries but none were sent to DataForSEO."
                logger.error(f"❌ {error_msg}")
                job.status = "failed"
                job.error_message = error_msg
                job.result = {
                    "error": error_msg,
                    "search_statistics": search_stats
                }
                await safe_commit(db, f"marking job {job_id} as failed (zero queries executed)")
                return {"error": error_msg}
            
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
                    "results_skipped_existing": search_stats["results_skipped_existing"],
                    "results_skipped_no_email": search_stats.get("results_skipped_no_email", 0),
                    "intent_distribution": search_stats["intent_distribution"],
                    "partner_qualified": search_stats["partner_qualified"],
                    "snov_calls_made": search_stats["snov_calls_made"],
                    "snov_calls_skipped": search_stats["snov_calls_skipped"]
                },
                "queries_detail": search_stats["queries_detail"][:20]  # Limit to first 20 for size
            }
            if not await safe_commit(db, f"completing job {job_id}"):
                logger.error(f"❌ [DISCOVERY] Failed to commit job completion for {job_id}")
                return {"error": "Failed to update job status"}
            
            # Calculate total execution time
            total_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            
            logger.info(f"✅ [DISCOVERY] Job {job_id} completed in {total_time:.1f}s")
            logger.info(f"📊 [DISCOVERY] Output - Queries: {search_stats['queries_executed']} executed, {search_stats['queries_successful']} successful, {search_stats['queries_failed']} failed")
            logger.info(f"🔍 [DISCOVERY] Output - Results: {search_stats['total_results_found']} found, {search_stats['results_saved']} saved")
            logger.info(f"⏭️  [DISCOVERY] Output - Skipped: {search_stats['results_skipped_duplicate']} duplicates, {search_stats['results_skipped_existing']} existing, {search_stats.get('results_skipped_no_email', 0)} no email")
            logger.info(f"🎯 [DISCOVERY] Intent Distribution: {search_stats['intent_distribution']}")
            logger.info(f"📧 [DISCOVERY] Snov Calls: {search_stats['snov_calls_made']} made, {search_stats['snov_calls_skipped']} skipped (intent filtering)")
            logger.info(f"✅ [DISCOVERY] Partner Qualified: {search_stats['partner_qualified']} domains")
            
            # NOTE: No need to auto-trigger enrichment since we enrich during discovery
            # All saved prospects already have emails
            
            return {
                "job_id": job_id,
                "status": "completed",
                "prospects_discovered": len(all_prospects),
                "search_statistics": {
                    "total_queries": search_stats["total_queries"],
                    "queries_executed": search_stats["queries_executed"],
                    "queries_successful": search_stats["queries_successful"],
                    "queries_failed": search_stats["queries_failed"],
                    "total_results_found": search_stats["total_results_found"],
                    "results_processed": search_stats["results_processed"],
                    "results_saved": search_stats["results_saved"],
                    "results_skipped_duplicate": search_stats["results_skipped_duplicate"],
                    "results_skipped_existing": search_stats["results_skipped_existing"],
                    "results_skipped_no_email": search_stats.get("results_skipped_no_email", 0)
                }
            }
        
        except Exception as e:
            logger.error(f"Discovery job {job_id} failed: {e}", exc_info=True)
            try:
                job.status = "failed"
                job.error_message = str(e)
                await safe_commit(db, f"marking job {job_id} as failed (exception handler)")
            except Exception as commit_err:
                logger.error(f"❌ [DISCOVERY] Failed to commit error status for job {job_id}: {commit_err}", exc_info=True)
            return {"error": str(e)}


async def process_discovery_job(job_id: str):
    """
    Wrapper to process discovery job in background
    This can be called from FastAPI BackgroundTasks or asyncio
    """
    try:
        await discover_websites_async(job_id)
    except asyncio.CancelledError:
        logger.info(f"Discovery job {job_id} was cancelled")
        raise  # Re-raise to properly handle cancellation
    except Exception as e:
        logger.error(f"Error processing discovery job {job_id}: {e}", exc_info=True)

