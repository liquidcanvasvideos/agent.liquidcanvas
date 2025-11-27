"""
Enhanced email extraction with multiple techniques (like Hunter.io)
"""
import re
from typing import List, Set, Dict, Optional
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import logging

logger = logging.getLogger(__name__)


class EnhancedEmailExtractor:
    """
    Enhanced email extractor using multiple techniques:
    1. Standard HTML parsing
    2. Footer/Header extraction
    3. Contact page discovery
    4. JavaScript rendering (via Playwright)
    5. Hunter.io API integration
    """
    
    # Email regex pattern (improved)
    EMAIL_PATTERN = re.compile(
        r'\b[A-Za-z0-9](?:[A-Za-z0-9._%+-]*[A-Za-z0-9])?@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Z|a-z]{2,}\b'
    )
    
    # Common email patterns in text
    EMAIL_PATTERNS = [
        re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
        re.compile(r'[A-Za-z0-9._%+-]+\s*\[?at\]?\s*[A-Za-z0-9.-]+\s*\[?dot\]?\s*[A-Z|a-z]{2,}', re.IGNORECASE),
        re.compile(r'[A-Za-z0-9._%+-]+\s*\(at\)\s*[A-Za-z0-9.-]+\s*\(dot\)\s*[A-Z|a-z]{2,}', re.IGNORECASE),
    ]
    
    def __init__(self, hunter_io_client=None):
        """
        Initialize enhanced email extractor
        
        Args:
            hunter_io_client: Optional HunterIOClient instance
        """
        self.hunter_io_client = hunter_io_client
    
    def extract_all_emails(
        self,
        html_content: str,
        base_url: str,
        use_hunter_io: bool = True,
        use_playwright: bool = False,
        playwright_context = None
    ) -> Dict[str, any]:
        """
        Extract emails using all available techniques
        
        Args:
            html_content: HTML content
            base_url: Base URL of the page
            use_hunter_io: Whether to use Hunter.io API
            use_playwright: Whether to use Playwright for JS rendering
            playwright_context: Playwright browser context (if available)
            
        Returns:
            Dictionary with emails and metadata
        """
        all_emails: Set[str] = set()
        sources = {}  # Track where each email was found
        
        # 1. Extract from main HTML
        main_emails = self.extract_from_html(html_content)
        for email in main_emails:
            all_emails.add(email.lower())
            sources[email.lower()] = sources.get(email.lower(), []) + ["main_page"]
        
        # 2. Extract from footer
        footer_emails = self.extract_from_footer(html_content)
        for email in footer_emails:
            all_emails.add(email.lower())
            sources[email.lower()] = sources.get(email.lower(), []) + ["footer"]
        
        # 3. Extract from header
        header_emails = self.extract_from_header(html_content)
        for email in header_emails:
            all_emails.add(email.lower())
            sources[email.lower()] = sources.get(email.lower(), []) + ["header"]
        
        # 4. Extract from contact forms
        form_emails = self.extract_from_forms(html_content)
        for email in form_emails:
            all_emails.add(email.lower())
            sources[email.lower()] = sources.get(email.lower(), []) + ["contact_form"]
        
        # 5. Extract from JavaScript (if Playwright available)
        if use_playwright and playwright_context:
            js_emails = self.extract_from_javascript(base_url, playwright_context)
            for email in js_emails:
                all_emails.add(email.lower())
                sources[email.lower()] = sources.get(email.lower(), []) + ["javascript"]
        
        # 6. Use Hunter.io API (if configured) - REAL-TIME email finding
        if use_hunter_io and self.hunter_io_client and self.hunter_io_client.is_configured():
            domain = urlparse(base_url).netloc.replace('www.', '')
            logger.info(f"🔍 Calling Hunter.io API in REAL-TIME for domain: {domain}")
            hunter_emails = self.extract_from_hunter_io(domain)
            if hunter_emails:
                logger.info(f"✅ Hunter.io API returned {len(hunter_emails)} email(s) for {domain}")
            for email in hunter_emails:
                all_emails.add(email.lower())
                sources[email.lower()] = sources.get(email.lower(), []) + ["hunter_io"]
        
        # Filter and validate
        valid_emails = []
        for email in all_emails:
            if self._is_valid_email(email):
                valid_emails.append({
                    "email": email,
                    "sources": list(set(sources.get(email, [])))
                })
        
        return {
            "emails": valid_emails,
            "total": len(valid_emails),
            "sources": sources
        }
    
    def extract_from_html(self, html_content: str) -> List[str]:
        """Extract emails from HTML using standard methods"""
        emails: Set[str] = set()
        
        soup = BeautifulSoup(html_content, "lxml")
        
        # Extract from text content
        text_content = soup.get_text()
        for pattern in self.EMAIL_PATTERNS:
            found = pattern.findall(text_content)
            emails.update(found)
        
        # Extract from mailto links
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            if href.startswith("mailto:"):
                email = href.replace("mailto:", "").split("?")[0].split("&")[0].strip()
                if email:
                    emails.add(email)
        
        # Extract from data attributes
        for tag in soup.find_all(attrs={"data-email": True}):
            email = tag.get("data-email", "").strip()
            if email:
                emails.add(email)
        
        # Extract from meta tags
        for meta in soup.find_all("meta"):
            content = meta.get("content", "")
            if "@" in content:
                for pattern in self.EMAIL_PATTERNS:
                    found = pattern.findall(content)
                    emails.update(found)
        
        # Extract from script tags
        for script in soup.find_all("script"):
            if script.string:
                for pattern in self.EMAIL_PATTERNS:
                    found = pattern.findall(script.string)
                    emails.update(found)
        
        return list(emails)
    
    def extract_from_footer(self, html_content: str) -> List[str]:
        """Extract emails specifically from footer sections"""
        emails: Set[str] = set()
        soup = BeautifulSoup(html_content, "lxml")
        
        # Find footer elements
        footer_selectors = [
            "footer",
            "[class*='footer']",
            "[id*='footer']",
            "[class*='Footer']",
            "[id*='Footer']",
        ]
        
        for selector in footer_selectors:
            for footer in soup.select(selector):
                text = footer.get_text()
                for pattern in self.EMAIL_PATTERNS:
                    found = pattern.findall(text)
                    emails.update(found)
                
                # Check mailto links in footer
                for link in footer.find_all("a", href=True):
                    href = link.get("href", "")
                    if href.startswith("mailto:"):
                        email = href.replace("mailto:", "").split("?")[0].strip()
                        if email:
                            emails.add(email)
        
        return list(emails)
    
    def extract_from_header(self, html_content: str) -> List[str]:
        """Extract emails from header/navigation sections"""
        emails: Set[str] = set()
        soup = BeautifulSoup(html_content, "lxml")
        
        # Find header elements
        header_selectors = [
            "header",
            "[class*='header']",
            "[id*='header']",
            "[class*='Header']",
            "[id*='Header']",
            "nav",
            "[class*='nav']",
            "[class*='Nav']",
        ]
        
        for selector in header_selectors:
            for header in soup.select(selector):
                text = header.get_text()
                for pattern in self.EMAIL_PATTERNS:
                    found = pattern.findall(text)
                    emails.update(found)
                
                # Check mailto links
                for link in header.find_all("a", href=True):
                    href = link.get("href", "")
                    if href.startswith("mailto:"):
                        email = href.replace("mailto:", "").split("?")[0].strip()
                        if email:
                            emails.add(email)
        
        return list(emails)
    
    def extract_from_forms(self, html_content: str) -> List[str]:
        """Extract emails from contact forms"""
        emails: Set[str] = set()
        soup = BeautifulSoup(html_content, "lxml")
        
        # Find all forms
        for form in soup.find_all("form"):
            # Check form action URLs
            action = form.get("action", "")
            if action:
                for pattern in self.EMAIL_PATTERNS:
                    found = pattern.findall(action)
                    emails.update(found)
            
            # Check form data attributes
            for tag in form.find_all(attrs={"data-email": True}):
                email = tag.get("data-email", "").strip()
                if email:
                    emails.add(email)
            
            # Check input fields with email type
            for input_field in form.find_all("input", type="email"):
                value = input_field.get("value", "")
                if value:
                    emails.add(value)
                placeholder = input_field.get("placeholder", "")
                if placeholder and "@" in placeholder:
                    for pattern in self.EMAIL_PATTERNS:
                        found = pattern.findall(placeholder)
                        emails.update(found)
        
        return list(emails)
    
    def extract_from_javascript(self, url: str, playwright_context) -> List[str]:
        """Extract emails from JavaScript-rendered content using Playwright"""
        emails: Set[str] = set()
        
        try:
            page = playwright_context.new_page()
            page.goto(url, wait_until="networkidle", timeout=30000)
            
            # Get rendered HTML
            html = page.content()
            
            # Extract emails from rendered content
            for pattern in self.EMAIL_PATTERNS:
                found = pattern.findall(html)
                emails.update(found)
            
            # Check for mailto links
            mailto_links = page.query_selector_all('a[href^="mailto:"]')
            for link in mailto_links:
                href = link.get_attribute("href")
                if href:
                    email = href.replace("mailto:", "").split("?")[0].strip()
                    if email:
                        emails.add(email)
            
            page.close()
        except Exception as e:
            logger.warning(f"Error extracting emails with Playwright from {url}: {str(e)}")
        
        return list(emails)
    
    def extract_from_hunter_io(self, domain: str) -> List[str]:
        """Extract emails using Hunter.io API"""
        if not self.hunter_io_client or not self.hunter_io_client.is_configured():
            return []
        
        try:
            result = self.hunter_io_client.domain_search(domain, limit=50)
            if result.get("success") and result.get("emails"):
                return [email_data["email"] for email_data in result["emails"]]
        except Exception as e:
            logger.warning(f"Error using Hunter.io for {domain}: {str(e)}")
        
        return []
    
    def _is_valid_email(self, email: str) -> bool:
        """Validate email address and filter out false positives"""
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
            "test@test",
            "noreply@",
            "no-reply@",
        ]
        
        for fp in false_positives:
            if fp in email_lower:
                return False
        
        # Filter out image file extensions and other file types
        image_extensions = [
            '.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp', '.bmp', '.ico',
            '.tiff', '.tif', '.heic', '.heif', '.avif', '.apng'
        ]
        
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
        
        # Validate local part
        if not local_part or len(local_part) < 1:
            return False
        
        # Validate domain part
        if not domain_part or len(domain_part) < 4:
            return False
        
        # Domain should have a dot
        if '.' not in domain_part:
            return False
        
        # Split domain into name and TLD
        domain_parts = domain_part.split('.')
        if len(domain_parts) < 2:
            return False
        
        tld = domain_parts[-1].lower()
        
        # Filter out file extension TLDs
        invalid_tlds = [
            'jpg', 'jpeg', 'png', 'gif', 'svg', 'webp', 'bmp', 'ico',
            'pdf', 'doc', 'docx', 'xls', 'xlsx', 'zip', 'rar', 'tar', 'gz',
            'mp4', 'mp3', 'avi', 'mov', 'wmv', 'flv', 'webm',
            'css', 'js', 'json', 'xml', 'html', 'htm'
        ]
        
        if tld in invalid_tlds:
            return False
        
        # TLD should be at least 2 characters
        if len(tld) < 2:
            return False
        
        # Domain name should not be just numbers
        domain_name = '.'.join(domain_parts[:-1])
        if domain_name.isdigit() or len(domain_name) < 2:
            if domain_name not in ['x', 'i', 'a']:
                return False
        
        return True

