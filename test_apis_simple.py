"""
Simple test script to verify Hunter.io and DataForSEO APIs
Tests APIs directly without loading full settings
"""
import os
import sys
import requests
import base64
import json

def test_hunter_io_direct():
    """Test Hunter.io API directly"""
    print("\n" + "="*60)
    print("TESTING HUNTER.IO API (REAL-TIME)")
    print("="*60)
    
    # Get API key from environment or .env file
    api_key = None
    
    # Try to read from .env file
    try:
        if os.path.exists('.env'):
            with open('.env', 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith('HUNTER_IO_API_KEY='):
                        api_key = line.split('=', 1)[1].strip().strip('"').strip("'")
                        break
    except Exception as e:
        print(f"⚠️ Could not read .env file: {e}")
    
    # Fallback to environment variable
    if not api_key:
        api_key = os.getenv('HUNTER_IO_API_KEY')
    
    if not api_key or not api_key.strip():
        print("❌ HUNTER.IO: API key not found")
        print("   Set HUNTER_IO_API_KEY in .env file or environment variable")
        return False
    
    print(f"✅ HUNTER.IO: API key found: {api_key[:10]}...{api_key[-4:]}")
    
    # Test API call
    test_domain = "liquidcanvas.art"
    print(f"\n🔍 Making REAL-TIME API call to Hunter.io for domain: {test_domain}")
    
    try:
        url = "https://api.hunter.io/v2/domain-search"
        params = {
            "domain": test_domain,
            "api_key": api_key,
            "limit": 10
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get("data") and data["data"].get("emails"):
            emails = data["data"]["emails"]
            total = data["data"].get("total", len(emails))
            pattern = data["data"].get("pattern", "N/A")
            
            print(f"✅ HUNTER.IO: REAL-TIME API call successful!")
            print(f"   Found {total} total email(s) for {test_domain}")
            print(f"   Email pattern: {pattern}")
            
            if emails:
                print(f"\n   Emails found:")
                for i, email_data in enumerate(emails[:5], 1):
                    email = email_data.get("value", "N/A")
                    confidence = email_data.get("confidence_score", 0)
                    email_type = email_data.get("type", "N/A")
                    print(f"   {i}. {email} (confidence: {confidence}%, type: {email_type})")
                if len(emails) > 5:
                    print(f"   ... and {len(emails) - 5} more")
            
            return True
        else:
            error = data.get("errors", [{}])[0].get("details", "No emails found")
            print(f"⚠️ HUNTER.IO: No emails found (this is normal for some domains)")
            print(f"   Response: {error}")
            return True  # Still consider it a pass if API works
            
    except requests.exceptions.RequestException as e:
        print(f"❌ HUNTER.IO: API request failed: {e}")
        return False
    except Exception as e:
        print(f"❌ HUNTER.IO: Error: {e}")
        return False


def test_dataforseo_direct():
    """Test DataForSEO API directly"""
    print("\n" + "="*60)
    print("TESTING DATAFORSEO API (REAL-TIME)")
    print("="*60)
    
    # Get credentials from environment or .env file
    login = None
    password = None
    
    # Try to read from .env file
    try:
        if os.path.exists('.env'):
            with open('.env', 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith('DATAFORSEO_LOGIN='):
                        login = line.split('=', 1)[1].strip().strip('"').strip("'")
                    elif line.startswith('DATAFORSEO_PASSWORD='):
                        password = line.split('=', 1)[1].strip().strip('"').strip("'")
    except Exception as e:
        print(f"⚠️ Could not read .env file: {e}")
    
    # Fallback to environment variables
    if not login:
        login = os.getenv('DATAFORSEO_LOGIN')
    if not password:
        password = os.getenv('DATAFORSEO_PASSWORD')
    
    if not login or not login.strip() or not password or not password.strip():
        print("❌ DATAFORSEO: Credentials not found")
        print("   Set DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD in .env file")
        return False
    
    print(f"✅ DATAFORSEO: Login found: {login}")
    print(f"✅ DATAFORSEO: Password found: {'*' * len(password)}")
    
    # Test API call
    test_query = "home decor blog"
    print(f"\n🔍 Making REAL-TIME API call to DataForSEO for query: '{test_query}'")
    
    try:
        url = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"
        
        # Create basic auth header
        credentials = f"{login}:{password}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/json"
        }
        
        payload = [{
            "keyword": test_query,
            "location_code": 2840,  # USA
            "language_code": "en",
            "depth": 5,
            "device": "desktop",
            "os": "windows"
        }]
        
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get("tasks") and len(data["tasks"]) > 0:
            task = data["tasks"][0]
            if task.get("status_code") == 20000 and task.get("result"):
                results = task["result"][0].get("items", [])
                organic_results = [r for r in results if r.get("type") == "organic"]
                
                print(f"✅ DATAFORSEO: REAL-TIME API call successful!")
                print(f"   Found {len(organic_results)} result(s) for '{test_query}'")
                
                if organic_results:
                    print(f"\n   Top results:")
                    for i, item in enumerate(organic_results[:3], 1):
                        url_result = item.get("url", "N/A")
                        title = item.get("title", "N/A")
                        position = item.get("rank_absolute", 0)
                        print(f"   {i}. [{position}] {title}")
                        print(f"      {url_result}")
                    if len(organic_results) > 3:
                        print(f"   ... and {len(organic_results) - 3} more results")
                
                return True
            else:
                error = task.get("status_message", "Unknown error")
                print(f"❌ DATAFORSEO: API returned error: {error}")
                return False
        else:
            print(f"❌ DATAFORSEO: Unexpected response format")
            print(f"   Response: {json.dumps(data, indent=2)[:500]}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ DATAFORSEO: API request failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                print(f"   Error details: {json.dumps(error_data, indent=2)[:500]}")
            except:
                print(f"   Response: {e.response.text[:500]}")
        return False
    except Exception as e:
        print(f"❌ DATAFORSEO: Error: {e}")
        import traceback
        traceback.print_exc()
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
        "dataforseo": False
    }
    
    # Test Hunter.io
    results["hunter_io"] = test_hunter_io_direct()
    
    # Test DataForSEO
    results["dataforseo"] = test_dataforseo_direct()
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Hunter.io API:     {'✅ PASS' if results['hunter_io'] else '❌ FAIL'}")
    print(f"DataForSEO API:    {'✅ PASS' if results['dataforseo'] else '❌ FAIL'}")
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

