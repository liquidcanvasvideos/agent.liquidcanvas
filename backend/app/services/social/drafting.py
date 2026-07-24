"""
Social Outreach Drafting Service

Generates platform-specific messages using Gemini AI.
Completely separate from website email drafting.
"""
import logging
from typing import Dict, Any, Optional, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.clients.gemini import GeminiClient
from app.models.social import (
    SocialProfile,
    SocialDraft,
    SocialMessage,
    SocialPlatform,
    MessageType,
    MessageStatus,
)

logger = logging.getLogger(__name__)


class SocialDraftingService:
    """
    Service for generating social media outreach messages.
    
    Platform-specific message generation with:
    - Platform-appropriate tone and format
    - Follow-up generation with message history
    - Humorous, clever, non-repetitive follow-ups
    """
    
    def __init__(self):
        self.gemini_client = None
        try:
            self.gemini_client = GeminiClient()
        except Exception as e:
            logger.warning(f"⚠️  Gemini client not configured: {e}")
    
    def is_configured(self) -> bool:
        """Check if Gemini is configured"""
        return self.gemini_client is not None and self.gemini_client.is_configured()
    
    async def compose_initial_message(
        self,
        profile: SocialProfile,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Compose an initial outreach message for a social profile.
        
        Args:
            profile: Social profile to draft for
            db: Database session
        
        Returns:
            Dict with 'success', 'body', and optionally 'error'
        """
        if not self.is_configured():
            return {
                "success": False,
                "error": "Gemini API not configured",
                "body": None
            }
        
        platform = profile.platform.value
        logger.info(f"✍️  [SOCIAL DRAFTING] Composing initial message for {platform} profile: {profile.username}")
        
        # Build context about the profile
        context_parts = []
        if profile.full_name:
            context_parts.append(f"Name: {profile.full_name}")
        if profile.username:
            context_parts.append(f"Username: @{profile.username}")
        if profile.bio:
            context_parts.append(f"Bio: {profile.bio[:200]}")  # Limit bio length
        if profile.location:
            context_parts.append(f"Location: {profile.location}")
        if profile.category:
            context_parts.append(f"Category: {profile.category}")
        if profile.followers_count:
            context_parts.append(f"Followers: {profile.followers_count:,}")
        if profile.profile_url:
            context_parts.append(f"Profile: {profile.profile_url}")
        
        context = "\n".join(context_parts) if context_parts else f"Profile: @{profile.username}"
        
        # Platform-specific prompt
        prompt = self._build_initial_prompt(platform, context, profile)
        
        try:
            # Use GeminiClient to generate message (same client as website outreach)
            gemini_result = await self.gemini_client.compose_social_message(
                platform=platform,
                prompt=prompt,
                is_followup=False
            )
            
            if gemini_result.get("success"):
                return {
                    "success": True,
                    "body": gemini_result.get("body", ""),
                    "error": None
                }
            else:
                return {
                    "success": False,
                    "error": gemini_result.get("error", "Unknown error"),
                    "body": None
                }
        except Exception as e:
            logger.error(f"❌ [SOCIAL DRAFTING] Error composing initial message: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "body": None
            }
    
    async def compose_followup_message(
        self,
        profile: SocialProfile,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Compose a follow-up message for a social profile.
        
        Uses message history to generate humorous, clever, non-repetitive follow-ups.
        
        Args:
            profile: Social profile to draft for
            db: Database session
        
        Returns:
            Dict with 'success', 'body', and optionally 'error'
        """
        if not self.is_configured():
            return {
                "success": False,
                "error": "Gemini API not configured",
                "body": None
            }
        
        platform = profile.platform.value
        logger.info(f"🔄 [SOCIAL DRAFTING] Composing follow-up for {platform} profile: {profile.username}")
        
        # Get previous messages
        previous_messages_result = await db.execute(
            select(SocialMessage).where(
                SocialMessage.profile_id == profile.id,
                SocialMessage.status == MessageStatus.SENT.value
            ).order_by(SocialMessage.sent_at.desc())
        )
        previous_messages = previous_messages_result.scalars().all()
        
        if not previous_messages:
            logger.warning(f"⚠️  No previous messages for profile {profile.id}, cannot create follow-up")
            return {
                "success": False,
                "error": "No previous messages found",
                "body": None
            }
        
        # Build message history context
        message_history = []
        for idx, msg in enumerate(reversed(previous_messages), 1):  # Reverse to chronological order
            message_history.append({
                "sequence": idx,
                "type": msg.message_type.value,
                "body": msg.sent_body or msg.draft_body or "",
                "sent_at": msg.sent_at.isoformat() if msg.sent_at else ""
            })
        
        # Build profile context
        context_parts = []
        if profile.full_name:
            context_parts.append(f"Name: {profile.full_name}")
        if profile.username:
            context_parts.append(f"Username: @{profile.username}")
        if profile.bio:
            context_parts.append(f"Bio: {profile.bio[:200]}")
        if profile.location:
            context_parts.append(f"Location: {profile.location}")
        
        context = "\n".join(context_parts) if context_parts else f"Profile: @{profile.username}"
        
        # Platform-specific follow-up prompt
        prompt = self._build_followup_prompt(platform, context, message_history, profile)
        
        try:
            # Use GeminiClient to generate follow-up message (same client as website outreach)
            gemini_result = await self.gemini_client.compose_social_message(
                platform=platform,
                prompt=prompt,
                is_followup=True
            )
            
            if gemini_result.get("success"):
                return {
                    "success": True,
                    "body": gemini_result.get("body", ""),
                    "error": None
                }
            else:
                return {
                    "success": False,
                    "error": gemini_result.get("error", "Unknown error"),
                    "body": None
                }
        except Exception as e:
            logger.error(f"❌ [SOCIAL DRAFTING] Error composing follow-up: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "body": None
            }
    
    def _build_initial_prompt(
        self,
        platform: str,
        context: str,
        profile: SocialProfile
    ) -> str:
        """
        Build platform-specific prompt for initial messages.
        
        Each platform has different:
        - Character limits
        - Tone expectations
        - Format requirements
        """
        platform_guidance = {
            "linkedin": {
                "tone": "professional, warm, and business-focused",
                "length": "2-3 short paragraphs",
                "format": "LinkedIn message format",
                "character_limit": "300 characters"
            },
            "instagram": {
                "tone": "friendly, creative, and visually-oriented",
                "length": "1-2 short paragraphs",
                "format": "Instagram DM format",
                "character_limit": "1000 characters"
            },
            "tiktok": {
                "tone": "casual, fun, and engaging",
                "length": "1-2 short paragraphs",
                "format": "TikTok message format",
                "character_limit": "1000 characters"
            },
            "facebook": {
                "tone": "friendly, conversational, and approachable",
                "length": "2-3 short paragraphs",
                "format": "Facebook message format",
                "character_limit": "2000 characters"
            }
        }
        
        guidance = platform_guidance.get(platform.lower(), {
            "tone": "friendly and professional",
            "length": "2-3 short paragraphs",
            "format": "social media message format",
            "character_limit": "1000 characters"
        })
        
        from app.clients.gemini import CANONICAL_LIQUID_CANVAS_DESCRIPTION
        
        return f"""You are a professional outreach specialist for Liquid Canvas (liquidcanvas.art), a mobile-to-TV streaming art platform.

ABOUT LIQUID CANVAS (CANONICAL DESCRIPTION - USE THIS EXACTLY):
{CANONICAL_LIQUID_CANVAS_DESCRIPTION}

Your task is to compose a personalized {platform} outreach message.

Profile context:
{context}

Platform: {platform.upper()}
Tone: {guidance['tone']}
Length: {guidance['length']}
Format: {guidance['format']}
Character limit: {guidance['character_limit']}

Requirements:
1. The message must be {guidance['tone']}
2. It should mention something specific about their profile/bio/content
3. It should introduce Liquid Canvas as a mobile-to-TV streaming art platform - emphasize TV-based art streaming, playlists, connected TVs, personal + shared display, and NFTs where relevant
4. It should be concise and fit within {guidance['character_limit']}
5. It should include a clear call-to-action
6. It should be warm but not overly salesy
7. Platform-appropriate: {guidance['format']}

CRITICAL POSITIONING RULES:
- Liquid Canvas is a streaming art platform, NOT an art services company, creative agency, design studio, or art consultancy
- Emphasize: TV-based art streaming, playlists, connected TVs, personal + shared display, NFTs
- Avoid generic "art collaboration" or "creative services" language

You MUST return ONLY valid JSON with this exact structure:
{{
  "body": "Message body text ({guidance['length']}, {guidance['tone']}, references liquidcanvas.art where appropriate)"
}}

Do not include any text before or after the JSON. Return ONLY the JSON object."""
    
    def _build_followup_prompt(
        self,
        platform: str,
        context: str,
        message_history: List[Dict[str, Any]],
        profile: SocialProfile
    ) -> str:
        """
        Build platform-specific prompt for follow-up messages.
        
        Follow-ups should be:
        - Humorous and clever
        - Non-repetitive
        - Reference previous messages subtly
        - Platform-appropriate
        """
        platform_guidance = {
            "linkedin": {
                "tone": "professional but playful, witty, and memorable",
                "length": "1-2 short paragraphs",
                "character_limit": "300 characters"
            },
            "instagram": {
                "tone": "playful, creative, and light",
                "length": "1-2 short paragraphs",
                "character_limit": "1000 characters"
            },
            "tiktok": {
                "tone": "casual, fun, and clever",
                "length": "1-2 short paragraphs",
                "character_limit": "1000 characters"
            },
            "facebook": {
                "tone": "friendly, conversational, and witty",
                "length": "1-2 short paragraphs",
                "character_limit": "2000 characters"
            }
        }
        
        guidance = platform_guidance.get(platform.lower(), {
            "tone": "playful and professional",
            "length": "1-2 short paragraphs",
            "character_limit": "1000 characters"
        })
        
        # Build message history text
        history_text = []
        for msg in message_history:
            history_text.append(
                f"Message #{msg['sequence']} ({msg['type']}, sent {msg['sent_at']}):\n{msg['body'][:300]}..."
            )
        
        history_context = "\n\n".join(history_text) if history_text else "No previous messages"
        followup_number = len(message_history) + 1
        
        from app.clients.gemini import CANONICAL_LIQUID_CANVAS_DESCRIPTION
        
        return f"""You are a professional outreach specialist for Liquid Canvas (liquidcanvas.art), a mobile-to-TV streaming art platform.

ABOUT LIQUID CANVAS (CANONICAL DESCRIPTION - USE THIS EXACTLY):
{CANONICAL_LIQUID_CANVAS_DESCRIPTION}

Your task is to compose a SHORT, PLAYFUL, LIGHT, WITTY follow-up message for {platform.upper()}. This is follow-up #{followup_number} in the conversation.

Profile context:
{context}

Previous messages in this conversation:
{history_context}

Platform: {platform.upper()}
Tone: {guidance['tone']}
Length: {guidance['length']}
Character limit: {guidance['character_limit']}

Requirements:
1. The message must be SHORT ({guidance['length']})
2. It should be PLAYFUL and LIGHT - use humor, wit, and a clever hook that makes them smile
3. It should be POLITE and professional (playful doesn't mean unprofessional)
4. Reference the previous attempt SUBTLY and PLAYFULLY (don't be pushy or desperate)
5. It should be memorable and stand out - think of it as a friendly nudge, not a sales pitch
6. Keep it concise - people are busy
7. The tone should be LIGHT and CONVERSATIONAL - like you're reaching out to a friend, not a cold prospect
8. Reference Liquid Canvas (liquidcanvas.art) naturally if relevant, but keep it subtle in follow-ups
9. DO NOT repeat content from previous messages - be fresh and new
10. Make it {guidance['tone']} - this is {platform}, not a formal email

You MUST return ONLY valid JSON with this exact structure:
{{
  "body": "Message body text ({guidance['length']}, {guidance['tone']}, witty, references previous attempt subtly)"
}}

Do not include any text before or after the JSON. Return ONLY the JSON object."""

