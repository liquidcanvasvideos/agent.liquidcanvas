"""
Snov.io API client for email enrichment
"""
import httpx
from typing import Dict, List, Optional, Any
import os
from dotenv import load_dotenv
import logging
import json
import base64

from app.services.exceptions import RateLimitError

load_dotenv()

logger = logging.getLogger(__name__)


class SnovIOClient:
    """Client for Snov.io API"""
    
    BASE_URL = "https://api.snov.io/v1"
    
    def __init__(self, user_id: Optional[str] = None, secret: Optional[str] = None):
        """
        Initialize Snov.io client
        
        Args:
            user_id: Snov.io User ID (if None, uses SNOV_USER_ID from env)
            secret: Snov.io Secret (if None, uses SNOV_SECRET from env)
        """
        self.user_id = user_id or os.getenv("SNOV_USER_ID")
        self.secret = secret or os.getenv("SNOV_SECRET")
        
        if not self.user_id or not self.secret:
            raise ValueError("Snov.io credentials not configured. Set SNOV_USER_ID and SNOV_SECRET")
    
    def is_configured(self) -> bool:
        """Check if client is properly configured"""
        return bool(self.user_id and self.secret and self.user_id.strip() and self.secret.strip())
    
    async def _get_access_token(self) -> str:
        """
        Get access token using OAuth2 client credentials flow
        
        Snov.io API uses OAuth2 with client_id and client_secret as form data.
        Alternative: Some Snov.io endpoints may accept credentials directly.
        
        Returns:
            Access token string
        """
        url = f"{self.BASE_URL}/oauth/access_token"
        
        # Try method 1: OAuth2 with form data (client_id/client_secret)
        data_method1 = {
            "grant_type": "client_credentials",
            "client_id": self.user_id,
            "client_secret": self.secret
        }
        
        # Try method 2: OAuth2 with user_id/secret as form data (alternative format)
        data_method2 = {
            "grant_type": "client_credentials",
            "user_id": self.user_id,
            "secret": self.secret
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        # Try method 1 first
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.debug(f"Requesting Snov.io access token (method 1) with user_id: {self.user_id[:10] if self.user_id else 'None'}...")
                response = await client.post(url, headers=headers, data=data_method1)
                
                if response.status_code == 200:
                    result = response.json()
                    access_token = result.get("access_token")
                    if access_token:
                        logger.debug("✅ Snov.io access token obtained successfully (method 1)")
                        return access_token
                
                # If method 1 failed, try method 2
                logger.debug(f"Method 1 failed ({response.status_code}), trying method 2...")
                if response.status_code != 200:
                    error_body = response.text
                    logger.debug(f"Method 1 error response: {error_body}")
                
                response = await client.post(url, headers=headers, data=data_method2)
                
                # Log response details for debugging
                if response.status_code != 200:
                    try:
                        error_body = response.text
                        logger.error(f"Snov.io token request failed ({response.status_code}): {error_body}")
                    except:
                        logger.error(f"Snov.io token request failed ({response.status_code}): {response.text}")
                else:
                    result = response.json()
                    access_token = result.get("access_token")
                    if access_token:
                        logger.debug("✅ Snov.io access token obtained successfully (method 2)")
                        return access_token
                
                response.raise_for_status()
                result = response.json()
                
                access_token = result.get("access_token")
                if not access_token:
                    logger.error(f"No access_token in Snov.io response: {result}")
                    raise ValueError("No access token in response")
                
                return access_token
                
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP {e.response.status_code}"
            try:
                error_body = e.response.json()
                error_msg += f": {error_body}"
            except:
                error_msg += f": {e.response.text[:500]}"  # Limit error message length
            logger.error(f"Snov.io token request failed: {error_msg}")
            raise Exception(f"Failed to get Snov.io access token: {error_msg}")
        except Exception as e:
            logger.error(f"Snov.io token request failed: {str(e)}", exc_info=True)
            raise Exception(f"Failed to get Snov.io access token: {str(e)}")
    
    async def domain_search(
        self,
        domain: str,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Search for emails associated with a domain
        
        Args:
            domain: Domain name (e.g., "example.com")
            limit: Maximum number of results (default: 10)
        
        Returns:
            Dictionary with email results in format compatible with Hunter.io response
        """
        try:
            # Get access token
            access_token = await self._get_access_token()
            
            # Snov.io API endpoint - try different formats
            # Method 1: Use access_token in Authorization header (OAuth2 standard)
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            # Try multiple endpoint variations with different parameter formats
            endpoints_to_try = [
                {
                    "endpoint": "/get-domain-emails-with-info",
                    "params": {"domain": domain, "type": "all", "limit": min(limit, 100)},
                    "headers": headers
                },
                {
                    "endpoint": "/get-domain-emails-with-info",
                    "params": {"domain": domain, "access_token": access_token, "type": "all", "limit": min(limit, 100)},
                    "headers": {"Content-Type": "application/json"}
                },
                {
                    "endpoint": "/get-domain-emails",
                    "params": {"domain": domain, "type": "all", "limit": min(limit, 100)},
                    "headers": headers
                },
                {
                    "endpoint": "/get-domain-emails",
                    "params": {"domain": domain, "access_token": access_token, "type": "all", "limit": min(limit, 100)},
                    "headers": {"Content-Type": "application/json"}
                },
                {
                    "endpoint": "/domain-emails",
                    "params": {"domain": domain, "type": "all", "limit": min(limit, 100)},
                    "headers": headers
                },
                {
                    "endpoint": "/domain-emails",
                    "params": {"domain": domain, "access_token": access_token, "type": "all", "limit": min(limit, 100)},
                    "headers": {"Content-Type": "application/json"}
                },
            ]
            
            last_error = None
            async with httpx.AsyncClient(timeout=30.0) as client:
                for endpoint_config in endpoints_to_try:
                    method = endpoint_config["method"]
                    endpoint = endpoint_config["endpoint"]
                    params = endpoint_config["params"]
                    req_headers = endpoint_config["headers"]
                    body = endpoint_config["body"]
                    url = f"{self.BASE_URL}{endpoint}"
                    try:
                        auth_method = 'Bearer token' if 'Authorization' in req_headers else 'access_token param'
                        logger.info(f"Calling Snov.io API for domain: {domain} using {method} {endpoint} with {auth_method}")
                        
                        if method == "POST":
                            response = await client.post(url, params=params, headers=req_headers, json=body)
                        else:
                            response = await client.get(url, params=params, headers=req_headers)
                        
                        # If 404, try next endpoint
                        if response.status_code == 404:
                            error_body = response.text[:200] if response.text else ""
                            logger.debug(f"Snov.io endpoint {endpoint} returned 404: {error_body}, trying next method...")
                            last_error = f"HTTP 404: {error_body}"
                            continue
                        
                        # If 401, authentication issue - try different auth method
                        if response.status_code == 401:
                            error_body = response.text[:200] if response.text else ""
                            logger.debug(f"Snov.io endpoint {endpoint} returned 401 (auth failed): {error_body}, trying different auth method...")
                            last_error = f"HTTP 401: {error_body}"
                            continue
                        
                        response.raise_for_status()
                        result = response.json()
                        logger.info(f"✅ Snov.io API call successful for {domain} using endpoint: {endpoint}")
                        break  # Success, exit loop
                    except httpx.HTTPStatusError as e:
                        if e.response.status_code == 404:
                            error_body = e.response.text[:200] if e.response.text else ""
                            logger.debug(f"Snov.io endpoint {endpoint} returned 404: {error_body}, trying next method...")
                            last_error = f"HTTP 404: {error_body}"
                            continue
                        elif e.response.status_code == 401:
                            error_body = e.response.text[:200] if e.response.text else ""
                            logger.debug(f"Snov.io endpoint {endpoint} returned 401 (auth failed): {error_body}, trying different auth method...")
                            last_error = f"HTTP 401: {error_body}"
                            continue
                        else:
                            # Log non-404/401 errors but continue trying
                            error_body = e.response.text[:200] if e.response.text else ""
                            logger.warning(f"Snov.io endpoint {endpoint} returned {e.response.status_code}: {error_body}")
                            last_error = f"HTTP {e.response.status_code}: {error_body}"
                            continue
                else:
                    # All endpoints failed with 404 - domain not in Snov.io database
                    logger.info(f"Snov.io returned 404 for all endpoints for {domain} - domain may not be in database")
                    return {
                        "success": True,  # Treat as success (no emails found, not an error)
                        "domain": domain,
                        "emails": [],
                        "total": 0,
                        "message": "Domain not found in Snov.io database"
                    }
                
                # Handle Snov.io response format
                if result.get("success"):
                    emails_data = result.get("emails", [])
                    logger.info(f"Snov.io found {len(emails_data)} email(s) for {domain}")
                    
                    # Convert Snov.io format to Hunter.io-compatible format
                    formatted_emails = []
                    for email_data in emails_data:
                        if not isinstance(email_data, dict):
                            continue
                        
                        email_value = email_data.get("email") or email_data.get("emailAddress")
                        if not email_value:
                            continue
                        
                        # Snov.io provides confidence as a score (0-100)
                        confidence_score = float(email_data.get("confidence", 0) or 0)
                        
                        # Determine email type
                        email_type = "personal" if email_data.get("type") == "personal" else "generic"
                        
                        formatted_emails.append({
                            "value": email_value,
                            "type": email_type,
                            "confidence_score": confidence_score
                        })
                    
                    return {
                        "success": True,
                        "domain": domain,
                        "emails": formatted_emails,
                        "total": len(formatted_emails),
                        "raw_response": result
                    }
                else:
                    error_msg = result.get("error", {}).get("message", "No emails found")
                    logger.info(f"Snov.io returned no emails for {domain}: {error_msg}")
                    return {
                        "success": True,  # Still success, just no emails
                        "domain": domain,
                        "emails": [],
                        "total": 0,
                        "message": error_msg
                    }
        
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            error_text = e.response.text
            
            # Handle 404 gracefully - domain not in Snov.io database
            if status_code == 404:
                logger.info(f"Snov.io returned 404 for {domain} - domain not in database")
                return {
                    "success": True,  # Treat as success (no emails found, not an error)
                    "domain": domain,
                    "emails": [],
                    "total": 0,
                    "message": "Domain not found in Snov.io database"
                }
            
            logger.error(f"Snov.io API HTTP error for {domain}: {status_code} - {error_text}")
            
            # Detect 429 rate limit
            if status_code == 429:
                logger.warning(f"⚠️  [SNOV] Rate limit (429) detected for {domain}")
                try:
                    error_body = e.response.json()
                    error_msg = error_body.get("error", {}).get("message", "Rate limit exceeded")
                except:
                    error_msg = "Rate limit exceeded"
                
                raise RateLimitError(
                    provider="snov",
                    message=f"Snov.io rate limit exceeded: {error_msg}",
                    retry_after=60,
                    error_id="too_many_requests",
                    details=error_msg
                )
            
            return {
                "success": False,
                "error": f"HTTP {status_code}: {e.response.text}",
                "domain": domain
            }
        except RateLimitError:
            raise
        except Exception as e:
            logger.error(f"Snov.io API call failed for {domain}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "domain": domain
            }
    
    async def email_verifier(
        self,
        email: str
    ) -> Dict[str, Any]:
        """
        Verify an email address
        
        Args:
            email: Email address to verify
        
        Returns:
            Dictionary with verification result
        """
        try:
            access_token = await self._get_access_token()
            
            url = f"{self.BASE_URL}/verify-email"
            
            params = {
                "email": email,
                "access_token": access_token
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                result = response.json()
                
                # Snov.io verification response format
                if result.get("success"):
                    data = result.get("result", {})
                    # Map Snov.io status to Hunter.io-compatible format
                    snov_status = data.get("status", "unknown")
                    status_map = {
                        "valid": "deliverable",
                        "invalid": "undeliverable",
                        "unknown": "unknown",
                        "risky": "risky"
                    }
                    
                    return {
                        "success": True,
                        "email": email,
                        "result": status_map.get(snov_status, "unknown"),
                        "score": float(data.get("score", 0) or 0),
                        "sources": [],
                        "raw_response": result
                    }
                else:
                    return {
                        "success": False,
                        "error": result.get("error", {}).get("message", "No verification data returned"),
                        "email": email
                    }
        
        except Exception as e:
            logger.error(f"Snov.io email verification failed for {email}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "email": email
            }
    
    async def email_finder(
        self,
        domain: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Find email for a specific person
        
        Args:
            domain: Domain name (e.g., "example.com")
            first_name: First name (optional)
            last_name: Last name (optional)
        
        Returns:
            Dictionary with email result
        """
        try:
            access_token = await self._get_access_token()
            
            url = f"{self.BASE_URL}/get-emails-from-names"
            
            params = {
                "domain": domain,
                "access_token": access_token
            }
            
            if first_name:
                params["firstName"] = first_name
            if last_name:
                params["lastName"] = last_name
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.info(f"Calling Snov.io email-finder for {domain} (name: {first_name} {last_name})")
                response = await client.get(url, params=params)
                response.raise_for_status()
                result = response.json()
                
                if result.get("success") and result.get("emails"):
                    emails = result["emails"]
                    if isinstance(emails, list) and len(emails) > 0:
                        best_email = emails[0]  # Snov.io returns best match first
                        return {
                            "success": True,
                            "email": best_email.get("email"),
                            "score": float(best_email.get("confidence", 0) or 0),
                            "sources": [],
                            "first_name": best_email.get("firstName"),
                            "last_name": best_email.get("lastName"),
                            "company": None,
                            "position": None,
                            "raw_response": result
                        }
                
                return {
                    "success": False,
                    "error": "No email found",
                    "domain": domain
                }
        
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            if status_code == 429:
                return {
                    "success": False,
                    "status": "rate_limited",
                    "error": f"HTTP {status_code}: Rate limit exceeded"
                }
            return {
                "success": False,
                "error": f"HTTP {status_code}: {e.response.text}",
                "domain": domain
            }
        except Exception as e:
            logger.error(f"Snov.io email-finder failed for {domain}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "domain": domain
            }

