"""
Domain normalization utilities
"""
import re
from urllib.parse import urlparse
from typing import Optional


def normalize_domain(url_or_domain: str) -> Optional[str]:
    """
    Normalize any URL or domain into a clean domain string.
    
    Examples:
        https://example.com/index.html → example.com
        http://www.example.com/path?query=1 → example.com
        example.com → example.com
        www.example.com → example.com
    
    Args:
        url_or_domain: URL or domain string
    
    Returns:
        Clean domain string or None if invalid
    """
    if not url_or_domain or not isinstance(url_or_domain, str):
        return None
    
    url_or_domain = url_or_domain.strip()
    if not url_or_domain:
        return None
    
    # If it already looks like a domain (no protocol), try to parse it
    if not url_or_domain.startswith(('http://', 'https://')):
        # Add protocol temporarily for parsing
        url_or_domain = f"https://{url_or_domain}"
    
    try:
        parsed = urlparse(url_or_domain)
        domain = parsed.netloc or parsed.path.split('/')[0]
        
        if not domain:
            return None
        
        # Remove www. prefix
        domain = domain.lower().replace('www.', '')
        
        # Remove port if present
        if ':' in domain:
            domain = domain.split(':')[0]
        
        # Validate domain format (must have at least one dot)
        if '.' not in domain:
            return None
        
        # Basic validation: must have valid TLD
        parts = domain.split('.')
        if len(parts) < 2:
            return None
        
        # Check TLD is at least 2 characters
        tld = parts[-1]
        if len(tld) < 2:
            return None
        
        return domain
    
    except Exception:
        return None


def validate_domain(domain: str) -> bool:
    """
    Validate that a domain string is properly formatted.
    
    Args:
        domain: Domain string to validate
    
    Returns:
        True if valid, False otherwise
    """
    if not domain or not isinstance(domain, str):
        return False
    
    domain = domain.strip().lower()
    
    # Must have at least one dot
    if '.' not in domain:
        return False
    
    # Must not contain protocol
    if domain.startswith(('http://', 'https://')):
        return False
    
    # Must not contain path
    if '/' in domain:
        return False
    
    # Must not contain query params
    if '?' in domain or '&' in domain:
        return False
    
    # Basic regex validation
    domain_pattern = re.compile(
        r'^([a-z0-9]([a-z0-9\-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$'
    )
    
    return bool(domain_pattern.match(domain))

