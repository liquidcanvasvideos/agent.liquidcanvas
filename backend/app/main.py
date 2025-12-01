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
from app.api import auth, settings
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(prospects.router, prefix="/api/prospects", tags=["prospects"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])

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
    """Health check endpoint"""
    return {"status": "healthy"}


@app.on_event("startup")
async def startup():
    """Startup event - run migrations and start scheduler"""
    # Run database migrations on startup (for free tier - no pre-deploy command)
    try:
        import asyncio
        from alembic.config import Config
        from alembic import command
        
        logger.info("Running database migrations on startup...")
        
        # Get the backend directory path
        import os
        backend_dir = os.path.dirname(os.path.dirname(__file__))
        alembic_cfg = Config(os.path.join(backend_dir, "alembic.ini"))
        
        # Run migrations
        try:
            command.upgrade(alembic_cfg, "head")
            logger.info("✅ Database migrations completed successfully")
        except Exception as migration_error:
            logger.warning(f"Migration failed (may be first run): {migration_error}")
            # Try to create tables directly if migrations fail (first deploy)
            try:
                async with engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)
                logger.info("✅ Created database tables directly (first deploy)")
            except Exception as create_error:
                logger.error(f"Failed to create tables: {create_error}")
    except Exception as e:
        logger.warning(f"Migration setup failed: {e}")
        # Fallback: create tables directly
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("✅ Created database tables directly (fallback)")
        except Exception as create_error:
            logger.error(f"Failed to create tables: {create_error}")
    
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
    except Exception as e:
        logger.error(f"Failed to check/add discovery_query_id column: {e}", exc_info=True)
    
    # Start scheduler for periodic tasks (only if explicitly enabled)
    try:
        enable_automation = os.getenv("ENABLE_AUTOMATION", "false").lower() == "true"
        if enable_automation:
            from app.scheduler import start_scheduler
            start_scheduler()
            logger.info("Scheduler started successfully (automation enabled)")
        else:
            logger.info("Scheduler not started (ENABLE_AUTOMATION is false)")
    except Exception as e:
        logger.warning(f"Failed to start scheduler: {e}")


@app.on_event("shutdown")
async def shutdown():
    """Shutdown event - stop scheduler"""
    try:
        from app.scheduler import stop_scheduler
        stop_scheduler()
    except Exception as e:
        logger.warning(f"Error stopping scheduler: {e}")

