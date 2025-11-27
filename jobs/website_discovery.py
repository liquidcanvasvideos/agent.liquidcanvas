"""
Website discovery via search engines and seed lists
"""
import requests
from typing import List, Dict, Optional, Tuple
from urllib.parse import quote_plus, urlparse
from utils.config import settings
import logging

logger = logging.getLogger(__name__)


class WebsiteDiscovery:
    """Discover new art websites via search engines and seed lists"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": settings.SCRAPER_USER_AGENT
        })
    
    def search_google(self, query: str, num_results: int = 10) -> List[str]:
        """
        Search Google for websites (using custom search API or scraping)
        
        Note: For production, use Google Custom Search API
        For now, returns empty list - implement with API key
        
        Args:
            query: Search query
            num_results: Number of results to return
            
        Returns:
            List of URLs
        """
        # TODO: Implement with Google Custom Search API
        # Requires: GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_ENGINE_ID
        # For now, return empty list
        logger.info(f"Google search for: {query} (not implemented - requires API key)")
        return []
    
    def search_bing(self, query: str, num_results: int = 10) -> List[str]:
        """
        Search Bing for websites (using Bing Search API or scraping)
        
        Note: For production, use Bing Search API
        For now, returns empty list - implement with API key
        
        Args:
            query: Search query
            num_results: Number of results to return
            
        Returns:
            List of URLs
        """
        # TODO: Implement with Bing Search API
        # Requires: BING_SEARCH_API_KEY
        # For now, return empty list
        logger.info(f"Bing search for: {query} (not implemented - requires API key)")
        return []
    
    def search_duckduckgo(self, query: str, num_results: int = 10) -> List[str]:
        """
        Search DuckDuckGo using duckduckgo-search library (no API key required)
        
        Args:
            query: Search query
            num_results: Number of results to return
            
        Returns:
            List of URLs
        """
        try:
            # Try using duckduckgo_search library if available
            try:
                from duckduckgo_search import DDGS
                logger.info(f"Attempting DuckDuckGo search for: {query}")
                with DDGS() as ddgs:
                    results = list(ddgs.text(query, max_results=num_results))
                    urls = [r.get('href', '') for r in results if r.get('href', '').startswith('http')]
                    logger.info(f"DuckDuckGo search found {len(urls)} results for: {query}")
                    if len(urls) == 0:
                        logger.warning(f"No URLs found for query: {query}. Results: {results[:2] if results else 'None'}")
                    return urls[:num_results]
            except ImportError as e:
                # Fallback to HTML scraping
                logger.warning(f"duckduckgo_search library not installed ({str(e)}), using HTML scraping fallback")
                url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
                logger.info(f"Fetching: {url}")
                response = self.session.get(url, timeout=15)
                
                if response.status_code == 200:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(response.content, "html.parser")
                    urls = []
                    
                    # Try multiple selectors for DuckDuckGo results
                    selectors = [
                        ("a", {"class": "result__url"}),
                        ("a", {"class": "result-link"}),
                        ("a", {"class": "web-result"}),
                    ]
                    
                    for selector, attrs in selectors:
                        for link in soup.find_all(selector, attrs):
                            href = link.get("href", "")
                            if href and href.startswith("http") and href not in urls:
                                urls.append(href)
                                if len(urls) >= num_results:
                                    break
                        if len(urls) >= num_results:
                            break
                    
                    logger.info(f"DuckDuckGo HTML search found {len(urls)} results for: {query}")
                    return urls
        except Exception as e:
            logger.error(f"Error searching DuckDuckGo for '{query}': {str(e)}", exc_info=True)
            import traceback
            logger.error(traceback.format_exc())
        
        logger.warning(f"Returning empty list for query: {query}")
        return []
    
    def fetch_from_seed_list(self, seed_file: str = "seed_websites.txt") -> List[str]:
        """
        Fetch websites from seed list file
        
        Args:
            seed_file: Path to seed file (one URL per line)
            
        Returns:
            List of URLs from seed file
        """
        urls = []
        try:
            import os
            seed_path = os.path.join(os.getcwd(), seed_file)
            
            if os.path.exists(seed_path):
                with open(seed_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        url = line.strip()
                        if url and url.startswith(("http://", "https://")):
                            urls.append(url)
                
                logger.info(f"Loaded {len(urls)} URLs from seed file: {seed_file}")
            else:
                logger.warning(f"Seed file not found: {seed_file}")
        except Exception as e:
            logger.error(f"Error reading seed file: {str(e)}")
        
        return urls
    
    def discover_art_websites(
        self, 
        db_session: Optional[object] = None,
        location: Optional[str] = None,
        categories: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Discover websites using multiple sources with location-based search
        
        Args:
            db_session: Optional database session to save discovered websites
            location: Optional location filter (usa, canada, uk_london, germany, france, europe)
            categories: Optional list of category keys to filter by
            
        Returns:
            List of dictionaries with discovered website info: {url, title, snippet, source, search_query, category}
        """
        all_discoveries = {}  # Use dict to track unique URLs with metadata
        
        # Generate location-based search queries
        from utils.location_search import Location, generate_location_queries
        
        if location:
            # Handle comma-separated locations
            location_list = [loc.strip() for loc in location.split(',')] if isinstance(location, str) else location
            search_queries = []
            
            for loc_str in location_list:
                try:
                    location_enum = Location(loc_str)
                    queries = generate_location_queries(
                        location_enum, 
                        categories=categories,
                        include_social=True
                    )
                    search_queries.extend(queries)
                    logger.info(f"Generated {len(queries)} queries for location: {loc_str}")
                except ValueError:
                    logger.warning(f"Invalid location: {loc_str}, skipping")
                    continue
            
            if not search_queries:
                logger.warning(f"No valid locations found, using default queries")
                search_queries = self._get_default_queries()
            else:
                logger.info(f"Total {len(search_queries)} queries generated for locations: {', '.join(location_list)}")
        else:
            # Default queries (all locations, all categories)
            search_queries = []
            for loc in Location:
                queries = generate_location_queries(loc, categories=categories, include_social=True)
                search_queries.extend(queries)
            logger.info(f"Generated {len(search_queries)} queries for all locations")
        
        # If no queries generated, use default
        if not search_queries:
            search_queries = self._get_default_queries()
        
        # Try DataForSEO first (if configured), fallback to DuckDuckGo
        use_dataforseo = False
        dataforseo_client = None
        try:
            from extractor.dataforseo_client import DataForSEOClient
            dataforseo_client = DataForSEOClient()
            if dataforseo_client.is_configured():
                use_dataforseo = True
                logger.info("✅ Using DataForSEO API for website discovery (high-quality SERP results)")
            else:
                logger.info("ℹ️ DataForSEO not configured, using DuckDuckGo (free alternative)")
        except Exception as e:
            logger.warning(f"Could not initialize DataForSEO client: {e}. Falling back to DuckDuckGo.")
        
        # Search DuckDuckGo (no API key required) or DataForSEO
        import random
        shuffled_queries = search_queries.copy()
        random.shuffle(shuffled_queries)
        
        # Limit to 15 queries per run to avoid overwhelming (increased for location-based)
        queries_to_search = shuffled_queries[:15]
        
        # Get location code for DataForSEO
        location_code = 2840  # Default to USA
        if use_dataforseo and location:
            location_code = dataforseo_client.get_location_code(location)
        
        for query, category in queries_to_search:
            try:
                if use_dataforseo:
                    # Use DataForSEO SERP API
                    serp_results = dataforseo_client.serp_google_organic(
                        keyword=query,
                        location_code=location_code,
                        depth=10
                    )
                    
                    if serp_results.get("success") and serp_results.get("results"):
                        for result in serp_results["results"]:
                            url = result.get('url', '')
                            if url and url.startswith('http'):
                                if url not in all_discoveries:
                                    all_discoveries[url] = {
                                        'url': url,
                                        'title': result.get('title', ''),
                                        'snippet': result.get('description', ''),
                                        'source': 'dataforseo',
                                        'search_query': query,
                                        'category': category,
                                        'rank': result.get('position', 0),
                                        'metrics': result.get('metrics', {})
                                    }
                    # Rate limiting for DataForSEO (they have API limits)
                    import time
                    time.sleep(2)  # Slightly longer delay for paid API
                else:
                    # Fallback to DuckDuckGo
                    results = self.search_duckduckgo_detailed(query, num_results=5)
                    for result in results:
                        url = result.get('url', '')
                        if url and url.startswith('http'):
                            if url not in all_discoveries:
                                all_discoveries[url] = {
                                    'url': url,
                                    'title': result.get('title', ''),
                                    'snippet': result.get('snippet', ''),
                                    'source': 'duckduckgo',
                                    'search_query': query,
                                    'category': category
                                }
                    # Rate limiting
                    import time
                    time.sleep(1)
            except Exception as e:
                logger.error(f"Error searching for '{query}': {str(e)}")
                continue
        
        # Fetch from seed list
        seed_urls = self.fetch_from_seed_list()
        for url in seed_urls:
            if url not in all_discoveries:
                parsed = urlparse(url)
                all_discoveries[url] = {
                    'url': url,
                    'title': '',
                    'snippet': '',
                    'source': 'seed_list',
                    'search_query': '',
                    'category': 'unknown'
                }
        
        # Save to database if session provided and filter out existing URLs
        if db_session:
            from db.models import DiscoveredWebsite, ScrapedWebsite
            saved_count = 0
            new_discoveries = {}
            
            # Get all existing URLs from both tables to filter out
            existing_discovered_urls = set(
                url[0] for url in db_session.query(DiscoveredWebsite.url).all()
            )
            existing_scraped_urls = set(
                url[0] for url in db_session.query(ScrapedWebsite.url).all()
            )
            all_existing_urls = existing_discovered_urls | existing_scraped_urls
            
            logger.info(f"Found {len(all_existing_urls)} existing URLs in database (will filter from {len(all_discoveries)} discovered)")
            
            for url, info in all_discoveries.items():
                try:
                    # Skip if URL already exists in either table
                    if url in all_existing_urls:
                        continue
                    
                    # Save new discovered website
                    parsed = urlparse(url)
                    discovered = DiscoveredWebsite(
                        url=info['url'],
                        domain=parsed.netloc,
                        title=info.get('title', ''),
                        snippet=info.get('snippet', ''),
                        source=info['source'],
                        search_query=info.get('search_query', ''),
                        category=info.get('category', 'unknown')
                    )
                    db_session.add(discovered)
                    saved_count += 1
                    new_discoveries[url] = info
                except Exception as e:
                    logger.error(f"Error saving discovered website {url}: {str(e)}")
                    continue
            
            try:
                db_session.commit()
                filtered_count = len(all_discoveries) - saved_count
                logger.info(f"Saved {saved_count} new discovered websites to database (filtered out {filtered_count} existing URLs)")
            except Exception as e:
                logger.error(f"Error committing discovered websites: {str(e)}")
                db_session.rollback()
                # If commit fails, return empty list to avoid processing duplicates
                return []
            
            # Return only new discoveries
            unique_discoveries = list(new_discoveries.values())
            logger.info(f"Returning {len(unique_discoveries)} new unique website URLs (filtered from {len(all_discoveries)} total discovered)")
            return unique_discoveries
        else:
            # If no db session, return all (but this shouldn't happen in production)
            unique_discoveries = list(all_discoveries.values())
            logger.info(f"Discovered {len(unique_discoveries)} unique website URLs (no DB session to filter)")
            return unique_discoveries
    
    def _get_default_queries(self) -> List[Tuple[str, str]]:
        """Get default search queries (fallback)"""
        return [
            # Home Decor
            ("home decor blog", "home_decor"),
            ("interior design blog", "home_decor"),
            ("home decoration website", "home_decor"),
            # Holiday
            ("holiday blog", "holiday"),
            ("holiday planning website", "holiday"),
            ("holiday ideas blog", "holiday"),
            # Parenting
            ("parenting blog", "parenting"),
            ("mom blog", "parenting"),
            ("family lifestyle blog", "parenting"),
            # Audio Visuals
            ("audio visual blog", "audio_visuals"),
            ("home theater blog", "audio_visuals"),
            ("audio equipment review", "audio_visuals"),
            # Gift Guides
            ("gift guide blog", "gift_guides"),
            ("gift ideas blog", "gift_guides"),
            ("gift recommendations website", "gift_guides"),
            # Tech Innovation
            ("tech innovation blog", "tech_innovation"),
            ("technology blog", "tech_innovation"),
            ("tech review blog", "tech_innovation")
        ]
        
        # Search DuckDuckGo (no API key required)
        import random
        shuffled_queries = search_queries.copy()
        random.shuffle(shuffled_queries)
        
        # Limit to 10 queries per run to avoid overwhelming
        queries_to_search = shuffled_queries[:10]
        
        for query, category in queries_to_search:
            try:
                # Get detailed results from DuckDuckGo
                results = self.search_duckduckgo_detailed(query, num_results=5)
                for result in results:
                    url = result.get('url', '')
                    if url and url.startswith('http'):
                        if url not in all_discoveries:
                            all_discoveries[url] = {
                                'url': url,
                                'title': result.get('title', ''),
                                'snippet': result.get('snippet', ''),
                                'source': 'duckduckgo',
                                'search_query': query,
                                'category': category
                            }
                # Rate limiting
                import time
                time.sleep(1)
            except Exception as e:
                logger.error(f"Error searching for '{query}': {str(e)}")
                continue
        
        # Fetch from seed list
        seed_urls = self.fetch_from_seed_list()
        for url in seed_urls:
            if url not in all_discoveries:
                parsed = urlparse(url)
                all_discoveries[url] = {
                    'url': url,
                    'title': '',
                    'snippet': '',
                    'source': 'seed_list',
                    'search_query': '',
                    'category': 'unknown'
                }
        
        # Save to database if session provided and filter out existing URLs
        if db_session:
            from db.models import DiscoveredWebsite, ScrapedWebsite
            saved_count = 0
            new_discoveries = {}
            
            # Get all existing URLs from both tables to filter out
            existing_discovered_urls = set(
                url[0] for url in db_session.query(DiscoveredWebsite.url).all()
            )
            existing_scraped_urls = set(
                url[0] for url in db_session.query(ScrapedWebsite.url).all()
            )
            all_existing_urls = existing_discovered_urls | existing_scraped_urls
            
            logger.info(f"Found {len(all_existing_urls)} existing URLs in database (will filter from {len(all_discoveries)} discovered)")
            
            for url, info in all_discoveries.items():
                try:
                    # Skip if URL already exists in either table
                    if url in all_existing_urls:
                        continue
                    
                    # Save new discovered website
                    parsed = urlparse(url)
                    discovered = DiscoveredWebsite(
                        url=info['url'],
                        domain=parsed.netloc,
                        title=info.get('title', ''),
                        snippet=info.get('snippet', ''),
                        source=info['source'],
                        search_query=info.get('search_query', ''),
                        category=info.get('category', 'unknown')
                    )
                    db_session.add(discovered)
                    saved_count += 1
                    new_discoveries[url] = info
                except Exception as e:
                    logger.error(f"Error saving discovered website {url}: {str(e)}")
                    continue
            
            try:
                db_session.commit()
                filtered_count = len(all_discoveries) - saved_count
                logger.info(f"Saved {saved_count} new discovered websites to database (filtered out {filtered_count} existing URLs)")
            except Exception as e:
                logger.error(f"Error committing discovered websites: {str(e)}")
                db_session.rollback()
                # If commit fails, return empty list to avoid processing duplicates
                return []
            
            # Return only new discoveries
            unique_discoveries = list(new_discoveries.values())
            logger.info(f"Returning {len(unique_discoveries)} new unique website URLs (filtered from {len(all_discoveries)} total discovered)")
            return unique_discoveries
        else:
            # If no db session, return all (but this shouldn't happen in production)
            unique_discoveries = list(all_discoveries.values())
            logger.info(f"Discovered {len(unique_discoveries)} unique website URLs (no DB session to filter)")
            return unique_discoveries
    
    def search_duckduckgo_detailed(self, query: str, num_results: int = 10) -> List[Dict]:
        """
        Search DuckDuckGo and return detailed results with title and snippet
        
        Args:
            query: Search query
            num_results: Number of results to return
            
        Returns:
            List of dicts with 'url', 'title', 'snippet'
        """
        try:
            from duckduckgo_search import DDGS
            logger.info(f"Attempting DuckDuckGo search for: {query}")
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=num_results))
                detailed_results = []
                for r in results:
                    if r.get('href', '').startswith('http'):
                        detailed_results.append({
                            'url': r.get('href', ''),
                            'title': r.get('title', ''),
                            'snippet': r.get('body', '')
                        })
                logger.info(f"DuckDuckGo search found {len(detailed_results)} results for: {query}")
                return detailed_results[:num_results]
        except ImportError:
            # Fallback: return basic URLs without details
            urls = self.search_duckduckgo(query, num_results)
            return [{'url': url, 'title': '', 'snippet': ''} for url in urls]
        except Exception as e:
            logger.error(f"Error in search_duckduckgo_detailed for '{query}': {str(e)}")
            return []

