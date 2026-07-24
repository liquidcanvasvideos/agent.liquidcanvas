"""
Shared email sending service
Used by both pipeline send and manual send endpoints
"""
import logging
import os
import smtplib
import base64
import re
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email import encoders
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.prospect import Prospect, SendStatus
from app.models.email_log import EmailLog
from app.models.email_attachment import EmailAttachment
from app.clients.gmail import GmailClient

logger = logging.getLogger(__name__)


def _smtp_configured() -> bool:
    return bool(
        os.getenv("SMTP_HOST")
        and os.getenv("SMTP_PORT")
        and os.getenv("SMTP_USER")
        and os.getenv("SMTP_PASSWORD")
    )


async def _get_attachments(db: AsyncSession, prospect_id: str) -> list[EmailAttachment]:
    result = await db.execute(
        select(EmailAttachment).where(
            (EmailAttachment.scope == "global")
            | (EmailAttachment.prospect_id == prospect_id)
        )
    )
    attachments = result.scalars().all()
    # Avoid auto-attaching global images to every email (Gmail may render them inline)
    filtered: list[EmailAttachment] = []
    for a in attachments:
        if a.scope == "global" and (a.content_type or "").lower().startswith("image/"):
            continue
        filtered.append(a)
    return filtered


def _send_email_smtp(
    to_email: str,
    subject: str,
    body: str,
    cc: Optional[str] = None,
    bcc: Optional[str] = None,
    attachments: Optional[list[EmailAttachment]] = None
) -> Dict[str, Any]:
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    from_email = os.getenv("SMTP_FROM") or username
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() != "false"

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

            start, end = src_match.span("src")
            return tag[:start] + f"cid:{cid}" + tag[end:]

        return img_tag_re.sub(_replace_img_tag, html), inline

    # Root message: mixed (attachments) -> related (html + inline)
    message = MIMEMultipart("mixed")
    message["to"] = to_email
    message["subject"] = subject
    message["from"] = from_email
    if cc:
        message["cc"] = cc
    if bcc:
        message["bcc"] = bcc

    inline_images: list[tuple[str, bytes, str]] = []
    html_body = body
    if body and "data:image" in body:
        try:
            html_body, inline_images = _extract_inline_images(body)
        except Exception:
            html_body = body
            inline_images = []

    logger.info(f"📎 [SMTP] Inline images extracted: {len(inline_images)}")

    related = MIMEMultipart("related")
    alternative = MIMEMultipart("alternative")
    alternative.attach(MIMEText(html_body or "", "html"))
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

    for attachment in attachments or []:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(attachment.data)
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f"attachment; filename=\"{attachment.filename}\"",
        )
        message.attach(part)

    try:
        with smtplib.SMTP(host, port, timeout=30) as server:
            if use_tls:
                server.starttls()
            server.login(username, password)
            recipients: list[str] = [to_email]
            if cc:
                recipients.extend([e.strip() for e in cc.split(",") if e.strip()])
            if bcc:
                recipients.extend([e.strip() for e in bcc.split(",") if e.strip()])
            server.sendmail(from_email, recipients, message.as_string())
        return {"success": True, "message_id": "smtp"}
    except Exception as e:
        logger.error(f"❌ [SEND] SMTP send failed: {e}")
        return {"success": False, "error": "SMTP send failed", "error_detail": str(e)}


async def send_prospect_email(
    prospect: Prospect,
    db: AsyncSession,
    gmail_client: Optional[GmailClient] = None,
    cc: Optional[str] = None,
    bcc: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Send email for a single prospect using Gmail API.
    
    This is the canonical send logic used by both:
    - Pipeline send (batch)
    - Manual send (individual)
    
    Args:
        prospect: Prospect model instance
        db: Database session
        gmail_client: Optional Gmail client (will create if not provided)
        
    Returns:
        Dict with 'success' (bool) and 'message_id' or 'error'
        
    Raises:
        ValueError: If prospect is not sendable
        Exception: If Gmail send fails
    """
    # Validate prospect is sendable
    if not prospect.contact_email:
        raise ValueError("Prospect has no contact email")
    
    if not prospect.draft_subject or not prospect.draft_body:
        raise ValueError("Prospect has no draft email (draft_subject and draft_body required)")
    
    if prospect.send_status == SendStatus.SENT.value:
        raise ValueError("Email already sent for this prospect")
    
    # Get email content - use draft_body (final_body is set after sending)
    subject = prospect.draft_subject
    body = prospect.draft_body

    if not cc:
        cc = getattr(prospect, "cc", None)
    
    if not subject or not body:
        raise ValueError("Prospect has no draft email (draft_subject and draft_body required)")
    
    attachments = await _get_attachments(db, str(prospect.id))

    # SMTP path (app password) if configured
    if _smtp_configured():
        logger.info("📧 [SEND] Using SMTP sender (app password)")
        send_result = _send_email_smtp(
            to_email=prospect.contact_email,
            subject=subject,
            body=body,
            cc=cc,
            bcc=bcc,
            attachments=attachments
        )
    else:
        # Initialize Gmail client if not provided
        if not gmail_client:
            try:
                logger.info("🔧 [SEND] Initializing Gmail client...")
                gmail_client = GmailClient()
                
                # Verify client is properly configured
                if not gmail_client.is_configured():
                    raise ValueError(
                        "Gmail client is not properly configured. "
                        "Set SMTP_* env vars for SMTP or Gmail OAuth env vars."
                    )
                
                # If using refresh token, test that it works
                if gmail_client.refresh_token and not gmail_client.access_token:
                    logger.info("🔄 [SEND] Testing refresh token...")
                    if not await gmail_client.refresh_access_token():
                        raise ValueError(
                            "Gmail refresh token is invalid or expired. "
                            "Please generate a new refresh token or use SMTP app password."
                        )
                
                logger.info("✅ [SEND] Gmail client initialized successfully")
            except ValueError as e:
                error_msg = str(e)
                logger.error(f"❌ [SEND] Gmail client initialization failed: {error_msg}")
                raise ValueError(error_msg)
            except Exception as e:
                logger.error(f"❌ [SEND] Unexpected error initializing Gmail client: {e}", exc_info=True)
                raise ValueError(f"Gmail configuration error: {str(e)}")
    
    # Send email
    logger.info(f"📧 [SEND] Sending email to {prospect.contact_email} (prospect_id: {prospect.id})...")

    if not _smtp_configured():
        try:
            send_result = await gmail_client.send_email(
                to_email=prospect.contact_email,
                subject=subject,
                body=body,
                cc=cc,
                bcc=bcc,
                attachments=attachments,
                is_html=True
            )
        except Exception as send_err:
            logger.error(f"❌ [SEND] Gmail API call failed: {send_err}", exc_info=True)
            raise Exception(f"Failed to send email via Gmail: {send_err}")
    
    if not send_result.get("success"):
        error_msg = send_result.get('error', 'Unknown error')
        error_detail = send_result.get('error_detail', error_msg)
        status_code = send_result.get('status_code')
        
        logger.error(f"❌ [SEND] Gmail returned error: {error_msg}")
        if error_detail and error_detail != error_msg:
            logger.error(f"❌ [SEND] Error details: {error_detail}")
        
        # Provide structured error message
        full_error = f"Gmail API error: {error_msg}"
        if error_detail and error_detail != error_msg:
            full_error += f"\n\n{error_detail}"
        
        raise Exception(full_error)
    
    # Create email log
    email_log = EmailLog(
        prospect_id=prospect.id,
        subject=subject,
        body=body,
        response=send_result
    )
    db.add(email_log)
    
    # Update prospect: move draft_body to final_body, set sent_at, update status
    # Move draft to final_body after sending (preserves sent email content)
    prospect.final_body = prospect.draft_body
    
    # Clear draft after sending (but keep final_body)
    prospect.draft_body = None
    prospect.draft_subject = None
    
    prospect.last_sent = datetime.now(timezone.utc)
    prospect.send_status = SendStatus.SENT.value
    prospect.outreach_status = "sent"  # Legacy field
    
    # Increment follow-up sequence index if this is a follow-up
    if prospect.sequence_index and prospect.sequence_index > 0:
        # This is already a follow-up, increment
        prospect.sequence_index += 1
    elif prospect.thread_id and prospect.thread_id != prospect.id:
        # This is a follow-up (thread_id != own id), set sequence_index to 1
        prospect.sequence_index = 1
    
    # Commit changes
    await db.commit()
    await db.refresh(prospect)
    
    message_id = send_result.get('message_id', 'N/A')
    logger.info(f"✅ [SEND] Email sent to {prospect.contact_email} (message_id: {message_id})")
    logger.info(f"📝 [SEND] Updated prospect {prospect.id} - send_status=SENT, last_sent={prospect.last_sent}")
    
    return {
        "success": True,
        "message_id": message_id,
        "sent_at": prospect.last_sent.isoformat() if prospect.last_sent else None
    }

