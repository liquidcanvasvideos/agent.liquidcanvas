"""
Contact extraction service that coordinates all extractors and saves to database
"""
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from db.models import Contact, ContactForm, ScrapedWebsite
from extractor.email_extractor import EmailExtractor
from extractor.enhanced_email_extractor import EnhancedEmailExtractor
from extractor.hunter_io_client import HunterIOClient
from extractor.phone_extractor import PhoneExtractor
from extractor.social_extractor import SocialExtractor
from extractor.contact_form_extractor import ContactFormExtractor
from extractor.contact_page_crawler import ContactPageCrawler
from utils.activity_logger import ActivityLogger
import logging

logger = logging.getLogger(__name__)


class ContactExtractionService:
    """Service for extracting contacts and saving to database"""
    
    def __init__(self, db: Session):
        """
        Initialize contact extraction service
        
        Args:
            db: Database session
        """
        self.db = db
        
        # Initialize Hunter.io client if API key is configured
        hunter_client = None
        try:
            from utils.config import settings
            if hasattr(settings, 'HUNTER_IO_API_KEY') and settings.HUNTER_IO_API_KEY:
                hunter_client = HunterIOClient(settings.HUNTER_IO_API_KEY)
                logger.info("Hunter.io client initialized")
        except Exception as e:
            logger.warning(f"Could not initialize Hunter.io client: {e}")
        
        # Use enhanced email extractor (falls back to basic if Hunter.io not available)
        self.email_extractor = EmailExtractor()  # Keep for backward compatibility
        self.enhanced_email_extractor = EnhancedEmailExtractor(hunter_io_client=hunter_client)
        
        self.phone_extractor = PhoneExtractor()
        self.social_extractor = SocialExtractor()
        self.form_extractor = ContactFormExtractor()
        self.contact_crawler = ContactPageCrawler()
        self.activity_logger = ActivityLogger(db)
    
    def extract_and_save(self, website_id: int, html_content: str, base_url: str) -> Dict:
        """
        Extract all contact information and save to database
        
        Args:
            website_id: ID of the scraped website
            html_content: HTML content to extract from
            base_url: Base URL for resolving relative links
            
        Returns:
            Dictionary with extraction results
        """
        try:
            website = self.db.query(ScrapedWebsite).filter(
                ScrapedWebsite.id == website_id
            ).first()
            
            if not website:
                logger.error(f"Website {website_id} not found")
                return {"error": "Website not found"}
            
            results = {
                "emails_extracted": 0,
                "phones_extracted": 0,
                "social_links_extracted": 0,
                "contact_forms_extracted": 0,
                "contact_pages_found": 0
            }
            
            # Extract from main page
            self._extract_from_page(website_id, html_content, base_url, results)
            
            # Crawl and extract from contact pages
            contact_pages = self.contact_crawler.detect_contact_page(base_url)
            results["contact_pages_found"] = len(contact_pages)
            
            for contact_url, contact_html in self.contact_crawler.crawl_contact_pages(base_url):
                self._extract_from_page(website_id, contact_html, contact_url, results)
            
            self.db.commit()
            logger.info(f"Extracted contacts for website {website_id}: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Error extracting contacts for website {website_id}: {str(e)}")
            self.db.rollback()
            return {"error": str(e)}
    
    def _extract_from_page(
        self,
        website_id: int,
        html_content: str,
        page_url: str,
        results: Dict
    ):
        """Extract contacts from a single page using enhanced extraction"""
        # Use enhanced email extractor (includes footer, header, forms, Hunter.io)
        try:
            # Try to get Playwright context if available (for JS-rendered emails)
            playwright_context = None
            try:
                from scraper.website_scraper import WebsiteScraper
                scraper = WebsiteScraper()
                if hasattr(scraper, 'playwright_context') and scraper.playwright_context:
                    playwright_context = scraper.playwright_context
            except:
                pass
            
            # Use enhanced extractor
            email_results = self.enhanced_email_extractor.extract_all_emails(
                html_content=html_content,
                base_url=page_url,
                use_hunter_io=True,
                use_playwright=(playwright_context is not None),
                playwright_context=playwright_context
            )
            
            # Extract emails from enhanced results
            emails = [email_data["email"] for email_data in email_results.get("emails", [])]
            
            # Log sources for debugging
            if email_results.get("sources"):
                logger.info(f"Email extraction sources for {page_url}: {email_results['sources']}")
        except Exception as e:
            logger.warning(f"Enhanced email extraction failed, falling back to basic: {e}")
            # Fallback to basic extraction
            emails = self.email_extractor.extract_from_html(html_content)
        
        for email in emails:
            existing = self.db.query(Contact).filter(
                Contact.website_id == website_id,
                Contact.email == email
            ).first()
            if not existing:
                contact = Contact(
                    website_id=website_id,
                    email=email,
                    contact_page_url=page_url
                )
                self.db.add(contact)
                results["emails_extracted"] += 1
        
        # Extract phone numbers
        phones = self.phone_extractor.extract_from_html(html_content)
        for phone in phones:
            existing = self.db.query(Contact).filter(
                Contact.website_id == website_id,
                Contact.phone_number == phone
            ).first()
            if not existing:
                contact = Contact(
                    website_id=website_id,
                    phone_number=phone,
                    contact_page_url=page_url
                )
                self.db.add(contact)
                results["phones_extracted"] += 1
        
        # Extract social links
        social_links = self.social_extractor.extract_from_html(html_content)
        for platform, urls in social_links.items():
            for url in urls:
                existing = self.db.query(Contact).filter(
                    Contact.website_id == website_id,
                    Contact.social_platform == platform,
                    Contact.social_url == url
                ).first()
                if not existing:
                    contact = Contact(
                        website_id=website_id,
                        social_platform=platform,
                        social_url=url,
                        contact_page_url=page_url
                    )
                    self.db.add(contact)
                    results["social_links_extracted"] += 1
        
        # Extract contact forms
        forms = self.form_extractor.extract_contact_forms(html_content, page_url)
        for form in forms:
            existing = self.db.query(ContactForm).filter(
                ContactForm.website_id == website_id,
                ContactForm.form_url == page_url,
                ContactForm.form_action == form.get("action", "")
            ).first()
            if not existing:
                contact_form = ContactForm(
                    website_id=website_id,
                    form_url=page_url,
                    form_action=form.get("action", ""),
                    form_method=form.get("method", "post"),
                    form_fields=form.get("fields", []),
                    is_contact_form=form.get("is_contact_form", True),
                    metadata=form
                )
                self.db.add(contact_form)
                results["contact_forms_extracted"] += 1
    
    def extract_emails(self, html_content: str) -> List[str]:
        """Extract emails from HTML"""
        return self.email_extractor.extract_from_html(html_content)
    
    def extract_social_links(self, html_content: str) -> Dict[str, List[str]]:
        """Extract social links from HTML"""
        return self.social_extractor.extract_from_html(html_content)
    
    def detect_contact_page(self, base_url: str) -> List[str]:
        """Detect contact pages"""
        return self.contact_crawler.detect_contact_page(base_url)
    
    def extract_and_store_contacts(self, website_id: int) -> Dict:
        """
        Extract contacts from a website using stored HTML
        
        Args:
            website_id: ID of the scraped website
            
        Returns:
            Dictionary with extraction results
        """
        try:
            website = self.db.query(ScrapedWebsite).filter(
                ScrapedWebsite.id == website_id
            ).first()
            
            if not website:
                logger.error(f"Website {website_id} not found")
                return {"error": "Website not found"}
            
            # If no HTML stored, re-scrape the website
            if not website.raw_html:
                logger.warning(f"No HTML content for website {website_id}, re-scraping...")
                from scraper.scraper_service import ScraperService
                scraper_service = ScraperService(self.db, apply_quality_filter=False)
                updated_website = scraper_service.scrape_website(website.url, skip_quality_check=True)
                if updated_website and updated_website.raw_html:
                    website = updated_website
                    self.db.refresh(website)
                else:
                    logger.error(f"Failed to re-scrape website {website_id}")
                    return {"error": "No HTML content available and re-scraping failed"}
            
            # Log extraction start
            self.activity_logger.log_extraction_start(website_id, website.url)
            
            results = {
                "emails_extracted": 0,
                "phones_extracted": 0,
                "social_links_extracted": 0,
                "contact_forms_extracted": 0,
                "contact_pages_found": 0
            }
            
            # Extract from main page using enhanced extraction
            self.activity_logger.log_extraction_progress(website_id, "Extracting from main page")
            logger.info(f"Extracting contacts from main page: {website.url}")
            self._extract_from_page(website_id, website.raw_html, website.url, results)
            
            # Crawl and extract from contact pages (expanded list)
            try:
                self.activity_logger.log_extraction_progress(website_id, "Crawling contact pages")
                logger.info(f"Discovering contact pages for: {website.url}")
                contact_pages = self.contact_crawler.detect_contact_page(website.url)
                results["contact_pages_found"] = len(contact_pages)
                logger.info(f"Found {len(contact_pages)} contact pages")
                
                if contact_pages:
                    self.activity_logger.log_extraction_progress(
                        website_id,
                        f"Found {len(contact_pages)} contact pages",
                        len(contact_pages)
                    )
                
                for contact_url, contact_html in self.contact_crawler.crawl_contact_pages(website.url):
                    logger.info(f"Extracting from contact page: {contact_url}")
                    self._extract_from_page(website_id, contact_html, contact_url, results)
            except Exception as e:
                logger.warning(f"Failed to crawl contact pages: {e}")
            
            self.db.commit()
            logger.info(f"Extracted contacts for website {website_id}: {results}")
            
            # Log extraction success
            self.activity_logger.log_extraction_success(
                website_id,
                results["emails_extracted"],
                results["phones_extracted"],
                results["social_links_extracted"]
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Error extracting contacts for website {website_id}: {str(e)}")
            self.db.rollback()
            return {"error": str(e)}

