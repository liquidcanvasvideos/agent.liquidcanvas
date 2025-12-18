from enum import Enum


class DiscoveryStatus(str, Enum):
    """
    Canonical discovery_status values used throughout the pipeline.
    Backed by a VARCHAR column on Prospect.discovery_status.
    """

    NEW = "NEW"
    DISCOVERED = "DISCOVERED"
    SCRAPED = "SCRAPED"
    VERIFIED = "VERIFIED"
    OUTREACH_READY = "OUTREACH_READY"
    CONTACTED = "CONTACTED"


class ScrapeStatus(str, Enum):
    """
    Canonical scrape_status values used for scraping / enrichment.
    """

    DISCOVERED = "DISCOVERED"
    SCRAPED = "SCRAPED"
    ENRICHED = "ENRICHED"
    NO_EMAIL_FOUND = "NO_EMAIL_FOUND"
    FAILED = "failed"


class VerificationStatus(str, Enum):
    """
    Canonical verification_status values.
    """

    UNVERIFIED = "UNVERIFIED"
    PENDING = "pending"
    VERIFIED = "verified"
    UNVERIFIED_LOWER = "unverified"
    FAILED = "failed"


class DraftStatus(str, Enum):
    """
    Canonical draft_status values.
    """

    PENDING = "pending"
    DRAFTED = "drafted"
    FAILED = "failed"


class SendStatus(str, Enum):
    """
    Canonical send_status values.
    """

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


