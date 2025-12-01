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
                    
                    # Format emails
                    formatted_emails = []
                    for email in emails:
                        formatted_emails.append({
                            "value": email.get("value", ""),
                            "type": email.get("type", ""),  # generic, personal, etc.
                            "confidence_score": email.get("confidence_score", 0),
                            "sources": email.get("sources", []),
                            "first_name": email.get("first_name"),
                            "last_name": email.get("last_name"),
                            "position": email.get("position"),
                            "company": email.get("company")
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
            logger.error(f"Hunter.io API HTTP error for {domain}: {e.response.status_code} - {e.response.text}")
            return {
                "success": False,
                "error": f"HTTP {e.response.status_code}: {e.response.text}",
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

