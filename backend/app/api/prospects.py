"""
Prospect management API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from typing import List, Optional, Dict
from uuid import UUID
import os
from dotenv import load_dotenv
import logging

from app.db.database import get_db
from app.api.auth import get_current_user_optional
from app.utils.email_validation import format_job_error

logger = logging.getLogger(__name__)
from app.models.prospect import Prospect
from app.models.job import Job
from app.schemas.prospect import (
    ProspectResponse,
    ProspectListResponse,
    ComposeRequest,
    ComposeResponse,
    SendRequest,
    SendResponse
)

load_dotenv()

router = APIRouter()


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
                "source": result.get("source") if isinstance(result, dict) else "hunter_io",
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
            "source": result.get("source", "hunter_io"),
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
            "source": "hunter_io",
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
        
        # Enrich using domain and page_url (if available)
        from app.services.enrichment import enrich_prospect_email
        enrich_result = await enrich_prospect_email(prospect.domain, None, prospect.page_url)
        
        if enrich_result and enrich_result.get("email"):
            # Update prospect with email
            prospect.contact_email = enrich_result["email"]
            prospect.contact_method = enrich_result.get("source", "snov_io")
            prospect.snov_payload = enrich_result  # Use snov_payload instead of hunter_payload
            await db.commit()
            await db.refresh(prospect)
            
            return {
                "success": True,
                "email": enrich_result["email"],
                "name": enrich_result.get("name"),
                "company": enrich_result.get("company"),
                "confidence": enrich_result.get("confidence"),
                "domain": prospect.domain,
                "source": enrich_result.get("source", "hunter_io"),
                "message": f"Email enriched for {prospect.domain}"
            }
        else:
            # No email found, but update snov_payload for retry
            if enrich_result:
                prospect.snov_payload = enrich_result
                await db.commit()
            
            return {
                "success": False,
                "email": None,
                "name": None,
                "company": None,
                "confidence": None,
                "domain": prospect.domain,
                "source": None,
                "message": f"No email found for {prospect.domain}. Will retry later."
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


@router.post("/enrich")
async def create_enrichment_job(
    prospect_ids: Optional[List[UUID]] = None,
    max_prospects: int = 100,
    only_missing_emails: bool = False,  # New parameter: only enrich prospects without emails
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Create a new enrichment job to find emails for prospects
    
    Query params:
    - prospect_ids: Optional list of specific prospect IDs to enrich
    - max_prospects: Maximum number of prospects to enrich (if no IDs specified)
    - only_missing_emails: If True, only enrich prospects that don't have emails yet (prioritizes existing prospects without emails)
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
    # Create job record
    job = Job(
        job_type="enrich",
        params={
            "prospect_ids": [str(pid) for pid in prospect_ids] if prospect_ids else None,
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
            raise HTTPException(
                status_code=500,
                detail="System error: Unable to start enrichment job due to code issue. Please contact support."
            )
        except ImportError as import_err:
            logger.error(f"❌ Import error for enrichment task: {import_err}", exc_info=True)
            job.status = "failed"
            job.error_message = "System error: Module import failed. Please contact support."
            await db.commit()
            await db.refresh(job)
            raise HTTPException(
                status_code=500,
                detail="System error: Unable to import enrichment task module. Please contact support."
            )
        
        asyncio.create_task(process_enrichment_job(str(job.id)))
        logger.info(f"✅ Enrichment job {job.id} started in background")
    except HTTPException:
        # Re-raise HTTP exceptions (already handled above)
        raise
    except Exception as e:
        logger.error(f"❌ Failed to start enrichment job {job.id}: {e}", exc_info=True)
        job.status = "failed"
        # Use helper to format error message
        job.error_message = format_job_error(e)
        await db.commit()
        await db.refresh(job)
        return {
            "job_id": job.id,
            "status": "failed",
            "error": job.error_message
        }
    
    return {
        "job_id": job.id,
        "status": "pending",
        "message": f"Enrichment job {job.id} started successfully"
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
    Returns: { data: Prospect[], page, limit, total, totalPages }
    """
    # Enforce max limit of 10
    limit = max(1, min(limit, 10))
    
    # Call list_prospects with page-based pagination
    result = await list_prospects(
        skip=None,
        limit=limit,
        page=page,
        status=None,
        min_score=None,
        has_email=None,
        db=db,
        current_user=current_user
    )
    
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


@router.get("")
async def list_prospects(
    skip: Optional[int] = None,
    limit: int = 50,
    page: Optional[int] = None,  # New page-based pagination
    status: Optional[str] = None,
    min_score: Optional[float] = None,
    has_email: Optional[str] = None,  # Changed to str to handle string "true"/"false" from frontend
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
        # DEBUG: Log incoming parameters
        logger.info(f"🔍 GET /api/prospects - skip={skip}, limit={limit}, status={status}, min_score={min_score}, has_email={has_email} (type: {type(has_email)})")
        
        # Parse pagination (support both page-based and skip-based)
        try:
            # Default: page=1, limit=10, max limit=10
            if page is not None:
                # Page-based pagination (1-based)
                page = max(1, int(page))
            else:
                # Default: page 1
                page = 1
            
            # Enforce max limit of 10
            limit = int(limit) if limit is not None else 10
            limit = max(1, min(limit, 10))  # Enforce 1-10 range
            
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
        except Exception as e:
            logger.error(f"🔴 Error building query filters: {e}", exc_info=True)
            response_data["error"] = f"Error building query: {str(e)}"
            response_data["data"] = {"data": [], "prospects": [], "total": 0, "page": page, "totalPages": 0, "skip": skip, "limit": limit}
            return response_data
        
        logger.info(f"🔍 Query filters applied successfully")
        
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
            error_str = str(db_err).lower()
            if "discovery_query_id" in error_str and ("column" in error_str or "does not exist" in error_str):
                logger.error(f"🔴 Database schema error: discovery_query_id column missing")
                response_data["error"] = "Database schema mismatch: 'discovery_query_id' column missing. Migration needs to be applied."
            else:
                response_data["error"] = f"Database error: {str(db_err)}"
            total_pages = (total + limit - 1) // limit if total > 0 else 0
            response_data["data"] = {"data": [], "prospects": [], "total": total, "page": page, "totalPages": total_pages, "skip": skip, "limit": limit}
            return response_data
        
        # Convert to response models
        logger.info(f"🔍 Converting {len(prospects)} prospects to response format...")
        prospect_responses = []
        for idx, p in enumerate(prospects):
            try:
                prospect_responses.append(ProspectResponse.model_validate(p))
            except Exception as e:
                logger.error(f"🔴 Error validating prospect {idx+1}/{len(prospects)} (id={getattr(p, 'id', 'unknown')}): {e}", exc_info=True)
                # Continue processing other prospects instead of failing completely
                continue
        
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
        response_data["error"] = f"Internal server error: {str(err)}"
        total_pages = 0
        page = 1
        skip = 0
        limit = 10
        response_data["data"] = {"data": [], "prospects": [], "total": 0, "page": page, "totalPages": total_pages, "skip": skip, "limit": limit}
        return response_data


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
    
    return ProspectResponse.model_validate(prospect)


@router.post("/{prospect_id}/compose", response_model=ComposeResponse)
async def compose_email(
    prospect_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Compose an email for a prospect using Gemini
    
    This will:
    1. Fetch prospect details
    2. Call Gemini API to generate email
    3. Save draft to prospect record
    """
    result = await db.execute(select(Prospect).where(Prospect.id == prospect_id))
    prospect = result.scalar_one_or_none()
    
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")
    
    # Import Gemini client
    try:
        from app.clients.gemini import GeminiClient
        client = GeminiClient()
    except ImportError as e:
        logger.error(f"Failed to import GeminiClient: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Gemini client not available: {str(e)}")
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"Gemini API not configured: {str(e)}")
    
    # Extract snippet from DataForSEO payload (safe None check)
    page_snippet = None
    if prospect.dataforseo_payload and isinstance(prospect.dataforseo_payload, dict):
        page_snippet = prospect.dataforseo_payload.get("description") or prospect.dataforseo_payload.get("snippet")
    
    # Extract contact name from Hunter.io payload (safe list access)
    contact_name = None
    if prospect.hunter_payload and isinstance(prospect.hunter_payload, dict):
        emails = prospect.hunter_payload.get("emails", [])
        if emails and isinstance(emails, list) and len(emails) > 0:
            first_email = emails[0]
            if isinstance(first_email, dict):
                first_name = first_email.get("first_name")
                last_name = first_email.get("last_name")
                if first_name or last_name:
                    contact_name = f"{first_name or ''} {last_name or ''}".strip()
    
    # Call Gemini to compose email (use await, not asyncio.run in async function)
    gemini_result = await client.compose_email(
        domain=prospect.domain,
        page_title=prospect.page_title,
        page_url=prospect.page_url,
        page_snippet=page_snippet,
        contact_name=contact_name
    )
    
    if not gemini_result.get("success"):
        error = gemini_result.get("error", "Unknown error")
        raise HTTPException(status_code=500, detail=f"Failed to compose email: {error}")
    
    # Save draft to prospect
    prospect.draft_subject = gemini_result.get("subject")
    prospect.draft_body = gemini_result.get("body")
    
    await db.commit()
    await db.refresh(prospect)
    
    return ComposeResponse(
        prospect_id=prospect.id,
        subject=prospect.draft_subject,
        body=prospect.draft_body,
        draft_saved=True
    )


@router.post("/{prospect_id}/send", response_model=SendResponse)
async def send_email(
    prospect_id: UUID,
    request: SendRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Send an email to a prospect via Gmail API
    
    This will:
    1. Fetch prospect details
    2. Use provided subject/body or draft
    3. Send via Gmail API (will be implemented in Phase 6)
    4. Create email log entry
    5. Update prospect status
    """
    result = await db.execute(select(Prospect).where(Prospect.id == prospect_id))
    prospect = result.scalar_one_or_none()
    
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")
    
    if not prospect.contact_email:
        raise HTTPException(status_code=400, detail="Prospect has no contact email")
    
    # Use draft if subject/body not provided
    subject = request.subject or prospect.draft_subject
    body = request.body or prospect.draft_body
    
    if not subject or not body:
        raise HTTPException(
            status_code=400,
            detail="Email subject and body required. Either provide in request or compose email first."
        )
    
    # Send email via Gmail API
    from datetime import datetime
    from app.models.email_log import EmailLog
    import asyncio
    
    try:
        from app.clients.gmail import GmailClient
        gmail_client = GmailClient()
    except ImportError as e:
        logger.error(f"Failed to import GmailClient: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Gmail client not available: {str(e)}")
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"Gmail not configured: {str(e)}")
    
    # Send email
    send_result = asyncio.run(gmail_client.send_email(
        to_email=prospect.contact_email,
        subject=subject,
        body=body
    ))
    
    if not send_result.get("success"):
        error = send_result.get("error", "Unknown error")
        raise HTTPException(status_code=500, detail=f"Failed to send email: {error}")
    
    # Create email log entry
    email_log = EmailLog(
        prospect_id=prospect.id,
        subject=subject,
        body=body,
        response=send_result
    )
    db.add(email_log)
    
    # Update prospect
    prospect.outreach_status = "sent"
    prospect.last_sent = datetime.utcnow()
    
    await db.commit()
    await db.refresh(email_log)
    
    return SendResponse(
        prospect_id=prospect.id,
        email_log_id=email_log.id,
        sent_at=email_log.sent_at,
        success=True,
        message_id=send_result.get("message_id")
    )
