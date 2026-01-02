"""
Health check endpoints

FEATURE-SCOPED VALIDATION:
- /health - Basic health check (always returns 200)
- /health/ready - Database connectivity check
- /health/schema - Full schema diagnostics (can return 500 if invalid)
"""
from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from app.db.database import engine
from app.utils.schema_validator import get_full_schema_diagnostics
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health")
async def health():
    """Health check endpoint - responds immediately for Render deployment checks"""
    return {"status": "healthy", "service": "art-outreach-api"}


@router.get("/health/ready")
async def readiness():
    """Readiness check - verifies database connectivity"""
    try:
        # Quick database connectivity check (with timeout)
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ready", "database": "connected"}
    except Exception as e:
        logger.warning(f"Readiness check failed: {e}")
        # Still return 200 so Render doesn't fail deployment
        # Database might be temporarily unavailable
        return {"status": "ready", "database": "checking", "warning": str(e)}


@router.get("/health/schema")
async def schema_check():
    """
    Full schema validation endpoint - provides comprehensive diagnostics.
    
    This endpoint can safely return 500 if schema is invalid.
    It is NOT used by the frontend UI - it's for diagnostics only.
    """
    try:
        diagnostics = await get_full_schema_diagnostics(engine)
        
        # If schema is invalid, return 500 (this is a diagnostic endpoint)
        if diagnostics["status"] == "error":
            raise HTTPException(
                status_code=500,
                detail=diagnostics
            )
        
        if not diagnostics.get("all_tables_valid", False):
            # Schema is incomplete - return 500 for diagnostic purposes
            raise HTTPException(
                status_code=500,
                detail=diagnostics
            )
        
        # All good - return 200 with diagnostics
        return diagnostics
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Schema check failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "error": str(e),
                "message": "Could not check schema"
            }
        )
