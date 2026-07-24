"""
Real-Time Social Media Scraper

Uses Playwright with stealth mode and proxy rotation for live scraping.
Scrapes follower counts, bio data, emails, and link-in-bio URLs.
"""
import logging
import re
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from urllib.parse import urlparse, urljoin
import httpx
from bs4 import BeautifulSoup

from app.utils.email_validation import is_plausible_email

logger = logging.getLogger(__name__)

# Try to import Playwright
try:
    from playwright.async_api import async_playwright, Browser, BrowserContext, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("⚠️  Playwright not installed. Install with: pip install playwright && playwright install chromium")


class RealtimeSocialScraper:
    """
    Real-time browser-based scraper for social media profiles.
    
    Features:
    - Playwright with stealth mode
    - Proxy rotation (if configured)
    - Human-like behavior
    - Extracts follower counts, bio, emails, external links
    """
    
    def __init__(self, use_proxy: bool = False, proxy_list: Optional[List[str]] = None):
        self.use_proxy = use_proxy
        self.proxy_list = proxy_list or []
        self.proxy_index = 0
    
    def _get_next_proxy(self) -> Optional[Dict[str, str]]:
        """Get next proxy from rotation"""
        if not self.use_proxy or not self.proxy_list:
            return None
        
        proxy = self.proxy_list[self.proxy_index % len(self.proxy_list)]
        self.proxy_index += 1
        
        # Parse proxy format: http://user:pass@host:port
        parsed = urlparse(proxy)
        return {
            "server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}",
            "username": parsed.username,
            "password": parsed.password,
        }
    
    async def _create_stealth_context(self, browser: Browser) -> BrowserContext:
        """Create a browser context with stealth settings"""
        proxy = self._get_next_proxy()
        
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='en-US',
            timezone_id='America/New_York',
            permissions=['geolocation'],
            proxy=proxy,
            # Stealth settings
            java_script_enabled=True,
            bypass_csp=True,
            ignore_https_errors=False,
            # Extra headers to appear more human
            extra_http_headers={
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Cache-Control': 'max-age=0',
            }
        )
        
        # Add stealth scripts to avoid detection
        await context.add_init_script("""
            // Override navigator.webdriver
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Override chrome runtime
            window.chrome = {
                runtime: {}
            };
            
            // Override permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)
        
        return context
    
    async def scrape_instagram_realtime(self, profile_url: str) -> Dict[str, Any]:
        """
        Real-time Instagram scraping using Playwright.
        
        Returns:
            {
                "follower_count": int | None,
                "bio_text": str | None,
                "email": str | None,
                "external_links": List[str],
                "engagement_rate": float | None,
                "success": bool,
                "error": str | None
            }
        """
        if not PLAYWRIGHT_AVAILABLE:
            logger.error("❌ [REALTIME INSTAGRAM] Playwright not available")
            return {"success": False, "error": "Playwright not installed"}
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox',
                    ]
                )
                
                context = await self._create_stealth_context(browser)
                page = await context.new_page()
                
                logger.info(f"🔍 [REALTIME INSTAGRAM] Loading {profile_url}...")
                
                # Navigate with human-like delays
                await page.goto(profile_url, wait_until='networkidle', timeout=30000)
                await asyncio.sleep(2)  # Wait for JavaScript to render
                
                # Scroll to trigger lazy loading
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(1)
                
                html = await page.content()
                
                result = {
                    "follower_count": None,
                    "bio_text": None,
                    "email": None,
                    "external_links": [],
                    "engagement_rate": 2.5,
                    "success": True,
                    "error": None
                }
                
                # Extract follower count - intensive patterns
                follower_patterns = [
                    r'"edge_followed_by":\{"count":(\d+)\}',
                    r'"follower_count":(\d+)',
                    r'"userInteractionCount":(\d+)',
                    r'"followers":\{"count":(\d+)\}',
                    r'"followerCount":(\d+)',
                ]
                
                for pattern in follower_patterns:
                    matches = re.findall(pattern, html, re.IGNORECASE)
                    if matches:
                        try:
                            count_str = matches[0].replace(',', '').strip()
                            result["follower_count"] = int(count_str)
                            logger.info(f"✅ [REALTIME INSTAGRAM] Found follower count: {result['follower_count']}")
                            break
                        except (ValueError, IndexError):
                            continue
                
                # Extract bio text
                try:
                    bio_text = await page.evaluate("""
                        () => {
                            // Try multiple selectors for bio
                            const selectors = [
                                'meta[property="og:description"]',
                                '[data-testid="user-bio"]',
                                'article header section',
                                'h1 + span',
                            ];
                            
                            for (const selector of selectors) {
                                const element = document.querySelector(selector);
                                if (element) {
                                    const text = element.textContent || element.content || '';
                                    if (text.trim().length > 0) {
                                        return text.trim();
                                    }
                                }
                            }
                            return null;
                        }
                    """)
                    
                    if bio_text:
                        result["bio_text"] = bio_text
                        logger.info(f"✅ [REALTIME INSTAGRAM] Found bio: {bio_text[:50]}...")
                except Exception as e:
                    logger.debug(f"⚠️  [REALTIME INSTAGRAM] Could not extract bio: {e}")
                
                # Extract email from bio
                if result["bio_text"]:
                    email_patterns = [
                        r'mailto:([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                        r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                    ]
                    
                    for pattern in email_patterns:
                        matches = re.findall(pattern, result["bio_text"])
                        for match in matches:
                            email = match.lower().strip()
                            if is_plausible_email(email) and 'instagram.com' not in email:
                                result["email"] = email
                                logger.info(f"✅ [REALTIME INSTAGRAM] Found email: {email}")
                                break
                        if result["email"]:
                            break
                
                # Extract external links (link-in-bio)
                try:
                    external_links = await page.evaluate("""
                        () => {
                            const links = [];
                            // Look for link-in-bio
                            const linkElements = document.querySelectorAll('a[href]');
                            for (const link of linkElements) {
                                const href = link.getAttribute('href');
                                if (href && !href.includes('instagram.com') && 
                                    (href.startsWith('http://') || href.startsWith('https://'))) {
                                    links.push(href);
                                }
                            }
                            return [...new Set(links)]; // Deduplicate
                        }
                    """)
                    
                    result["external_links"] = external_links[:5]  # Limit to 5 links
                    if external_links:
                        logger.info(f"✅ [REALTIME INSTAGRAM] Found {len(external_links)} external links")
                except Exception as e:
                    logger.debug(f"⚠️  [REALTIME INSTAGRAM] Could not extract external links: {e}")
                
                # If external links found, crawl them for emails
                if result["external_links"]:
                    for link_url in result["external_links"][:2]:  # Limit to 2 links
                        try:
                            async with httpx.AsyncClient(timeout=10.0) as client:
                                link_response = await client.get(link_url, headers={
                                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                                })
                                link_html = link_response.text
                                
                                # Extract emails from linked page
                                email_patterns = [
                                    r'mailto:([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                                    r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                                ]
                                
                                for pattern in email_patterns:
                                    matches = re.findall(pattern, link_html)
                                    for match in matches:
                                        email = match.lower().strip()
                                        if is_plausible_email(email) and not result["email"]:
                                            result["email"] = email
                                            logger.info(f"✅ [REALTIME INSTAGRAM] Found email from link-in-bio: {email}")
                                            break
                                    if result["email"]:
                                        break
                        except Exception as e:
                            logger.debug(f"⚠️  [REALTIME INSTAGRAM] Could not crawl link {link_url}: {e}")
                
                await browser.close()
                
                return result
                
        except Exception as e:
            logger.error(f"❌ [REALTIME INSTAGRAM] Error scraping {profile_url}: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    async def scrape_linkedin_realtime(self, profile_url: str) -> Dict[str, Any]:
        """Real-time LinkedIn scraping using Playwright"""
        if not PLAYWRIGHT_AVAILABLE:
            return {"success": False, "error": "Playwright not installed"}
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await self._create_stealth_context(browser)
                page = await context.new_page()
                
                logger.info(f"🔍 [REALTIME LINKEDIN] Loading {profile_url}...")
                
                await page.goto(profile_url, wait_until='networkidle', timeout=30000)
                await asyncio.sleep(2)
                
                html = await page.content()
                
                result = {
                    "follower_count": None,
                    "bio_text": None,
                    "email": None,
                    "external_links": [],
                    "engagement_rate": 1.5,
                    "success": True,
                    "error": None
                }
                
                # Extract follower/connection count
                follower_patterns = [
                    r'"connectionsCount":(\d+)',
                    r'"followerCount":(\d+)',
                    r'(\d+(?:,\d+)*)\+?\s*connections?',
                    r'(\d+(?:,\d+)*)\s*followers?',
                ]
                
                for pattern in follower_patterns:
                    matches = re.findall(pattern, html, re.IGNORECASE)
                    if matches:
                        try:
                            count_str = matches[0].replace(',', '').strip()
                            result["follower_count"] = int(count_str)
                            logger.info(f"✅ [REALTIME LINKEDIN] Found follower count: {result['follower_count']}")
                            break
                        except (ValueError, IndexError):
                            continue
                
                # Extract bio/headline
                try:
                    bio_text = await page.evaluate("""
                        () => {
                            const selectors = [
                                'meta[property="og:description"]',
                                '.text-body-medium',
                                'h1 + p',
                            ];
                            for (const selector of selectors) {
                                const el = document.querySelector(selector);
                                if (el) {
                                    const text = el.textContent || el.content || '';
                                    if (text.trim().length > 0) return text.trim();
                                }
                            }
                            return null;
                        }
                    """)
                    if bio_text:
                        result["bio_text"] = bio_text
                except Exception as e:
                    logger.debug(f"⚠️  [REALTIME LINKEDIN] Could not extract bio: {e}")
                
                # Extract email
                if result["bio_text"]:
                    email_patterns = [
                        r'mailto:([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                        r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                    ]
                    for pattern in email_patterns:
                        matches = re.findall(pattern, result["bio_text"])
                        for match in matches:
                            email = match.lower().strip()
                            if is_plausible_email(email) and 'linkedin.com' not in email:
                                result["email"] = email
                                break
                        if result["email"]:
                            break
                
                await browser.close()
                return result
                
        except Exception as e:
            logger.error(f"❌ [REALTIME LINKEDIN] Error: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    async def scrape_facebook_realtime(self, profile_url: str) -> Dict[str, Any]:
        """Real-time Facebook scraping using Playwright"""
        if not PLAYWRIGHT_AVAILABLE:
            return {"success": False, "error": "Playwright not installed"}
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await self._create_stealth_context(browser)
                page = await context.new_page()
                
                logger.info(f"🔍 [REALTIME FACEBOOK] Loading {profile_url}...")
                
                await page.goto(profile_url, wait_until='networkidle', timeout=30000)
                await asyncio.sleep(2)
                
                html = await page.content()
                
                result = {
                    "follower_count": None,
                    "bio_text": None,
                    "email": None,
                    "external_links": [],
                    "engagement_rate": 2.0,
                    "success": True,
                    "error": None
                }
                
                # Extract follower count
                follower_patterns = [
                    r'"follower_count":(\d+)',
                    r'"likes":(\d+)',
                    r'(\d+(?:,\d+)*)\s*(?:people|person)\s*(?:like|follow)',
                ]
                
                for pattern in follower_patterns:
                    matches = re.findall(pattern, html, re.IGNORECASE)
                    if matches:
                        try:
                            count_str = matches[0].replace(',', '').strip()
                            result["follower_count"] = int(count_str)
                            logger.info(f"✅ [REALTIME FACEBOOK] Found follower count: {result['follower_count']}")
                            break
                        except (ValueError, IndexError):
                            continue
                
                # Extract bio
                try:
                    bio_text = await page.evaluate("""
                        () => {
                            const selectors = [
                                'meta[property="og:description"]',
                                '[data-testid="profile-bio"]',
                            ];
                            for (const selector of selectors) {
                                const el = document.querySelector(selector);
                                if (el) {
                                    const text = el.textContent || el.content || '';
                                    if (text.trim().length > 0) return text.trim();
                                }
                            }
                            return null;
                        }
                    """)
                    if bio_text:
                        result["bio_text"] = bio_text
                except Exception as e:
                    logger.debug(f"⚠️  [REALTIME FACEBOOK] Could not extract bio: {e}")
                
                # Extract email
                if result["bio_text"]:
                    email_patterns = [
                        r'mailto:([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                        r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                    ]
                    for pattern in email_patterns:
                        matches = re.findall(pattern, result["bio_text"])
                        for match in matches:
                            email = match.lower().strip()
                            if is_plausible_email(email) and 'facebook.com' not in email:
                                result["email"] = email
                                break
                        if result["email"]:
                            break
                
                await browser.close()
                return result
                
        except Exception as e:
            logger.error(f"❌ [REALTIME FACEBOOK] Error: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    async def scrape_tiktok_realtime(self, profile_url: str) -> Dict[str, Any]:
        """Real-time TikTok scraping using Playwright"""
        if not PLAYWRIGHT_AVAILABLE:
            return {"success": False, "error": "Playwright not installed"}
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await self._create_stealth_context(browser)
                page = await context.new_page()
                
                logger.info(f"🔍 [REALTIME TIKTOK] Loading {profile_url}...")
                
                await page.goto(profile_url, wait_until='networkidle', timeout=30000)
                await asyncio.sleep(2)
                
                html = await page.content()
                
                result = {
                    "follower_count": None,
                    "bio_text": None,
                    "email": None,
                    "external_links": [],
                    "engagement_rate": 3.5,
                    "success": True,
                    "error": None
                }
                
                # Extract follower count
                follower_patterns = [
                    r'"followerCount":(\d+)',
                    r'"follower_count":(\d+)',
                    r'(\d+(?:,\d+)*)\s*followers?',
                ]
                
                for pattern in follower_patterns:
                    matches = re.findall(pattern, html, re.IGNORECASE)
                    if matches:
                        try:
                            count_str = matches[0].replace(',', '').strip()
                            result["follower_count"] = int(count_str)
                            logger.info(f"✅ [REALTIME TIKTOK] Found follower count: {result['follower_count']}")
                            break
                        except (ValueError, IndexError):
                            continue
                
                # Extract bio
                try:
                    bio_text = await page.evaluate("""
                        () => {
                            const selectors = [
                                'meta[property="og:description"]',
                                '[data-e2e="user-bio"]',
                            ];
                            for (const selector of selectors) {
                                const el = document.querySelector(selector);
                                if (el) {
                                    const text = el.textContent || el.content || '';
                                    if (text.trim().length > 0) return text.trim();
                                }
                            }
                            return null;
                        }
                    """)
                    if bio_text:
                        result["bio_text"] = bio_text
                except Exception as e:
                    logger.debug(f"⚠️  [REALTIME TIKTOK] Could not extract bio: {e}")
                
                # Extract email
                if result["bio_text"]:
                    email_patterns = [
                        r'mailto:([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                        r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                    ]
                    for pattern in email_patterns:
                        matches = re.findall(pattern, result["bio_text"])
                        for match in matches:
                            email = match.lower().strip()
                            if is_plausible_email(email) and 'tiktok.com' not in email:
                                result["email"] = email
                                break
                        if result["email"]:
                            break
                
                await browser.close()
                return result
                
        except Exception as e:
            logger.error(f"❌ [REALTIME TIKTOK] Error: {e}", exc_info=True)
            return {"success": False, "error": str(e)}


async def scrape_social_profile_realtime(profile_url: str, platform: str, use_proxy: bool = False) -> Dict[str, Any]:
    """
    Real-time scraping wrapper for all platforms.
    
    Args:
        profile_url: Full URL to the profile
        platform: 'linkedin', 'instagram', 'facebook', or 'tiktok'
        use_proxy: Whether to use proxy rotation
    
    Returns:
        {
            "follower_count": int | None,
            "bio_text": str | None,
            "email": str | None,
            "external_links": List[str],
            "engagement_rate": float | None,
            "success": bool,
            "error": str | None
        }
    """
    scraper = RealtimeSocialScraper(use_proxy=use_proxy)
    platform_lower = platform.lower()
    
    if platform_lower == 'instagram':
        return await scraper.scrape_instagram_realtime(profile_url)
    elif platform_lower == 'linkedin':
        return await scraper.scrape_linkedin_realtime(profile_url)
    elif platform_lower == 'facebook':
        return await scraper.scrape_facebook_realtime(profile_url)
    elif platform_lower == 'tiktok':
        return await scraper.scrape_tiktok_realtime(profile_url)
    else:
        logger.warning(f"⚠️  [REALTIME SCRAPE] Unknown platform: {platform}")
        return {"success": False, "error": f"Unknown platform: {platform}"}

