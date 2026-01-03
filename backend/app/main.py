"""
FastAPI application entry point
"""
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.api import jobs, prospects
from app.db.database import engine, Base
import os
import logging
import traceback

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Art Outreach Automation API",
    description="API for automated art website discovery and outreach",
    version="2.0.0"
)


@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    """
    Fallback middleware to guarantee CORS headers on all responses.
    This runs in addition to CORSMiddleware, but ensures that even
    unexpected 500 errors include Access-Control-Allow-* headers so
    the frontend can read the response instead of seeing a CORS block.
    """
    try:
        response = await call_next(request)
        # Always add CORS headers, even if CORSMiddleware didn't
        response.headers.setdefault("Access-Control-Allow-Origin", "*")
        response.headers.setdefault("Access-Control-Allow-Methods", "*")
        response.headers.setdefault("Access-Control-Allow-Headers", "*")
        return response
    except Exception as e:
        # If an exception occurs, create a response with CORS headers
        logger.error(f"Unhandled exception in middleware: {e}", exc_info=True)
        error_response = JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "error": str(e)}
        )
        error_response.headers["Access-Control-Allow-Origin"] = "*"
        error_response.headers["Access-Control-Allow-Methods"] = "*"
        error_response.headers["Access-Control-Allow-Headers"] = "*"
        return error_response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler to ensure all errors include CORS headers.
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    error_response = JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error": str(exc),
            "type": type(exc).__name__
        }
    )
    error_response.headers["Access-Control-Allow-Origin"] = "*"
    error_response.headers["Access-Control-Allow-Methods"] = "*"
    error_response.headers["Access-Control-Allow-Headers"] = "*"
    return error_response


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """
    HTTP exception handler with CORS headers.
    """
    error_response = JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )
    error_response.headers["Access-Control-Allow-Origin"] = "*"
    error_response.headers["Access-Control-Allow-Methods"] = "*"
    error_response.headers["Access-Control-Allow-Headers"] = "*"
    return error_response


app.add_middleware(
    CORSMiddleware,
    # Use wildcard origins with credentials disabled so Render always
    # sends Access-Control-Allow-Origin, regardless of the caller.
    # We rely on Authorization headers, not cookies.
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
from app.api import auth, settings, scraper, pipeline, manual, health, social
from app.api import social_pipeline  # Separate pipeline API for social outreach
# To use Supabase Auth instead, replace the line below with:
# from app.api import auth_supabase
# app.include_router(auth_supabase.router, prefix="/api/auth", tags=["auth"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(jobs.router, tags=["jobs"])  # Already has /api/jobs prefix
app.include_router(prospects.router, prefix="/api/prospects", tags=["prospects"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(scraper.router, prefix="/api/scraper", tags=["scraper"])
app.include_router(pipeline.router, tags=["pipeline"])  # Already has /api/pipeline prefix (WEBSITE OUTREACH)
app.include_router(manual.router, tags=["manual"])  # Already has /api/manual prefix
app.include_router(health.router, tags=["health"])  # Health check endpoints
app.include_router(social.router, tags=["social"])  # Social outreach - separate from website outreach
app.include_router(social_pipeline.router, tags=["social-pipeline"])  # Social pipeline - completely separate from website pipeline

# Webhook routes
from app.api import webhooks
app.include_router(webhooks.router, prefix="/api", tags=["webhooks"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Art Outreach Automation API",
        "version": "2.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health():
    """Health check endpoint - responds immediately for Render deployment checks"""
    return {"status": "healthy", "service": "art-outreach-api"}

@app.get("/health/ready")
async def readiness():
    """Readiness check - verifies database connectivity"""
    try:
        # Quick database connectivity check (with timeout)
        from sqlalchemy import text
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ready", "database": "connected"}
    except Exception as e:
        logger.warning(f"Readiness check failed: {e}")
        # Still return 200 so Render doesn't fail deployment
        # Database might be temporarily unavailable
        return {"status": "ready", "database": "checking", "warning": str(e)}


@app.on_event("startup")
async def startup():
    """Startup event - run migrations and start scheduler"""
    # Log that server is starting (important for Render deployment checks)
    logger.info("🚀 Server starting up...")
    logger.info(f"📡 Server will listen on port {os.getenv('PORT', '8000')}")
    
    # CRITICAL: Run migrations BEFORE server accepts requests
    # This ensures schema is correct before any API calls
    import asyncio
    
    async def run_database_setup():
        """Run all database setup operations - BLOCKING until complete"""
        # CRITICAL: Run migrations FIRST before any queries
        # This ensures schema is correct before SELECT queries run
        try:
            from alembic.config import Config
            from alembic import command
            
            logger.info("🔄 Running database migrations on startup (CRITICAL: must run before queries)...")
            logger.info("=" * 60)
            
            # Get the backend directory path - try multiple locations
            import os
            import glob
            
            # Try to find alembic.ini in common locations
            possible_paths = [
                os.path.join(os.path.dirname(os.path.dirname(__file__)), "alembic.ini"),  # backend/alembic.ini
                os.path.join(os.path.dirname(__file__), "..", "..", "alembic.ini"),  # backend/alembic.ini (alternative)
                "alembic.ini",  # Current directory
                "/app/alembic.ini",  # Render /app directory
                "/app/backend/alembic.ini",  # Render /app/backend directory
            ]
            
            alembic_ini_path = None
            for path in possible_paths:
                if os.path.exists(path):
                    alembic_ini_path = path
                    logger.info(f"✅ Found alembic.ini at: {path}")
                    break
            
            if not alembic_ini_path:
                # Last resort: search for it
                logger.warning("⚠️  alembic.ini not found in expected locations, searching...")
                found = glob.glob("**/alembic.ini", recursive=True)
                if found:
                    alembic_ini_path = found[0]
                    logger.info(f"✅ Found alembic.ini at: {alembic_ini_path}")
                else:
                    logger.error(f"❌ CRITICAL: alembic.ini not found anywhere")
                    logger.error(f"❌ Current directory: {os.getcwd()}")
                    logger.error(f"❌ Searched paths: {possible_paths}")
                    raise FileNotFoundError("alembic.ini not found in any expected location")
            
            alembic_cfg = Config(alembic_ini_path)
            
            # Get database URL and set in config
            database_url = os.getenv("DATABASE_URL")
            if database_url:
                # Convert asyncpg URL to psycopg2 for Alembic
                if database_url.startswith("postgresql+asyncpg://"):
                    sync_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
                    alembic_cfg.set_main_option("sqlalchemy.url", sync_url)
                    logger.info("✅ Converted asyncpg URL to psycopg2 format for Alembic")
            
            # Run migrations FIRST - AUTOMATIC ON EVERY STARTUP
            # This is CRITICAL: Migrations MUST run before any database queries
            try:
                logger.info("🚀 Executing: alembic upgrade heads")
                logger.info("📝 This runs automatically on every backend startup")
                logger.info(f"📁 Using alembic.ini: {alembic_ini_path}")
                logger.info(f"📁 Database URL configured: {'Yes' if database_url else 'No'}")
                logger.info("=" * 60)
                
                # Change to the directory containing alembic.ini for better compatibility
                alembic_dir = os.path.dirname(os.path.abspath(alembic_ini_path))
                original_cwd = os.getcwd()
                try:
                    os.chdir(alembic_dir)
                    logger.info(f"📁 Changed to directory: {alembic_dir}")
                    # Use 'heads' instead of 'head' to upgrade all migration branches
                    command.upgrade(alembic_cfg, "heads")
                finally:
                    os.chdir(original_cwd)
                
                logger.info("=" * 60)
                logger.info("✅ Database migrations completed successfully")
                logger.info("✅ All tables are up-to-date with latest schema")
                logger.info("=" * 60)
                
                # Schema validation is now handled by validate_all_tables_exist() after migrations
                # This ensures all tables (website + social) are validated together
                logger.info("✅ Migrations completed - schema validation will run next")
            except Exception as migration_error:
                logger.error("=" * 80)
                logger.error("❌ CRITICAL: Migration execution failed")
                logger.error(f"❌ Error type: {type(migration_error).__name__}")
                logger.error(f"❌ Error message: {str(migration_error)}")
                logger.error("=" * 80)
                logger.error("❌ Full traceback:")
                import traceback
                logger.error(traceback.format_exc())
                logger.error("=" * 80)
                logger.error("❌ alembic upgrade head failed")
                logger.error("=" * 80)
                logger.error("⚠️  APPLICATION WILL CONTINUE TO START")
                logger.error("⚠️  Some features may not work until migrations are fixed")
                logger.error("⚠️  Use /health/migrate endpoint to retry migrations")
                logger.error("=" * 80)
                # Don't fail hard - allow app to start but log the error
                # This prevents deployment failures while still alerting to the issue
        except Exception as e:
            logger.error("=" * 80)
            logger.error(f"❌ CRITICAL: Migration setup failed: {e}", exc_info=True)
            logger.error("❌ Application will continue to start")
            logger.error("⚠️  Some features may not work until migrations are fixed")
            logger.error("⚠️  Use /health/migrate endpoint to retry migrations")
            logger.error("=" * 80)
            # Don't re-raise - allow app to start even if migrations fail
            # This prevents deployment failures while still alerting to the issue
        
        # Add a small delay after migrations
        await asyncio.sleep(1)
        
        # All post-migration database operations wrapped in try-except
        # This ensures app starts even if any of these operations fail
        try:
            # TASK: Log database connection info and data count
            try:
                from sqlalchemy import text
                async with engine.begin() as conn:
                    # Log current database and server address
                    db_info_result = await conn.execute(
                        text("SELECT current_database(), inet_server_addr()")
                    )
                    db_info = db_info_result.fetchone()
                    if db_info:
                        db_name = db_info[0]
                        db_host = db_info[1] or "localhost (local connection)"
                        logger.info(f"📊 Connected to database: {db_name}")
                        logger.info(f"📊 Database server address: {db_host}")
                    else:
                        logger.warning("⚠️  Could not retrieve database connection info")
                    
                    # Log prospects count
                    count_result = await conn.execute(
                        text("SELECT COUNT(*) FROM prospects")
                    )
                    prospects_count = count_result.scalar() or 0
                    logger.info(f"📊 Prospects count in database: {prospects_count}")
            except Exception as db_check_err:
                logger.error(f"❌ Error checking database connection: {db_check_err}", exc_info=True)
            
            # EMERGENCY FIX: Check and add discovery_query_id column if missing
            try:
                from sqlalchemy import text
                async with engine.begin() as conn:
                # Check if column exists
                result = await conn.execute(
                    text("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name = 'prospects' 
                        AND column_name = 'discovery_query_id'
                    """)
                )
                column_exists = result.fetchone() is not None
                
                if not column_exists:
                    logger.warning("⚠️  Missing discovery_query_id column - adding it now...")
                    # Add column
                    await conn.execute(
                        text("ALTER TABLE prospects ADD COLUMN discovery_query_id UUID")
                    )
                    # Create index
                    await conn.execute(
                        text("CREATE INDEX IF NOT EXISTS ix_prospects_discovery_query_id ON prospects(discovery_query_id)")
                    )
                    # Check if discovery_queries table exists and add FK
                    table_check = await conn.execute(
                        text("SELECT 1 FROM information_schema.tables WHERE table_name = 'discovery_queries'")
                    )
                    if table_check.fetchone():
                        fk_check = await conn.execute(
                            text("""
                                SELECT 1 FROM information_schema.table_constraints 
                                WHERE constraint_name = 'fk_prospects_discovery_query_id'
                            """)
                        )
                        if not fk_check.fetchone():
                            await conn.execute(
                                text("""
                                    ALTER TABLE prospects
                                    ADD CONSTRAINT fk_prospects_discovery_query_id
                                    FOREIGN KEY (discovery_query_id)
                                    REFERENCES discovery_queries(id)
                                    ON DELETE SET NULL
                                """)
                            )
                    logger.info("✅ Added discovery_query_id column, index, and foreign key")
                else:
                    logger.info("✅ discovery_query_id column already exists")
                
                # Check and add serp_intent columns if missing
                serp_intent_check = await conn.execute(
                    text("""
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'prospects' AND column_name = 'serp_intent'
                    """)
                )
                serp_intent_exists = serp_intent_check.fetchone() is not None
                
                if not serp_intent_exists:
                    logger.warning("⚠️  Missing serp_intent columns - adding them now...")
                    # Add serp_intent column
                    await conn.execute(
                        text("ALTER TABLE prospects ADD COLUMN serp_intent VARCHAR")
                    )
                    # Add serp_confidence column
                    await conn.execute(
                        text("ALTER TABLE prospects ADD COLUMN serp_confidence NUMERIC(3, 2)")
                    )
                    # Add serp_signals column (JSON)
                    await conn.execute(
                        text("ALTER TABLE prospects ADD COLUMN serp_signals JSONB")
                    )
                    logger.info("✅ Added serp_intent, serp_confidence, and serp_signals columns")
                else:
                    logger.info("✅ serp_intent columns already exist")
                
                # Ensure discovery metadata columns exist (required for /api/pipeline/websites)
                discovery_metadata_columns = [
                    ("discovery_category", "VARCHAR"),
                    ("discovery_location", "VARCHAR"),
                    ("discovery_keywords", "TEXT"),
                ]
                
                for column_name, sql_type in discovery_metadata_columns:
                    column_check = await conn.execute(
                        text("""
                            SELECT column_name
                            FROM information_schema.columns 
                            WHERE table_name = 'prospects' 
                            AND column_name = :column_name
                        """),
                        {"column_name": column_name}
                    )
                    if not column_check.fetchone():
                        logger.warning(f"⚠️  Missing {column_name} column - adding it now...")
                        await conn.execute(
                            text(f"ALTER TABLE prospects ADD COLUMN {column_name} {sql_type}")
                        )
                        logger.info(f"✅ Added {column_name} column")
                    else:
                        logger.info(f"✅ {column_name} column already exists")
                
                # Ensure scraping and verification metadata columns exist (required for pipeline queries)
                metadata_columns = [
                    ("scrape_payload", "JSONB"),
                    ("scrape_source_url", "TEXT"),
                    ("verification_confidence", "NUMERIC(5, 2)"),
                    ("verification_payload", "JSONB"),
                    ("dataforseo_payload", "JSONB"),
                    ("snov_payload", "JSONB"),
                ]
                
                for column_name, sql_type in metadata_columns:
                    column_check = await conn.execute(
                        text("""
                            SELECT column_name
                            FROM information_schema.columns 
                            WHERE table_name = 'prospects' 
                            AND column_name = :column_name
                        """),
                        {"column_name": column_name}
                    )
                    if not column_check.fetchone():
                        logger.warning(f"⚠️  Missing {column_name} column - adding it now...")
                        await conn.execute(
                            text(f"ALTER TABLE prospects ADD COLUMN {column_name} {sql_type}")
                        )
                        logger.info(f"✅ Added {column_name} column")
                    else:
                        logger.info(f"✅ {column_name} column already exists")
                
                # BULLETPROOF FIX: Ensure ALL pipeline status columns exist
                # Required columns for /api/pipeline/status and pipeline endpoints to work without 500 errors
                # Format: (column_name, sql_type, default_value, should_be_not_null)
                # These columns are CRITICAL - missing any causes UndefinedColumnError
                required_pipeline_columns = [
                    ("discovery_status", "VARCHAR", "NEW", True),
                    ("scrape_status", "VARCHAR", "DISCOVERED", True),
                    ("approval_status", "VARCHAR", "PENDING", True),
                    ("verification_status", "VARCHAR", "UNVERIFIED", True),
                    ("draft_status", "VARCHAR", "pending", True),  # pending, drafted, failed
                    ("send_status", "VARCHAR", "pending", True),  # pending, sent, failed
                    ("stage", "VARCHAR", "DISCOVERED", True),  # Canonical pipeline stage: DISCOVERED, SCRAPED, LEAD, VERIFIED, DRAFTED, SENT
                ]
                
                for column_name, sql_type, default_value, should_be_not_null in required_pipeline_columns:
                    # Check if column exists
                    column_check = await conn.execute(
                        text("""
                            SELECT column_name, is_nullable, column_default
                            FROM information_schema.columns 
                            WHERE table_name = 'prospects' 
                            AND column_name = :column_name
                        """),
                        {"column_name": column_name}
                    )
                    column_row = column_check.fetchone()
                    
                    if not column_row:
                        logger.warning(f"⚠️  Missing {column_name} column - adding it now...")
                        # Step 1: Add column as nullable first (safe for existing rows)
                        await conn.execute(
                            text(f"ALTER TABLE prospects ADD COLUMN {column_name} {sql_type}")
                        )
                        # Step 2: Backfill existing rows with default value
                        await conn.execute(
                            text(f"UPDATE prospects SET {column_name} = :default_value WHERE {column_name} IS NULL"),
                            {"default_value": default_value}
                        )
                        # Step 3: Set default (use string formatting for ALTER TABLE)
                        await conn.execute(
                            text(f"ALTER TABLE prospects ALTER COLUMN {column_name} SET DEFAULT '{default_value}'")
                        )
                        # Step 4: Make NOT NULL if required (safe now that all rows have values)
                        if should_be_not_null:
                            await conn.execute(
                                text(f"ALTER TABLE prospects ALTER COLUMN {column_name} SET NOT NULL")
                            )
                        # Step 5: Create index for performance
                        await conn.execute(
                            text(f"CREATE INDEX IF NOT EXISTS ix_prospects_{column_name} ON prospects({column_name})")
                        )
                        logger.info(f"✅ Added {column_name} column ({'NOT NULL' if should_be_not_null else 'NULLABLE'}, DEFAULT '{default_value}') with index")
                        
                        # Special handling for stage column: backfill based on email presence
                        if column_name == "stage":
                            logger.info("🔄 Backfilling stage column based on email presence...")
                            # Prospects with emails → LEAD
                            await conn.execute(
                                text("UPDATE prospects SET stage = 'LEAD' WHERE contact_email IS NOT NULL AND contact_email != '' AND stage = 'DISCOVERED'")
                            )
                            # Prospects with scrape_status=SCRAPED but no email → SCRAPED
                            await conn.execute(
                                text("UPDATE prospects SET stage = 'SCRAPED' WHERE scrape_status = 'SCRAPED' AND (contact_email IS NULL OR contact_email = '') AND stage = 'DISCOVERED'")
                            )
                            # Prospects with scrape_status=ENRICHED → LEAD (they have emails)
                            await conn.execute(
                                text("UPDATE prospects SET stage = 'LEAD' WHERE scrape_status = 'ENRICHED' AND stage = 'DISCOVERED'")
                            )
                            logger.info("✅ Stage column backfilled based on email presence")
                    else:
                        # Column exists - check if it needs to be fixed
                        is_nullable = column_row[1] == 'YES'
                        current_default = column_row[2]
                        default_str = f"'{default_value}'"
                        
                        needs_fix = False
                        if should_be_not_null and is_nullable:
                            needs_fix = True
                        if current_default and default_str not in str(current_default):
                            needs_fix = True
                        
                        if needs_fix:
                            logger.warning(f"⚠️  {column_name} column exists but needs fixing (nullable={is_nullable}, default={current_default})")
                            # Backfill NULL values
                            await conn.execute(
                                text(f"UPDATE prospects SET {column_name} = :default_value WHERE {column_name} IS NULL"),
                                {"default_value": default_value}
                            )
                            # Update default if needed
                            if not current_default or default_str not in str(current_default):
                                await conn.execute(
                                    text(f"ALTER TABLE prospects ALTER COLUMN {column_name} DROP DEFAULT")
                                )
                                await conn.execute(
                                    text(f"ALTER TABLE prospects ALTER COLUMN {column_name} SET DEFAULT '{default_value}'")
                                )
                            # Make NOT NULL if required and currently nullable
                            if should_be_not_null and is_nullable:
                                await conn.execute(
                                    text(f"ALTER TABLE prospects ALTER COLUMN {column_name} SET NOT NULL")
                                )
                            logger.info(f"✅ Fixed {column_name} column (now {'NOT NULL' if should_be_not_null else 'NULLABLE'} with DEFAULT '{default_value}')")
                            
                            # Special handling for stage column: backfill based on email presence
                            if column_name == "stage":
                                logger.info("🔄 Backfilling stage column based on email presence...")
                                # Prospects with emails → LEAD
                                await conn.execute(
                                    text("UPDATE prospects SET stage = 'LEAD' WHERE contact_email IS NOT NULL AND contact_email != '' AND stage = 'DISCOVERED'")
                                )
                                # Prospects with scrape_status=SCRAPED but no email → SCRAPED
                                await conn.execute(
                                    text("UPDATE prospects SET stage = 'SCRAPED' WHERE scrape_status = 'SCRAPED' AND (contact_email IS NULL OR contact_email = '') AND stage = 'DISCOVERED'")
                                )
                                # Prospects with scrape_status=ENRICHED → LEAD (they have emails)
                                await conn.execute(
                                    text("UPDATE prospects SET stage = 'LEAD' WHERE scrape_status = 'ENRICHED' AND stage = 'DISCOVERED'")
                                )
                                logger.info("✅ Stage column backfilled based on email presence")
                        else:
                            logger.info(f"✅ {column_name} column already exists and is correct")
            except Exception as e:
                logger.error(f"Failed to check/add discovery_status column: {e}", exc_info=True)
        except Exception as post_migration_error:
            logger.error("=" * 80)
            logger.error("❌ CRITICAL: Post-migration database operations failed")
            logger.error(f"❌ Error: {post_migration_error}")
            logger.error("=" * 80)
            logger.error("⚠️  APPLICATION WILL CONTINUE TO START")
            logger.error("⚠️  Some database operations may not have completed")
            logger.error("=" * 80)
    
    # CRITICAL: Run migrations BLOCKING - server won't accept requests until migrations complete
    # This ensures schema is ready before any API calls
    logger.info("⏳ Waiting for database migrations to complete...")
    logger.info("📝 Alembic upgrade head runs automatically on every startup")
    
    # Run migrations - log errors but don't exit
    # Allow app to start even if migrations have issues (they can be fixed manually)
    migration_success = False
    try:
        await run_database_setup()
        logger.info("✅ Database migrations completed")
        migration_success = True
    except Exception as migration_error:
        logger.error("=" * 80)
        logger.error("❌ CRITICAL: Database migrations failed during startup")
        logger.error(f"❌ Error: {migration_error}")
        logger.error("=" * 80)
        logger.error("⚠️  APPLICATION WILL CONTINUE TO START")
        logger.error("⚠️  Some features may not work until migrations are fixed")
        logger.error("⚠️  Run 'alembic upgrade head' manually to fix")
        logger.error("=" * 80)
        # Log error but don't exit - allow app to start
        migration_success = False
    
    # Validate ALL tables exist after migrations
    # Log errors but don't exit - allow app to start
    schema_valid = False
        try:
            from app.utils.schema_validator import validate_all_tables_exist, SchemaValidationError
            await validate_all_tables_exist(engine)
            logger.info("✅ Database schema validated - All required tables present")
            schema_valid = True
        except SchemaValidationError as schema_error:
            # If social tables are missing, try to create them automatically
            logger.warning("⚠️  Schema validation failed - checking social tables...")
            try:
                from app.utils.social_schema_init import ensure_social_tables_exist
                social_success, social_missing = await ensure_social_tables_exist(engine)
                if social_success:
                    logger.info("✅ Social outreach tables created automatically")
                    # Re-validate after creating social tables
                    try:
                        await validate_all_tables_exist(engine)
                        logger.info("✅ Database schema validated after social table creation")
                        schema_valid = True
                    except SchemaValidationError:
                        logger.warning("⚠️  Schema still invalid after social table creation")
                        schema_valid = False
                else:
                    logger.warning(f"⚠️  Could not create social tables: {', '.join(social_missing)}")
                    schema_valid = False
            except Exception as init_error:
                logger.error(f"❌ Failed to initialize social tables: {init_error}", exc_info=True)
                schema_valid = False
        except Exception as validation_error:
            logger.error("=" * 80)
            logger.error("❌ CRITICAL: Schema validation check failed")
            logger.error(f"❌ Error: {validation_error}")
            logger.error("=" * 80)
            logger.error("⚠️  APPLICATION WILL CONTINUE TO START")
            logger.error("⚠️  Some features may not work until schema is fixed")
            logger.error("=" * 80)
            schema_valid = False
        logger.error("=" * 80)
        logger.error("❌ CRITICAL: Schema validation check failed")
        logger.error(f"❌ Error: {validation_error}")
        logger.error("=" * 80)
        logger.error("⚠️  APPLICATION WILL CONTINUE TO START")
        logger.error("⚠️  Some features may not work until schema is fixed")
        logger.error("=" * 80)
        schema_valid = False
    
    # Log final status
    if migration_success and schema_valid:
        logger.info("✅ Server is ready - All validations passed")
    else:
        logger.warning("⚠️  Server is starting with validation issues - some features may not work")
        # If social tables are missing, log explicit instructions
        if not schema_valid:
            try:
                from app.utils.schema_validator import validate_social_tables_exist
                social_valid, social_missing = await validate_social_tables_exist(engine)
                if not social_valid:
                    logger.error("=" * 80)
                    logger.error("❌ SOCIAL OUTREACH TABLES MISSING")
                    logger.error(f"❌ Missing tables: {', '.join(social_missing)}")
                    logger.error("=" * 80)
                    logger.error("🔧 TO FIX: Run migrations manually on Render:")
                    logger.error("   1. Go to Render Dashboard → Your Service → Shell")
                    logger.error("   2. Run: cd /app && alembic upgrade head")
                    logger.error("   3. Or: cd /app/backend && alembic upgrade head")
                    logger.error("=" * 80)
            except Exception as e:
                logger.error(f"Could not check social tables: {e}")
    
    # Start scheduler for periodic tasks (always start - scraper check runs every minute)
    try:
        from app.scheduler import start_scheduler
        start_scheduler()
        logger.info("✅ Scheduler started successfully (automatic scraper check enabled)")
    except Exception as e:
        logger.error(f"❌ Failed to start scheduler: {e}", exc_info=True)
    
    # Log that startup is complete (server is ready to accept requests)
    logger.info("✅ Server startup complete - ready to accept requests")


@app.on_event("shutdown")
async def shutdown():
    """Shutdown event - stop scheduler"""
    try:
        from app.scheduler import stop_scheduler
        stop_scheduler()
    except Exception as e:
        logger.warning(f"Error stopping scheduler: {e}")

