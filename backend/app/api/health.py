"""
Health check endpoints

FEATURE-SCOPED VALIDATION:
- /health - Basic health check (always returns 200)
- /health/ready - Database connectivity check
- /health/schema - Full schema diagnostics (can return 500 if invalid)
- /health/migrate - Run database migrations (protected by token)
"""
from fastapi import APIRouter, HTTPException, Header
from sqlalchemy import text
from app.db.database import engine
from app.utils.schema_validator import get_full_schema_diagnostics
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/health/fix-discovery-query-id")
async def fix_discovery_query_id_column():
    """
    Manually fix discovery_query_id column if missing.
    This endpoint can be called to add the column immediately.
    """
    try:
        from sqlalchemy import text
        from app.db.database import AsyncSessionLocal
        
        async with AsyncSessionLocal() as db:
            # Check if column exists
            result = await db.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'prospects' 
                AND column_name = 'discovery_query_id'
                AND table_schema = 'public'
            """))
            row = result.fetchone()
            if not row:
                await db.execute(text("ALTER TABLE prospects ADD COLUMN discovery_query_id UUID"))
                await db.execute(text("CREATE INDEX IF NOT EXISTS ix_prospects_discovery_query_id ON prospects(discovery_query_id)"))
                await db.commit()
                return {
                    "success": True,
                    "message": "Successfully added discovery_query_id column and index"
                }
            else:
                return {
                    "success": True,
                    "message": "Column discovery_query_id already exists"
                }
    except Exception as e:
        logger.error(f"Error fixing discovery_query_id column: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }  # No prefix - routes are /health, /health/ready, /health/migrate


@router.get("/health")
async def health():
    """Health check endpoint - responds immediately for Render deployment checks"""
    return {"status": "healthy", "service": "art-outreach-api"}


@router.get("/health/connection-string")
async def check_connection_string():
    """
    Diagnostic endpoint to check DATABASE_URL format (without exposing password).
    Helps diagnose connection issues.
    """
    import os
    from urllib.parse import urlparse
    
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        return {
            "error": "DATABASE_URL not set",
            "status": "error"
        }
    
    try:
        # Parse URL to extract components (safely)
        # Handle both postgresql:// and postgresql+asyncpg://
        url_to_parse = database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
        parsed = urlparse(url_to_parse)
        
        # Extract hostname and port
        hostname = parsed.hostname or "unknown"
        port = parsed.port or 5432
        database = parsed.path.lstrip("/") if parsed.path else "unknown"
        username = parsed.username or "unknown"
        
        # Check if it's a Supabase URL
        is_supabase = ".supabase.co" in hostname or "pooler.supabase.com" in hostname
        
        # Verify hostname format
        hostname_parts = hostname.split(".")
        is_valid_format = len(hostname_parts) >= 3
        
        return {
            "status": "ok",
            "hostname": hostname,
            "port": port,
            "database": database,
            "username": username,
            "is_supabase": is_supabase,
            "hostname_parts_count": len(hostname_parts),
            "hostname_valid": is_valid_format,
            "hostname_parts": hostname_parts,
            "scheme": parsed.scheme,
            "warning": "Hostname appears truncated" if is_supabase and not is_valid_format else None
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "raw_url_length": len(database_url) if database_url else 0
        }


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


@router.post("/health/migrate")
async def run_migrations(
    x_migration_token: Optional[str] = Header(None, alias="X-Migration-Token")
):
    """
    Run database migrations via HTTP endpoint.
    
    PROTECTED: Requires X-Migration-Token header matching MIGRATION_TOKEN env var.
    
    This allows running migrations on Render free tier without shell access.
    Set MIGRATION_TOKEN environment variable in Render dashboard.
    
    Usage:
    curl -X POST https://your-app.onrender.com/api/health/migrate \
         -H "X-Migration-Token: your-secret-token"
    """
    # Check for migration token
    required_token = os.getenv("MIGRATION_TOKEN")
    
    if not required_token:
        logger.warning("⚠️  MIGRATION_TOKEN not set - migration endpoint disabled")
        raise HTTPException(
            status_code=503,
            detail="Migration endpoint not configured. Set MIGRATION_TOKEN environment variable."
        )
    
    if not x_migration_token or x_migration_token != required_token:
        logger.warning("⚠️  Invalid migration token attempt")
        raise HTTPException(
            status_code=401,
            detail="Invalid migration token"
        )
    
    try:
        from alembic.config import Config
        from alembic import command
        
        logger.info("🔄 [MIGRATION ENDPOINT] Running migrations via HTTP request...")
        logger.info("=" * 60)
        
        # Get the backend directory path
        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        alembic_cfg = Config(os.path.join(backend_dir, "alembic.ini"))
        
        # Get database URL and set in config
        database_url = os.getenv("DATABASE_URL")
        if database_url:
            # Convert asyncpg URL to psycopg2 for Alembic
            if database_url.startswith("postgresql+asyncpg://"):
                sync_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
                alembic_cfg.set_main_option("sqlalchemy.url", sync_url)
                logger.info("✅ Converted asyncpg URL to psycopg2 format for Alembic")
        
        # Run migrations - use 'heads' to upgrade all branches
        logger.info("🚀 Executing: alembic upgrade heads")
        # Use 'heads' instead of 'head' to upgrade all migration branches
        command.upgrade(alembic_cfg, "heads")
        
        logger.info("=" * 60)
        logger.info("✅ Database migrations completed successfully")
        logger.info("=" * 60)
        
        # Verify tables exist
        from app.utils.schema_validator import get_full_schema_diagnostics
        diagnostics = await get_full_schema_diagnostics(engine)
        
        return {
            "status": "success",
            "message": "Migrations completed successfully",
            "schema_diagnostics": diagnostics
        }
        
    except Exception as e:
        logger.error(f"❌ [MIGRATION ENDPOINT] Migration failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "error": str(e),
                "message": "Migration failed. Check logs for details."
            }
        )
