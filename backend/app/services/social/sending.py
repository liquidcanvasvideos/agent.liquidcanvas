"""
Social Outreach Message Sending Service

Sends messages via platform-specific APIs.
Completely separate from website email sending.
"""
import logging
import asyncio
import os
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.social import (
    SocialProfile,
    SocialMessage,
    SocialPlatform,
    MessageType,
    MessageStatus,
    OutreachStatus,
)

logger = logging.getLogger(__name__)


class SocialSendingService:
    """
    Service for sending social media messages.
    
    Platform-specific sending with:
    - Rate limiting per platform
    - Error handling and retries
    - Message status tracking
    - Delivery confirmation
    """
    
    def __init__(self):
        # Rate limiting: messages per minute per platform
        self.rate_limits = {
            SocialPlatform.LINKEDIN.value: {"max_per_minute": 10, "delay_seconds": 6},
            SocialPlatform.INSTAGRAM.value: {"max_per_minute": 5, "delay_seconds": 12},
            SocialPlatform.TIKTOK.value: {"max_per_minute": 5, "delay_seconds": 12},
            SocialPlatform.FACEBOOK.value: {"max_per_minute": 10, "delay_seconds": 6},
        }
        
        # Track last send time per platform for rate limiting
        self.last_send_times = {}
        self.send_counts = {}  # Count of sends in current minute window
    
    async def send_message(
        self,
        profile: Any,  # Can be SocialProfile or Prospect
        draft_body: str,
        db: AsyncSession,
        retry_count: int = 0,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Send a message to a social profile or prospect.
        
        Args:
            profile: Social profile or Prospect to send to
            draft_body: Message body to send
            db: Database session
            retry_count: Current retry attempt
            max_retries: Maximum retry attempts
        
        Returns:
            Dict with 'success', 'message_id', 'error', 'status'
        """
        # Determine platform and username from either model
        if hasattr(profile, 'platform') and hasattr(profile.platform, 'value'):
            platform = profile.platform.value
        elif hasattr(profile, 'source_platform'):
            platform = profile.source_platform
        else:
            platform = "unknown"

        username = getattr(profile, 'username', 'unknown')
        profile_id = profile.id if not hasattr(profile, 'source_type') else None
        
        logger.info(f"📤 [SOCIAL SENDING] Sending {platform} message to @{username} (attempt {retry_count + 1})")
        
        # Rate limiting
        await self._apply_rate_limit(platform)
        
        try:
            # Platform-specific sending
            send_result = await self._send_platform_message(platform, profile, draft_body)
            
            if send_result.get("success"):
                # Create message record
                message = SocialMessage(
                    profile_id=profile_id,
                    # If it's a Prospect (source_type exists), we don't have a direct link to SocialProfile yet
                    # in this specific message model, but we can store the platform
                    platform=platform,
                    message_type=MessageType.INITIAL.value if retry_count == 0 else MessageType.FOLLOWUP.value,
                    draft_body=draft_body,
                    sent_body=send_result.get("sent_body", draft_body),
                    status=MessageStatus.SENT.value,
                    sent_at=datetime.now(timezone.utc),
                    thread_id=send_result.get("thread_id")
                )
                
                db.add(message)
                
                # Update profile status
                if hasattr(profile, 'outreach_status'):
                    profile.outreach_status = OutreachStatus.SENT.value
                elif hasattr(profile, 'send_status'):
                    from app.models.prospect import SendStatus
                    profile.send_status = SendStatus.SENT.value
                
                if hasattr(profile, 'last_contacted_at'):
                    profile.last_contacted_at = datetime.now(timezone.utc)
                elif hasattr(profile, 'last_sent'):
                    profile.last_sent = datetime.now(timezone.utc)
                
                await db.commit()
                
                logger.info(f"✅ [SOCIAL SENDING] Message sent to @{username} (message_id: {message.id})")
                
                return {
                    "success": True,
                    "message_id": str(message.id),
                    "status": MessageStatus.SENT.value,
                    "error": None
                }
            else:
                error = send_result.get("error", "Unknown error")
                logger.warning(f"⚠️  [SOCIAL SENDING] Failed to send to @{username}: {error}")
                
                # Retry logic
                if retry_count < max_retries:
                    retry_delay = (retry_count + 1) * 5  # Exponential backoff: 5s, 10s, 15s
                    logger.info(f"🔄 [SOCIAL SENDING] Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                    return await self.send_message(profile, draft_body, db, retry_count + 1, max_retries)
                else:
                    # Max retries reached - mark as failed
                    message = SocialMessage(
                        profile_id=profile_id,
                        platform=platform,
                        message_type=MessageType.INITIAL.value,
                        draft_body=draft_body,
                        sent_body=None,
                        status=MessageStatus.FAILED.value,
                        sent_at=None
                    )
                    
                    db.add(message)
                    await db.commit()
                    
                    return {
                        "success": False,
                        "message_id": str(message.id),
                        "status": MessageStatus.FAILED.value,
                        "error": error
                    }
        
        except Exception as e:
            logger.error(f"❌ [SOCIAL SENDING] Exception sending to @{username}: {e}", exc_info=True)
            
            # Retry on exception
            if retry_count < max_retries:
                retry_delay = (retry_count + 1) * 5
                logger.info(f"🔄 [SOCIAL SENDING] Retrying after exception in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
                return await self.send_message(profile, draft_body, db, retry_count + 1, max_retries)
            else:
                # Mark as failed
                message = SocialMessage(
                    profile_id=profile_id,
                    platform=platform,
                    message_type=MessageType.INITIAL.value,
                    draft_body=draft_body,
                    sent_body=None,
                    status=MessageStatus.FAILED.value,
                    sent_at=None
                )
                
                db.add(message)
                await db.commit()
                
                return {
                    "success": False,
                    "message_id": str(message.id),
                    "status": MessageStatus.FAILED.value,
                    "error": str(e)
                }
    
    async def _send_platform_message(
        self,
        platform: str,
        profile: Any,
        message_body: str
    ) -> Dict[str, Any]:
        """
        Send message via platform-specific API.
        
        Args:
            platform: Platform name
            profile: Social profile or Prospect
            message_body: Message to send
        
        Returns:
            Dict with 'success', 'sent_body', 'thread_id', 'error'
        """
        username = getattr(profile, 'username', 'unknown')
        profile_url = getattr(profile, 'profile_url', 'unknown')
        logger.info(f"🔌 [SOCIAL SENDING] Platform API integration for {platform}...")
        logger.info(f"   Would send to: @{username}")
        logger.info(f"   Message: {message_body[:100]}...")
        
        # Simulate API call delay
        await asyncio.sleep(1)
        
        # REAL IMPLEMENTATION LOGIC
        try:
            if platform == SocialPlatform.LINKEDIN.value:
                # LinkedIn requires specialized connection/messaging flow
                # For now, we simulate success if configured
                return await self._send_linkedin_message(profile, message_body)
            elif platform == SocialPlatform.INSTAGRAM.value:
                return await self._send_instagram_message(profile, message_body)
            elif platform == SocialPlatform.FACEBOOK.value:
                return await self._send_facebook_message(profile, message_body)
            elif platform == SocialPlatform.TIKTOK.value:
                return await self._send_tiktok_message(profile, message_body)
            else:
                return {"success": False, "error": f"Unsupported platform: {platform}"}
        except Exception as e:
            logger.error(f"❌ [SOCIAL SENDING] API error for {platform}: {e}")
            return {"success": False, "error": str(e)}

    async def _send_linkedin_message(self, profile: Any, message: str) -> Dict[str, Any]:
        """LinkedIn specialized connection/message logic"""
        try:
            from app.clients.linkedin import LinkedInClient
            client = LinkedInClient()
            
            # Since LinkedIn often requires a connection first, we attempt a connection request with a note
            # or a direct message if already connected (handled by the client)
            success = await client.send_connection_with_note(
                profile_url=profile.profile_url,
                note=message
            )
            
            if success:
                return {"success": True, "sent_body": message, "thread_id": f"li_{profile.id}"}
            return {"success": False, "error": "LinkedIn client failed to send message/connection"}
        except Exception as e:
            logger.error(f"❌ [SOCIAL SENDING] LinkedIn API error: {e}")
            return {"success": False, "error": str(e)}

    async def _send_instagram_message(self, profile: Any, message: str) -> Dict[str, Any]:
        """Instagram Graph API DM logic"""
        try:
            if os.getenv("SOCIAL_SENDING_PROVIDER", "api").lower() == "selenium" or os.getenv("SOCIAL_USE_SELENIUM", "").strip().lower() in {"1", "true", "yes", "y", "on"}:
                from app.services.social.selenium_sender import send_instagram_dm
                selenium_timeout = int(os.getenv("SOCIAL_SELENIUM_SEND_TIMEOUT_SECONDS", "180"))
                if selenium_timeout > 0:
                    try:
                        return await asyncio.wait_for(
                            asyncio.to_thread(send_instagram_dm, profile, message),
                            timeout=selenium_timeout,
                        )
                    except asyncio.TimeoutError:
                        return {
                            "success": False,
                            "error": f"Selenium Instagram send timed out after {selenium_timeout}s",
                        }
                return await asyncio.to_thread(send_instagram_dm, profile, message)

            from app.clients.instagram import InstagramClient
            client = InstagramClient()
            
            # Use the Instagram client to send a DM
            success = await client.send_dm(
                username=profile.username,
                message=message
            )
            
            if success:
                return {"success": True, "sent_body": message, "thread_id": f"ig_{profile.id}"}
            return {"success": False, "error": "Instagram client failed to send DM"}
        except Exception as e:
            logger.error(f"❌ [SOCIAL SENDING] Instagram API error: {e}")
            return {"success": False, "error": str(e)}

    async def _send_facebook_message(self, profile: Any, message: str) -> Dict[str, Any]:
        """Facebook Messenger API logic"""
        try:
            if os.getenv("SOCIAL_SENDING_PROVIDER", "api").lower() == "selenium" or os.getenv("SOCIAL_USE_SELENIUM", "").strip().lower() in {"1", "true", "yes", "y", "on"}:
                from app.services.social.selenium_sender import send_facebook_message
                selenium_timeout = int(os.getenv("SOCIAL_SELENIUM_SEND_TIMEOUT_SECONDS", "180"))
                if selenium_timeout > 0:
                    try:
                        return await asyncio.wait_for(
                            asyncio.to_thread(send_facebook_message, profile, message),
                            timeout=selenium_timeout,
                        )
                    except asyncio.TimeoutError:
                        return {
                            "success": False,
                            "error": f"Selenium Facebook send timed out after {selenium_timeout}s",
                        }
                return await asyncio.to_thread(send_facebook_message, profile, message)

            from app.clients.facebook import FacebookClient
            client = FacebookClient()
            
            # Use the Facebook client to send a message
            success = await client.send_message(
                profile_id=profile.username, # Or appropriate ID
                message=message
            )
            
            if success:
                return {"success": True, "sent_body": message, "thread_id": f"fb_{profile.id}"}
            return {"success": False, "error": "Facebook client failed to send message"}
        except Exception as e:
            logger.error(f"❌ [SOCIAL SENDING] Facebook API error: {e}")
            return {"success": False, "error": str(e)}

    async def _send_tiktok_message(self, profile: Any, message: str) -> Dict[str, Any]:
        """TikTok DM logic"""
        try:
            if os.getenv("SOCIAL_SENDING_PROVIDER", "api").lower() == "selenium" or os.getenv("SOCIAL_USE_SELENIUM", "").strip().lower() in {"1", "true", "yes", "y", "on"}:
                from app.services.social.selenium_sender import send_tiktok_dm
                selenium_timeout = int(os.getenv("SOCIAL_SELENIUM_SEND_TIMEOUT_SECONDS", "180"))
                if selenium_timeout > 0:
                    try:
                        return await asyncio.wait_for(
                            asyncio.to_thread(send_tiktok_dm, profile, message),
                            timeout=selenium_timeout,
                        )
                    except asyncio.TimeoutError:
                        return {
                            "success": False,
                            "error": f"Selenium TikTok send timed out after {selenium_timeout}s",
                        }
                return await asyncio.to_thread(send_tiktok_dm, profile, message)

            from app.clients.tiktok import TikTokClient
            client = TikTokClient()
            
            # Use the TikTok client to send a DM
            success = await client.send_dm(
                username=profile.username,
                message=message
            )
            
            if success:
                return {"success": True, "sent_body": message, "thread_id": f"tt_{profile.id}"}
            return {"success": False, "error": "TikTok client failed to send DM"}
        except Exception as e:
            logger.error(f"❌ [SOCIAL SENDING] TikTok API error: {e}")
            return {"success": False, "error": str(e)}
    
    def _check_platform_api_config(self, platform: str) -> bool:
        """
        Check if platform API is configured.
        
        In production, this would check for:
        - API keys
        - OAuth tokens
        - API credentials
        
        Args:
            platform: Platform name
        
        Returns:
            True if API is configured, False otherwise
        """
        import os
        
        # Check for platform-specific environment variables
        platform_env_vars = {
            SocialPlatform.LINKEDIN.value: ["LINKEDIN_CLIENT_ID", "LINKEDIN_CLIENT_SECRET", "LINKEDIN_ACCESS_TOKEN"],
            SocialPlatform.INSTAGRAM.value: ["INSTAGRAM_APP_ID", "INSTAGRAM_APP_SECRET", "INSTAGRAM_ACCESS_TOKEN"],
            SocialPlatform.TIKTOK.value: ["TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "TIKTOK_ACCESS_TOKEN"],
            SocialPlatform.FACEBOOK.value: ["FACEBOOK_APP_ID", "FACEBOOK_APP_SECRET", "FACEBOOK_ACCESS_TOKEN"],
        }
        
        required_vars = platform_env_vars.get(platform.lower(), [])
        
        if not required_vars:
            return False
        
        # Check if at least one required var is set (simplified check)
        for var in required_vars:
            if os.getenv(var):
                return True
        
        return False
    
    async def _apply_rate_limit(self, platform: str):
        """
        Apply rate limiting for platform.
        
        Ensures we don't exceed platform-specific rate limits.
        
        Args:
            platform: Platform name
        """
        if platform not in self.rate_limits:
            logger.warning(f"⚠️  No rate limit configured for {platform}, using default")
            await asyncio.sleep(6)  # Default delay
            return
        
        limit_config = self.rate_limits[platform]
        max_per_minute = limit_config["max_per_minute"]
        delay_seconds = limit_config["delay_seconds"]
        
        current_time = datetime.now(timezone.utc)
        
        # Initialize tracking if needed
        if platform not in self.last_send_times:
            self.last_send_times[platform] = []
            self.send_counts[platform] = 0
        
        # Remove sends older than 1 minute
        one_minute_ago = current_time.timestamp() - 60
        self.last_send_times[platform] = [
            ts for ts in self.last_send_times[platform] if ts > one_minute_ago
        ]
        
        # Check if we're at the limit
        if len(self.last_send_times[platform]) >= max_per_minute:
            # Calculate wait time until oldest send is 1 minute old
            oldest_send = min(self.last_send_times[platform])
            wait_until = oldest_send + 60
            wait_seconds = max(0, wait_until - current_time.timestamp())
            
            if wait_seconds > 0:
                logger.info(f"⏳ [SOCIAL SENDING] Rate limit reached for {platform}, waiting {wait_seconds:.1f} seconds")
                await asyncio.sleep(wait_seconds)
        
        # Record this send
        self.last_send_times[platform].append(current_time.timestamp())
    
    async def send_batch(
        self,
        profiles: List[SocialProfile],
        draft_bodies: Dict[UUID, str],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Send messages to multiple profiles in batch.
        
        Applies rate limiting and handles errors per profile.
        
        Args:
            profiles: List of profiles to send to
            draft_bodies: Dict mapping profile_id to draft body
            db: Database session
        
        Returns:
            Dict with 'sent', 'failed', 'total', 'results'
        """
        logger.info(f"📤 [SOCIAL SENDING] Sending batch of {len(profiles)} messages")
        
        sent_count = 0
        failed_count = 0
        results = []
        
        for profile in profiles:
            draft_body = draft_bodies.get(profile.id, "")
            
            if not draft_body:
                logger.warning(f"⚠️  No draft body for profile {profile.id}, skipping")
                failed_count += 1
                results.append({
                    "profile_id": str(profile.id),
                    "username": profile.username,
                    "success": False,
                    "error": "No draft body"
                })
                continue
            
            send_result = await self.send_message(profile, draft_body, db)
            
            if send_result.get("success"):
                sent_count += 1
            else:
                failed_count += 1
            
            results.append({
                "profile_id": str(profile.id),
                "username": profile.username,
                "success": send_result.get("success"),
                "message_id": send_result.get("message_id"),
                "error": send_result.get("error")
            })
        
        logger.info(f"✅ [SOCIAL SENDING] Batch complete: {sent_count} sent, {failed_count} failed")
        
        return {
            "sent": sent_count,
            "failed": failed_count,
            "total": len(profiles),
            "results": results
        }

