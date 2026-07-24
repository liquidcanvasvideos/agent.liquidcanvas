"""
Instagram Discovery Service

Discovers Instagram profiles based on:
- Hashtags
- Bio keywords
- Location tags
- Follower range
"""
from typing import List, Dict, Any
import logging
from .base_discovery import BaseDiscoveryService

logger = logging.getLogger(__name__)


class InstagramDiscoveryService(BaseDiscoveryService):
    """
    Instagram-specific discovery service.
    
    Discovery method:
    - Hashtag graph traversal
    - Bio parsing
    - Profile engagement scoring
    """
    
    def __init__(self):
        super().__init__("instagram")
    
    def parse_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse Instagram-specific parameters.
        
        Expected parameters:
        - hashtags: List of hashtags to search
        - bio_keywords: Keywords to search in bio
        - location_tags: Location tags to search
        - follower_min: Minimum follower count
        - follower_max: Maximum follower count
        """
        return {
            "hashtags": parameters.get("hashtags", []),
            "bio_keywords": parameters.get("bio_keywords", []),
            "location_tags": parameters.get("location_tags", []),
            "follower_min": parameters.get("follower_min", 0),
            "follower_max": parameters.get("follower_max", 10000000),
        }
    
    async def send_message(
        self,
        profile_id: UUID,
        content: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send DM to Instagram profile"""
        self.logger.info(f" [INSTAGRAM] Sending message to {profile_id}")
        # TODO: Implement Instagram DM logic via Graph API or automation
        return {"status": "sent", "platform": "instagram"}

    async def connect(
        self,
        profile_id: UUID,
        message: Optional[str] = None
    ) -> Dict[str, Any]:
        """Instagram 'follow' logic if needed"""
        self.logger.info(f" [INSTAGRAM] Following profile {profile_id}")
        return {"status": "followed", "platform": "instagram"}
    
    async def discover_profiles(
        self,
        categories: List[str],
        locations: List[str],
        keywords: List[str],
        parameters: Dict[str, Any],
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Discover Instagram profiles.
        """
        self.logger.info(f" [INSTAGRAM] Starting discovery")
        
        from app.adapters.social_discovery import InstagramDiscoveryAdapter
        adapter = InstagramDiscoveryAdapter()
        
        adapter_params = {
            "categories": categories,
            "locations": locations,
            "keywords": keywords,
            "max_results": max_results,
            **parameters
        }
        
        # Implementation similar to LinkedInDiscoveryService
        # The actual logic is in the adapter
        return adapter.discover_profiles(adapter_params)
    
    def calculate_engagement_score(
        self,
        followers_count: int,
        profile_data: Dict[str, Any]
    ) -> float:
        """
        Calculate Instagram engagement score.
        
        Factors:
        - Follower count (normalized)
        - Average likes per post
        - Average comments per post
        - Post frequency
        - Profile completeness
        """
        score = 0.0
        
        # Base score from followers (normalized to 0-40)
        if followers_count > 0:
            # Instagram engagement typically 1-5% of followers
            # Normalize: 0-10k = 0-20, 10k-100k = 20-35, 100k+ = 35-40
            if followers_count < 10000:
                score += (followers_count / 10000) * 20
            elif followers_count < 100000:
                score += 20 + ((followers_count - 10000) / 90000) * 15
            else:
                score += 35 + min((followers_count - 100000) / 1000000, 1.0) * 5
        
        # Engagement rate (0-30)
        # TODO: Calculate from likes/comments data
        # For now, estimate based on follower count
        if followers_count > 0:
            # Assume 2-3% engagement for active accounts
            estimated_engagement = 2.5
            score += min(estimated_engagement * 10, 30)
        
        # Profile completeness (0-20)
        completeness = 0
        if profile_data.get("full_name"):
            completeness += 5
        if profile_data.get("bio"):
            completeness += 10
        if profile_data.get("location"):
            completeness += 5
        score += completeness
        
        # Activity indicators (0-10)
        # TODO: Add post frequency, story activity, etc.
        if completeness >= 15:
            score += 10
        
        return min(score, 100.0)

