"""
Health check endpoints

Includes schema validation endpoint to verify ORM matches database.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine
from sqlalchemy import text
from app.db.database import get_db, engine, Base
from app.utils.schema_validator import validate_prospect_schema
from typing import Dict, Any
import logging
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health_check():
    """Basic health check"""
    return {"status": "ok"}


@router.get("/schema")
async def schema_health_check():
    """
    Schema validation health check
    
    Verifies that ORM models match database schema.
    Returns 500 if mismatch detected (prevents silent failures).
    """
    try:
        is_valid, missing_columns = await validate_prospect_schema(engine, Base)
        
        if not is_valid:
            logger.error(f"❌ Schema mismatch detected: Missing columns {missing_columns}")
            raise HTTPException(
                status_code=500,
                detail=f"Schema mismatch: Missing columns {missing_columns}. Run migrations."
            )
        
        # Also check total prospects count
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT COUNT(*) FROM prospects"))
            total_prospects = result.scalar() or 0
        
        return {
            "status": "ok",
            "schema_valid": True,
            "total_prospects": total_prospects,
            "message": "ORM model matches database schema"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Schema health check failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Schema health check failed: {str(e)}"
        )


@router.get("/gmail")
async def gmail_health_check():
    """
    Gmail configuration health check
    
    Checks if Gmail API credentials are configured.
    Returns status and configuration details (without exposing secrets).
    Optionally tests token refresh if refresh_token is configured.
    """
    logger.info("🔍 Checking Gmail configuration...")
    
    access_token = os.getenv("GMAIL_ACCESS_TOKEN")
    refresh_token = os.getenv("GMAIL_REFRESH_TOKEN")
    client_id = os.getenv("GMAIL_CLIENT_ID")
    client_secret = os.getenv("GMAIL_CLIENT_SECRET")
    
    has_access_token = bool(access_token)
    has_refresh_token = bool(refresh_token)
    has_client_id = bool(client_id)
    has_client_secret = bool(client_secret)
    
    # Check if we have minimum required credentials
    is_configured = has_access_token or (has_refresh_token and has_client_id and has_client_secret)
    
    status = "configured" if is_configured else "not_configured"
    
    details = {
        "status": status,
        "has_access_token": has_access_token,
        "has_refresh_token": has_refresh_token,
        "has_client_id": has_client_id,
        "has_client_secret": has_client_secret,
    }
    
    # Test token refresh if refresh_token is configured
    if has_refresh_token and has_client_id and has_client_secret:
        try:
            from app.clients.gmail import GmailClient
            gmail_client = GmailClient()
            token_refresh_success = await gmail_client.refresh_access_token()
            details["token_refresh_test"] = "success" if token_refresh_success else "failed"
            if token_refresh_success:
                details["message"] = "Gmail is configured and token refresh works. Ready to send emails."
            else:
                details["message"] = "Gmail credentials are set, but token refresh failed. Check refresh token validity."
                details["troubleshooting"] = (
                    "Token refresh failed. Possible causes:\n"
                    "1. Refresh token expired or revoked - generate a new one\n"
                    "2. OAuth consent screen not configured correctly\n"
                    "3. Required Gmail API scopes not granted\n"
                    "4. Client ID/Secret mismatch"
                )
        except Exception as e:
            details["token_refresh_test"] = "error"
            details["token_refresh_error"] = str(e)
            details["message"] = f"Gmail credentials are set, but initialization failed: {str(e)}"
    elif not is_configured:
        details["message"] = (
            "Gmail is not configured. To enable email sending, set one of the following:\n"
            "Option 1: Set GMAIL_ACCESS_TOKEN (temporary, expires)\n"
            "Option 2: Set GMAIL_REFRESH_TOKEN, GMAIL_CLIENT_ID, and GMAIL_CLIENT_SECRET (recommended, auto-refreshes)"
        )
        details["instructions"] = {
            "option_1": "Set GMAIL_ACCESS_TOKEN environment variable",
            "option_2": "Set GMAIL_REFRESH_TOKEN, GMAIL_CLIENT_ID, and GMAIL_CLIENT_SECRET environment variables"
        }
    else:
        details["message"] = "Gmail is configured and ready to send emails."
        if has_refresh_token:
            details["auth_method"] = "refresh_token (recommended - auto-refreshes)"
        else:
            details["auth_method"] = "access_token (may expire)"
    
    logger.info(f"📧 Gmail configuration check: {status}")
    
    return details

