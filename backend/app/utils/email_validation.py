"""
Email validation utilities for filtering out garbage emails
"""
import re
from typing import List


# RFC 5322 compliant email regex (simplified but strict)
EMAIL_REGEX = re.compile(
    r"(?:[a-zA-Z0-9!#$%&'*+/=?^_`{|}~-]+"
    r"(?:\.[a-zA-Z0-9!#$%&'*+/=?^_`{|}~-]+)*"
    r"@"
    r"(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+"
    r"[a-zA-Z]{2,63})"
)


def is_plausible_email(email: str) -> bool:
    """
    Check if an email address is plausible and not garbage.
    
    Filters out:
    - File paths (.css, .jpg, .js, etc.)
    - CSS selectors and class names
    - Very short or malformed addresses
    - Invalid TLDs
    
    Args:
        email: Email string to validate
    
    Returns:
        True if email is plausible, False otherwise
    """
    if not email or not isinstance(email, str):
        return False
    
    email = email.strip()
    
    # Length check (RFC 5322 max is 320, but we'll be stricter)
    if len(email) > 255 or len(email) < 5:  # min: a@b.c
        return False
    
    lowered = email.lower()
    
    # Hard reject obvious asset/file paths
    file_extensions = [
        ".css", ".js", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
        ".pdf", ".zip", ".tar", ".gz", ".mp4", ".mp3", ".avi", ".mov",
        ".woff", ".woff2", ".ttf", ".eot", ".ico", ".xml", ".json"
    ]
    if any(ext in lowered for ext in file_extensions):
        return False
    
    # Reject CSS selectors and class patterns
    if any(pattern in lowered for pattern in [
        ".maplibregl-", ".ctrl-", "@media", "@import", "@keyframes",
        "acceler@ed-", "backwards-compat", "white-chocol@e"
    ]):
        return False
    
    # Must contain @
    if "@" not in email:
        return False
    
    # Split into local and domain parts
    parts = email.split("@", 1)
    if len(parts) != 2:
        return False
    
    local, domain = parts[0].strip(), parts[1].strip()
    
    # Validate local part
    if not local or len(local) < 1:
        return False
    
    # Local part should not be too long (RFC 5322: max 64 chars)
    if len(local) > 64:
        return False
    
    # Local part should not contain consecutive dots
    if ".." in local:
        return False
    
    # Local part should not start or end with dot
    if local.startswith(".") or local.endswith("."):
        return False
    
    # Validate domain part
    if not domain or "." not in domain:
        return False
    
    # Domain should not be too long (RFC 5322: max 255 chars)
    if len(domain) > 255:
        return False
    
    # Domain should not contain consecutive dots
    if ".." in domain:
        return False
    
    # Domain should not start or end with dot or hyphen
    if domain.startswith(".") or domain.endswith(".") or domain.startswith("-") or domain.endswith("-"):
        return False
    
    # Extract TLD (top-level domain)
    tld = domain.rsplit(".", 1)[-1]
    if not tld or not (2 <= len(tld) <= 24):
        return False
    
    # TLD should be alphabetic only
    if not tld.isalpha():
        return False
    
    # Reject common false positives
    false_positives = [
        "example.com", "test.com", "localhost", "domain.com",
        "company.com", "email.com", "your.email", "noreply",
        "no-reply", "donotreply"
    ]
    if domain.lower() in false_positives:
        return False
    
    # Reject if local part looks like a file path segment
    if any(char in local for char in ["/", "\\", ":", "*", "?", '"', "<", ">", "|"]):
        return False
    
    # Reject if domain contains invalid characters
    if not re.match(r'^[a-zA-Z0-9.-]+$', domain):
        return False
    
    return True


def extract_emails_from_text(text: str) -> List[str]:
    """
    Extract plausible email addresses from text.
    
    Args:
        text: Text content to search for emails
    
    Returns:
        List of valid, plausible email addresses (deduplicated)
    """
    if not text:
        return []
    
    # Find all potential email matches
    raw_matches = set(EMAIL_REGEX.findall(text))
    
    # Filter to only plausible emails
    plausible_emails = []
    for email in raw_matches:
        if is_plausible_email(email):
            plausible_emails.append(email.lower())
    
    # Remove duplicates while preserving order
    seen = set()
    unique_emails = []
    for email in plausible_emails:
        if email not in seen:
            seen.add(email)
            unique_emails.append(email)
    
    return unique_emails


def format_job_error(e: Exception) -> str:
    """
    Format exception into a short, user-friendly error message for job.error_message.
    
    Args:
        e: Exception to format
    
    Returns:
        Short error message string
    """
    if isinstance(e, SyntaxError):
        return "Internal code syntax error in enrichment task."
    if isinstance(e, ImportError):
        return "Module import failed. Please contact support."
    if isinstance(e, TimeoutError):
        return "Job timed out while running."
    if isinstance(e, ValueError):
        return f"Invalid input: {str(e)[:50]}"
    
    # For other exceptions, use class name and first 50 chars of message
    error_msg = str(e)
    if len(error_msg) > 50:
        error_msg = error_msg[:50] + "..."
    
    return f"{e.__class__.__name__}: {error_msg}"

