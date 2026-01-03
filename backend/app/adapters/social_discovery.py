"""
Social Discovery Adapters

Platform-specific discovery adapters for social media.
Each adapter normalizes results into Prospect objects with source_type='social'.
Uses real API clients when credentials are available, falls back to DataForSEO search otherwise.
"""
from typing import List, Dict, Any, Optional
from app.models.prospect import Prospect
from app.db.database import AsyncSession
import logging
import uuid
import os

logger = logging.getLogger(__name__)


class LinkedInDiscoveryAdapter:
    """LinkedIn discovery adapter"""
    
    async def discover(self, params: Dict[str, Any], db: AsyncSession) -> List[Prospect]:
        """
        Discover LinkedIn profiles using real LinkedIn API or DataForSEO fallback.
        
        Params:
            categories: List[str] - Categories to search
            locations: List[str] - Locations to search
            keywords: List[str] - Keywords to search
            max_results: int - Maximum results
        """
        categories = params.get('categories', [])
        locations = params.get('locations', [])
        keywords = params.get('keywords', [])
        max_results = params.get('max_results', 100)
        
        logger.info(f"🔍 [LINKEDIN DISCOVERY] Starting discovery: {len(categories)} categories, {len(locations)} locations, {len(keywords)} keywords")
        
        prospects = []
        
        # Try LinkedIn API first if credentials are available
        linkedin_token = os.getenv("LINKEDIN_ACCESS_TOKEN")
        if linkedin_token:
            try:
                from app.clients.linkedin import LinkedInClient
                client = LinkedInClient(linkedin_token)
                
                logger.info("✅ [LINKEDIN DISCOVERY] Using LinkedIn API")
                profiles = await client.search_people(keywords, locations, categories, max_results)
                
                for profile_data in profiles:
                    prospect = self._normalize_to_prospect(profile_data)
                    prospect.discovery_category = categories[0] if categories else None
                    prospect.discovery_location = locations[0] if locations else None
                    prospects.append(prospect)
                
                logger.info(f"✅ [LINKEDIN DISCOVERY] Discovered {len(prospects)} profiles via LinkedIn API")
                return prospects[:max_results]
                
            except Exception as e:
                logger.warning(f"⚠️  [LINKEDIN DISCOVERY] LinkedIn API failed: {e}. Falling back to DataForSEO search.")
        
        # Fallback: Use DataForSEO to search for LinkedIn profiles
        try:
            from app.clients.dataforseo import DataForSEOClient
            client = DataForSEOClient()
            
            logger.info("🔍 [LINKEDIN DISCOVERY] Using DataForSEO to search for LinkedIn profiles")
            
            # Build search queries: "site:linkedin.com/in/ [category] [location]"
            search_queries = []
            for category in categories:
                for location in locations:
                    query = f"site:linkedin.com/in/ {category} {location}"
                    search_queries.append(query)
            
            # Limit queries to avoid excessive API calls
            search_queries = search_queries[:10]
            
            for query in search_queries:
                if len(prospects) >= max_results:
                    break
                
                # Get location code for DataForSEO
                location_code = client.get_location_code(locations[0] if locations else "usa")
                
                # Search using DataForSEO
                serp_results = await client.serp_google_organic(
                    keyword=query,
                    location_code=location_code,
                    depth=10
                )
                
                if serp_results.get("success") and serp_results.get("results"):
                    for result in serp_results["results"]:
                        url = result.get("url", "")
                        if "linkedin.com/in/" in url:
                            # Extract username from URL
                            username = url.split("linkedin.com/in/")[-1].split("/")[0].split("?")[0]
                            
                            prospect = Prospect(
                                id=uuid.uuid4(),
                                source_type='social',
                                source_platform='linkedin',
                                domain=f"linkedin.com/in/{username}",
                                page_url=url,
                                page_title=result.get("title", f"LinkedIn Profile: {username}"),
                                display_name=result.get("title", username),
                                username=username,
                                profile_url=url,
                                discovery_status='DISCOVERED',
                                scrape_status='DISCOVERED',
                                approval_status='PENDING',
                                discovery_category=categories[0] if categories else None,
                                discovery_location=locations[0] if locations else None,
                            )
                            prospects.append(prospect)
                            
                            if len(prospects) >= max_results:
                                break
            
            logger.info(f"✅ [LINKEDIN DISCOVERY] Discovered {len(prospects)} profiles via DataForSEO")
            return prospects[:max_results]
            
        except Exception as e:
            logger.error(f"❌ [LINKEDIN DISCOVERY] DataForSEO fallback failed: {e}", exc_info=True)
            raise Exception(f"LinkedIn discovery failed: {e}. Please configure LINKEDIN_ACCESS_TOKEN or ensure DataForSEO credentials are set.")
    
    def _normalize_to_prospect(self, profile_data: Dict[str, Any]) -> Prospect:
        """Normalize LinkedIn profile data to Prospect"""
        return Prospect(
            id=uuid.uuid4(),
            source_type='social',
            source_platform='linkedin',
            domain=f"linkedin.com/in/{profile_data.get('username', '')}",
            page_url=profile_data.get('profile_url'),
            page_title=profile_data.get('headline', ''),
            display_name=profile_data.get('full_name'),
            username=profile_data.get('username'),
            profile_url=profile_data.get('profile_url'),
            follower_count=profile_data.get('connections_count', 0),
            engagement_rate=profile_data.get('engagement_rate'),
            discovery_status='DISCOVERED',
            scrape_status='DISCOVERED',
            approval_status='PENDING',
            discovery_category=profile_data.get('category'),
            discovery_location=profile_data.get('location'),
        )


class InstagramDiscoveryAdapter:
    """Instagram discovery adapter"""
    
    async def discover(self, params: Dict[str, Any], db: AsyncSession) -> List[Prospect]:
        """
        Discover Instagram profiles using real Instagram Graph API or DataForSEO fallback.
        
        Params:
            categories: List[str] - Categories to search
            locations: List[str] - Locations to search
            keywords: List[str] - Keywords to search
            max_results: int - Maximum results
        """
        categories = params.get('categories', [])
        locations = params.get('locations', [])
        keywords = params.get('keywords', [])
        max_results = params.get('max_results', 100)
        
        logger.info(f"🔍 [INSTAGRAM DISCOVERY] Starting discovery: {len(categories)} categories, {len(locations)} locations")
        
        prospects = []
        
        # Try Instagram Graph API first if credentials are available
        instagram_token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
        if instagram_token:
            try:
                from app.clients.instagram import InstagramClient
                client = InstagramClient(instagram_token)
                
                logger.info("✅ [INSTAGRAM DISCOVERY] Using Instagram Graph API")
                profiles = await client.search_users(keywords, locations, categories, max_results)
                
                for profile_data in profiles:
                    prospect = self._normalize_to_prospect(profile_data)
                    prospect.discovery_category = categories[0] if categories else None
                    prospect.discovery_location = locations[0] if locations else None
                    prospects.append(prospect)
                
                logger.info(f"✅ [INSTAGRAM DISCOVERY] Discovered {len(prospects)} profiles via Instagram API")
                return prospects[:max_results]
                
            except Exception as e:
                logger.warning(f"⚠️  [INSTAGRAM DISCOVERY] Instagram API failed: {e}. Falling back to DataForSEO search.")
        
        # Fallback: Use DataForSEO to search for Instagram profiles
        try:
            from app.clients.dataforseo import DataForSEOClient
            client = DataForSEOClient()
            
            logger.info("🔍 [INSTAGRAM DISCOVERY] Using DataForSEO to search for Instagram profiles")
            
            # Build search queries: "site:instagram.com [category] [location]"
            search_queries = []
            for category in categories:
                for location in locations:
                    query = f"site:instagram.com {category} {location}"
                    search_queries.append(query)
            
            search_queries = search_queries[:10]
            
            for query in search_queries:
                if len(prospects) >= max_results:
                    break
                
                location_code = client.get_location_code(locations[0] if locations else "usa")
                serp_results = await client.serp_google_organic(
                    keyword=query,
                    location_code=location_code,
                    depth=10
                )
                
                if serp_results.get("success") and serp_results.get("results"):
                    for result in serp_results["results"]:
                        url = result.get("url", "")
                        if "instagram.com/" in url and "/p/" not in url and "/reel/" not in url:
                            # Extract username from URL
                            username = url.split("instagram.com/")[-1].split("/")[0].split("?")[0]
                            
                            prospect = Prospect(
                                id=uuid.uuid4(),
                                source_type='social',
                                source_platform='instagram',
                                domain=f"instagram.com/{username}",
                                page_url=url,
                                page_title=result.get("title", f"Instagram Profile: {username}"),
                                display_name=result.get("title", username),
                                username=username,
                                profile_url=url,
                                discovery_status='DISCOVERED',
                                scrape_status='DISCOVERED',
                                approval_status='PENDING',
                                discovery_category=categories[0] if categories else None,
                                discovery_location=locations[0] if locations else None,
                            )
                            prospects.append(prospect)
                            
                            if len(prospects) >= max_results:
                                break
            
            logger.info(f"✅ [INSTAGRAM DISCOVERY] Discovered {len(prospects)} profiles via DataForSEO")
            return prospects[:max_results]
            
        except Exception as e:
            logger.error(f"❌ [INSTAGRAM DISCOVERY] DataForSEO fallback failed: {e}", exc_info=True)
            raise Exception(f"Instagram discovery failed: {e}. Please configure INSTAGRAM_ACCESS_TOKEN or ensure DataForSEO credentials are set.")
    
    def _normalize_to_prospect(self, profile_data: Dict[str, Any]) -> Prospect:
        """Normalize Instagram profile data to Prospect"""
        return Prospect(
            id=uuid.uuid4(),
            source_type='social',
            source_platform='instagram',
            domain=f"instagram.com/{profile_data.get('username', '')}",
            page_url=profile_data.get('profile_url'),
            page_title=profile_data.get('bio', ''),
            display_name=profile_data.get('full_name'),
            username=profile_data.get('username'),
            profile_url=profile_data.get('profile_url'),
            follower_count=profile_data.get('followers', 0),
            engagement_rate=profile_data.get('engagement_rate'),
            discovery_status='DISCOVERED',
            scrape_status='DISCOVERED',
            approval_status='PENDING',
            discovery_category=profile_data.get('category'),
        )


class TikTokDiscoveryAdapter:
    """TikTok discovery adapter"""
    
    async def discover(self, params: Dict[str, Any], db: AsyncSession) -> List[Prospect]:
        """
        Discover TikTok profiles using real TikTok API or DataForSEO fallback.
        
        Params:
            categories: List[str] - Categories to search
            locations: List[str] - Locations to search
            keywords: List[str] - Keywords to search
            max_results: int - Maximum results
        """
        categories = params.get('categories', [])
        locations = params.get('locations', [])
        keywords = params.get('keywords', [])
        max_results = params.get('max_results', 100)
        
        logger.info(f"🔍 [TIKTOK DISCOVERY] Starting discovery: {len(categories)} categories, {len(locations)} locations")
        
        prospects = []
        
        # Try TikTok API first if credentials are available
        tiktok_key = os.getenv("TIKTOK_CLIENT_KEY")
        tiktok_secret = os.getenv("TIKTOK_CLIENT_SECRET")
        if tiktok_key and tiktok_secret:
            try:
                from app.clients.tiktok import TikTokClient
                client = TikTokClient(tiktok_key, tiktok_secret)
                
                logger.info("✅ [TIKTOK DISCOVERY] Using TikTok API")
                profiles = await client.search_users(keywords, locations, categories, max_results)
                
                for profile_data in profiles:
                    prospect = self._normalize_to_prospect(profile_data)
                    prospect.discovery_category = categories[0] if categories else None
                    prospect.discovery_location = locations[0] if locations else None
                    prospects.append(prospect)
                
                logger.info(f"✅ [TIKTOK DISCOVERY] Discovered {len(prospects)} profiles via TikTok API")
                return prospects[:max_results]
                
            except Exception as e:
                logger.warning(f"⚠️  [TIKTOK DISCOVERY] TikTok API failed: {e}. Falling back to DataForSEO search.")
        
        # Fallback: Use DataForSEO to search for TikTok profiles
        try:
            from app.clients.dataforseo import DataForSEOClient
            client = DataForSEOClient()
            
            logger.info("🔍 [TIKTOK DISCOVERY] Using DataForSEO to search for TikTok profiles")
            
            # Build search queries: "site:tiktok.com/@ [category] [location]"
            search_queries = []
            for category in categories:
                for location in locations:
                    query = f"site:tiktok.com/@ {category} {location}"
                    search_queries.append(query)
            
            search_queries = search_queries[:10]
            
            for query in search_queries:
                if len(prospects) >= max_results:
                    break
                
                location_code = client.get_location_code(locations[0] if locations else "usa")
                serp_results = await client.serp_google_organic(
                    keyword=query,
                    location_code=location_code,
                    depth=10
                )
                
                if serp_results.get("success") and serp_results.get("results"):
                    for result in serp_results["results"]:
                        url = result.get("url", "")
                        if "tiktok.com/@" in url:
                            # Extract username from URL
                            username = url.split("tiktok.com/@")[-1].split("/")[0].split("?")[0]
                            
                            prospect = Prospect(
                                id=uuid.uuid4(),
                                source_type='social',
                                source_platform='tiktok',
                                domain=f"tiktok.com/@{username}",
                                page_url=url,
                                page_title=result.get("title", f"TikTok Profile: {username}"),
                                display_name=result.get("title", username),
                                username=username,
                                profile_url=url,
                                discovery_status='DISCOVERED',
                                scrape_status='DISCOVERED',
                                approval_status='PENDING',
                                discovery_category=categories[0] if categories else None,
                                discovery_location=locations[0] if locations else None,
                            )
                            prospects.append(prospect)
                            
                            if len(prospects) >= max_results:
                                break
            
            logger.info(f"✅ [TIKTOK DISCOVERY] Discovered {len(prospects)} profiles via DataForSEO")
            return prospects[:max_results]
            
        except Exception as e:
            logger.error(f"❌ [TIKTOK DISCOVERY] DataForSEO fallback failed: {e}", exc_info=True)
            raise Exception(f"TikTok discovery failed: {e}. Please configure TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET or ensure DataForSEO credentials are set.")
    
    def _normalize_to_prospect(self, profile_data: Dict[str, Any]) -> Prospect:
        """Normalize TikTok profile data to Prospect"""
        return Prospect(
            id=uuid.uuid4(),
            source_type='social',
            source_platform='tiktok',
            domain=f"tiktok.com/@{profile_data.get('username', '')}",
            page_url=profile_data.get('profile_url'),
            page_title=profile_data.get('bio', ''),
            display_name=profile_data.get('display_name'),
            username=profile_data.get('username'),
            profile_url=profile_data.get('profile_url'),
            follower_count=profile_data.get('followers', 0),
            engagement_rate=profile_data.get('engagement_rate'),
            discovery_status='DISCOVERED',
            scrape_status='DISCOVERED',
            approval_status='PENDING',
            discovery_category=profile_data.get('category'),
        )


class FacebookDiscoveryAdapter:
    """Facebook discovery adapter"""
    
    async def discover(self, params: Dict[str, Any], db: AsyncSession) -> List[Prospect]:
        """
        Discover Facebook pages/profiles using real Facebook Graph API or DataForSEO fallback.
        
        Params:
            categories: List[str] - Categories to search
            locations: List[str] - Locations to search
            keywords: List[str] - Keywords to search
            max_results: int - Maximum results
        """
        categories = params.get('categories', [])
        locations = params.get('locations', [])
        keywords = params.get('keywords', [])
        max_results = params.get('max_results', 100)
        
        logger.info(f"🔍 [FACEBOOK DISCOVERY] Starting discovery: {len(categories)} categories, {len(locations)} locations")
        
        prospects = []
        
        # Try Facebook Graph API first if credentials are available
        facebook_token = os.getenv("FACEBOOK_ACCESS_TOKEN")
        if facebook_token:
            try:
                from app.clients.facebook import FacebookClient
                client = FacebookClient(facebook_token)
                
                logger.info("✅ [FACEBOOK DISCOVERY] Using Facebook Graph API")
                pages = await client.search_pages(keywords, locations, categories, max_results)
                
                for page_data in pages:
                    prospect = self._normalize_to_prospect(page_data)
                    prospect.discovery_category = categories[0] if categories else None
                    prospect.discovery_location = locations[0] if locations else None
                    prospects.append(prospect)
                
                logger.info(f"✅ [FACEBOOK DISCOVERY] Discovered {len(prospects)} pages via Facebook API")
                return prospects[:max_results]
                
            except Exception as e:
                logger.warning(f"⚠️  [FACEBOOK DISCOVERY] Facebook API failed: {e}. Falling back to DataForSEO search.")
        
        # Fallback: Use DataForSEO to search for Facebook pages
        try:
            from app.clients.dataforseo import DataForSEOClient
            client = DataForSEOClient()
            
            logger.info("🔍 [FACEBOOK DISCOVERY] Using DataForSEO to search for Facebook pages")
            
            # Build search queries: "site:facebook.com [category] [location]"
            search_queries = []
            for category in categories:
                for location in locations:
                    query = f"site:facebook.com {category} {location}"
                    search_queries.append(query)
            
            search_queries = search_queries[:10]
            
            for query in search_queries:
                if len(prospects) >= max_results:
                    break
                
                location_code = client.get_location_code(locations[0] if locations else "usa")
                serp_results = await client.serp_google_organic(
                    keyword=query,
                    location_code=location_code,
                    depth=10
                )
                
                if serp_results.get("success") and serp_results.get("results"):
                    for result in serp_results["results"]:
                        url = result.get("url", "")
                        if "facebook.com/" in url and "/pages/" not in url:
                            # Extract username/page name from URL
                            username = url.split("facebook.com/")[-1].split("/")[0].split("?")[0]
                            
                            prospect = Prospect(
                                id=uuid.uuid4(),
                                source_type='social',
                                source_platform='facebook',
                                domain=f"facebook.com/{username}",
                                page_url=url,
                                page_title=result.get("title", f"Facebook Page: {username}"),
                                display_name=result.get("title", username),
                                username=username,
                                profile_url=url,
                                discovery_status='DISCOVERED',
                                scrape_status='DISCOVERED',
                                approval_status='PENDING',
                                discovery_category=categories[0] if categories else None,
                                discovery_location=locations[0] if locations else None,
                            )
                            prospects.append(prospect)
                            
                            if len(prospects) >= max_results:
                                break
            
            logger.info(f"✅ [FACEBOOK DISCOVERY] Discovered {len(prospects)} pages via DataForSEO")
            return prospects[:max_results]
            
        except Exception as e:
            logger.error(f"❌ [FACEBOOK DISCOVERY] DataForSEO fallback failed: {e}", exc_info=True)
            raise Exception(f"Facebook discovery failed: {e}. Please configure FACEBOOK_ACCESS_TOKEN or ensure DataForSEO credentials are set.")
    
    def _normalize_to_prospect(self, profile_data: Dict[str, Any]) -> Prospect:
        """Normalize Facebook profile data to Prospect"""
        return Prospect(
            id=uuid.uuid4(),
            source_type='social',
            source_platform='facebook',
            domain=f"facebook.com/{profile_data.get('username', '')}",
            page_url=profile_data.get('profile_url'),
            page_title=profile_data.get('bio', ''),
            display_name=profile_data.get('full_name'),
            username=profile_data.get('username'),
            profile_url=profile_data.get('profile_url'),
            follower_count=profile_data.get('friends_count', 0),
            engagement_rate=profile_data.get('engagement_rate'),
            discovery_status='DISCOVERED',
            scrape_status='DISCOVERED',
            approval_status='PENDING',
            discovery_category=profile_data.get('category'),
            discovery_location=profile_data.get('location'),
        )

