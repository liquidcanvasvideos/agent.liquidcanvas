"""
Global scraper control system - Master switch, automation, scheduling
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
import logging

from app.db.database import get_db
from app.models.settings import Settings
from app.models.job import Job

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================
# Helper functions for scraper settings
# ============================================

async def get_scraper_setting(db: AsyncSession, key: str, default: Any = None) -> Any:
    """Get a scraper setting value from DB"""
    try:
        result = await db.execute(
            select(Settings).where(Settings.key == f"scraper_{key}")
        )
        setting = result.scalar_one_or_none()
        if setting and setting.value:
            return setting.value.get("value", default)
        return default
    except Exception as e:
        logger.error(f"Error getting scraper setting {key}: {e}", exc_info=True)
        return default


async def set_scraper_setting(db: AsyncSession, key: str, value: Any) -> None:
    """Set a scraper setting value in DB"""
    try:
        result = await db.execute(
            select(Settings).where(Settings.key == f"scraper_{key}")
        )
        setting = result.scalar_one_or_none()
        
        if setting:
            setting.value = {"value": value}
            setting.updated_at = func.now()
        else:
            setting = Settings(
                key=f"scraper_{key}",
                value={"value": value}
            )
            db.add(setting)
        
        await db.commit()
        await db.refresh(setting)
    except Exception as e:
        await db.rollback()
        logger.error(f"Error setting scraper setting {key}: {e}", exc_info=True)
        raise


async def check_master_switch(db: AsyncSession) -> bool:
    """Check if master switch is enabled"""
    enabled = await get_scraper_setting(db, "master_enabled", False)
    return bool(enabled)


async def validate_master_switch(db: AsyncSession) -> None:
    """Validate master switch is ON, raise error if OFF"""
    if not await check_master_switch(db):
        raise HTTPException(
            status_code=403,
            detail="Master switch disabled. Please enable the master switch to run scraping operations."
        )


# ============================================
# Request/Response Models
# ============================================

class MasterSwitchRequest(BaseModel):
    enabled: bool


class MasterSwitchResponse(BaseModel):
    enabled: bool
    message: str


class AutoSwitchRequest(BaseModel):
    enabled: bool


class AutoSwitchResponse(BaseModel):
    enabled: bool
    message: str
    can_enable: bool
    missing_fields: List[str]


class ScraperConfigRequest(BaseModel):
    locations: List[str] = Field(default_factory=list)
    categories: List[str] = Field(default_factory=list)
    interval: str = Field(default="1h")  # "1h", "2h", "3h", "4h", "5h", "daily", "weekly"


class ScraperConfigResponse(BaseModel):
    locations: List[str]
    categories: List[str]
    interval: str
    next_run_at: Optional[str] = None


class ScraperStatusResponse(BaseModel):
    master_enabled: bool
    auto_enabled: bool
    locations: List[str]
    categories: List[str]
    interval: str
    next_run_at: Optional[str] = None
    status: str  # "idle", "running", "disabled"
    can_enable_auto: bool
    missing_fields: List[str]


# ============================================
# Master Switch Endpoints
# ============================================

@router.get("/master", response_model=MasterSwitchResponse)
async def get_master_switch(db: AsyncSession = Depends(get_db)):
    """Get master switch status"""
    enabled = await check_master_switch(db)
    return MasterSwitchResponse(
        enabled=enabled,
        message="Master switch is enabled" if enabled else "Master switch is disabled"
    )


@router.post("/master", response_model=MasterSwitchResponse)
async def set_master_switch(
    request: MasterSwitchRequest,
    db: AsyncSession = Depends(get_db)
):
    """Set master switch status"""
    await set_scraper_setting(db, "master_enabled", request.enabled)
    
    # If disabling master, also disable auto
    if not request.enabled:
        await set_scraper_setting(db, "auto_enabled", False)
        logger.info("Master switch disabled - auto scraper also disabled")
    
    return MasterSwitchResponse(
        enabled=request.enabled,
        message="Master switch enabled" if request.enabled else "Master switch disabled"
    )


# ============================================
# Auto Switch Endpoints
# ============================================

@router.get("/automatic", response_model=AutoSwitchResponse)
async def get_auto_switch(db: AsyncSession = Depends(get_db)):
    """Get auto switch status and validation"""
    master_enabled = await check_master_switch(db)
    auto_enabled = await get_scraper_setting(db, "auto_enabled", False)
    
    locations = await get_scraper_setting(db, "locations", [])
    categories = await get_scraper_setting(db, "categories", [])
    interval = await get_scraper_setting(db, "interval", None)
    
    missing_fields = []
    if not locations or len(locations) == 0:
        missing_fields.append("locations")
    if not categories or len(categories) == 0:
        missing_fields.append("categories")
    if not interval:
        missing_fields.append("interval")
    
    can_enable = master_enabled and len(missing_fields) == 0
    
    return AutoSwitchResponse(
        enabled=auto_enabled,
        message="Auto scraper is enabled" if auto_enabled else "Auto scraper is disabled",
        can_enable=can_enable,
        missing_fields=missing_fields
    )


@router.post("/automatic", response_model=AutoSwitchResponse)
async def set_auto_switch(
    request: AutoSwitchRequest,
    db: AsyncSession = Depends(get_db)
):
    """Set auto switch status with validation"""
    master_enabled = await check_master_switch(db)
    
    if request.enabled and not master_enabled:
        raise HTTPException(
            status_code=400,
            detail="Cannot enable automatic scraper: Master switch must be enabled first."
        )
    
    if request.enabled:
        # Validate required fields
        locations = await get_scraper_setting(db, "locations", [])
        categories = await get_scraper_setting(db, "categories", [])
        interval = await get_scraper_setting(db, "interval", None)
        
        missing_fields = []
        if not locations or len(locations) == 0:
            missing_fields.append("locations")
        if not categories or len(categories) == 0:
            missing_fields.append("categories")
        if not interval:
            missing_fields.append("interval")
        
        if missing_fields:
            raise HTTPException(
                status_code=400,
                detail=f"You must select location, category, and interval before enabling automation. Missing: {', '.join(missing_fields)}"
            )
        
        # Calculate next run time
        await calculate_and_set_next_run(db, interval)
    
    await set_scraper_setting(db, "auto_enabled", request.enabled)
    
    return AutoSwitchResponse(
        enabled=request.enabled,
        message="Auto scraper enabled" if request.enabled else "Auto scraper disabled",
        can_enable=True,
        missing_fields=[]
    )


# ============================================
# Config Endpoint
# ============================================

@router.post("/config", response_model=ScraperConfigResponse)
async def set_scraper_config(
    request: ScraperConfigRequest,
    db: AsyncSession = Depends(get_db)
):
    """Set scraper configuration (locations, categories, interval)"""
    master_enabled = await check_master_switch(db)
    
    if not master_enabled:
        raise HTTPException(
            status_code=400,
            detail="Cannot save config: Master switch must be enabled first."
        )
    
    # Validate interval
    valid_intervals = ["1h", "2h", "3h", "4h", "5h", "daily", "weekly"]
    if request.interval not in valid_intervals:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid interval. Must be one of: {', '.join(valid_intervals)}"
        )
    
    await set_scraper_setting(db, "locations", request.locations)
    await set_scraper_setting(db, "categories", request.categories)
    await set_scraper_setting(db, "interval", request.interval)
    
    # If auto is enabled, recalculate next run
    auto_enabled = await get_scraper_setting(db, "auto_enabled", False)
    if auto_enabled:
        await calculate_and_set_next_run(db, request.interval)
    
    next_run_at = await get_scraper_setting(db, "next_run_at", None)
    
    return ScraperConfigResponse(
        locations=request.locations,
        categories=request.categories,
        interval=request.interval,
        next_run_at=next_run_at
    )


# ============================================
# Status Endpoint
# ============================================

@router.get("/status", response_model=ScraperStatusResponse)
async def get_scraper_status(db: AsyncSession = Depends(get_db)):
    """Get complete scraper status"""
    master_enabled = await check_master_switch(db)
    auto_enabled = await get_scraper_setting(db, "auto_enabled", False)
    locations = await get_scraper_setting(db, "locations", [])
    categories = await get_scraper_setting(db, "categories", [])
    interval = await get_scraper_setting(db, "interval", "1h")
    next_run_at = await get_scraper_setting(db, "next_run_at", None)
    
    missing_fields = []
    if not locations or len(locations) == 0:
        missing_fields.append("locations")
    if not categories or len(categories) == 0:
        missing_fields.append("categories")
    if not interval:
        missing_fields.append("interval")
    
    can_enable_auto = master_enabled and len(missing_fields) == 0
    
    # Check if there's a running job
    status = "disabled"
    if not master_enabled:
        status = "disabled"
    elif auto_enabled:
        # Check for running discovery/enrichment jobs
        result = await db.execute(
            select(Job).where(
                Job.job_type.in_(["discover", "enrich"]),
                Job.status == "running"
            ).order_by(Job.created_at.desc())
        )
        running_job = result.scalar_one_or_none()
        if running_job:
            status = "running"
        else:
            status = "idle"
    else:
        status = "idle"
    
    return ScraperStatusResponse(
        master_enabled=master_enabled,
        auto_enabled=auto_enabled,
        locations=locations,
        categories=categories,
        interval=interval,
        next_run_at=next_run_at,
        status=status,
        can_enable_auto=can_enable_auto,
        missing_fields=missing_fields
    )


# ============================================
# Helper: Calculate next run time
# ============================================

async def calculate_and_set_next_run(db: AsyncSession, interval: str) -> None:
    """Calculate and set next run time based on interval"""
    now = datetime.now(timezone.utc)
    
    interval_map = {
        "1h": timedelta(hours=1),
        "2h": timedelta(hours=2),
        "3h": timedelta(hours=3),
        "4h": timedelta(hours=4),
        "5h": timedelta(hours=5),
        "daily": timedelta(days=1),
        "weekly": timedelta(days=7),
    }
    
    delta = interval_map.get(interval, timedelta(hours=1))
    next_run = now + delta
    
    await set_scraper_setting(db, "next_run_at", next_run.isoformat())
    logger.info(f"Next run scheduled for {next_run.isoformat()} (interval: {interval})")


# ============================================
# History Endpoint
# ============================================

class ScraperHistoryResponse(BaseModel):
    id: str
    triggered_at: str
    completed_at: Optional[str]
    success_count: int
    failed_count: int
    duration_seconds: Optional[float]
    status: str
    error_message: Optional[str]


class ScraperHistoryListResponse(BaseModel):
    data: List[ScraperHistoryResponse]
    page: int
    limit: int
    total: int
    total_pages: int


@router.get("/history", response_model=ScraperHistoryListResponse)
async def get_scraper_history(
    page: int = 1,
    limit: int = 10,
    db: AsyncSession = Depends(get_db)
):
    """Get scraper history with pagination"""
    from app.models.scraper_history import ScraperHistory
    
    # Validate pagination - enforce max limit of 10
    page = max(1, page)
    limit = max(1, min(limit, 10))  # Cap at 10
    skip = (page - 1) * limit
    
    # Get total count
    count_result = await db.execute(select(func.count()).select_from(ScraperHistory))
    total = count_result.scalar() or 0
    
    # Get paginated results
    query = select(ScraperHistory).order_by(ScraperHistory.triggered_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    history_items = result.scalars().all()
    
    # Convert to response
    history_data = []
    for item in history_items:
        history_data.append(ScraperHistoryResponse(
            id=str(item.id),
            triggered_at=item.triggered_at.isoformat() if item.triggered_at else "",
            completed_at=item.completed_at.isoformat() if item.completed_at else None,
            success_count=item.success_count or 0,
            failed_count=item.failed_count or 0,
            duration_seconds=float(item.duration_seconds) if item.duration_seconds else None,
            status=item.status,
            error_message=item.error_message
        ))
    
    total_pages = (total + limit - 1) // limit if total > 0 else 0
    
    return ScraperHistoryListResponse(
        data=history_data,
        page=page,
        limit=limit,
        total=total,
        totalPages=total_pages
    )


# ============================================
# Websites Endpoint (if needed)
# ============================================

@router.get("/websites")
async def list_websites(
    page: int = 1,
    limit: int = 10,
    db: AsyncSession = Depends(get_db)
):
    """
    List websites (prospects) with pagination
    Same as /prospects but with standardized response format
    """
    from app.api.prospects import list_prospects
    
    # Enforce max limit of 10
    limit = max(1, min(limit, 10))
    
    # Call prospects endpoint with page-based pagination
    result = await list_prospects(
        skip=None,
        limit=limit,
        page=page,
        status=None,
        min_score=None,
        has_email=None,
        db=db,
        current_user=None
    )
    
    # Return standardized format
    if result.get("success") and result.get("data"):
        data = result["data"]
        return {
            "data": data.get("prospects", []),
            "page": data.get("page", page),
            "limit": data.get("limit", limit),
            "total": data.get("total", 0),
            "totalPages": data.get("totalPages", 0)
        }
    
    return {
        "data": [],
        "page": page,
        "limit": limit,
        "total": 0,
        "totalPages": 0
    }

