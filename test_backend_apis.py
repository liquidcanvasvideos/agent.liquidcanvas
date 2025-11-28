"""
Comprehensive test script to verify backend APIs and dependencies are working
"""
import os
import sys
import requests
from urllib.parse import urlparse

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_hunter_io():
    """Test Hunter.io API"""
    print("\n" + "="*60)
    print("TESTING HUNTER.IO API")
    print("="*60)
    
    try:
        from extractor.hunter_io_client import HunterIOClient
        from utils.config import settings
        
        api_key = getattr(settings, 'HUNTER_IO_API_KEY', None)
        if not api_key or not api_key.strip():
            print("[FAIL] Hunter.io API key not configured")
            return False
        
        client = HunterIOClient(api_key)
        if not client.is_configured():
            print("[FAIL] Hunter.io client not properly configured")
            return False
        
        # Test with a real domain
        test_domain = "liquidcanvas.art"
        print(f"Testing Hunter.io API with domain: {test_domain}")
        
        result = client.domain_search(test_domain)
        if result and result.get("emails"):
            emails = result["emails"]
            print(f"[PASS] Hunter.io API working! Found {len(emails)} email(s):")
            for email in emails[:5]:  # Show first 5
                print(f"   - {email.get('value', 'N/A')} (confidence: {email.get('confidence_score', 'N/A')})")
            return True
        else:
            print(f"[WARN] Hunter.io API responded but no emails found for {test_domain}")
            print(f"   Response: {result}")
            return True  # API is working, just no emails for this domain
    except Exception as e:
        print(f"[FAIL] Hunter.io API test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_dataforseo():
    """Test DataForSEO API"""
    print("\n" + "="*60)
    print("TESTING DATAFORSEO API")
    print("="*60)
    
    try:
        from extractor.dataforseo_client import DataForSEOClient
        from utils.config import settings
        
        login = getattr(settings, 'DATAFORSEO_LOGIN', None)
        password = getattr(settings, 'DATAFORSEO_PASSWORD', None)
        
        if not login or not password or not login.strip() or not password.strip():
            print("[FAIL] DataForSEO credentials not configured")
            return False
        
        client = DataForSEOClient(login, password)
        if not client.is_configured():
            print("[FAIL] DataForSEO client not properly configured")
            return False
        
        # Test with a real search query
        test_query = "home decor blog usa"
        print(f"Testing DataForSEO API with query: '{test_query}'")
        
        result = client.serp_google_organic(
            keyword=test_query,
            location_code=2840,  # USA
            depth=5
        )
        
        if result and result.get("success"):
            results = result.get("results", [])
            print(f"[PASS] DataForSEO API working! Found {len(results)} result(s):")
            for i, item in enumerate(results[:3], 1):  # Show first 3
                print(f"   {i}. {item.get('title', 'N/A')}")
                print(f"      URL: {item.get('url', 'N/A')}")
            return True
        else:
            error = result.get("error", "Unknown error") if result else "No response"
            print(f"[FAIL] DataForSEO API test failed: {error}")
            return False
    except Exception as e:
        print(f"[FAIL] DataForSEO API test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_contact_extraction():
    """Test contact extraction with APIs"""
    print("\n" + "="*60)
    print("TESTING CONTACT EXTRACTION (with APIs)")
    print("="*60)
    
    try:
        from db.database import SessionLocal
        from extractor.contact_extraction_service import ContactExtractionService
        from scraper.scraper_service import ScraperService
        
        db = SessionLocal()
        try:
            # Test with a real website
            test_url = "https://www.liquidcanvas.art"
            print(f"Testing contact extraction for: {test_url}")
            
            # First scrape the website
            scraper = ScraperService(db, apply_quality_filter=False)
            website = scraper.scrape_website(test_url, skip_quality_check=True)
            
            if not website:
                print("[FAIL] Failed to scrape website")
                return False
            
            print(f"[PASS] Website scraped successfully (ID: {website.id})")
            
            # Now extract contacts
            extraction_service = ContactExtractionService(db)
            result = extraction_service.extract_and_store_contacts(website.id)
            
            if result and "error" not in result:
                emails = result.get("emails_extracted", 0)
                phones = result.get("phones_extracted", 0)
                social = result.get("social_links_extracted", 0)
                
                print(f"[PASS] Contact extraction successful!")
                print(f"   - Emails: {emails}")
                print(f"   - Phones: {phones}")
                print(f"   - Social links: {social}")
                
                # Check if Hunter.io was used
                from db.models import Contact
                try:
                    hunter_contacts = db.query(Contact).filter(
                        Contact.website_id == website.id,
                        Contact.source == "hunter_io"
                    ).all()
                    
                    if hunter_contacts:
                        print(f"[PASS] Hunter.io was used! Found {len(hunter_contacts)} email(s) via Hunter.io:")
                        for contact in hunter_contacts:
                            print(f"   - {contact.email}")
                except Exception as db_error:
                    # Database might not have source column yet
                    print(f"[WARN] Could not check Hunter.io usage (database migration needed): {db_error}")
                
                return True
            else:
                error = result.get("error", "Unknown error") if result else "No result"
                print(f"[FAIL] Contact extraction failed: {error}")
                return False
        finally:
            db.close()
    except Exception as e:
        print(f"[FAIL] Contact extraction test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_website_discovery():
    """Test website discovery with DataForSEO"""
    print("\n" + "="*60)
    print("TESTING WEBSITE DISCOVERY (with DataForSEO)")
    print("="*60)
    
    try:
        from db.database import SessionLocal
        from jobs.website_discovery import WebsiteDiscovery
        
        db = SessionLocal()
        try:
            discovery = WebsiteDiscovery()
            
            # Test with a small discovery (no DB save, just search)
            print("Testing discovery with location: usa, category: home_decor")
            
            # Don't save to DB, just test the search
            from utils.location_search import Location, generate_location_queries
            queries = generate_location_queries(Location.usa, categories=["home_decor"], include_social=False)
            
            print(f"Generated {len(queries)} search queries")
            print(f"Sample queries: {[q[0] for q in queries[:3]]}")
            
            # Test DataForSEO search
            from extractor.dataforseo_client import DataForSEOClient
            from utils.config import settings
            
            login = getattr(settings, 'DATAFORSEO_LOGIN', None)
            password = getattr(settings, 'DATAFORSEO_PASSWORD', None)
            
            if login and password:
                client = DataForSEOClient(login, password)
                if client.is_configured():
                    test_query = queries[0][0] if queries else "home decor blog"
                    print(f"\nTesting DataForSEO search with: '{test_query}'")
                    
                    result = client.serp_google_organic(
                        keyword=test_query,
                        location_code=2840,
                        depth=5
                    )
                    
                    if result and result.get("success"):
                        results = result.get("results", [])
                        print(f"[PASS] DataForSEO discovery working! Found {len(results)} websites")
                        for i, item in enumerate(results[:3], 1):
                            print(f"   {i}. {item.get('title', 'N/A')}")
                            print(f"      {item.get('url', 'N/A')}")
                        return True
                    else:
                        print(f"[WARN] DataForSEO search returned no results")
                        return False
                else:
                    print("[WARN] DataForSEO not configured, skipping API test")
                    return True
            else:
                print("[WARN] DataForSEO credentials not found")
                return False
        finally:
            db.close()
    except Exception as e:
        print(f"[FAIL] Website discovery test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("BACKEND API & DEPENDENCY TEST SUITE")
    print("="*60)
    print("\nThis script will test:")
    print("1. Hunter.io API integration")
    print("2. DataForSEO API integration")
    print("3. Contact extraction with APIs")
    print("4. Website discovery with DataForSEO")
    
    results = {
        "Hunter.io": test_hunter_io(),
        "DataForSEO": test_dataforseo(),
        "Contact Extraction": test_contact_extraction(),
        "Website Discovery": test_website_discovery()
    }
    
    print("\n" + "="*60)
    print("TEST RESULTS SUMMARY")
    print("="*60)
    for test_name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{test_name}: {status}")
    
    all_passed = all(results.values())
    print("\n" + "="*60)
    if all_passed:
        print("[SUCCESS] ALL TESTS PASSED - Backend is working correctly!")
    else:
        print("[FAILURE] SOME TESTS FAILED - Check the errors above")
    print("="*60)
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

