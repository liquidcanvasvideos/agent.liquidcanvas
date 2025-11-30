"""
Background tasks module - processes jobs directly in backend
Free tier compatible - no separate worker service needed
"""
from app.tasks.discovery import process_discovery_job, discover_websites_async
from app.tasks.enrichment import process_enrichment_job
from app.tasks.send import process_send_job

__all__ = [
    "process_discovery_job",
    "discover_websites_async",
    "process_enrichment_job",
    "process_send_job"
]

