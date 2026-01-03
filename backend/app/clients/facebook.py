"""
Facebook Graph API Client

Uses Facebook Graph API to discover pages and profiles.
Requires Meta Developer account and app creation.
"""
import httpx
import os
import logging
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class FacebookClient:
    """Client for Facebook Graph API"""
    
    BASE_URL = "https://graph.facebook.com/v18.0"
    
    def __init__(self, access_token: Optional[str] = None):
        """
        Initialize Facebook client
        
        Args:
            access_token: Facebook Graph API access token (if None, uses FACEBOOK_ACCESS_TOKEN from env)
        """
        self.access_token = access_token or os.getenv("FACEBOOK_ACCESS_TOKEN")
        
        if not self.access_token:
            raise ValueError("Facebook access token not configured. Set FACEBOOK_ACCESS_TOKEN")
        
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
    
    def is_configured(self) -> bool:
        """Check if Facebook is configured"""
        return bool(self.access_token and self.access_token.strip())
    
    async def search_pages(
        self,
        keywords: List[str],
        locations: List[str],
        categories: List[str],
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Search for Facebook pages
        
        Args:
            keywords: Keywords to search
            locations: Locations to filter
            categories: Categories/industries
            max_results: Maximum results to return
        
        Returns:
            List of page data dictionaries
        """
        pages = []
        search_query = " ".join(keywords + categories)
        
        url = f"{self.BASE_URL}/pages/search"
        params = {
            "q": search_query,
            "type": "page",
            "fields": "id,name,username,about,category,location,fan_count,link",
            "limit": min(max_results, 25),  # Facebook API limit
            "access_token": self.access_token
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
                
                if response.status_code == 401:
                    logger.error("❌ [FACEBOOK] Unauthorized - invalid or expired access token")
                    raise ValueError("Facebook access token is invalid or expired")
                
                if response.status_code == 403:
                    logger.error("❌ [FACEBOOK] Forbidden - missing required API permissions")
                    raise ValueError("Facebook API permissions not granted. Requires 'pages_read_engagement' permission")
                
                if not response.is_success:
                    error_msg = f"Facebook API error: {response.status_code} - {response.text}"
                    logger.error(f"❌ [FACEBOOK] {error_msg}")
                    raise Exception(error_msg)
                
                data = response.json()
                pages = data.get("data", [])
                
                logger.info(f"✅ [FACEBOOK] Found {len(pages)} pages")
                return pages
                
        except Exception as e:
            logger.error(f"❌ [FACEBOOK] Error searching pages: {e}", exc_info=True)
            raise

