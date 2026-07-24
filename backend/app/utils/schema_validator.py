"""
Schema validation utilities - HARD FAIL on schema mismatches

This module provides functions to validate that the database schema
matches the ORM models exactly. Any mismatch causes a hard failure.
"""
import logging
from typing import Dict, List, Set
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine
from app.db.database import Base

logger = logging.getLogger(__name__)


# Required columns from Prospect model - ALL must exist
REQUIRED_PROSPECT_COLUMNS = {
    # Core fields
    'id', 'domain', 'page_url', 'page_title', 'contact_email', 'contact_method',
    'da_est', 'score', 'outreach_status', 'last_sent', 'followups_sent',
    'draft_subject', 'draft_body', 'final_body', 'thread_id', 'sequence_index',
    'is_manual', 'created_at', 'updated_at',
    
    # Pipeline status fields
    'discovery_status', 'scrape_status', 'approval_status', 'verification_status',
    'draft_status', 'send_status', 'stage',
    
    # Discovery metadata
    'discovery_query_id', 'discovery_category', 'discovery_location', 'discovery_keywords',
    
    # Scraping metadata
    'scrape_payload', 'scrape_source_url',
    
    # Verification metadata
    'verification_confidence', 'verification_payload',
    
    # API responses
    'dataforseo_payload', 'snov_payload',
    
    # SERP intent
    'serp_intent', 'serp_confidence', 'serp_signals',
    
    # Social outreach fields
    'source_type', 'source_platform', 'profile_url', 'username', 'display_name',
    'follower_count', 'engagement_rate',
    
    # Realtime scraping fields
    'bio_text', 'external_links', 'scraped_at',
}


async def validate_prospect_schema(db: AsyncSession) -> Dict:
    """
    Validate that prospects table has ALL required columns from Prospect model.
    
    Returns:
        Dict with validation results:
        - valid: bool
        - missing_columns: List[str]
        - existing_columns: List[str]
        - error: str (if validation failed)
    
    Raises:
        Exception: If any required column is missing (HARD FAIL)
    """
    try:
        # Get all columns from prospects table
        result = await db.execute(text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'prospects'
            AND table_schema = 'public'
            ORDER BY column_name
        """))
        db_columns = {row[0]: {'type': row[1], 'nullable': row[2]} for row in result.fetchall()}
        
        # Check for missing required columns
        missing_columns = REQUIRED_PROSPECT_COLUMNS - set(db_columns.keys())
        
        if missing_columns:
            error_msg = f"CRITICAL: prospects table is missing {len(missing_columns)} required columns: {', '.join(sorted(missing_columns))}"
            logger.error("=" * 80)
            logger.error(f"❌ {error_msg}")
            logger.error("=" * 80)
            logger.error("❌ This indicates a schema mismatch that will cause query failures")
            logger.error("❌ ABORTING STARTUP TO PREVENT DATA CORRUPTION")
            logger.error("=" * 80)
            
            return {
                "valid": False,
                "missing_columns": sorted(missing_columns),
                "existing_columns": sorted(db_columns.keys()),
                "error": error_msg
            }
        
        logger.info("=" * 60)
        logger.info("✅ PROSPECT SCHEMA VALIDATION PASSED")
        logger.info(f"   All {len(REQUIRED_PROSPECT_COLUMNS)} required columns exist")
        logger.info("=" * 60)
        
        return {
            "valid": True,
            "missing_columns": [],
            "existing_columns": sorted(db_columns.keys()),
            "error": None
        }
        
    except Exception as e:
        error_msg = f"Schema validation failed: {str(e)}"
        logger.error("=" * 80)
        logger.error(f"❌ {error_msg}")
        logger.error("=" * 80)
        raise Exception(error_msg) from e


async def validate_alembic_version_table(db: AsyncSession) -> Dict:
    """
    Validate that alembic_version table exists and has correct structure.
    
    Returns:
        Dict with validation results
    
    Raises:
        Exception: If alembic_version table is missing or corrupted
    """
    try:
        # Check if table exists
        table_check = await db.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'alembic_version'
            )
        """))
        table_exists = table_check.scalar()
        
        if not table_exists:
            error_msg = "CRITICAL: alembic_version table does not exist - Alembic will re-run all migrations from base"
            logger.error("=" * 80)
            logger.error(f"❌ {error_msg}")
            logger.error("=" * 80)
            logger.error("❌ This will cause schema corruption and data loss")
            logger.error("❌ ABORTING STARTUP")
            logger.error("=" * 80)
            
            return {
                "valid": False,
                "table_exists": False,
                "error": error_msg
            }
        
        # Check table structure
        column_check = await db.execute(text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'alembic_version' 
            AND table_schema = 'public'
        """))
        columns = {row[0]: row[1] for row in column_check.fetchall()}
        
        if 'version_num' not in columns:
            error_msg = "CRITICAL: alembic_version table exists but missing version_num column - table structure is corrupted"
            logger.error("=" * 80)
            logger.error(f"❌ {error_msg}")
            logger.error("=" * 80)
            raise Exception(error_msg)
        
        # Get current version
        version_result = await db.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
        version_row = version_result.fetchone()
        current_version = version_row[0] if version_row else None
        
        logger.info("=" * 60)
        logger.info("✅ ALEMBIC_VERSION TABLE VALIDATION PASSED")
        logger.info(f"   Table exists: ✅")
        logger.info(f"   Current version: {current_version}")
        logger.info("=" * 60)
        
        return {
            "valid": True,
            "table_exists": True,
            "current_version": current_version,
            "error": None
        }
        
    except Exception as e:
        error_msg = f"Alembic version table validation failed: {str(e)}"
        logger.error("=" * 80)
        logger.error(f"❌ {error_msg}")
        logger.error("=" * 80)
        raise Exception(error_msg) from e


async def get_full_schema_diagnostics(engine: AsyncEngine) -> Dict:
    """
    Get comprehensive schema diagnostics comparing database to ORM models.
    
    Args:
        engine: AsyncEngine instance from app.db.database
        
    Returns:
        JSON-serializable dict containing:
        - alembic_revision: Current Alembic revision from alembic_version table
        - database_name: Name of the connected database
        - db_columns: List of columns in prospects table (from information_schema)
        - model_columns: List of columns defined in Prospect model
        - schema_match: Boolean indicating if model columns ⊆ db columns
        - status: "ok" or "error"
        - all_tables_valid: Boolean indicating if all required tables exist
    """
    try:
        async with engine.begin() as conn:
            diagnostics = {
                "status": "ok",
                "alembic_revision": None,
                "database_name": None,
                "db_columns": [],
                "model_columns": [],
                "schema_match": False,
                "all_tables_valid": False,
                "missing_columns": [],
                "extra_columns": []
            }
            
            # Get database name
            try:
                db_info_result = await conn.execute(text("SELECT current_database()"))
                db_name = db_info_result.scalar()
                diagnostics["database_name"] = db_name
            except Exception as e:
                logger.warning(f"Could not get database name: {e}")
            
            # Get Alembic revision
            try:
                version_result = await conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
                version_row = version_result.fetchone()
                if version_row:
                    diagnostics["alembic_revision"] = version_row[0]
            except Exception as e:
                logger.warning(f"Could not get Alembic revision: {e}")
            
            # Get actual database columns from information_schema
            try:
                columns_result = await conn.execute(text("""
                    SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'prospects'
                    AND table_schema = 'public'
                    ORDER BY column_name
        """))
                db_columns = [row[0] for row in columns_result.fetchall()]
                diagnostics["db_columns"] = db_columns
            except Exception as e:
                logger.error(f"Could not get database columns: {e}")
                diagnostics["status"] = "error"
                diagnostics["error"] = f"Failed to read database columns: {str(e)}"
                return diagnostics
            
            # Get model-defined columns from Base.metadata
            try:
                if "prospects" in Base.metadata.tables:
                    prospects_table = Base.metadata.tables["prospects"]
                    model_columns = [col.name for col in prospects_table.columns]
                    diagnostics["model_columns"] = model_columns
                else:
                    logger.warning("prospects table not found in Base.metadata.tables")
                    # Fallback: use REQUIRED_PROSPECT_COLUMNS
                    diagnostics["model_columns"] = sorted(REQUIRED_PROSPECT_COLUMNS)
            except Exception as e:
                logger.error(f"Could not get model columns: {e}")
                # Fallback: use REQUIRED_PROSPECT_COLUMNS
                diagnostics["model_columns"] = sorted(REQUIRED_PROSPECT_COLUMNS)
            
            # Compare: model columns must be subset of db columns
            db_columns_set = set(db_columns)
            model_columns_set = set(diagnostics["model_columns"])
            
            missing_columns = model_columns_set - db_columns_set
            extra_columns = db_columns_set - model_columns_set
            
            diagnostics["missing_columns"] = sorted(missing_columns)
            diagnostics["extra_columns"] = sorted(extra_columns)
            diagnostics["schema_match"] = len(missing_columns) == 0
            
            # Check if all required tables exist
            try:
                tables_result = await conn.execute(text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_type = 'BASE TABLE'
                """))
                existing_tables = {row[0] for row in tables_result.fetchall()}
                required_tables = {'prospects', 'jobs', 'email_logs', 'settings', 'discovery_queries', 'alembic_version'}
                diagnostics["all_tables_valid"] = required_tables.issubset(existing_tables)
            except Exception as e:
                logger.warning(f"Could not check required tables: {e}")
            
            return diagnostics
            
    except Exception as e:
        logger.error(f"Schema diagnostics failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "message": "Could not get schema diagnostics"
        }
