"""
API routes for application settings and automation control
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Optional, List
from pydantic import BaseModel, ConfigDict
from db.database import get_db
from utils.app_settings import AppSettingsManager
from db.models import EmailTemplate
from jobs.scheduler import scheduler
from utils.auth import get_current_user

router = APIRouter()


class AutomationStatusResponse(BaseModel):
    automation_enabled: bool
    email_trigger_mode: str  # "automatic" or "manual"
    search_interval_seconds: int
    next_search_time: Optional[str] = None  # ISO format timestamp
    settings: Dict


class EmailTriggerModeRequest(BaseModel):
    mode: str  # "automatic" or "manual"


class AutomationToggleRequest(BaseModel):
    enabled: bool


class SearchIntervalRequest(BaseModel):
    interval_seconds: int  # Minimum 10 seconds


class EmailTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    name: str
    category: Optional[str]
    subject_template: str
    body_template: str
    is_active: bool
    is_default: bool
    variables: Optional[Dict]
    description: Optional[str]
    created_at: str
    updated_at: Optional[str]


class EmailTemplateRequest(BaseModel):
    name: str
    category: Optional[str] = None
    subject_template: str
    body_template: str
    is_active: bool = True
    is_default: bool = False
    variables: Optional[Dict] = None
    description: Optional[str] = None


@router.get("/automation/status", response_model=AutomationStatusResponse)
async def get_automation_status(
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """Get current automation status and settings"""
    settings_manager = AppSettingsManager(db)
    
    # Get next search time from scheduler
    next_search_time = None
    if scheduler and scheduler.running:
        try:
            job = scheduler.get_job('fetch_new_art_websites')
            if job and job.next_run_time:
                next_search_time = job.next_run_time.isoformat()
        except Exception:
            # If scheduler doesn't have the job yet, calculate from last job run
            pass
    
    # If no next_run_time from scheduler, calculate from last job execution
    if not next_search_time:
        from db.models import ScrapingJob
        from sqlalchemy import desc
        last_job = db.query(ScrapingJob).filter(
            ScrapingJob.job_type == 'fetch_new_art_websites'
        ).order_by(desc(ScrapingJob.completed_at)).first()
        
        if last_job and last_job.completed_at:
            from datetime import datetime, timedelta
            search_interval = settings_manager.get_search_interval_seconds()
            next_search_time = (last_job.completed_at + timedelta(seconds=search_interval)).isoformat()
        elif last_job and last_job.started_at:
            # If job is still running, calculate from start time
            from datetime import datetime, timedelta
            search_interval = settings_manager.get_search_interval_seconds()
            next_search_time = (last_job.started_at + timedelta(seconds=search_interval)).isoformat()
    
    return AutomationStatusResponse(
        automation_enabled=settings_manager.get_automation_enabled(),
        email_trigger_mode=settings_manager.get_email_trigger_mode(),
        search_interval_seconds=settings_manager.get_search_interval_seconds(),
        next_search_time=next_search_time,
        settings=settings_manager.get_all_settings()
    )


@router.post("/automation/toggle")
async def toggle_automation(
    request: AutomationToggleRequest,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """Turn automation on or off"""
    from jobs.scheduler import scheduler
    
    settings_manager = AppSettingsManager(db)
    settings_manager.set_automation_enabled(request.enabled)
    
    # Control scheduler
    if scheduler:
        if request.enabled:
            if not scheduler.running:
                scheduler.start()
        else:
            # Don't shutdown, just pause jobs
            scheduler.pause()
    
    return {
        "automation_enabled": request.enabled,
        "message": f"Automation {'enabled' if request.enabled else 'disabled'}"
    }


@router.post("/automation/email-trigger-mode")
async def set_email_trigger_mode(
    request: EmailTriggerModeRequest,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """Set email trigger mode (automatic or manual)"""
    if request.mode not in ["automatic", "manual"]:
        raise HTTPException(
            status_code=400,
            detail="Mode must be 'automatic' or 'manual'"
        )
    
    settings_manager = AppSettingsManager(db)
    settings_manager.set_email_trigger_mode(request.mode)
    
    return {
        "email_trigger_mode": request.mode,
        "message": f"Email trigger mode set to {request.mode}"
    }


@router.post("/automation/search-interval")
async def set_search_interval(
    request: SearchIntervalRequest,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """Set search interval in seconds (minimum 10 seconds)"""
    if request.interval_seconds < 10:
        raise HTTPException(
            status_code=400,
            detail="Minimum interval is 10 seconds to avoid rate limits"
        )
    
    settings_manager = AppSettingsManager(db)
    settings_manager.set_search_interval_seconds(request.interval_seconds)
    
    # Update scheduler job
    if scheduler and scheduler.running:
        from apscheduler.triggers.interval import IntervalTrigger
        from jobs.automation_jobs import fetch_new_art_websites
        
        scheduler.remove_job('fetch_new_art_websites')
        scheduler.add_job(
            func=fetch_new_art_websites,
            trigger=IntervalTrigger(seconds=request.interval_seconds),
            id='fetch_new_art_websites',
            name=f'Fetch New Art Websites (Every {request.interval_seconds}s)',
            replace_existing=True,
            max_instances=1
        )
    
    return {
        "search_interval_seconds": request.interval_seconds,
        "message": f"Search interval set to {request.interval_seconds} seconds"
    }


@router.get("/templates", response_model=List[EmailTemplateResponse])
async def get_email_templates(
    category: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get all email templates, optionally filtered by category"""
    query = db.query(EmailTemplate)
    
    if category:
        query = query.filter(EmailTemplate.category == category)
    
    templates = query.order_by(EmailTemplate.category, EmailTemplate.name).all()
    
    return [
        EmailTemplateResponse(
            id=t.id,
            name=t.name,
            category=t.category,
            subject_template=t.subject_template,
            body_template=t.body_template,
            is_active=t.is_active,
            is_default=t.is_default,
            variables=t.variables,
            description=t.description,
            created_at=t.created_at.isoformat() if t.created_at else "",
            updated_at=t.updated_at.isoformat() if t.updated_at else None
        )
        for t in templates
    ]


@router.post("/templates", response_model=EmailTemplateResponse)
async def create_email_template(
    template: EmailTemplateRequest,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """Create a new email template"""
    # If this is set as default, unset other defaults for the same category
    if template.is_default and template.category:
        db.query(EmailTemplate).filter(
            EmailTemplate.category == template.category,
            EmailTemplate.is_default == True
        ).update({"is_default": False})
    
    new_template = EmailTemplate(
        name=template.name,
        category=template.category,
        subject_template=template.subject_template,
        body_template=template.body_template,
        is_active=template.is_active,
        is_default=template.is_default,
        variables=template.variables,
        description=template.description
    )
    
    db.add(new_template)
    db.commit()
    db.refresh(new_template)
    
    return EmailTemplateResponse(
        id=new_template.id,
        name=new_template.name,
        category=new_template.category,
        subject_template=new_template.subject_template,
        body_template=new_template.body_template,
        is_active=new_template.is_active,
        is_default=new_template.is_default,
        variables=new_template.variables,
        description=new_template.description,
        created_at=new_template.created_at.isoformat() if new_template.created_at else "",
        updated_at=new_template.updated_at.isoformat() if new_template.updated_at else None
    )


@router.put("/templates/{template_id}", response_model=EmailTemplateResponse)
async def update_email_template(
    template_id: int,
    template: EmailTemplateRequest,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """Update an existing email template"""
    existing = db.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # If setting as default, unset other defaults
    if template.is_default and template.category:
        db.query(EmailTemplate).filter(
            EmailTemplate.category == template.category,
            EmailTemplate.id != template_id,
            EmailTemplate.is_default == True
        ).update({"is_default": False})
    
    existing.name = template.name
    existing.category = template.category
    existing.subject_template = template.subject_template
    existing.body_template = template.body_template
    existing.is_active = template.is_active
    existing.is_default = template.is_default
    existing.variables = template.variables
    existing.description = template.description
    
    db.commit()
    db.refresh(existing)
    
    return EmailTemplateResponse(
        id=existing.id,
        name=existing.name,
        category=existing.category,
        subject_template=existing.subject_template,
        body_template=existing.body_template,
        is_active=existing.is_active,
        is_default=existing.is_default,
        variables=existing.variables,
        description=existing.description,
        created_at=existing.created_at.isoformat() if existing.created_at else "",
        updated_at=existing.updated_at.isoformat() if existing.updated_at else None
    )


@router.delete("/templates/{template_id}")
async def delete_email_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """Delete an email template"""
    template = db.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    db.delete(template)
    db.commit()
    
    return {"message": "Template deleted successfully"}


@router.get("/templates/variables")
async def get_template_variables():
    """Get available template variables"""
    return {
        "variables": {
            "business_name": "Name of the business/website",
            "recipient_name": "Name of the contact/recipient",
            "business_context": "Context about the business (from description/social media)",
            "personalized_intro": "Personalized introduction based on platform/category",
            "specific_offer": "Specific collaboration offer based on category",
            "website_url": "URL of the website",
            "category": "Website category (art_gallery, interior_decor, etc.)",
            "social_platform": "Social media platform if available",
            "your_name": "Your name (configurable)"
        },
        "example": {
            "subject": "Collaboration Opportunity for {business_name}",
            "body": "Hello {recipient_name},\n\nI discovered {business_name} and was impressed by {business_context}.\n\n{personalized_intro}\n\n{specific_offer}\n\nBest regards,\n{your_name}"
        }
    }
