"""
DataForSEO API client for SERP data and domain metrics
"""
import requests
import base64
from typing import List, Dict, Optional
from utils.config import settings
import logging

logger = logging.getLogger(__name__)


class DataForSEOClient:
    """Client for DataForSEO API"""
    
    BASE_URL = "https://api.dataforseo.com/v3"
    
    def __init__(self, login: Optional[str] = None, password: Optional[str] = None):
        """
        Initialize DataForSEO client
        
        Args:
            login: DataForSEO login/email (if None, uses DATAFORSEO_LOGIN from settings)
            password: DataForSEO password/token (if None, uses DATAFORSEO_PASSWORD from settings)
        """
        self.login = login or getattr(settings, 'DATAFORSEO_LOGIN', None)
        self.password = password or getattr(settings, 'DATAFORSEO_PASSWORD', None)
        
        # Always initialize headers (even if empty)
        self.headers = {
            "Content-Type": "application/json"
        }
        
        if self.login and self.password and self.login.strip() and self.password.strip():
            # Create basic auth header
            credentials = f"{self.login}:{self.password}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            self.headers["Authorization"] = f"Basic {encoded_credentials}"
        else:
            logger.warning("DataForSEO credentials not configured. Set DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD in .env")
    
    def is_configured(self) -> bool:
        """Check if credentials are configured"""
        return (
            self.login is not None 
            and self.password is not None 
            and self.login.strip() != "" 
            and self.password.strip() != ""
            and "Authorization" in self.headers
        )
    
    def serp_google_organic(self, keyword: str, location_code: int = 2840, language_code: str = "en", 
                           depth: int = 10) -> Dict:
        """
        Get Google organic search results
        
        Args:
            keyword: Search keyword/query
            location_code: Location code (2840 = United States, 2826 = United Kingdom, etc.)
            language_code: Language code (en, de, fr, etc.)
            depth: Number of results to return (max 100)
            
        Returns:
            Dictionary with search results including URLs, titles, snippets, and metrics
        """
        if not self.is_configured():
            return {"error": "DataForSEO credentials not configured"}
        
        try:
            url = f"{self.BASE_URL}/serp/google/organic/live/advanced"
            
            payload = [{
                "keyword": keyword,
                "location_code": location_code,
                "language_code": language_code,
                "depth": min(depth, 100),
                "device": "desktop",
                "os": "windows"
            }]
            
            logger.info(f"🌐 Making REAL-TIME DataForSEO API request: {keyword} (location: {location_code})")
            response = requests.post(url, json=payload, headers=self.headers, timeout=30)
            response.raise_for_status()
            logger.debug(f"✅ DataForSEO API response received: {response.status_code}")
            
            data = response.json()
            
            if data.get("tasks") and len(data["tasks"]) > 0:
                task = data["tasks"][0]
                if task.get("status_code") == 20000 and task.get("result"):
                    results = task["result"][0].get("items", [])
                    
                    formatted_results = []
                    for item in results:
                        if item.get("type") == "organic":
                            formatted_results.append({
                                "url": item.get("url", ""),
                                "title": item.get("title", ""),
                                "description": item.get("description", ""),
                                "domain": item.get("domain", ""),
                                "rank_group": item.get("rank_group", 0),
                                "rank_absolute": item.get("rank_absolute", 0),
                                "position": item.get("rank_absolute", 0),
                                "metrics": {
                                    "etv": item.get("metrics", {}).get("etv", 0),  # Estimated traffic value
                                    "impressions_etv": item.get("metrics", {}).get("impressions_etv", 0),
                                }
                            })
                    
                    return {
                        "success": True,
                        "keyword": keyword,
                        "results": formatted_results,
                        "total": len(formatted_results)
                    }
            
            return {
                "success": False,
                "error": "No results found or API error",
                "raw_response": data
            }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"DataForSEO API error: {str(e)}")
            return {"error": f"API request failed: {str(e)}"}
        except Exception as e:
            logger.error(f"Unexpected error in DataForSEO serp_google_organic: {str(e)}")
            return {"error": str(e)}
    
    def domain_metrics(self, target: str) -> Dict:
        """
        Get domain metrics (Domain Authority, Page Authority, etc.)
        
        Args:
            target: Domain name (e.g., "liquidcanvas.art") or URL
            
        Returns:
            Dictionary with domain metrics
        """
        if not self.is_configured():
            return {"error": "DataForSEO credentials not configured"}
        
        try:
            url = f"{self.BASE_URL}/backlinks/summary/live"
            
            payload = [{
                "target": target,
                "internal_list_limit": 10,
                "backlinks_status_type": "live"
            }]
            
            response = requests.post(url, json=payload, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get("tasks") and len(data["tasks"]) > 0:
                task = data["tasks"][0]
                if task.get("status_code") == 20000 and task.get("result"):
                    result = task["result"][0]
                    
                    return {
                        "success": True,
                        "target": target,
                        "backlinks": result.get("backlinks", 0),
                        "referring_domains": result.get("referring_domains", 0),
                        "referring_main_domains": result.get("referring_main_domains", 0),
                        "referring_ips": result.get("referring_ips", 0),
                        "referring_subnets": result.get("referring_subnets", 0),
                        "referring_pages": result.get("referring_pages", 0),
                        "dofollow": result.get("dofollow", 0),
                        "nofollow": result.get("nofollow", 0),
                        "spam_score": result.get("spam_score", 0),
                        "domain_rank": result.get("domain_rank", 0),
                        "page_rank": result.get("page_rank", 0),
                    }
            
            return {
                "success": False,
                "error": "No metrics found",
                "raw_response": data
            }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"DataForSEO API error: {str(e)}")
            return {"error": f"API request failed: {str(e)}"}
        except Exception as e:
            logger.error(f"Unexpected error in DataForSEO domain_metrics: {str(e)}")
            return {"error": str(e)}
    
    def get_location_code(self, location: str) -> int:
        """
        Get DataForSEO location code from location name
        
        Args:
            location: Location name (usa, canada, uk_london, germany, france, europe)
            
        Returns:
            Location code (default: 2840 for USA)
        """
        location_map = {
            "usa": 2840,
            "canada": 2124,
            "uk_london": 2826,
            "germany": 2276,
            "france": 2250,
            "europe": 2826,  # Default to UK for Europe
        }
        
        return location_map.get(location.lower(), 2840)  # Default to USA

