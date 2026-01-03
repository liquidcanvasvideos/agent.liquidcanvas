"""
LinkedIn API Client

Uses LinkedIn API v2 to discover profiles.
Requires LinkedIn Developer account and OAuth credentials.
"""
import httpx
import os
import logging
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class LinkedInClient:
    """Client for LinkedIn API"""
    
    BASE_URL = "https://api.linkedin.com/v2"
    
    def __init__(self, access_token: Optional[str] = None):
        """
        Initialize LinkedIn client
        
        Args:
            access_token: LinkedIn OAuth access token (if None, uses LINKEDIN_ACCESS_TOKEN from env)
        """
        self.access_token = access_token or os.getenv("LINKEDIN_ACCESS_TOKEN")
        
        if not self.access_token:
            raise ValueError("LinkedIn access token not configured. Set LINKEDIN_ACCESS_TOKEN")
        
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
    
    def is_configured(self) -> bool:
        """Check if LinkedIn is configured"""
        return bool(self.access_token and self.access_token.strip())
    
    async def search_people(
        self,
        keywords: List[str],
        locations: List[str],
        categories: List[str],
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Search for LinkedIn profiles
        
        Note: LinkedIn API v2 has limited search capabilities.
        This uses People Search API which requires specific permissions.
        
        Args:
            keywords: Keywords to search
            locations: Locations to filter
            categories: Categories/industries
            max_results: Maximum results to return
        
        Returns:
            List of profile data dictionaries
        """
        # LinkedIn People Search API endpoint
        # Note: This requires specific API permissions and may be restricted
        url = f"{self.BASE_URL}/peopleSearch"
        
        # Build search query
        query_parts = []
        if keywords:
            query_parts.extend(keywords)
        if categories:
            query_parts.extend(categories)
        
        search_query = " ".join(query_parts)
        
        params = {
            "q": "people",
            "keywords": search_query,
            "count": min(max_results, 25),  # LinkedIn API limit
            "start": 0
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=self.headers, params=params)
                
                if response.status_code == 401:
                    logger.error("❌ [LINKEDIN] Unauthorized - invalid or expired access token")
                    raise ValueError("LinkedIn access token is invalid or expired")
                
                if response.status_code == 403:
                    logger.error("❌ [LINKEDIN] Forbidden - missing required API permissions")
                    raise ValueError("LinkedIn API permissions not granted. Requires 'People Search' permission")
                
                if not response.is_success:
                    error_msg = f"LinkedIn API error: {response.status_code} - {response.text}"
                    logger.error(f"❌ [LINKEDIN] {error_msg}")
                    raise Exception(error_msg)
                
                data = response.json()
                profiles = data.get("elements", [])
                
                logger.info(f"✅ [LINKEDIN] Found {len(profiles)} profiles")
                return profiles
                
        except Exception as e:
            logger.error(f"❌ [LINKEDIN] Error searching profiles: {e}", exc_info=True)
            raise
    
    async def get_profile(self, profile_id: str) -> Dict[str, Any]:
        """Get detailed profile information"""
        url = f"{self.BASE_URL}/people/(id:{profile_id})"
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=self.headers)
                
                if not response.is_success:
                    raise Exception(f"LinkedIn API error: {response.status_code}")
                
                return response.json()
        except Exception as e:
            logger.error(f"❌ [LINKEDIN] Error getting profile {profile_id}: {e}")
            raise

