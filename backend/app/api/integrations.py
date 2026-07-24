"""
Social Integrations API

Manages OAuth connections and capability detection for social media platforms.
Supports Instagram, Facebook, TikTok, and Email (SMTP).

CRITICAL DESIGN PRINCIPLES:
1. Never store raw API keys when OAuth is required
2. Encrypt all tokens at rest
3. Validate tokens before allowing actions
4. Fail fast with clear error messages
5. Capability detection is platform-specific and realistic
6. Discovery works without integrations, outreach requires valid integrations
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field, validator
import logging
import os
import httpx
from urllib.parse import urlencode

from app.db.database import get_db
from app.models.social_integration import SocialIntegration, Platform, ConnectionStatus
from app.utils.encryption import encrypt_token, decrypt_token, mask_token
from app.api.auth import get_current_user_optional  # Adjust based on your auth system

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations", tags=["integrations"])


# ============================================================================
# Pydantic Models
# ============================================================================

class IntegrationResponse(BaseModel):
    """Response model for integration (tokens are masked)"""
    id: str
    platform: str
    connection_status: str
    scopes_granted: Optional[List[str]] = None
    account_id: Optional[str] = None
    page_id: Optional[str] = None
    business_id: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    last_verified_at: Optional[datetime] = None
    email_address: Optional[str] = None  # For email integrations
    smtp_host: Optional[str] = None  # For email integrations
    smtp_port: Optional[int] = None  # For email integrations
    is_connected: bool
    platform_metadata: Optional[Dict[str, Any]] = None  # Renamed from 'metadata' (reserved in SQLAlchemy)
    
    class Config:
        from_attributes = True


class IntegrationCreate(BaseModel):
    """Request model for creating/updating integration"""
    platform: str = Field(..., description="Platform: instagram, facebook, tiktok, or email")
    # OAuth fields (for Instagram/Facebook)
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    scopes_granted: Optional[List[str]] = None
    account_id: Optional[str] = None
    page_id: Optional[str] = None
    business_id: Optional[str] = None
    # Email fields (for SMTP)
    email_address: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    
    @validator('platform')
    def validate_platform(cls, v):
        valid_platforms = ['instagram', 'facebook', 'tiktok', 'email']
        if v.lower() not in valid_platforms:
            raise ValueError(f"Platform must be one of: {valid_platforms}")
        return v.lower()


class CapabilityResponse(BaseModel):
    """Response model for platform capabilities"""
    platform: str
    is_connected: bool
    connection_status: str
    can_send_dm: bool
    can_discover: bool
    can_read_messages: bool
    reason: Optional[str] = None  # Explanation if capabilities are limited
    scopes_granted: Optional[List[str]] = None
    token_expires_at: Optional[datetime] = None


class OAuthCallbackRequest(BaseModel):
    """Request model for OAuth callback"""
    code: str
    state: Optional[str] = None
    platform: str


class ApiKeyRequest(BaseModel):
    """Request model for API key storage"""
    user_id: str
    api_key: str


# ============================================================================
# Helper Functions
# ============================================================================

async def get_integration_for_user(
    db: AsyncSession,
    user_id: str,
    platform: str
) -> Optional[SocialIntegration]:
    """Get integration for user and platform"""
    result = await db.execute(
        select(SocialIntegration).where(
            and_(
                SocialIntegration.user_id == user_id,
                SocialIntegration.platform == platform
            )
        )
    )
    return result.scalar_one_or_none()


async def validate_token_with_platform(
    integration: SocialIntegration
) -> tuple[bool, Optional[str]]:
    """
    Validate token with platform API.
    
    Returns:
        (is_valid, error_message)
    """
    try:
        if integration.platform == Platform.INSTAGRAM.value:
            return await _validate_instagram_token(integration)
        elif integration.platform == Platform.FACEBOOK.value:
            return await _validate_facebook_token(integration)
        elif integration.platform == Platform.TIKTOK.value:
            # TikTok doesn't have official DM API - always return unsupported
            return False, "TikTok does not provide an official DM API"
        elif integration.platform == Platform.EMAIL.value:
            return await _validate_email_smtp(integration)
        else:
            return False, f"Unknown platform: {integration.platform}"
    except Exception as e:
        logger.error(f"Token validation error for {integration.platform}: {e}", exc_info=True)
        return False, str(e)


async def _validate_instagram_token(integration: SocialIntegration) -> tuple[bool, Optional[str]]:
    """Validate Instagram token via Meta Graph API"""
    try:
        # Check if token is expired - try to refresh if we have refresh token
        if integration.is_token_expired():
            if integration.refresh_token:
                # Try to refresh the token
                refreshed = await _refresh_meta_token(integration)
                if refreshed:
                    return True, None
                else:
                    return False, "Token expired and refresh failed"
            else:
                return False, "Token has expired and no refresh token available"
        
        # Decrypt token
        access_token = decrypt_token(integration.access_token)
        
        # Validate token by making a debug API call
        debug_url = f"https://graph.facebook.com/v18.0/debug_token"
        debug_params = {
            "input_token": access_token,
            "access_token": access_token
        }
        
        async with httpx.AsyncClient() as client:
            debug_response = await client.get(debug_url, params=debug_params, timeout=10.0)
            debug_response.raise_for_status()
            debug_data = debug_response.json()
        
        # Check if token is valid
        data = debug_data.get("data", {})
        is_valid = data.get("is_valid", False)
        
        if not is_valid:
            error_msg = data.get("error", {}).get("message", "Token is invalid")
            return False, error_msg
        
        return True, None
        
    except ValueError as e:
        # Decryption failed
        return False, f"Token decryption failed: {e}"
    except httpx.HTTPStatusError as e:
        return False, f"Token validation API error: {e.response.text if hasattr(e, 'response') else str(e)}"
    except Exception as e:
        return False, f"Token validation failed: {e}"


async def _validate_facebook_token(integration: SocialIntegration) -> tuple[bool, Optional[str]]:
    """Validate Facebook token via Meta Graph API"""
    try:
        # Check if token is expired - try to refresh if we have refresh token
        if integration.is_token_expired():
            if integration.refresh_token:
                # Try to refresh the token
                refreshed = await _refresh_meta_token(integration)
                if refreshed:
                    return True, None
                else:
                    return False, "Token expired and refresh failed"
            else:
                return False, "Token has expired and no refresh token available"
        
        # Decrypt token
        access_token = decrypt_token(integration.access_token)
        
        # Validate token by making a debug API call
        debug_url = f"https://graph.facebook.com/v18.0/debug_token"
        debug_params = {
            "input_token": access_token,
            "access_token": access_token
        }
        
        async with httpx.AsyncClient() as client:
            debug_response = await client.get(debug_url, params=debug_params, timeout=10.0)
            debug_response.raise_for_status()
            debug_data = debug_response.json()
        
        # Check if token is valid
        data = debug_data.get("data", {})
        is_valid = data.get("is_valid", False)
        
        if not is_valid:
            error_msg = data.get("error", {}).get("message", "Token is invalid")
            return False, error_msg
        
        return True, None
        
    except ValueError as e:
        return False, f"Token decryption failed: {e}"
    except httpx.HTTPStatusError as e:
        return False, f"Token validation API error: {e.response.text if hasattr(e, 'response') else str(e)}"
    except Exception as e:
        return False, f"Token validation failed: {e}"


async def _validate_email_smtp(integration: SocialIntegration) -> tuple[bool, Optional[str]]:
    """Validate SMTP configuration by attempting connection"""
    try:
        import smtplib
        from email.mime.text import MIMEText
        
        if not all([integration.smtp_host, integration.smtp_port, integration.smtp_username, integration.smtp_password]):
            return False, "SMTP configuration incomplete"
        
        # Decrypt password
        password = decrypt_token(integration.smtp_password)
        
        # Test SMTP connection
        if integration.smtp_port == 465:
            # SSL connection
            server = smtplib.SMTP_SSL(integration.smtp_host, integration.smtp_port, timeout=10)
        else:
            # TLS connection
            server = smtplib.SMTP(integration.smtp_host, integration.smtp_port, timeout=10)
            server.starttls()
        
        server.login(integration.smtp_username, password)
        server.quit()
        
        return True, None
        
    except smtplib.SMTPAuthenticationError:
        return False, "SMTP authentication failed - check username and password"
    except smtplib.SMTPConnectError:
        return False, f"Could not connect to SMTP server {integration.smtp_host}:{integration.smtp_port}"
    except Exception as e:
        return False, f"SMTP validation failed: {e}"


def detect_capabilities(integration: Optional[SocialIntegration]) -> Dict[str, Any]:
    """
    Detect platform-specific capabilities based on integration status and scopes.
    
    CRITICAL: This function returns REALISTIC capabilities, not optimistic ones.
    If a platform doesn't support DM, it returns can_send_dm=False with clear reason.
    """
    if not integration or not integration.is_connected():
        return {
            "is_connected": False,
            "connection_status": integration.connection_status.value if integration and integration.connection_status else "not_connected",
            "can_send_dm": False,
            "can_discover": True,  # Discovery works without integrations
            "can_read_messages": False,
            "reason": "Integration not connected or token expired",
            "scopes_granted": None,
            "token_expires_at": None,
        }
    
    platform = integration.platform
    scopes = integration.scopes_granted or []
    
    capabilities = {
        "is_connected": True,
        "connection_status": integration.connection_status.value if hasattr(integration.connection_status, 'value') else str(integration.connection_status),
        "can_discover": True,  # Discovery always works
        "scopes_granted": scopes,
        "token_expires_at": integration.token_expires_at,
    }
    
    # Platform-specific capability detection
    if platform == Platform.INSTAGRAM.value:
        # Instagram: Can send DMs ONLY if:
        # 1. Business or Creator account (not personal)
        # 2. Has instagram_manage_messages scope
        # 3. Account is connected to a Facebook Page
        has_message_scope = "instagram_manage_messages" in scopes
        has_business_account = integration.business_id is not None
        
        capabilities["can_send_dm"] = has_message_scope and has_business_account
        capabilities["can_read_messages"] = has_message_scope
        
        if not capabilities["can_send_dm"]:
            if not has_message_scope:
                capabilities["reason"] = "Missing 'instagram_manage_messages' scope. Reconnect with proper permissions."
            elif not has_business_account:
                capabilities["reason"] = "Instagram account must be a Business or Creator account connected to a Facebook Page."
            else:
                capabilities["reason"] = "Instagram DM capability unavailable"
    
    elif platform == Platform.FACEBOOK.value:
        # Facebook: Can send messages via Messenger API ONLY if:
        # 1. Has pages_messaging scope
        # 2. Page is connected
        # 3. User has previously messaged the page (for most use cases)
        has_messaging_scope = "pages_messaging" in scopes
        has_page = integration.page_id is not None
        
        capabilities["can_send_dm"] = has_messaging_scope and has_page
        capabilities["can_read_messages"] = has_messaging_scope
        
        if not capabilities["can_send_dm"]:
            if not has_messaging_scope:
                capabilities["reason"] = "Missing 'pages_messaging' scope. Reconnect with proper permissions."
            elif not has_page:
                capabilities["reason"] = "Facebook Page not connected. Connect a Page to enable messaging."
            else:
                capabilities["reason"] = "Facebook Messenger capability unavailable"
    
    elif platform == Platform.TIKTOK.value:
        # TikTok: NO official DM API exists
        # This is explicitly documented - TikTok does not provide messaging APIs
        capabilities["can_send_dm"] = False
        capabilities["can_read_messages"] = False
        capabilities["reason"] = (
            "TikTok does not provide an official Direct Message API. "
            "Messaging is not supported through the TikTok platform API."
        )
    
    elif platform == Platform.EMAIL.value:
        # Email: Can send if SMTP is configured and validated
        has_smtp = all([
            integration.smtp_host,
            integration.smtp_port,
            integration.smtp_username,
            integration.smtp_password
        ])
        
        capabilities["can_send_dm"] = has_smtp  # Email "DM" = sending email
        capabilities["can_read_messages"] = False  # Email reading requires IMAP, not implemented
        
        if not capabilities["can_send_dm"]:
            capabilities["reason"] = "SMTP configuration incomplete or invalid"
    
    else:
        capabilities["can_send_dm"] = False
        capabilities["can_read_messages"] = False
        capabilities["reason"] = f"Unknown platform: {platform}"
    
    return capabilities


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/", response_model=List[IntegrationResponse])
async def list_integrations(
    user_id: str = Query(..., description="User ID"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    List all integrations for a user.
    
    Returns integrations with masked tokens (for security).
    """
    result = await db.execute(
        select(SocialIntegration).where(SocialIntegration.user_id == user_id)
    )
    integrations = result.scalars().all()
    
    # Convert to response models (tokens are already encrypted in DB, we just don't return them)
    return [
        IntegrationResponse(
            id=str(integration.id),
            platform=integration.platform,
            connection_status=integration.connection_status,
            scopes_granted=integration.scopes_granted,
            account_id=integration.account_id,
            page_id=integration.page_id,
            business_id=integration.business_id,
            token_expires_at=integration.token_expires_at,
            last_verified_at=integration.last_verified_at,
            email_address=integration.email_address,
            smtp_host=integration.smtp_host,
            smtp_port=integration.smtp_port,
            is_connected=integration.is_connected(),
            platform_metadata=integration.platform_metadata,
        )
        for integration in integrations
    ]


@router.get("/capabilities", response_model=List[CapabilityResponse])
async def get_capabilities(
    user_id: str = Query(..., description="User ID"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Get capabilities for all platforms.
    
    This endpoint is CRITICAL for frontend - it determines which buttons to enable/disable.
    Returns realistic capabilities based on actual integration status and platform limitations.
    """
    # Get all integrations for user
    result = await db.execute(
        select(SocialIntegration).where(SocialIntegration.user_id == user_id)
    )
    integrations = result.scalars().all()
    
    # Create a map of platform -> integration
    integration_map = {intg.platform: intg for intg in integrations}
    
    # Check all platforms
    capabilities_list = []
    for platform in Platform:
        integration = integration_map.get(platform.value)
        caps = detect_capabilities(integration)
        caps["platform"] = platform.value
        
        capabilities_list.append(CapabilityResponse(**caps))
    
    return capabilities_list


@router.get("/{platform}/capabilities", response_model=CapabilityResponse)
async def get_platform_capabilities(
    platform: str,
    user_id: str = Query(..., description="User ID"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Get capabilities for a specific platform.
    """
    if platform not in [p.value for p in Platform]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid platform. Must be one of: {[p.value for p in Platform]}"
        )
    
    integration = await get_integration_for_user(db, user_id, platform)
    caps = detect_capabilities(integration)
    caps["platform"] = platform
    
    return CapabilityResponse(**caps)


@router.post("/", response_model=IntegrationResponse, status_code=status.HTTP_201_CREATED)
async def create_integration(
    integration_data: IntegrationCreate,
    user_id: str = Query(..., description="User ID"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Create or update a social integration.
    
    CRITICAL: This endpoint validates tokens before saving.
    If validation fails, returns 400 with clear error message.
    """
    # Check if integration already exists
    existing = await get_integration_for_user(db, user_id, integration_data.platform)
    
    if existing:
        # Update existing
        integration = existing
    else:
        # Create new
        integration = SocialIntegration(
            user_id=user_id,
            platform=integration_data.platform,
        )
        db.add(integration)
    
    # Update fields
    if integration_data.platform in [Platform.INSTAGRAM.value, Platform.FACEBOOK.value]:
        # OAuth platforms
        if integration_data.access_token:
            integration.access_token = encrypt_token(integration_data.access_token)
        if integration_data.refresh_token:
            integration.refresh_token = encrypt_token(integration_data.refresh_token)
        if integration_data.token_expires_at:
            integration.token_expires_at = integration_data.token_expires_at
        if integration_data.scopes_granted:
            integration.scopes_granted = integration_data.scopes_granted
        if integration_data.account_id:
            integration.account_id = integration_data.account_id
        if integration_data.page_id:
            integration.page_id = integration_data.page_id
        if integration_data.business_id:
            integration.business_id = integration_data.business_id
    
    elif integration_data.platform == Platform.EMAIL.value:
        # Email/SMTP
        if integration_data.email_address:
            integration.email_address = integration_data.email_address
        if integration_data.smtp_host:
            integration.smtp_host = integration_data.smtp_host
        if integration_data.smtp_port:
            integration.smtp_port = integration_data.smtp_port
        if integration_data.smtp_username:
            integration.smtp_username = integration_data.smtp_username
        if integration_data.smtp_password:
            integration.smtp_password = encrypt_token(integration_data.smtp_password)
    
    # Validate token/configuration before saving
    is_valid, error_msg = await validate_token_with_platform(integration)
    
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Integration validation failed: {error_msg}"
        )
    
    # Update status and verification time
    integration.connection_status = ConnectionStatus.CONNECTED.value
    integration.last_verified_at = datetime.now(timezone.utc)
    
    await db.commit()
    await db.refresh(integration)
    
    return IntegrationResponse(
        id=str(integration.id),
        platform=integration.platform,
        connection_status=integration.connection_status,
        scopes_granted=integration.scopes_granted,
        account_id=integration.account_id,
        page_id=integration.page_id,
        business_id=integration.business_id,
        token_expires_at=integration.token_expires_at,
        last_verified_at=integration.last_verified_at,
        email_address=integration.email_address,
        smtp_host=integration.smtp_host,
        smtp_port=integration.smtp_port,
        is_connected=integration.is_connected(),
        metadata=integration.metadata,
    )


@router.post("/{platform}/validate", status_code=status.HTTP_200_OK)
async def validate_integration(
    platform: str,
    user_id: str = Query(..., description="User ID"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Validate an existing integration's token/configuration.
    
    Updates connection_status and last_verified_at based on validation result.
    """
    integration = await get_integration_for_user(db, user_id, platform)
    
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No integration found for platform: {platform}"
        )
    
    is_valid, error_msg = await validate_token_with_platform(integration)
    
    if is_valid:
        integration.connection_status = ConnectionStatus.CONNECTED.value
        integration.last_verified_at = datetime.now(timezone.utc)
    else:
        if integration.is_token_expired():
            integration.connection_status = ConnectionStatus.EXPIRED.value
        else:
            integration.connection_status = ConnectionStatus.ERROR.value
        if integration.platform_metadata is None:
            integration.platform_metadata = {}
        integration.platform_metadata["last_validation_error"] = error_msg
    
    await db.commit()
    
    return {
        "is_valid": is_valid,
        "error_message": error_msg,
        "connection_status": integration.connection_status,
        "last_verified_at": integration.last_verified_at,
    }


@router.post("/{platform}/api-key", response_model=IntegrationResponse)
async def save_api_key(
    platform: str,
    request: ApiKeyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Save API key/token for a platform (simple approach, no OAuth).
    Stores the API key encrypted in access_token field.
    """
    if platform not in [Platform.INSTAGRAM.value, Platform.FACEBOOK.value, Platform.TIKTOK.value]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"API key storage not supported for platform: {platform}"
        )
    
    user_id = request.user_id
    api_key = request.api_key
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="api_key is required"
        )
    
    logger.info(f"🔑 [API KEY] Saving API key for {platform} (user: {user_id})")
    
    # Get or create integration
    integration = await get_integration_for_user(db, user_id, platform)
    
    if not integration:
        integration = SocialIntegration(
            user_id=user_id,
            platform=platform,
        )
        db.add(integration)
    
    # Encrypt and store API key in access_token field
    integration.access_token = encrypt_token(api_key)
    integration.connection_status = ConnectionStatus.CONNECTED.value
    integration.last_verified_at = datetime.now(timezone.utc)
    
    # For API keys, we don't have expiry info, so set token_expires_at to None
    # (or set a far future date if you want to track it)
    integration.token_expires_at = None
    
    # Clear OAuth-specific fields since this is API key-based
    integration.scopes_granted = None
    integration.account_id = None
    integration.page_id = None
    integration.business_id = None
    
    # Update metadata to indicate this is API key-based
    if integration.platform_metadata is None:
        integration.platform_metadata = {}
    integration.platform_metadata["auth_method"] = "api_key"
    integration.platform_metadata["saved_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.commit()
    await db.refresh(integration)
    
    logger.info(f"✅ [API KEY] Successfully saved API key for {platform} (user: {user_id})")
    
    return IntegrationResponse(
        id=str(integration.id),
        platform=integration.platform,
        connection_status=integration.connection_status,
        scopes_granted=integration.scopes_granted,
        account_id=integration.account_id,
        page_id=integration.page_id,
        business_id=integration.business_id,
        token_expires_at=integration.token_expires_at,
        last_verified_at=integration.last_verified_at,
        is_connected=integration.is_connected(),
        metadata=integration.metadata,
    )


@router.delete("/{platform}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_integration(
    platform: str,
    user_id: str = Query(..., description="User ID"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """Delete an integration"""
    integration = await get_integration_for_user(db, user_id, platform)
    
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No integration found for platform: {platform}"
        )
    
    await db.delete(integration)
    await db.commit()
    
    return None


# ============================================================================
# OAuth Flow Endpoints (Placeholder - implement based on your OAuth provider)
# ============================================================================

@router.get("/oauth/{platform}/authorize")
async def oauth_authorize(
    platform: str,
    user_id: str = Query(..., description="User ID"),
    redirect_uri: str = Query(..., description="OAuth redirect URI")
):
    """
    Generate OAuth authorization URL for platform.
    
    Returns URL that user should be redirected to for OAuth consent.
    """
    if platform not in [Platform.INSTAGRAM.value, Platform.FACEBOOK.value]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth not supported for platform: {platform}"
        )
    
    # TODO: Implement OAuth URL generation
    # For Instagram/Facebook, use Meta Graph API OAuth
    # Example: https://www.facebook.com/v18.0/dialog/oauth?client_id=...&redirect_uri=...&scope=...
    
    client_id = os.getenv(f"{platform.upper()}_CLIENT_ID")
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"{platform.upper()}_CLIENT_ID not configured"
        )
    
    # Build OAuth URL
    scopes = {
        Platform.INSTAGRAM.value: "instagram_basic,instagram_manage_messages,pages_show_list",
        Platform.FACEBOOK.value: "pages_messaging,pages_show_list",
    }.get(platform, "")
    
    oauth_url = (
        f"https://www.facebook.com/v18.0/dialog/oauth?"
        f"client_id={client_id}&"
        f"redirect_uri={redirect_uri}&"
        f"scope={scopes}&"
        f"state={user_id}"  # Use user_id as state for security
    )
    
    return {"authorization_url": oauth_url}


@router.post("/oauth/{platform}/callback")
async def oauth_callback(
    platform: str,
    callback_data: OAuthCallbackRequest,
    user_id: str = Query(..., description="User ID"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    """
    Handle OAuth callback and exchange code for tokens.
    
    This endpoint receives the OAuth callback, exchanges the code for tokens,
    validates them, and saves the integration.
    """
    if platform not in [Platform.INSTAGRAM.value, Platform.FACEBOOK.value]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth not supported for platform: {platform}"
        )
    
    try:
        # Get OAuth credentials from environment
        client_id = os.getenv(f"{platform.upper()}_CLIENT_ID")
        client_secret = os.getenv(f"{platform.upper()}_CLIENT_SECRET")
        redirect_uri = os.getenv(f"{platform.upper()}_REDIRECT_URI", "http://localhost:3000/settings")
        
        if not client_id or not client_secret:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"{platform.upper()}_CLIENT_ID and {platform.upper()}_CLIENT_SECRET must be configured"
            )
        
        # Step 1: Exchange authorization code for access token
        token_url = "https://graph.facebook.com/v18.0/oauth/access_token"
        token_params = {
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "code": callback_data.code
        }
        
        async with httpx.AsyncClient() as client:
            token_response = await client.get(token_url, params=token_params)
            token_response.raise_for_status()
            token_data = token_response.json()
        
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to obtain access token from OAuth provider"
            )
        
        expires_in = token_data.get("expires_in", 0)  # Seconds until expiry
        token_expires_at = None
        if expires_in:
            token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        
        # Step 2: Get user info and granted scopes
        # For Meta Graph API, we need to:
        # - Get the user's pages (for Facebook)
        # - Get the Instagram Business Account (for Instagram)
        # - Extract granted scopes from the token
        
        # Get debug token info to extract scopes
        debug_url = f"https://graph.facebook.com/v18.0/debug_token"
        debug_params = {
            "input_token": access_token,
            "access_token": access_token
        }
        
        async with httpx.AsyncClient() as client:
            debug_response = await client.get(debug_url, params=debug_params)
            debug_response.raise_for_status()
            debug_data = debug_response.json()
        
        scopes_granted = debug_data.get("data", {}).get("scopes", [])
        
        # Step 3: Get user/account info
        account_id = None
        page_id = None
        business_id = None
        
        if platform == Platform.FACEBOOK.value:
            # Get user's pages
            pages_url = f"https://graph.facebook.com/v18.0/me/accounts"
            pages_params = {"access_token": access_token}
            
            async with httpx.AsyncClient() as client:
                pages_response = await client.get(pages_url, params=pages_params)
                if pages_response.status_code == 200:
                    pages_data = pages_response.json()
                    pages = pages_data.get("data", [])
                    if pages:
                        # Use first page
                        page_id = pages[0].get("id")
                        account_id = pages[0].get("id")
        
        elif platform == Platform.INSTAGRAM.value:
            # Get Instagram Business Account
            # First, get pages to find connected Instagram account
            pages_url = f"https://graph.facebook.com/v18.0/me/accounts"
            pages_params = {"access_token": access_token, "fields": "instagram_business_account"}
            
            async with httpx.AsyncClient() as client:
                pages_response = await client.get(pages_url, params=pages_params)
                if pages_response.status_code == 200:
                    pages_data = pages_response.json()
                    pages = pages_data.get("data", [])
                    for page in pages:
                        instagram_account = page.get("instagram_business_account")
                        if instagram_account:
                            account_id = instagram_account.get("id")
                            page_id = page.get("id")
                            business_id = page.get("id")
                            break
        
        # Step 4: Create or update integration
        integration = await get_integration_for_user(db, user_id, platform)
        
        if not integration:
            integration = SocialIntegration(
                user_id=user_id,
                platform=platform,
            )
            db.add(integration)
        
        # Update integration fields
        integration.access_token = encrypt_token(access_token)
        integration.token_expires_at = token_expires_at
        integration.scopes_granted = scopes_granted
        integration.account_id = account_id
        integration.page_id = page_id
        integration.business_id = business_id
        integration.connection_status = ConnectionStatus.CONNECTED.value
        integration.last_verified_at = datetime.now(timezone.utc)
        
        # Step 5: Validate token
        is_valid, error_msg = await validate_token_with_platform(integration)
        
        if not is_valid:
            integration.connection_status = ConnectionStatus.ERROR.value
            if integration.platform_metadata is None:
                integration.platform_metadata = {}
            integration.platform_metadata["validation_error"] = error_msg
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Token validation failed: {error_msg}"
            )
        
        await db.commit()
        await db.refresh(integration)
        
        logger.info(f"✅ [OAUTH CALLBACK] Successfully connected {platform} for user {user_id}")
        
        return IntegrationResponse(
            id=str(integration.id),
            platform=integration.platform,
            connection_status=integration.connection_status,
            scopes_granted=integration.scopes_granted,
            account_id=integration.account_id,
            page_id=integration.page_id,
            business_id=integration.business_id,
            token_expires_at=integration.token_expires_at,
            last_verified_at=integration.last_verified_at,
            is_connected=integration.is_connected(),
            platform_metadata=integration.platform_metadata,
        )
        
    except httpx.HTTPStatusError as e:
        logger.error(f"❌ [OAUTH CALLBACK] HTTP error during OAuth callback: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth provider error: {e.response.text if hasattr(e, 'response') else str(e)}"
        )
    except Exception as e:
        logger.error(f"❌ [OAUTH CALLBACK] Error during OAuth callback: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OAuth callback failed: {str(e)}"
        )

