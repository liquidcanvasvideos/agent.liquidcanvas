"""
Gmail API client for sending emails
"""
import base64
import json
import re
import uuid
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email import encoders
from typing import Dict, Any, Optional, TYPE_CHECKING
import os
from dotenv import load_dotenv
import logging
import httpx

load_dotenv()

logger = logging.getLogger(__name__)


class GmailClient:
    """Client for Gmail API"""
    
    BASE_URL = "https://gmail.googleapis.com/gmail/v1"
    
    def __init__(
        self,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None
    ):
        """
        Initialize Gmail client
        
        Args:
            access_token: OAuth2 access token (if None, uses GMAIL_ACCESS_TOKEN from env)
            refresh_token: OAuth2 refresh token (if None, uses GMAIL_REFRESH_TOKEN from env)
            client_id: OAuth2 client ID (if None, uses GMAIL_CLIENT_ID from env)
            client_secret: OAuth2 client secret (if None, uses GMAIL_CLIENT_SECRET from env)
        """
        self.access_token = access_token or os.getenv("GMAIL_ACCESS_TOKEN")
        self.refresh_token = refresh_token or os.getenv("GMAIL_REFRESH_TOKEN")
        self.client_id = client_id or os.getenv("GMAIL_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("GMAIL_CLIENT_SECRET")
        
        if not self.access_token and not self.refresh_token:
            raise ValueError("Gmail credentials not configured. Set GMAIL_ACCESS_TOKEN or GMAIL_REFRESH_TOKEN")
    
    def is_configured(self) -> bool:
        """Check if client is properly configured"""
        return bool(self.access_token or (self.refresh_token and self.client_id and self.client_secret))
    
    async def refresh_access_token(self) -> bool:
        """
        Refresh access token using refresh token
        
        Returns:
            True if successful, False otherwise
        """
        if not self.refresh_token or not self.client_id or not self.client_secret:
            logger.error("Cannot refresh token: missing refresh_token, client_id, or client_secret")
            return False
        
        url = "https://oauth2.googleapis.com/token"
        
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token"
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.debug(f"Refreshing Gmail access token with client_id: {self.client_id[:20]}...")
                response = await client.post(url, data=payload)
                
                # Log response status for debugging
                logger.debug(f"Token refresh response status: {response.status_code}")
                
                if response.status_code != 200:
                    error_text = response.text
                    logger.error(f"Token refresh failed with status {response.status_code}: {error_text}")
                    # Provide more helpful error messages
                    if response.status_code == 400:
                        try:
                            error_json = response.json()
                            error_detail = error_json.get("error_description", error_text)
                            if "invalid_grant" in error_detail.lower():
                                logger.error("❌ Invalid refresh token - token may be expired or revoked. Please generate a new refresh token.")
                            elif "invalid_client" in error_detail.lower():
                                logger.error("❌ Invalid client credentials - check GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET")
                        except:
                            pass
                    return False
                
                response.raise_for_status()
                result = response.json()
                
                self.access_token = result.get("access_token")
                if self.access_token:
                    logger.info("✅ Gmail access token refreshed successfully")
                    return True
                else:
                    logger.error("Failed to refresh token: no access_token in response")
                    logger.error(f"Response: {result}")
                    return False
        
        except httpx.HTTPStatusError as e:
            error_text = e.response.text if e.response else "No response text"
            logger.error(f"HTTP error refreshing Gmail access token: {e.response.status_code} - {error_text}")
            return False
        except Exception as e:
            logger.error(f"Failed to refresh Gmail access token: {str(e)}", exc_info=True)
            return False
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        from_email: Optional[str] = None,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        attachments: Optional[list] = None,
        is_html: bool = True
    ) -> Dict[str, Any]:
        """
        Send an email via Gmail API
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Email body (plain text)
            from_email: Sender email (if None, uses authenticated user's email)
        
        Returns:
            Dictionary with send result
        """
        # CRITICAL: Ensure we have a valid access token before attempting to send
        # Try to refresh if we don't have one or if it might be expired
        if not self.access_token:
            logger.warning("⚠️  No access token available, attempting refresh...")
            if not await self.refresh_access_token():
                error_detail = (
                    "Gmail access token is missing and refresh failed. "
                    "Please check:\n"
                    "1. GMAIL_REFRESH_TOKEN is set in environment variables\n"
                    "2. GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET are set\n"
                    "3. Refresh token is valid and not revoked\n"
                    "4. OAuth consent screen is properly configured"
                )
                logger.error(f"❌ {error_detail}")
                return {
                    "success": False,
                    "error": "Failed to obtain Gmail access token",
                    "error_detail": error_detail
                }
        
        def _extract_inline_images(html: str) -> tuple[str, list[tuple[str, bytes, str]]]:
            if not html:
                return html, []

            img_tag_re = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
            src_re = re.compile(
                r"src\s*=\s*(?P<q>['\"])(?P<src>data:(?P<mime>image/[a-zA-Z0-9.+-]+);base64,(?P<b64>[^'\"]+))(?P=q)",
                re.IGNORECASE,
            )

            inline: list[tuple[str, bytes, str]] = []

            def _replace_img_tag(match: re.Match) -> str:
                tag = match.group(0)
                src_match = src_re.search(tag)
                if not src_match:
                    return tag

                mime = (src_match.group("mime") or "image/png").lower()
                b64 = src_match.group("b64") or ""
                try:
                    raw = base64.b64decode(b64)
                except Exception:
                    return tag

                cid = f"img-{uuid.uuid4().hex}"
                inline.append((mime, raw, cid))

                q = src_match.group("q") or '"'
                start, end = src_match.span("src")
                return tag[:start] + f"cid:{cid}" + tag[end:]

            return img_tag_re.sub(_replace_img_tag, html), inline

        # Root: mixed (supports attachments)
        message = MIMEMultipart("mixed")
        message["to"] = to_email
        message["subject"] = subject
        if from_email:
            message["from"] = from_email
        if cc:
            message["cc"] = cc
        if bcc:
            message["bcc"] = bcc

        inline_images: list[tuple[str, bytes, str]] = []
        if is_html and body and "data:image" in body:
            try:
                body, inline_images = _extract_inline_images(body)
            except Exception:
                inline_images = []

        if is_html:
            logger.info(f"📎 [GMAIL] Inline images extracted: {len(inline_images)}")

        if is_html:
            # Body: related -> alternative(html) + inline images
            related = MIMEMultipart("related")
            alternative = MIMEMultipart("alternative")
            alternative.attach(MIMEText(body or "", "html"))
            related.attach(alternative)

            for mime, raw, cid in inline_images:
                ext = (mime.split("/", 1)[1] if "/" in mime else "png")
                filename = f"inline-{cid}.{ext}"
                subtype = ext if ext else "png"
                try:
                    img = MIMEImage(raw, _subtype=subtype)
                    img.replace_header("Content-Type", mime)
                except Exception:
                    maintype, subtype = (mime.split("/", 1) + ["octet-stream"])[:2]
                    img = MIMEBase(maintype, subtype)
                    img.set_payload(raw)
                    encoders.encode_base64(img)
                    img.add_header("Content-Type", mime)

                img.add_header("Content-ID", f"<{cid}>")
                img.add_header("Content-Disposition", "inline", filename=filename)
                img.add_header("Content-Location", filename)
                related.attach(img)

            message.attach(related)
        else:
            message.attach(MIMEText(body or "", "plain"))

        for attachment in attachments or []:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.data)
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f"attachment; filename=\"{attachment.filename}\"",
            )
            message.attach(part)
        
        # Encode message
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        
        url = f"{self.BASE_URL}/users/me/messages/send"
        
        payload = {
            "raw": raw_message
        }
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.info(f"Sending email via Gmail API to: {to_email}")
                response = await client.post(url, headers=headers, json=payload)
                
                # If unauthorized, try refreshing token
                if response.status_code == 401:
                    logger.warning("Gmail API returned 401, attempting token refresh")
                    if await self.refresh_access_token():
                        headers["Authorization"] = f"Bearer {self.access_token}"
                        response = await client.post(url, headers=headers, json=payload)
                
                response.raise_for_status()
                result = response.json()
                
                message_id = result.get("id")
                logger.info(f"✅ Email sent successfully. Message ID: {message_id}")
                
                return {
                    "success": True,
                    "message_id": message_id,
                    "thread_id": result.get("threadId"),
                    "raw_response": result
                }
        
        except httpx.HTTPStatusError as e:
            error_text = e.response.text
            status_code = e.response.status_code
            logger.error(f"❌ Gmail API HTTP error: {status_code} - {error_text}")
            
            # Provide specific error messages for common status codes
            if status_code == 403:
                error_detail = (
                    "Gmail API returned 403 Forbidden. "
                    "This usually means:\n"
                    "1. OAuth scope 'https://www.googleapis.com/auth/gmail.send' is not granted\n"
                    "2. App is not verified (if in production)\n"
                    "3. User has not granted permission to send emails"
                )
            elif status_code == 400:
                error_detail = (
                    "Gmail API returned 400 Bad Request. "
                    "Check email format and message structure."
                )
            else:
                error_detail = f"HTTP {status_code}: {error_text}"
            
            return {
                "success": False,
                "error": f"Gmail API error: HTTP {status_code}",
                "error_detail": error_detail,
                "status_code": status_code
            }
        except Exception as e:
            logger.error(f"❌ Gmail API call failed: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": f"Gmail API error: {str(e)}",
                "error_detail": "An unexpected error occurred while calling Gmail API. Check logs for details."
            }
    
    async def get_user_profile(self) -> Dict[str, Any]:
        """
        Get authenticated user's Gmail profile
        
        Returns:
            Dictionary with user profile info
        """
        if not self.access_token:
            if not await self.refresh_access_token():
                return {"success": False, "error": "Failed to obtain access token"}
        
        url = f"{self.BASE_URL}/users/me/profile"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                return {
                    "success": True,
                    "profile": response.json()
                }
        except Exception as e:
            logger.error(f"Failed to get Gmail profile: {str(e)}")
            return {"success": False, "error": str(e)}

