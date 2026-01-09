"""
Database configuration and session management

ISOLATED: Engine creation is lazy to prevent conflicts with Alembic imports.
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from typing import AsyncGenerator
import os
import sys
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass  # Continue without .env if it has issues
import logging

logger = logging.getLogger(__name__)

# Database URL from environment
# Render provides postgresql:// but we need postgresql+asyncpg:// for async SQLAlchemy
raw_database_url = os.getenv("DATABASE_URL")

if not raw_database_url:
    logger.warning("DATABASE_URL environment variable not set! Using default local database.")
    raw_database_url = "postgresql+asyncpg://art_outreach:art_outreach@localhost:5432/art_outreach"

# Log database URL info (without exposing password)
if raw_database_url:
    # Mask password in URL for logging
    safe_url = raw_database_url
    if "@" in safe_url:
        parts = safe_url.split("@")
        if ":" in parts[0]:
            user_pass = parts[0].split(":")
            if len(user_pass) >= 2:
                safe_url = f"{user_pass[0]}:****@{parts[1]}"
    logger.info("=" * 80)
    logger.info(f"📊 RAW DATABASE_URL (masked): {safe_url}")
    logger.info(f"📊 DATABASE_URL length: {len(raw_database_url)} characters")
    # Extract and log hostname immediately
    if "@" in raw_database_url:
        try:
            host_part = raw_database_url.split("@")[1].split("/")[0]
            hostname = host_part.split(":")[0]
            logger.info(f"📊 EXTRACTED HOSTNAME: {hostname}")
            logger.info(f"📊 HOSTNAME LENGTH: {len(hostname)} characters")
            logger.info(f"📊 HOSTNAME PARTS: {len(hostname.split('.'))} parts")
            if ".supabase.co" in hostname:
                if len(hostname.split(".")) < 4:
                    logger.error("=" * 80)
                    logger.error(f"❌ CRITICAL: HOSTNAME IS TRUNCATED!")
                    logger.error(f"❌ Expected: db.[ref].supabase.co (4+ parts)")
                    logger.error(f"❌ Got: {hostname} ({len(hostname.split('.'))} parts)")
                    logger.error("=" * 80)
                else:
                    logger.info(f"✅ Hostname format looks correct")
        except Exception as e:
            logger.error(f"❌ Error extracting hostname: {e}")
    logger.info("=" * 80)
else:
    logger.warning("⚠️  DATABASE_URL environment variable not set!")

# Convert postgresql:// to postgresql+asyncpg:// if needed
# Also properly encode special characters in password to prevent URL parsing issues
from urllib.parse import quote

def encode_password_in_url(url: str) -> str:
    """
    Manually extract and encode the password in a database URL.
    This is necessary because urlparse can fail on URLs with special characters.
    """
    try:
        # Find the scheme (postgresql://, postgresql+asyncpg://, etc.)
        scheme_end = url.find("://")
        if scheme_end == -1:
            logger.warning("Invalid URL format: no :// found")
            return url  # Not a valid URL format
        
        scheme = url[:scheme_end + 3]
        rest = url[scheme_end + 3:]
        
        # Find the @ symbol which separates credentials from host
        at_pos = rest.find("@")
        if at_pos == -1:
            logger.debug("No credentials found in URL (no @ symbol)")
            return url  # No credentials, return as-is
        
        credentials = rest[:at_pos]
        host_and_path = rest[at_pos + 1:]
        
        # Split username and password
        # IMPORTANT: Use rsplit with maxsplit=1 to handle passwords that might contain ':'
        if ":" not in credentials:
            logger.debug("No password found in URL (no : in credentials)")
            return url  # No password, return as-is
        
        # Use rsplit to get the LAST colon (in case password contains colons)
        parts = credentials.rsplit(":", 1)
        if len(parts) != 2:
            logger.warning(f"Unexpected credentials format, using as-is")
            return url
        
        username = parts[0]
        password = parts[1]
        
        # Log (without exposing password) for debugging
        original_host = host_and_path.split("/")[0].split(":")[0]
        logger.info(f"🔐 Encoding password for user: {username}, host: {original_host}")
        logger.debug(f"Password length: {len(password)} characters")
        
        # Check if password is already URL-encoded (contains %)
        if "%" in password:
            logger.info("ℹ️  Password appears to already be URL-encoded, skipping re-encoding")
            return url
        
        # URL-encode the password (use quote, not quote_plus, for passwords)
        # quote() properly handles special characters like !, @, #, etc.
        encoded_password = quote(password, safe="")
        
        # Reconstruct the URL
        encoded_url = f"{scheme}{username}:{encoded_password}@{host_and_path}"
        
        # Verify the hostname is preserved
        if "@" in encoded_url:
            encoded_host = encoded_url.split("@")[1].split("/")[0].split(":")[0]
            if encoded_host != original_host:
                logger.error(f"❌ CRITICAL: Hostname mismatch after encoding!")
                logger.error(f"   Original: {original_host}")
                logger.error(f"   Encoded:  {encoded_host}")
                logger.error(f"   This will cause connection failures!")
            else:
                logger.info(f"✅ Password encoded successfully, hostname preserved: {encoded_host}")
        
        return encoded_url
    except Exception as e:
        logger.error(f"Could not encode password in URL: {e}", exc_info=True)
        return url

# Convert scheme first
if raw_database_url.startswith("postgresql://"):
    temp_url = raw_database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif raw_database_url.startswith("postgres://"):
    temp_url = raw_database_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif raw_database_url.startswith("postgresql+asyncpg://"):
    temp_url = raw_database_url
else:
    temp_url = raw_database_url

# Encode password to handle special characters (critical for Supabase)
DATABASE_URL = encode_password_in_url(temp_url)
if DATABASE_URL != temp_url:
    logger.info("✅ Properly encoded password in DATABASE_URL to handle special characters")
else:
    logger.info("ℹ️  No password encoding applied (password may already be encoded or not present)")

# Log the hostname to verify it's correct (without exposing password)
try:
    if "@" in DATABASE_URL:
        host_part = DATABASE_URL.split("@")[1].split("/")[0]
        logger.info(f"📊 Connection target: {host_part}")
        # Verify hostname is complete (not truncated)
        if ".supabase.co" in host_part:
            if len(host_part.split(".")) < 4:
                logger.error(f"❌ CRITICAL: Hostname appears truncated! Expected full Supabase hostname, got: {host_part}")
            else:
                logger.info(f"✅ Hostname appears complete: {host_part}")
    else:
        logger.warning("⚠️  No @ symbol found in DATABASE_URL - cannot extract hostname")
except Exception as e:
    logger.error(f"❌ Error extracting hostname: {e}", exc_info=True)

# Note: SSL for asyncpg is configured via connect_args, not URL parameters
# We'll handle SSL in the engine creation below

# Log connection details (without password) - enhanced verification
if "@" in DATABASE_URL:
    try:
        # Extract host and port for logging
        parts = DATABASE_URL.split("@")
        if len(parts) > 1:
            host_port_db = parts[1]
            if "/" in host_port_db:
                host_port = host_port_db.split("/")[0]
                logger.info(f"📊 Attempting to connect to database at: {host_port}")
                # Verify hostname is complete (not truncated)
                hostname = host_port.split(":")[0]
                if ".supabase.co" in hostname:
                    if len(hostname.split(".")) < 4:
                        logger.error(f"❌ CRITICAL: Hostname appears truncated! Expected full Supabase hostname, got: {hostname}")
                    else:
                        logger.info(f"✅ Hostname appears complete: {hostname}")
    except Exception as e:
        logger.error(f"❌ Error extracting connection details: {e}", exc_info=True)

# CRITICAL: Lazy engine initialization to prevent conflicts with Alembic
# Alembic imports this module but uses its own sync engine
# We detect Alembic context and delay engine creation

_engine_instance = None
_engine_lock = None

def _get_engine():
    """Get or create the async engine - lazy initialization"""
    global _engine_instance, _engine_lock
    if _engine_instance is None:
        import threading
        if _engine_lock is None:
            _engine_lock = threading.Lock()
        with _engine_lock:
            if _engine_instance is None:
                # Supabase requires SSL connections - configure for asyncpg
                connect_args = {}
                if ".supabase.co" in DATABASE_URL:
                    # asyncpg uses ssl context for SSL connections
                    # For Supabase, we need to require SSL
                    import ssl
                    connect_args = {
                        "ssl": ssl.create_default_context()
                    }
                    logger.info("✅ Configured SSL for Supabase connection")
                
                # Log the final URL being used (without password) for debugging
                try:
                    if "@" in DATABASE_URL:
                        final_host = DATABASE_URL.split("@")[1].split("/")[0].split(":")[0]
                        logger.info(f"🔗 Creating engine with hostname: {final_host}")
                        if ".supabase.co" in final_host and len(final_host.split(".")) < 4:
                            logger.error(f"❌ CRITICAL: Hostname is truncated in final DATABASE_URL: {final_host}")
                            logger.error(f"❌ This will cause connection failures!")
                except Exception as e:
                    logger.warning(f"Could not log final hostname: {e}")
                
                _engine_instance = create_async_engine(
                    DATABASE_URL,
                    echo=False,  # Set to False in production (was True for debugging)
                    future=True,
                    pool_pre_ping=True,
                    pool_size=10,
                    max_overflow=20,
                    connect_args=connect_args
                )
                logger.info("✅ Async engine created successfully")
    return _engine_instance

# Check if we're being imported by Alembic
# Alembic runs as a script, so sys.argv[0] will contain 'alembic'
_is_alembic_context = (
    len(sys.argv) > 0 and 'alembic' in sys.argv[0].lower()
) or any('alembic' in str(arg).lower() for arg in sys.argv)

if _is_alembic_context:
    # Being imported by Alembic - don't create engine
    # Create a proxy that will create engine on first use (but Alembic won't use it)
    class EngineProxy:
        """Proxy for engine that creates it lazily - Alembic won't use this"""
        def __getattr__(self, name):
            return getattr(_get_engine(), name)
        def __call__(self, *args, **kwargs):
            return _get_engine()(*args, **kwargs)
        def __enter__(self):
            return _get_engine().__enter__()
        def __exit__(self, *args):
            return _get_engine().__exit__(*args)
    engine = EngineProxy()
else:
    # Normal application import - create engine immediately
    engine = _get_engine()

# Create async session factory
# Use lazy engine access for session factory
_session_factory_instance = None
_session_factory_lock = None

def _get_session_factory():
    """Get or create the session factory"""
    global _session_factory_instance, _session_factory_lock
    if _session_factory_instance is None:
        import threading
        if _session_factory_lock is None:
            _session_factory_lock = threading.Lock()
        with _session_factory_lock:
            if _session_factory_instance is None:
                _session_factory_instance = async_sessionmaker(
                    _get_engine(),
                    class_=AsyncSession,
                    expire_on_commit=False,
                    autocommit=False,
                    autoflush=False
                )
    return _session_factory_instance

if _is_alembic_context:
    # For Alembic, create a proxy (but Alembic won't use it)
    class SessionFactoryProxy:
        def __call__(self, *args, **kwargs):
            return _get_session_factory()(*args, **kwargs)
        def __getattr__(self, name):
            return getattr(_get_session_factory(), name)
    AsyncSessionLocal = SessionFactoryProxy()
else:
    AsyncSessionLocal = _get_session_factory()

# Base class for models
Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting database session
    """
    try:
        async with AsyncSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"Database session error: {e}", exc_info=True)
                raise
            finally:
                await session.close()
    except Exception as e:
        logger.error(f"Failed to create database session: {e}", exc_info=True)
        logger.error(f"DATABASE_URL is set: {bool(os.getenv('DATABASE_URL'))}")
        if "@" in DATABASE_URL:
            try:
                parts = DATABASE_URL.split("@")
                if len(parts) > 1:
                    host_port = parts[1].split("/")[0]
                    logger.error(f"Attempted to connect to: {host_port}")
            except Exception:
                pass
        raise
