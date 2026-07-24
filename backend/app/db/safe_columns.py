"""
Safe column lists for prospects table queries.

This module defines explicit column lists to prevent SELECT * failures
when columns are missing from the database schema.
"""
from typing import List

# Core required columns (always present)
PROSPECT_CORE_COLUMNS = [
    "id",
    "domain",
    "page_url",
    "page_title",
    "contact_email",
    "contact_method",
    "da_est",
    "score",
    "discovery_status",
    "approval_status",
    "scrape_status",
    "verification_status",
    "draft_status",
    "send_status",
    "stage",
    "outreach_status",
    "last_sent",
    "followups_sent",
    "is_manual",
    "discovery_query_id",
    "discovery_category",
    "discovery_location",
    "discovery_keywords",
    "scrape_payload",
    "scrape_source_url",
    "verification_confidence",
    "verification_payload",
    "dataforseo_payload",
    "snov_payload",
    "serp_intent",
    "serp_confidence",
    "serp_signals",
    "created_at",
    "updated_at",
]

# Optional columns (may not exist in older schemas)
PROSPECT_OPTIONAL_COLUMNS = [
    "draft_subject",
    "draft_body",
    "final_body",
    "thread_id",
    "sequence_index",
]

# Safe list query columns (excludes optional columns that might not exist)
PROSPECT_SAFE_LIST_COLUMNS = PROSPECT_CORE_COLUMNS + [
    "draft_subject",
    "draft_body",
    # Exclude final_body, thread_id, sequence_index from list queries
    # These are only used in specific contexts
]

# Full column list (for when all columns are confirmed to exist)
PROSPECT_FULL_COLUMNS = PROSPECT_CORE_COLUMNS + PROSPECT_OPTIONAL_COLUMNS

def get_safe_columns(include_optional: bool = False) -> List[str]:
    """
    Get safe column list for queries.
    
    Args:
        include_optional: If True, includes optional columns (only use after schema validation)
    
    Returns:
        List of column names
    """
    if include_optional:
        return PROSPECT_FULL_COLUMNS.copy()
    return PROSPECT_SAFE_LIST_COLUMNS.copy()

