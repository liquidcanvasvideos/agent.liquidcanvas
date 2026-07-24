#!/usr/bin/env python3
"""
Hunter.io API Key Verification Script

Tests whether the Hunter.io API key is active and working.
"""
import os
import sys
import json
from typing import Optional, Dict, Any
import httpx
from dotenv import load_dotenv

# Load environment variables (same as backend)
load_dotenv()

# Use the same env var the backend uses
HUNTER_API_KEY = os.getenv("HUNTER_IO_API_KEY")
BASE_URL = "https://api.hunter.io/v2"


def print_status(message: str, status: str = "info"):
    """Print color-coded status messages"""
    colors = {
        "success": "\033[92m",  # Green
        "error": "\033[91m",    # Red
        "warning": "\033[93m",  # Yellow
        "info": "\033[94m",     # Blue
        "reset": "\033[0m"      # Reset
    }
    symbols = {
        "success": "✅",
        "error": "❌",
        "warning": "⚠️ ",
        "info": "ℹ️ "
    }
    color = colors.get(status, colors["info"])
    symbol = symbols.get(status, "")
    reset = colors["reset"]
    print(f"{color}{symbol} {message}{reset}")


def print_response_summary(response: httpx.Response, endpoint: str):
    """Print HTTP response summary"""
    status_code = response.status_code
    status_emoji = "✅" if 200 <= status_code < 300 else "❌" if status_code >= 400 else "⚠️ "
    
    print(f"\n  Endpoint {endpoint}: {status_code} {response.reason_phrase} {status_emoji}")
    
    # Print rate limit headers if present
    rate_limit_remaining = response.headers.get("X-RateLimit-Remaining")
    rate_limit_limit = response.headers.get("X-RateLimit-Limit")
    rate_limit_reset = response.headers.get("X-RateLimit-Reset")
    
    if rate_limit_remaining is not None:
        print(f"  Rate Limit: {rate_limit_remaining}/{rate_limit_limit} remaining")
        if rate_limit_reset:
            print(f"  Rate Limit Reset: {rate_limit_reset}")
    
    # Print response body (first 3 KB)
    try:
        body_text = response.text[:3072]  # First 3 KB
        print(f"  Response body (first 3 KB):")
        print(f"  {body_text}")
    except Exception as e:
        print(f"  Could not read response body: {e}")


def check_account_status() -> tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    Check Hunter.io account status
    
    Returns:
        (success, response_data, error_message)
    """
    try:
        url = f"{BASE_URL}/account"
        params = {"api_key": HUNTER_API_KEY}
        
        print(f"\n📡 Calling {url}...")
        
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, params=params)
            print_response_summary(response, "/account")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    return True, data, None
                except json.JSONDecodeError:
                    return False, None, "Invalid JSON response"
            elif response.status_code == 429:
                # Rate limited
                try:
                    error_data = response.json()
                    errors = error_data.get("errors", [])
                    if errors and len(errors) > 0:
                        first_error = errors[0] if isinstance(errors[0], dict) else {}
                        error_id = first_error.get("id", "")
                        details = first_error.get("details", "")
                        
                        if error_id == "restricted_account" or (details and "restricted" in details.lower()):
                            return False, error_data, f"Account restricted: {details}"
                        else:
                            retry_after = response.headers.get("Retry-After", "unknown")
                            return False, error_data, f"Rate limited - retry after: {retry_after}"
                except json.JSONDecodeError:
                    return False, None, "Rate limited (could not parse error details)"
            else:
                try:
                    error_data = response.json()
                    errors = error_data.get("errors", [])
                    if errors and len(errors) > 0:
                        first_error = errors[0] if isinstance(errors[0], dict) else {}
                        error_id = first_error.get("id", "")
                        details = first_error.get("details", "")
                        
                        if error_id == "restricted_account":
                            return False, error_data, f"Account restricted: {details}"
                        else:
                            return False, error_data, f"Error: {error_id} - {details}"
                except json.JSONDecodeError:
                    return False, None, f"HTTP {response.status_code}: {response.text[:200]}"
                    
    except httpx.TimeoutException:
        return False, None, "Request timed out"
    except httpx.NetworkError as e:
        return False, None, f"Network error: {str(e)}"
    except Exception as e:
        return False, None, f"Unexpected error: {str(e)}"


def test_domain_search() -> tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    Test domain search endpoint
    
    Returns:
        (success, response_data, error_message)
    """
    try:
        url = f"{BASE_URL}/domain-search"
        params = {
            "api_key": HUNTER_API_KEY,
            "domain": "example.com"
        }
        
        print(f"\n📡 Calling {url}?domain=example.com...")
        
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, params=params)
            print_response_summary(response, "/domain-search")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    return True, data, None
                except json.JSONDecodeError:
                    return False, None, "Invalid JSON response"
            elif response.status_code == 429:
                # Rate limited
                try:
                    error_data = response.json()
                    errors = error_data.get("errors", [])
                    if errors and len(errors) > 0:
                        first_error = errors[0] if isinstance(errors[0], dict) else {}
                        error_id = first_error.get("id", "")
                        details = first_error.get("details", "")
                        
                        if error_id == "restricted_account" or (details and "restricted" in details.lower()):
                            return False, error_data, f"Account restricted: {details}"
                        else:
                            retry_after = response.headers.get("Retry-After", "unknown")
                            return False, error_data, f"Rate limited - retry after: {retry_after}"
                except json.JSONDecodeError:
                    return False, None, "Rate limited (could not parse error details)"
            else:
                try:
                    error_data = response.json()
                    errors = error_data.get("errors", [])
                    if errors and len(errors) > 0:
                        first_error = errors[0] if isinstance(errors[0], dict) else {}
                        error_id = first_error.get("id", "")
                        details = first_error.get("details", "")
                        
                        if error_id == "restricted_account":
                            return False, error_data, f"Account restricted: {details}"
                        else:
                            return False, error_data, f"Error: {error_id} - {details}"
                except json.JSONDecodeError:
                    return False, None, f"HTTP {response.status_code}: {response.text[:200]}"
                    
    except httpx.TimeoutException:
        return False, None, "Request timed out"
    except httpx.NetworkError as e:
        return False, None, f"Network error: {str(e)}"
    except Exception as e:
        return False, None, f"Unexpected error: {str(e)}"


def main():
    """Main verification function"""
    print("=" * 60)
    print("Hunter.io API Key Verification")
    print("=" * 60)
    
    # Check if API key is loaded
    if not HUNTER_API_KEY or not HUNTER_API_KEY.strip():
        print_status("HUNTER API KEY: ✗ Missing or empty", "error")
        print("\nPlease set HUNTER_IO_API_KEY in your .env file or environment.")
        sys.exit(2)
    
    # Mask the key for display (show first 8 chars and last 4)
    masked_key = f"{HUNTER_API_KEY[:8]}...{HUNTER_API_KEY[-4:]}" if len(HUNTER_API_KEY) > 12 else "***"
    print_status(f"HUNTER API KEY: ✓ Loaded ({masked_key})", "success")
    
    # Test account endpoint
    account_success, account_data, account_error = check_account_status()
    
    if not account_success:
        if account_error and "restricted" in account_error.lower():
            print_status(f"API key is restricted — {account_error}", "error")
            sys.exit(1)
        elif account_error and "rate limit" in account_error.lower():
            print_status(f"API rate limited — {account_error}", "warning")
            # Continue to test domain search anyway
        else:
            print_status(f"Account check failed — {account_error}", "error")
            sys.exit(1)
    else:
        print_status("Account endpoint: ✓ Working", "success")
    
    # Test domain search endpoint
    search_success, search_data, search_error = test_domain_search()
    
    if not search_success:
        if search_error and "restricted" in search_error.lower():
            print_status(f"API key is restricted — {search_error}", "error")
            sys.exit(1)
        elif search_error and "rate limit" in search_error.lower():
            print_status(f"API rate limited — {search_error}", "warning")
            print_status("Domain search endpoint: ⚠️ Rate limited (but key is valid)", "warning")
            sys.exit(1)
        else:
            print_status(f"Domain search failed — {search_error}", "error")
            sys.exit(1)
    else:
        print_status("Domain search endpoint: ✓ Working", "success")
    
    # Success!
    print("\n" + "=" * 60)
    print_status("API key is active and accepted", "success")
    print("=" * 60)
    sys.exit(0)
if __name__ == "__main__":
    main()



