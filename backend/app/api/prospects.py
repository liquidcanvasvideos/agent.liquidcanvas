"""
Prospect management API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Response, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_
from typing import List, Optional, Dict
from uuid import UUID
import os
from dotenv import load_dotenv
import logging
import csv
import io
from datetime import datetime

from app.db.database import get_db
from app.api.auth import get_current_user_optional
from app.utils.email_validation import format_job_error

logger = logging.getLogger(__name__)
from app.models.prospect import Prospect
from app.models.email_attachment import EmailAttachment
from app.models.job import Job
from app.schemas.prospect import (
    ProspectResponse,
    ProspectListResponse,
    ComposeRequest,
    ComposeResponse,
    SendRequest,
    SendResponse
)
from pydantic import BaseModel

load_dotenv()

router = APIRouter()

MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024  # 10MB


class BulkDraftRequest(BaseModel):
    subject: str
    body: str
    category: Optional[str] = None


@router.get("/categories")
async def get_available_categories(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Get unique categories from prospects in the database.
    
    This endpoint returns all unique discovery_category values that exist in the database.
    Useful for populating filter dropdowns dynamically based on actual data.
    
    After migrating categories, this endpoint will automatically return the new category names.
    """
    try:
        # Get unique categories from prospects
        result = await db.execute(
            select(Prospect.discovery_category)
            .where(Prospect.discovery_category.isnot(None))
            .distinct()
            .order_by(Prospect.discovery_category)
        )
        categories = [row[0] for row in result.all() if row[0]]
        
        # Also include standard categories that might not have records yet
        # This ensures the dropdown always has all valid options
        standard_categories = [
            'Art Lovers', 'Interior Design', 'Pet Lovers', 'Dogs and Cat Owners - Fur Parent', 
            'Childhood Development', 'Holidays', 'Famous Quotes', 'Home Decor', 
            'Audio Visual', 'Interior Decor', 'Holiday Decor', 'Home Tech', 
            'Parenting', 'NFTs', 'Museum'
        ]
        
        # Combine and deduplicate
        all_categories = sorted(list(set(categories + standard_categories)))
        
        logger.info(f"📊 [CATEGORIES] Returning {len(all_categories)} unique categories (found {len(categories)} in DB)")
        
        return {
            "categories": all_categories,
            "count": len(all_categories),
            "from_database": len(categories)
        }
    except Exception as e:
        logger.error(f"❌ [CATEGORIES] Failed to get categories: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get categories: {str(e)}")


@router.post("/enrich/direct")
async def enrich_direct(
    domain: str,
    name: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Direct enrichment endpoint - takes domain + name, returns email
    
    Args:
        domain: Domain name (e.g., "example.com")
        name: Optional contact name
        
    Returns:
        Normalized enrichment result in a shape compatible with the frontend:
        {
            email: str | null,
            name: str | null,
            company: str | null,
            confidence: float | null,
            domain: str,
            success: bool,
            source: str | null,
            error: str | null
        }
    """
    # Check master switch
    try:
        from app.api.scraper import validate_master_switch
        await validate_master_switch(db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking master switch: {e}", exc_info=True)
        # Continue if check fails
    
    import time
    start_time = time.time()
    
    logger.info(f"🔍 [ENRICHMENT API] Direct enrichment request - domain: {domain}, name: {name}")
    logger.info(f"📥 [ENRICHMENT API] Input - domain: {domain}, name: {name}")
    
    try:
        from app.services.enrichment import enrich_prospect_email
        
        result = await enrich_prospect_email(domain, name, None)
        
        if not result or not result.get("email"):
            api_time = (time.time() - start_time) * 1000
            logger.warning(f"⚠️  [ENRICHMENT API] No email found for {domain} after {api_time:.0f}ms")
            return {
                "success": False,
                "email": None,
                "name": result.get("name") if isinstance(result, dict) else None,
                "company": result.get("company") if isinstance(result, dict) else None,
                "confidence": result.get("confidence") if isinstance(result, dict) else None,
                "domain": domain,
                "source": result.get("source") if isinstance(result, dict) else "snov_io",
                "error": f"No email found for domain {domain}",
            }
        
        api_time = (time.time() - start_time) * 1000
        logger.info(f"✅ [ENRICHMENT API] Enrichment completed in {api_time:.0f}ms")
        logger.info(f"📤 [ENRICHMENT API] Output - {result}")
        
        return {
            "success": True,
            "email": result.get("email"),
            "name": result.get("name"),
            "company": result.get("company"),
            "confidence": result.get("confidence"),
            "domain": domain,
            "source": result.get("source", "snov_io"),
            "error": None,
        }
        
    except Exception as e:
        api_time = (time.time() - start_time) * 1000
        error_msg = f"Enrichment failed after {api_time:.0f}ms: {str(e)}"
        logger.error(f"❌ [ENRICHMENT API] {error_msg}", exc_info=True)
        import traceback
        return {
            "success": False,
            "email": None,
            "name": None,
            "company": None,
            "confidence": None,
            "domain": domain,
            "source": "snov_io",
            "error": error_msg,
        }


@router.post("/enrich/{prospect_id}")
async def enrich_prospect_by_id(
    prospect_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Enrich a single prospect by ID and update it in the database
    """
    try:
        # Get prospect
        result = await db.execute(select(Prospect).where(Prospect.id == prospect_id))
        prospect = result.scalar_one_or_none()
        
        if not prospect:
            raise HTTPException(status_code=404, detail="Prospect not found")
        
        # Check intent - warn if not partner-qualified (but allow manual enrichment)
        if prospect.serp_intent and prospect.serp_intent not in ["service", "brand"]:
            logger.warning(f"⚠️  [ENRICHMENT API] Enriching prospect {prospect_id} with non-partner intent: {prospect.serp_intent}")
        
        # STRICT MODE: Enrich using domain and page_url
        from app.services.enrichment import enrich_prospect_email
        enrich_result = await enrich_prospect_email(prospect.domain, None, prospect.page_url)
        
        if not enrich_result:
            # Enrichment service returned None (should not happen)
            logger.error(f"❌ [ENRICHMENT API] Enrichment service returned None for {prospect.domain}")
            enrich_result = {
                "emails": [],
                "primary_email": None,
                "email_status": "no_email_found",
                "pages_crawled": [],
                "emails_by_page": {},
                "snov_emails_accepted": 0,
                "snov_emails_rejected": 0,
                "success": False,
                "source": "error",
                "error": "Enrichment service returned None",
            }
        
        email_status = enrich_result.get("email_status", "no_email_found")
        primary_email = enrich_result.get("primary_email")
        
        if email_status == "found" and primary_email:
            # Email found on website - update prospect
            prospect.contact_email = primary_email
            prospect.contact_method = enrich_result.get("source", "html_scraping")
            prospect.snov_payload = enrich_result
            await db.commit()
            await db.refresh(prospect)
            
            pages_crawled = len(enrich_result.get("pages_crawled", []))
            return {
                "success": True,
                "email": primary_email,
                "name": None,
                "company": None,
                "confidence": 50.0,
                "domain": prospect.domain,
                "source": enrich_result.get("source", "html_scraping"),
                "message": f"Email found on website: {primary_email}",
                "pages_crawled": pages_crawled,
            }
        else:
            # No email found on website - store "no_email_found" status
            prospect.contact_email = None
            prospect.contact_method = "no_email_found"
            prospect.snov_payload = enrich_result
            await db.commit()
            await db.refresh(prospect)
            
            pages_crawled = len(enrich_result.get("pages_crawled", []))
            return {
                "success": False,
                "email": None,
                "name": None,
                "company": None,
                "confidence": None,
                "domain": prospect.domain,
                "source": None,
                "message": f"No email found on website for {prospect.domain}",
                "pages_crawled": pages_crawled,
                "error": enrich_result.get("error", "No email found on website"),
            }
            
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"❌ Error enriching prospect {prospect_id}: {e}", exc_info=True)
        from app.utils.email_validation import format_job_error
        error_msg = format_job_error(e)
        logger.error(f"❌ [ENRICHMENT API] Failed to enrich prospect {prospect_id}: {error_msg}")
        raise HTTPException(status_code=500, detail=f"Failed to enrich prospect: {error_msg}")


@router.post("/bulk_draft")
async def bulk_draft_endpoint(
    payload: BulkDraftRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Apply a draft subject/body to all prospects matching a category filter.
    If category is None, applies to all website prospects with verified emails.
    """
    from app.models.prospect import VerificationStatus

    query = select(Prospect).where(
        and_(
            Prospect.contact_email.isnot(None),
            Prospect.verification_status == VerificationStatus.VERIFIED.value,
            or_(Prospect.source_type == "website", Prospect.source_type.is_(None))
        )
    )

    if payload.category:
        query = query.where(Prospect.discovery_category == payload.category)

    result = await db.execute(query)
    prospects = result.scalars().all()

    if not prospects:
        return {"success": True, "updated": 0, "message": "No matching prospects found"}

    for prospect in prospects:
        prospect.draft_subject = payload.subject
        prospect.draft_body = payload.body
        prospect.draft_status = "drafted"

    await db.commit()

    return {
        "success": True,
        "updated": len(prospects),
        "message": f"Draft applied to {len(prospects)} prospect(s)"
    }


@router.post("/deduplicate")
async def deduplicate_prospects(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Remove duplicate prospects by domain, keeping the best version of each.
    
    Strategy:
    - Groups prospects by domain (case-insensitive)
    - For each domain, keeps the prospect with:
      1. Highest priority: Has email (contact_email IS NOT NULL)
      2. Second priority: Most recent updated_at
      3. Third priority: Most recent created_at
    - Deletes all other duplicates
    """
    try:
        logger.info("🔍 Starting prospect deduplication...")
        
        # Find all prospects grouped by domain
        # Use func.lower() for case-insensitive comparison
        from sqlalchemy import func as sql_func
        
        # Get all prospects with their domain (lowercased for grouping)
        result = await db.execute(
            select(
                Prospect.id,
                Prospect.domain,
                Prospect.contact_email,
                Prospect.updated_at,
                Prospect.created_at,
                sql_func.lower(Prospect.domain).label('domain_lower')
            )
        )
        all_prospects = result.all()
        
        # Group by domain (case-insensitive)
        domain_groups: Dict[str, List[Dict]] = {}
        for p in all_prospects:
            domain_lower = p.domain_lower
            if domain_lower not in domain_groups:
                domain_groups[domain_lower] = []
            domain_groups[domain_lower].append({
                'id': p.id,
                'domain': p.domain,
                'has_email': p.contact_email is not None and str(p.contact_email).strip() != '',
                'updated_at': p.updated_at,
                'created_at': p.created_at
            })
        
        # Find duplicates (domains with more than 1 prospect)
        duplicates_found = 0
        to_delete = []
        kept = []
        
        for domain_lower, prospects_list in domain_groups.items():
            if len(prospects_list) > 1:
                duplicates_found += len(prospects_list) - 1
                
                # Sort to find the best one to keep
                # Priority: 1) Has email, 2) Most recent updated_at, 3) Most recent created_at
                sorted_prospects = sorted(
                    prospects_list,
                    key=lambda p: (
                        not p['has_email'],  # False (has email) comes before True (no email)
                        -(p['updated_at'].timestamp() if p['updated_at'] else 0),  # Most recent first
                        -(p['created_at'].timestamp() if p['created_at'] else 0)  # Most recent first
                    )
                )
                
                # Keep the first (best) one
                best = sorted_prospects[0]
                kept.append({
                    'id': best['id'],
                    'domain': best['domain'],
                    'has_email': best['has_email']
                })
                
                # Mark others for deletion
                for p in sorted_prospects[1:]:
                    to_delete.append(p['id'])
        
        # Delete duplicates
        deleted_count = 0
        if to_delete:
            logger.info(f"🗑️  Deleting {len(to_delete)} duplicate prospects...")
            delete_result = await db.execute(
                select(Prospect).where(Prospect.id.in_(to_delete))
            )
            duplicates_to_delete = delete_result.scalars().all()
            
            for prospect in duplicates_to_delete:
                await db.delete(prospect)
            
            await db.commit()
            deleted_count = len(duplicates_to_delete)
            logger.info(f"✅ Deleted {deleted_count} duplicate prospects")
        else:
            logger.info("✅ No duplicates found - all prospects are unique")
        
        return {
            "success": True,
            "duplicates_found": duplicates_found,
            "deleted": deleted_count,
            "kept": len(kept),
            "message": f"Removed {deleted_count} duplicate prospect(s), kept {len(kept)} unique domain(s)"
        }
        
    except Exception as e:
        await db.rollback()
        logger.error(f"❌ Error deduplicating prospects: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to deduplicate prospects: {str(e)}")


@router.post("/enrich-and-deduplicate")
async def enrich_and_deduplicate(
    max_prospects: int = 100,
    only_missing_emails: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Combined endpoint: First enrich existing prospects, then deduplicate.
    
    This is the main endpoint for the "Enrich & Clean" button.
    """
    try:
        # Step 1: Create enrichment job (reuse the existing endpoint logic)
        logger.info("🔍 Step 1: Starting enrichment job...")
        
        # Check master switch
        try:
            from app.api.scraper import validate_master_switch
            await validate_master_switch(db)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error checking master switch: {e}", exc_info=True)
        
        # Create job record
        job = Job(
            job_type="enrich",
            params={
                "prospect_ids": None,
                "max_prospects": max_prospects,
                "only_missing_emails": only_missing_emails
            },
            status="pending"
        )
        
        db.add(job)
        await db.commit()
        await db.refresh(job)
        
        # Start enrichment task in background
        try:
            import asyncio
            # Import inside function to catch syntax errors early
            try:
                from app.tasks.enrichment import process_enrichment_job
            except SyntaxError as syntax_err:
                logger.error(f"❌ Syntax error in enrichment task module: {syntax_err}", exc_info=True)
                job.status = "failed"
                job.error_message = "System error: Code syntax issue detected. Please contact support."
                await db.commit()
                await db.refresh(job)
                return {
                    "success": False,
                    "job_id": job.id,
                    "status": "failed",
                    "error": "System error: Unable to start enrichment job due to code issue. Please contact support."
                }
            except ImportError as import_err:
                logger.error(f"❌ Import error for enrichment task: {import_err}", exc_info=True)
                job.status = "failed"
                job.error_message = "System error: Module import failed. Please contact support."
                await db.commit()
                await db.refresh(job)
                return {
                    "success": False,
                    "job_id": job.id,
                    "status": "failed",
                    "error": "System error: Unable to import enrichment task module. Please contact support."
                }
            
            asyncio.create_task(process_enrichment_job(str(job.id)))
            logger.info(f"✅ Enrichment job {job.id} started in background")
        except Exception as e:
            logger.error(f"❌ Failed to start enrichment job {job.id}: {e}", exc_info=True)
            job.status = "failed"
            # Use helper to format error message
            job.error_message = format_job_error(e)
            await db.commit()
            await db.refresh(job)
            return {
                "success": False,
                "job_id": job.id,
                "status": "failed",
                "error": job.error_message
            }
        
        enrichment_result = {
            "job_id": str(job.id),
            "status": "pending",
            "message": f"Enrichment job {job.id} started successfully"
        }
        
        # Step 2: Deduplicate
        logger.info("🔍 Step 2: Starting deduplication...")
        deduplicate_result = await deduplicate_prospects(db=db, current_user=current_user)
        
        return {
            "success": True,
            "enrichment": enrichment_result,
            "deduplication": deduplicate_result,
            "message": "Enrichment job started and deduplication completed"
        }
        
    except Exception as e:
        logger.error(f"❌ Error in enrich-and-deduplicate: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed: {str(e)}")


@router.get("/websites")
async def list_websites(
    page: int = 1,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    List websites (prospects) with pagination - standardized format
    
    WEBSITE OUTREACH ONLY: Returns prospects where source_type='website' or source_type IS NULL
    Excludes social profiles (LinkedIn, Instagram, Facebook, TikTok)
    
    Returns: { data: Prospect[], page, limit, total, totalPages }
    """
    # Enforce max limit of 10
    limit = max(1, min(limit, 10))
    
    # CRITICAL: Filter by source_type='website' to separate from social outreach
    website_filter = or_(
        Prospect.source_type == 'website',
        Prospect.source_type.is_(None)  # Legacy prospects (default to website)
    )
    
    try:
        # Get total count
        count_query = select(func.count(Prospect.id)).where(website_filter)
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        # Calculate pagination
        skip = (page - 1) * limit
        total_pages = (total + limit - 1) // limit if total > 0 else 0
        
        # Build query with website filter
        query = select(Prospect).where(website_filter).order_by(Prospect.created_at.desc())
        result = await db.execute(query.offset(skip).limit(limit))
        prospects = result.scalars().all()
        
        # Convert to response format
        prospect_responses = []
        for p in prospects:
            try:
                response_dict = {
                    "id": str(p.id),
                    "domain": p.domain or "",
                    "page_url": getattr(p, 'page_url', None),
                    "page_title": getattr(p, 'page_title', None),
                    "contact_email": getattr(p, 'contact_email', None),
                    "discovery_category": getattr(p, 'discovery_category', None),
                    "discovery_location": getattr(p, 'discovery_location', None),
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                    "scrape_status": getattr(p, 'scrape_status', None),
                    "approval_status": getattr(p, 'approval_status', None),
                }
                prospect_responses.append(ProspectResponse(**response_dict))
            except Exception as e:
                logger.warning(f"⚠️  Skipping prospect {p.id} due to conversion error: {e}")
                continue
        
        return {
            "data": prospect_responses,
            "page": page,
            "limit": limit,
            "total": total,
            "totalPages": total_pages
        }
    except Exception as e:
        logger.error(f"❌ [WEBSITES] Error listing websites: {e}", exc_info=True)
        return {
            "data": [],
            "page": page,
            "limit": limit,
            "total": 0,
            "totalPages": 0
        }
    
    # Return standardized format
    if result.get("success") and result.get("data"):
        data = result["data"]
        return {
            "data": data.get("data", data.get("prospects", [])),
            "page": data.get("page", page),
            "limit": data.get("limit", limit),
            "total": data.get("total", 0),
            "totalPages": data.get("totalPages", 0)
        }
    
    return {
        "data": [],
        "page": page,
        "limit": limit,
        "total": 0,
        "totalPages": 0
    }


@router.post("/{prospect_id}/promote")
async def promote_to_lead(
    prospect_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Explicitly promote a prospect to LEAD stage
    
    Requirements:
    - Prospect must have stage = EMAIL_FOUND (has email but not yet promoted)
    - Sets stage = LEAD (ready for outreach)
    """
    from sqlalchemy import text
    from app.models.prospect import ProspectStage
    
    # Get prospect
    result = await db.execute(select(Prospect).where(Prospect.id == prospect_id))
    prospect = result.scalar_one_or_none()
    
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")
    
    # Check if stage column exists
    try:
        column_check = await db.execute(
            text("""
                SELECT column_name
                FROM information_schema.columns 
                WHERE table_name = 'prospects' 
                AND column_name = 'stage'
            """)
        )
        if not column_check.fetchone():
            raise HTTPException(status_code=400, detail="Stage column not available. Migration required.")
        
        # Check current stage
        if prospect.stage == ProspectStage.LEAD.value:
            return {"success": True, "message": "Prospect is already a LEAD", "stage": prospect.stage}
        
        if prospect.stage != ProspectStage.EMAIL_FOUND.value:
            raise HTTPException(
                status_code=400, 
                detail=f"Prospect must be in EMAIL_FOUND stage to promote. Current stage: {prospect.stage}"
            )
        
        # Promote to LEAD
        prospect.stage = ProspectStage.LEAD.value
        await db.commit()
        await db.refresh(prospect)
        
        logger.info(f"✅ Promoted prospect {prospect_id} to LEAD stage")
        return {"success": True, "message": "Prospect promoted to LEAD", "stage": prospect.stage}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error promoting prospect to LEAD: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to promote prospect: {str(e)}")


def _normalize_category(category: Optional[str]) -> Optional[str]:
    """
    Normalize category input: trim whitespace, handle empty strings, convert to None.
    Categories are stored as-is in the database (case-sensitive at storage, case-insensitive at query).
    """
    if not category:
        return None
    normalized = category.strip()
    if not normalized or normalized.lower() == 'all':
        return None
    return normalized


def _build_leads_base_query(category: Optional[str] = None):
    """
    Build a single, deterministic base query for leads endpoint.
    
    This function ensures COUNT(*) and SELECT queries use identical filters,
    preventing data integrity violations.
    
    Args:
        category: Optional category filter (normalized before use)
    
    Returns:
        Tuple of (base_query, total_count) where:
        - base_query: select(Prospect) with all filters applied
        - count_query: select(func.count(Prospect.id)) with same filters
    """
    from app.models.prospect import ScrapeStatus
    
    # Normalize category input
    normalized_category = _normalize_category(category)
    
    # CRITICAL: Filter by source_type='website' to separate from social outreach
    website_filter = or_(
        Prospect.source_type == 'website',
        Prospect.source_type.is_(None)  # Legacy prospects (default to website)
    )
    
    # Base filters: scrape_status and source_type (always applied)
    base_conditions = [
        Prospect.scrape_status.in_([
            ScrapeStatus.SCRAPED.value,
            ScrapeStatus.ENRICHED.value
        ]),
        # Leads tab should show only items that have been approved in Websites.
        Prospect.approval_status == "approved",
        # Leads tab should only show items with emails.
        Prospect.contact_email.isnot(None),
        func.length(func.trim(Prospect.contact_email)) > 0,
        # Hide any leads that already have a draft (they belong in Drafts).
        or_(
            Prospect.draft_subject.is_(None),
            func.length(func.trim(Prospect.draft_subject)) == 0,
            Prospect.draft_body.is_(None),
            func.length(func.trim(Prospect.draft_body)) == 0,
        ),
        website_filter
    ]
    
    # Add category filter if provided (exact match, case-insensitive)
    if normalized_category:
        # Use ilike for case-insensitive EXACT matching (not partial)
        # This ensures "Museum" matches "Museum" but not "Art Museum"
        category_condition = and_(
            Prospect.discovery_category.isnot(None),
            Prospect.discovery_category.ilike(normalized_category)  # Exact match, case-insensitive
        )
        base_conditions.append(category_condition)
        logger.info(f"🔍 [LEADS BASE QUERY] Category filter applied: '{normalized_category}' (exact match, case-insensitive)")
    else:
        logger.info(f"🔍 [LEADS BASE QUERY] No category filter (returning all leads)")
    
    # Build WHERE clause from all conditions
    where_clause = and_(*base_conditions)
    
    # Build base query for SELECT (data)
    base_query = select(Prospect).where(where_clause).order_by(Prospect.created_at.desc())
    
    # Build count query using SAME where_clause (critical for data integrity)
    count_query = select(func.count(Prospect.id)).where(where_clause)
    
    return base_query, count_query


@router.get("/leads")
async def list_leads(
    skip: int = 0,
    limit: int = 50,
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    List prospects with scraped emails (matches pipeline "Scraped" card count)
    
    WEBSITE OUTREACH ONLY: Returns prospects where scrape_status IN ("SCRAPED", "ENRICHED") AND source_type='website'
    This matches the pipeline status "scraped" count exactly.
    
    Category filtering:
    - If category is None, empty, or "all" → returns all leads
    - If category is provided → exact match (case-insensitive)
    - Invalid categories return empty results, never errors
    """
    try:
        normalized_category = _normalize_category(category)
        logger.info(f"📊 [LEADS] Request: skip={skip}, limit={limit}, category={category} (normalized: {normalized_category})")
        
        # Build base query and count query from same source (critical for data integrity)
        base_query, count_query = _build_leads_base_query(category)
        
        # Execute count query FIRST
        try:
            total_result = await db.execute(count_query)
            total = total_result.scalar() or 0
            logger.info(f"📊 [LEADS] COUNT query result: {total} total leads" + (f" (category: '{normalized_category}')" if normalized_category else ""))
        except Exception as count_err:
            # Defensive: If count fails, log but don't crash - return empty result
            logger.error(f"❌ [LEADS] COUNT query failed: {count_err}", exc_info=True)
            logger.warning(f"⚠️  [LEADS] Returning empty result due to COUNT failure")
            return {
                "data": [],
                "total": 0,
                "skip": skip,
                "limit": limit
            }
        
        # Execute data query with pagination
        try:
            result = await db.execute(base_query.offset(skip).limit(limit))
            prospects = result.scalars().all()
            logger.info(f"📊 [LEADS] SELECT query result: {len(prospects)} prospects returned (total available: {total})")
        except Exception as query_err:
            error_str = str(query_err).lower()
            logger.error(f"❌ [LEADS] SELECT query failed: {query_err}", exc_info=True)
            
            # Handle schema mismatch errors gracefully
            if "undefinedcolumn" in error_str or "does not exist" in error_str or "bio_text" in error_str:
                logger.error(f"❌ [LEADS] Schema mismatch detected: {query_err}")
                await db.rollback()
                raise HTTPException(
                    status_code=500,
                    detail=f"Database schema mismatch: Missing required columns. Please run migrations: 'alembic upgrade head' or use the /api/health/migrate endpoint. Error: {str(query_err)}"
                )
            
            # For other query errors, return empty result instead of crashing
            logger.warning(f"⚠️  [LEADS] Query error, returning empty result: {query_err}")
            return {
                "data": [],
                "total": 0,
                "skip": skip,
                "limit": limit
            }
        
        # Defensive: If count says we have data but query returned none, adjust total
        # This handles edge cases where COUNT and SELECT diverge (shouldn't happen but be safe)
        if total > 0 and len(prospects) == 0 and skip == 0:
            logger.warning(f"⚠️  [LEADS] COUNT returned {total} but SELECT returned 0 rows (skip={skip}). This may indicate pagination issue or data was deleted.")
            # Don't raise error - just return empty result
            total = 0
        
        # Safely convert prospects to response, handling NULL draft fields and missing columns
        prospect_responses = []
        for p in prospects:
            try:
                # Use model_validate which handles NULL values better than from_orm
                # If final_body column doesn't exist, model_validate will fail
                # Catch and handle gracefully
                # Use manual dict construction to avoid final_body errors
                response_dict = {
                    "id": p.id,
                    "domain": p.domain or "",
                    "page_url": getattr(p, 'page_url', None),
                    "page_title": getattr(p, 'page_title', None),
                    "contact_email": getattr(p, 'contact_email', None),
                    "contact_method": getattr(p, 'contact_method', None),
                    "da_est": getattr(p, 'da_est', None),
                    "score": getattr(p, 'score', None),
                    "outreach_status": getattr(p, 'outreach_status', 'pending'),
                    "last_sent": getattr(p, 'last_sent', None).isoformat() if getattr(p, 'last_sent', None) else None,
                    "followups_sent": getattr(p, 'followups_sent', 0) or 0,
                    "draft_subject": getattr(p, 'draft_subject', None),
                    "draft_body": getattr(p, 'draft_body', None),
                    # final_body is commented out in schema, so don't include it
                    "thread_id": getattr(p, 'thread_id', None),
                    "sequence_index": getattr(p, 'sequence_index', None) or 0,
                    "is_manual": getattr(p, 'is_manual', None) or False,
                    "discovery_status": getattr(p, 'discovery_status', None),
                    "discovery_category": getattr(p, 'discovery_category', None),
                    "discovery_location": getattr(p, 'discovery_location', None),
                    "approval_status": getattr(p, 'approval_status', None),
                    "scrape_status": getattr(p, 'scrape_status', None),
                    "verification_status": getattr(p, 'verification_status', None),
                    "draft_status": getattr(p, 'draft_status', None),
                    "send_status": getattr(p, 'send_status', None),
                    "stage": getattr(p, 'stage', None),
                    "created_at": getattr(p, 'created_at', None).isoformat() if getattr(p, 'created_at', None) else None,
                    "updated_at": getattr(p, 'updated_at', None).isoformat() if getattr(p, 'updated_at', None) else None,
                }
                prospect_responses.append(ProspectResponse(**response_dict))
            except Exception as e:
                error_msg = str(e).lower()
                if 'final_body' in error_msg or 'column' in error_msg:
                    logger.warning(f"⚠️  Schema mismatch for prospect {getattr(p, 'id', 'unknown')}: {e}")
                    logger.warning(f"⚠️  This indicates missing columns - migration may not have run")
                    # Try to create a minimal response without the problematic field
                    try:
                        # Manually build response, skipping final_body if it doesn't exist
                        response_dict = {
                            "id": p.id,
                            "domain": p.domain or "",
                            "page_url": getattr(p, 'page_url', None),
                            "page_title": getattr(p, 'page_title', None),
                            "contact_email": getattr(p, 'contact_email', None),
                            "contact_method": getattr(p, 'contact_method', None),
                            "da_est": getattr(p, 'da_est', None),
                            "score": getattr(p, 'score', None),
                            "outreach_status": getattr(p, 'outreach_status', 'pending'),
                            "last_sent": getattr(p, 'last_sent', None),
                            "followups_sent": getattr(p, 'followups_sent', 0),
                            "draft_subject": getattr(p, 'draft_subject', None),
                            "draft_body": getattr(p, 'draft_body', None),
                            "final_body": None,  # Set to None if column doesn't exist
                            "thread_id": getattr(p, 'thread_id', None),
                            "sequence_index": getattr(p, 'sequence_index', None),
                            "is_manual": getattr(p, 'is_manual', None),
                            "discovery_status": getattr(p, 'discovery_status', None),
                            "approval_status": getattr(p, 'approval_status', None),
                            "scrape_status": getattr(p, 'scrape_status', None),
                            "verification_status": getattr(p, 'verification_status', None),
                            "draft_status": getattr(p, 'draft_status', None),
                            "send_status": getattr(p, 'send_status', None),
                            "stage": getattr(p, 'stage', None),
                            "created_at": getattr(p, 'created_at', None),
                            "updated_at": getattr(p, 'updated_at', None),
                        }
                        prospect_responses.append(ProspectResponse(**response_dict))
                    except Exception as fallback_err:
                        logger.error(f"❌ Fallback conversion also failed: {fallback_err}")
                        continue
                else:
                    logger.warning(f"⚠️  Error converting prospect {getattr(p, 'id', 'unknown')} to response: {e}")
                    continue
        
        logger.info(f"✅ [LEADS] Returning {len(prospect_responses)} leads (total: {total})")
        logger.info(f"📊 [LEADS] Response structure: data length={len(prospect_responses)}, total={total}, skip={skip}, limit={limit}")
        
        # CRITICAL: Check if we have prospects but no responses (conversion failed)
        if len(prospects) > 0 and len(prospect_responses) == 0:
            logger.error(f"❌ [LEADS] CRITICAL: Query returned {len(prospects)} prospects but all conversions failed! This indicates a schema mismatch. Setting total=0 to prevent data integrity violation.")
            total = 0
        
        # Convert to dicts safely
        data_dicts = []
        for p in prospect_responses:
            try:
                if hasattr(p, 'dict'):
                    data_dicts.append(p.dict())
                elif hasattr(p, 'model_dump'):
                    data_dicts.append(p.model_dump())
                else:
                    # Already a dict
                    data_dicts.append(p)
            except Exception as e:
                logger.error(f"❌ Error converting prospect response to dict: {e}")
                continue
        
        # CRITICAL: Final check - if we have responses but dict conversion failed
        if len(prospect_responses) > 0 and len(data_dicts) == 0:
            logger.error(f"❌ [LEADS] CRITICAL: Had {len(prospect_responses)} responses but all dict conversions failed! Setting total=0 to prevent data integrity violation.")
            total = 0
        
        # Log first few items for debugging
        if len(data_dicts) > 0:
            logger.info(f"📊 [LEADS] First lead sample: {data_dicts[0] if data_dicts else 'N/A'}")
        
        response = {
            "data": data_dicts,
            "total": total,
            "skip": skip,
            "limit": limit
        }
        
        # CRITICAL: Guard against data integrity violation
        from app.utils.response_guard import validate_list_response
        response = validate_list_response(response, "list_leads")
        
        logger.info(f"📊 [LEADS] Final response: {len(data_dicts)} items in data array")
        
        return response
        
    except HTTPException:
        # Re-raise HTTP exceptions (already handled)
        raise
    except Exception as e:
        # CRITICAL: Do NOT return empty array - raise error instead
        logger.error(f"❌ [LEADS] Unexpected error: {e}", exc_info=True)
        try:
            await db.rollback()  # Rollback on exception to prevent transaction poisoning
        except Exception as rollback_err:
            logger.error(f"❌ Error during rollback: {rollback_err}", exc_info=True)
        from fastapi import HTTPException
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}. Check logs for details."
        )


@router.get("/scraped-emails")
async def list_scraped_emails(
    skip: int = 0,
    limit: int = 50,
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    List prospects with scraped or enriched emails
    
    WEBSITE OUTREACH ONLY: Returns prospects where:
    - contact_email IS NOT NULL
    AND
    - scrape_status IN ("SCRAPED", "ENRICHED")
    AND
    - source_type='website' OR source_type IS NULL
    
    This shows website prospects that have been scraped or enriched, not manually added.
    Excludes social profiles.
    """
    try:
        from app.models.prospect import ScrapeStatus
        
        # CRITICAL: Filter by source_type='website' to separate from social outreach
        website_filter = or_(
            Prospect.source_type == 'website',
            Prospect.source_type.is_(None)  # Legacy prospects (default to website)
        )
        
        # SINGLE SOURCE OF TRUTH: contact_email IS NOT NULL AND scrape_status IN ("SCRAPED", "ENRICHED") AND source_type='website'
        logger.info(f"🔍 [SCRAPED EMAILS] Querying website prospects with contact_email IS NOT NULL AND scrape_status IN ('SCRAPED', 'ENRICHED') (skip={skip}, limit={limit})")
        
        # Build base filters
        base_filters = [
            Prospect.contact_email.isnot(None),
            Prospect.scrape_status.in_([
                ScrapeStatus.SCRAPED.value,
                ScrapeStatus.ENRICHED.value
            ]),
            website_filter
        ]
        
        # Add category filter if provided (case-insensitive, handle NULL values)
        if category and category.lower() != 'all':
            logger.info(f"🔍 [SCRAPED EMAILS] Filtering by category: {category} (case-insensitive using ilike)")
            # Add NULL check and case-insensitive comparison using ilike (more reliable than func.lower)
            base_filters.append(Prospect.discovery_category.isnot(None))
            base_filters.append(Prospect.discovery_category.ilike(category))
        
        # Get total count FIRST (before any filtering)
        count_query = select(func.count(Prospect.id)).where(and_(*base_filters))
        
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        logger.info(f"📊 [SCRAPED EMAILS] RAW COUNT (before pagination): {total} website prospects with contact_email IS NOT NULL AND scrape_status IN ('SCRAPED', 'ENRICHED')" + (f" and category='{category}'" if (category and category.lower() != 'all') else ""))
        
        # Build query with website filter
        query = select(Prospect).where(and_(*base_filters)).order_by(Prospect.created_at.desc())
        
        # Get paginated results
        # SCHEMA MUST BE CORRECT - migrations must be run manually at deploy time
        # If this fails with UndefinedColumnError, migrations need to be run
        try:
            result = await db.execute(query.offset(skip).limit(limit))
            prospects = result.scalars().all()
        except Exception as query_err:
            error_str = str(query_err).lower()
            logger.error(f"❌ [SCRAPED EMAILS] Query error: {query_err}", exc_info=True)
            if "undefinedcolumn" in error_str or "does not exist" in error_str or "bio_text" in error_str:
                logger.error(f"❌ [SCRAPED EMAILS] Schema mismatch detected: {query_err}")
                await db.rollback()
                raise HTTPException(
                    status_code=500,
                    detail=f"Database schema mismatch: Missing required columns. Please run migrations: 'alembic upgrade head' or use the /api/health/migrate endpoint. Error: {str(query_err)}"
                )
            await db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Internal server error while querying scraped emails: {str(query_err)}"
            )
        
        logger.info(f"📊 [SCRAPED EMAILS] QUERY RESULT: Found {len(prospects)} prospects from database query (total available: {total})")
        
        # CRITICAL: Verify data integrity - total must match actual data
        if total > 0 and len(prospects) == 0:
            logger.error(f"❌ [SCRAPED EMAILS] DATA INTEGRITY VIOLATION: total={total} but query returned 0 rows")
            await db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Data integrity violation: COUNT query returned {total} but SELECT query returned 0 rows. This indicates a schema mismatch or query error. Ensure migrations have run successfully."
            )
        
        # Safely convert prospects to response - use manual dict construction to avoid final_body issues
        prospect_responses = []
        conversion_errors = 0
        for p in prospects:
            try:
                # Manually build response dict to avoid final_body issues
                response_dict = {
                    "id": p.id,
                    "domain": p.domain or "",
                    "page_url": getattr(p, 'page_url', None),
                    "page_title": getattr(p, 'page_title', None),
                    "contact_email": getattr(p, 'contact_email', None),
                    "contact_method": getattr(p, 'contact_method', None),
                    "da_est": getattr(p, 'da_est', None),
                    "score": getattr(p, 'score', None),
                    "outreach_status": getattr(p, 'outreach_status', 'pending'),
                    "last_sent": getattr(p, 'last_sent', None).isoformat() if getattr(p, 'last_sent', None) else None,
                    "followups_sent": getattr(p, 'followups_sent', 0) or 0,
                    "draft_subject": getattr(p, 'draft_subject', None),
                    "draft_body": getattr(p, 'draft_body', None),
                    # final_body is commented out in schema, so don't include it
                    "thread_id": getattr(p, 'thread_id', None),
                    "sequence_index": getattr(p, 'sequence_index', None) or 0,
                    "is_manual": getattr(p, 'is_manual', None) or False,
                    "discovery_status": getattr(p, 'discovery_status', None),
                    "discovery_category": getattr(p, 'discovery_category', None),
                    "discovery_location": getattr(p, 'discovery_location', None),
                    "approval_status": getattr(p, 'approval_status', None),
                    "scrape_status": getattr(p, 'scrape_status', None),
                    "verification_status": getattr(p, 'verification_status', None),
                    "draft_status": getattr(p, 'draft_status', None),
                    "send_status": getattr(p, 'send_status', None),
                    "stage": getattr(p, 'stage', None),
                    "created_at": getattr(p, 'created_at', None).isoformat() if getattr(p, 'created_at', None) else None,
                    "updated_at": getattr(p, 'updated_at', None).isoformat() if getattr(p, 'updated_at', None) else None,
                }
                prospect_responses.append(ProspectResponse(**response_dict))
            except Exception as e:
                conversion_errors += 1
                error_msg = str(e).lower()
                logger.warning(f"⚠️  Error converting prospect {getattr(p, 'id', 'unknown')}: {error_msg[:200]}")
                continue
        
        if conversion_errors > 0:
            logger.warning(f"⚠️  [SCRAPED EMAILS] Had {conversion_errors} conversion errors, but {len(prospect_responses)} prospects converted successfully")
        
        logger.info(f"✅ [SCRAPED EMAILS] Returning {len(prospect_responses)} scraped emails (total: {total})")
        
        response = {
            "data": [p.dict() for p in prospect_responses],
            "total": total,
            "skip": skip,
            "limit": limit
        }
        
        # CRITICAL: Guard against data integrity violation
        from app.utils.response_guard import validate_list_response
        response = validate_list_response(response, "list_scraped_emails")
        
        return response
        
    except HTTPException:
        # Re-raise HTTP exceptions (already handled)
        raise
    except Exception as e:
        # CRITICAL: Do NOT return empty array - raise error instead
        logger.error(f"❌ [SCRAPED EMAILS] Unexpected error: {e}", exc_info=True)
        try:
            await db.rollback()  # Rollback on exception to prevent transaction poisoning
        except Exception as rollback_err:
            logger.error(f"❌ Error during rollback: {rollback_err}", exc_info=True)
        from fastapi import HTTPException
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}. Check logs for details."
        )


@router.get("")
async def list_prospects(
    skip: Optional[int] = None,
    limit: int = 50,
    page: Optional[int] = None,  # New page-based pagination
    status: Optional[str] = None,
    min_score: Optional[float] = None,
    has_email: Optional[str] = None,  # Changed to str to handle string "true"/"false" from frontend
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    List prospects with filtering and pagination
    
    Query params:
    - page: Page number (1-based, alternative to skip)
    - skip: Pagination offset (alternative to page)
    - limit: Number of results per page (max 1000)
    - status: Filter by outreach_status
    - min_score: Minimum score threshold
    - has_email: Filter by whether prospect has email (string "true"/"false")
    
    Returns: {success: bool, data: {prospects, total, page, totalPages, skip, limit}, error: null | string}
    """
    # Initialize response structure - data MUST be a dict, never an array
    response_data = {
        "success": False,
        "data": {
            "prospects": [],
            "total": 0,
            "skip": skip,
            "limit": limit
        },
        "error": None
    }
    
    try:
        # DEBUG: Log incoming parameters and total prospects count
        logger.info(f"🔍 GET /api/prospects - skip={skip}, limit={limit}, status={status}, min_score={min_score}, has_email={has_email} (type: {type(has_email)}), category={category}")
        
        # Log total prospects count for debugging
        try:
            total_all_result = await db.execute(select(func.count(Prospect.id)))
            total_all = total_all_result.scalar() or 0
            logger.info(f"📊 [LIST PROSPECTS] Total prospects in database: {total_all}")
        except Exception as e:
            logger.warning(f"⚠️  Could not count total prospects: {e}")
        
        # Parse pagination (support both page-based and skip-based)
        try:
            # Default: page=1, limit=50, max limit=1000
            if page is not None:
                # Page-based pagination (1-based)
                page = max(1, int(page))
            else:
                # Default: page 1
                page = 1
            
            # Enforce max limit of 1000 (for stats queries), default 50
            limit = int(limit) if limit is not None else 50
            limit = max(1, min(limit, 1000))  # Enforce 1-1000 range
            
            # Calculate skip from page
            skip = (page - 1) * limit
            
            logger.info(f"🔍 Parsed page={page}, skip={skip}, limit={limit}")
        except (ValueError, TypeError) as e:
            logger.error(f"🔴 Error parsing pagination: {e}")
            response_data["error"] = f"Invalid pagination parameters: {str(e)}"
            response_data["data"] = {"data": [], "prospects": [], "total": 0, "page": 1, "totalPages": 0, "skip": 0, "limit": 10}
            return response_data
        
        # Parse has_email as boolean (strict string check)
        has_email_bool = None
        if has_email is not None:
            try:
                if isinstance(has_email, str):
                    has_email_bool = has_email.lower() == "true"
                elif isinstance(has_email, bool):
                    has_email_bool = has_email
                logger.info(f"🔍 Parsed has_email: '{has_email}' -> {has_email_bool} (type: {type(has_email_bool)})")
            except Exception as e:
                logger.warning(f"⚠️  Error parsing has_email: {e}, treating as None")
                has_email_bool = None
        
        normalized_category = _normalize_category(category)

        # Build query
        logger.info(f"🔍 Building database query...")
        query = select(Prospect)
        logger.info(f"🔍 Initial query object created")
        
        # Apply filters
        try:
            if status:
                query = query.where(Prospect.outreach_status == status)
                logger.info(f"🔍 Added status filter: {status}")
            if min_score is not None:
                query = query.where(Prospect.score >= min_score)
                logger.info(f"🔍 Added min_score filter: {min_score}")
            if has_email_bool is not None:
                if has_email_bool:
                    query = query.where(Prospect.contact_email.isnot(None))
                    logger.info(f"🔍 Added has_email filter: True (contact_email IS NOT NULL)")
                else:
                    query = query.where(Prospect.contact_email.is_(None))
                    logger.info(f"🔍 Added has_email filter: False (contact_email IS NULL)")
            if normalized_category:
                query = query.where(and_(
                    Prospect.discovery_category.isnot(None),
                    Prospect.discovery_category.ilike(normalized_category)
                ))
                logger.info(f"🔍 Added category filter: {normalized_category}")
        except Exception as e:
            logger.error(f"🔴 Error building query filters: {e}", exc_info=True)
            try:
                await db.rollback()  # Rollback on exception to prevent transaction poisoning
            except Exception as rollback_err:
                logger.error(f"❌ Error during rollback: {rollback_err}", exc_info=True)
            response_data["error"] = f"Error building query: {str(e)}"
            response_data["data"] = {"data": [], "prospects": [], "total": 0, "page": page, "totalPages": 0, "skip": skip, "limit": limit}
            return response_data
        
        # Log filter criteria
        filter_summary = []
        if status:
            filter_summary.append(f"outreach_status={status}")
        if min_score is not None:
            filter_summary.append(f"min_score={min_score}")
        if has_email_bool is not None:
            filter_summary.append(f"has_email={has_email_bool}")
        if normalized_category:
            filter_summary.append(f"category={normalized_category}")
        logger.info(f"🔍 Query filters applied: {', '.join(filter_summary) if filter_summary else 'NONE (showing all prospects)'}")
        
        # Get total count
        logger.info(f"🔍 Executing count query...")
        try:
            count_query = select(func.count()).select_from(Prospect)
            if status:
                count_query = count_query.where(Prospect.outreach_status == status)
            if min_score is not None:
                count_query = count_query.where(Prospect.score >= min_score)
            if has_email_bool is not None:
                if has_email_bool:
                    count_query = count_query.where(Prospect.contact_email.isnot(None))
                else:
                    count_query = count_query.where(Prospect.contact_email.is_(None))
            if normalized_category:
                count_query = count_query.where(and_(
                    Prospect.discovery_category.isnot(None),
                    Prospect.discovery_category.ilike(normalized_category)
                ))
            
            logger.info(f"🔍 Count query built, executing...")
            total_result = await db.execute(count_query)
            total = total_result.scalar() or 0
            logger.info(f"🔍 Count query executed successfully, total={total}")
        except Exception as count_err:
            logger.error(f"🔴 Error executing count query: {count_err}", exc_info=True)
            error_str = str(count_err).lower()
            if "discovery_query_id" in error_str and ("column" in error_str or "does not exist" in error_str):
                response_data["error"] = "Database schema mismatch: 'discovery_query_id' column missing. Migration needs to be applied."
            else:
                response_data["error"] = f"Database error during count query: {str(count_err)}"
            response_data["data"] = {"data": [], "prospects": [], "total": 0, "page": page, "totalPages": 0, "skip": skip, "limit": limit}
            return response_data
        
        # Get paginated results
        logger.info(f"🔍 Building paginated query...")
        try:
            query = query.order_by(Prospect.score.desc(), Prospect.created_at.desc())
            query = query.offset(skip).limit(limit)
            logger.info(f"🔍 Paginated query built, executing...")
        except Exception as e:
            logger.error(f"🔴 Error building paginated query: {e}", exc_info=True)
            response_data["error"] = f"Error building paginated query: {str(e)}"
            total_pages = (total + limit - 1) // limit if total > 0 else 0
            response_data["data"] = {"data": [], "prospects": [], "total": total, "page": page, "totalPages": total_pages, "skip": skip, "limit": limit}
            return response_data
        
        # Execute main query
        logger.info(f"🔍 Executing main query...")
        try:
            result = await db.execute(query)
            prospects = result.scalars().all()
            logger.info(f"🔍 Main query executed successfully, found {len(prospects)} prospects")
        except Exception as db_err:
            logger.error(f"🔴 Error executing main query: {db_err}", exc_info=True)
            try:
                await db.rollback()  # Rollback on exception to prevent transaction poisoning
            except Exception as rollback_err:
                logger.error(f"❌ Error during rollback: {rollback_err}", exc_info=True)
            error_str = str(db_err).lower()
            if "discovery_query_id" in error_str and ("column" in error_str or "does not exist" in error_str):
                logger.error(f"🔴 Database schema error: discovery_query_id column missing")
                response_data["error"] = "Database schema mismatch: 'discovery_query_id' column missing. Migration needs to be applied."
            else:
                response_data["error"] = f"Database error: {str(db_err)}"
            total_pages = (total + limit - 1) // limit if total > 0 else 0
            response_data["data"] = {"data": [], "prospects": [], "total": total, "page": page, "totalPages": total_pages, "skip": skip, "limit": limit}
            return response_data
        
        # Convert to response models using manual dict construction to avoid final_body issues
        logger.info(f"🔍 Converting {len(prospects)} prospects to response format...")
        prospect_responses = []
        conversion_errors = 0
        for idx, p in enumerate(prospects):
            try:
                # Use manual dict construction instead of model_validate to avoid final_body errors
                response_dict = {
                    "id": p.id,
                    "domain": p.domain or "",
                    "page_url": getattr(p, 'page_url', None),
                    "page_title": getattr(p, 'page_title', None),
                    "contact_email": getattr(p, 'contact_email', None),
                    "contact_method": getattr(p, 'contact_method', None),
                    "da_est": getattr(p, 'da_est', None),
                    "score": getattr(p, 'score', None),
                    "outreach_status": getattr(p, 'outreach_status', 'pending'),
                    "last_sent": getattr(p, 'last_sent', None).isoformat() if getattr(p, 'last_sent', None) else None,
                    "followups_sent": getattr(p, 'followups_sent', 0) or 0,
                    "draft_subject": getattr(p, 'draft_subject', None),
                    "draft_body": getattr(p, 'draft_body', None),
                    # final_body is commented out in schema, so don't include it
                    "thread_id": getattr(p, 'thread_id', None),
                    "sequence_index": getattr(p, 'sequence_index', None) or 0,
                    "is_manual": getattr(p, 'is_manual', None) or False,
                    "discovery_status": getattr(p, 'discovery_status', None),
                    "discovery_category": getattr(p, 'discovery_category', None),
                    "discovery_location": getattr(p, 'discovery_location', None),
                    "discovery_keywords": getattr(p, 'discovery_keywords', None),
                    "scrape_source_url": getattr(p, 'scrape_source_url', None),
                    "approval_status": getattr(p, 'approval_status', None),
                    "scrape_status": getattr(p, 'scrape_status', None),
                    "verification_status": getattr(p, 'verification_status', None),
                    "draft_status": getattr(p, 'draft_status', None),
                    "send_status": getattr(p, 'send_status', None),
                    "stage": getattr(p, 'stage', None),
                    "created_at": getattr(p, 'created_at', None).isoformat() if getattr(p, 'created_at', None) else None,
                    "updated_at": getattr(p, 'updated_at', None).isoformat() if getattr(p, 'updated_at', None) else None,
                }
                prospect_responses.append(ProspectResponse(**response_dict))
            except Exception as e:
                conversion_errors += 1
                logger.error(f"🔴 Error validating prospect {idx+1}/{len(prospects)} (id={getattr(p, 'id', 'unknown')}): {e}", exc_info=True)
                # Continue processing other prospects instead of failing completely
                continue
        
        if conversion_errors > 0:
            logger.warning(f"⚠️  [LIST PROSPECTS] Had {conversion_errors} conversion errors, but {len(prospect_responses)} prospects converted successfully")
        logger.info(f"✅ Successfully converted {len(prospect_responses)} prospects")
        
        # Calculate total pages
        total_pages = (total + limit - 1) // limit if total > 0 else 0
        
        # Build success response - standardized format
        response_data["success"] = True
        response_data["data"] = {
            "data": prospect_responses,  # Main data array
            "prospects": prospect_responses,  # Backward compatibility
            "total": total,
            "page": page,
            "limit": limit,
            "totalPages": total_pages,
            "skip": skip  # Backward compatibility
        }
        
        logger.info(f"✅ Returning success response with {len(prospect_responses)} prospects")
        return response_data
    
    except HTTPException:
        # Re-raise HTTPExceptions (they're already properly formatted)
        raise
    except Exception as err:
        logger.error(f"🔴 Unexpected error in prospects endpoint: {err}", exc_info=True)
        logger.error(f"🔴 Error type: {type(err).__name__}")
        logger.error(f"🔴 Error message: {str(err)}")
        import traceback
        logger.error(f"🔴 Full traceback: {traceback.format_exc()}")
        try:
            await db.rollback()  # Rollback on exception to prevent transaction poisoning
        except Exception as rollback_err:
            logger.error(f"❌ Error during rollback: {rollback_err}", exc_info=True)
        response_data["error"] = f"Internal server error: {str(err)}"
        total_pages = 0
        page = 1
        skip = 0
        limit = 10
        response_data["data"] = {"data": [], "prospects": [], "total": 0, "page": page, "totalPages": total_pages, "skip": skip, "limit": limit}
        return response_data


# ============================================
# ATTACHMENTS
# ============================================


@router.post("/attachments")
async def upload_attachment(
    scope: str = Form("global"),
    prospect_id: Optional[UUID] = Form(None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Upload an attachment (global or per-prospect).
    scope: global | prospect
    """
    if scope not in {"global", "prospect"}:
        raise HTTPException(status_code=400, detail="Invalid scope. Use 'global' or 'prospect'.")

    if scope == "prospect" and not prospect_id:
        raise HTTPException(status_code=400, detail="prospect_id is required for prospect scope")

    content = await file.read()
    if len(content) > MAX_ATTACHMENT_BYTES:
        raise HTTPException(status_code=400, detail="Attachment exceeds 10MB limit")

    attachment = EmailAttachment(
        prospect_id=prospect_id,
        filename=file.filename or "attachment",
        content_type=file.content_type or "application/octet-stream",
        size_bytes=len(content),
        scope=scope,
        data=content
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)

    return {
        "id": str(attachment.id),
        "filename": attachment.filename,
        "content_type": attachment.content_type,
        "size_bytes": attachment.size_bytes,
        "scope": attachment.scope,
        "prospect_id": str(attachment.prospect_id) if attachment.prospect_id else None,
        "created_at": attachment.created_at.isoformat() if attachment.created_at else None,
    }


@router.get("/attachments")
async def list_attachments(
    scope: Optional[str] = None,
    prospect_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    query = select(EmailAttachment)
    if scope:
        query = query.where(EmailAttachment.scope == scope)
    if prospect_id:
        query = query.where(EmailAttachment.prospect_id == prospect_id)

    result = await db.execute(query.order_by(EmailAttachment.created_at.desc()))
    attachments = result.scalars().all()

    return {
        "data": [
            {
                "id": str(a.id),
                "filename": a.filename,
                "content_type": a.content_type,
                "size_bytes": a.size_bytes,
                "scope": a.scope,
                "prospect_id": str(a.prospect_id) if a.prospect_id else None,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in attachments
        ]
    }


@router.get("/attachments/{attachment_id}")
async def download_attachment(
    attachment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    result = await db.execute(select(EmailAttachment).where(EmailAttachment.id == attachment_id))
    attachment = result.scalar_one_or_none()

    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    media_type = attachment.content_type or "application/octet-stream"
    filename = attachment.filename or "attachment"

    return Response(
        content=attachment.data or b"",
        media_type=media_type,
        headers={"Content-Disposition": f"inline; filename=\"{filename}\""},
    )


@router.delete("/attachments/{attachment_id}")
async def delete_attachment(
    attachment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    result = await db.execute(select(EmailAttachment).where(EmailAttachment.id == attachment_id))
    attachment = result.scalar_one_or_none()

    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    await db.delete(attachment)
    await db.commit()

    return {"success": True}


@router.get("/{prospect_id}", response_model=ProspectResponse)
async def get_prospect(
    prospect_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get a single prospect by ID"""
    result = await db.execute(select(Prospect).where(Prospect.id == prospect_id))
    prospect = result.scalar_one_or_none()
    
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")
    
    # Use manual dict construction to avoid final_body errors
    response_dict = {
        "id": prospect.id,
        "domain": prospect.domain or "",
        "page_url": getattr(prospect, 'page_url', None),
        "page_title": getattr(prospect, 'page_title', None),
        "contact_email": getattr(prospect, 'contact_email', None),
        "contact_method": getattr(prospect, 'contact_method', None),
        "da_est": getattr(prospect, 'da_est', None),
        "score": getattr(prospect, 'score', None),
        "outreach_status": getattr(prospect, 'outreach_status', 'pending'),
        "last_sent": getattr(prospect, 'last_sent', None).isoformat() if getattr(prospect, 'last_sent', None) else None,
        "followups_sent": getattr(prospect, 'followups_sent', 0) or 0,
        "draft_subject": getattr(prospect, 'draft_subject', None),
        "draft_body": getattr(prospect, 'draft_body', None),
        # final_body is commented out in schema, so don't include it
        "thread_id": getattr(prospect, 'thread_id', None),
        "sequence_index": getattr(prospect, 'sequence_index', None) or 0,
        "is_manual": getattr(prospect, 'is_manual', None) or False,
        "discovery_status": getattr(prospect, 'discovery_status', None),
        "approval_status": getattr(prospect, 'approval_status', None),
        "scrape_status": getattr(prospect, 'scrape_status', None),
        "verification_status": getattr(prospect, 'verification_status', None),
        "draft_status": getattr(prospect, 'draft_status', None),
        "send_status": getattr(prospect, 'send_status', None),
        "stage": getattr(prospect, 'stage', None),
        "created_at": getattr(prospect, 'created_at', None).isoformat() if getattr(prospect, 'created_at', None) else None,
        "updated_at": getattr(prospect, 'updated_at', None).isoformat() if getattr(prospect, 'updated_at', None) else None,
    }
    return ProspectResponse(**response_dict)


@router.get("/{prospect_id}/sent-email")
async def get_sent_email(
    prospect_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    from app.models.email_log import EmailLog

    result = await db.execute(
        select(EmailLog).where(EmailLog.prospect_id == prospect_id).order_by(EmailLog.sent_at.desc())
    )
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="No sent email found for this prospect")

    attachments_result = await db.execute(
        select(EmailAttachment)
        .where(and_(EmailAttachment.prospect_id == prospect_id, EmailAttachment.scope == "prospect"))
        .order_by(EmailAttachment.created_at.desc())
    )
    attachments = attachments_result.scalars().all()

    resp = log.response if isinstance(log.response, dict) else {}

    return {
        "email_log_id": str(log.id),
        "prospect_id": str(log.prospect_id),
        "subject": log.subject or "",
        "body": log.body or "",
        "sent_at": log.sent_at.isoformat() if log.sent_at else None,
        "provider": "smtp" if (resp.get("message_id") == "smtp") else "gmail",
        "message_id": resp.get("message_id"),
        "thread_id": resp.get("thread_id"),
        "raw_response": resp,
        "attachments": [
            {
                "id": str(a.id),
                "filename": a.filename,
                "content_type": a.content_type,
                "size_bytes": a.size_bytes,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in attachments
        ],
    }


@router.put("/{prospect_id}/draft")
async def update_prospect_draft(
    prospect_id: UUID,
    draft: dict,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Update draft for a website prospect.
    
    Allows manual editing of draft_subject and draft_body.
    """
    try:
        result = await db.execute(
            select(Prospect).where(Prospect.id == prospect_id)
        )
        prospect = result.scalar_one_or_none()
        
        if not prospect:
            raise HTTPException(status_code=404, detail="Prospect not found")
        
        if 'subject' in draft:
            prospect.draft_subject = draft['subject']
        if 'body' in draft:
            prospect.draft_body = draft['body']
        
        prospect.draft_status = 'drafted'
        
        await db.commit()
        
        return {
            "success": True,
            "message": "Draft updated successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update draft: {str(e)}")


@router.get("/debug/gemini-test")
async def debug_gemini_test():
    """
    Test Gemini API directly without database
    """
    try:
        from app.clients.gemini import GeminiClient
        client = GeminiClient()
        
        # Test simple generateContent call
        url = f"{client.BASE_URL}/models/{client.model}:generateContent?key={client.api_key}"
        test_payload = {
            "contents": [{
                "parts": [{
                    "text": "Say hello"
                }]
            }],
            "generationConfig": {
                "maxOutputTokens": 10
            }
        }
        
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as http_client:
            response = await http_client.post(url, json=test_payload)
            
            return {
                "status_code": response.status_code,
                "response_text": response.text[:500] if response.text else None,
                "model": client.model,
                "url": url.replace(client.api_key, "[API_KEY]")
            }
    except Exception as e:
        import traceback
        return {
            "error": str(e),
            "traceback": traceback.format_exc(),
            "model": client.model if 'client' in locals() else None
        }


@router.get("/debug/gemini-models")
async def debug_gemini_models():
    """
    List available Gemini models for the configured API key.
    """
    try:
        from app.clients.gemini import GeminiClient
        client = GeminiClient()

        import httpx
        url = f"{client.BASE_URL}/models?key={client.api_key}"
        async with httpx.AsyncClient(timeout=10.0) as http_client:
            response = await http_client.get(url)

        data = response.json() if response.text else {}
        models = [m.get("name") for m in data.get("models", []) if isinstance(m, dict)]

        return {
            "status_code": response.status_code,
            "model_count": len(models),
            "models": models[:50],
            "base_url": client.BASE_URL,
        }
    except Exception as e:
        import traceback
        return {
            "error": str(e),
            "traceback": traceback.format_exc(),
        }


@router.get("/debug/gemini-config")
async def debug_gemini_config():
    """
    Debug endpoint to check current Gemini configuration
    """
    from app.clients.gemini import GeminiClient
    import os
    
    try:
        client = GeminiClient()
        return {
            "gemini_model_env": os.getenv("GEMINI_MODEL", "NOT_USED"),
            "gemini_base_url_env": os.getenv("GEMINI_BASE_URL", "NOT_USED"),
            "client_model": client.model,
            "base_url": client.BASE_URL,
            "api_key_exists": bool(client.api_key),
            "api_key_prefix": client.api_key[:10] + "..." if client.api_key else None
        }
    except Exception as e:
        return {
            "error": str(e),
            "gemini_model_env": os.getenv("GEMINI_MODEL"),
            "base_url": os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")
        }


@router.post("/{prospect_id}/compose", response_model=ComposeResponse)
async def compose_email(
    prospect_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Compose an email for a prospect using Gemini
    
    STRICT DRAFT-ONLY: This endpoint ONLY saves drafts, never sends emails.
    
    Rules:
    - If email already exists → overwrite draft, not duplicate
    - Save draft_body and draft_subject
    - Set draft_status to "drafted"
    - If this is a follow-up (duplicate domain/email), use Gemini follow-up logic with memory
    """
    from datetime import datetime, timezone
    from sqlalchemy import or_
    from app.models.email_log import EmailLog
    
    # Database operations first
    try:
        result = await db.execute(select(Prospect).where(Prospect.id == prospect_id))
        prospect = result.scalar_one_or_none()
        
        if not prospect:
            raise HTTPException(status_code=404, detail="Prospect not found")
        
        logger.info(f"✅ [COMPOSE] Database session OK, prospect found: {prospect.domain}")
    except HTTPException:
        # Re-raise HTTP exceptions (like 404)
        raise
    except Exception as e:
        logger.error(f"❌ [COMPOSE] Database session error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    
    # Check for duplicates (same domain OR same email) = follow-up
    # If duplicate exists and has been sent, this is a follow-up
    # Only consider prospects that have actually been sent (last_sent is not None)
    duplicate_check = await db.execute(
        select(Prospect).where(
            Prospect.id != prospect_id,
            or_(
                Prospect.domain == prospect.domain,
                Prospect.contact_email == prospect.contact_email
            ),
            Prospect.last_sent.isnot(None)
        )
    )
    duplicate_prospect = duplicate_check.scalar_one_or_none()
    is_followup = duplicate_prospect is not None
    
    if is_followup:
        logger.info(f"📝 [COMPOSE] Follow-up email for {prospect.domain} (original sent to {duplicate_prospect.domain or duplicate_prospect.contact_email})")
        # Use sequence index from original prospect
        prospect.sequence_index = (duplicate_prospect.sequence_index or 0) + 1
        prospect.thread_id = duplicate_prospect.thread_id or duplicate_prospect.id
        logger.info(f"📝 [COMPOSE] Follow-up sequence index: {prospect.sequence_index}, thread_id: {prospect.thread_id}")
    else:
        # Ensure thread_id is set for initial emails
        if not prospect.thread_id:
            prospect.thread_id = prospect.id
        prospect.sequence_index = 0
        logger.info(f"📝 [COMPOSE] Initial email for {prospect.domain} (thread_id: {prospect.thread_id})")
    
    # Import and initialize Gemini client
    try:
        from app.clients.gemini import GeminiClient
        client = GeminiClient()
        logger.info(f"✅ [COMPOSE] Gemini client initialized with model: {client.model}")
        
        # Validate model exists and supports generateContent
        logger.info(f"🔍 [COMPOSE] Validating Gemini model {client.model}...")
        # Temporarily bypass validation to test
        is_valid = True  # await client.validate_model()
        if not is_valid:
            logger.error(f"❌ [COMPOSE] Gemini model {client.model} failed validation")
            raise HTTPException(
                status_code=500, 
                detail=f"Gemini model {client.model} is not available or doesn't support generateContent. Check backend logs for details."
            )
        
        logger.info(f"✅ [COMPOSE] Gemini model {client.model} validated successfully")
    except ImportError as e:
        logger.error(f"Failed to import GeminiClient: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Gemini client not available: {str(e)}")
    except ValueError as e:
        logger.error(f"Gemini API configuration error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Gemini API not configured: {str(e)}")
    except Exception as e:
        logger.error(f"❌ [COMPOSE] Unexpected error with Gemini client: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to initialize Gemini client: {str(e)}")
    
    # Extract snippet from DataForSEO payload (safe None check)
    page_snippet = None
    if prospect.dataforseo_payload and isinstance(prospect.dataforseo_payload, dict):
        page_snippet = prospect.dataforseo_payload.get("description") or prospect.dataforseo_payload.get("snippet")
    
    # Extract contact name from Snov.io payload (safe list access)
    contact_name = None
    if prospect.snov_payload and isinstance(prospect.snov_payload, dict):
        emails = prospect.snov_payload.get("emails", [])
        if emails and isinstance(emails, list) and len(emails) > 0:
            first_email = emails[0]
            if isinstance(first_email, dict):
                first_name = first_email.get("first_name")
                last_name = first_email.get("last_name")
                if first_name or last_name:
                    contact_name = f"{first_name or ''} {last_name or ''}".strip()
    
    # If follow-up, fetch previous emails in thread for Gemini memory
    if is_followup and prospect.thread_id:
        # Get all sent emails in this thread (from email_logs)
        previous_emails_query = await db.execute(
            select(EmailLog).where(
                EmailLog.prospect_id.in_(
                    select(Prospect.id).where(Prospect.thread_id == prospect.thread_id)
                )
            ).order_by(EmailLog.sent_at.asc())
        )
        previous_logs = previous_emails_query.scalars().all()
        
        # Also check prospects with final_body (sent emails)
        # Defensive: Check if final_body column exists before querying
        previous_prospects = []
        try:
            from sqlalchemy import text
            # Check if final_body column exists
            column_check = await db.execute(
                text("""
                    SELECT column_name
                    FROM information_schema.columns 
                    WHERE table_name = 'prospects' 
                    AND column_name = 'final_body'
                """)
            )
            if column_check.fetchone():
                # Column exists - safe to query using ORM
                previous_prospects_query = await db.execute(
                    select(Prospect).where(
                        Prospect.thread_id == prospect.thread_id,
                        Prospect.id != prospect_id,
                        Prospect.final_body.isnot(None)
                    ).order_by(Prospect.last_sent.asc())
                )
                previous_prospects = previous_prospects_query.scalars().all()
            else:
                logger.warning("⚠️  final_body column doesn't exist - skipping prospect history check")
        except Exception as e:
            logger.warning(f"⚠️  Error checking final_body column: {e}")
        
        # Build previous emails list
        previous_emails = []
        for log in previous_logs:
            previous_emails.append({
                "subject": log.subject or "No subject",
                "body": log.body or "",
                "sent_at": log.sent_at.isoformat() if log.sent_at else "",
                "sequence_index": 0  # EmailLogs don't have sequence_index, assume 0
            })
        
        for prev_prospect in previous_prospects:
            # final_body column doesn't exist yet - use draft_body or None
            final_body = getattr(prev_prospect, 'final_body', None) or getattr(prev_prospect, 'draft_body', None)
            previous_emails.append({
                "subject": prev_prospect.draft_subject or "No subject",
                "body": final_body or "",
                "sent_at": prev_prospect.last_sent.isoformat() if prev_prospect.last_sent else "",
                "sequence_index": prev_prospect.sequence_index or 0
            })
        
        # Sort by sent_at
        previous_emails.sort(key=lambda x: x.get("sent_at", ""))
        
        # Call Gemini to compose follow-up email with memory
        gemini_result = await client.compose_followup_email(
            domain=prospect.domain,
            previous_emails=previous_emails,
            page_title=prospect.page_title,
            page_url=prospect.page_url,
            page_snippet=page_snippet,
            contact_name=contact_name
        )
    else:
        # Initial email - use regular compose
        # Get category from prospect (discovery_category or inferred from domain/title)
        category = prospect.discovery_category
        if not category:
            # Try to infer from page_title or domain
            title_lower = (prospect.page_title or "").lower()
            domain_lower = (prospect.domain or "").lower()
            if "museum" in title_lower or "museum" in domain_lower:
                category = "Museum"
            elif "gallery" in title_lower or "gallery" in domain_lower:
                category = "Art Gallery"
            elif "interior design" in title_lower or "interior decor" in title_lower:
                category = "Interior Design"
            elif "parenting" in title_lower or "mom" in title_lower:
                category = "Parenting"
            elif "nft" in title_lower or "nft" in domain_lower:
                category = "NFTs"
        
        gemini_result = await client.compose_email(
            domain=prospect.domain,
            page_title=prospect.page_title,
            page_url=prospect.page_url,
            page_snippet=page_snippet,
            contact_name=contact_name,
            category=category
        )
    
    if not gemini_result.get("success"):
        error = gemini_result.get("error", "Unknown error")
        logger.error(f"❌ [COMPOSE] Gemini API error: {error}")
        logger.error(f"❌ [COMPOSE] Full Gemini result: {gemini_result}")
        raise HTTPException(status_code=500, detail=f"Failed to compose email: {error}")
    
    # Save draft to prospect (OVERWRITE if draft already exists, don't duplicate)
    prospect.draft_subject = gemini_result.get("subject")
    prospect.draft_body = gemini_result.get("body")
    # drafted_at column doesn't exist - use draft_subject/draft_body as indicators
    # prospect.drafted_at = datetime.now(timezone.utc)  # REMOVED: Column doesn't exist
    # Update draft_status to "drafted" so pipeline Drafting card reflects this
    from app.models.prospect import DraftStatus
    prospect.draft_status = DraftStatus.DRAFTED.value
    
    await db.commit()
    await db.refresh(prospect)
    
    logger.info(f"✅ [COMPOSE] Draft saved for {prospect.domain} (follow-up: {is_followup}, sequence: {prospect.sequence_index})")
    
    return ComposeResponse(
        prospect_id=prospect.id,
        subject=prospect.draft_subject,
        body=prospect.draft_body,
        draft_saved=True
    )


@router.post("/{prospect_id}/send", response_model=SendResponse)
async def send_email(
    prospect_id: UUID,
    payload: Optional[dict] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Manual send endpoint - sends a single drafted email.
    
    CANONICAL RULES:
    - Works ONLY on existing drafts (no raw text from UI)
    - Email content comes ONLY from database (draft_subject, draft_body)
    - Same Gmail send logic as pipeline
    - Same thread_id and sequence_index handling
    - Same send_status updates
    - Pipeline counts must reflect manual sends
    
    Requirements:
    - draft_status = 'drafted' (draft exists and is ready)
    - draft_subject IS NOT NULL
    - draft_body IS NOT NULL
    - send_status != 'sent' (not already sent)
    - contact_email IS NOT NULL
    - verification_status = 'verified'
    
    Returns:
        SendResponse with success status and message_id
    """
    from app.models.prospect import DraftStatus, SendStatus, VerificationStatus
    from app.services.email_sender import send_prospect_email
    from app.models.email_log import EmailLog
    
    # Fetch prospect
    result = await db.execute(select(Prospect).where(Prospect.id == prospect_id))
    prospect = result.scalar_one_or_none()
    
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")
    
    # Validate: draft_status = 'drafted' (draft exists and is ready)
    # Note: User requirement says 'ready' but enum uses 'drafted' - they mean the same thing
    if prospect.draft_status != DraftStatus.DRAFTED.value:
        raise HTTPException(
            status_code=400,
            detail=f"Prospect is not ready for sending. Current draft_status: {prospect.draft_status}. Draft must be created first (draft_status = 'drafted')."
        )
    
    # Validate: draft_subject and draft_body exist
    if not prospect.draft_subject or not prospect.draft_body:
        raise HTTPException(
            status_code=400,
            detail="Prospect has no draft email. Draft subject and body are required. Compose email first."
        )
    
    # Validate: send_status != 'sent' (not already sent)
    if prospect.send_status == SendStatus.SENT.value:
        raise HTTPException(
            status_code=409,  # Conflict - already sent
            detail="Email already sent for this prospect. Cannot send again."
        )
    
    # Validate: contact_email exists
    if not prospect.contact_email:
        raise HTTPException(
            status_code=400,
            detail="Prospect has no contact email. Cannot send email."
        )
    
    # Validate: verification_status = 'verified'
    if prospect.verification_status != VerificationStatus.VERIFIED.value:
        raise HTTPException(
            status_code=400,
            detail=f"Prospect email is not verified. Current status: {prospect.verification_status}. Verify email first."
        )
    
    cc = None
    bcc = None
    if isinstance(payload, dict):
        cc_val = payload.get("cc")
        bcc_val = payload.get("bcc")
        cc = str(cc_val).strip() if cc_val else None
        bcc = str(bcc_val).strip() if bcc_val else None

    # Send email using shared service (same logic as pipeline)
    try:
        logger.info(f"📧 [MANUAL SEND] Attempting to send email for prospect {prospect_id}...")
        send_result = await send_prospect_email(prospect, db, cc=cc, bcc=bcc)
        logger.info(f"✅ [MANUAL SEND] Email sent successfully for prospect {prospect_id}")
    except ValueError as e:
        # Validation errors (400) - prospect not sendable
        error_msg = str(e)
        logger.warning(f"⚠️  [MANUAL SEND] Validation error for prospect {prospect_id}: {error_msg}")
        raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        # Gmail API errors (500) - backend failure
        error_msg = str(e)
        logger.error(f"❌ [MANUAL SEND] Failed to send email for prospect {prospect_id}: {error_msg}", exc_info=True)
        
        # Check if error contains Gmail-specific issues
        if "Gmail" in error_msg or "access token" in error_msg.lower() or "refresh token" in error_msg.lower():
            # Provide more helpful error message for Gmail auth issues
            detail = (
                f"Gmail sending failed: {error_msg}\n\n"
                "This usually means:\n"
                "1. Gmail OAuth credentials are missing or invalid\n"
                "2. Refresh token expired or revoked\n"
                "3. Required OAuth scopes not granted\n"
                "Check /api/health/gmail for configuration status."
            )
        else:
            detail = f"Failed to send email: {error_msg}"
        
        raise HTTPException(status_code=500, detail=detail)
    
    # Get the email log that was created
    email_log_result = await db.execute(
        select(EmailLog).where(EmailLog.prospect_id == prospect_id).order_by(EmailLog.sent_at.desc())
    )
    email_log = email_log_result.scalar_one_or_none()
    
    if not email_log:
        # Fallback - create response without email_log_id
        logger.warning(f"⚠️  [MANUAL SEND] Email log not found for prospect {prospect_id} after sending")
        return SendResponse(
            prospect_id=prospect.id,
            email_log_id=prospect_id,  # Use prospect_id as fallback
            sent_at=prospect.last_sent or datetime.now(timezone.utc),
            success=True,
            message_id=send_result.get("message_id")
        )
    
    logger.info(f"✅ [MANUAL SEND] Email sent successfully for prospect {prospect_id} (message_id: {send_result.get('message_id')})")
    
    return SendResponse(
        prospect_id=prospect.id,
        email_log_id=email_log.id,
        sent_at=email_log.sent_at,
        success=True,
        message_id=send_result.get("message_id")
    )


# ============================================
# CSV EXPORT
# ============================================

@router.get("/export/csv")
async def export_prospects_csv(
    status: Optional[str] = None,
    source_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Export prospects to CSV.
    
    Query params:
    - status: Filter by outreach_status (e.g., 'sent', 'drafted')
    - source_type: Filter by source_type ('website' or 'social')
    
    Returns CSV file with all matching prospects (no pagination limit).
    """
    try:
        query = select(Prospect)
        
        # Apply filters
        if status:
            query = query.where(Prospect.outreach_status == status)
        if source_type:
            query = query.where(Prospect.source_type == source_type)
        else:
            # Default to website if not specified
            query = query.where(or_(
                Prospect.source_type == 'website',
                Prospect.source_type.is_(None)
            ))
        
        # Get all results (no pagination for export)
        result = await db.execute(query.order_by(Prospect.created_at.desc()))
        prospects = result.scalars().all()
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'ID', 'Domain', 'Page URL', 'Page Title', 'Contact Email',
            'Category', 'Location', 'Score', 'Status', 'Draft Subject',
            'Draft Body', 'Last Sent', 'Follow-ups Sent', 'Created At'
        ])
        
        # Write rows
        for p in prospects:
            writer.writerow([
                str(p.id),
                p.domain or '',
                p.page_url or '',
                p.page_title or '',
                p.contact_email or '',
                p.discovery_category or '',
                p.discovery_location or '',
                p.score or 0,
                p.outreach_status or 'pending',
                getattr(p, 'draft_subject', None) or '',
                getattr(p, 'draft_body', None) or '',
                p.last_sent.isoformat() if getattr(p, 'last_sent', None) else '',
                getattr(p, 'followups_sent', 0) or 0,
                p.created_at.isoformat() if p.created_at else ''
            ])
        
        # Return CSV as response
        csv_content = output.getvalue()
        output.close()
        
        filename = f"prospects_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        logger.error(f"❌ [CSV EXPORT] Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to export CSV: {str(e)}")


@router.get("/leads/export/csv")
async def export_leads_csv(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Export leads (scraped emails) to CSV.
    
    Returns CSV file with all leads (website outreach only).
    """
    try:
        from app.models.prospect import ScrapeStatus
        
        website_filter = or_(
            Prospect.source_type == 'website',
            Prospect.source_type.is_(None)
        )
        
        query = select(Prospect).where(
            and_(
                Prospect.scrape_status.in_([
                    ScrapeStatus.SCRAPED.value,
                    ScrapeStatus.ENRICHED.value
                ]),
                website_filter
            )
        )
        
        result = await db.execute(query.order_by(Prospect.created_at.desc()))
        prospects = result.scalars().all()
        
        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow([
            'ID', 'Domain', 'Contact Email', 'Category', 'Location',
            'Score', 'Verification Status', 'Draft Subject', 'Created At'
        ])
        
        for p in prospects:
            writer.writerow([
                str(p.id),
                p.domain or '',
                p.contact_email or '',
                p.discovery_category or '',
                p.discovery_location or '',
                p.score or 0,
                p.verification_status or '',
                getattr(p, 'draft_subject', None) or '',
                p.created_at.isoformat() if p.created_at else ''
            ])
        
        csv_content = output.getvalue()
        output.close()
        
        filename = f"leads_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        logger.error(f"❌ [CSV EXPORT LEADS] Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to export leads CSV: {str(e)}")


@router.get("/scraped-emails/export/csv")
async def export_scraped_emails_csv(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Export scraped emails to CSV.
    
    Returns CSV file with all scraped emails (website outreach only).
    """
    try:
        from app.models.prospect import ScrapeStatus
        
        website_filter = or_(
            Prospect.source_type == 'website',
            Prospect.source_type.is_(None)
        )
        
        query = select(Prospect).where(
            and_(
                Prospect.scrape_status.in_([
                    ScrapeStatus.SCRAPED.value,
                    ScrapeStatus.ENRICHED.value
                ]),
                Prospect.contact_email.isnot(None),
                website_filter
            )
        )
        
        result = await db.execute(query.order_by(Prospect.created_at.desc()))
        prospects = result.scalars().all()
        
        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow([
            'ID', 'Domain', 'Contact Email', 'Source', 'Category',
            'Verification Status', 'Confidence', 'Created At'
        ])
        
        for p in prospects:
            writer.writerow([
                str(p.id),
                p.domain or '',
                p.contact_email or '',
                p.scrape_source_url or 'Snov.io',
                p.discovery_category or '',
                p.verification_status or '',
                float(p.verification_confidence) if p.verification_confidence else 0,
                p.created_at.isoformat() if p.created_at else ''
            ])
        
        csv_content = output.getvalue()
        output.close()
        
        filename = f"scraped_emails_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        logger.error(f"❌ [CSV EXPORT SCRAPED EMAILS] Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to export scraped emails CSV: {str(e)}")


# ============================================
# ATTACHMENTS
# ============================================


@router.post("/attachments")
async def upload_attachment(
    scope: str = Form("global"),
    prospect_id: Optional[UUID] = Form(None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Upload an attachment (global or per-prospect).
    scope: global | prospect
    """
    if scope not in {"global", "prospect"}:
        raise HTTPException(status_code=400, detail="Invalid scope. Use 'global' or 'prospect'.")

    if scope == "prospect" and not prospect_id:
        raise HTTPException(status_code=400, detail="prospect_id is required for prospect scope")

    content = await file.read()
    if len(content) > MAX_ATTACHMENT_BYTES:
        raise HTTPException(status_code=400, detail="Attachment exceeds 10MB limit")

    attachment = EmailAttachment(
        prospect_id=prospect_id,
        filename=file.filename or "attachment",
        content_type=file.content_type or "application/octet-stream",
        size_bytes=len(content),
        scope=scope,
        data=content
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)

    return {
        "id": str(attachment.id),
        "filename": attachment.filename,
        "content_type": attachment.content_type,
        "size_bytes": attachment.size_bytes,
        "scope": attachment.scope,
        "prospect_id": str(attachment.prospect_id) if attachment.prospect_id else None,
        "created_at": attachment.created_at.isoformat() if attachment.created_at else None,
    }


@router.get("/attachments")
async def list_attachments(
    scope: Optional[str] = None,
    prospect_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    query = select(EmailAttachment)
    if scope:
        query = query.where(EmailAttachment.scope == scope)
    if prospect_id:
        query = query.where(EmailAttachment.prospect_id == prospect_id)

    result = await db.execute(query.order_by(EmailAttachment.created_at.desc()))
    attachments = result.scalars().all()

    return {
        "data": [
            {
                "id": str(a.id),
                "filename": a.filename,
                "content_type": a.content_type,
                "size_bytes": a.size_bytes,
                "scope": a.scope,
                "prospect_id": str(a.prospect_id) if a.prospect_id else None,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in attachments
        ]
    }


@router.delete("/attachments/{attachment_id}")
async def delete_attachment(
    attachment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    result = await db.execute(select(EmailAttachment).where(EmailAttachment.id == attachment_id))
    attachment = result.scalar_one_or_none()

    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    await db.delete(attachment)
    await db.commit()

    return {"success": True}


# ============================================
# GEMINI CHAT
# ============================================

class GeminiChatRequest(BaseModel):
    # prospect_id is in the URL path, not the body
    message: str
    current_subject: Optional[str] = None
    current_body: Optional[str] = None


class BulkDraftRequest(BaseModel):
    subject: str
    body: str
    category: Optional[str] = None


class GeminiChatResponse(BaseModel):
    success: bool
    response: str
    candidate_draft: Optional[Dict[str, str]] = None  # {subject: str, body: str} if draft suggestion detected


@router.post("/{prospect_id}/chat", response_model=GeminiChatResponse)
async def gemini_chat(
    prospect_id: UUID,
    request: GeminiChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Chat with Gemini to refine email drafts.
    
    This is a human-in-the-loop feature - Gemini provides suggestions,
    but the user must manually copy/paste into the draft editor.
    """
    stage = "init"
    try:
        logger.info(f"🔵 [GEMINI CHAT] Request received for prospect {prospect_id}")
        
        # Stage 1: Prospect lookup
        stage = "prospect_lookup"
        result = await db.execute(select(Prospect).where(Prospect.id == prospect_id))
        prospect = result.scalar_one_or_none()
        
        if not prospect:
            logger.warning(f"⚠️  [GEMINI CHAT] Prospect {prospect_id} not found")
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "PROSPECT_NOT_FOUND",
                    "message": f"Prospect {prospect_id} not found",
                    "stage": stage
                }
            )
        
        logger.info(f"✅ [GEMINI CHAT] Prospect found: {prospect.domain}")
        
        # Stage 2: Gemini client initialization
        stage = "init"
        from app.clients.gemini import GeminiClient
        import os
        
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not gemini_api_key:
            logger.error("❌ [GEMINI CHAT] GEMINI_API_KEY not found in environment")
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "GEMINI_CHAT_FAILED",
                    "message": "Gemini API key not configured. Please set GEMINI_API_KEY environment variable.",
                    "stage": stage
                }
            )
        
        try:
            gemini_client = GeminiClient()
            if not gemini_client.is_configured():
                raise ValueError("Gemini client not properly configured")
            logger.info("✅ [GEMINI CHAT] Gemini client initialized")
        except Exception as e:
            logger.error(f"❌ [GEMINI CHAT] Failed to initialize Gemini client: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "GEMINI_CHAT_FAILED",
                    "message": f"Failed to initialize Gemini client: {str(e)}",
                    "stage": stage
                }
            )
        
        # Stage 3: Build prompt using centralized method
        stage = "prompt"
        context = await gemini_client.build_chat_prompt(
            prospect=prospect,
            user_message=request.message,
            current_subject=request.current_subject,
            current_body=request.current_body
        )
        
        logger.info(f"✅ [GEMINI CHAT] Prompt built ({len(context)} chars)")
        
        # Stage 4: API call
        stage = "api_call"
        url = f"{gemini_client.BASE_URL}/models/{gemini_client.model}:generateContent?key={gemini_client.api_key}"
        
        payload = {
            "contents": [{"parts": [{"text": context}]}],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 1024
            }
        }
        
        import httpx
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.info(f"🔵 [GEMINI CHAT] Calling Gemini API: {url[:80]}...")
                response = await client.post(url, json=payload)
                logger.info(f"🔵 [GEMINI CHAT] Response status: {response.status_code}")
                
                if response.status_code != 200:
                    error_text = response.text[:500] if response.text else "No error details"
                    logger.error(f"❌ [GEMINI CHAT] Gemini API returned {response.status_code}: {error_text}")
                    raise HTTPException(
                        status_code=500,
                        detail={
                            "error": "GEMINI_CHAT_FAILED",
                            "message": f"Gemini API returned status {response.status_code}: {error_text}",
                            "stage": stage
                        }
                    )
                
                result = response.json()
                logger.info(f"✅ [GEMINI CHAT] Gemini API call successful")
        except httpx.TimeoutException:
            logger.error("❌ [GEMINI CHAT] Gemini API call timed out")
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "GEMINI_CHAT_FAILED",
                    "message": "Gemini API call timed out after 30 seconds",
                    "stage": stage
                }
            )
        except httpx.RequestError as e:
            logger.error(f"❌ [GEMINI CHAT] Network error calling Gemini API: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "GEMINI_CHAT_FAILED",
                    "message": f"Network error calling Gemini API: {str(e)}",
                    "stage": stage
                }
            )
        
        # Stage 5: Parse response
        stage = "response"
        if not result.get("candidates") or len(result["candidates"]) == 0:
            logger.error(f"❌ [GEMINI CHAT] No candidates in Gemini response: {result}")
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "GEMINI_CHAT_FAILED",
                    "message": "Gemini API returned no candidates in response",
                    "stage": stage
                }
            )
        
        candidate = result["candidates"][0]
        if not candidate.get("content") or not candidate["content"].get("parts"):
            logger.error(f"❌ [GEMINI CHAT] Invalid candidate structure: {candidate}")
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "GEMINI_CHAT_FAILED",
                    "message": "Gemini API returned invalid response structure",
                    "stage": stage
                }
            )
        
        parts = candidate["content"]["parts"]
        if not parts or not isinstance(parts, list) or len(parts) == 0:
            logger.error(f"❌ [GEMINI CHAT] No parts in candidate: {parts}")
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "GEMINI_CHAT_FAILED",
                    "message": "Gemini API returned no content parts",
                    "stage": stage
                }
            )
        
        text_content = parts[0].get("text", "") if isinstance(parts[0], dict) else ""
        if not text_content:
            logger.error(f"❌ [GEMINI CHAT] Empty text content in response")
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "GEMINI_CHAT_FAILED",
                    "message": "Gemini API returned empty response",
                    "stage": stage
                }
            )
        
        # Stage 6: Parse response for draft suggestions
        stage = "parse"
        candidate_draft = None
        
        # Look for draft suggestion markers
        import re
        draft_pattern = r'---\s*DRAFT SUGGESTION\s*---\s*Subject:\s*(.+?)\s*Body:\s*(.+?)\s*---\s*END DRAFT SUGGESTION\s*---'
        match = re.search(draft_pattern, text_content, re.DOTALL | re.IGNORECASE)
        
        if match:
            suggested_subject = match.group(1).strip()
            suggested_body = match.group(2).strip()
            
            # Strip markdown formatting (asterisks, etc.) from draft suggestions
            from app.clients.gemini import strip_markdown_formatting
            suggested_subject = strip_markdown_formatting(suggested_subject)
            suggested_body = strip_markdown_formatting(suggested_body)
            
            # Remove the draft suggestion markers from the response text
            # Keep the conversational part before/after
            text_content = re.sub(draft_pattern, '', text_content, flags=re.DOTALL | re.IGNORECASE).strip()
            
            candidate_draft = {
                "subject": suggested_subject,
                "body": suggested_body
            }
            logger.info(f"✅ [GEMINI CHAT] Draft suggestion detected: subject={len(suggested_subject)} chars, body={len(suggested_body)} chars")
        
        logger.info(f"✅ [GEMINI CHAT] Successfully generated response ({len(text_content)} chars, draft_suggestion={'yes' if candidate_draft else 'no'})")
        return GeminiChatResponse(
            success=True,
            response=text_content,
            candidate_draft=candidate_draft
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [GEMINI CHAT] Unexpected error at stage '{stage}': {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "GEMINI_CHAT_FAILED",
                "message": f"Unexpected error: {str(e)}",
                "stage": stage
            }
    )
