"""
Provider state management for tracking rate limits and restrictions.
Uses Redis if available, falls back to in-memory storage.
"""
import os
import logging
import time
from typing import Optional, Dict
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Try to import Redis
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not available, using in-memory provider state")

# In-memory fallback storage
_memory_state: Dict[str, float] = {}  # provider_name -> unix timestamp when restriction expires


class ProviderState:
    """
    Manages provider state (rate limits, restrictions) with Redis or in-memory fallback.
    """
    
    def __init__(self):
        self.redis_client = None
        self.use_redis = False
        
        if REDIS_AVAILABLE:
            redis_url = os.getenv("REDIS_URL")
            if redis_url:
                try:
                    self.redis_client = redis.from_url(
                        redis_url,
                        socket_connect_timeout=2,
                        socket_timeout=2,
                        decode_responses=True
                    )
                    # Test connection
                    self.redis_client.ping()
                    self.use_redis = True
                    logger.info("✅ ProviderState: Using Redis for rate limit tracking")
                except Exception as e:
                    logger.warning(f"⚠️  ProviderState: Redis connection failed ({e}), using in-memory fallback")
                    self.use_redis = False
            else:
                logger.info("ProviderState: REDIS_URL not set, using in-memory storage")
        else:
            logger.info("ProviderState: Redis not installed, using in-memory storage")
    
    def set_restricted(self, provider: str, seconds: Optional[int] = None) -> None:
        """
        Mark a provider as restricted (rate-limited) for a specified duration.
        
        Args:
            provider: Provider name (e.g., "hunter")
            seconds: Duration in seconds (default: 3600 = 1 hour)
        """
        if seconds is None:
            seconds = 3600  # Default: 1 hour
        
        expires_at = time.time() + seconds
        
        if self.use_redis and self.redis_client:
            try:
                key = f"provider:restricted:{provider}"
                self.redis_client.setex(key, seconds, str(expires_at))
                logger.warning(f"🚫 [PROVIDER_STATE] Marked {provider} as restricted for {seconds}s (expires at {datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat()})")
            except Exception as e:
                logger.error(f"❌ [PROVIDER_STATE] Failed to set Redis restriction for {provider}: {e}")
                # Fallback to memory
                _memory_state[provider] = expires_at
        else:
            _memory_state[provider] = expires_at
            logger.warning(f"🚫 [PROVIDER_STATE] Marked {provider} as restricted for {seconds}s (in-memory, expires at {datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat()})")
    
    def is_restricted(self, provider: str) -> bool:
        """
        Check if a provider is currently restricted (rate-limited).
        
        Args:
            provider: Provider name (e.g., "hunter")
        
        Returns:
            True if provider is restricted, False otherwise
        """
        if self.use_redis and self.redis_client:
            try:
                key = f"provider:restricted:{provider}"
                expires_at_str = self.redis_client.get(key)
                if expires_at_str:
                    expires_at = float(expires_at_str)
                    if time.time() < expires_at:
                        return True
                    else:
                        # Expired, clean up
                        self.redis_client.delete(key)
                        return False
                return False
            except Exception as e:
                logger.error(f"❌ [PROVIDER_STATE] Failed to check Redis restriction for {provider}: {e}")
                # Fallback to memory
                if provider in _memory_state:
                    expires_at = _memory_state[provider]
                    if time.time() < expires_at:
                        return True
                    else:
                        # Expired, clean up
                        del _memory_state[provider]
                        return False
                return False
        else:
            # In-memory check
            if provider in _memory_state:
                expires_at = _memory_state[provider]
                if time.time() < expires_at:
                    return True
                else:
                    # Expired, clean up
                    del _memory_state[provider]
                    return False
            return False
    
    def clear_restriction(self, provider: str) -> None:
        """
        Clear restriction for a provider (manual override).
        
        Args:
            provider: Provider name
        """
        if self.use_redis and self.redis_client:
            try:
                key = f"provider:restricted:{provider}"
                self.redis_client.delete(key)
                logger.info(f"✅ [PROVIDER_STATE] Cleared restriction for {provider}")
            except Exception as e:
                logger.error(f"❌ [PROVIDER_STATE] Failed to clear Redis restriction for {provider}: {e}")
        
        if provider in _memory_state:
            del _memory_state[provider]
            logger.info(f"✅ [PROVIDER_STATE] Cleared in-memory restriction for {provider}")


# Global singleton instance
_provider_state_instance: Optional[ProviderState] = None


def get_provider_state() -> ProviderState:
    """
    Get the global ProviderState instance (singleton).
    
    Returns:
        ProviderState instance
    """
    global _provider_state_instance
    if _provider_state_instance is None:
        _provider_state_instance = ProviderState()
    return _provider_state_instance

