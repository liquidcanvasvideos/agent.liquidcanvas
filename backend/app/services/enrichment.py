"""
Standalone enrichment service
Can be called from discovery or as a separate job.

Returns a dict compatible with the frontend EnrichmentResult shape
for successful lookups:

{
    "email": str,
    "name": str | None,
    "company": str | None,
    "confidence": float,
    "domain": str,
    "success": bool,
    "source": str | None,
    "error": str | None,
    "status": str | None,  # "rate_limited", "pending_retry", etc.
}

or None when no email candidate could be found.
"""
import logging
import time
import re
import httpx
from typing import Optional, Dict, Any
from app.clients.hunter import HunterIOClient

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
    emails_with_sources = []
    
    # Method 1: Extract from href="mailto:" links (highest priority)
    mailto_pattern = re.compile(r'mailto:([a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,})', re.IGNORECASE)
    mailto_matches = mailto_pattern.findall(html_content)
    for email in mailto_matches:
        email_lower = email.lower().strip()
        if email_lower:
            # Check if matches domain
            priority = 90
            if domain and domain.lower() in email_lower:
                priority = 100  # Mailto + domain match = highest priority
            emails_with_sources.append((email_lower, priority, 'mailto'))
    
    # Method 2: Standard email regex
    email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
    found_emails = email_pattern.findall(html_content)
    
    # Method 3: Decode HTML entities (e.g., &#64; for @, &#46; for .)
    import html
    decoded_html = html.unescape(html_content)
    decoded_emails = email_pattern.findall(decoded_html)
    found_emails.extend(decoded_emails)
    
    # Method 4: Handle obfuscated emails (e.g., "contact at domain dot com")
    obfuscated_pattern = re.compile(
        r'([a-z0-9._%+-]+)\s*(?:at|@|\[at\]|\(at\))\s*([a-z0-9.-]+)\s*(?:dot|\.|\[dot\]|\(dot\))\s*([a-z]{2,})',
        re.IGNORECASE
    )
    obfuscated_matches = obfuscated_pattern.findall(html_content)
    for match in obfuscated_matches:
        if len(match) == 3:
            email = f"{match[0]}@{match[1]}.{match[2]}"
            found_emails.append(email.lower())
    
    # Common contact email prefixes (higher priority)
    common_contact_prefixes = ['info', 'contact', 'support', 'hello', 'hi', 'sales', 'help', 'inquiry', 'enquiry', 'admin', 'team']
    
    # Process and score all found emails
    seen_emails = set()
    for email in found_emails:
        email_lower = email.lower().strip()
        
        # Skip if already processed (from mailto)
        if email_lower in seen_emails:
            continue
        seen_emails.add(email_lower)
        
        # Skip invalid emails
        if not email_lower or '@' not in email_lower:
            continue
        
        # Filter out obvious false positives
        if any(skip in email_lower for skip in [
            'example.com', 'test@', 'noreply', 'no-reply', '@sentry', '@wix',
            'email@email.com', 'test@test.com', 'admin@example.com',
            'your@email.com', 'your.email@', '@domain.com', '@company.com',
            '@a.', '@a.price', '@a.com'  # Filter out partial matches like "kd@a.price"
        ]):
            continue
        
        # Must have valid domain structure
        parts = email_lower.split('@')
        if len(parts) != 2 or '.' not in parts[1]:
            continue
        
        # Check for suspicious patterns (very short domains, single character domains)
        domain_part = parts[1]
        if len(domain_part) < 4 or domain_part.count('.') == 0:
            continue
        
        # Skip emails with very short local parts (likely false positives)
        if len(parts[0]) < 2:
            continue
        
        # Calculate priority score
        priority = 50  # Default priority
        local_part = parts[0]
        email_domain = domain_part
        
        # Check if email domain matches the website domain
        if domain:
            domain_lower = domain.lower().replace('www.', '')
            if domain_lower in email_domain or email_domain in domain_lower:
                priority = 70  # Domain match
                # Check if it's also a common contact email
                if any(prefix in local_part for prefix in common_contact_prefixes):
                    priority = 80  # Domain match + common contact email
            else:
                # Email domain doesn't match website domain - lower priority but still valid
                # Only include if it's a common contact email
                if any(prefix in local_part for prefix in common_contact_prefixes):
                    priority = 60  # Common contact email but different domain
                else:
                    # Different domain and not a common contact email - likely false positive
                    continue
        
        emails_with_sources.append((email_lower, priority, 'html'))
    
    # Sort by priority (highest first), then remove duplicates keeping highest priority
    emails_with_sources.sort(key=lambda x: x[1], reverse=True)
    
    # Remove duplicates, keeping highest priority version
    seen = set()
    filtered = []
    for email, priority, source in emails_with_sources:
        if email not in seen:
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
                logger.info(f"✅ [SCRAPING] Found {len(emails_with_priority)} email(s) on {url}. Best: {best_email} (priority: {best_priority})")
                if len(emails_with_priority) > 1:
                    logger.debug(f"   Other emails found: {[e[0] for e in emails_with_priority[1:3]]}")
                return best_email
            else:
                logger.debug(f"⚠️  [SCRAPING] No valid emails found in HTML for {url}")
    except httpx.HTTPStatusError as e:
        logger.debug(f"HTTP error scraping {url}: {e.response.status_code}")
    except Exception as e:
        logger.debug(f"Local email scraping failed for {url}: {e}")
    
    return None


async def _scrape_email_from_domain(domain: str, page_url: Optional[str] = None) -> Optional[str]:
    """
    Scrape email from a domain by trying multiple common contact page URLs.
    Returns first valid email found, or None.
    
    Tries in order:
    1. Provided page_url (if available)
    2. Homepage
    3. Common contact page paths
    """
    urls_to_try = []
    
    # Priority 1: Use the page_url from prospect if available
    if page_url:
        urls_to_try.append(page_url)
    
    # Priority 2: Homepage
    urls_to_try.append(f"https://{domain}")
    urls_to_try.append(f"http://{domain}")
    
    # Priority 3: Common contact page paths
    common_paths = [
        "/contact",
        "/contact-us",
        "/contactus",
        "/get-in-touch",
        "/getintouch",
        "/reach-us",
        "/reachus",
        "/about",
        "/about-us",
        "/aboutus",
    ]
    
    for path in common_paths:
        urls_to_try.append(f"https://{domain}{path}")
        urls_to_try.append(f"http://{domain}{path}")
    
    logger.info(f"🔍 [SCRAPING] Trying {len(urls_to_try)} URLs for {domain}")
    
    # Try each URL until we find an email
    for url in urls_to_try:
        email = await _scrape_email_from_url(url, domain)
        if email:
            logger.info(f"✅ [SCRAPING] Found email {email} on {url}")
            return email
    
    logger.warning(f"⚠️  [SCRAPING] No emails found after trying {len(urls_to_try)} URLs for {domain}")
    return None


async def enrich_prospect_email(domain: str, name: Optional[str] = None, page_url: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Enrich a prospect's email using Hunter.io.

    This service is intentionally low‑level and is used by both discovery and
    the direct enrichment API.

    Returns a normalized dict on success (see module docstring) or None when
    no usable email candidate is found.
    """
    start_time = time.time()
    logger.info(f"🔍 [ENRICHMENT] Starting enrichment for domain: {domain}, name: {name or 'N/A'}")
    logger.info(f"📥 [ENRICHMENT] Input - domain: {domain}, name: {name}")
    
    try:
        # Initialize Hunter client
        try:
            hunter_client = HunterIOClient()
            logger.info(f"✅ [ENRICHMENT] Hunter.io client initialized")
        except ValueError as e:
            error_msg = f"Hunter.io not configured: {e}"
            logger.error(f"❌ [ENRICHMENT] {error_msg}")
            raise ValueError(error_msg) from e
        
        # Call Hunter.io API
        try:
            hunter_result = await hunter_client.domain_search(domain)
            api_time = (time.time() - start_time) * 1000
            logger.info(f"⏱️  [ENRICHMENT] Hunter.io API call completed in {api_time:.0f}ms")
        except Exception as api_err:
            api_time = (time.time() - start_time) * 1000
            error_msg = f"Hunter.io API call failed after {api_time:.0f}ms: {str(api_err)}"
            logger.error(f"❌ [ENRICHMENT] {error_msg}", exc_info=True)
            raise Exception(error_msg) from api_err
        
        # Process response - handle rate limits specially
        if not hunter_result.get("success"):
            error_msg = hunter_result.get('error', 'Unknown error')
            status = hunter_result.get('status')
            
            # Handle rate limit - return special status, DO NOT return None
            if status == "rate_limited":
                logger.warning(f"⚠️  [ENRICHMENT] Hunter.io rate limited for {domain}")
                # Try local scraping fallback - try multiple contact pages
                try:
                    local_email = await _scrape_email_from_domain(domain, page_url)
                    if local_email:
                        logger.info(f"✅ [ENRICHMENT] Local scraping found email for {domain}: {local_email}")
                        return {
                            "email": local_email,
                            "name": None,
                            "company": None,
                            "confidence": 50.0,  # Lower confidence for local scraping
                            "domain": domain,
                            "success": True,
                            "source": "local_scraping",
                            "error": None,
                            "status": None,
                        }
                    else:
                        # No email found locally, mark for retry
                        logger.warning(f"⚠️  [ENRICHMENT] No email found via local scraping for {domain}, marking for retry")
                        return {
                            "email": None,
                            "name": None,
                            "company": None,
                            "confidence": 0.0,
                            "domain": domain,
                            "success": False,
                            "source": None,
                            "error": "Rate limited and local scraping found no email",
                            "status": "pending_retry",
                        }
                except Exception as scrape_err:
                    logger.warning(f"⚠️  [ENRICHMENT] Local scraping failed for {domain}: {scrape_err}, marking for retry")
                    return {
                        "email": None,
                        "name": None,
                        "company": None,
                        "confidence": 0.0,
                        "domain": domain,
                        "success": False,
                        "source": None,
                        "error": f"Rate limited and local scraping failed: {scrape_err}",
                        "status": "pending_retry",
                    }
            
            # For other errors, try local scraping fallback
            logger.warning(f"⚠️  [ENRICHMENT] Hunter.io returned error: {error_msg}, trying local scraping fallback")
            try:
                local_email = await _scrape_email_from_domain(domain, page_url)
                if local_email:
                    logger.info(f"✅ [ENRICHMENT] Local scraping found email for {domain}: {local_email}")
                    return {
                        "email": local_email,
                        "name": None,
                        "company": None,
                        "confidence": 50.0,
                        "domain": domain,
                        "success": True,
                        "source": "local_scraping",
                        "error": None,
                        "status": None,
                    }
            except Exception as scrape_err:
                logger.debug(f"Local scraping fallback failed for {domain}: {scrape_err}")
            
            # If local scraping also fails, mark for retry instead of returning None
            logger.warning(f"⚠️  [ENRICHMENT] All enrichment methods failed for {domain}, marking for retry")
            return {
                "email": None,
                "name": None,
                "company": None,
                "confidence": 0.0,
                "domain": domain,
                "success": False,
                "source": None,
                "error": error_msg,
                "status": "pending_retry",
            }
        
        emails = hunter_result.get("emails", [])
        if not emails or len(emails) == 0:
            logger.info(f"⚠️  [ENRICHMENT] No emails found for {domain} via Hunter.io, trying local scraping")
            # Try local scraping fallback - try multiple contact pages
            try:
                local_email = await _scrape_email_from_domain(domain, page_url)
                if local_email:
                    logger.info(f"✅ [ENRICHMENT] Local scraping found email for {domain}: {local_email}")
                    return {
                        "email": local_email,
                        "name": None,
                        "company": None,
                        "confidence": 50.0,
                        "domain": domain,
                        "success": True,
                        "source": "local_scraping",
                        "error": None,
                        "status": None,
                    }
            except Exception as scrape_err:
                logger.debug(f"Local scraping fallback failed for {domain}: {scrape_err}")
            
            # Mark for retry instead of returning None
            logger.warning(f"⚠️  [ENRICHMENT] No emails found for {domain}, marking for retry")
            return {
                "email": None,
                "name": None,
                "company": None,
                "confidence": 0.0,
                "domain": domain,
                "success": False,
                "source": None,
                "error": "No emails found via Hunter.io or local scraping",
                "status": "pending_retry",
            }
        
        # Get best email (highest confidence)
        best_email = None
        best_confidence = 0.0
        for email_data in emails:
            if not isinstance(email_data, dict):
                continue
            confidence = float(email_data.get("confidence_score", 0) or 0)
            if confidence > best_confidence:
                best_confidence = confidence
                best_email = email_data
        
        if not best_email or not best_email.get("value"):
            logger.warning(f"⚠️  [ENRICHMENT] No valid email value in response for {domain}")
            return None
        
        email_value = best_email["value"]
        # Build a simple display name from first/last name if present
        first_name = best_email.get("first_name") or ""
        last_name = best_email.get("last_name") or ""
        full_name = f"{first_name} {last_name}".strip() or None
        company = best_email.get("company")
        
        total_time = (time.time() - start_time) * 1000
        
        result: Dict[str, Any] = {
            "email": email_value,
            "name": full_name,
            "company": company,
            "confidence": best_confidence,
            "domain": domain,
            "success": True,
            "source": "hunter_io",
            "error": None,
        }
        
        logger.info(f"✅ [ENRICHMENT] Enriched {domain} in {total_time:.0f}ms")
        logger.info(
            "📤 [ENRICHMENT] Output - email=%s, name=%s, company=%s, confidence=%.1f, source=%s",
            email_value,
            full_name,
            company,
            best_confidence,
            "hunter_io",
        )
        
        return result
        
    except Exception as e:
        total_time = (time.time() - start_time) * 1000
        error_msg = f"Enrichment failed for {domain} after {total_time:.0f}ms: {str(e)}"
        logger.error(f"❌ [ENRICHMENT] {error_msg}", exc_info=True)
        # Re-raise with full context
        raise Exception(error_msg) from e

