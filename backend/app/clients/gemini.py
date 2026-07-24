"""Google Gemini API client for email composition"""
import httpx
from typing import Dict, Any, Optional, List, TYPE_CHECKING
import os
from dotenv import load_dotenv
import logging
import json
import asyncio

if TYPE_CHECKING:
    from app.models.prospect import Prospect

load_dotenv()

logger = logging.getLogger(__name__)

# CANONICAL LIQUID CANVAS DESCRIPTION (NON-NEGOTIABLE)
# This is the ONLY valid source of truth for Liquid Canvas positioning.
# Must be used consistently across all drafting, Gemini prompts, and outreach logic.
CANONICAL_LIQUID_CANVAS_DESCRIPTION = """Liquid Canvas is a mobile-to-TV streaming art platform with a curated gallery of over 6,000 pieces of art.
Subscribers can create custom playlists and push art to any connected TV.
Users can upload personal photos and videos, connect to the TVs of family and friends, and turn any TV into a connected picture frame.
Liquid Canvas supports NFT display and sharing.
It turns any TV into a work of art and transforms rooms into galleries.
Liquid Canvas is like Spotify for TV art.

Website: https://liquidcanvas.art

CRITICAL POSITIONING RULES:
- Liquid Canvas is a streaming art platform, NOT an art services company
- Liquid Canvas is NOT a creative agency, design studio, or art consultancy
- Emphasize: TV-based art streaming, playlists, connected TVs, personal + shared display, NFTs
- Avoid generic "art collaboration" or "creative services" language"""


def strip_markdown_formatting(text: str) -> str:
    """
    Strip markdown formatting from text, especially asterisks for bold/italic.
    
    Removes:
    - **bold** -> bold
    - *italic* -> italic
    - ***bold italic*** -> bold italic
    - Other common markdown formatting
    
    Returns plain text suitable for email/DM drafts.
    """
    if not text:
        return text
    
    import re
    
    # Remove markdown bold/italic (**, *, ***)
    text = re.sub(r'\*\*\*([^*]+)\*\*\*', r'\1', text)  # ***bold italic***
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # **bold**
    text = re.sub(r'\*([^*]+)\*', r'\1', text)  # *italic*
    
    # Remove other markdown formatting
    text = re.sub(r'__([^_]+)__', r'\1', text)  # __bold__
    text = re.sub(r'_([^_]+)_', r'\1', text)  # _italic_
    text = re.sub(r'~~([^~]+)~~', r'\1', text)  # ~~strikethrough~~
    text = re.sub(r'`([^`]+)`', r'\1', text)  # `code`
    text = re.sub(r'```[\s\S]*?```', '', text)  # ```code blocks```
    
    # Clean up any remaining asterisks that might be standalone
    text = re.sub(r'\*+', '', text)
    
    # Clean up extra whitespace
    text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)  # Multiple blank lines -> double
    text = text.strip()
    
    return text


class GeminiClient:
    """Client for Google Gemini API"""
    
    BASE_URL = "https://generativelanguage.googleapis.com/v1"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Gemini client
        
        Args:
            api_key: Gemini API key (if None, uses GEMINI_API_KEY from env)
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "AIzaSyC-MKn0wqH-PAbVjA3i_bVn0uvquopzzWk")
        # Use hardcoded model that works with v1 API - updated 2025-01-29
        self.model = "gemini-2.0-flash"
        
        if not self.api_key:
            raise ValueError("Gemini API key not configured. Set GEMINI_API_KEY")
    
    def is_configured(self) -> bool:
        """Check if client is properly configured"""
        return bool(self.api_key and self.api_key.strip())
    
    async def validate_model(self) -> bool:
        """
        Validate that the configured model exists and supports generateContent.
        
        Returns:
            True if model is valid, False otherwise
        """
        try:
            logger.info(f"🔍 [GEMINI] Validating model: {self.model}")
            url = f"{self.BASE_URL}/models/{self.model}:generateContent?key={self.api_key}"
            test_payload = {
                "contents": [{
                    "parts": [{
                        "text": "test"
                    }]
                }],
                "generationConfig": {
                    "maxOutputTokens": 1
                }
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=test_payload)
                if response.status_code == 200:
                    logger.info(f"✅ Gemini model {self.model} is valid and supports generateContent")
                    return True
                else:
                    error_detail = response.text
                    logger.error(f"❌ Gemini model {self.model} validation failed: {response.status_code} - {error_detail}")
                    
                    # If model not found, try fallback models
                    if response.status_code == 404:
                        # First, let's list available models to debug
                        logger.info(f"🔍 [GEMINI] Listing available models to debug...")
                        list_url = f"{self.BASE_URL}/models?key={self.api_key}"
                        list_response = await client.get(list_url)
                        if list_response.status_code == 200:
                            models_data = list_response.json()
                            available_models = []
                            if "models" in models_data:
                                for model in models_data["models"]:
                                    if "generateContent" in model.get("supportedGenerationMethods", []):
                                        available_models.append(model["name"])
                                logger.info(f"✅ [GEMINI] Available models with generateContent: {available_models}")
                            else:
                                logger.warning(f"⚠️ [GEMINI] No models found in response: {models_data}")
                        else:
                            logger.error(f"❌ [GEMINI] Failed to list models: {list_response.status_code} - {list_response.text}")
                        
                        # Try most likely models first, stop on first success
                        fallback_models = [
                            "gemini-1.5-flash",
                            "gemini-1.5-pro",
                            "gemini-1.5-flash-latest",
                            "gemini-1.5-pro-latest"
                        ]
                        
                        for fallback in fallback_models:
                            if fallback == self.model:
                                continue
                            logger.info(f"🔄 [GEMINI] Trying fallback model: {fallback}")
                            fallback_url = f"{self.BASE_URL}/models/{fallback}:generateContent?key={self.api_key}"
                            fallback_response = await client.post(fallback_url, json=test_payload)
                            
                            if fallback_response.status_code == 200:
                                logger.info(f"✅ [GEMINI] Fallback model {fallback} works! Updating model...")
                                self.model = fallback
                                return True
                            elif fallback_response.status_code == 429:
                                logger.warning(f"⚠️ [GEMINI] Rate limited on model {fallback}, waiting before retry...")
                                await asyncio.sleep(2)  # Wait 2 seconds on rate limit
                                continue
                            else:
                                logger.warning(f"⚠️ [GEMINI] Fallback model {fallback} failed: {fallback_response.status_code}")
                    
                    # Handle rate limit for initial model too
                    elif response.status_code == 429:
                        logger.warning(f"⚠️ [GEMINI] Rate limited on model {self.model}, waiting...")
                        await asyncio.sleep(3)
                        # Retry once after waiting
                        retry_response = await client.post(url, json=test_payload)
                        if retry_response.status_code == 200:
                            logger.info(f"✅ Gemini model {self.model} worked after retry")
                            return True
                    
                    return False
        except Exception as e:
            logger.error(f"❌ Failed to validate Gemini model {self.model}: {e}", exc_info=True)
            return False
    
    async def _search_liquid_canvas_info(self) -> str:
        """
        Search for information about Liquid Canvas using Gemini's web search
        
        Returns:
            String with information about Liquid Canvas
        """
        search_url = f"{self.BASE_URL}/models/{self.model}:generateContent?key={self.api_key}"
        
        search_prompt = f"""Search DEEPLY into the internet for comprehensive information about Liquid Canvas (liquidcanvas.art), a mobile-to-TV streaming art platform.

CANONICAL DESCRIPTION (use this as reference):
{CANONICAL_LIQUID_CANVAS_DESCRIPTION}

Search VERY DEEPLY - not just surface search. Look into:
1. Current features and capabilities (search multiple sources, forums, reviews)
2. Recent updates or new functionality (check changelogs, release notes, blog posts)
3. User testimonials or reviews (search review sites, social media, forums, Reddit)
4. Any notable partnerships or integrations (search news articles, press releases, partnership announcements)
5. Community discussions and feedback (search forums, social media discussions, user groups)
6. Technical documentation and API information (if available)
7. Competitor comparisons and market positioning

Use deep web search - go beyond the first page of results. Search multiple sources, forums, review sites, social media, and community discussions.

Return a comprehensive summary (4-6 sentences) that confirms or supplements the canonical description above with deep insights.
IMPORTANT: Liquid Canvas is a streaming art platform, NOT an art services company or creative agency."""
        
        search_payload = {
            "contents": [{
                "parts": [{
                    "text": search_prompt
                }]
            }],
            "tools": [{
                "googleSearchRetrieval": {
                    "dynamicRetrievalConfig": {
                        "mode": "MODE_DYNAMIC",
                        "dynamicThreshold": 0.3
                    }
                }
            }],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 1024
            }
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.info("🔍 Searching for Liquid Canvas information...")
                response = await client.post(search_url, json=search_payload)
                response.raise_for_status()
                result = response.json()
                
                if result.get("candidates") and len(result["candidates"]) > 0:
                    candidate = result["candidates"][0]
                    if candidate.get("content") and candidate["content"].get("parts"):
                        parts = candidate["content"]["parts"]
                        if parts and isinstance(parts, list) and len(parts) > 0:
                            info_text = parts[0].get("text", "") if isinstance(parts[0], dict) else ""
                            if info_text:
                                logger.info("✅ Found Liquid Canvas information")
                                return info_text
        except Exception as e:
            logger.warning(f"⚠️  Failed to search for Liquid Canvas info: {e}. Using default info.")
        
        # Fallback: Use canonical description
        return CANONICAL_LIQUID_CANVAS_DESCRIPTION
    
    async def _fetch_website_content(self, page_url: Optional[str], domain: str) -> Optional[str]:
        """
        Fetch and extract main content from a website URL.
        
        Returns:
            Extracted text content from the website, or None if fetch fails
        """
        if not page_url:
            # Try homepage
            page_url = f"https://{domain}"
        
        try:
            import httpx
            from bs4 import BeautifulSoup
            
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                response = await client.get(page_url, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                response.raise_for_status()
                html = response.text
                
                # Parse HTML and extract main content
                soup = BeautifulSoup(html, 'html.parser')
                
                # Remove script and style elements
                for script in soup(["script", "style", "nav", "footer", "header"]):
                    script.decompose()
                
                # Get text content
                text = soup.get_text()
                
                # Clean up whitespace
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                text = ' '.join(chunk for chunk in chunks if chunk)
                
                # Limit to first 2000 characters to avoid token limits
                if len(text) > 2000:
                    text = text[:2000] + "..."
                
                logger.info(f"✅ Fetched website content from {page_url} ({len(text)} chars)")
                return text
        except Exception as e:
            logger.warning(f"⚠️  Failed to fetch website content from {page_url}: {e}")
            return None
    
    async def build_chat_prompt(
        self,
        prospect: "Prospect",
        user_message: str,
        current_subject: Optional[str] = None,
        current_body: Optional[str] = None
    ) -> str:
        """
        Build a prompt for Gemini chat to refine email drafts.
        
        This centralizes prompt construction for chat, ensuring Liquid Canvas context
        is always included and positioning is clear.
        
        Args:
            prospect: Prospect model object with domain, page_title, page_url, etc.
            user_message: User's chat message/request
            current_subject: Current draft subject (if any)
            current_body: Current draft body (if any)
        
        Returns:
            Complete prompt string for Gemini
        """
        # Get Liquid Canvas context
        liquid_canvas_info = await self._search_liquid_canvas_info()
        
        # Build positioning summary - only for website prospects
        source_type = getattr(prospect, 'source_type', None)
        positioning_summary = ""
        
        if source_type != 'social':
            # Website prospect - fetch website content and build positioning summary
            website_content = await self._fetch_website_content(
                getattr(prospect, 'page_url', None),
                getattr(prospect, 'domain', '')
            )
            positioning_summary = await self._build_positioning_summary(
                website_content,
                getattr(prospect, 'page_title', None),
                getattr(prospect, 'page_snippet', None),
                getattr(prospect, 'domain', '')
            )
        else:
            # Social media profile - build simpler positioning based on platform and profile info
            platform = getattr(prospect, 'source_platform', 'social media')
            username = getattr(prospect, 'display_name', None) or getattr(prospect, 'username', 'Unknown')
            positioning_summary = f"This is a {platform.title()} profile for {username}. Consider the platform's communication style ({platform.title()} messages are typically more casual and engaging than email) and tailor the message accordingly."
        
        # Build prospect context - handle both website and social profiles
        prospect_info = []
        source_type = getattr(prospect, 'source_type', None)
        
        if source_type == 'social':
            # Social media profile
            if hasattr(prospect, 'source_platform') and prospect.source_platform:
                prospect_info.append(f"- Platform: {prospect.source_platform.title()}")
            if hasattr(prospect, 'username') and prospect.username:
                prospect_info.append(f"- Username: @{prospect.username}")
            if hasattr(prospect, 'display_name') and prospect.display_name:
                prospect_info.append(f"- Display Name: {prospect.display_name}")
            if hasattr(prospect, 'profile_url') and prospect.profile_url:
                prospect_info.append(f"- Profile URL: {prospect.profile_url}")
            if hasattr(prospect, 'follower_count') and prospect.follower_count:
                prospect_info.append(f"- Followers: {prospect.follower_count:,}")
            if hasattr(prospect, 'engagement_rate') and prospect.engagement_rate:
                prospect_info.append(f"- Engagement Rate: {prospect.engagement_rate}%")
            prospect_context = "\n".join(prospect_info) if prospect_info else "- Platform: Unknown"
        else:
            # Website prospect
            if hasattr(prospect, 'domain') and prospect.domain:
                prospect_info.append(f"- Domain: {prospect.domain}")
            if hasattr(prospect, 'page_title') and prospect.page_title:
                prospect_info.append(f"- Website Title: {prospect.page_title}")
            if hasattr(prospect, 'page_url') and prospect.page_url:
                prospect_info.append(f"- Website URL: {prospect.page_url}")
            if hasattr(prospect, 'discovery_category') and prospect.discovery_category:
                prospect_info.append(f"- Category: {prospect.discovery_category}")
            prospect_context = "\n".join(prospect_info) if prospect_info else "- Domain: Unknown"
        
        # Build current draft context
        draft_context = []
        if current_subject:
            draft_context.append(f"Subject: {current_subject}")
        else:
            draft_context.append("Subject: (not set)")
        
        if current_body:
            draft_context.append(f"Body: {current_body}")
        else:
            draft_context.append("Body: (empty)")
        
        draft_text = "\n".join(draft_context)
        
        # Determine message type based on source_type
        source_type = getattr(prospect, 'source_type', None)
        message_type = "social media message" if source_type == 'social' else "email draft"
        platform_context = ""
        if source_type == 'social':
            platform = getattr(prospect, 'source_platform', 'social media')
            platform_context = f"\nPLATFORM: {platform.title()}\nNote: Social media messages should be more casual, engaging, and platform-appropriate than email outreach."
        
        # Build complete prompt
        prompt = f"""You are a professional outreach specialist helping refine a {message_type} for Liquid Canvas (liquidcanvas.art), a mobile-to-TV streaming art platform.{platform_context}

ABOUT LIQUID CANVAS (READ THIS FIRST):
{liquid_canvas_info}

Website: https://liquidcanvas.art

POSITIONING SUMMARY (How to approach this recipient):
{positioning_summary}

PROSPECT INFORMATION:
{prospect_context}

CURRENT DRAFT:
{draft_text}

USER REQUEST:
{user_message}

INSTRUCTIONS:
Respond conversationally and naturally. Explain your reasoning, ask clarifying questions if needed, and provide helpful suggestions.

You can:
- Suggest alternative phrasing
- Improve clarity or tone
- Add personalization based on the prospect's website
- Refine the call-to-action
- Make it more engaging
- Ensure Liquid Canvas is clearly introduced
- Match the recipient's role/organization type

DRAFT SUGGESTION (IMPORTANT):
When the user asks you to:
- "regenerate" or "regenerate the draft"
- "rewrite" or "rewrite the draft"
- "create a new version" or "generate a new draft"
- "make it better" or "improve the draft"
- Or any similar request to create/update the draft

You MUST provide a complete draft suggestion wrapped in these exact markers:

--- DRAFT SUGGESTION ---
Subject: [your suggested subject line]
Body: [your suggested body text]
--- END DRAFT SUGGESTION ---

For other conversational requests (questions, clarifications, explanations), respond conversationally without the draft markers.

IMPORTANT: If the user's request implies they want a new or improved draft, ALWAYS include the draft suggestion markers.

Draft suggestions are OPTIONAL. Only include them if you think a full rewrite would be helpful. Most responses should be conversational guidance without draft markers."""
        
        return prompt
    
    async def _build_positioning_summary(
        self,
        website_content: Optional[str],
        page_title: Optional[str],
        page_snippet: Optional[str],
        domain: str
    ) -> str:
        """
        Build an internal positioning summary using Gemini.
        
        This analyzes the recipient's website and determines how to position Liquid Canvas.
        """
        url = f"{self.BASE_URL}/models/{self.model}:generateContent?key={self.api_key}"
        
        analysis_prompt = f"""Analyze this website and create a positioning summary for outreach.

Website Information:
- Domain: {domain}
- Title: {page_title or 'Unknown'}
- Description: {page_snippet or 'Not provided'}
- Content: {website_content[:1500] if website_content else 'Not available'}

Create a brief positioning summary (2-3 sentences) that:
1. Identifies what type of organization/business this is
2. Notes their focus area or niche
3. Suggests how Liquid Canvas (liquidcanvas.art) could be relevant to them
4. Identifies the best angle for outreach

Return ONLY the positioning summary text, no additional formatting."""
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json={
                    "contents": [{"parts": [{"text": analysis_prompt}]}],
                    "generationConfig": {
                        "temperature": 0.5,
                        "maxOutputTokens": 256
                    }
                })
                response.raise_for_status()
                result = response.json()
                
                if result.get("candidates") and len(result["candidates"]) > 0:
                    candidate = result["candidates"][0]
                    if candidate.get("content") and candidate["content"].get("parts"):
                        parts = candidate["content"]["parts"]
                        if parts and isinstance(parts, list) and len(parts) > 0:
                            summary = parts[0].get("text", "") if isinstance(parts[0], dict) else ""
                            if summary:
                                logger.info("✅ Built positioning summary")
                                return summary
        except Exception as e:
            logger.warning(f"⚠️  Failed to build positioning summary: {e}")
        
        # Fallback summary
        return f"This appears to be a {page_title or 'business'} in the {domain} domain. Liquid Canvas, a mobile-to-TV streaming art platform, could help them display curated art collections, create custom playlists, and transform their spaces into galleries using connected TVs."
    
    async def compose_email(
        self,
        domain: str,
        page_title: Optional[str] = None,
        page_url: Optional[str] = None,
        page_snippet: Optional[str] = None,
        contact_name: Optional[str] = None,
        category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Compose an email using Gemini API with Liquid Canvas information.
        
        CRITICAL: Reads website content first, builds positioning summary, then generates email.
        
        Args:
            domain: Website domain
            page_title: Page title (business/organization name)
            page_url: Page URL
            page_snippet: Page description/snippet
            contact_name: Contact name (if available)
            category: Category of the prospect (e.g., "Museum", "Art Gallery", "Interior Design", etc.)
        
        Returns:
            Dictionary with subject and body
        """
        url = f"{self.BASE_URL}/models/{self.model}:generateContent?key={self.api_key}"
        
        # STEP 1: Search for Liquid Canvas information
        liquid_canvas_info = await self._search_liquid_canvas_info()
        
        # STEP 2: Fetch website content
        logger.info(f"📄 [GEMINI] Fetching website content for {domain}...")
        website_content = await self._fetch_website_content(page_url, domain)
        
        # STEP 3: Build positioning summary
        logger.info(f"📊 [GEMINI] Building positioning summary for {domain}...")
        positioning_summary = await self._build_positioning_summary(
            website_content,
            page_title,
            page_snippet,
            domain
        )
        
        # STEP 4: Build context for the email
        # Extract business/organization name from page_title
        business_name = page_title or domain or "Business"
        
        context_parts = []
        if page_title:
            context_parts.append(f"Business/Organization Name: {page_title}")
        if domain:
            context_parts.append(f"Domain: {domain}")
        if page_snippet:
            context_parts.append(f"Description: {page_snippet}")
        if page_url:
            context_parts.append(f"URL: {page_url}")
        if website_content:
            context_parts.append(f"Website Content Preview: {website_content[:500]}...")
        if contact_name:
            context_parts.append(f"Contact Name: {contact_name}")
        if category:
            context_parts.append(f"Category: {category}")
        
        context = "\n".join(context_parts) if context_parts else f"Website: {domain}"
        
        # Create category-specific context for ALL categories
        category_context = ""
        if category:
            category_lower = category.lower()
            if "museum" in category_lower:
                category_context = f"\n\nCATEGORY CONTEXT:\nThis recipient is a museum named '{business_name}'. Use the museum name '{business_name}' in the email to personalize it. Reference the museum's collection, exhibitions, or mission when relevant. Liquid Canvas can help museums display their collections on TVs throughout the facility."
            elif "art gallery" in category_lower or "gallery" in category_lower:
                category_context = f"\n\nCATEGORY CONTEXT:\nThis recipient is an art gallery named '{business_name}'. Use the gallery name '{business_name}' in the email to personalize it. Reference their exhibitions, artist roster, or curation style when relevant. Liquid Canvas can help galleries showcase artwork on connected TVs."
            elif "interior design" in category_lower or "interior decor" in category_lower:
                category_context = f"\n\nCATEGORY CONTEXT:\nThis recipient is an interior design business named '{business_name}'. Use the business name '{business_name}' in the email to personalize it. Reference their design style, portfolio, or client work when relevant. Liquid Canvas can help interior designers create beautiful art displays for their clients' spaces."
            elif "home decor" in category_lower or "holiday decor" in category_lower:
                category_context = f"\n\nCATEGORY CONTEXT:\nThis recipient is a home decor business named '{business_name}'. Use the business name '{business_name}' in the email to personalize it. Reference their products, style, or seasonal offerings when relevant. Liquid Canvas can help enhance home decor with curated art displays."
            elif "parenting" in category_lower or "mom" in category_lower:
                category_context = f"\n\nCATEGORY CONTEXT:\nThis recipient is a parenting/mom blog or resource named '{business_name}'. Use the business name '{business_name}' in the email to personalize it. Reference their content, community, or parenting focus when relevant. Liquid Canvas can help families create beautiful art displays in their homes."
            elif "nft" in category_lower:
                category_context = f"\n\nCATEGORY CONTEXT:\nThis recipient is an NFT platform or business named '{business_name}'. Use the business name '{business_name}' in the email to personalize it. Reference their NFT collection, platform, or digital art focus when relevant. Liquid Canvas supports NFT display and sharing."
            elif "photographer" in category_lower or "photography" in category_lower:
                category_context = f"\n\nCATEGORY CONTEXT:\nThis recipient is a photographer named '{business_name}'. Use their name '{business_name}' in the email to personalize it. Reference their photography style, portfolio, or specialty when relevant. Liquid Canvas can help photographers display their work on connected TVs."
            elif "painter" in category_lower or "artist" in category_lower:
                category_context = f"\n\nCATEGORY CONTEXT:\nThis recipient is an artist/painter named '{business_name}'. Use their name '{business_name}' in the email to personalize it. Reference their artistic style, portfolio, or exhibitions when relevant. Liquid Canvas can help artists showcase their work on connected TVs."
            elif "dog" in category_lower or "cat" in category_lower:
                category_context = f"\n\nCATEGORY CONTEXT:\nThis recipient is a pet-related business or resource named '{business_name}'. Use the business name '{business_name}' in the email to personalize it. Reference their pet focus, products, or community when relevant. Liquid Canvas can help create beautiful art displays for pet-friendly spaces."
            elif "holiday" in category_lower:
                category_context = f"\n\nCATEGORY CONTEXT:\nThis recipient is a holiday-focused business or resource named '{business_name}'. Use the business name '{business_name}' in the email to personalize it. Reference their holiday focus, products, or seasonal offerings when relevant. Liquid Canvas can help create festive art displays for holiday celebrations."
            elif "home tech" in category_lower or "tech" in category_lower:
                category_context = f"\n\nCATEGORY CONTEXT:\nThis recipient is a home tech business named '{business_name}'. Use the business name '{business_name}' in the email to personalize it. Reference their tech products, smart home solutions, or innovation focus when relevant. Liquid Canvas integrates with smart home systems for art display."
            elif "audio visual" in category_lower or "av" in category_lower:
                category_context = f"\n\nCATEGORY CONTEXT:\nThis recipient is an audio-visual business named '{business_name}'. Use the business name '{business_name}' in the email to personalize it. Reference their AV solutions, home theater systems, or technology focus when relevant. Liquid Canvas can integrate with AV systems for art display."
            else:
                # Generic category context
                category_context = f"\n\nCATEGORY CONTEXT:\nThis recipient is in the '{category}' category and their business/organization is named '{business_name}'. Use the business name '{business_name}' in the email to personalize it. Reference their specific focus, products, or services when relevant."
        
        # Contact name context
        contact_context = ""
        if contact_name:
            contact_context = f"\n\nCONTACT NAME:\nThe recipient's name is '{contact_name}'. Use this name to personalize the greeting (e.g., 'Hello {contact_name},' or 'Dear {contact_name},')."
        
        prompt = f"""You are a professional outreach specialist for Liquid Canvas (liquidcanvas.art), a mobile-to-TV streaming art platform.

ABOUT LIQUID CANVAS (READ THIS FIRST):
{liquid_canvas_info}

Website: https://liquidcanvas.art

POSITIONING SUMMARY (How to approach this recipient):
{positioning_summary}
{category_context}
{contact_context}

RECIPIENT'S WEBSITE CONTEXT:
{context}

YOUR TASK:
Compose a personalized outreach email that:
1. Clearly introduces Liquid Canvas (liquidcanvas.art) - mention who we are and what we do
2. References something specific about their website/content (use the positioning summary)
3. Positions Liquid Canvas as relevant to their organization type/niche
4. Is professional, friendly, and personalized
5. Is concise (2-3 short paragraphs)
6. Includes a clear call-to-action
7. Is warm but not overly salesy
8. Uses the Liquid Canvas information to make the email authentic and specific
{f"9. Use the business/organization name '{business_name}' throughout the email to personalize it" if business_name else ""}
{f"10. Use the contact name '{contact_name}' in the greeting to personalize the email" if contact_name else ""}

CRITICAL: The email MUST clearly introduce Liquid Canvas. Do not assume they know who we are.

You MUST return ONLY valid JSON with this exact structure:
{{
  "subject": "Email subject line (max 60 characters)",
  "body": "Email body text (2-3 paragraphs, professional tone, references liquidcanvas.art where appropriate)"
}}

Do not include any text before or after the JSON. Return ONLY the JSON object."""

        payload = {
            "contents": [{
                "parts": [{
                    "text": prompt
                }]
            }],
            "generationConfig": {
                "temperature": 0.7,
                "topK": 40,
                "topP": 0.95,
                "maxOutputTokens": 1024
            }
        }
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                logger.info(f"Calling Gemini API to compose email for domain: {domain}")
                response = await client.post(url, json=payload)
                response.raise_for_status()
                result = response.json()
                
                # Extract content from Gemini response
                if result.get("candidates") and len(result["candidates"]) > 0:
                    candidate = result["candidates"][0]
                    if candidate.get("content") and candidate["content"].get("parts"):
                        parts = candidate["content"]["parts"]
                        # Safely get first part
                        if parts and isinstance(parts, list) and len(parts) > 0:
                            text_content = parts[0].get("text", "") if isinstance(parts[0], dict) else ""
                        else:
                            text_content = ""
                        
                        # Parse JSON response
                        try:
                            email_data = json.loads(text_content)
                            
                            subject = email_data.get("subject", f"Partnership Opportunity - {domain}")
                            body = email_data.get("body", f"Hello,\n\nI noticed your website {domain}...")
                            
                            # Strip markdown formatting (asterisks, etc.)
                            subject = strip_markdown_formatting(subject)
                            body = strip_markdown_formatting(body)
                            
                            logger.info(f"✅ Gemini composed email for {domain}")
                            
                            return {
                                "success": True,
                                "subject": subject,
                                "body": body,
                                "raw_response": result
                            }
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to parse Gemini JSON response: {e}")
                            logger.error(f"Response text: {text_content[:200]}")
                            # Fallback to extracting from text
                            return self._extract_from_text(text_content, domain)
                    else:
                        return {
                            "success": False,
                            "error": "No content in Gemini response",
                            "domain": domain
                        }
                else:
                    error_msg = result.get("error", {}).get("message", "Unknown error")
                    return {
                        "success": False,
                        "error": error_msg,
                        "domain": domain
                    }
        
        except httpx.HTTPStatusError as e:
            logger.error(f"Gemini API HTTP error for {domain}: {e.response.status_code} - {e.response.text}")
            return {
                "success": False,
                "error": f"HTTP {e.response.status_code}: {e.response.text}",
                "domain": domain
            }
        except Exception as e:
            logger.error(f"Gemini API call failed for {domain}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "domain": domain
            }

    async def generate_category_template(self, category: str, notes: Optional[str] = None) -> Dict[str, Any]:
        url = f"{self.BASE_URL}/models/{self.model}:generateContent?key={self.api_key}"

        liquid_canvas_info = await self._search_liquid_canvas_info()
        notes_text = (notes or "").strip()

        prompt = f"""You are creating a reusable outreach email TEMPLATE for Liquid Canvas (liquidcanvas.art), a mobile-to-TV streaming art platform.

ABOUT LIQUID CANVAS (READ THIS FIRST):
{liquid_canvas_info}

TARGET CATEGORY:
{category}

OPTIONAL NOTES FROM USER:
{notes_text if notes_text else '(none)'}

TASK:
Create a concept + reusable templates that can be applied to many recipients in this category.

RULES:
- Output MUST be strict JSON (no markdown, no extra text)
- JSON keys: concept, subject_template, body_template
- Templates should use placeholders when helpful:
  - {{business_name}} for organization name
  - {{domain}} for domain
- Keep body to 2-3 short paragraphs with a clear CTA
- Do not include overly generic filler; keep it adaptable
"""

        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                response = await client.post(
                    url,
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 900},
                    },
                )
                response.raise_for_status()
                data = response.json()

            text_out = ""
            if data.get("candidates"):
                parts = data["candidates"][0].get("content", {}).get("parts", [])
                if parts and isinstance(parts[0], dict):
                    text_out = (parts[0].get("text") or "").strip()

            if not text_out:
                return {"success": False, "error": "Gemini returned empty response"}

            try:
                parsed = json.loads(text_out)
            except Exception:
                start = text_out.find("{")
                end = text_out.rfind("}")
                if start >= 0 and end > start:
                    parsed = json.loads(text_out[start : end + 1])
                else:
                    raise

            concept = (parsed.get("concept") or "").strip()
            subject_template = (parsed.get("subject_template") or "").strip()
            body_template = (parsed.get("body_template") or "").strip()
            if not concept or not subject_template or not body_template:
                return {"success": False, "error": "Template JSON missing required fields"}

            return {
                "success": True,
                "concept": concept,
                "subject_template": subject_template,
                "body_template": body_template,
            }
        except Exception as e:
            logger.error(f"❌ [GEMINI] Failed to generate category template: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def compose_email_from_template(
        self,
        domain: str,
        page_title: Optional[str],
        page_url: Optional[str],
        page_snippet: Optional[str],
        category: Optional[str],
        concept: str,
        subject_template: str,
        body_template: str,
    ) -> Dict[str, Any]:
        url = f"{self.BASE_URL}/models/{self.model}:generateContent?key={self.api_key}"

        liquid_canvas_info = await self._search_liquid_canvas_info()
        website_content = await self._fetch_website_content(page_url, domain)
        business_name = (page_title or domain or "Business").strip()

        prompt = f"""You are generating a personalized outreach email for Liquid Canvas (liquidcanvas.art), a mobile-to-TV streaming art platform.

ABOUT LIQUID CANVAS (READ THIS FIRST):
{liquid_canvas_info}

RECIPIENT CONTEXT:
- Category: {category or 'Unknown'}
- Domain: {domain}
- Business Name: {business_name}
- Website URL: {page_url or f'https://{domain}'}
- Website Snippet: {page_snippet or '(none)'}
- Website Content Preview: {(website_content[:800] + '...') if website_content else '(not available)'}

CATEGORY CONCEPT:
{concept}

TEMPLATE (DO NOT COPY VERBATIM, ADAPT IT):
Subject template: {subject_template}
Body template: {body_template}

TASK:
Return strict JSON only (no markdown) with keys: subject, body.
The subject/body should be adapted to this recipient using their business name and any relevant detail from their snippet/content.
Keep body 2-3 short paragraphs + CTA.
"""

        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                response = await client.post(
                    url,
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"temperature": 0.5, "maxOutputTokens": 900},
                    },
                )
                response.raise_for_status()
                data = response.json()

            text_out = ""
            if data.get("candidates"):
                parts = data["candidates"][0].get("content", {}).get("parts", [])
                if parts and isinstance(parts[0], dict):
                    text_out = (parts[0].get("text") or "").strip()

            if not text_out:
                return {"success": False, "error": "Gemini returned empty response"}

            try:
                parsed = json.loads(text_out)
            except Exception:
                start = text_out.find("{")
                end = text_out.rfind("}")
                if start >= 0 and end > start:
                    parsed = json.loads(text_out[start : end + 1])
                else:
                    raise

            subject = strip_markdown_formatting((parsed.get("subject") or "").strip())
            body = strip_markdown_formatting((parsed.get("body") or "").strip())
            if not subject or not body:
                return {"success": False, "error": "Gemini returned empty subject/body"}

            return {"success": True, "subject": subject, "body": body}
        except Exception as e:
            logger.error(f"❌ [GEMINI] Failed to compose from template for {domain}: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    async def compose_social_message(
        self,
        platform: str,
        prompt: str,
        is_followup: bool = False
    ) -> Dict[str, Any]:
        """
        Compose a social media message using Gemini API.
        
        This is a generic method for social platforms that accepts a custom prompt.
        Used by SocialDraftingService for platform-specific message generation.
        
        Args:
            platform: Platform name (linkedin, instagram, tiktok, facebook)
            prompt: The prompt to send to Gemini
            is_followup: Whether this is a follow-up message (affects temperature)
        
        Returns:
            Dictionary with 'success', 'body', and optionally 'error'
        """
        url = f"{self.BASE_URL}/models/{self.model}:generateContent?key={self.api_key}"
        
        payload = {
            "contents": [{
                "parts": [{
                    "text": prompt
                }]
            }],
            "generationConfig": {
                "temperature": 0.8 if is_followup else 0.7,  # Higher temperature for follow-ups
                "topK": 40,
                "topP": 0.95,
                "maxOutputTokens": 1024
            }
        }
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                logger.info(f"Calling Gemini API to compose {platform} {'follow-up' if is_followup else 'initial'} message")
                response = await client.post(url, json=payload)
                response.raise_for_status()
                result = response.json()
                
                # Extract content from Gemini response
                if result.get("candidates") and len(result["candidates"]) > 0:
                    candidate = result["candidates"][0]
                    if candidate.get("content") and candidate["content"].get("parts"):
                        parts = candidate["content"]["parts"]
                        if parts and isinstance(parts, list) and len(parts) > 0:
                            text_content = parts[0].get("text", "") if isinstance(parts[0], dict) else ""
                        else:
                            text_content = ""
                        
                        # Parse JSON response
                        try:
                            message_data = json.loads(text_content)
                            body = message_data.get("body", "")
                            
                            if not body:
                                return {
                                    "success": False,
                                    "error": "Empty message body from Gemini",
                                    "body": None
                                }
                            
                            # Strip markdown formatting (asterisks, etc.)
                            body = strip_markdown_formatting(body)
                            
                            logger.info(f"✅ Gemini composed {platform} message ({len(body)} chars)")
                            
                            return {
                                "success": True,
                                "body": body,
                                "error": None
                            }
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to parse Gemini JSON response: {e}")
                            logger.error(f"Response text: {text_content[:200]}")
                            return {
                                "success": False,
                                "error": f"Failed to parse JSON: {e}",
                                "body": None
                            }
                    else:
                        return {
                            "success": False,
                            "error": "No content in Gemini response",
                            "body": None
                        }
                else:
                    error_msg = result.get("error", {}).get("message", "Unknown error")
                    return {
                        "success": False,
                        "error": error_msg,
                        "body": None
                    }
        
        except httpx.HTTPStatusError as e:
            logger.error(f"Gemini API HTTP error for {platform}: {e.response.status_code} - {e.response.text}")
            return {
                "success": False,
                "error": f"HTTP {e.response.status_code}: {e.response.text}",
                "body": None
            }
        except Exception as e:
            logger.error(f"Gemini API call failed for {platform}: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "body": None
            }
    
    def _extract_from_text(self, text: str, domain: str) -> Dict[str, Any]:
        """
        Fallback: Extract subject and body from text if JSON parsing fails
        
        Args:
            text: Text response from Gemini
            domain: Domain name
        
        Returns:
            Dictionary with subject and body
        """
        # Try to find JSON in text
        import re
        json_match = re.search(r'\{[^{}]*"subject"[^{}]*\}', text, re.DOTALL)
        if json_match:
            try:
                email_data = json.loads(json_match.group())
                subject = email_data.get("subject", f"Partnership Opportunity - {domain}")
                body = email_data.get("body", text)
                
                # Strip markdown formatting (asterisks, etc.)
                subject = strip_markdown_formatting(subject)
                body = strip_markdown_formatting(body)
                
                return {
                    "success": True,
                    "subject": subject,
                    "body": body
                }
            except:
                pass
        
        # Ultimate fallback
        lines = text.strip().split('\n')
        subject = lines[0][:60] if lines else f"Partnership Opportunity - {domain}"
        body = '\n'.join(lines[1:]) if len(lines) > 1 else text
        
        return {
            "success": True,
            "subject": subject,
            "body": body
        }
    
    async def compose_followup_email(
        self,
        domain: str,
        previous_emails: List[Dict[str, Any]],
        page_title: Optional[str] = None,
        page_url: Optional[str] = None,
        page_snippet: Optional[str] = None,
        contact_name: Optional[str] = None,
        category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Compose a follow-up email using Gemini API with memory of previous emails
        
        Args:
            domain: Website domain
            previous_emails: List of previous emails in thread, each with:
                - subject: str
                - body: str
                - sent_at: str (ISO timestamp)
                - sequence_index: int (0 = initial, 1+ = follow-up)
            page_title: Page title (business/organization name)
            page_url: Page URL
            page_snippet: Page description/snippet
            contact_name: Contact name (if available)
            category: Category of the prospect (e.g., "Museum", "Art Gallery", "Interior Design", etc.)
        
        Returns:
            Dictionary with subject and body
        """
        url = f"{self.BASE_URL}/models/{self.model}:generateContent?key={self.api_key}"
        
        # Build context for the email
        # Extract business/organization name from page_title
        business_name = page_title or domain or "Business"
        
        context_parts = []
        if page_title:
            context_parts.append(f"Business/Organization Name: {page_title}")
        if domain:
            context_parts.append(f"Domain: {domain}")
        if page_snippet:
            context_parts.append(f"Description: {page_snippet}")
        if page_url:
            context_parts.append(f"URL: {page_url}")
        if contact_name:
            context_parts.append(f"Contact Name: {contact_name}")
        if category:
            context_parts.append(f"Category: {category}")
        
        context = "\n".join(context_parts) if context_parts else f"Website: {domain}"
        
        # Build previous emails context
        previous_context = []
        for idx, prev_email in enumerate(previous_emails, 1):
            prev_subject = prev_email.get("subject", "No subject")
            prev_body = prev_email.get("body", "")
            prev_sent_at = prev_email.get("sent_at", "")
            seq_idx = prev_email.get("sequence_index", idx - 1)
            
            if seq_idx == 0:
                previous_context.append(f"Initial Email ({prev_sent_at}):\nSubject: {prev_subject}\nBody: {prev_body[:500]}...")
            else:
                previous_context.append(f"Follow-up #{seq_idx} ({prev_sent_at}):\nSubject: {prev_subject}\nBody: {prev_body[:500]}...")
        
        previous_emails_text = "\n\n".join(previous_context) if previous_context else "No previous emails"
        followup_count = len(previous_emails)
        
        # Search for Liquid Canvas information (cache it to avoid repeated searches)
        liquid_canvas_info = await self._search_liquid_canvas_info()
        
        # Create category-specific context (same logic as compose_email)
        category_context = ""
        if category:
            category_lower = category.lower()
            if "museum" in category_lower:
                category_context = f"\n\nCATEGORY CONTEXT:\nThis recipient is a museum named '{business_name}'. Use the museum name '{business_name}' in the email to personalize it."
            elif "art gallery" in category_lower or "gallery" in category_lower:
                category_context = f"\n\nCATEGORY CONTEXT:\nThis recipient is an art gallery named '{business_name}'. Use the gallery name '{business_name}' in the email to personalize it."
            elif "interior design" in category_lower or "interior decor" in category_lower:
                category_context = f"\n\nCATEGORY CONTEXT:\nThis recipient is an interior design business named '{business_name}'. Use the business name '{business_name}' in the email to personalize it."
            elif "home decor" in category_lower or "holiday decor" in category_lower:
                category_context = f"\n\nCATEGORY CONTEXT:\nThis recipient is a home decor business named '{business_name}'. Use the business name '{business_name}' in the email to personalize it."
            elif "parenting" in category_lower or "mom" in category_lower:
                category_context = f"\n\nCATEGORY CONTEXT:\nThis recipient is a parenting/mom blog or resource named '{business_name}'. Use the business name '{business_name}' in the email to personalize it."
            elif "nft" in category_lower:
                category_context = f"\n\nCATEGORY CONTEXT:\nThis recipient is an NFT platform or business named '{business_name}'. Use the business name '{business_name}' in the email to personalize it."
            elif "photographer" in category_lower or "photography" in category_lower:
                category_context = f"\n\nCATEGORY CONTEXT:\nThis recipient is a photographer named '{business_name}'. Use their name '{business_name}' in the email to personalize it."
            elif "painter" in category_lower or "artist" in category_lower:
                category_context = f"\n\nCATEGORY CONTEXT:\nThis recipient is an artist/painter named '{business_name}'. Use their name '{business_name}' in the email to personalize it."
            elif "dog" in category_lower or "cat" in category_lower:
                category_context = f"\n\nCATEGORY CONTEXT:\nThis recipient is a pet-related business or resource named '{business_name}'. Use the business name '{business_name}' in the email to personalize it."
            elif "holiday" in category_lower:
                category_context = f"\n\nCATEGORY CONTEXT:\nThis recipient is a holiday-focused business or resource named '{business_name}'. Use the business name '{business_name}' in the email to personalize it."
            elif "home tech" in category_lower or "tech" in category_lower:
                category_context = f"\n\nCATEGORY CONTEXT:\nThis recipient is a home tech business named '{business_name}'. Use the business name '{business_name}' in the email to personalize it."
            elif "audio visual" in category_lower or "av" in category_lower:
                category_context = f"\n\nCATEGORY CONTEXT:\nThis recipient is an audio-visual business named '{business_name}'. Use the business name '{business_name}' in the email to personalize it."
            else:
                category_context = f"\n\nCATEGORY CONTEXT:\nThis recipient is in the '{category}' category and their business/organization is named '{business_name}'. Use the business name '{business_name}' in the email to personalize it."
        
        # Contact name context
        contact_context = ""
        if contact_name:
            contact_context = f"\n\nCONTACT NAME:\nThe recipient's name is '{contact_name}'. Use this name to personalize the greeting."
        
        # Create prompt for follow-up email
        prompt = f"""You are a professional outreach specialist for Liquid Canvas (liquidcanvas.art), a mobile-to-TV streaming art platform.

About Liquid Canvas:
{liquid_canvas_info}

Website: https://liquidcanvas.art

Your task is to compose a SHORT, PLAYFUL, LIGHT, WITTY follow-up email. This is follow-up #{followup_count} in the thread.

Context about their website:
{context}
{category_context}
{contact_context}

Previous emails in this thread:
{previous_emails_text}

Requirements:
1. The email must be SHORT (1-2 paragraphs max)
2. It should be PLAYFUL and LIGHT - use humor, wit, and a clever hook that makes them smile
3. It should be POLITE and professional (playful doesn't mean unprofessional)
4. Reference the previous attempt SUBTLY and PLAYFULLY (don't be pushy or desperate)
5. It should be memorable and stand out - think of it as a friendly nudge, not a sales pitch
6. Keep it concise - people are busy
7. The tone should be LIGHT and CONVERSATIONAL - like you're reaching out to a friend, not a cold prospect
8. Reference Liquid Canvas (liquidcanvas.art) naturally if relevant, but keep it subtle in follow-ups

You MUST return ONLY valid JSON with this exact structure:
{{
  "subject": "Email subject line (max 60 characters, witty and attention-grabbing)",
  "body": "Email body text (1-2 short paragraphs, witty, polite, references previous attempt subtly)"
}}

Do not include any text before or after the JSON. Return ONLY the JSON object."""

        payload = {
            "contents": [{
                "parts": [{
                    "text": prompt
                }]
            }],
            "generationConfig": {
                "temperature": 0.8,  # Higher temperature for more creativity in follow-ups
                "topK": 40,
                "topP": 0.95,
                "maxOutputTokens": 1024
            }
        }
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                logger.info(f"Calling Gemini API to compose follow-up email #{followup_count} for domain: {domain}")
                response = await client.post(url, json=payload)
                response.raise_for_status()
                result = response.json()
                
                # Extract content from Gemini response (same logic as compose_email)
                if result.get("candidates") and len(result["candidates"]) > 0:
                    candidate = result["candidates"][0]
                    if candidate.get("content") and candidate["content"].get("parts"):
                        parts = candidate["content"]["parts"]
                        if parts and isinstance(parts, list) and len(parts) > 0:
                            text_content = parts[0].get("text", "") if isinstance(parts[0], dict) else ""
                        else:
                            text_content = ""
                        
                        # Parse JSON response
                        try:
                            email_data = json.loads(text_content)
                            
                            subject = email_data.get("subject", f"Following up - {domain}")
                            body = email_data.get("body", f"Hello,\n\nJust wanted to follow up on my previous message...")
                            
                            # Strip markdown formatting (asterisks, etc.)
                            subject = strip_markdown_formatting(subject)
                            body = strip_markdown_formatting(body)
                            
                            logger.info(f"✅ Gemini composed follow-up email #{followup_count} for {domain}")
                            
                            return {
                                "success": True,
                                "subject": subject,
                                "body": body,
                                "raw_response": result
                            }
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to parse Gemini JSON response: {e}")
                            logger.error(f"Response text: {text_content[:200]}")
                            return self._extract_from_text(text_content, domain)
                    else:
                        return {
                            "success": False,
                            "error": "No content in Gemini response",
                            "domain": domain
                        }
                else:
                    error_msg = result.get("error", {}).get("message", "Unknown error")
                    return {
                        "success": False,
                        "error": error_msg,
                        "domain": domain
                    }
        
        except httpx.HTTPStatusError as e:
            logger.error(f"Gemini API HTTP error for {domain}: {e.response.status_code} - {e.response.text}")
            return {
                "success": False,
                "error": f"HTTP {e.response.status_code}: {e.response.text}",
                "domain": domain
            }
        except Exception as e:
            logger.error(f"Gemini API call failed for {domain}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "domain": domain
            }
    
    async def compose_social_message(
        self,
        platform: str,
        prompt: str,
        is_followup: bool = False
    ) -> Dict[str, Any]:
        """
        Compose a social media message using Gemini API.
        
        This is a generic method for social platforms that accepts a custom prompt.
        Used by SocialDraftingService for platform-specific message generation.
        
        Args:
            platform: Platform name (linkedin, instagram, tiktok, facebook)
            prompt: The prompt to send to Gemini
            is_followup: Whether this is a follow-up message (affects temperature)
        
        Returns:
            Dictionary with 'success', 'body', and optionally 'error'
        """
        url = f"{self.BASE_URL}/models/{self.model}:generateContent?key={self.api_key}"
        
        payload = {
            "contents": [{
                "parts": [{
                    "text": prompt
                }]
            }],
            "generationConfig": {
                "temperature": 0.8 if is_followup else 0.7,  # Higher temperature for follow-ups
                "topK": 40,
                "topP": 0.95,
                "maxOutputTokens": 1024
            }
        }
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                logger.info(f"Calling Gemini API to compose {platform} {'follow-up' if is_followup else 'initial'} message")
                response = await client.post(url, json=payload)
                response.raise_for_status()
                result = response.json()
                
                # Extract content from Gemini response
                if result.get("candidates") and len(result["candidates"]) > 0:
                    candidate = result["candidates"][0]
                    if candidate.get("content") and candidate["content"].get("parts"):
                        parts = candidate["content"]["parts"]
                        if parts and isinstance(parts, list) and len(parts) > 0:
                            text_content = parts[0].get("text", "") if isinstance(parts[0], dict) else ""
                        else:
                            text_content = ""
                        
                        # Parse JSON response
                        try:
                            message_data = json.loads(text_content)
                            body = message_data.get("body", "")
                            
                            if not body:
                                return {
                                    "success": False,
                                    "error": "Empty message body from Gemini",
                                    "body": None
                                }
                            
                            # Strip markdown formatting (asterisks, etc.)
                            body = strip_markdown_formatting(body)
                            
                            logger.info(f"✅ Gemini composed {platform} message ({len(body)} chars)")
                            
                            return {
                                "success": True,
                                "body": body,
                                "error": None
                            }
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to parse Gemini JSON response: {e}")
                            logger.error(f"Response text: {text_content[:200]}")
                            return {
                                "success": False,
                                "error": f"Failed to parse JSON: {e}",
                                "body": None
                            }
                    else:
                        return {
                            "success": False,
                            "error": "No content in Gemini response",
                            "body": None
                        }
                else:
                    error_msg = result.get("error", {}).get("message", "Unknown error")
                    return {
                        "success": False,
                        "error": error_msg,
                        "body": None
                    }
        
        except httpx.HTTPStatusError as e:
            logger.error(f"Gemini API HTTP error for {platform}: {e.response.status_code} - {e.response.text}")
            return {
                "success": False,
                "error": f"HTTP {e.response.status_code}: {e.response.text}",
                "body": None
            }
        except Exception as e:
            logger.error(f"Gemini API call failed for {platform}: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "body": None
            }

