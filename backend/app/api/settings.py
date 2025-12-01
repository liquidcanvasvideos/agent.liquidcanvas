"""
Settings and API configuration management endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import os
from dotenv import load_dotenv
import logging

from app.db.database import get_db
from app.models.settings import Settings
from sqlalchemy import select
from sqlalchemy.sql import func

load_dotenv()
logger = logging.getLogger(__name__)

router = APIRouter()


class APIKeyUpdate(BaseModel):
    """Request model for updating API keys"""
    value: Optional[str] = None
    enabled: bool = True


class ServiceStatus(BaseModel):
    """Response model for service status"""
    name: str
    enabled: bool
    configured: bool
    status: str  # "connected", "disconnected", "error", "not_configured"
    message: Optional[str] = None
    last_tested: Optional[str] = None


class SettingsResponse(BaseModel):
    """Response model for all settings"""
    services: Dict[str, ServiceStatus]
    api_keys: Dict[str, bool]  # Key name -> is_configured (without exposing values)


# API Key environment variable mappings
API_KEY_MAPPINGS = {
    "hunter_io": "HUNTER_IO_API_KEY",
    "dataforseo_login": "DATAFORSEO_LOGIN",
    "dataforseo_password": "DATAFORSEO_PASSWORD",
    "gemini": "GEMINI_API_KEY",
    "gmail_client_id": "GMAIL_CLIENT_ID",
    "gmail_client_secret": "GMAIL_CLIENT_SECRET",
    "gmail_refresh_token": "GMAIL_REFRESH_TOKEN",
}


@router.get("/api-keys", response_model=Dict[str, bool])
async def get_api_keys_status():
    """
    Get status of all API keys (configured or not, without exposing values)
    """
    status = {}
    for key_name, env_var in API_KEY_MAPPINGS.items():
        value = os.getenv(env_var)
        status[key_name] = bool(value and value.strip())
    return status


@router.post("/api-keys/{key_name}")
async def update_api_key(key_name: str, update: APIKeyUpdate):
    """
    Update an API key (for now, returns instructions - actual update requires env var change)
    
    Note: In production, you'd want to store these securely (e.g., in a database with encryption)
    For now, we return instructions since environment variables require server restart
    """
    if key_name not in API_KEY_MAPPINGS:
        raise HTTPException(status_code=404, detail=f"API key '{key_name}' not found")
    
    env_var = API_KEY_MAPPINGS[key_name]
    
    # In a real implementation, you'd update the environment variable or database
    # For now, we return instructions
    return {
        "message": f"To update {key_name}, set environment variable {env_var}",
        "environment_variable": env_var,
        "note": "Environment variables require server restart to take effect. Update in Render dashboard → Environment Variables"
    }


@router.get("/services/status", response_model=SettingsResponse)
async def get_services_status():
    """
    Get status of all services (Hunter.io, DataForSEO, Gemini, Gmail)
    """
    services = {}
    api_keys_status = {}
    
    # First, check all API keys
    for key_name, env_var in API_KEY_MAPPINGS.items():
        value = os.getenv(env_var)
        is_configured = bool(value and value.strip())
        api_keys_status[key_name] = is_configured
    
    # Check Hunter.io
    hunter_key = os.getenv("HUNTER_IO_API_KEY")
    hunter_configured = bool(hunter_key and hunter_key.strip())
    services["Hunter.io"] = ServiceStatus(
        name="Hunter.io",
        enabled=hunter_configured,
        configured=hunter_configured,
        status="not_configured" if not hunter_configured else "unknown",
        message="Not configured" if not hunter_configured else "Configured (not tested)",
    )
    
    # Check DataForSEO
    dataforseo_login = os.getenv("DATAFORSEO_LOGIN")
    dataforseo_password = os.getenv("DATAFORSEO_PASSWORD")
    dataforseo_configured = bool(
        dataforseo_login and dataforseo_password and 
        dataforseo_login.strip() and dataforseo_password.strip()
    )
    services["DataForSEO"] = ServiceStatus(
        name="DataForSEO",
        enabled=dataforseo_configured,
        configured=dataforseo_configured,
        status="not_configured" if not dataforseo_configured else "unknown",
        message="Not configured" if not dataforseo_configured else "Configured (not tested)",
    )
    
    # Check Gemini
    gemini_key = os.getenv("GEMINI_API_KEY")
    gemini_configured = bool(gemini_key and gemini_key.strip())
    services["Google Gemini"] = ServiceStatus(
        name="Google Gemini",
        enabled=gemini_configured,
        configured=gemini_configured,
        status="not_configured" if not gemini_configured else "unknown",
        message="Not configured" if not gemini_configured else "Configured (not tested)",
    )
    
    # Check Gmail
    gmail_client_id = os.getenv("GMAIL_CLIENT_ID")
    gmail_client_secret = os.getenv("GMAIL_CLIENT_SECRET")
    gmail_refresh_token = os.getenv("GMAIL_REFRESH_TOKEN")
    gmail_configured = bool(
        gmail_client_id and gmail_client_secret and gmail_refresh_token and
        all(v.strip() for v in [gmail_client_id, gmail_client_secret, gmail_refresh_token])
    )
    services["Gmail API"] = ServiceStatus(
        name="Gmail API",
        enabled=gmail_configured,
        configured=gmail_configured,
        status="not_configured" if not gmail_configured else "unknown",
        message="Not configured" if not gmail_configured else "Configured (not tested)",
    )
    
    return SettingsResponse(services=services, api_keys=api_keys_status)


@router.post("/services/{service_name}/test")
async def test_service(service_name: str):
    """
    Test a service connection
    
    Service names: "Hunter.io", "DataForSEO", "Google Gemini", "Gmail API"
    """
    try:
        service_lower = service_name.lower().replace(" ", "").replace(".", "")
        
        if "hunter" in service_lower:
            from app.clients.hunter import HunterIOClient
            api_key = os.getenv("HUNTER_IO_API_KEY")
            if not api_key:
                return {
                    "success": False,
                    "status": "not_configured",
                    "message": "Hunter.io API key not configured"
                }
            client = HunterIOClient(api_key)
            # Test with a known domain
            result = await client.domain_search("liquidcanvas.art")
            return {
                "success": True,
                "status": "connected",
                "message": f"Hunter.io is working. Found {len(result.get('emails', []))} emails for test domain.",
                "test_result": result
            }
        
        elif "dataforseo" in service_lower:
            from app.clients.dataforseo import DataForSEOClient
            login = os.getenv("DATAFORSEO_LOGIN")
            password = os.getenv("DATAFORSEO_PASSWORD")
            if not login or not password:
                return {
                    "success": False,
                    "status": "not_configured",
                    "message": "DataForSEO credentials not configured"
                }
            client = DataForSEOClient(login, password)
            # Test by getting location code (synchronous method)
            location_code = client.get_location_code("usa")
            # Test with a simple search query
            test_result = await client.serp_google_organic("test query", location_code=location_code, depth=1)
            if test_result.get("success"):
                return {
                    "success": True,
                    "status": "connected",
                    "message": f"DataForSEO is working. Location code for USA: {location_code}",
                    "test_result": {"location_code": location_code, "api_test": "passed"}
                }
            else:
                return {
                    "success": False,
                    "status": "error",
                    "message": f"DataForSEO test failed: {test_result.get('error')}",
                    "test_result": {"location_code": location_code, "api_test": "failed", "error": test_result.get("error")}
                }
        
        elif "gemini" in service_lower:
            from app.clients.gemini import GeminiClient
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                return {
                    "success": False,
                    "status": "not_configured",
                    "message": "Gemini API key not configured"
                }
            client = GeminiClient(api_key)
            # Test with a simple prompt
            result = await client.compose_email(
                domain="test.com",
                page_title="Test Page",
                page_snippet="Test snippet"
            )
            return {
                "success": True,
                "status": "connected",
                "message": "Gemini is working. Email composition test successful.",
                "test_result": {"subject": result.get("subject", ""), "body_preview": result.get("body", "")[:100]}
            }
        
        elif "gmail" in service_lower:
            from app.clients.gmail import GmailClient
            client_id = os.getenv("GMAIL_CLIENT_ID")
            client_secret = os.getenv("GMAIL_CLIENT_SECRET")
            refresh_token = os.getenv("GMAIL_REFRESH_TOKEN")
            if not all([client_id, client_secret, refresh_token]):
                return {
                    "success": False,
                    "status": "not_configured",
                    "message": "Gmail API credentials not fully configured"
                }
            client = GmailClient(client_id=client_id, client_secret=client_secret, refresh_token=refresh_token)
            # Test by refreshing token (which validates credentials)
            success = await client.refresh_access_token()
            if success:
                return {
                    "success": True,
                    "status": "connected",
                    "message": "Gmail API is working. Credentials are valid and token refresh successful.",
                    "test_result": {"token_refreshed": True}
                }
            else:
                return {
                    "success": False,
                    "status": "error",
                    "message": "Gmail API credentials are invalid or token refresh failed"
                }
        
        else:
            raise HTTPException(status_code=404, detail=f"Service '{service_name}' not found")
    
    except ImportError as e:
        logger.error(f"Failed to import service client: {e}", exc_info=True)
        return {
            "success": False,
            "status": "error",
            "message": f"Service client not available: {str(e)}"
        }
    except Exception as e:
        logger.error(f"Error testing {service_name}: {e}", exc_info=True)
        return {
            "success": False,
            "status": "error",
            "message": f"Test failed: {str(e)}"
        }


# Automation Settings Models
class AutomationSettings(BaseModel):
    """Request/Response model for automation settings"""
    enabled: bool = Field(False, description="Master switch for automation")
    automatic_scraper: bool = Field(False, description="Enable automatic scraping")
    locations: list[str] = Field(default_factory=list, description="Selected locations for scraping")
    categories: list[str] = Field(default_factory=list, description="Selected categories for scraping")
    keywords: Optional[str] = Field(None, description="Optional keywords for scraping")
    max_results: int = Field(100, ge=1, le=1000, description="Maximum results per scrape")


@router.get("/diagnostics/dataforseo")
async def get_dataforseo_diagnostics():
    """
    Get diagnostic information about DataForSEO API usage
    
    Returns:
        Diagnostic data including request counts, success rates, last request/response
    """
    try:
        from app.clients.dataforseo import DataForSEOClient
        
        login = os.getenv("DATAFORSEO_LOGIN")
        password = os.getenv("DATAFORSEO_PASSWORD")
        
        if not login or not password:
            return {
                "error": "DataForSEO not configured",
                "credentials_configured": False
            }
        
        client = DataForSEOClient(login, password)
        diagnostics = client.get_diagnostics()
        
        return {
            "success": True,
            "diagnostics": diagnostics,
            "payload_format": {
                "expected": {
                    "data": [{
                        "keyword": "string (required)",
                        "location_code": "integer (required)",
                        "language_code": "string (required, 2 chars)",
                        "depth": "integer (optional, 1-100)"
                    }]
                },
                "note": "Payload must be wrapped in 'data' array. No device/os fields."
            }
        }
    except Exception as e:
        logger.error(f"Error getting DataForSEO diagnostics: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/automation", response_model=AutomationSettings)
async def get_automation_settings(db: AsyncSession = Depends(get_db)):
    """
    Get current automation settings
    """
    try:
        result = await db.execute(
            select(Settings).where(Settings.key == "automation")
        )
        settings_row = result.scalar_one_or_none()
        
        if settings_row and settings_row.value:
            return AutomationSettings(**settings_row.value)
        else:
            # Return defaults
            return AutomationSettings()
    except Exception as e:
        logger.error(f"Error getting automation settings: {e}", exc_info=True)
        return AutomationSettings()


@router.post("/automation", response_model=AutomationSettings)
async def update_automation_settings(
    settings: AutomationSettings,
    db: AsyncSession = Depends(get_db)
):
    """
    Update automation settings
    """
    try:
        result = await db.execute(
            select(Settings).where(Settings.key == "automation")
        )
        settings_row = result.scalar_one_or_none()
        
        if settings_row:
            # Update existing
            settings_row.value = settings.dict()
            settings_row.updated_at = func.now()
        else:
            # Create new
            settings_row = Settings(
                key="automation",
                value=settings.dict()
            )
            db.add(settings_row)
        
        await db.commit()
        await db.refresh(settings_row)
        
        return AutomationSettings(**settings_row.value)
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating automation settings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update settings: {str(e)}")

