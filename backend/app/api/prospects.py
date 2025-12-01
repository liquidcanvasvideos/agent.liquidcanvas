"""
Prospect management API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from typing import List, Optional
from uuid import UUID
import os
from dotenv import load_dotenv
import logging

from app.db.database import get_db
from app.api.auth import get_current_user_optional

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
        { email: str, confidence: float, source: str } or error
    """
    import time
    start_time = time.time()
    
    logger.info(f"🔍 [ENRICHMENT API] Direct enrichment request - domain: {domain}, name: {name}")
    logger.info(f"📥 [ENRICHMENT API] Input - domain: {domain}, name: {name}")
    
    try:
        from app.services.enrichment import enrich_prospect_email
        
        result = await enrich_prospect_email(domain, name)
        
        if not result:
            api_time = (time.time() - start_time) * 1000
            logger.warning(f"⚠️  [ENRICHMENT API] No email found for {domain} after {api_time:.0f}ms")
            return {
                "success": False,
                "error": f"No email found for domain {domain}",
                "domain": domain
            }
        
        api_time = (time.time() - start_time) * 1000
        logger.info(f"✅ [ENRICHMENT API] Enrichment completed in {api_time:.0f}ms")
        logger.info(f"📤 [ENRICHMENT API] Output - {result}")
        
        return {
            "success": True,
            "email": result["email"],
            "confidence": result["confidence"],
            "source": result["source"],
            "domain": domain
        }
        
    except Exception as e:
        api_time = (time.time() - start_time) * 1000
        error_msg = f"Enrichment failed after {api_time:.0f}ms: {str(e)}"
        logger.error(f"❌ [ENRICHMENT API] {error_msg}", exc_info=True)
        import traceback
        return {
            "success": False,
            "error": error_msg,
            "stack_trace": traceback.format_exc(),
            "domain": domain
        }


@router.post("/enrich")
async def create_enrichment_job(
    prospect_ids: Optional[List[UUID]] = None,
    max_prospects: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new enrichment job to find emails for prospects
    
    Query params:
    - prospect_ids: Optional list of specific prospect IDs to enrich
    - max_prospects: Maximum number of prospects to enrich (if no IDs specified)
    """
    # Create job record
    job = Job(
        job_type="enrich",
        params={
            "prospect_ids": [str(pid) for pid in prospect_ids] if prospect_ids else None,
            "max_prospects": max_prospects
        },
        status="pending"
    )
    
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    # Start enrichment task in background
    try:
        from app.tasks.enrichment import process_enrichment_job
        import asyncio
        asyncio.create_task(process_enrichment_job(str(job.id)))
        logger.info(f"✅ Enrichment job {job.id} started in background")
    except Exception as e:
        logger.error(f"❌ Failed to start enrichment job {job.id}: {e}", exc_info=True)
        job.status = "failed"
        job.error_message = f"Failed to start job: {e}"
        await db.commit()
        await db.refresh(job)
        return {
            "job_id": job.id,
            "status": "failed",
            "error": str(e)
        }
    
    return {
        "job_id": job.id,
        "status": "pending",
        "message": f"Enrichment job {job.id} started successfully"
    }


@router.get("")
async def list_prospects(
    skip: int = 0,
    limit: int = 50,
    status: Optional[str] = None,
    min_score: Optional[float] = None,
    has_email: Optional[str] = None,  # Changed to str to handle string "true"/"false" from frontend
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    List prospects with filtering
    
    Query params:
    - skip: Pagination offset
    - limit: Number of results (max 200)
    - status: Filter by outreach_status
    - min_score: Minimum score threshold
    - has_email: Filter by whether prospect has email (string "true"/"false")
    
    Returns: {success: bool, data: [], error: null | string}
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
        
        # Parse skip and limit as numbers (defensive)
        try:
            skip = int(skip) if skip is not None else 0
            limit = int(limit) if limit is not None else 50
            # Enforce max limit
            limit = min(limit, 1000) if limit > 0 else 50
            logger.info(f"🔍 Parsed skip={skip} (type: {type(skip)}), limit={limit} (type: {type(limit)})")
        except (ValueError, TypeError) as e:
            logger.error(f"🔴 Error parsing skip/limit: {e}")
            response_data["error"] = f"Invalid pagination parameters: {str(e)}"
            response_data["data"] = {"prospects": [], "total": 0, "skip": 0, "limit": 50}
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
            response_data["data"] = {"prospects": [], "total": 0, "skip": skip, "limit": limit}
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
            response_data["data"] = {"prospects": [], "total": 0, "skip": skip, "limit": limit}
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
            response_data["data"] = {"prospects": [], "total": total, "skip": skip, "limit": limit}
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
            response_data["data"] = {"prospects": [], "total": total, "skip": skip, "limit": limit}
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
        
        # Build success response
        response_data["success"] = True
        response_data["data"] = {
            "prospects": prospect_responses,
            "total": total,
            "skip": skip,
            "limit": limit
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
        response_data["data"] = {"prospects": [], "total": 0, "skip": skip, "limit": limit}
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
