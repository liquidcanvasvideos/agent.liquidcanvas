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
    
    async def compose_email(
        self,
        domain: str,
        page_title: Optional[str] = None,
        page_url: Optional[str] = None,
        page_snippet: Optional[str] = None,
        contact_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Compose an email using Gemini API
        
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
        
        # Create prompt for structured JSON output
        prompt = f"""You are a professional outreach specialist for an art and creative services company.

Your task is to compose a personalized outreach email to a website owner or content creator.

Context about their website:
{context}

Requirements:
1. The email must be professional, friendly, and personalized
2. It should mention something specific about their website/content
3. It should introduce our art and creative services company
4. It should be concise (2-3 short paragraphs)
5. It should include a clear call-to-action
6. It should be warm but not overly salesy

You MUST return ONLY valid JSON with this exact structure:
{{
  "subject": "Email subject line (max 60 characters)",
  "body": "Email body text (2-3 paragraphs, professional tone)"
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
        
        # Create prompt for follow-up email
        prompt = f"""You are a professional outreach specialist for an art and creative services company.

Your task is to compose a SHORT, WITTY, POLITE follow-up email. This is follow-up #{followup_count} in the thread.

Context about their website:
{context}

Previous emails in this thread:
{previous_emails_text}

Requirements:
1. The email must be SHORT (1-2 paragraphs max)
2. It should be WITTY and CLEVER (use a humorous hook, but not spammy)
3. It should be POLITE and professional
4. Reference the previous attempt SUBTLY (don't be pushy)
5. It should be memorable and stand out
6. Keep it concise - people are busy

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

