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

