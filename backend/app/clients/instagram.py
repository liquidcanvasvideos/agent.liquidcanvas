"""
Instagram Graph API Client

Uses Instagram Graph API (Meta) to discover profiles.
Requires Meta Developer account, app creation, and App Review.
"""
import httpx
import os
import logging
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class InstagramClient:
    """Client for Instagram Graph API"""
    
    BASE_URL = "https://graph.instagram.com"
    GRAPH_API_URL = "https://graph.facebook.com/v18.0"
    
    def __init__(self, access_token: Optional[str] = None):
        """
        Initialize Instagram client
        
        Args:
            access_token: Instagram Graph API access token (if None, uses INSTAGRAM_ACCESS_TOKEN from env)
        """
        self.access_token = access_token or os.getenv("INSTAGRAM_ACCESS_TOKEN")
        
        if not self.access_token:
            raise ValueError("Instagram access token not configured. Set INSTAGRAM_ACCESS_TOKEN")
        
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
    
    def is_configured(self) -> bool:
        """Check if Instagram is configured"""
        return bool(self.access_token and self.access_token.strip())
    
    async def search_users(
        self,
        keywords: List[str],
        locations: List[str],
        categories: List[str],
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Search for Instagram profiles
        
        Note: Instagram Graph API has limited search capabilities.
        This uses hashtag search and user search endpoints.
        
        Args:
            keywords: Keywords to search
            locations: Locations to filter (limited support)
            categories: Categories/niches
            max_results: Maximum results to return
        
        Returns:
            List of profile data dictionaries
        """
        profiles = []
        
        # Search by hashtags (if keywords provided)
        if keywords:
            for keyword in keywords[:5]:  # Limit to 5 keywords
                hashtag_profiles = await self._search_by_hashtag(keyword, max_results // len(keywords))
                profiles.extend(hashtag_profiles)
                
                if len(profiles) >= max_results:
                    break
        
        # Search by category hashtags
        if categories:
            for category in categories[:3]:  # Limit to 3 categories
                category_hashtag = category.lower().replace(" ", "")
                category_profiles = await self._search_by_hashtag(category_hashtag, max_results // len(categories))
                profiles.extend(category_profiles)
                
                if len(profiles) >= max_results:
                    break
        
        return profiles[:max_results]
    
    async def _search_by_hashtag(self, hashtag: str, limit: int = 25) -> List[Dict[str, Any]]:
        """Search for profiles by hashtag"""
        # Remove # if present
        hashtag = hashtag.lstrip("#")
        
        # Instagram Graph API hashtag search
        url = f"{self.GRAPH_API_URL}/ig_hashtag_search"
        params = {
            "user_id": "me",  # Requires user context
            "q": hashtag,
            "access_token": self.access_token
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
                
                if response.status_code == 401:
                    logger.error("❌ [INSTAGRAM] Unauthorized - invalid or expired access token")
                    raise ValueError("Instagram access token is invalid or expired")
                
                if response.status_code == 403:
                    logger.error("❌ [INSTAGRAM] Forbidden - missing required API permissions")
                    raise ValueError("Instagram API permissions not granted. Requires 'instagram_basic' and 'instagram_content_publish' permissions")
                
                if not response.is_success:
                    error_msg = f"Instagram API error: {response.status_code} - {response.text}"
                    logger.error(f"❌ [INSTAGRAM] {error_msg}")
                    raise Exception(error_msg)
                
                data = response.json()
                hashtag_id = data.get("data", [{}])[0].get("id") if data.get("data") else None
                
                if not hashtag_id:
                    return []
                
                # Get top media for this hashtag
                media_url = f"{self.GRAPH_API_URL}/{hashtag_id}/top_media"
                media_params = {
                    "user_id": "me",
                    "fields": "id,username,caption,like_count,comments_count",
                    "limit": limit,
                    "access_token": self.access_token
                }
                
                media_response = await client.get(media_url, params=media_params)
                
                if media_response.is_success:
                    media_data = media_response.json()
                    # Extract unique usernames from media
                    usernames = set()
                    for item in media_data.get("data", []):
                        username = item.get("username")
                        if username:
                            usernames.add(username)
                    
                    # Get profile info for each username
                    profiles = []
                    for username in list(usernames)[:limit]:
                        profile = await self._get_user_profile(username)
                        if profile:
                            profiles.append(profile)
                    
                    return profiles
                
                return []
                
        except Exception as e:
            logger.error(f"❌ [INSTAGRAM] Error searching by hashtag {hashtag}: {e}", exc_info=True)
            return []
    
    async def _get_user_profile(self, username: str) -> Optional[Dict[str, Any]]:
        """Get Instagram user profile by username"""
        url = f"{self.GRAPH_API_URL}/{username}"
        params = {
            "fields": "id,username,account_type,media_count,followers_count,follows_count",
            "access_token": self.access_token
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
                
                if response.is_success:
                    return response.json()
                return None
        except Exception as e:
            logger.warning(f"⚠️  [INSTAGRAM] Could not get profile for {username}: {e}")
            return None

