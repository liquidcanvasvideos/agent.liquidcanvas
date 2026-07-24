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
        max_results = params.get('max_results', 1000)  # DEEP SEARCH: Increased default from 100 to 1000 for deeper search
        
        logger.info(f"🔍 [LINKEDIN DISCOVERY] ========================================")
        logger.info(f"🔍 [LINKEDIN DISCOVERY] Starting discovery")
        logger.info(f"🔍 [LINKEDIN DISCOVERY] Categories: {categories} ({len(categories)} total)")
        logger.info(f"🔍 [LINKEDIN DISCOVERY] Locations: {locations} ({len(locations)} total)")
        logger.info(f"🔍 [LINKEDIN DISCOVERY] Keywords: {keywords} ({len(keywords) if keywords else 0} total)")
        logger.info(f"🔍 [LINKEDIN DISCOVERY] Max results: {max_results}")
        logger.info(f"🔍 [LINKEDIN DISCOVERY] ========================================")
        
        prospects = []
        
        # Try LinkedIn API first if credentials are available
        linkedin_token = os.getenv("LINKEDIN_ACCESS_TOKEN")
        if linkedin_token and linkedin_token.strip() and linkedin_token != "your_linkedin_access_token":
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
            logger.info(f"📋 [LINKEDIN DISCOVERY] Categories: {categories}, Locations: {locations}")
            
            # DEEP SEARCH: Build comprehensive query variations - search the entire internet for profiles
            # Store queries as tuples (query, location, category) to track which location/category each query corresponds to
            # Strategy: Ensure ALL category/location combinations get at least one query before limiting
            search_queries = []
            seen_queries = set()
            
            # Essential query pattern - ensure every category/location combination gets at least this one
            essential_pattern = 'site:linkedin.com/in/ "{category}" "{location}"'
            
            # First pass: Ensure at least ONE query for EACH category/location combination
            for category in categories:
                for location in locations:
                    query = essential_pattern.format(category=category, location=location)
                    if query not in seen_queries:
                        seen_queries.add(query)
                        search_queries.append((query, location, category))  # Store query with location AND category
            
            # Second pass: Add more variations for each category/location combination (up to limit)
            # Base query patterns - many variations to search deeper
            base_patterns = [
                'site:linkedin.com/in/ "{category}" "{location}" email',
                'site:linkedin.com/in/ "{category}" "{location}" gmail.com',
                'site:linkedin.com/in/ "{category}" "{location}" "contact me"',
                'site:linkedin.com/in/ "{category}" "{location}" "freelance"',
                'site:linkedin.com/in/ "{category}" "{location}" "commission"',
                'site:linkedin.com/in/ "{category}" "{location}" artist',
                'site:linkedin.com/in/ "{category}" "{location}" creator',
                'site:linkedin.com/in/ "{category}" "{location}" founder',
                'site:linkedin.com/in/ "{category}" "{location}" owner',
                'inurl:linkedin.com/in/ "{category}" "{location}" "at gmail.com"',
                'inurl:linkedin.com/in/ "{category}" "{location}" "send email"',
            ]
            
            # Add variations for each category/location combination
            for category in categories:
                for location in locations:
                    for pattern in base_patterns:
                        if len(search_queries) >= 1000:  # Limit total queries
                            break
                        query = pattern.format(category=category, location=location)
                        if query not in seen_queries:
                            seen_queries.add(query)
                            search_queries.append((query, location, category))  # Store query with location AND category
                    if len(search_queries) >= 1000:
                        break
                if len(search_queries) >= 1000:
                    break
            
            # DEEP SEARCH: Only use keyword-based queries if keywords are provided, 
            # and ALWAYS constrain by both category and location to avoid "sovereign" searches.
            if keywords and len(search_queries) < 1000:
                keyword_patterns = [
                    'site:linkedin.com/in/ "{keyword}" "{category}" "{location}"',
                    'site:linkedin.com/in/ {keyword} "{category}" "{location}"',
                    '"{keyword}" "{category}" "{location}" site:linkedin.com/in/',
                ]
                
                for keyword in keywords:
                    for category in categories:
                        for location in locations:
                            for pattern in keyword_patterns:
                                if len(search_queries) >= 1000:
                                    break
                                query = pattern.format(keyword=keyword, category=category, location=location)
                                if query not in seen_queries:
                                    seen_queries.add(query)
                                    search_queries.append((query, location, category))
                            if len(search_queries) >= 1000:
                                break
                        if len(search_queries) >= 1000:
                            break
                    if len(search_queries) >= 1000:
                        break
            
            # REMOVED: no_location_patterns pass to ensure strict adherence to selected location/category.
            
            # Final limit to ensure we don't exceed reasonable bounds
            search_queries = search_queries[:1000]
            logger.info(f"📊 [LINKEDIN DISCOVERY] Built {len(search_queries)} search queries")
            
            queries_executed = 0
            queries_successful = 0
            total_results_found = 0
            
            for query, query_location, query_category in search_queries:
                if len(prospects) >= max_results:
                    break
                
                try:
                    queries_executed += 1
                    logger.info(f"🔍 [LINKEDIN DISCOVERY] Executing query {queries_executed}/{len(search_queries)}: '{query}' (location: {query_location}, category: {query_category})")
                    
                    # Get location code for DataForSEO - use the location from the query
                    location_code = client.get_location_code(query_location)
                    logger.debug(f"📍 [LINKEDIN DISCOVERY] Using location code {location_code} for '{query_location}'")
                    
                    # DEEP SEARCH: Search using DataForSEO with maximum depth
                    serp_results = await client.serp_google_organic(
                        keyword=query,
                        location_code=location_code,
                        depth=100  # DataForSEO limit is 100
                    )
                    
                    logger.info(f"📥 [LINKEDIN DISCOVERY] Query result - success: {serp_results.get('success')}, results count: {len(serp_results.get('results', []))}")
                    
                    if serp_results.get("success"):
                        results_list = serp_results.get("results", [])
                        total_results_found += len(results_list)
                        queries_successful += 1
                        
                        if results_list:
                            logger.info(f"✅ [LINKEDIN DISCOVERY] Found {len(results_list)} results for query '{query}'")
                            
                            for result in results_list:
                                url = result.get("url", "")
                                logger.debug(f"🔗 [LINKEDIN DISCOVERY] Checking URL: {url}")
                                
                                if "linkedin.com/in/" in url:
                                    # Extract username from URL
                                    username = url.split("linkedin.com/in/")[-1].split("/")[0].split("?")[0]
                                    
                                    # Skip if we already have this username
                                    if any(p.username == username for p in prospects):
                                        logger.debug(f"⏭️  [LINKEDIN DISCOVERY] Skipping duplicate username: {username}")
                                        continue
                                    
                                    logger.info(f"✅ [LINKEDIN DISCOVERY] Found LinkedIn profile: {username} - {result.get('title', 'No title')}")
                                    
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
                                        discovery_category=query_category,  # Use the category from the query
                                        discovery_location=query_location,  # Use the location from the query
                                        # Set default follower count and engagement rate (will be updated later if available)
                                        follower_count=1000,  # Default to pass qualification
                                        engagement_rate=1.5,  # Default to pass LinkedIn minimum (1.0%)
                                    )
                                    prospects.append(prospect)
                                    
                                    if len(prospects) >= max_results:
                                        break
                                else:
                                    logger.debug(f"⏭️  [LINKEDIN DISCOVERY] URL doesn't match LinkedIn profile pattern: {url}")
                        else:
                            logger.warning(f"⚠️  [LINKEDIN DISCOVERY] Query '{query}' returned no results")
                    else:
                        error_msg = serp_results.get("error", "Unknown error")
                        logger.warning(f"⚠️  [LINKEDIN DISCOVERY] Query '{query}' failed: {error_msg}")
                except Exception as query_error:
                    logger.error(f"❌ [LINKEDIN DISCOVERY] Query '{query}' failed with exception: {query_error}", exc_info=True)
                    continue
            
            logger.info(f"📊 [LINKEDIN DISCOVERY] Summary - Queries executed: {queries_executed}, Successful: {queries_successful}, Total results: {total_results_found}, Profiles extracted: {len(prospects)}")
            logger.info(f"✅ [LINKEDIN DISCOVERY] Discovered {len(prospects)} profiles via DataForSEO")
            return prospects[:max_results]
            
        except ValueError as cred_error:
            # DataForSEO credentials not configured
            logger.error(f"❌ [LINKEDIN DISCOVERY] DataForSEO credentials not configured: {cred_error}")
            logger.error("❌ [LINKEDIN DISCOVERY] Please set DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD environment variables")
            # Return empty list instead of raising - allows job to complete gracefully
            return []
        except Exception as e:
            logger.error(f"❌ [LINKEDIN DISCOVERY] DataForSEO fallback failed: {e}", exc_info=True)
            # Return empty list instead of raising - allows job to complete gracefully
            logger.error("❌ [LINKEDIN DISCOVERY] Discovery failed. Please configure LINKEDIN_ACCESS_TOKEN or ensure DataForSEO credentials are set.")
            return []
    
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
        max_results = params.get('max_results', 1000)  # DEEP SEARCH: Increased default from 100 to 1000 for deeper search
        
        logger.info(f"🔍 [INSTAGRAM DISCOVERY] ========================================")
        logger.info(f"🔍 [INSTAGRAM DISCOVERY] Starting discovery")
        logger.info(f"🔍 [INSTAGRAM DISCOVERY] Categories: {categories} ({len(categories)} total)")
        logger.info(f"🔍 [INSTAGRAM DISCOVERY] Locations: {locations} ({len(locations)} total)")
        logger.info(f"🔍 [INSTAGRAM DISCOVERY] Keywords: {keywords} ({len(keywords) if keywords else 0} total)")
        logger.info(f"🔍 [INSTAGRAM DISCOVERY] Max results: {max_results}")
        logger.info(f"🔍 [INSTAGRAM DISCOVERY] ========================================")
        
        prospects = []
        
        # Try Instagram Graph API first if credentials are available
        instagram_token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
        if instagram_token and instagram_token.strip() and instagram_token != "your_instagram_access_token":
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
            
            # DEEP SEARCH: Build comprehensive query variations - search the entire internet for Instagram profiles
            # Store queries as tuples (query, location) to track which location each query corresponds to
            # Strategy: Ensure ALL category/location combinations get at least one query before limiting
            search_queries = []
            seen_queries = set()
            
            # Essential query pattern - ensure every category/location combination gets at least this one
            essential_pattern = 'site:instagram.com "{category}" "{location}"'
            
            # First pass: Ensure at least ONE query for EACH category/location combination
            for category in categories:
                for location in locations:
                    query = essential_pattern.format(category=category, location=location)
                    if query not in seen_queries:
                        seen_queries.add(query)
                        search_queries.append((query, location, category))  # Store query with location AND category
            
            # Second pass: Add more variations for each category/location combination (up to limit)
            # Base query patterns - many variations to search deeper
            base_patterns = [
                'site:instagram.com "{category}" "{location}" email',
                'site:instagram.com "{category}" "{location}" gmail.com',
                'site:instagram.com "{category}" "{location}" "linktr.ee"',
                'site:instagram.com "{category}" "{location}" "contact me"',
                'site:instagram.com "{category}" "{location}" "DM for"',
                'site:instagram.com "{category}" "{location}" artist',
                'site:instagram.com "{category}" "{location}" creator',
                'site:instagram.com "{category}" "{location}" founder',
                'site:instagram.com "{category}" "{location}" gallery',
                'inurl:instagram.com "{category}" "{location}" "gmail.com"',
                'site:instagram.com "{category}" "{location}" "linkinbio"',
            ]
            
            # Add variations for each category/location combination
            for category in categories:
                for location in locations:
                    for pattern in base_patterns:
                        if len(search_queries) >= 1000:  # Limit total queries
                            break
                        query = pattern.format(category=category, location=location)
                        if query not in seen_queries:
                            seen_queries.add(query)
                            search_queries.append((query, location, category))  # Store query with location AND category
                    if len(search_queries) >= 1000:
                        break
                if len(search_queries) >= 1000:
                    break
            
            # DEEP SEARCH: Only use keyword-based queries if keywords are provided, 
            # and ALWAYS constrain by both category and location to avoid "sovereign" searches.
            if keywords and len(search_queries) < 1000:
                keyword_patterns = [
                    'site:instagram.com "{keyword}" "{category}" "{location}"',
                    'site:instagram.com {keyword} "{category}" "{location}"',
                    '"{keyword}" "{category}" "{location}" site:instagram.com',
                ]
                
                for keyword in keywords:
                    for category in categories:
                        for location in locations:
                            for pattern in keyword_patterns:
                                if len(search_queries) >= 1000:
                                    break
                                query = pattern.format(keyword=keyword, category=category, location=location)
                                if query not in seen_queries:
                                    seen_queries.add(query)
                                    search_queries.append((query, location, category))
                            if len(search_queries) >= 1000:
                                break
                        if len(search_queries) >= 1000:
                            break
                    if len(search_queries) >= 1000:
                        break
            
            # REMOVED: no_location_patterns pass to ensure strict adherence to selected location/category.
            
            # Final limit to ensure we don't exceed reasonable bounds
            search_queries = search_queries[:1000]
            
            logger.info(f"📊 [INSTAGRAM DISCOVERY] Built {len(search_queries)} search queries")
            
            queries_executed = 0
            queries_successful = 0
            total_results_found = 0
            profiles_extracted = 0
            
            for query, query_location, query_category in search_queries:
                if len(prospects) >= max_results:
                    logger.info(f"✅ [INSTAGRAM DISCOVERY] Reached max_results ({max_results}), stopping query execution")
                    break
                
                try:
                    queries_executed += 1
                    logger.info(f"🔍 [INSTAGRAM DISCOVERY] Executing query {queries_executed}/{len(search_queries)}: '{query}' (location: {query_location}, category: {query_category})")
                    
                    # Get location code for DataForSEO - use the location from the query
                    location_code = client.get_location_code(query_location)
                    logger.debug(f"📍 [INSTAGRAM DISCOVERY] Using location code {location_code} for '{query_location}'")
                    
                    # DEEP SEARCH: Search with maximum depth
                    serp_results = await client.serp_google_organic(
                        keyword=query,
                        location_code=location_code,
                        depth=100  # DataForSEO limit is 100
                    )
                    
                    logger.info(f"📥 [INSTAGRAM DISCOVERY] Query result - success: {serp_results.get('success')}, results count: {len(serp_results.get('results', []))}")
                    
                    # CRITICAL: Check for DataForSEO credit/account errors
                    if serp_results.get("error_code") == 402 or serp_results.get("error_type") == "insufficient_credits":
                        error_msg = serp_results.get("error", "DataForSEO account has insufficient credits")
                        logger.error(f"❌ [INSTAGRAM DISCOVERY] DataForSEO account error: {error_msg}")
                        logger.error(f"❌ [INSTAGRAM DISCOVERY] Please add credits to your DataForSEO account at https://dataforseo.com")
                        # Stop processing queries - account issue affects all queries
                        raise ValueError(f"DataForSEO account error: {error_msg}. Please add credits to continue.")
                    
                    if serp_results.get("success"):
                        results_list = serp_results.get("results", [])
                        total_results_found += len(results_list)
                        queries_successful += 1
                        
                        if results_list:
                            logger.info(f"✅ [INSTAGRAM DISCOVERY] Found {len(results_list)} results for query '{query}'")
                            
                            for result in results_list:
                                url = result.get("url", "")
                                logger.debug(f"🔗 [INSTAGRAM DISCOVERY] Checking URL: {url}")
                                
                                # More lenient URL matching - accept any instagram.com URL that's not a post/reel/story
                                if "instagram.com/" in url:
                                    # Skip posts, reels, stories, and other non-profile URLs
                                    if any(skip in url for skip in ["/p/", "/reel/", "/stories/", "/tv/", "/explore/", "/accounts/", "/direct/"]):
                                        logger.debug(f"⏭️  [INSTAGRAM DISCOVERY] Skipping non-profile URL: {url}")
                                        continue
                                    
                                    # Extract username from URL - handle various formats
                                    url_parts = url.split("instagram.com/")[-1].split("/")[0].split("?")[0]
                                    username = url_parts.strip()
                                    
                                    # Skip empty or invalid usernames
                                    if not username or len(username) < 1:
                                        logger.debug(f"⏭️  [INSTAGRAM DISCOVERY] Skipping invalid username from URL: {url}")
                                        continue
                                    
                                    # Skip if we already have this username
                                    if any(p.username == username for p in prospects):
                                        logger.debug(f"⏭️  [INSTAGRAM DISCOVERY] Skipping duplicate username: {username}")
                                        continue
                                    
                                    logger.info(f"✅ [INSTAGRAM DISCOVERY] Found Instagram profile: {username} - {result.get('title', 'No title')}")
                                    
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
                                        discovery_category=query_category,  # Use the category from the query
                                        discovery_location=query_location,  # Use the location from the query
                                        # Set default follower count and engagement rate
                                        follower_count=1000,  # Default to pass qualification
                                        engagement_rate=2.5,  # Default to pass Instagram minimum (2.0%)
                                    )
                                    prospects.append(prospect)
                                    profiles_extracted += 1
                                    
                                    if len(prospects) >= max_results:
                                        logger.info(f"✅ [INSTAGRAM DISCOVERY] Reached max_results ({max_results})")
                                        break
                                else:
                                    logger.debug(f"⏭️  [INSTAGRAM DISCOVERY] URL doesn't match Instagram pattern: {url}")
                        else:
                            logger.warning(f"⚠️  [INSTAGRAM DISCOVERY] Query '{query}' returned no results")
                    else:
                        error_msg = serp_results.get("error", "Unknown error")
                        logger.warning(f"⚠️  [INSTAGRAM DISCOVERY] Query '{query}' failed: {error_msg}")
                except Exception as query_error:
                    logger.error(f"❌ [INSTAGRAM DISCOVERY] Query '{query}' failed with exception: {query_error}", exc_info=True)
                    continue
            
            logger.info(f"📊 [INSTAGRAM DISCOVERY] Summary - Queries executed: {queries_executed}, Successful: {queries_successful}, Total results: {total_results_found}, Profiles extracted: {profiles_extracted}")
            
            logger.info(f"✅ [INSTAGRAM DISCOVERY] Discovered {len(prospects)} profiles via DataForSEO")
            return prospects[:max_results]
            
        except ValueError as cred_error:
            logger.error(f"❌ [INSTAGRAM DISCOVERY] DataForSEO credentials not configured: {cred_error}")
            logger.error("❌ [INSTAGRAM DISCOVERY] Please set DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD environment variables")
            return []
        except Exception as e:
            logger.error(f"❌ [INSTAGRAM DISCOVERY] DataForSEO fallback failed: {e}", exc_info=True)
            logger.error("❌ [INSTAGRAM DISCOVERY] Discovery failed. Please configure INSTAGRAM_ACCESS_TOKEN or ensure DataForSEO credentials are set.")
            return []
    
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
        max_results = params.get('max_results', 1000)  # DEEP SEARCH: Increased default from 100 to 1000 for deeper search
        
        logger.info(f"🔍 [TIKTOK DISCOVERY] Starting discovery: {len(categories)} categories, {len(locations)} locations")
        
        prospects = []
        
        # Try TikTok API first if credentials are available
        tiktok_key = os.getenv("TIKTOK_CLIENT_KEY")
        tiktok_secret = os.getenv("TIKTOK_CLIENT_SECRET")
        if tiktok_key and tiktok_secret and tiktok_key.strip() and tiktok_secret.strip() and \
           tiktok_key != "your_tiktok_client_key" and tiktok_secret != "your_tiktok_client_secret":
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
            
            # DEEP SEARCH: Build comprehensive query variations - search the entire internet for TikTok profiles
            # Store queries as tuples (query, location) to track which location each query corresponds to
            # Strategy: Ensure ALL category/location combinations get at least one query before limiting
            search_queries = []
            seen_queries = set()
            
            # Essential query pattern - ensure every category/location combination gets at least this one
            essential_pattern = 'site:tiktok.com/@ "{category}" "{location}"'
            
            # First pass: Ensure at least ONE query for EACH category/location combination
            for category in categories:
                for location in locations:
                    query = essential_pattern.format(category=category, location=location)
                    if query not in seen_queries:
                        seen_queries.add(query)
                        search_queries.append((query, location, category))  # Store query with location AND category
            
            # Second pass: Add more variations for each category/location combination (up to limit)
            # Base query patterns - many variations to search deeper
            base_patterns = [
                'site:tiktok.com/@ "{category}" "{location}" email',
                'site:tiktok.com/@ "{category}" "{location}" gmail.com',
                'site:tiktok.com/@ "{category}" "{location}" "linktr.ee"',
                'site:tiktok.com/@ "{category}" "{location}" "contact me"',
                'site:tiktok.com/@ "{category}" "{location}" creator',
                'site:tiktok.com/@ "{category}" "{location}" artist',
                'site:tiktok.com/@ "{category}" "{location}" business',
                'inurl:tiktok.com/@ "{category}" "{location}" "gmail.com"',
                'site:tiktok.com/@ "{category}" "{location}" "linkinbio"',
            ]
            
            # Add variations for each category/location combination
            for category in categories:
                for location in locations:
                    for pattern in base_patterns:
                        if len(search_queries) >= 1000:  # Limit total queries
                            break
                        query = pattern.format(category=category, location=location)
                        if query not in seen_queries:
                            seen_queries.add(query)
                            search_queries.append((query, location, category))  # Store query with location AND category
                    if len(search_queries) >= 1000:
                        break
                if len(search_queries) >= 1000:
                    break
            
            # DEEP SEARCH: Only use keyword-based queries if keywords are provided, 
            # and ALWAYS constrain by both category and location to avoid "sovereign" searches.
            if keywords and len(search_queries) < 1000:
                keyword_patterns = [
                    'site:tiktok.com/@ "{keyword}" "{category}" "{location}"',
                    'site:tiktok.com/@ {keyword} "{category}" "{location}"',
                    '"{keyword}" "{category}" "{location}" site:tiktok.com/@',
                ]
                
                for keyword in keywords:
                    for category in categories:
                        for location in locations:
                            for pattern in keyword_patterns:
                                if len(search_queries) >= 1000:
                                    break
                                query = pattern.format(keyword=keyword, category=category, location=location)
                                if query not in seen_queries:
                                    seen_queries.add(query)
                                    search_queries.append((query, location, category))
                            if len(search_queries) >= 1000:
                                break
                        if len(search_queries) >= 1000:
                            break
                    if len(search_queries) >= 1000:
                        break
            
            # REMOVED: no_location_patterns pass to ensure strict adherence to selected location/category.
            
            # Final limit to ensure we don't exceed reasonable bounds
            search_queries = search_queries[:1000]
            
            logger.info(f"📊 [TIKTOK DISCOVERY] Built {len(search_queries)} search queries")
            
            queries_executed = 0
            queries_successful = 0
            total_results_found = 0
            profiles_extracted = 0
            
            for query, query_location, query_category in search_queries:
                if len(prospects) >= max_results:
                    logger.info(f"✅ [TIKTOK DISCOVERY] Reached max_results ({max_results}), stopping query execution")
                    break
                
                try:
                    queries_executed += 1
                    logger.info(f"🔍 [TIKTOK DISCOVERY] Executing query {queries_executed}/{len(search_queries)}: '{query}' (location: {query_location}, category: {query_category})")
                    
                    # Get location code for DataForSEO - use the location from the query
                    location_code = client.get_location_code(query_location)
                    logger.debug(f"📍 [TIKTOK DISCOVERY] Using location code {location_code} for '{query_location}'")
                    
                    # DEEP SEARCH: Search with maximum depth
                    serp_results = await client.serp_google_organic(
                        keyword=query,
                        location_code=location_code,
                        depth=100  # DataForSEO limit is 100
                    )
                    
                    logger.info(f"📥 [TIKTOK DISCOVERY] Query result - success: {serp_results.get('success')}, results count: {len(serp_results.get('results', []))}")
                    
                    # CRITICAL: Check for DataForSEO credit/account errors
                    if serp_results.get("error_code") == 402 or serp_results.get("error_type") == "insufficient_credits":
                        error_msg = serp_results.get("error", "DataForSEO account has insufficient credits")
                        logger.error(f"❌ [TIKTOK DISCOVERY] DataForSEO account error: {error_msg}")
                        logger.error(f"❌ [TIKTOK DISCOVERY] Please add credits to your DataForSEO account at https://dataforseo.com")
                        # Stop processing queries - account issue affects all queries
                        raise ValueError(f"DataForSEO account error: {error_msg}. Please add credits to continue.")
                    
                    if serp_results.get("success"):
                        results_list = serp_results.get("results", [])
                        total_results_found += len(results_list)
                        queries_successful += 1
                        
                        if results_list:
                            logger.info(f"✅ [TIKTOK DISCOVERY] Found {len(results_list)} results for query '{query}'")
                            
                            for result in results_list:
                                url = result.get("url", "")
                                logger.debug(f"🔗 [TIKTOK DISCOVERY] Checking URL: {url}")
                                
                                if "tiktok.com/@" in url or "tiktok.com/" in url:
                                    # Extract username from URL - handle various formats
                                    if "tiktok.com/@" in url:
                                        username = url.split("tiktok.com/@")[-1].split("/")[0].split("?")[0]
                                    else:
                                        # Handle URLs without @ symbol
                                        username = url.split("tiktok.com/")[-1].split("/")[0].split("?")[0]
                                    
                                    # Skip empty or invalid usernames
                                    if not username or len(username) < 1:
                                        logger.debug(f"⏭️  [TIKTOK DISCOVERY] Skipping invalid username from URL: {url}")
                                        continue
                                    
                                    # Skip if we already have this username
                                    if any(p.username == username for p in prospects):
                                        logger.debug(f"⏭️  [TIKTOK DISCOVERY] Skipping duplicate username: {username}")
                                        continue
                                    
                                    logger.info(f"✅ [TIKTOK DISCOVERY] Found TikTok profile: {username} - {result.get('title', 'No title')}")
                                    
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
                                        discovery_category=query_category,  # Use the category from the query
                                        discovery_location=query_location,  # Use the location from the query
                                        # Set default follower count and engagement rate
                                        follower_count=1000,  # Default to pass qualification
                                        engagement_rate=3.5,  # Default to pass TikTok minimum (3.0%)
                                    )
                                    prospects.append(prospect)
                                    profiles_extracted += 1
                                    
                                    if len(prospects) >= max_results:
                                        logger.info(f"✅ [TIKTOK DISCOVERY] Reached max_results ({max_results})")
                                        break
                                else:
                                    logger.debug(f"⏭️  [TIKTOK DISCOVERY] URL doesn't match TikTok pattern: {url}")
                        else:
                            logger.warning(f"⚠️  [TIKTOK DISCOVERY] Query '{query}' returned no results")
                    else:
                        error_msg = serp_results.get("error", "Unknown error")
                        logger.warning(f"⚠️  [TIKTOK DISCOVERY] Query '{query}' failed: {error_msg}")
                except Exception as query_error:
                    logger.error(f"❌ [TIKTOK DISCOVERY] Query '{query}' failed with exception: {query_error}", exc_info=True)
                    continue
            
            logger.info(f"📊 [TIKTOK DISCOVERY] Summary - Queries executed: {queries_executed}, Successful: {queries_successful}, Total results: {total_results_found}, Profiles extracted: {profiles_extracted}")
            
            logger.info(f"✅ [TIKTOK DISCOVERY] Discovered {len(prospects)} profiles via DataForSEO")
            return prospects[:max_results]
            
        except ValueError as cred_error:
            logger.error(f"❌ [TIKTOK DISCOVERY] DataForSEO credentials not configured: {cred_error}")
            logger.error("❌ [TIKTOK DISCOVERY] Please set DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD environment variables")
            return []
        except Exception as e:
            logger.error(f"❌ [TIKTOK DISCOVERY] DataForSEO fallback failed: {e}", exc_info=True)
            logger.error("❌ [TIKTOK DISCOVERY] Discovery failed. Please configure TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET or ensure DataForSEO credentials are set.")
            return []
    
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
        max_results = params.get('max_results', 1000)  # DEEP SEARCH: Increased default from 100 to 1000 for deeper search
        
        logger.info(f"🔍 [FACEBOOK DISCOVERY] Starting discovery: {len(categories)} categories, {len(locations)} locations")
        
        prospects = []
        
        # Try Facebook API first if credentials are available
        facebook_token = os.getenv("FACEBOOK_ACCESS_TOKEN")
        if facebook_token and facebook_token.strip() and facebook_token != "your_facebook_access_token":
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
            
            # DEEP SEARCH: Build comprehensive query variations - search the entire internet for Facebook pages
            # Store queries as tuples (query, location) to track which location each query corresponds to
            # Strategy: Ensure ALL category/location combinations get at least one query before limiting
            search_queries = []
            seen_queries = set()
            
            # Essential query pattern - ensure every category/location combination gets at least this one
            essential_pattern = 'site:facebook.com "{category}" "{location}"'
            
            # First pass: Ensure at least ONE query for EACH category/location combination
            for category in categories:
                for location in locations:
                    query = essential_pattern.format(category=category, location=location)
                    if query not in seen_queries:
                        seen_queries.add(query)
                        search_queries.append((query, location, category))  # Store query with location AND category
            
            # Second pass: Add more variations for each category/location combination (up to limit)
            # Base query patterns - many variations to search deeper
            base_patterns = [
                'site:facebook.com "{category}" "{location}" email',
                'site:facebook.com "{category}" "{location}" gmail.com',
                'site:facebook.com "{category}" "{location}" "contact me"',
                'site:facebook.com "{category}" "{location}" "page"',
                'site:facebook.com "{category}" "{location}" artist',
                'site:facebook.com "{category}" "{location}" creator',
                'site:facebook.com "{category}" "{location}" gallery',
                'inurl:facebook.com "{category}" "{location}" "gmail.com"',
                'site:facebook.com "{category}" "{location}" "contact us"',
            ]
            
            # Add variations for each category/location combination
            for category in categories:
                for location in locations:
                    for pattern in base_patterns:
                        if len(search_queries) >= 1000:  # Limit total queries
                            break
                        query = pattern.format(category=category, location=location)
                        if query not in seen_queries:
                            seen_queries.add(query)
                            search_queries.append((query, location, category))  # Store query with location AND category
                    if len(search_queries) >= 1000:
                        break
                if len(search_queries) >= 1000:
                    break
            
            # DEEP SEARCH: Only use keyword-based queries if keywords are provided, 
            # and ALWAYS constrain by both category and location to avoid "sovereign" searches.
            if keywords and len(search_queries) < 1000:
                keyword_patterns = [
                    'site:facebook.com "{keyword}" "{category}" "{location}"',
                    'site:facebook.com {keyword} "{category}" "{location}"',
                    '"{keyword}" "{category}" "{location}" site:facebook.com',
                ]
                
                for keyword in keywords:
                    for category in categories:
                        for location in locations:
                            for pattern in keyword_patterns:
                                if len(search_queries) >= 1000:
                                    break
                                query = pattern.format(keyword=keyword, category=category, location=location)
                                if query not in seen_queries:
                                    seen_queries.add(query)
                                    search_queries.append((query, location, category))
                            if len(search_queries) >= 1000:
                                break
                        if len(search_queries) >= 1000:
                            break
                    if len(search_queries) >= 1000:
                        break
            
            # REMOVED: no_location_patterns pass to ensure strict adherence to selected location/category.
            
            # Final limit to ensure we don't exceed reasonable bounds
            search_queries = search_queries[:1000]
            
            logger.info(f"📊 [FACEBOOK DISCOVERY] Built {len(search_queries)} search queries")
            
            queries_executed = 0
            queries_successful = 0
            total_results_found = 0
            profiles_extracted = 0
            
            for query, query_location, query_category in search_queries:
                if len(prospects) >= max_results:
                    logger.info(f"✅ [FACEBOOK DISCOVERY] Reached max_results ({max_results}), stopping query execution")
                    break
                
                try:
                    queries_executed += 1
                    logger.info(f"🔍 [FACEBOOK DISCOVERY] Executing query {queries_executed}/{len(search_queries)}: '{query}' (location: {query_location}, category: {query_category})")
                    
                    # Get location code for DataForSEO - use the location from the query
                    location_code = client.get_location_code(query_location)
                    logger.debug(f"📍 [FACEBOOK DISCOVERY] Using location code {location_code} for '{query_location}'")
                    
                    # DEEP SEARCH: Search with maximum depth
                    serp_results = await client.serp_google_organic(
                        keyword=query,
                        location_code=location_code,
                        depth=100  # DataForSEO limit is 100
                    )
                    
                    logger.info(f"📥 [FACEBOOK DISCOVERY] Query result - success: {serp_results.get('success')}, results count: {len(serp_results.get('results', []))}")
                    
                    # CRITICAL: Check for DataForSEO credit/account errors
                    if serp_results.get("error_code") == 402 or serp_results.get("error_type") == "insufficient_credits":
                        error_msg = serp_results.get("error", "DataForSEO account has insufficient credits")
                        logger.error(f"❌ [FACEBOOK DISCOVERY] DataForSEO account error: {error_msg}")
                        logger.error(f"❌ [FACEBOOK DISCOVERY] Please add credits to your DataForSEO account at https://dataforseo.com")
                        # Stop processing queries - account issue affects all queries
                        raise ValueError(f"DataForSEO account error: {error_msg}. Please add credits to continue.")
                    
                    if serp_results.get("success"):
                        results_list = serp_results.get("results", [])
                        total_results_found += len(results_list)
                        queries_successful += 1
                        
                        if results_list:
                            logger.info(f"✅ [FACEBOOK DISCOVERY] Found {len(results_list)} results for query '{query}'")
                            
                            for result in results_list:
                                url = result.get("url", "")
                                logger.debug(f"🔗 [FACEBOOK DISCOVERY] Checking URL: {url}")
                                
                                # More lenient URL matching - accept Facebook pages and profiles
                                if "facebook.com/" in url:
                                    # Skip certain Facebook URLs that aren't pages/profiles
                                    if any(skip in url for skip in ["/pages/", "/groups/", "/events/", "/marketplace/", "/watch/", "/login", "/signup"]):
                                        logger.debug(f"⏭️  [FACEBOOK DISCOVERY] Skipping non-page URL: {url}")
                                        continue
                                    
                                    # Extract username/page name from URL
                                    username = url.split("facebook.com/")[-1].split("/")[0].split("?")[0]
                                    
                                    # Skip empty or invalid usernames
                                    if not username or len(username) < 1:
                                        logger.debug(f"⏭️  [FACEBOOK DISCOVERY] Skipping invalid username from URL: {url}")
                                        continue
                                    
                                    # Skip if we already have this username
                                    if any(p.username == username for p in prospects):
                                        logger.debug(f"⏭️  [FACEBOOK DISCOVERY] Skipping duplicate username: {username}")
                                        continue
                                    
                                    logger.info(f"✅ [FACEBOOK DISCOVERY] Found Facebook page: {username} - {result.get('title', 'No title')}")
                                    
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
                                        discovery_category=query_category,  # Use the category from the query
                                        discovery_location=query_location,  # Use the location from the query
                                        # Set default follower count and engagement rate
                                        follower_count=1000,  # Default to pass qualification
                                        engagement_rate=2.0,  # Default to pass Facebook minimum (1.5%)
                                    )
                                    prospects.append(prospect)
                                    profiles_extracted += 1
                                    
                                    if len(prospects) >= max_results:
                                        logger.info(f"✅ [FACEBOOK DISCOVERY] Reached max_results ({max_results})")
                                        break
                                else:
                                    logger.debug(f"⏭️  [FACEBOOK DISCOVERY] URL doesn't match Facebook pattern: {url}")
                        else:
                            logger.warning(f"⚠️  [FACEBOOK DISCOVERY] Query '{query}' returned no results")
                    else:
                        error_msg = serp_results.get("error", "Unknown error")
                        logger.warning(f"⚠️  [FACEBOOK DISCOVERY] Query '{query}' failed: {error_msg}")
                except Exception as query_error:
                    logger.error(f"❌ [FACEBOOK DISCOVERY] Query '{query}' failed with exception: {query_error}", exc_info=True)
                    continue
            
            logger.info(f"📊 [FACEBOOK DISCOVERY] Summary - Queries executed: {queries_executed}, Successful: {queries_successful}, Total results: {total_results_found}, Profiles extracted: {profiles_extracted}")
            
            logger.info(f"✅ [FACEBOOK DISCOVERY] Discovered {len(prospects)} pages via DataForSEO")
            return prospects[:max_results]
            
        except ValueError as cred_error:
            logger.error(f"❌ [FACEBOOK DISCOVERY] DataForSEO credentials not configured: {cred_error}")
            logger.error("❌ [FACEBOOK DISCOVERY] Please set DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD environment variables")
            return []
        except Exception as e:
            logger.error(f"❌ [FACEBOOK DISCOVERY] DataForSEO fallback failed: {e}", exc_info=True)
            logger.error("❌ [FACEBOOK DISCOVERY] Discovery failed. Please configure FACEBOOK_ACCESS_TOKEN or ensure DataForSEO credentials are set.")
            return []
    
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

