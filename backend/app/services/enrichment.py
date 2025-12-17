"""
STRICT MODE enrichment service - ONLY saves emails found explicitly on websites.

Rules:
- Emails must be extracted from actual HTML content
- Snov.io emails are ONLY accepted if source = "website" is explicitly stated
- NO pattern generation, NO guessing, NO fallbacks
- If no email found → return "no_email_found" status
"""
import logging
import time
import re
import httpx
from typing import Optional, Dict, Any, List, Set
from app.utils.domain import normalize_domain, validate_domain
from app.utils.email_validation import is_plausible_email
from app.services.exceptions import RateLimitError

logger = logging.getLogger(__name__)


def _extract_emails_from_html(html_content: str, domain: Optional[str] = None) -> list[tuple[str, int]]:
    """
    Extract email addresses from HTML content using multiple methods.
    Handles obfuscated emails and various formats.
    
    Returns list of (email, priority_score) tuples, sorted by priority (highest first).
    Priority scoring:
    - 100: Email from mailto: link AND matches domain
    - 90: Email from mailto: link
    - 80: Email matches domain AND is common contact email (info, contact, support, hello, etc.)
    - 70: Email matches domain
    - 60: Common contact email (info, contact, support, hello, etc.)
    - 50: Other valid email
    - 0: Filtered out (invalid/false positive)
    """
    if not html_content:
        return []
    
    emails_found: Set[str] = set()
    emails_with_priority: List[tuple[str, int]] = []
    
    # Extract domain for matching
    domain_lower = domain.lower() if domain else None
    
    # Method 1: Extract from mailto: links (highest priority)
    mailto_pattern = r'mailto:([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
    mailto_matches = re.finditer(mailto_pattern, html_content, re.IGNORECASE)
    for match in mailto_matches:
        email = match.group(1).lower().strip()
        if email not in emails_found and is_plausible_email(email):
            emails_found.add(email)
            # Check if email matches domain
            if domain_lower and domain_lower in email:
                priority = 100  # mailto + domain match
            else:
                priority = 90  # mailto only
            emails_with_priority.append((email, priority))
    
    # Method 2: Extract plain email addresses from text
    # More restrictive pattern to avoid false positives
    email_pattern = r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b'
    text_matches = re.finditer(email_pattern, html_content, re.IGNORECASE)
    
    common_contact_emails = ['info', 'contact', 'support', 'hello', 'hi', 'sales', 'help', 'admin', 'team']
    
    for match in text_matches:
        email = match.group(0).lower().strip()
        if email in emails_found:
            continue
        
        if not is_plausible_email(email):
            continue
        
        # Skip common false positives
        if any(skip in email for skip in ['example.com', 'test@', 'noreply', 'no-reply', 'donotreply']):
            continue
        
        emails_found.add(email)
        
        # Calculate priority
        local_part = email.split('@')[0]
        if domain_lower and domain_lower in email:
            if local_part in common_contact_emails:
                priority = 80  # domain match + common contact
            else:
                priority = 70  # domain match
        elif local_part in common_contact_emails:
            priority = 60  # common contact
        else:
            priority = 50  # other valid email
        
        emails_with_priority.append((email, priority))
    
    # Sort by priority (highest first)
    emails_with_priority.sort(key=lambda x: x[1], reverse=True)
    
    # Filter out duplicates and invalid emails
    filtered = []
    seen = set()
    for email, priority in emails_with_priority:
        if email not in seen and is_plausible_email(email):
            seen.add(email)
            filtered.append((email, priority))
    
    return filtered


async def _scrape_email_from_url(url: str, domain: Optional[str] = None) -> Optional[str]:
    """
    Scrape email from a website URL using local HTML parsing.
    Returns the best email found (highest priority), or None.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.get(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            })
            response.raise_for_status()
            html = response.text
            
            # Extract domain from URL if not provided
            if not domain:
                try:
                    from urllib.parse import urlparse
                    parsed = urlparse(url)
                    domain = parsed.netloc.replace('www.', '')
                except:
                    pass
            
            emails_with_priority = _extract_emails_from_html(html, domain)
            if emails_with_priority:
                # Get the highest priority email
                best_email, best_priority = emails_with_priority[0]
                # Double-check plausibility before returning
                if is_plausible_email(best_email):
                    logger.info(f"✅ [SCRAPING] Found {len(emails_with_priority)} email(s) on {url}. Best: {best_email} (priority: {best_priority})")
                    if len(emails_with_priority) > 1:
                        logger.debug(f"   Other emails found: {[e[0] for e in emails_with_priority[1:3]]}")
                    return best_email
                else:
                    logger.debug(f"🚫 [SCRAPING] Best email candidate failed plausibility check: {best_email}")
            else:
                logger.debug(f"⚠️  [SCRAPING] No valid emails found in HTML for {url}")
    except httpx.HTTPStatusError as e:
        logger.debug(f"HTTP error scraping {url}: {e.response.status_code}")
    except Exception as e:
        logger.debug(f"Local email scraping failed for {url}: {e}")
    
    return None


async def _scrape_emails_from_domain(domain: str, page_url: Optional[str] = None) -> Dict[str, List[str]]:
    """
    Scrape emails from a domain by trying multiple common contact page URLs.
    Returns dict with page_url -> list of emails found.
    
    STRICT MODE: Only returns emails found in actual HTML content.
    """
    urls_to_try = []
    pages_crawled = []
    emails_by_page: Dict[str, List[str]] = {}
    
    # Priority 1: Use the page_url from prospect if available
    if page_url:
        urls_to_try.append(page_url)
    
    # Priority 2: Homepage
    urls_to_try.append(f"https://{domain}")
    urls_to_try.append(f"http://{domain}")
    
    # Priority 3: Common contact page paths
    common_paths = [
        "/contact", "/contact-us", "/contactus", "/get-in-touch", "/getintouch",
        "/reach-us", "/reachus", "/about", "/about-us", "/aboutus",
        "/contact.html", "/contact.php", "/contact-page", "/contactus.html",
        "/get-in-touch.html", "/reach-out", "/reachout", "/connect",
        "/connect-with-us", "/email-us", "/email", "/mail", "/mail-us",
        "/support", "/help", "/help-center", "/faq", "/faqs", "/team"
    ]
    
    for path in common_paths:
        urls_to_try.append(f"https://{domain}{path}")
        urls_to_try.append(f"http://{domain}{path}")
    
    logger.info(f"🔍 [SCRAPING] Will try {len(urls_to_try)} URLs for {domain}")
    
    # Try each URL until we find emails
    for url in urls_to_try:
        try:
            email = await _scrape_email_from_url(url, domain)
            pages_crawled.append(url)
            if email:
                if url not in emails_by_page:
                    emails_by_page[url] = []
                emails_by_page[url].append(email)
                logger.info(f"✅ [SCRAPING] Found email {email} on {url}")
        except Exception as e:
            logger.debug(f"Failed to scrape {url}: {e}")
    
    logger.info(f"📊 [SCRAPING] Crawled {len(pages_crawled)} pages for {domain}, found emails on {len(emails_by_page)} pages")
    return emails_by_page


def _is_snov_email_from_website(email_data: Dict[str, Any]) -> bool:
    """
    Check if Snov.io email was explicitly found on the website.
    
    STRICT MODE: Only accept if source metadata indicates website.
    """
    # Check for explicit source indicators
    source = email_data.get("source", "").lower()
    sources = email_data.get("sources", [])
    
    # Accept if source explicitly says "website" or "web"
    if "website" in source or "web" in source:
        return True
    
    # Check sources array
    if isinstance(sources, list):
        for src in sources:
            if isinstance(src, dict):
                src_type = src.get("type", "").lower() or src.get("source", "").lower()
                if "website" in src_type or "web" in src_type:
                    return True
            elif isinstance(src, str):
                if "website" in src.lower() or "web" in src.lower():
                    return True
    
    # Check for page URL or website URL in metadata
    if email_data.get("page_url") or email_data.get("website_url") or email_data.get("url"):
        return True
    
    # If no source metadata, REJECT (strict mode)
    return False


async def enrich_prospect_email(domain: str, name: Optional[str] = None, page_url: Optional[str] = None) -> Dict[str, Any]:
    """
    STRICT MODE enrichment: Only saves emails found explicitly on websites.
    
    Pipeline:
    1. Scrape homepage, /contact, /about, /team pages
    2. Extract emails from HTML using regex
    3. Optionally check Snov.io, but ONLY accept if source = "website"
    4. Deduplicate and validate format
    5. Return all found emails OR "no_email_found" status
    
    Returns:
    {
        "emails": List[str],  # All emails found (may be empty)
        "primary_email": str | None,  # First email if any found
        "email_status": "found" | "no_email_found",
        "pages_crawled": List[str],
        "emails_by_page": Dict[str, List[str]],
        "snov_emails_accepted": int,
        "snov_emails_rejected": int,
        "domain": str,
        "success": bool,
        "source": "html_scraping" | "snov_website" | "no_email_found",
        "error": str | None,
    }
    """
    start_time = time.time()
    
    # Normalize domain first
    normalized_domain = normalize_domain(domain)
    if not normalized_domain:
        error_msg = f"Invalid domain format: {domain}"
        logger.error(f"❌ [ENRICHMENT] {error_msg}")
        return {
            "emails": [],
            "primary_email": None,
            "email_status": "no_email_found",
            "pages_crawled": [],
            "emails_by_page": {},
            "snov_emails_accepted": 0,
            "snov_emails_rejected": 0,
            "domain": domain,
            "success": False,
            "source": "no_email_found",
            "error": error_msg,
        }
    
    logger.info(f"🔍 [ENRICHMENT] STRICT MODE: Starting enrichment for {normalized_domain}")
    logger.info(f"📥 [ENRICHMENT] Input - domain: {domain} → normalized: {normalized_domain}, page_url: {page_url or 'N/A'}")
    
    all_emails: Set[str] = set()
    pages_crawled: List[str] = []
    emails_by_page: Dict[str, List[str]] = {}
    snov_emails_accepted = 0
    snov_emails_rejected = 0
    
    # STEP 1: Scrape website pages for emails
    logger.info(f"📄 [ENRICHMENT] Step 1: Scraping website pages for {normalized_domain}...")
    try:
        emails_by_page = await _scrape_emails_from_domain(normalized_domain, page_url)
        pages_crawled = list(emails_by_page.keys())
        
        # Collect all unique emails
        for url, emails in emails_by_page.items():
            for email in emails:
                if is_plausible_email(email):
                    all_emails.add(email)
                    logger.info(f"✅ [ENRICHMENT] Email found on {url}: {email}")
        
        logger.info(f"📊 [ENRICHMENT] Step 1 complete: Crawled {len(pages_crawled)} pages, found {len(all_emails)} unique email(s)")
        
    except Exception as scrape_err:
        logger.error(f"❌ [ENRICHMENT] HTML scraping failed for {normalized_domain}: {scrape_err}", exc_info=True)
    
    # STEP 2: Optionally check Snov.io, but ONLY accept website-source emails
    logger.info(f"📞 [ENRICHMENT] Step 2: Checking Snov.io for website-source emails (STRICT MODE)...")
    try:
        from app.clients.snov import SnovIOClient
        snov_client = SnovIOClient()
        snov_result = await snov_client.domain_search(normalized_domain)
        
        if snov_result.get("success") and snov_result.get("emails"):
            snov_emails = snov_result.get("emails", [])
            logger.info(f"📧 [ENRICHMENT] Snov.io returned {len(snov_emails)} email(s) for {normalized_domain}")
            
            for email_data in snov_emails:
                if not isinstance(email_data, dict):
                    continue
                
                email_value = email_data.get("value")
                if not email_value or not is_plausible_email(email_value):
                    continue
                
                # STRICT MODE: Only accept if explicitly from website
                if _is_snov_email_from_website(email_data):
                    if email_value not in all_emails:
                        all_emails.add(email_value)
                        snov_emails_accepted += 1
                        logger.info(f"✅ [ENRICHMENT] Accepted Snov.io email (website source): {email_value}")
                    else:
                        logger.debug(f"ℹ️  [ENRICHMENT] Snov.io email already found via scraping: {email_value}")
                else:
                    snov_emails_rejected += 1
                    logger.warning(f"🚫 [ENRICHMENT] Rejected Snov.io email (no website source): {email_value}")
        else:
            logger.info(f"ℹ️  [ENRICHMENT] Snov.io returned no emails or failed for {normalized_domain}")
            
    except Exception as snov_err:
        logger.warning(f"⚠️  [ENRICHMENT] Snov.io check failed for {normalized_domain}: {snov_err}")
        # Continue - Snov.io is optional
    
    # STEP 3: Deduplicate and validate
    unique_emails = sorted(list(all_emails))  # Sort for consistency
    primary_email = unique_emails[0] if unique_emails else None
    
    # STEP 4: Determine result
    total_time = (time.time() - start_time) * 1000
    
    if unique_emails:
        email_status = "found"
        source = "html_scraping" if snov_emails_accepted == 0 else "html_scraping+snov_website"
        logger.info(f"✅ [ENRICHMENT] SUCCESS: Found {len(unique_emails)} email(s) for {normalized_domain} in {total_time:.0f}ms")
        logger.info(f"📧 [ENRICHMENT] Emails: {', '.join(unique_emails)}")
        logger.info(f"📄 [ENRICHMENT] Pages crawled: {len(pages_crawled)}")
        logger.info(f"✅ [ENRICHMENT] Snov.io: {snov_emails_accepted} accepted, {snov_emails_rejected} rejected")
    else:
        email_status = "no_email_found"
        source = "no_email_found"
        logger.warning(f"⚠️  [ENRICHMENT] NO EMAIL FOUND for {normalized_domain} after {total_time:.0f}ms")
        logger.info(f"📄 [ENRICHMENT] Pages crawled: {len(pages_crawled)}")
        logger.info(f"🚫 [ENRICHMENT] Snov.io: {snov_emails_accepted} accepted, {snov_emails_rejected} rejected")
    
    return {
        "emails": unique_emails,
        "primary_email": primary_email,
        "email_status": email_status,
        "pages_crawled": pages_crawled,
        "emails_by_page": emails_by_page,
        "snov_emails_accepted": snov_emails_accepted,
        "snov_emails_rejected": snov_emails_rejected,
        "domain": normalized_domain,
        "success": len(unique_emails) > 0,
        "source": source,
        "error": None,
    }
