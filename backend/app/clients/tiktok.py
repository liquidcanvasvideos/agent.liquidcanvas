"""
TikTok API Client

Uses TikTok API to discover profiles.
Requires TikTok Developer account and app creation.
"""
import httpx
import os
import logging
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class TikTokClient:
    """Client for TikTok API"""
    
    BASE_URL = "https://open.tiktokapis.com/v2"
    
    def __init__(self, client_key: Optional[str] = None, client_secret: Optional[str] = None):
        """
        Initialize TikTok client
        
        Args:
            client_key: TikTok client key (if None, uses TIKTOK_CLIENT_KEY from env)
            client_secret: TikTok client secret (if None, uses TIKTOK_CLIENT_SECRET from env)
        """
        self.client_key = client_key or os.getenv("TIKTOK_CLIENT_KEY")
        self.client_secret = client_secret or os.getenv("TIKTOK_CLIENT_SECRET")
        
        if not self.client_key or not self.client_secret:
            raise ValueError("TikTok credentials not configured. Set TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET")
        
        self.access_token = None
    
    def is_configured(self) -> bool:
        """Check if TikTok is configured"""
        return bool(self.client_key and self.client_secret)
    
    async def _get_access_token(self) -> str:
        """Get OAuth access token"""
        if self.access_token:
            return self.access_token
        
        url = f"{self.BASE_URL}/oauth/token/"
        data = {
            "client_key": self.client_key,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials"
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=data)
                
                if not response.is_success:
                    raise Exception(f"TikTok OAuth error: {response.status_code}")
                
                result = response.json()
                self.access_token = result.get("access_token")
                
                if not self.access_token:
                    raise Exception("TikTok OAuth did not return access token")
                
                return self.access_token
        except Exception as e:
            logger.error(f"❌ [TIKTOK] Error getting access token: {e}")
            raise
    
    async def search_users(
        self,
        keywords: List[str],
        locations: List[str],
        categories: List[str],
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Search for TikTok profiles
        
        Note: TikTok API has limited search capabilities.
        This uses user search endpoints.
        
        Args:
            keywords: Keywords to search
            locations: Locations to filter
            categories: Categories/niches
            max_results: Maximum results to return
        
        Returns:
            List of profile data dictionaries
        """
        access_token = await self._get_access_token()
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        # TikTok user search endpoint
        url = f"{self.BASE_URL}/research/user/info/"
        
        # Note: TikTok API requires specific permissions and may be restricted
        # This is a placeholder for the actual implementation
        search_query = " ".join(keywords + categories)
        
        params = {
            "query": search_query,
            "max_count": min(max_results, 20)  # TikTok API limit
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=headers, params=params)
                
                if response.status_code == 401:
                    logger.error("❌ [TIKTOK] Unauthorized - invalid credentials")
                    raise ValueError("TikTok credentials are invalid")
                
                if response.status_code == 403:
                    logger.error("❌ [TIKTOK] Forbidden - missing required API permissions")
                    raise ValueError("TikTok API permissions not granted")
                
                if not response.is_success:
                    error_msg = f"TikTok API error: {response.status_code} - {response.text}"
                    logger.error(f"❌ [TIKTOK] {error_msg}")
                    raise Exception(error_msg)
                
                data = response.json()
                users = data.get("data", {}).get("users", [])
                
                logger.info(f"✅ [TIKTOK] Found {len(users)} users")
                return users
                
        except Exception as e:
            logger.error(f"❌ [TIKTOK] Error searching users: {e}", exc_info=True)
            raise

