"""
Google Gemini API client for email composition
"""
import httpx
from typing import Dict, Any, Optional, List
import os
from dotenv import load_dotenv
import logging
import json

load_dotenv()

logger = logging.getLogger(__name__)


class GeminiClient:
    """Client for Google Gemini API"""
    
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Gemini client
        
        Args:
            api_key: Gemini API key (if None, uses GEMINI_API_KEY from env)
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        
        if not self.api_key:
            raise ValueError("Gemini API key not configured. Set GEMINI_API_KEY")
    
    def is_configured(self) -> bool:
        """Check if client is properly configured"""
        return bool(self.api_key and self.api_key.strip())
    
    async def _search_liquid_canvas_info(self) -> str:
        """
        Search for information about Liquid Canvas using Gemini's web search
        
        Returns:
            String with information about Liquid Canvas
        """
        search_url = f"{self.BASE_URL}/models/gemini-2.0-flash-exp:generateContent?key={self.api_key}"
        
        search_prompt = """Search for information about Liquid Canvas (liquidcanvas.art). 
Find out:
1. What services they offer
2. What type of art/creative work they do
3. Their unique value proposition
4. Any notable projects or work
5. Their website URL: liquidcanvas.art

Return a concise summary (2-3 sentences) about Liquid Canvas that can be used in outreach emails."""
        
        search_payload = {
            "contents": [{
                "parts": [{
                    "text": search_prompt
                }]
            }],
            "tools": [{
                "googleSearchRetrieval": {}
            }],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 512
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
        
        # Fallback default information
        return """Liquid Canvas (liquidcanvas.art) is an art and creative services company specializing in innovative visual solutions and artistic collaborations. We offer custom creative services, digital art, and artistic partnerships for businesses and creators."""
    
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
        url = f"{self.BASE_URL}/models/gemini-2.0-flash-exp:generateContent?key={self.api_key}"
        
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
        return f"This appears to be a {page_title or 'business'} in the {domain} domain. Liquid Canvas could offer creative services and artistic collaborations relevant to their needs."
    
    async def compose_email(
        self,
        domain: str,
        page_title: Optional[str] = None,
        page_url: Optional[str] = None,
        page_snippet: Optional[str] = None,
        contact_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Compose an email using Gemini API with Liquid Canvas information.
        
        CRITICAL: Reads website content first, builds positioning summary, then generates email.
        
        Args:
            domain: Website domain
            page_title: Page title
            page_url: Page URL
            page_snippet: Page description/snippet
            contact_name: Contact name (if available)
        
        Returns:
            Dictionary with subject and body
        """
        url = f"{self.BASE_URL}/models/gemini-2.0-flash-exp:generateContent?key={self.api_key}"
        
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
        context_parts = []
        if page_title:
            context_parts.append(f"Website Title: {page_title}")
        if domain:
            context_parts.append(f"Domain: {domain}")
        if page_snippet:
            context_parts.append(f"Description: {page_snippet}")
        if page_url:
            context_parts.append(f"URL: {page_url}")
        if website_content:
            context_parts.append(f"Website Content Preview: {website_content[:500]}...")
        
        context = "\n".join(context_parts) if context_parts else f"Website: {domain}"
        
        # Create prompt for structured JSON output
        prompt = f"""You are a professional outreach specialist for Liquid Canvas (liquidcanvas.art), an art and creative services company.

ABOUT LIQUID CANVAS (READ THIS FIRST):
{liquid_canvas_info}

Website: https://liquidcanvas.art

POSITIONING SUMMARY (How to approach this recipient):
{positioning_summary}

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
                "maxOutputTokens": 1024,
                "responseMimeType": "application/json"
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
        url = f"{self.BASE_URL}/models/gemini-2.0-flash-exp:generateContent?key={self.api_key}"
        
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
                "maxOutputTokens": 1024,
                "responseMimeType": "application/json"
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
                return {
                    "success": True,
                    "subject": email_data.get("subject", f"Partnership Opportunity - {domain}"),
                    "body": email_data.get("body", text)
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
        contact_name: Optional[str] = None
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
            page_title: Page title
            page_url: Page URL
            page_snippet: Page description/snippet
            contact_name: Contact name (if available)
        
        Returns:
            Dictionary with subject and body
        """
        url = f"{self.BASE_URL}/models/gemini-2.0-flash-exp:generateContent?key={self.api_key}"
        
        # Build context for the email
        context_parts = []
        if page_title:
            context_parts.append(f"Website Title: {page_title}")
        if domain:
            context_parts.append(f"Domain: {domain}")
        if page_snippet:
            context_parts.append(f"Description: {page_snippet}")
        if page_url:
            context_parts.append(f"URL: {page_url}")
        
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
        
        # Create prompt for follow-up email
        prompt = f"""You are a professional outreach specialist for Liquid Canvas (liquidcanvas.art), an art and creative services company.

About Liquid Canvas:
{liquid_canvas_info}

Website: https://liquidcanvas.art

Your task is to compose a SHORT, PLAYFUL, LIGHT, WITTY follow-up email. This is follow-up #{followup_count} in the thread.

Context about their website:
{context}

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
                "maxOutputTokens": 1024,
                "responseMimeType": "application/json"
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
        url = f"{self.BASE_URL}/models/gemini-2.0-flash-exp:generateContent?key={self.api_key}"
        
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
                "maxOutputTokens": 1024,
                "responseMimeType": "application/json"
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

