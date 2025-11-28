"""
FastAPI application entry point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import jobs, prospects
from app.db.database import engine, Base
import os
import logging

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Art Outreach Automation API",
    description="API for automated art website discovery and outreach",
    version="2.0.0"
)

# CORS configuration
cors_origins = [
    "http://localhost:3000",
    "http://localhost:8000",
    "https://agent.liquidcanvas.art",
]

if os.getenv("CORS_ORIGINS"):
    cors_origins.extend(os.getenv("CORS_ORIGINS").split(","))

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(prospects.router, prefix="/api/prospects", tags=["prospects"])

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
    
    # Start scheduler for periodic tasks
    try:
        from app.scheduler import start_scheduler
        start_scheduler()
        logger.info("Scheduler started successfully")
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

