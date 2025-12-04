"""
Hunter.io API client for email enrichment
"""
import httpx
from typing import Dict, List, Optional, Any
import os
from dotenv import load_dotenv
import logging

load_dotenv()

logger = logging.getLogger(__name__)


class HunterIOClient:
    """Client for Hunter.io API"""
    
    BASE_URL = "https://api.hunter.io/v2"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Hunter.io client
        
        Args:
            api_key: Hunter.io API key (if None, uses HUNTER_IO_API_KEY from env)
        """
        self.api_key = api_key or os.getenv("HUNTER_IO_API_KEY")
        
        if not self.api_key:
            raise ValueError("Hunter.io API key not configured. Set HUNTER_IO_API_KEY")
    
    def is_configured(self) -> bool:
        """Check if client is properly configured"""
        return bool(self.api_key and self.api_key.strip())
    
    async def domain_search(
        self,
        domain: str,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        Search for emails associated with a domain
        
        Args:
            domain: Domain name (e.g., "example.com")
            limit: Maximum number of results (default: 50)
        
        Returns:
            Dictionary with email results
        """
        # Hunter free / lower plans often cap results to 10 emails; requesting
        # more can trigger a pagination_error (HTTP 400). To keep enrichment
        # working reliably, we clamp the limit to 10 here.
        effective_limit = max(1, min(int(limit or 10), 10))

        url = f"{self.BASE_URL}/domain-search"
        
        params = {
            "domain": domain,
            "api_key": self.api_key,
            "limit": effective_limit,
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.info(f"Calling Hunter.io API for domain: {domain} (limit={effective_limit})")
                response = await client.get(url, params=params)
                response.raise_for_status()
                result = response.json()
                
                if result.get("data"):
                    emails = result["data"].get("emails", [])
                    logger.info(f"Hunter.io found {len(emails)} email(s) for {domain}")
                    
                    # Parse emails correctly - extract ONLY: value, type, confidence_score
                    formatted_emails = []
                    for email in emails:
                        if not isinstance(email, dict):
                            continue
                        
                        # Extract ONLY the required fields as specified
                        email_value = email.get("value")
                        email_type = email.get("type", "")
                        confidence_score = float(email.get("confidence_score", 0) or 0)
                        
                        if not email_value:
                            continue
                        
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
                    # Safely extract error message
                    errors = result.get("errors", [])
                    if errors and isinstance(errors, list) and len(errors) > 0:
                        error = errors[0] if isinstance(errors[0], dict) else {}
                    else:
                        error = {}
                    error_msg = error.get("details", "No emails found")
                    logger.info(f"Hunter.io returned no emails for {domain}: {error_msg}")
                    return {
                        "success": True,  # Still success, just no emails
                        "domain": domain,
                        "emails": [],
                        "total": 0,
                        "message": error_msg
                    }
        
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            logger.error(f"Hunter.io API HTTP error for {domain}: {status_code} - {e.response.text}")
            
            # Detect 429 rate limit - DO NOT treat as "no email found"
            if status_code == 429:
                logger.warning(f"⚠️  [HUNTER] Rate limit (429) detected for {domain}")
                return {
                    "success": False,
                    "status": "rate_limited",
                    "error": f"HTTP {status_code}: {e.response.text}",
                    "domain": domain
                }
            
            return {
                "success": False,
                "error": f"HTTP {status_code}: {e.response.text}",
                "domain": domain
            }
        except Exception as e:
            logger.error(f"Hunter.io API call failed for {domain}: {str(e)}")
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
        url = f"{self.BASE_URL}/email-verifier"
        
        params = {
            "email": email,
            "api_key": self.api_key
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                result = response.json()
                
                if result.get("data"):
                    data = result["data"]
                    return {
                        "success": True,
                        "email": email,
                        "result": data.get("result"),  # deliverable, undeliverable, risky, unknown
                        "score": data.get("score", 0),
                        "sources": data.get("sources", []),
                        "raw_response": result
                    }
                else:
                    return {
                        "success": False,
                        "error": "No verification data returned",
                        "email": email
                    }
        
        except Exception as e:
            logger.error(f"Hunter.io email verification failed for {email}: {str(e)}")
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
        url = f"{self.BASE_URL}/email-finder"
        
        params = {
            "domain": domain,
            "api_key": self.api_key
        }
        
        if first_name:
            params["first_name"] = first_name
        if last_name:
            params["last_name"] = last_name
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.info(f"Calling Hunter.io email-finder for {domain} (name: {first_name} {last_name})")
                response = await client.get(url, params=params)
                response.raise_for_status()
                result = response.json()
                
                if result.get("data") and result["data"].get("email"):
                    data = result["data"]
                    return {
                        "success": True,
                        "email": data.get("email"),
                        "score": data.get("score", 0),
                        "sources": data.get("sources", []),
                        "first_name": data.get("first_name"),
                        "last_name": data.get("last_name"),
                        "company": data.get("company"),
                        "position": data.get("position"),
                        "raw_response": result
                    }
                else:
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
            logger.error(f"Hunter.io email-finder failed for {domain}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "domain": domain
            }
    
    async def company_enrichment(
        self,
        domain: str
    ) -> Dict[str, Any]:
        """
        Get company information for a domain
        
        Args:
            domain: Domain name (e.g., "example.com")
        
        Returns:
            Dictionary with company information
        """
        url = f"{self.BASE_URL}/companies/find"
        
        params = {
            "domain": domain,
            "api_key": self.api_key
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.info(f"Calling Hunter.io company enrichment for {domain}")
                response = await client.get(url, params=params)
                response.raise_for_status()
                result = response.json()
                
                if result.get("data"):
                    data = result["data"]
                    return {
                        "success": True,
                        "domain": domain,
                        "name": data.get("name"),
                        "country": data.get("country"),
                        "industry": data.get("industry"),
                        "employees": data.get("employees"),
                        "linkedin_url": data.get("linkedin_url"),
                        "twitter_url": data.get("twitter_url"),
                        "facebook_url": data.get("facebook_url"),
                        "phone_numbers": data.get("phone_numbers", []),
                        "raw_response": result
                    }
                else:
                    return {
                        "success": False,
                        "error": "No company data found",
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
            logger.error(f"Hunter.io company enrichment failed for {domain}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "domain": domain
            }
    
    async def combined_enrichment(
        self,
        email: str
    ) -> Dict[str, Any]:
        """
        Get combined enrichment data (person + company) for an email
        
        Args:
            email: Email address
        
        Returns:
            Dictionary with combined enrichment data
        """
        url = f"{self.BASE_URL}/combined/find"
        
        params = {
            "email": email,
            "api_key": self.api_key
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.info(f"Calling Hunter.io combined enrichment for {email}")
                response = await client.get(url, params=params)
                response.raise_for_status()
                result = response.json()
                
                if result.get("data"):
                    data = result["data"]
                    return {
                        "success": True,
                        "email": email,
                        "person": data.get("person", {}),
                        "company": data.get("company", {}),
                        "raw_response": result
                    }
                else:
                    return {
                        "success": False,
                        "error": "No enrichment data found",
                        "email": email
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
                "email": email
            }
        except Exception as e:
            logger.error(f"Hunter.io combined enrichment failed for {email}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "email": email
            }

