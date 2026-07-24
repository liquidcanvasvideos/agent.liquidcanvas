"""
Email Attachments Schema Initialization

Safety net to ensure the email_attachments table exists when migrations
have not been applied yet. This keeps attachment APIs from 500'ing.
"""
from typing import List, Tuple
import logging
import os
from urllib.parse import quote_plus, urlparse, urlunparse

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)


async def ensure_email_attachments_table_exists(engine: AsyncEngine) -> Tuple[bool, List[str]]:
    """
    Ensure the email_attachments table exists.

    Returns:
        (success, missing_tables)
    """
    required_table = "email_attachments"

    try:
        async with engine.begin() as conn:
            result = await conn.execute(
                text(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = :table_name
                    """
                ),
                {"table_name": required_table},
            )
            exists = result.fetchone() is not None

        if exists:
            logger.info("✅ Email attachments table exists")
            return (True, [])

        logger.warning("⚠️  email_attachments table missing - creating it now...")

        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            logger.error("❌ DATABASE_URL not set - cannot create email_attachments table")
            return (False, [required_table])

        if database_url.startswith("postgresql+asyncpg://"):
            sync_url = database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
        elif database_url.startswith("postgres://"):
            sync_url = database_url.replace("postgres://", "postgresql://", 1)
        else:
            sync_url = database_url

        if "?" in sync_url:
            base_url, query_string = sync_url.split("?", 1)
            query_params = [
                param
                for param in query_string.split("&")
                if not param.lower().startswith(("pgbouncer=", "sslmode="))
            ]
            sync_url = f"{base_url}?{'&'.join(query_params)}" if query_params else base_url

        parsed = urlparse(sync_url)
        if parsed.password:
            encoded_password = quote_plus(parsed.password)
            netloc = f"{parsed.username}:{encoded_password}@{parsed.hostname}"
            if parsed.port:
                netloc += f":{parsed.port}"
            sync_url = urlunparse(
                (parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment)
            )

        from app.models.email_attachment import EmailAttachment

        sync_engine = create_engine(sync_url, echo=False)
        try:
            with sync_engine.begin() as sync_conn:
                EmailAttachment.__table__.create(sync_conn, checkfirst=True)
        finally:
            sync_engine.dispose()

        async with engine.begin() as conn:
            verify = await conn.execute(
                text(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = :table_name
                    """
                ),
                {"table_name": required_table},
            )
            created = verify.fetchone() is not None

        if not created:
            logger.error("❌ Failed to create email_attachments table")
            return (False, [required_table])

        logger.info("✅ email_attachments table created successfully")
        return (True, [])

    except Exception as err:
        logger.error("❌ Failed to ensure email_attachments table exists: %s", err, exc_info=True)
        return (False, [required_table])
