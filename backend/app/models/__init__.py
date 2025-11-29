"""
Import all models here for Alembic to detect them
"""
from app.models.prospect import Prospect
from app.models.job import Job
from app.models.email_log import EmailLog
from app.models.settings import Settings

__all__ = ["Prospect", "Job", "EmailLog"]
