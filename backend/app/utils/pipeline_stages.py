"""
Pipeline Stage Definitions - Single Source of Truth

This module defines explicit, deterministic mappings for pipeline stages.
All endpoints MUST use these definitions to ensure consistency.
"""
from typing import Dict, List
from sqlalchemy import select
from app.models.prospect import (
    Prospect,
    DiscoveryStatus,
    ScrapeStatus,
    VerificationStatus,
    DraftStatus,
    SendStatus,
)


# ============================================
# PIPELINE STAGE DEFINITIONS
# ============================================

PIPELINE_STAGE_DEFINITIONS = {
    "DISCOVERED": {
        "description": "Website discovered",
        "condition": lambda: Prospect.discovery_status == DiscoveryStatus.DISCOVERED.value,
        "status_field": "discovery_status",
        "status_value": "DISCOVERED"
    },
    "SCRAPED": {
        "description": "Email scraped or enriched",
        "condition": lambda: Prospect.scrape_status.in_([
            ScrapeStatus.SCRAPED.value,
            ScrapeStatus.ENRICHED.value
        ]),
        "status_field": "scrape_status",
        "status_value": ["SCRAPED", "ENRICHED"]
    },
    "VERIFIED": {
        "description": "Email verified",
        "condition": lambda: Prospect.verification_status == VerificationStatus.VERIFIED.value,
        "status_field": "verification_status",
        "status_value": "verified"
    },
    "DRAFTED": {
        "description": "Email drafted",
        "condition": lambda: Prospect.draft_status == DraftStatus.DRAFTED.value,
        "status_field": "draft_status",
        "status_value": "drafted"
    },
    "SENT": {
        "description": "Email sent",
        "condition": lambda: Prospect.send_status == SendStatus.SENT.value,
        "status_field": "send_status",
        "status_value": "sent"
    }
}


def get_stage_query(stage_name: str):
    """
    Get SQLAlchemy query condition for a pipeline stage.
    
    Args:
        stage_name: One of DISCOVERED, SCRAPED, VERIFIED, DRAFTED, SENT
        
    Returns:
        SQLAlchemy condition object
    """
    if stage_name not in PIPELINE_STAGE_DEFINITIONS:
        raise ValueError(f"Unknown stage: {stage_name}")
    
    return PIPELINE_STAGE_DEFINITIONS[stage_name]["condition"]()


def count_by_stage(stage_name: str, query_base=None):
    """
    Count prospects by pipeline stage.
    
    Args:
        stage_name: One of DISCOVERED, SCRAPED, VERIFIED, DRAFTED, SENT
        query_base: Optional base query to apply stage condition to
        
    Returns:
        SQLAlchemy count query
    """
    from sqlalchemy import func, select
    
    if query_base is None:
        query_base = select(Prospect)
    
    condition = get_stage_query(stage_name)
    return select(func.count(Prospect.id)).where(condition)


# ============================================
# TAB DEFINITIONS (for list endpoints)
# ============================================

TAB_DEFINITIONS = {
    "websites": {
        "description": "All prospects with domain",
        "condition": lambda: Prospect.domain.isnot(None),
        "endpoint": "/api/pipeline/websites"
    },
    "leads": {
        "description": "All prospects with email",
        "condition": lambda: Prospect.contact_email.isnot(None),
        "endpoint": "/api/prospects/leads"
    },
    "scraped_emails": {
        "description": "Prospects with email AND scraped/enriched",
        "condition": lambda: (
            Prospect.contact_email.isnot(None),
            Prospect.scrape_status.in_([
                ScrapeStatus.SCRAPED.value,
                ScrapeStatus.ENRICHED.value
            ])
        ),
        "endpoint": "/api/prospects/scraped-emails"
    }
}

