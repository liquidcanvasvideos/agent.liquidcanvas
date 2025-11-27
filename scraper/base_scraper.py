"""
Base scraper class with common functionality
"""
import requests
from bs4 import BeautifulSoup
from typing import Optional, Dict, Any, Tuple
from utils.config import settings
from scraper.rate_limiter import RateLimiter
import time
import logging

logger = logging.getLogger(__name__)


class BaseScraper:
    """Base class for all scrapers"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": settings.SCRAPER_USER_AGENT
        })
        self.timeout = settings.SCRAPER_TIMEOUT
        self.max_retries = settings.SCRAPER_MAX_RETRIES
        self.rate_limiter = RateLimiter(max_requests=10, time_window=60)
    
    def fetch_page(self, url: str, use_rate_limit: bool = True, silent_404: bool = False) -> Tuple[Optional[BeautifulSoup], Optional[str]]:
        """
        Fetch and parse a web page with error handling and rate limiting
        
        Args:
            url: URL to fetch
            use_rate_limit: Whether to apply rate limiting
            silent_404: If True, log 404 errors at DEBUG level instead of ERROR (for expected 404s)
            
        Returns:
            Tuple of (BeautifulSoup object or None, raw HTML string or None)
        """
        from urllib.parse import urlparse
        
        # Apply rate limiting
        if use_rate_limit:
            domain = urlparse(url).netloc
            self.rate_limiter.wait_if_needed(domain)
        
        # Retry logic
        last_error = None
        is_404 = False
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(
                    url,
                    timeout=self.timeout,
                    allow_redirects=True
                )
                response.raise_for_status()
                raw_html = response.text
                soup = BeautifulSoup(raw_html, "lxml")
                return soup, raw_html
            except requests.exceptions.HTTPError as e:
                # Check if it's a 404 error - check both response status and error message
                status_code = None
                if hasattr(e, 'response') and e.response is not None:
                    status_code = e.response.status_code
                
                # Also check the error message string for 404 indicators
                error_str = str(e)
                error_msg_lower = error_str.lower()
                
                # Check for 404 in multiple ways - be very explicit
                is_404_error = False
                if status_code == 404:
                    is_404_error = True
                elif '404' in error_msg_lower:
                    is_404_error = True
                elif 'not found' in error_msg_lower:
                    is_404_error = True
                
                if is_404_error:
                    is_404 = True
                    last_error = f"404 Client Error: Not Found for url: {url}"
                    break  # Don't retry 404s - exit immediately
                else:
                    last_error = f"HTTP error: {str(e)}"
                    if attempt < self.max_retries - 1:
                        time.sleep(1)
            except requests.exceptions.Timeout as e:
                last_error = f"Timeout: {str(e)}"
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
            except requests.exceptions.RequestException as e:
                last_error = f"Request error: {str(e)}"
                if attempt < self.max_retries - 1:
                    time.sleep(1)
            except Exception as e:
                last_error = f"Unexpected error: {str(e)}"
                break
        
        # Log at appropriate level
        if is_404 and silent_404:
            logger.debug(f"Page not found (expected): {url}")
        else:
            logger.error(f"Error fetching {url} after {self.max_retries} attempts: {last_error}")
        return None, None
    
    def extract_metadata(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """
        Extract comprehensive metadata from a page
        
        Args:
            soup: BeautifulSoup object
            url: Source URL
            
        Returns:
            Dictionary with metadata
        """
        metadata = {
            "url": url,
            "title": "",
            "description": "",
            "keywords": [],
            "og_image": "",
            "og_description": "",
            "og_title": "",
            "twitter_card": "",
            "canonical_url": "",
            "author": "",
            "language": ""
        }
        
        if soup:
            # Title
            title_tag = soup.find("title")
            if title_tag:
                metadata["title"] = title_tag.get_text(strip=True)
            
            # Meta description
            meta_desc = soup.find("meta", attrs={"name": "description"})
            if meta_desc:
                metadata["description"] = meta_desc.get("content", "")
            
            # Keywords
            meta_keywords = soup.find("meta", attrs={"name": "keywords"})
            if meta_keywords:
                keywords = meta_keywords.get("content", "")
                metadata["keywords"] = [k.strip() for k in keywords.split(",") if k.strip()]
            
            # Open Graph tags
            og_image = soup.find("meta", property="og:image")
            if og_image:
                metadata["og_image"] = og_image.get("content", "")
            
            og_desc = soup.find("meta", property="og:description")
            if og_desc:
                metadata["og_description"] = og_desc.get("content", "")
            
            og_title = soup.find("meta", property="og:title")
            if og_title:
                metadata["og_title"] = og_title.get("content", "")
            
            # Twitter Card
            twitter_card = soup.find("meta", attrs={"name": "twitter:card"})
            if twitter_card:
                metadata["twitter_card"] = twitter_card.get("content", "")
            
            # Canonical URL
            canonical = soup.find("link", rel="canonical")
            if canonical:
                metadata["canonical_url"] = canonical.get("href", "")
            
            # Author
            author = soup.find("meta", attrs={"name": "author"})
            if author:
                metadata["author"] = author.get("content", "")
            
            # Language
            html_tag = soup.find("html")
            if html_tag:
                metadata["language"] = html_tag.get("lang", "")
        
        return metadata

