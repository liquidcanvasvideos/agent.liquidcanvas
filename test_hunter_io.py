"""
Quick test script to verify Hunter.io API integration
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from extractor.hunter_io_client import HunterIOClient
from utils.config import settings

def test_hunter_io():
    """Test Hunter.io API connection"""
    print("Testing Hunter.io API Integration...")
    print("=" * 50)
    
    # Check if API key is configured
    api_key = getattr(settings, 'HUNTER_IO_API_KEY', None)
    if not api_key:
        print("❌ ERROR: HUNTER_IO_API_KEY not found in settings")
        print("   Make sure you've added it to your .env file")
        return False
    
    print(f"✅ API Key found: {api_key[:10]}...{api_key[-5:]}")
    
    # Initialize client
    client = HunterIOClient(api_key)
    
    if not client.is_configured():
        print("❌ ERROR: Hunter.io client not configured")
        return False
    
    print("✅ Hunter.io client initialized")
    print()
    
    # Test domain search
    print("Testing domain search for 'liquidcanvas.art'...")
    result = client.domain_search("liquidcanvas.art", limit=5)
    
    if "error" in result:
        print(f"❌ Error: {result['error']}")
        return False
    
    if result.get("success"):
        emails = result.get("emails", [])
        print(f"✅ Success! Found {len(emails)} emails:")
        for email_data in emails:
            print(f"   - {email_data['email']} (confidence: {email_data.get('confidence', 'N/A')})")
        print()
        print(f"Email pattern: {result.get('pattern', 'N/A')}")
    else:
        print(f"⚠️  No emails found: {result.get('error', 'Unknown error')}")
    
    print()
    print("=" * 50)
    print("✅ Hunter.io integration is working!")
    return True

if __name__ == "__main__":
    try:
        test_hunter_io()
    except Exception as e:
        print(f"❌ Error during test: {str(e)}")
        import traceback
        traceback.print_exc()

