"""
Base Discovery Service for Social Platforms

Abstract base class that all platform-specific discovery services must implement.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from uuid import UUID
import logging

logger = logging.getLogger(__name__)


class BaseDiscoveryService(ABC):
    """
    Base class for platform-specific discovery services.
    
    Each platform (LinkedIn, Instagram, TikTok, Facebook) implements this interface.
    """
    
    def __init__(self, platform: str):
        self.platform = platform
        self.logger = logging.getLogger(f"{__name__}.{platform}")
    
    @abstractmethod
    async def discover_profiles(
        self,
        categories: List[str],
        locations: List[str],
        keywords: List[str],
        parameters: Dict[str, Any],
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Discover profiles based on search criteria.
        
        Args:
            categories: List of categories to search
            locations: List of locations to search
            keywords: List of keywords to search
            parameters: Platform-specific parameters (job_title, industry, hashtags, etc.)
            max_results: Maximum number of profiles to return
        
        Returns:
            List of profile dictionaries with normalized structure:
            {
                "username": str,
                "full_name": str,
                "profile_url": str,
                "bio": str,
                "location": str,
                "category": str,
                "followers_count": int,
                "engagement_score": float,
                "platform": str,
            }
        """
        pass
    
    @abstractmethod
    def parse_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse and validate platform-specific parameters.
        
        Args:
            parameters: Raw parameters from discovery job
        
        Returns:
            Validated and normalized parameters dict
        """
        pass
    
    @abstractmethod
    def calculate_engagement_score(
        self,
        followers_count: int,
        profile_data: Dict[str, Any]
    ) -> float:
        """
        Calculate engagement score for a profile.
        
        Platform-specific algorithm based on:
        - Follower count
        - Post frequency
        - Engagement metrics
        - Profile completeness
        
        Returns:
            Engagement score (0.0 to 100.0)
        """
        pass
    
    def normalize_profile(self, raw_profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize profile data to common structure.
        
        Override in platform-specific services if needed.
        """
        return {
            "username": raw_profile.get("username", ""),
            "full_name": raw_profile.get("full_name") or raw_profile.get("name", ""),
            "profile_url": raw_profile.get("profile_url", ""),
            "bio": raw_profile.get("bio") or raw_profile.get("description", ""),
            "location": raw_profile.get("location", ""),
            "category": raw_profile.get("category"),
            "followers_count": raw_profile.get("followers_count", 0),
            "engagement_score": raw_profile.get("engagement_score", 0.0),
            "platform": self.platform,
        }
    
    def validate_profile(self, profile: Dict[str, Any]) -> bool:
        """
        Validate that a profile has required fields.
        
        Returns:
            True if profile is valid, False otherwise
        """
        required_fields = ["username", "profile_url", "platform"]
        return all(profile.get(field) for field in required_fields)

