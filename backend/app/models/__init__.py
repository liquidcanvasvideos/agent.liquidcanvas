"""
Import all models here for Alembic to detect them
"""
from app.models.prospect import Prospect
from app.models.job import Job
from app.models.email_log import EmailLog
from app.models.settings import Settings
from app.models.email_attachment import EmailAttachment
from app.models.discovery_query import DiscoveryQuery
from app.models.scraper_history import ScraperHistory
# Import social outreach models (separate system, but need to be in metadata)
from app.models.social import SocialProfile, SocialDiscoveryJob, SocialDraft, SocialMessage
from app.models.social_integration import SocialIntegration, Platform, ConnectionStatus

__all__ = [
    "Prospect", "Job", "EmailLog", "Settings", "DiscoveryQuery", "ScraperHistory", "EmailAttachment",
    "SocialProfile", "SocialDiscoveryJob", "SocialDraft", "SocialMessage",
    "SocialIntegration", "Platform", "ConnectionStatus"
]
