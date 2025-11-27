"""
Contact page detection and crawling
"""
from typing import List, Optional, Tuple
from urllib.parse import urljoin, urlparse
from scraper.base_scraper import BaseScraper
import logging

logger = logging.getLogger(__name__)


class ContactPageCrawler(BaseScraper):
    """Crawl common contact page paths"""
    
    # Common contact page paths (expanded list)
    CONTACT_PATHS = [
        "/contact",
        "/about",
        "/support",
        "/info",
        "/team",
        "/contact-us",
        "/get-in-touch",
        "/reach-us",
        "/connect",
        "/about-us",
        "/contact.html",
        "/about.html",
        "/contactus",
        "/aboutus",
        "/getintouch",
        "/reachout",
        "/say-hello",
        "/hello",
        "/help",
        "/faq",
        "/questions",
        "/inquiry",
        "/inquiries",
        "/message",
        "/messages",
        "/write-us",
        "/email-us",
        "/call-us",
        "/location",
        "/locations",
        "/office",
        "/offices",
        "/headquarters",
        "/hq",
        "/address",
        "/find-us",
        "/findus",
        "/visit-us",
        "/visit",
        "/careers",
        "/career",
        "/jobs",
        "/join-us",
        "/join",
        "/press",
        "/press-kit",
        "/media",
        "/news",
        "/blog",
        "/newsletter",
        "/subscribe",
    ]
    
    def detect_contact_page(self, base_url: str) -> List[str]:
        """
        Detect contact pages by trying common paths
        
        Args:
            base_url: Base URL of the website
            
        Returns:
            List of found contact page URLs
        """
        found_pages = []
        total_checked = len(self.CONTACT_PATHS)
        
        logger.debug(f"Checking {total_checked} common contact page paths for {base_url}")
        
        for path in self.CONTACT_PATHS:
            contact_url = urljoin(base_url.rstrip("/"), path)
            if self._check_page_exists(contact_url):
                found_pages.append(contact_url)
                logger.info(f"Found contact page: {contact_url}")
        
        if found_pages:
            logger.info(f"✅ Found {len(found_pages)} contact page(s) out of {total_checked} paths checked for {base_url}")
        else:
            logger.debug(f"No contact pages found from common paths for {base_url} (this is normal)")
        
        return found_pages
    
    def _check_page_exists(self, url: str) -> bool:
        """
        Check if a page exists and is accessible
        
        Args:
            url: URL to check
            
        Returns:
            True if page exists and is accessible
        """
        try:
            # Use silent_404=True to avoid logging expected 404s as errors
            soup, _ = self.fetch_page(url, use_rate_limit=True, silent_404=True)
            if soup:
                # Check if page has contact-related content
                text = soup.get_text().lower()
                contact_indicators = [
                    "contact", "email", "phone", "address",
                    "reach", "connect", "get in touch"
                ]
                
                # If page has contact indicators, consider it valid
                if any(indicator in text for indicator in contact_indicators):
                    return True
                
                # Also check for forms
                if soup.find("form"):
                    return True
        except Exception as e:
            logger.debug(f"Page check failed for {url}: {str(e)}")
        
        return False
    
    def crawl_contact_pages(self, base_url: str) -> List[Tuple[str, str]]:
        """
        Crawl all detected contact pages and return their HTML
        
        Args:
            base_url: Base URL of the website
            
        Returns:
            List of tuples (url, html_content)
        """
        contact_pages = self.detect_contact_page(base_url)
        results = []
        
        for page_url in contact_pages:
            try:
                # Use silent_404=True since we already verified the page exists
                soup, raw_html = self.fetch_page(page_url, use_rate_limit=True, silent_404=True)
                if soup and raw_html:
                    results.append((page_url, raw_html))
            except Exception as e:
                logger.error(f"Error crawling contact page {page_url}: {str(e)}")
        
        return results

