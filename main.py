"""
Autonomous Art Outreach Scraper - Main FastAPI Application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from db.database import engine, Base
from api import routes
from utils.config import settings
from utils.logging_config import setup_logging

# Setup logging
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events"""
    # Startup: Create database tables
    Base.metadata.create_all(bind=engine)
    
    # Initialize background jobs
    from jobs.scheduler import start_scheduler
    start_scheduler()
    
    yield
    
    # Shutdown: Cleanup if needed
    pass


app = FastAPI(
    title="Autonomous Art Outreach Scraper",
    description="Production-grade web scraper for art-related websites and automated outreach",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(routes.router, prefix="/api/v1", tags=["api"])

# Include dashboard routes (no prefix for cleaner URLs)
from api.dashboard_routes import router as dashboard_router
app.include_router(dashboard_router, prefix="/api/v1", tags=["dashboard"])

# Include settings routes
from api.settings_routes import router as settings_router
app.include_router(settings_router, prefix="/api/v1", tags=["settings"])

# Include discovery routes
from api.discovery_routes import router as discovery_router
app.include_router(discovery_router, prefix="/api/v1", tags=["discovery"])

# Include debug routes
from api.debug_routes import router as debug_router
app.include_router(debug_router, prefix="/api/v1/debug", tags=["debug"])

# Include diagnostic routes
from api.diagnostic_routes import router as diagnostic_router
app.include_router(diagnostic_router, prefix="/api/v1", tags=["diagnostic"])

# Include auth routes
from api.auth_routes import router as auth_router
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Autonomous Art Outreach Scraper API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )

