"""
TikTok Discovery Service

Discovers TikTok profiles based on:
- Niche keywords
- Bio keywords
- Video caption keywords
- Location inference
"""
from typing import List, Dict, Any
import logging
from .base_discovery import BaseDiscoveryService

logger = logging.getLogger(__name__)


class TikTokDiscoveryService(BaseDiscoveryService):
    """
    TikTok-specific discovery service.
    
    Discovery method:
    - Content-first discovery
    - Profile extraction from videos
    """
    
    def __init__(self):
        super().__init__("tiktok")
    
    def parse_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse TikTok-specific parameters.
        
        Expected parameters:
        - niche_keywords: Niche/topic keywords
        - bio_keywords: Keywords to search in bio
        - caption_keywords: Keywords to search in video captions
        - location: Location to search
        - follower_min: Minimum follower count
        - follower_max: Maximum follower count
        """
        return {
            "niche_keywords": parameters.get("niche_keywords", []),
            "bio_keywords": parameters.get("bio_keywords", []),
            "caption_keywords": parameters.get("caption_keywords", []),
            "location": parameters.get("location"),
            "follower_min": parameters.get("follower_min", 0),
            "follower_max": parameters.get("follower_max", 10000000),
        }
    
    async def send_message(
        self,
        profile_id: UUID,
        content: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send message to TikTok profile"""
        self.logger.info(f" [TIKTOK] Sending message to {profile_id}")
        # TODO: Implement TikTok messaging logic
        return {"status": "sent", "platform": "tiktok"}

    async def connect(
        self,
        profile_id: UUID,
        message: Optional[str] = None
    ) -> Dict[str, Any]:
        """TikTok 'follow' logic"""
        self.logger.info(f" [TIKTOK] Following profile {profile_id}")
        return {"status": "followed", "platform": "tiktok"}
    
    async def discover_profiles(
        self,
        categories: List[str],
        locations: List[str],
        keywords: List[str],
        parameters: Dict[str, Any],
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Discover TikTok profiles.
        """
        self.logger.info(f" [TIKTOK] Starting discovery")
        
        adapter = TikTokDiscoveryAdapter()
        
        adapter_params = {
            "categories": categories,
            "locations": locations,
            "keywords": keywords,
            "max_results": max_results,
            **parameters
        }
        
        return adapter.discover_profiles(adapter_params)
    
    def calculate_engagement_score(
        self,
        followers_count: int,
        profile_data: Dict[str, Any]
    ) -> float:
        """
        Calculate TikTok engagement score.
        
        Factors:
        - Follower count (normalized)
        - Average views per video
        - Average likes per video
        - Video frequency
        - Profile completeness
        """
        score = 0.0
        
        # Base score from followers (normalized to 0-40)
        if followers_count > 0:
            # TikTok engagement typically 5-15% of followers
            # Normalize: 0-10k = 0-20, 10k-100k = 20-35, 100k+ = 35-40
            if followers_count < 10000:
                score += (followers_count / 10000) * 20
            elif followers_count < 100000:
                score += 20 + ((followers_count - 10000) / 90000) * 15
            else:
                score += 35 + min((followers_count - 100000) / 1000000, 1.0) * 5
        
        # Engagement rate (0-35)
        # TODO: Calculate from views/likes data
        # For now, estimate based on follower count
        if followers_count > 0:
            # Assume 8-10% engagement for active TikTok accounts
            estimated_engagement = 9.0
            score += min(estimated_engagement * 3.5, 35)
        
        # Profile completeness (0-15)
        completeness = 0
        if profile_data.get("full_name"):
            completeness += 5
        if profile_data.get("bio"):
            completeness += 10
        score += completeness
        
        # Activity indicators (0-10)
        # TODO: Add video frequency, recent activity, etc.
        if completeness >= 10:
            score += 10
        
        return min(score, 100.0)

