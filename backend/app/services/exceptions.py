"""
Custom exceptions for enrichment and provider errors
"""
from typing import Optional


class RateLimitError(Exception):
    """
    Raised when a provider (e.g., Hunter.io) returns a rate limit error.
    
    Attributes:
        provider: Name of the provider (e.g., "hunter")
        retry_after: Optional number of seconds to wait before retrying
        error_id: Optional error ID from the API response (e.g., "too_many_requests", "restricted_account")
        details: Optional error details message
    """
    
    def __init__(
        self,
        provider: str,
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None,
        error_id: Optional[str] = None,
        details: Optional[str] = None
    ):
        self.provider = provider
        self.retry_after = retry_after
        self.error_id = error_id
        self.details = details
        super().__init__(message)

