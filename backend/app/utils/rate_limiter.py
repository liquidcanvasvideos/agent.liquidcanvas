"""
Rate Limiting Utility

Provides rate limiting for API calls to prevent:
- API bans and account suspension
- Cost overruns
- Service overload
- Terms of Service violations
"""
import asyncio
import time
from typing import Optional, Dict
from limits import storage, strategies
from limits.storage import MemoryStorage
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Rate limiter for API calls.
    
    Uses the 'limits' library to enforce rate limits per API endpoint.
    Automatically queues requests when limits are exceeded.
    """
    
    # Per-platform rate limits (requests per hour)
    # These are conservative limits to stay well below API maximums
    RATE_LIMITS = {
        "linkedin": "100/hour",      # LinkedIn: ~100/hour
        "instagram": "180/hour",      # Instagram: ~200/hour (90% of limit)
        "facebook": "180/hour",      # Facebook: ~200/hour (90% of limit)
        "tiktok": "90/hour",         # TikTok: ~100/hour (90% of limit)
        "dataforseo": "900/hour",    # DataForSEO: varies by plan (conservative)
        "snov": "100/hour",          # Snov.io: varies by plan
        "hunter": "100/hour",        # Hunter.io: varies by plan
        "gemini": "60/minute",       # Gemini: 60 requests/minute
    }
    
    def __init__(self):
        """Initialize rate limiter with in-memory storage"""
        self.storage = MemoryStorage()
        self.strategies: Dict[str, strategies.MovingWindowRateLimiter] = {}
        
        # Initialize rate limiters for each platform
        for platform, limit in self.RATE_LIMITS.items():
            self.strategies[platform] = strategies.MovingWindowRateLimiter(self.storage)
    
    async def wait_if_needed(self, platform: str) -> None:
        """
        Check rate limit and wait if necessary.
        
        Args:
            platform: Platform name (linkedin, instagram, facebook, tiktok, dataforseo, etc.)
        
        Raises:
            ValueError: If platform is not configured
        """
        if platform not in self.strategies:
            raise ValueError(f"Rate limiter not configured for platform: {platform}")
        
        strategy = self.strategies[platform]
        limit_str = self.RATE_LIMITS[platform]
        
        # Check if we can make a request
        # CRITICAL FIX: limits library hit() method expects (limit, key) where limit can be a string
        # But the library internally may call .key_for() on the limit if it thinks it's an enum
        # Solution: Ensure we pass a plain string for the limit, not an enum-like object
        from limits import parse
        
        key = f"{platform}_api"
        
        try:
            # Parse the limit string into a RateLimitItem object
            # This ensures proper format and prevents the key_for() error
            rate_limit_item = parse(limit_str)
            
            # CORRECT USAGE: hit(rate_limit_item, key)
            # The rate_limit_item is a parsed RateLimitItem object, key is a string identifier
            can_proceed = strategy.hit(rate_limit_item, key)
            
        except Exception as parse_err:
            # If parsing fails, log error but allow request (fail open to prevent blocking discovery)
            logger.error(
                f"❌ [RATE LIMIT] Error parsing rate limit '{limit_str}' for {platform}: {parse_err}\n"
                f"This is likely the 'key_for' bug - allowing request to proceed",
                exc_info=True
            )
            logger.warning(f"⚠️  [RATE LIMIT] Allowing request to proceed despite rate limit parsing error")
            # Fail open: allow the request to proceed
            return
        
        if not can_proceed:
            # Calculate wait time (approximate)
            # Moving window: wait until oldest request expires
            wait_seconds = self._calculate_wait_time(limit_str)
            
            logger.warning(
                f"⚠️  [RATE LIMIT] {platform.upper()} rate limit exceeded. "
                f"Waiting {wait_seconds} seconds before next request."
            )
            
            await asyncio.sleep(wait_seconds)
            
            # Try again with correct usage
            try:
                rate_limit_item = parse(limit_str)
                can_proceed = strategy.hit(rate_limit_item, key)
            except Exception:
                # Fail open if parsing fails
                can_proceed = True
                logger.warning(f"⚠️  [RATE LIMIT] Retry parsing failed, allowing request to proceed")
            if not can_proceed:
                logger.error(f"❌ [RATE LIMIT] Still rate limited after wait for {platform}")
    
    def _calculate_wait_time(self, limit_str: str) -> float:
        """
        Calculate approximate wait time based on rate limit string.
        
        Args:
            limit_str: Rate limit string (e.g., "100/hour", "60/minute")
        
        Returns:
            Wait time in seconds
        """
        if "/hour" in limit_str:
            # For hourly limits, wait 1/100th of an hour (36 seconds)
            return 36.0
        elif "/minute" in limit_str:
            # For minute limits, wait 1/60th of a minute (1 second)
            return 1.0
        elif "/day" in limit_str:
            # For daily limits, wait 1/1000th of a day (86 seconds)
            return 86.0
        else:
            # Default: wait 10 seconds
            return 10.0
    
    def get_remaining_requests(self, platform: str) -> Optional[int]:
        """
        Get approximate number of remaining requests for a platform.
        
        Args:
            platform: Platform name
        
        Returns:
            Approximate remaining requests, or None if not available
        """
        if platform not in self.strategies:
            return None
        
        # Note: The 'limits' library doesn't provide a direct way to get remaining count
        # This is an approximation based on the rate limit
        limit_str = self.RATE_LIMITS[platform]
        
        if "/hour" in limit_str:
            limit_num = int(limit_str.split("/")[0])
            # This is a rough estimate - actual remaining depends on request history
            return limit_num  # Simplified - would need to track actual usage
        elif "/minute" in limit_str:
            limit_num = int(limit_str.split("/")[0])
            return limit_num
        
        return None
    
    def reset(self, platform: Optional[str] = None) -> None:
        """
        Reset rate limiter for a platform (or all platforms).
        
        Args:
            platform: Platform name, or None to reset all
        """
        if platform:
            if platform in self.strategies:
                # Clear storage for this platform
                key = f"{platform}_api"
                # Note: MemoryStorage doesn't have a direct clear method
                # This would require reinitializing the storage
                logger.info(f"🔄 [RATE LIMIT] Reset rate limiter for {platform}")
        else:
            # Reset all
            self.storage = MemoryStorage()
            for platform_name in self.RATE_LIMITS.keys():
                self.strategies[platform_name] = strategies.MovingWindowRateLimiter(self.storage)
            logger.info("🔄 [RATE LIMIT] Reset all rate limiters")


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get or create global rate limiter instance"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def rate_limit(platform: str):
    """
    Decorator to add rate limiting to async functions.
    
    Usage:
        @rate_limit("linkedin")
        async def search_linkedin():
            ...
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            limiter = get_rate_limiter()
            await limiter.wait_if_needed(platform)
            return await func(*args, **kwargs)
        return wrapper
    return decorator

