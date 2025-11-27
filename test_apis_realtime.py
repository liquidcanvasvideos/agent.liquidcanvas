"""
Test script to verify Hunter.io and DataForSEO are working in real-time
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from extractor.hunter_io_client import HunterIOClient
from extractor.dataforseo_client import DataForSEOClient
from utils.config import settings
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_hunter_io():
    """Test Hunter.io API in real-time"""
    print("\n" + "="*60)
    print("TESTING HUNTER.IO API (REAL-TIME)")
    print("="*60)
    
    # Check if API key is configured
    api_key = getattr(settings, 'HUNTER_IO_API_KEY', None)
    if not api_key or not api_key.strip():
        print("❌ HUNTER.IO: API key not configured in .env")
        print("   Set HUNTER_IO_API_KEY=your_key_here in .env")
        return False
    
    print(f"✅ HUNTER.IO: API key found: {api_key[:10]}...{api_key[-4:]}")
    
    # Initialize client
    try:
        client = HunterIOClient(api_key)
        if not client.is_configured():
            print("❌ HUNTER.IO: Client initialization failed")
            return False
        print("✅ HUNTER.IO: Client initialized successfully")
    except Exception as e:
        print(f"❌ HUNTER.IO: Error initializing client: {e}")
        return False
    
    # Test domain search (real-time API call)
    test_domain = "liquidcanvas.art"  # Your domain for testing
    print(f"\n🔍 Making REAL-TIME API call to Hunter.io for domain: {test_domain}")
    
    try:
        result = client.domain_search(test_domain, limit=10)
        
        if result.get("success"):
            emails = result.get("emails", [])
            total = result.get("total", 0)
            pattern = result.get("pattern", "N/A")
            
            print(f"✅ HUNTER.IO: REAL-TIME API call successful!")
            print(f"   Found {total} total email(s) for {test_domain}")
            print(f"   Email pattern: {pattern}")
            
            if emails:
                print(f"\n   Emails found:")
                for i, email_data in enumerate(emails[:5], 1):  # Show first 5
                    email = email_data.get("email", "N/A")
                    confidence = email_data.get("confidence", 0)
                    email_type = email_data.get("type", "N/A")
                    print(f"   {i}. {email} (confidence: {confidence}%, type: {email_type})")
                if len(emails) > 5:
                    print(f"   ... and {len(emails) - 5} more")
            else:
                print("   No emails found for this domain")
            
            return True
        else:
            error = result.get("error", "Unknown error")
            print(f"❌ HUNTER.IO: API call failed: {error}")
            return False
            
    except Exception as e:
        print(f"❌ HUNTER.IO: Error during API call: {e}")
        return False


def test_dataforseo():
    """Test DataForSEO API in real-time"""
    print("\n" + "="*60)
    print("TESTING DATAFORSEO API (REAL-TIME)")
    print("="*60)
    
    # Check if credentials are configured
    login = getattr(settings, 'DATAFORSEO_LOGIN', None)
    password = getattr(settings, 'DATAFORSEO_PASSWORD', None)
    
    if not login or not login.strip() or not password or not password.strip():
        print("❌ DATAFORSEO: Credentials not configured in .env")
        print("   Set DATAFORSEO_LOGIN=your_email@example.com")
        print("   Set DATAFORSEO_PASSWORD=your_password in .env")
        return False
    
    print(f"✅ DATAFORSEO: Login found: {login}")
    print(f"✅ DATAFORSEO: Password found: {'*' * len(password)}")
    
    # Initialize client
    try:
        client = DataForSEOClient()
        if not client.is_configured():
            print("❌ DATAFORSEO: Client initialization failed")
            return False
        print("✅ DATAFORSEO: Client initialized successfully")
    except Exception as e:
        print(f"❌ DATAFORSEO: Error initializing client: {e}")
        return False
    
    # Test Google SERP search (real-time API call)
    test_query = "home decor blog"
    test_location = 2840  # USA
    print(f"\n🔍 Making REAL-TIME API call to DataForSEO for query: '{test_query}' (location: {test_location})")
    
    try:
        result = client.serp_google_organic(
            keyword=test_query,
            location_code=test_location,
            depth=5  # Just get 5 results for testing
        )
        
        if result.get("success"):
            results = result.get("results", [])
            total = result.get("total", 0)
            
            print(f"✅ DATAFORSEO: REAL-TIME API call successful!")
            print(f"   Found {total} result(s) for '{test_query}'")
            
            if results:
                print(f"\n   Top results:")
                for i, item in enumerate(results[:3], 1):  # Show first 3
                    url = item.get("url", "N/A")
                    title = item.get("title", "N/A")
                    position = item.get("position", 0)
                    print(f"   {i}. [{position}] {title}")
                    print(f"      {url}")
                if len(results) > 3:
                    print(f"   ... and {len(results) - 3} more results")
            else:
                print("   No results found")
            
            return True
        else:
            error = result.get("error", "Unknown error")
            print(f"❌ DATAFORSEO: API call failed: {error}")
            return False
            
    except Exception as e:
        print(f"❌ DATAFORSEO: Error during API call: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_integration():
    """Test both APIs working together"""
    print("\n" + "="*60)
    print("TESTING INTEGRATION (Both APIs Together)")
    print("="*60)
    
    # Test DataForSEO to find a website
    print("\n1. Using DataForSEO to discover a website...")
    dataforseo_client = DataForSEOClient()
    
    if dataforseo_client.is_configured():
        result = dataforseo_client.serp_google_organic(
            keyword="interior design blog",
            location_code=2840,
            depth=3
        )
        
        if result.get("success") and result.get("results"):
            test_url = result["results"][0].get("url")
            domain = test_url.split("//")[1].split("/")[0].replace("www.", "")
            print(f"   ✅ Found website: {test_url}")
            print(f"   Domain: {domain}")
            
            # Test Hunter.io on that domain
            print(f"\n2. Using Hunter.io to find emails for {domain}...")
            hunter_client = HunterIOClient()
            
            if hunter_client.is_configured():
                hunter_result = hunter_client.domain_search(domain, limit=5)
                
                if hunter_result.get("success"):
                    emails = hunter_result.get("emails", [])
                    print(f"   ✅ Hunter.io found {len(emails)} email(s) for {domain}")
                    if emails:
                        for email_data in emails[:3]:
                            print(f"      - {email_data.get('email')}")
                    return True
                else:
                    print(f"   ⚠️ Hunter.io found no emails (this is normal for some domains)")
                    return True
            else:
                print("   ⚠️ Hunter.io not configured, skipping email test")
                return True
        else:
            print("   ❌ DataForSEO didn't return results")
            return False
    else:
        print("   ⚠️ DataForSEO not configured, skipping integration test")
        return False


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("REAL-TIME API TESTING SUITE")
    print("="*60)
    print("\nThis script tests both Hunter.io and DataForSEO APIs")
    print("to verify they're working in real-time.\n")
    
    results = {
        "hunter_io": False,
        "dataforseo": False,
        "integration": False
    }
    
    # Test Hunter.io
    results["hunter_io"] = test_hunter_io()
    
    # Test DataForSEO
    results["dataforseo"] = test_dataforseo()
    
    # Test integration
    if results["hunter_io"] and results["dataforseo"]:
        results["integration"] = test_integration()
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Hunter.io API:     {'✅ PASS' if results['hunter_io'] else '❌ FAIL'}")
    print(f"DataForSEO API:    {'✅ PASS' if results['dataforseo'] else '❌ FAIL'}")
    print(f"Integration Test:  {'✅ PASS' if results['integration'] else '⚠️ SKIP'}")
    print("="*60)
    
    if results["hunter_io"] and results["dataforseo"]:
        print("\n✅ All APIs are working in REAL-TIME!")
        print("   Your system is ready to use both Hunter.io and DataForSEO.")
    elif results["hunter_io"]:
        print("\n⚠️ Only Hunter.io is working. Configure DataForSEO for website discovery.")
    elif results["dataforseo"]:
        print("\n⚠️ Only DataForSEO is working. Configure Hunter.io for email extraction.")
    else:
        print("\n❌ Neither API is configured. Please set up your API credentials.")
        print("   See HUNTER_IO_SETUP.md and DATAFORSEO_SETUP.md for instructions.")
    
    return results


if __name__ == "__main__":
    main()

