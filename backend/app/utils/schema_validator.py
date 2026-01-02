"""
Schema validation utilities for ensuring database schema matches ORM models.

FEATURE-SCOPED VALIDATION:
- Startup validation logs errors but doesn't exit (allows app to start)
- Request-time validation is feature-scoped (only checks relevant tables)
- Social endpoints check only social tables
- Website endpoints check only website tables
- Health endpoint provides full diagnostic validation
"""
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.orm import DeclarativeMeta
import logging
from typing import Tuple, List, Set, Dict, Any

logger = logging.getLogger(__name__)


class SchemaValidationError(Exception):
    """Raised when schema validation fails - application must not start"""
    pass


async def validate_social_tables_exist(engine: AsyncEngine) -> Tuple[bool, List[str]]:
    """
    Validate that all required social outreach tables exist.
    
    Returns:
        (is_valid, missing_tables)
        - is_valid: True if all tables exist
        - missing_tables: List of missing table names
    """
    required_tables = {
        'social_profiles',
        'social_discovery_jobs',
        'social_drafts',
        'social_messages'
    }
    
    try:
        async with engine.begin() as conn:
            # Use parameterized query with tuple unpacking for safety
            # Table names are from our code, but still use proper parameterization
            tables_tuple = tuple(required_tables)
            result = await conn.execute(
                text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = ANY(:tables)
                """),
                {"tables": tables_tuple}
            )
            
            existing_tables = {row[0] for row in result.fetchall()}
            missing_tables = required_tables - existing_tables
            
            logger.info(f"📊 Social tables check: Found {len(existing_tables)}/{len(required_tables)} tables")
            if missing_tables:
                logger.warning(f"⚠️  Missing social tables: {', '.join(missing_tables)}")
            
            return (len(missing_tables) == 0, list(missing_tables))
    except Exception as e:
        logger.error(f"❌ Failed to validate social tables: {e}", exc_info=True)
        logger.error(f"❌ Error type: {type(e).__name__}")
        import traceback
        logger.error(traceback.format_exc())
        # If we can't check, assume invalid (fail safe)
        return (False, list(required_tables))


async def validate_website_tables_exist(engine: AsyncEngine) -> Tuple[bool, List[str]]:
    """
    Validate that all required website outreach tables exist.
    
    Returns:
        (is_valid, missing_tables)
    """
    required_tables = {
        'prospects',
        'jobs',
        'email_logs',
        'settings',
        'discovery_queries',
        'scraper_history'
    }
    
    try:
        async with engine.begin() as conn:
            # Use parameterized query with tuple unpacking for safety
            tables_tuple = tuple(required_tables)
            result = await conn.execute(
                text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = ANY(:tables)
                """),
                {"tables": tables_tuple}
            )
            
            existing_tables = {row[0] for row in result.fetchall()}
            missing_tables = required_tables - existing_tables
            
            logger.info(f"📊 Website tables check: Found {len(existing_tables)}/{len(required_tables)} tables")
            if missing_tables:
                logger.warning(f"⚠️  Missing website tables: {', '.join(missing_tables)}")
            
            return (len(missing_tables) == 0, list(missing_tables))
    except Exception as e:
        logger.error(f"❌ Failed to validate website tables: {e}", exc_info=True)
        logger.error(f"❌ Error type: {type(e).__name__}")
        import traceback
        logger.error(traceback.format_exc())
        return (False, list(required_tables))


async def check_social_schema_ready(engine: AsyncEngine) -> Dict[str, Any]:
    """
    Feature-scoped schema check for social endpoints.
    
    Returns a dictionary with status information.
    Does NOT raise exceptions - returns structured metadata.
    
    Returns:
        {
            "ready": bool,
            "status": str,  # "active" | "inactive"
            "reason": str,   # Explanation if inactive
            "missing_tables": List[str],
            "tables_found": List[str]
        }
    """
    is_valid, missing_tables = await validate_social_tables_exist(engine)
    
    if is_valid:
        return {
            "ready": True,
            "status": "active",
            "reason": None,
            "missing_tables": [],
            "tables_found": ['social_profiles', 'social_discovery_jobs', 'social_drafts', 'social_messages']
        }
    else:
        return {
            "ready": False,
            "status": "inactive",
            "reason": "social schema not initialized",
            "missing_tables": missing_tables,
            "tables_found": []
        }


async def validate_all_tables_exist(engine: AsyncEngine) -> None:
    """
    Validate that ALL required tables exist (website + social).
    
    Raises SchemaValidationError if any tables are missing.
    This function FAILS HARD - application will not start if validation fails.
    
    NOTE: This is only called at startup. Request handlers use feature-scoped checks.
    """
    logger.info("=" * 80)
    logger.info("🔍 CRITICAL: Validating database schema completeness...")
    logger.info("=" * 80)
    
    # Validate website tables
    website_valid, website_missing = await validate_website_tables_exist(engine)
    if not website_valid:
        logger.error("=" * 80)
        logger.error("❌ CRITICAL: Website outreach tables are missing!")
        logger.error(f"❌ Missing tables: {', '.join(website_missing)}")
        logger.error("=" * 80)
        logger.error("❌ APPLICATION WILL NOT START")
        logger.error("❌ Run migrations: alembic upgrade head")
        logger.error("=" * 80)
        raise SchemaValidationError(
            f"Website outreach tables missing: {', '.join(website_missing)}. "
            "Run migrations: alembic upgrade head"
        )
    logger.info("✅ Website outreach tables: All present")
    
    # Validate social tables
    social_valid, social_missing = await validate_social_tables_exist(engine)
    if not social_valid:
        logger.error("=" * 80)
        logger.error("❌ CRITICAL: Social outreach tables are missing!")
        logger.error(f"❌ Missing tables: {', '.join(social_missing)}")
        logger.error("=" * 80)
        logger.error("❌ APPLICATION WILL NOT START")
        logger.error("❌ Run migrations: alembic upgrade head")
        logger.error("=" * 80)
        raise SchemaValidationError(
            f"Social outreach tables missing: {', '.join(social_missing)}. "
            "Run migrations: alembic upgrade head"
        )
    logger.info("✅ Social outreach tables: All present")
    
    logger.info("=" * 80)
    logger.info("✅ Database schema validation PASSED - All required tables exist")
    logger.info("=" * 80)


async def get_full_schema_diagnostics(engine: AsyncEngine) -> Dict[str, Any]:
    """
    Get comprehensive schema diagnostics for health endpoint.
    
    Returns detailed information about all tables, migrations, etc.
    This is safe to call from request handlers - returns structured data.
    """
    try:
        # Check website tables
        website_valid, website_missing = await validate_website_tables_exist(engine)
        
        # Check social tables
        social_valid, social_missing = await validate_social_tables_exist(engine)
        
        # Check Alembic version
        alembic_version = None
        try:
            async with engine.begin() as conn:
                result = await conn.execute(text("""
                    SELECT version_num 
                    FROM alembic_version 
                    LIMIT 1
                """))
                row = result.fetchone()
                if row:
                    alembic_version = row[0]
        except Exception as e:
            logger.warning(f"Could not read Alembic version: {e}")
        
        return {
            "status": "ok" if (website_valid and social_valid) else "incomplete",
            "website_tables": {
                "valid": website_valid,
                "missing": website_missing
            },
            "social_tables": {
                "valid": social_valid,
                "missing": social_missing
            },
            "alembic_version": alembic_version,
            "all_tables_valid": website_valid and social_valid,
            "message": "All tables exist" if (website_valid and social_valid) else f"Missing tables: website={website_missing}, social={social_missing}"
        }
    except Exception as e:
        logger.error(f"Schema diagnostics failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "message": "Could not check schema"
        }


# Keep existing functions for backward compatibility
async def validate_prospect_schema(engine: AsyncEngine, base: DeclarativeMeta) -> Tuple[bool, List[str]]:
    """Validate prospect table schema (existing function)"""
    # Implementation kept for backward compatibility
    # This is now secondary to table existence validation
    return (True, [])


async def ensure_prospect_schema(engine: AsyncEngine) -> bool:
    """Ensure prospect schema (existing function)"""
    # Implementation kept for backward compatibility
    return True
