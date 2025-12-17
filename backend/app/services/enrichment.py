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
from typing import Optional, Dict, Any, List
from app.clients.snov import SnovIOClient
from app.utils.domain import normalize_domain, validate_domain
from app.utils.email_validation import is_plausible_email
from app.services.provider_state import get_provider_state
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
    # Only process if the pattern already looks email-like
    obfuscated_pattern = re.compile(
        r'([a-z0-9._%+-]+)\s*(?:at|@|\[at\]|\(at\))\s*([a-z0-9.-]+)\s*(?:dot|\.|\[dot\]|\(dot\))\s*([a-z]{2,})',
        re.IGNORECASE
    )
    obfuscated_matches = obfuscated_pattern.findall(html_content)
    for match in obfuscated_matches:
        if len(match) == 3:
            email = f"{match[0]}@{match[1]}.{match[2]}"
            # Only add if it's plausible (filters out garbage)
            if is_plausible_email(email):
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
        
        # Use strict plausibility check (filters out .css, .jpg, CSS selectors, etc.)
        if not is_plausible_email(email_lower):
            logger.debug(f"🚫 [ENRICHMENT] Discarding implausible email candidate: {email_lower}")
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


def _generate_email_patterns(domain: str, person_name: Optional[str] = None) -> List[str]:
    """
    Generate common email patterns for a domain.
    
    Args:
        domain: Domain name (e.g., "example.com")
        person_name: Optional person name for personalized patterns
    
    Returns:
        List of generated email addresses
    """
    if not domain or not validate_domain(domain):
        return []
    
    patterns = []
    
    # Common contact email patterns (expanded list for better coverage)
    common_prefixes = [
        'info', 'contact', 'support', 'hello', 'sales', 'help', 'admin', 'team',
        'hi', 'inquiry', 'enquiry', 'general', 'office', 'main', 'mail',
        'email', 'reach', 'connect', 'getintouch', 'get-in-touch', 'reachout',
        'business', 'service', 'services', 'customerservice', 'customer-service',
        'marketing', 'press', 'media', 'pr', 'publicrelations', 'public-relations'
    ]
    for prefix in common_prefixes:
        patterns.append(f"{prefix}@{domain}")
    
    # Personalized patterns if name provided
    if person_name:
        name_parts = person_name.strip().lower().split()
        if len(name_parts) >= 1:
            first_name = name_parts[0]
            # firstname@domain
            patterns.append(f"{first_name}@{domain}")
            
            if len(name_parts) >= 2:
                last_name = name_parts[1]
                # firstname.lastname@domain
                patterns.append(f"{first_name}.{last_name}@{domain}")
                # firstnamelastname@domain
                patterns.append(f"{first_name}{last_name}@{domain}")
    
    return patterns


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
    
    # Priority 3: Common contact page paths (expanded list)
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
        "/contact.html",
        "/contact.php",
        "/contact-page",
        "/contactus.html",
        "/get-in-touch.html",
        "/reach-out",
        "/reachout",
        "/connect",
        "/connect-with-us",
        "/email-us",
        "/email",
        "/mail",
        "/mail-us",
        "/support",
        "/help",
        "/help-center",
        "/faq",
        "/faqs",
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
    Enrich a prospect's email using Snov.io.

    This service is intentionally low‑level and is used by both discovery and
    the direct enrichment API.

    Returns a normalized dict on success (see module docstring) or None when
    no usable email candidate is found.
    """
    start_time = time.time()
    
    # Normalize domain first
    normalized_domain = normalize_domain(domain)
    if not normalized_domain:
        error_msg = f"Invalid domain format: {domain}"
        logger.error(f"❌ [ENRICHMENT] {error_msg}")
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
    
    logger.info(f"🔍 [ENRICHMENT] Starting enrichment for domain: {normalized_domain}, name: {name or 'N/A'}")
    logger.info(f"📥 [ENRICHMENT] Input - domain: {domain} → normalized: {normalized_domain}, name: {name}")
    
    try:
        # TEMP LOG: Before first Snov API call
        logger.info(f"📞 [ENRICHMENT] About to initialize Snov.io client for {normalized_domain}...")
        
        # Initialize Snov client
        try:
            snov_client = SnovIOClient()
            logger.info(f"✅ [ENRICHMENT] Snov.io client initialized")
        except ValueError as e:
            error_msg = f"Snov.io not configured: {e}"
            logger.error(f"❌ [ENRICHMENT] {error_msg}", exc_info=True)
            raise ValueError(error_msg) from e
        
        # TEMP LOG: Before first Snov API call
        logger.info(f"📞 [ENRICHMENT] About to call Snov.io domain_search API for {normalized_domain}...")
        
        # Call Snov.io API - use ONLY domain-search endpoint
        try:
            snov_result = await snov_client.domain_search(normalized_domain)
            api_time = (time.time() - start_time) * 1000
            logger.info(f"⏱️  [ENRICHMENT] Snov.io domain-search API call completed in {api_time:.0f}ms")
        except Exception as api_err:
            api_time = (time.time() - start_time) * 1000
            error_msg = f"Snov.io API call failed after {api_time:.0f}ms: {str(api_err)}"
            logger.error(f"❌ [ENRICHMENT] {error_msg}", exc_info=True)
            raise Exception(error_msg) from api_err
        
        # Process response - handle rate limits specially
        if not snov_result.get("success"):
            error_msg = snov_result.get('error', 'Unknown error')
            status = snov_result.get('status')
            
            # Handle rate limit - return special status, DO NOT return None
            if status == "rate_limited":
                logger.warning(f"⚠️  [ENRICHMENT] Snov.io rate limited for {normalized_domain}")
                # Try local scraping fallback - try multiple contact pages
                try:
                    local_email = await _scrape_email_from_domain(normalized_domain, page_url)
                    if local_email:
                        logger.info(f"✅ [ENRICHMENT] Local scraping found email for {normalized_domain}: {local_email}")
                        return {
                            "email": local_email,
                            "name": None,
                            "company": None,
                            "confidence": 50.0,  # Lower confidence for local scraping
                            "domain": normalized_domain,
                            "success": True,
                            "source": "local_scraping",
                            "error": None,
                            "status": None,
                        }
                    else:
                        # No email found locally, mark for retry
                        logger.warning(f"⚠️  [ENRICHMENT] No email found via local scraping for {normalized_domain}, marking for retry")
                        return {
                            "email": None,
                            "name": None,
                            "company": None,
                            "confidence": 0.0,
                            "domain": normalized_domain,
                            "success": False,
                            "source": None,
                            "error": "Rate limited and local scraping found no email",
                            "status": "pending_retry",
                        }
                except Exception as scrape_err:
                    logger.warning(f"⚠️  [ENRICHMENT] Local scraping failed for {normalized_domain}: {scrape_err}, marking for retry")
                    return {
                        "email": None,
                        "name": None,
                        "company": None,
                        "confidence": 0.0,
                        "domain": normalized_domain,
                        "success": False,
                        "source": None,
                        "error": f"Rate limited and local scraping failed: {scrape_err}",
                        "status": "pending_retry",
                    }
            
            # For other errors, try local scraping fallback
            logger.warning(f"⚠️  [ENRICHMENT] Snov.io returned error: {error_msg}, trying local scraping fallback")
            try:
                local_email = await _scrape_email_from_domain(normalized_domain, page_url)
                if local_email:
                    logger.info(f"✅ [ENRICHMENT] Local scraping found email for {normalized_domain}: {local_email}")
                    return {
                        "email": local_email,
                        "name": None,
                        "company": None,
                        "confidence": 50.0,
                        "domain": normalized_domain,
                        "success": True,
                        "source": "local_scraping",
                        "error": None,
                        "status": None,
                    }
            except Exception as scrape_err:
                logger.debug(f"Local scraping fallback failed for {normalized_domain}: {scrape_err}")
            
            # If local scraping also fails, mark for retry instead of returning None
            logger.warning(f"⚠️  [ENRICHMENT] All enrichment methods failed for {normalized_domain}, marking for retry")
            return {
                "email": None,
                "name": None,
                "company": None,
                "confidence": 0.0,
                "domain": normalized_domain,
                "success": False,
                "source": None,
                "error": error_msg,
                "status": "pending_retry",
            }
        
        emails = snov_result.get("emails", [])
        if not emails or len(emails) == 0:
            # Check if this was a 404 (domain not in database) - don't log as warning
            message = snov_result.get("message", "")
            if "not found in Snov.io database" in message or "Domain not found" in message:
                logger.info(f"ℹ️  [ENRICHMENT] Domain {normalized_domain} not in Snov.io database, trying local scraping fallback")
            else:
                logger.info(f"⚠️  [ENRICHMENT] No emails found for {normalized_domain} via Snov.io, trying fallback methods")
            
            # Fallback 1: Try local HTML scraping
            try:
                local_email = await _scrape_email_from_domain(normalized_domain, page_url)
                if local_email:
                    logger.info(f"✅ [ENRICHMENT] Local scraping found email for {normalized_domain}: {local_email}")
                    return {
                        "email": local_email,
                        "name": None,
                        "company": None,
                        "confidence": 50.0,
                        "domain": normalized_domain,
                        "success": True,
                        "source": "local_scraping",
                        "error": None,
                        "status": None,
                    }
            except Exception as scrape_err:
                logger.debug(f"Local scraping fallback failed for {normalized_domain}: {scrape_err}")
            
            # Fallback 2: Generate email patterns and verify
            try:
                generated_patterns = _generate_email_patterns(normalized_domain, name)
                logger.info(f"🔍 [ENRICHMENT] Generated {len(generated_patterns)} email patterns for {normalized_domain}")
                
                # Try to verify patterns (increased limit for better coverage)
                for pattern_email in generated_patterns[:10]:  # Increased from 5 to 10 to try more patterns
                    try:
                        verify_result = await snov_client.email_verifier(pattern_email)
                        if verify_result.get("success") and verify_result.get("result") == "deliverable":
                            score = verify_result.get("score", 0)
                            logger.info(f"✅ [ENRICHMENT] Verified pattern email {pattern_email} (score: {score})")
                            return {
                                "email": pattern_email,
                                "name": name,
                                "company": None,
                                "confidence": float(score),
                                "domain": normalized_domain,
                                "success": True,
                                "source": "pattern_generated",
                                "error": None,
                                "status": None,
                            }
                    except Exception as verify_err:
                        logger.debug(f"Email verification failed for {pattern_email}: {verify_err}")
                        continue
            except Exception as pattern_err:
                logger.debug(f"Email pattern generation failed for {normalized_domain}: {pattern_err}")
            
            # Mark for retry instead of returning None
            logger.warning(f"⚠️  [ENRICHMENT] No emails found for {normalized_domain} via any method, marking for retry")
            return {
                "email": None,
                "name": None,
                "company": None,
                "confidence": 0.0,
                "domain": normalized_domain,
                "success": False,
                "source": None,
                "error": "No emails found via Snov.io, local scraping, or pattern generation",
                "status": "pending_retry",
            }
        
        # Parse emails correctly - extract ONLY: value, type, confidence_score
        parsed_emails = []
        for email_data in emails:
            if not isinstance(email_data, dict):
                continue
            
            # Extract ONLY the required fields
            email_value = email_data.get("value")
            email_type = email_data.get("type")
            confidence = float(email_data.get("confidence_score", 0) or 0)
            
            if not email_value:
                continue
            
            parsed_emails.append({
                "value": email_value,
                "type": email_type,
                "confidence_score": confidence
            })
        
        if not parsed_emails:
            logger.warning(f"⚠️  [ENRICHMENT] No valid emails parsed from Snov.io response for {normalized_domain}, trying fallback methods")
            # Try local scraping as fallback before giving up
            try:
                local_email = await _scrape_email_from_domain(normalized_domain, page_url)
                if local_email:
                    logger.info(f"✅ [ENRICHMENT] Local scraping found email for {normalized_domain}: {local_email}")
                    return {
                        "email": local_email,
                        "name": None,
                        "company": None,
                        "confidence": 50.0,
                        "domain": normalized_domain,
                        "success": True,
                        "source": "local_scraping",
                        "error": None,
                        "status": None,
                    }
            except Exception as scrape_err:
                logger.debug(f"Local scraping fallback failed for {normalized_domain}: {scrape_err}")
            
            # Try pattern generation as last resort
            try:
                generated_patterns = _generate_email_patterns(normalized_domain, name)
                for pattern_email in generated_patterns[:3]:  # Limit to 3
                    try:
                        verify_result = await snov_client.email_verifier(pattern_email)
                        if verify_result.get("success") and verify_result.get("result") == "deliverable":
                            score = verify_result.get("score", 0)
                            logger.info(f"✅ [ENRICHMENT] Verified pattern email {pattern_email} (score: {score})")
                            return {
                                "email": pattern_email,
                                "name": name,
                                "company": None,
                                "confidence": float(score),
                                "domain": normalized_domain,
                                "success": True,
                                "source": "pattern_generated",
                                "error": None,
                                "status": None,
                            }
                    except Exception:
                        continue
            except Exception:
                pass
            
            # No email found anywhere - return structured response instead of None
            logger.warning(f"⚠️  [ENRICHMENT] No emails found for {normalized_domain} via any method")
            return {
                "email": None,
                "name": None,
                "company": None,
                "confidence": 0.0,
                "domain": normalized_domain,
                "success": False,
                "source": None,
                "error": "No valid email value in Snov.io response and all fallbacks failed",
                "status": "pending_retry",
            }
        
        # Get best email (highest confidence) from parsed emails
        best_email = None
        best_confidence = 0.0
        for email_data in parsed_emails:
            confidence = email_data.get("confidence_score", 0)
            if confidence > best_confidence:
                best_confidence = confidence
                best_email = email_data
        
        email_value = best_email["value"]
        email_type = best_email.get("type")
        full_name = name  # Use provided name if available
        company = None  # Not available from parsed email data
        
        # Optionally verify the email to increase confidence
        # Only verify if confidence is below 80 to avoid unnecessary API calls
        verified = False
        verification_score = 0
        if best_confidence < 80:
            try:
                verify_result = await snov_client.email_verifier(email_value)
                if verify_result.get("success") and verify_result.get("result") == "deliverable":
                    verified = True
                    verification_score = verify_result.get("score", 0)
                    logger.info(f"✅ [ENRICHMENT] Email {email_value} verified (score: {verification_score})")
            except Exception as verify_err:
                logger.debug(f"Email verification skipped for {email_value}: {verify_err}")
        
        total_time = (time.time() - start_time) * 1000
        
        result: Dict[str, Any] = {
            "email": email_value,
            "name": full_name,
            "company": company,
            "confidence": best_confidence,
            "email_type": email_type,
            "verified": verified,
            "verification_score": verification_score,
            "domain": normalized_domain,
            "success": True,
            "source": "snov_io",
            "error": None,
        }
        
        logger.info(f"✅ [ENRICHMENT] Enriched {normalized_domain} in {total_time:.0f}ms")
        logger.info(
            "📤 [ENRICHMENT] Output - email=%s, type=%s, name=%s, confidence=%.1f, verified=%s, source=%s",
            email_value,
            email_type,
            full_name,
            best_confidence,
            verified,
            "snov_io",
        )
        
        return result
        
    except Exception as e:
        total_time = (time.time() - start_time) * 1000
        error_msg = f"Enrichment failed for {domain} after {total_time:.0f}ms: {str(e)}"
        logger.error(f"❌ [ENRICHMENT] {error_msg}", exc_info=True)
        
        # Try local scraping as last resort before giving up
        try:
            logger.info(f"🔄 [ENRICHMENT] Attempting local scraping fallback after error for {normalized_domain}")
            local_email = await _scrape_email_from_domain(normalized_domain, page_url)
            if local_email:
                logger.info(f"✅ [ENRICHMENT] Local scraping found email for {normalized_domain} after error: {local_email}")
                return {
                    "email": local_email,
                    "name": None,
                    "company": None,
                    "confidence": 50.0,
                    "domain": normalized_domain,
                    "success": True,
                    "source": "local_scraping",
                    "error": None,
                    "status": None,
                }
        except Exception as scrape_err:
            logger.debug(f"Local scraping fallback also failed for {normalized_domain}: {scrape_err}")
        
        # Return structured error response instead of raising
        return {
            "email": None,
            "name": None,
            "company": None,
            "confidence": 0.0,
            "domain": normalized_domain or domain,
            "success": False,
            "source": None,
            "error": error_msg,
            "status": "pending_retry",
        }

