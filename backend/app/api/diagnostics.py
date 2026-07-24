"""
Database Diagnostics API

CRITICAL: This endpoint is for production forensics only.
Use this to diagnose schema state, migration history, and data visibility issues.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, func
from typing import Dict, Any, List, Optional
import logging

from app.db.database import get_db
from app.api.auth import get_current_user_optional
from app.models.prospect import Prospect
from app.models.job import Job

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/diagnostics", tags=["diagnostics"])


@router.get("/database-state")
async def get_database_state(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    STEP 1: Verify current data reality (raw SQL only)
    
    Returns:
    - Row counts for all main tables
    - Schema information for prospects table
    - Presence of critical columns
    """
    try:
        results = {}
        
        # Get row counts
        tables = ['prospects', 'jobs', 'discovery_queries', 'email_logs']
        for table in tables:
            try:
                result = await db.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = result.scalar() or 0
                results[f"{table}_count"] = count
            except Exception as e:
                results[f"{table}_count"] = f"ERROR: {str(e)}"
        
        # Get prospects schema
        schema_query = text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'prospects'
            ORDER BY ordinal_position
        """)
        schema_result = await db.execute(schema_query)
        columns = [
            {
                "name": row[0],
                "type": row[1],
                "nullable": row[2]
            }
            for row in schema_result.fetchall()
        ]
        results["prospects_schema"] = columns
        
        # Check for critical columns
        critical_columns = [
            'source_type', 'source_platform', 'approval_status',
            'discovery_status', 'scrape_status', 'discovery_query_id',
            'profile_url', 'username', 'display_name', 'follower_count',
            'engagement_rate', 'bio_text', 'external_links', 'scraped_at'
        ]
        column_names = {col["name"] for col in columns}
        results["critical_columns_present"] = {
            col: col in column_names for col in critical_columns
        }
        
        # Count social vs website prospects
        if 'source_type' in column_names:
            try:
                social_count = await db.execute(
                    text("SELECT COUNT(*) FROM prospects WHERE source_type = 'social'")
                )
                website_count = await db.execute(
                    text("SELECT COUNT(*) FROM prospects WHERE source_type = 'website' OR source_type IS NULL")
                )
                results["social_prospects_count"] = social_count.scalar() or 0
                results["website_prospects_count"] = website_count.scalar() or 0
            except Exception as e:
                results["social_prospects_count"] = f"ERROR: {str(e)}"
                results["website_prospects_count"] = f"ERROR: {str(e)}"
        else:
            results["social_prospects_count"] = "N/A - source_type column missing"
            results["website_prospects_count"] = "N/A - source_type column missing"
        
        return results
        
    except Exception as e:
        logger.error(f"❌ [DIAGNOSTICS] Error getting database state: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Diagnostic query failed: {str(e)}")


@router.get("/test-pipeline-queries")
async def test_pipeline_queries(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    STEP 5: Test pipeline queries directly to identify the mismatch
    
    Returns:
    - Raw SQL query results
    - ORM query results
    - Comparison showing where the mismatch occurs
    """
    try:
        results = {}
        
        # Test 1: Simple COUNT
        count_all = await db.execute(text("SELECT COUNT(*) FROM prospects"))
        results["count_all"] = count_all.scalar() or 0
        
        # Test 2: COUNT with discovery_status filter
        count_discovered = await db.execute(
            text("SELECT COUNT(*) FROM prospects WHERE discovery_status = 'DISCOVERED'")
        )
        results["count_discovered"] = count_discovered.scalar() or 0
        
        # Test 3: COUNT with discovery_status + source_type filter
        count_discovered_website = await db.execute(
            text("""
                SELECT COUNT(*) FROM prospects 
                WHERE discovery_status = 'DISCOVERED'
                AND (source_type = 'website' OR source_type IS NULL)
            """)
        )
        results["count_discovered_website"] = count_discovered_website.scalar() or 0
        
        # Test 4: SELECT with discovery_status (no source_type filter) - what /api/pipeline/websites uses
        select_discovered = await db.execute(
            text("""
                SELECT id, domain, page_url, discovery_status, source_type, source_platform
                FROM prospects 
                WHERE discovery_status = 'DISCOVERED'
                LIMIT 10
            """)
        )
        rows_discovered = select_discovered.fetchall()
        results["select_discovered_count"] = len(rows_discovered)
        results["select_discovered_sample"] = [
            {
                "id": str(row[0]),
                "domain": row[1],
                "page_url": row[2],
                "discovery_status": row[3],
                "source_type": row[4],
                "source_platform": row[5]
            }
            for row in rows_discovered[:5]
        ]
        
        # Test 5: SELECT with scrape_status filter (what /api/prospects/leads uses)
        count_scraped = await db.execute(
            text("""
                SELECT COUNT(*) FROM prospects 
                WHERE scrape_status IN ('SCRAPED', 'ENRICHED')
                AND (source_type = 'website' OR source_type IS NULL)
            """)
        )
        results["count_scraped_website"] = count_scraped.scalar() or 0
        
        select_scraped = await db.execute(
            text("""
                SELECT id, domain, scrape_status, source_type
                FROM prospects 
                WHERE scrape_status IN ('SCRAPED', 'ENRICHED')
                AND (source_type = 'website' OR source_type IS NULL)
                LIMIT 10
            """)
        )
        rows_scraped = select_scraped.fetchall()
        results["select_scraped_count"] = len(rows_scraped)
        results["select_scraped_sample"] = [
            {
                "id": str(row[0]),
                "domain": row[1],
                "scrape_status": row[2],
                "source_type": row[3]
            }
            for row in rows_scraped[:5]
        ]
        
        # Test 6: Check source_type distribution
        source_type_dist = await db.execute(
            text("""
                SELECT source_type, COUNT(*) as count
                FROM prospects
                GROUP BY source_type
            """)
        )
        results["source_type_distribution"] = {
            str(row[0]) if row[0] else 'NULL': row[1] 
            for row in source_type_dist.fetchall()
        }
        
        # Test 7: Check discovery_status distribution
        discovery_status_dist = await db.execute(
            text("""
                SELECT discovery_status, COUNT(*) as count
                FROM prospects
                GROUP BY discovery_status
            """)
        )
        results["discovery_status_distribution"] = {
            str(row[0]) if row[0] else 'NULL': row[1] 
            for row in discovery_status_dist.fetchall()
        }
        
        # Test 8: Check scrape_status distribution
        scrape_status_dist = await db.execute(
            text("""
                SELECT scrape_status, COUNT(*) as count
                FROM prospects
                GROUP BY scrape_status
            """)
        )
        results["scrape_status_distribution"] = {
            str(row[0]) if row[0] else 'NULL': row[1] 
            for row in scrape_status_dist.fetchall()
        }
        
        return results
        
    except Exception as e:
        logger.error(f"❌ [DIAGNOSTICS] Error testing pipeline queries: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Diagnostic query failed: {str(e)}")


@router.get("/alembic-state")
async def get_alembic_state(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    STEP 2: Check Alembic state (CRITICAL)
    
    Returns:
    - Current Alembic version
    - Migration history
    - Whether base migration re-ran
    """
    try:
        results = {}
        
        # Check if alembic_version table exists
        table_check = await db.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'alembic_version'
            )
        """))
        alembic_table_exists = table_check.scalar()
        results["alembic_version_table_exists"] = alembic_table_exists
        
        if alembic_table_exists:
            # Get current version
            version_result = await db.execute(text("SELECT * FROM alembic_version"))
            version_rows = version_result.fetchall()
            results["alembic_version_rows"] = len(version_rows)
            if version_rows:
                results["current_version"] = version_rows[0][0] if version_rows[0] else None
            else:
                results["current_version"] = None
                results["warning"] = "alembic_version table exists but is empty - Alembic history lost"
        else:
            results["current_version"] = None
            results["warning"] = "alembic_version table does not exist - fresh database or history lost"
        
        # Check for migration artifacts
        migration_artifacts = await db.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND (table_name LIKE '%migration%' OR table_name LIKE '%alembic%')
            ORDER BY table_name
        """))
        results["migration_artifacts"] = [row[0] for row in migration_artifacts.fetchall()]
        
        return results
        
    except Exception as e:
        logger.error(f"❌ [DIAGNOSTICS] Error getting Alembic state: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Diagnostic query failed: {str(e)}")


@router.get("/all-tables")
async def get_all_tables(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    STEP 3: Search for orphaned / old tables
    
    Returns:
    - All tables in public schema
    - Row counts for each table
    - Look for duplicates, legacy tables, etc.
    """
    try:
        results = {}
        
        # Get all tables
        tables_query = text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        tables_result = await db.execute(tables_query)
        tables = [row[0] for row in tables_result.fetchall()]
        results["all_tables"] = tables
        
        # Get row counts for each table
        table_counts = {}
        for table in tables:
            try:
                count_result = await db.execute(text(f"SELECT COUNT(*) FROM {table}"))
                table_counts[table] = count_result.scalar() or 0
            except Exception as e:
                table_counts[table] = f"ERROR: {str(e)}"
        results["table_row_counts"] = table_counts
        
        # Look for suspicious tables (duplicates, legacy, etc.)
        suspicious_patterns = [
            'old', 'backup', 'legacy', 'v1', 'v2', '_old', '_backup',
            'social_profiles', 'profiles_old', 'prospects_old'
        ]
        suspicious_tables = []
        for table in tables:
            for pattern in suspicious_patterns:
                if pattern in table.lower():
                    suspicious_tables.append(table)
                    break
        results["suspicious_tables"] = suspicious_tables
        
        return results
        
    except Exception as e:
        logger.error(f"❌ [DIAGNOSTICS] Error getting all tables: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Diagnostic query failed: {str(e)}")


@router.get("/overview-data-source")
async def get_overview_data_source(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    STEP 4: Trace Overview counts source
    
    Returns:
    - What tables/endpoints Overview uses
    - Actual counts from those sources
    - Comparison with Discovered/Leads queries
    """
    try:
        results = {}
        
        # Check what getSocialPipelineStatus would return
        try:
            from app.models.prospect import DiscoveryStatus
            
            # Check if source_type column exists
            column_check = await db.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'prospects' 
                AND column_name = 'source_type'
            """))
            source_type_exists = column_check.fetchone() is not None
            
            if source_type_exists:
                # Count discovered (what Overview shows)
                discovered_query = text("""
                    SELECT COUNT(*) 
                    FROM prospects 
                    WHERE source_type = 'social' 
                    AND discovery_status = 'DISCOVERED'
                """)
                discovered_result = await db.execute(discovered_query)
                results["overview_discovered_count"] = discovered_result.scalar() or 0
                
                # Count reviewed/approved (what Overview shows)
                reviewed_query = text("""
                    SELECT COUNT(*) 
                    FROM prospects 
                    WHERE source_type = 'social' 
                    AND (approval_status = 'approved' OR approval_status = 'APPROVED')
                """)
                reviewed_result = await db.execute(reviewed_query)
                results["overview_reviewed_count"] = reviewed_result.scalar() or 0
                
                # Count what Discovered tab would show (PENDING or NULL)
                discovered_tab_query = text("""
                    SELECT COUNT(*) 
                    FROM prospects 
                    WHERE source_type = 'social' 
                    AND discovery_status = 'DISCOVERED'
                    AND (approval_status = 'PENDING' OR approval_status IS NULL 
                         OR (approval_status IS NOT NULL AND LOWER(approval_status) != 'approved'))
                """)
                discovered_tab_result = await db.execute(discovered_tab_query)
                results["discovered_tab_count"] = discovered_tab_result.scalar() or 0
                
                # Count what Social Leads tab would show (approved)
                leads_tab_query = text("""
                    SELECT COUNT(*) 
                    FROM prospects 
                    WHERE source_type = 'social' 
                    AND discovery_status = 'DISCOVERED'
                    AND (approval_status = 'approved' OR approval_status = 'APPROVED')
                """)
                leads_tab_result = await db.execute(leads_tab_query)
                results["social_leads_tab_count"] = leads_tab_result.scalar() or 0
                
                # Breakdown by approval_status
                breakdown_query = text("""
                    SELECT approval_status, COUNT(*) as count
                    FROM prospects
                    WHERE source_type = 'social'
                    AND discovery_status = 'DISCOVERED'
                    GROUP BY approval_status
                """)
                breakdown_result = await db.execute(breakdown_query)
                breakdown = {str(row[0]) if row[0] else 'NULL': row[1] for row in breakdown_result.fetchall()}
                results["approval_status_breakdown"] = breakdown
            else:
                results["error"] = "source_type column does not exist - migration not applied"
                results["overview_discovered_count"] = "N/A"
                results["discovered_tab_count"] = "N/A"
                results["social_leads_tab_count"] = "N/A"
                
        except Exception as e:
            results["error"] = f"Query failed: {str(e)}"
            logger.error(f"❌ [DIAGNOSTICS] Error querying overview data source: {e}", exc_info=True)
        
        return results
        
    except Exception as e:
        logger.error(f"❌ [DIAGNOSTICS] Error getting overview data source: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Diagnostic query failed: {str(e)}")


@router.get("/database-identity")
async def get_database_identity(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    STEP 5: Confirm database identity (Render gotcha)
    
    Returns:
    - Database connection info (safe to expose)
    - Database name
    - Server version
    """
    try:
        results = {}
        
        # Get database name
        db_name_result = await db.execute(text("SELECT current_database()"))
        results["database_name"] = db_name_result.scalar()
        
        # Get PostgreSQL version
        version_result = await db.execute(text("SELECT version()"))
        results["postgres_version"] = version_result.scalar()
        
        # Get current user
        user_result = await db.execute(text("SELECT current_user"))
        results["database_user"] = user_result.scalar()
        
        # Get server host (if accessible)
        try:
            host_result = await db.execute(text("SELECT inet_server_addr()"))
            host = host_result.scalar()
            results["server_host"] = host if host else "Not accessible"
        except:
            results["server_host"] = "Not accessible"
        
        return results
        
    except Exception as e:
        logger.error(f"❌ [DIAGNOSTICS] Error getting database identity: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Diagnostic query failed: {str(e)}")


@router.get("/schema")
async def debug_schema(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Debug endpoint to check schema state.
    
    Returns:
    - alembic current revision
    - alembic head revision
    - list of prospects columns
    - database name + host
    """
    try:
        from sqlalchemy import text, create_engine
        from alembic.script import ScriptDirectory
        from alembic.runtime.migration import MigrationContext
        from alembic.config import Config
        import os
        
        results = {
            "database_info": {},
            "alembic_state": {},
            "prospects_columns": [],
            "schema_validation": {}
        }
        
        # Get database info
        db_info_result = await db.execute(text("SELECT current_database(), inet_server_addr()"))
        db_info = db_info_result.fetchone()
        if db_info:
            results["database_info"] = {
                "name": db_info[0],
                "host": db_info[1] or "localhost (local connection)"
            }
        
        # Get Alembic state
        try:
            database_url = os.getenv("DATABASE_URL", "")
            sync_url = database_url.replace("postgresql+asyncpg://", "postgresql://") if database_url.startswith("postgresql+asyncpg://") else database_url
            
            # Get current revision from alembic_version table
            version_result = await db.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
            version_row = version_result.fetchone()
            current_rev = version_row[0] if version_row else None
            
            # Get current revision via MigrationContext
            engine = create_engine(sync_url, pool_pre_ping=True)
            with engine.connect() as conn:
                context = MigrationContext.configure(conn)
                context_rev = context.get_current_revision()
            
            # Get head revision
            import glob
            alembic_ini_path = None
            possible_paths = [
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "alembic.ini"),
                "alembic.ini",
                "/app/alembic.ini",
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    alembic_ini_path = path
                    break
            
            if alembic_ini_path:
                alembic_cfg = Config(alembic_ini_path)
                if database_url:
                    if database_url.startswith("postgresql+asyncpg://"):
                        sync_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
                        alembic_cfg.set_main_option("sqlalchemy.url", sync_url)
                script = ScriptDirectory.from_config(alembic_cfg)
                heads = script.get_revision("heads")
                head_rev = heads.revision if heads else None
            else:
                head_rev = None
            
            results["alembic_state"] = {
                "alembic_version_table": current_rev,
                "migration_context": context_rev,
                "head_revision": head_rev,
                "is_at_head": current_rev == head_rev if current_rev and head_rev else False
            }
            
            engine.dispose()
        except Exception as alembic_err:
            results["alembic_state"] = {
                "error": str(alembic_err)
            }
        
        # Get prospects columns
        columns_result = await db.execute(text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'prospects' 
            AND table_schema = 'public'
            ORDER BY column_name
        """))
        results["prospects_columns"] = [
            {
                "name": row[0],
                "type": row[1],
                "nullable": row[2]
            }
            for row in columns_result.fetchall()
        ]
        
        # Run schema validation
        try:
            from app.utils.schema_validator import validate_prospect_schema, validate_alembic_version_table
            schema_validation = await validate_prospect_schema(db)
            alembic_validation = await validate_alembic_version_table(db)
            results["schema_validation"] = {
                "prospect_schema": schema_validation,
                "alembic_version": alembic_validation
            }
        except Exception as validation_err:
            results["schema_validation"] = {
                "error": str(validation_err)
            }
        
        return results
        
    except Exception as e:
        logger.error(f"❌ [DEBUG SCHEMA] Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Debug schema check failed: {str(e)}")


@router.get("/full-forensics")
async def get_full_forensics(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Complete forensics report combining all diagnostic endpoints.
    
    This provides a comprehensive view of the database state for incident classification.
    """
    try:
        # Run all diagnostics (call functions directly, not import)
        db_state = await get_database_state(db, current_user)
        alembic_state = await get_alembic_state(db, current_user)
        all_tables = await get_all_tables(db, current_user)
        overview_source = await get_overview_data_source(db, current_user)
        db_identity = await get_database_identity(db, current_user)
        test_queries = await test_pipeline_queries(db, current_user)
        
        # Classify incident
        classification = classify_incident(db_state, alembic_state, all_tables, overview_source)
        
        return {
            "database_state": db_state,
            "alembic_state": alembic_state,
            "all_tables": all_tables,
            "overview_data_source": overview_source,
            "database_identity": db_identity,
            "test_pipeline_queries": test_queries,
            "incident_classification": classification
        }
        
    except Exception as e:
        logger.error(f"❌ [DIAGNOSTICS] Error in full forensics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Forensics failed: {str(e)}")


def classify_incident(db_state: Dict, alembic_state: Dict, all_tables: Dict, overview_source: Dict) -> Dict[str, Any]:
    """
    Classify the incident based on diagnostic data.
    
    Returns: Case A, B, C, or D with evidence and recovery plan.
    """
    classification = {
        "case": None,
        "evidence": [],
        "root_cause": None,
        "recovery_plan": None
    }
    
    # Check for Case A: Wrong database connected
    prospects_count = db_state.get("prospects_count", 0)
    if isinstance(prospects_count, int) and prospects_count == 0:
        # Check if there are suspicious tables with data
        table_counts = all_tables.get("table_row_counts", {})
        for table, count in table_counts.items():
            if isinstance(count, int) and count > 0 and ('old' in table.lower() or 'backup' in table.lower()):
                classification["case"] = "A"
                classification["evidence"].append(f"Table {table} has {count} rows but prospects is empty")
                classification["root_cause"] = "Backend connected to wrong database instance"
                classification["recovery_plan"] = "Reconnect backend to correct database using correct DATABASE_URL"
                return classification
    
    # Check for Case B: Alembic history lost
    alembic_version = alembic_state.get("current_version")
    if not alembic_version or alembic_version == "000000000000":
        if prospects_count == 0:
            classification["case"] = "B"
            classification["evidence"].append("Alembic version is base migration (000000000000)")
            classification["evidence"].append("prospects table is empty")
            classification["root_cause"] = "Alembic migration history lost, base migration re-ran, tables recreated"
            classification["recovery_plan"] = "Check for database backups or point-in-time recovery. If data exists elsewhere, write one-time migration to restore."
            return classification
    
    # Check for Case C: Schema drift
    critical_columns = db_state.get("critical_columns_present", {})
    if not critical_columns.get("source_type", False):
        classification["case"] = "C"
        classification["evidence"].append("source_type column missing from prospects table")
        classification["evidence"].append(f"Migration add_social_columns_to_prospects not applied")
        classification["root_cause"] = "Schema drift - data exists but queries fail due to missing columns"
        classification["recovery_plan"] = "Run migration: alembic upgrade head. This will add missing columns without losing data."
        return classification
    
    # Check for Case D: Database reset
    if prospects_count == 0 and not any(isinstance(count, int) and count > 0 for count in all_tables.get("table_row_counts", {}).values()):
        classification["case"] = "D"
        classification["evidence"].append("All tables are empty")
        classification["evidence"].append("No migration history or fresh database")
        classification["root_cause"] = "Database was reset or recreated - data irreversibly lost"
        classification["recovery_plan"] = "Acknowledge data loss. Lock migrations permanently. Restore from backup if available."
        return classification
    
    # Default: Unknown
    classification["case"] = "UNKNOWN"
    classification["evidence"].append("Unable to classify - insufficient diagnostic data")
    classification["root_cause"] = "Requires manual investigation"
    classification["recovery_plan"] = "Review all diagnostic endpoints manually"
    
    return classification
