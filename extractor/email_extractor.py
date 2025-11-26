"""
Email extraction from web pages
"""
import re
from typing import List, Set
from bs4 import BeautifulSoup


class EmailExtractor:
    """Extract email addresses from web content"""
    
    # Email regex pattern
    EMAIL_PATTERN = re.compile(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    )
    
    def extract_from_html(self, html_content: str) -> List[str]:
        """
        Extract emails from HTML content using regex + BeautifulSoup
        
        Args:
            html_content: HTML string
            
        Returns:
            List of unique email addresses
        """
        emails: Set[str] = set()
        
        soup = BeautifulSoup(html_content, "lxml")
        
        # Extract from text content
        text_content = soup.get_text()
        found_emails = self.EMAIL_PATTERN.findall(text_content)
        emails.update(found_emails)
        
        # Extract from mailto links
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            if href.startswith("mailto:"):
                email = href.replace("mailto:", "").split("?")[0].strip()
                if self._is_valid_email(email):
                    emails.add(email)
        
        # Extract from data attributes
        for tag in soup.find_all(attrs={"data-email": True}):
            email = tag.get("data-email", "").strip()
            if self._is_valid_email(email):
                emails.add(email)
        
        # Extract from meta tags
        for meta in soup.find_all("meta"):
            content = meta.get("content", "")
            if "@" in content:
                found = self.EMAIL_PATTERN.findall(content)
                emails.update(found)
        
        # Extract from script tags (some sites embed emails in JS)
        for script in soup.find_all("script"):
            if script.string:
                found = self.EMAIL_PATTERN.findall(script.string)
                emails.update(found)
        
        # Filter out common false positives
        filtered_emails = [e.lower().strip() for e in emails if self._is_valid_email(e)]
        
        return list(set(filtered_emails))
    
    def extract_from_text(self, text: str) -> List[str]:
        """
        Extract emails from plain text
        
        Args:
            text: Plain text string
            
        Returns:
            List of unique email addresses
        """
        emails = self.EMAIL_PATTERN.findall(text)
        filtered_emails = [e for e in emails if self._is_valid_email(e)]
        return list(set(filtered_emails))
    
    def _is_valid_email(self, email: str) -> bool:
        """Validate email address and filter out common false positives"""
        if not email or len(email) < 5:
            return False
        
        email_lower = email.lower().strip()
        
        # Filter out common false positives
        false_positives = [
            "example.com",
            "email.com",
            "domain.com",
            "your-email.com",
            "xxx@xxx",
            "test@test"
        ]
        
        for fp in false_positives:
            if fp in email_lower:
                return False
        
        # Filter out image file extensions and other file types
        # Common image formats that might be mistaken for emails (e.g., hero@2x.jpg)
        image_extensions = [
            '.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp', '.bmp', '.ico',
            '.tiff', '.tif', '.heic', '.heif', '.avif', '.apng'
        ]
        
        # Other file extensions that might be mistaken for emails
        other_file_extensions = [
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.zip', '.rar', '.tar', '.gz',
            '.mp4', '.mp3', '.avi', '.mov', '.wmv', '.flv', '.webm',
            '.css', '.js', '.json', '.xml', '.html', '.htm'
        ]
        
        # Check if email ends with a file extension
        for ext in image_extensions + other_file_extensions:
            if email_lower.endswith(ext):
                return False
        
        # Split email into local and domain parts
        if '@' not in email_lower:
            return False
        
        parts = email_lower.split('@')
        if len(parts) != 2:
            return False
        
        local_part, domain_part = parts
        
        # Validate local part (before @)
        if not local_part or len(local_part) < 1:
            return False
        
        # Validate domain part (after @)
        if not domain_part or len(domain_part) < 4:  # At least "x.co"
            return False
        
        # Domain should have a dot (TLD separator)
        if '.' not in domain_part:
            return False
        
        # Split domain into name and TLD
        domain_parts = domain_part.split('.')
        if len(domain_parts) < 2:
            return False
        
        tld = domain_parts[-1].lower()
        
        # Filter out common false positive TLDs that are actually file extensions
        invalid_tlds = [
            'jpg', 'jpeg', 'png', 'gif', 'svg', 'webp', 'bmp', 'ico',
            'pdf', 'doc', 'docx', 'xls', 'xlsx', 'zip', 'rar', 'tar', 'gz',
            'mp4', 'mp3', 'avi', 'mov', 'wmv', 'flv', 'webm',
            'css', 'js', 'json', 'xml', 'html', 'htm'
        ]
        
        if tld in invalid_tlds:
            return False
        
        # TLD should be at least 2 characters (like .com, .org, etc.)
        if len(tld) < 2:
            return False
        
        # Domain name (before TLD) should not be just numbers (e.g., "2x" in "hero@2x.jpg")
        domain_name = '.'.join(domain_parts[:-1])
        if domain_name.isdigit() or len(domain_name) < 2:
            # Allow single character domains only if they're common (like "x.co")
            if domain_name not in ['x', 'i', 'a']:
                return False
        
        return True

