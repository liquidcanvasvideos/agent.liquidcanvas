"""
Local test script for DataForSEO integration
Tests the exact scenario: "home decor blog" in United States
"""
import asyncio
import os
import sys
from dotenv import load_dotenv

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

load_dotenv()

async def test_dataforseo():
    """Test DataForSEO with exact requirements"""
    from app.clients.dataforseo import DataForSEOClient
    
    print("=" * 80)
    print("DataForSEO Local Test")
    print("=" * 80)
    print()
    
    # Check credentials
    login = os.getenv("DATAFORSEO_LOGIN")
    password = os.getenv("DATAFORSEO_PASSWORD")
    
    if not login or not password:
        print("❌ ERROR: DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD must be set in .env")
        return False
    
    print(f"✅ Credentials found: {login[:3]}...")
    print()
    
    # Initialize client
    try:
        client = DataForSEOClient()
        print("✅ Client initialized")
    except Exception as e:
        print(f"❌ Client initialization failed: {e}")
        return False
    
    # Test location mapping
    print("\n📍 Testing location mapping:")
    test_locations = ["usa", "United States", "canada", "germany", "france", "uk_london"]
    for loc in test_locations:
        code = client.get_location_code(loc)
        print(f"   {loc:20} -> {code}")
    
    # Test with exact requirements
    print("\n" + "=" * 80)
    print("Testing: keyword='home decor blog', location='United States', language='en'")
    print("=" * 80)
    print()
    
    keyword = "home decor blog"
    location = "United States"
    location_code = client.get_location_code(location)
    language_code = "en"
    
    print(f"Keyword: '{keyword}'")
    print(f"Location: '{location}' -> code {location_code}")
    print(f"Language: '{language_code}'")
    print()
    
    # Make API call
    print("🔵 Making DataForSEO API call...")
    print()
    
    try:
        result = await client.serp_google_organic(
            keyword=keyword,
            location_code=location_code,
            language_code=language_code,
            depth=10,
            device="desktop"
        )
        
        print()
        print("=" * 80)
        print("RESULT")
        print("=" * 80)
        
        if result.get("success"):
            results = result.get("results", [])
            total = result.get("total", 0)
            
            print(f"✅ SUCCESS!")
            print(f"   Total results: {total}")
            print()
            
            if results:
                print("Top 5 results:")
                for i, item in enumerate(results[:5], 1):
                    print(f"   {i}. {item.get('title', 'N/A')[:60]}")
                    print(f"      URL: {item.get('url', 'N/A')}")
                    print(f"      Domain: {item.get('domain', 'N/A')}")
                    print()
            else:
                print("⚠️  No results returned (but API call succeeded)")
        else:
            error = result.get("error", "Unknown error")
            print(f"❌ FAILED: {error}")
            return False
        
        # Check diagnostics
        print("=" * 80)
        print("DIAGNOSTICS")
        print("=" * 80)
        diagnostics = client.get_diagnostics()
        print(f"Request count: {diagnostics['request_count']}")
        print(f"Success count: {diagnostics['success_count']}")
        print(f"Error count: {diagnostics['error_count']}")
        print(f"Success rate: {diagnostics['success_rate']:.1f}%")
        
        return result.get("success", False)
        
    except Exception as e:
        print(f"❌ Exception during test: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_dataforseo())
    sys.exit(0 if success else 1)

