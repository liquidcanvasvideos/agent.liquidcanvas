"""
FastAPI application entry point
"""
from fastapi import FastAPI, Request, Response, status
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

# Determine allowed CORS origins
cors_allow_origins_env = os.getenv("CORS_ALLOW_ORIGINS", "").strip()
required_origins = [
    "https://agent.liquidcanvas.art",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

env_origins = [o.strip() for o in cors_allow_origins_env.split(",") if o.strip()] if cors_allow_origins_env else []

# IMPORTANT: Never allow env var to accidentally remove required origins.
# Merge and keep stable order: required first, then any additional env origins.
# NOTE: The frontend may run on multiple domains (Vercel previews, custom domains).
# Since we do NOT use cookies (allow_credentials=False), it's safe to allow all origins.
allowed_origins = ["*"]


def _get_allowed_cors_origin(request: Request) -> str:
    origin = request.headers.get("origin")
    if origin and origin in allowed_origins:
        return origin
    return allowed_origins[0] if allowed_origins else "*"


# CRITICAL: Add CORS middleware FIRST, before any other middleware
# This ensures CORS headers are set on all responses, including errors
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.options("/{path:path}")
async def global_options_handler(path: str) -> Response:
    """Ensure CORS preflight always returns HTTP 200."""
    return Response(status_code=200)


@app.middleware("http")
async def add_cors_headers_fallback(request: Request, call_next):
    """
    Fallback middleware to guarantee CORS headers on all responses.
    This runs AFTER CORSMiddleware and ensures that even unexpected 500 errors
    include Access-Control-Allow-* headers so the frontend can read the response.
    """
    try:
        response = await call_next(request)
        requested_headers = request.headers.get("access-control-request-headers")
        # Always add CORS headers, even if CORSMiddleware didn't
        response.headers.setdefault("Access-Control-Allow-Origin", _get_allowed_cors_origin(request))
        response.headers.setdefault("Access-Control-Allow-Methods", "GET,POST,PUT,PATCH,DELETE,OPTIONS")
        response.headers.setdefault("Access-Control-Allow-Headers", requested_headers or "*")
        response.headers.setdefault("Access-Control-Expose-Headers", "*")
        return response
    except Exception as e:
        # If an exception occurs, create a response with CORS headers
        logger.error(f"Unhandled exception in middleware: {e}", exc_info=True)
        error_response = JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "error": str(e)}
        )
        requested_headers = request.headers.get("access-control-request-headers")
        error_response.headers["Access-Control-Allow-Origin"] = _get_allowed_cors_origin(request)
        error_response.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
        error_response.headers["Access-Control-Allow-Headers"] = requested_headers or "*"
        error_response.headers["Access-Control-Expose-Headers"] = "*"
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
    requested_headers = request.headers.get("access-control-request-headers")
    error_response.headers["Access-Control-Allow-Origin"] = _get_allowed_cors_origin(request)
    error_response.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
    error_response.headers["Access-Control-Allow-Headers"] = requested_headers or "*"
    error_response.headers["Access-Control-Expose-Headers"] = "*"
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
    requested_headers = request.headers.get("access-control-request-headers")
    error_response.headers["Access-Control-Allow-Origin"] = _get_allowed_cors_origin(request)
    error_response.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
    error_response.headers["Access-Control-Allow-Headers"] = requested_headers or "*"
    error_response.headers["Access-Control-Expose-Headers"] = "*"
    return error_response

# Include routers
from app.api import auth, settings, scraper, pipeline, manual, health, social
from app.api import social_pipeline  # Separate pipeline API for social outreach
from app.api import diagnostics  # Database forensics endpoints
from app.api import integrations  # Social integrations and OAuth management
from app.api import admin  # Admin endpoints
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
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])  # Admin endpoints
app.include_router(social.router, tags=["social"])  # Social outreach - separate from website outreach
app.include_router(social_pipeline.router, tags=["social-pipeline"])  # Social pipeline - completely separate from website pipeline
app.include_router(diagnostics.router, tags=["diagnostics"])  # Database forensics endpoints
app.include_router(integrations.router, prefix="/api", tags=["integrations"])  # Social integrations and OAuth management

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


@app.get("/api/test/gemini")
async def test_gemini():
    """Test Gemini API directly"""
    try:
        from app.clients.gemini import GeminiClient
        client = GeminiClient()
        
        import httpx
        url = f"{client.BASE_URL}/models/{client.model}:generateContent?key={client.api_key}"
        payload = {
            "contents": [{"parts": [{"text": "test"}]}],
            "generationConfig": {"maxOutputTokens": 1}
        }
        
        async with httpx.AsyncClient(timeout=10.0) as http_client:
            response = await http_client.post(url, json=payload)
            return {
                "status": response.status_code,
                "model": client.model,
                "response": response.text[:200] if response.text else None
            }
    except Exception as e:
        return {"error": str(e)}


@app.get("/health")
async def health():
    """Health check endpoint - responds immediately for Render deployment checks"""
    return {"status": "healthy", "service": "art-outreach-api"}


@app.get("/health/gemini")
async def health_gemini():
    """Expose Gemini validation status captured at startup."""
    return getattr(app.state, "gemini_status", {"configured": False, "valid": False})

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
    """Startup event - verify database connectivity and schema"""
    # Log that server is starting (important for Render deployment checks)
    logger.info("🚀 Server starting up...")
    logger.info(f"📡 Server will listen on port {os.getenv('PORT', '8000')}")
    
    # Check if AUTO_MIGRATE environment variable is set
    # If set to "true" or "1", run migrations automatically on startup
    # If set to "false" or "0", never run migrations automatically
    # If not set (default), run migrations only if schema mismatch is detected (smart auto-migrate)
    auto_migrate_env = os.getenv("AUTO_MIGRATE", "").lower()
    
    if auto_migrate_env in ("true", "1", "yes"):
        auto_migrate = True
        logger.info("🔄 AUTO_MIGRATE=true - migrations will run automatically on startup")
    elif auto_migrate_env in ("false", "0", "no"):
        auto_migrate = False
        logger.info("🔍 AUTO_MIGRATE=false - migrations will NOT run automatically")
        logger.info("💡 Run migrations manually: alembic upgrade head")
    else:
        # Default: Smart auto-migrate - only run if schema mismatch detected
        auto_migrate = None  # None means "smart" mode
        logger.info("🔍 AUTO_MIGRATE not set - using smart auto-migrate mode")
        logger.info("💡 Migrations will run automatically only if schema mismatch is detected")
        logger.info("💡 Set AUTO_MIGRATE=true to always run, AUTO_MIGRATE=false to never run")
    
    import asyncio

    # Validate Gemini configuration early to surface auth/model issues
    try:
        from app.clients.gemini import GeminiClient
        gemini_client = GeminiClient()
        is_valid = await gemini_client.validate_model()
        app.state.gemini_status = {
            "configured": True,
            "model": gemini_client.model,
            "base_url": gemini_client.BASE_URL,
            "valid": bool(is_valid),
        }
        if not is_valid:
            logger.error("❌ [STARTUP] Gemini model validation failed. Check API key/model availability.")
        else:
            logger.info("✅ [STARTUP] Gemini model validated successfully.")
    except Exception as e:
        app.state.gemini_status = {
            "configured": False,
            "valid": False,
            "error": str(e),
        }
        logger.error(f"❌ [STARTUP] Gemini validation error: {e}", exc_info=True)
    
    async def run_migrations_safely():
        """Run migrations with error handling - only if AUTO_MIGRATE is enabled"""
        if not auto_migrate:
            return
        
        try:
            from alembic.config import Config
            from alembic import command
            
            logger.info("🔄 Running database migrations on startup...")
            logger.info("=" * 60)
            
            # Get the backend directory path
            backend_dir = os.path.dirname(os.path.dirname(__file__))
            alembic_ini_path = os.path.join(backend_dir, "alembic.ini")
            
            if not os.path.exists(alembic_ini_path):
                logger.error(f"❌ alembic.ini not found at {alembic_ini_path}")
                logger.error("⚠️  Skipping migrations - app will continue to start")
                return
            
            alembic_cfg = Config(alembic_ini_path)
            
            # Get database URL and set in config
            database_url = os.getenv("DATABASE_URL")
            if database_url:
                if database_url.startswith("postgresql+asyncpg://"):
                    # Convert to sync format and remove unsupported parameters
                    sync_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
                    # Remove pgbouncer and sslmode parameters (not supported by psycopg2)
                    if "?" in sync_url:
                        base_url, query_string = sync_url.split("?", 1)
                        query_params = [p for p in query_string.split("&") 
                                      if not p.lower().startswith(("pgbouncer=", "sslmode="))]
                        sync_url = f"{base_url}?{'&'.join(query_params)}" if query_params else base_url
                    alembic_cfg.set_main_option("sqlalchemy.url", sync_url)
                    logger.info("✅ Converted asyncpg URL to psycopg2 format for Alembic (removed unsupported params)")
            
            # Change to the directory containing alembic.ini
            alembic_dir = os.path.dirname(os.path.abspath(alembic_ini_path))
            original_cwd = os.getcwd()
            try:
                os.chdir(alembic_dir)
                logger.info(f"📁 Changed to directory: {alembic_dir}")
                logger.info("🚀 Executing: alembic upgrade head")
                
                # Run migrations - catch SystemExit from Alembic to prevent app crash
                try:
                    logger.info("🚀 Starting migration upgrade to head...")
                    command.upgrade(alembic_cfg, "head")
                    logger.info("=" * 60)
                    logger.info("✅ Database migrations completed successfully")
                    logger.info("=" * 60)
                except Exception as migration_run_error:
                    # Catch any exceptions during migration execution
                    logger.error(f"❌ Migration execution error: {migration_run_error}")
                    raise
                except SystemExit as sys_exit:
                    # Alembic may call sys.exit() on errors - catch and convert to exception
                    exit_code = sys_exit.code if hasattr(sys_exit, 'code') else 1
                    logger.error(f"❌ Alembic exited with code {exit_code}")
                    raise Exception(f"Alembic migration failed with exit code {exit_code}. Check migration files and database state.") from sys_exit
            finally:
                os.chdir(original_cwd)
                
        except Exception as migration_error:
            logger.error("=" * 80)
            logger.error("❌ CRITICAL: Migration execution failed")
            logger.error(f"❌ Error type: {type(migration_error).__name__}")
            logger.error(f"❌ Error message: {str(migration_error)}")
            logger.error("=" * 80)
            logger.error("⚠️  APPLICATION WILL CONTINUE TO START")
            logger.error("⚠️  Some features may not work until migrations are fixed")
            logger.error("⚠️  Run 'alembic upgrade head' manually to fix")
            logger.error("=" * 80)
            # Don't exit - allow app to start even if migrations fail
    
    async def verify_database_state():
        """
        Verify database state WITHOUT running migrations.
        
        Migrations should be run at deploy time, not on every app boot.
        This prevents crash loops and repeated migration execution.
        """
        try:
            from alembic.config import Config
            from alembic.script import ScriptDirectory
            from sqlalchemy import create_engine, text
            
            logger.info("🔍 Verifying database state (migrations should be run at deploy time)...")
            logger.info("=" * 60)
            
            # Get database URL
            database_url = os.getenv("DATABASE_URL")
            if not database_url:
                logger.warning("⚠️  DATABASE_URL not set - skipping database verification")
                return
            
            # Convert asyncpg URL to psycopg2 for sync operations
            sync_url = database_url.replace("postgresql+asyncpg://", "postgresql://") if database_url.startswith("postgresql+asyncpg://") else database_url
            # Remove pgbouncer and sslmode parameters (not supported by psycopg2)
            if "?" in sync_url:
                base_url, query_string = sync_url.split("?", 1)
                query_params = [p for p in query_string.split("&") 
                              if not p.lower().startswith(("pgbouncer=", "sslmode="))]
                sync_url = f"{base_url}?{'&'.join(query_params)}" if query_params else base_url
            sync_engine = create_engine(sync_url, pool_pre_ping=True, connect_args={"sslmode": "require"} if ".supabase.co" in sync_url else {})
            
            try:
                with sync_engine.connect() as conn:
                    # Check if alembic_version table exists and has correct revision
                    version_table_check = conn.execute(text("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_schema = 'public' 
                            AND table_name = 'alembic_version'
                        )
                    """))
                    version_table_exists = version_table_check.scalar()
                    
                    if not version_table_exists:
                        logger.warning("=" * 80)
                        logger.warning("⚠️  alembic_version table is MISSING!")
                        logger.warning("⚠️  Run migrations manually: alembic upgrade head")
                        logger.warning("⚠️  Or use: python backend/fix_alembic_version.py")
                        logger.warning("=" * 80)
                        sync_engine.dispose()
                        return
                    
                    # Get current revision
                    version_result = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
                    version_row = version_result.fetchone()
                    current_rev = version_row[0] if version_row else None
                    
                    # Get head revision from script
                    backend_dir = os.path.dirname(os.path.dirname(__file__))
                    alembic_ini_path = os.path.join(backend_dir, "alembic.ini")
                    
                    if not os.path.exists(alembic_ini_path):
                        logger.warning(f"⚠️  alembic.ini not found at {alembic_ini_path}")
                        sync_engine.dispose()
                        return
                    
                    alembic_cfg = Config(alembic_ini_path)
                    if database_url.startswith("postgresql+asyncpg://"):
                        sync_url_for_cfg = database_url.replace("postgresql+asyncpg://", "postgresql://")
                        alembic_cfg.set_main_option("sqlalchemy.url", sync_url_for_cfg)
                    
                    script = ScriptDirectory.from_config(alembic_cfg)
                    heads = script.get_revision("heads")
                    head_rev = heads.revision if heads else None
                    
                    logger.info("=" * 60)
                    logger.info("📊 DATABASE STATE VERIFICATION")
                    logger.info(f"   alembic_version table: ✅ EXISTS")
                    logger.info(f"   Current DB revision: {current_rev}")
                    logger.info(f"   Head revision: {head_rev}")
                    
                    if current_rev == head_rev:
                        logger.info("   ✅ Database is at latest migration")
                    else:
                        logger.warning("=" * 80)
                        logger.warning(f"⚠️  Database is NOT at latest migration!")
                        logger.warning(f"⚠️  Current: {current_rev}, Expected: {head_rev}")
                        logger.warning("⚠️  Run migrations manually: alembic upgrade head")
                        logger.warning("⚠️  Or use: python backend/fix_alembic_version.py")
                        logger.warning("=" * 80)
                    
                    logger.info("=" * 60)
                    
            finally:
                sync_engine.dispose()
            
            # Verify database connectivity only
            try:
                async with engine.begin() as conn:
                    await conn.execute(text("SELECT 1"))
                logger.info("✅ Database connectivity verified")
            except Exception as db_err:
                logger.error(f"❌ Database connectivity check failed: {db_err}")
                # Don't exit - allow app to start even if DB is temporarily unavailable
                # This prevents deployment failures
                
            # Non-fatal schema diagnostics check
            try:
                from app.utils.schema_validator import get_full_schema_diagnostics
                diagnostics = await get_full_schema_diagnostics(engine)
                if not diagnostics.get("schema_match", False):
                    logger.warning("=" * 80)
                    logger.warning("⚠️  SCHEMA MISMATCH DETECTED (non-fatal)")
                    logger.warning(f"⚠️  Missing columns: {', '.join(diagnostics.get('missing_columns', []))}")
                    logger.warning("⚠️  This may cause query failures - ensure migrations have run")
                    logger.warning("⚠️  Run: alembic upgrade head")
                    logger.warning("=" * 80)
                else:
                    logger.info("✅ Schema consistency check passed - model columns match database")
            except Exception as diag_err:
                logger.warning(f"⚠️  Could not run schema diagnostics: {diag_err}")
                
        except Exception as verify_err:
            logger.warning(f"⚠️  Could not verify database state: {verify_err}")
            # Don't exit - allow app to start
            # Migrations can be run manually if needed
        
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
            
            # AUTOMATIC FIX: Check and add missing social columns if needed
            try:
                from sqlalchemy import text
                async with engine.begin() as conn:
                    # Check for all required social columns
                    result = await conn.execute(
                        text("""
                            SELECT column_name 
                            FROM information_schema.columns 
                            WHERE table_name = 'prospects' 
                            AND column_name IN ('source_type', 'source_platform', 'profile_url', 'username', 'display_name', 'follower_count', 'engagement_rate')
                            ORDER BY column_name
                        """)
                    )
                    existing_columns = {row[0] for row in result.fetchall()}
                    required_columns = {
                        'source_type': 'VARCHAR',
                        'source_platform': 'VARCHAR',
                        'profile_url': 'TEXT',
                        'username': 'VARCHAR',
                        'display_name': 'VARCHAR',
                        'follower_count': 'INTEGER',
                        'engagement_rate': 'NUMERIC',
                        'bio_text': 'TEXT',
                        'external_links': 'JSONB',
                        'scraped_at': 'TIMESTAMP WITH TIME ZONE'
                    }
                    missing_columns = {col: col_type for col, col_type in required_columns.items() if col not in existing_columns}
                    
                    if missing_columns:
                        logger.warning("=" * 80)
                        logger.warning(f"⚠️  Missing {len(missing_columns)} Prospect columns - applying automatic fix...")
                        logger.warning(f"⚠️  Missing: {', '.join(missing_columns.keys())}")
                        logger.warning("⚠️  This should not happen if migrations ran successfully!")
                        
                        # Build ALTER TABLE statement
                        alter_statements = []
                        for col_name, col_type in missing_columns.items():
                            if col_type == 'NUMERIC':
                                alter_statements.append(f"ADD COLUMN {col_name} NUMERIC(5, 2)")
                            elif col_type == 'JSONB':
                                alter_statements.append(f"ADD COLUMN {col_name} JSONB")
                            elif col_type == 'TIMESTAMP WITH TIME ZONE':
                                alter_statements.append(f"ADD COLUMN {col_name} TIMESTAMP WITH TIME ZONE")
                            elif col_type == 'TEXT':
                                alter_statements.append(f"ADD COLUMN {col_name} TEXT")
                            elif col_type == 'INTEGER':
                                alter_statements.append(f"ADD COLUMN {col_name} INTEGER")
                            elif col_type == 'VARCHAR':
                                alter_statements.append(f"ADD COLUMN {col_name} VARCHAR")
                            else:
                                alter_statements.append(f"ADD COLUMN {col_name} {col_type}")
                        
                        alter_sql = f"ALTER TABLE prospects {', '.join(alter_statements)}"
                        
                        try:
                            await conn.execute(text(alter_sql))
                            # Note: engine.begin() auto-commits on exit, no manual commit needed
                            logger.info("✅ Automatic schema fix applied successfully")
                            logger.info(f"✅ Added {len(missing_columns)} columns to prospects table")
                            
                            # Verify the fix
                            verify_result = await conn.execute(
                                text("""
                                    SELECT column_name 
                                    FROM information_schema.columns 
                                    WHERE table_name = 'prospects' 
                                    AND column_name IN ('source_type', 'source_platform', 'profile_url', 'username', 'display_name', 'follower_count', 'engagement_rate', 'bio_text', 'external_links', 'scraped_at')
                                """)
                            )
                            verified_columns = {row[0] for row in verify_result.fetchall()}
                            
                            if len(verified_columns) == 10:
                                logger.info("✅ All 10 Prospect columns verified after automatic fix")
                                # Test SELECT query
                                try:
                                    test_result = await conn.execute(
                                        text("SELECT source_type, source_platform FROM prospects LIMIT 1")
                                    )
                                    test_result.fetchone()  # Consume result
                                    logger.info("✅ SELECT query test passed - schema fix successful")
                                except Exception as test_err:
                                    logger.error(f"❌ SELECT query test failed: {test_err}")
                            else:
                                    logger.warning(f"⚠️  Verification incomplete - only {len(verified_columns)}/10 columns found")
                        except Exception as fix_err:
                            logger.error("=" * 80)
                            logger.error(f"❌ CRITICAL: Automatic schema fix failed: {fix_err}")
                            logger.error(f"❌ Error type: {type(fix_err).__name__}")
                            logger.error("❌ Manual intervention required - run fix_schema_now.py or apply SQL manually")
                            logger.error("=" * 80)
                            await conn.rollback()
                    else:
                        logger.info("✅ All Prospect columns verified: source_type, source_platform, profile_url, username, display_name, follower_count, engagement_rate, bio_text, external_links, scraped_at")
            except Exception as social_check_err:
                logger.error(f"❌ Error checking/fixing social columns: {social_check_err}", exc_info=True)
            
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
                    
                    # CRITICAL: Check if social columns exist (source_type, source_platform, etc.)
                    # These are required for social outreach feature
                    result = await conn.execute(
                        text("""
                            SELECT column_name 
                            FROM information_schema.columns 
                            WHERE table_name = 'prospects' 
                            AND column_name IN ('source_type', 'source_platform', 'profile_url', 'username')
                        """)
                    )
                    existing_social_columns = {row[0] for row in result.fetchall()}
                    required_columns = {'source_type', 'source_platform', 'profile_url', 'username'}
                    missing_columns = required_columns - existing_social_columns
                    
                    if missing_columns:
                        logger.error("=" * 80)
                        logger.error("❌ CRITICAL: Social outreach columns are missing!")
                        logger.error(f"❌ Missing columns: {', '.join(missing_columns)}")
                        logger.error("❌ Social outreach feature will NOT work until migration is applied")
                        logger.error("❌ Migration: add_social_columns_to_prospects")
                        logger.error("❌ Run: alembic upgrade head")
                        logger.error("=" * 80)
                    else:
                        logger.info("✅ Social outreach columns exist (source_type, source_platform, etc.)")
                    
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
    # Smart auto-migrate: Check schema first, then decide if migrations needed
    if auto_migrate is None:  # Smart mode - check schema first
        logger.info("🔍 Smart auto-migrate: Checking schema state...")
        try:
            # Quick schema check - see if bio_text column exists
            from sqlalchemy import create_engine, text
            from urllib.parse import urlparse, urlunparse, quote_plus
            database_url = os.getenv("DATABASE_URL")
            if database_url:
                # Convert asyncpg URL to sync URL for schema check
                # Properly handle special characters in password by using urllib.parse
                if database_url.startswith("postgresql+asyncpg://"):
                    # Remove the +asyncpg part
                    sync_url = database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
                    # Remove pgbouncer and sslmode parameters (not supported by psycopg2)
                    if "?" in sync_url:
                        base_url, query_string = sync_url.split("?", 1)
                        query_params = [p for p in query_string.split("&") 
                                      if not p.lower().startswith(("pgbouncer=", "sslmode="))]
                        sync_url = f"{base_url}?{'&'.join(query_params)}" if query_params else base_url
                elif database_url.startswith("postgresql://"):
                    sync_url = database_url
                else:
                    sync_url = database_url
                
                # Parse URL to ensure proper encoding of special characters
                # This is critical for Supabase passwords with special chars like '!'
                parsed = urlparse(sync_url)
                if parsed.password:
                    # URL-encode the password if it contains special characters
                    encoded_password = quote_plus(parsed.password)
                    netloc = f"{parsed.username}:{encoded_password}@{parsed.hostname}"
                    if parsed.port:
                        netloc += f":{parsed.port}"
                    sync_url = urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
                
                sync_engine = create_engine(sync_url, pool_pre_ping=True)
                try:
                    with sync_engine.connect() as conn:
                        # Check if bio_text column exists (indicator of schema mismatch)
                        column_check = conn.execute(text("""
                            SELECT column_name 
                            FROM information_schema.columns 
                            WHERE table_name = 'prospects' 
                            AND column_name = 'bio_text'
                        """))
                        bio_text_exists = column_check.fetchone() is not None
                        
                        if not bio_text_exists:
                            logger.warning("=" * 80)
                            logger.warning("⚠️  Schema mismatch detected: bio_text column missing")
                            logger.warning("🔄 Smart auto-migrate: Running migrations automatically...")
                            logger.warning("=" * 80)
                            auto_migrate = True  # Enable migrations for this startup
                        else:
                            logger.info("✅ Schema check passed - all required columns exist")
                            auto_migrate = False  # No migrations needed
                finally:
                    sync_engine.dispose()
            else:
                logger.warning("⚠️  DATABASE_URL not set - skipping smart auto-migrate check")
                auto_migrate = False
        except Exception as schema_check_err:
            logger.warning(f"⚠️  Could not check schema state: {schema_check_err}")
            logger.warning("⚠️  Skipping smart auto-migrate - run migrations manually if needed")
            auto_migrate = False
    
    # Run migrations if AUTO_MIGRATE is enabled (explicitly or via smart mode)
    migration_success = False
    if auto_migrate:
        logger.info("=" * 80)
        logger.info("🔄 AUTO_MIGRATE enabled - starting migration execution...")
        logger.info("=" * 80)
        try:
            await run_migrations_safely()
            logger.info("=" * 80)
            logger.info("✅ Database migrations completed successfully")
            logger.info("=" * 80)
            migration_success = True
        except Exception as migration_err:
            logger.error("=" * 80)
            logger.error("❌ CRITICAL: Migration execution failed")
            logger.error(f"❌ Error type: {type(migration_err).__name__}")
            logger.error(f"❌ Error message: {str(migration_err)}")
            logger.error("=" * 80)
            logger.error("⚠️  APPLICATION WILL CONTINUE TO START")
            logger.error("⚠️  Some features may not work until migrations are fixed")
            logger.error("⚠️  Run 'alembic upgrade head' manually to fix")
            logger.error("=" * 80)
            migration_success = False
            # Continue to start app even if migrations fail - DO NOT EXIT
    
    # Auto-fix discovery_query_id column if missing (non-blocking)
    try:
        from sqlalchemy import text
        from app.db.database import AsyncSessionLocal
        
        logger.info("🔍 Checking for discovery_query_id column...")
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
                logger.info("=" * 80)
                logger.info("⚠️  discovery_query_id column missing - adding it automatically...")
                logger.info("=" * 80)
                await db.execute(text("ALTER TABLE prospects ADD COLUMN discovery_query_id UUID"))
                await db.execute(text("CREATE INDEX IF NOT EXISTS ix_prospects_discovery_query_id ON prospects(discovery_query_id)"))
                await db.commit()
                logger.info("=" * 80)
                logger.info("✅ Successfully added discovery_query_id column and index")
                logger.info("=" * 80)
            else:
                logger.info("✅ discovery_query_id column already exists")
    except Exception as fix_error:
        logger.error("=" * 80)
        logger.error(f"❌ Could not auto-fix discovery_query_id column: {fix_error}")
        logger.error("=" * 80)
        import traceback
        logger.error(traceback.format_exc())
        # Non-blocking - continue startup

    # Ensure email attachments table exists (safety net for missing migrations)
    try:
        from app.utils.attachments_schema_init import ensure_email_attachments_table_exists

        attachments_ready, attachments_missing = await ensure_email_attachments_table_exists(engine)
        if not attachments_ready:
            logger.warning(
                f"⚠️  Email attachments table missing or failed to create: {', '.join(attachments_missing)}"
            )
    except Exception as attachments_error:
        logger.error(
            f"❌ Failed to ensure email_attachments table exists: {attachments_error}",
            exc_info=True,
        )

    # Validate schema after migrations
    # Use the schema validator to check if all required columns exist
    schema_valid = False
    try:
        from app.utils.schema_validator import validate_prospect_schema
        from app.db.database import AsyncSessionLocal
        
        async with AsyncSessionLocal() as db_session:
            validation_result = await validate_prospect_schema(db_session)
            if validation_result.get("valid", False):
                logger.info("✅ Database schema validated - All required columns present")
                schema_valid = True
            else:
                missing = validation_result.get("missing_columns", [])
                logger.warning(f"⚠️  Some columns missing: {', '.join(missing)}")
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
    
    # Log final status
    if migration_success and schema_valid:
        logger.info("✅ Server is ready - All validations passed")
    else:
        logger.warning("⚠️  Server is starting with validation issues - some features may not work")
    
    # Scheduler disabled to prevent auto-triggering on refresh
    logger.info("⚠️ Scheduler disabled - auto-drafting will not run")
    
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

