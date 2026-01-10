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
        # But be careful - some passwords might legitimately contain %
        # Check if it looks like URL encoding (has % followed by hex digits)
        import re
        if re.search(r'%[0-9A-Fa-f]{2}', password):
            logger.info("ℹ️  Password appears to already be URL-encoded, skipping re-encoding")
            logger.debug(f"Password contains URL-encoded characters: {len(re.findall(r'%[0-9A-Fa-f]{2}', password))} encoded sequences")
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

# CRITICAL: Check if SSL is required before removing query params
# We need to know if sslmode=require was present to configure SSL via connect_args
requires_ssl = False
if "?" in DATABASE_URL:
    query_string = DATABASE_URL.split("?", 1)[1]
    if "sslmode=require" in query_string or "sslmode=REQUIRE" in query_string:
        requires_ssl = True
        logger.info("ℹ️  Detected sslmode=require in connection string")

# CRITICAL: Remove sslmode query parameter from URL
# asyncpg doesn't accept sslmode as a parameter - SSL is configured via connect_args
if "?" in DATABASE_URL:
    url_parts = DATABASE_URL.split("?", 1)
    base_url = url_parts[0]
    query_string = url_parts[1] if len(url_parts) > 1 else ""
    
    # Remove sslmode parameter from query string
    if query_string:
        query_params = []
        for param in query_string.split("&"):
            if not param.startswith("sslmode="):
                query_params.append(param)
        
        if query_params:
            DATABASE_URL = f"{base_url}?{'&'.join(query_params)}"
        else:
            DATABASE_URL = base_url
        
        if "sslmode=" in query_string:
            logger.info("ℹ️  Removed sslmode query parameter (SSL configured via connect_args instead)")

# Store original DATABASE_URL for IPv4 resolution at runtime
# We'll resolve IPv4 when the engine is actually created, not at import time
# This avoids DNS resolution failures during module import
_original_database_url = DATABASE_URL

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

def get_engine():
    """Get the single async engine instance (public API)"""
    return _get_engine()

def _resolve_to_ipv4_sync(url: str) -> str:
    """
    Resolve Supabase hostname to IPv4 address synchronously.
    Returns URL with IPv4 address, or original URL if resolution fails.
    Uses multiple DNS resolution strategies for robustness.
    
    NOTE: If using connection pooler (port 6543 or pgbouncer=true),
    skip IPv4 resolution as the pooler handles IPv4 connections.
    """
    if "@" not in url or ".supabase.co" not in url:
        return url
    
    # Skip IPv4 resolution for connection pooler - it handles IPv4 internally
    if ":6543" in url or "pgbouncer=true" in url.lower():
        logger.info("ℹ️  Using connection pooler (port 6543) - skipping IPv4 resolution (pooler handles IPv4)")
        return url
    
    try:
        import socket
        import time
        
        # Extract hostname and port from URL
        scheme_part = url.split("://")[0] + "://"
        rest_after_scheme = url.split("://")[1]
        
        if "@" not in rest_after_scheme:
            return url
        
        creds_part = rest_after_scheme.split("@")[0]
        host_path_part = rest_after_scheme.split("@")[1]
        
        # Extract hostname and port
        if "/" in host_path_part:
            host_port_part = host_path_part.split("/")[0]
            path_part = "/" + "/".join(host_path_part.split("/")[1:])
        else:
            host_port_part = host_path_part
            path_part = ""
        
        if ":" in host_port_part:
            hostname, port_str = host_port_part.rsplit(":", 1)
            port = int(port_str)
        else:
            hostname = host_port_part
            port = 5432
        
        # Try multiple resolution strategies
        logger.info(f"🔍 Resolving {hostname} to IPv4 address...")
        max_retries = 5
        wait_base = 1
        
        for attempt in range(max_retries):
            try:
                # Strategy 1: Use getaddrinfo with AF_INET (IPv4 only)
                # Add timeout to prevent hanging
                socket.setdefaulttimeout(5)  # 5 second timeout
                addr_info = socket.getaddrinfo(hostname, port, socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
                socket.setdefaulttimeout(None)  # Reset timeout
                
                if addr_info:
                    ipv4_address = addr_info[0][4][0]
                    logger.info(f"✅ Resolved {hostname} to IPv4: {ipv4_address} (attempt {attempt + 1})")
                    
                    # Reconstruct URL with IPv4 address
                    resolved_url = f"{scheme_part}{creds_part}@{ipv4_address}:{port}{path_part}"
                    logger.info(f"✅ Using IPv4 address for connection: {ipv4_address}:{port}")
                    return resolved_url
                else:
                    logger.warning(f"⚠️  getaddrinfo returned empty result for {hostname} (attempt {attempt + 1})")
                    
            except socket.gaierror as gai_err:
                # DNS error - retry with exponential backoff
                socket.setdefaulttimeout(None)  # Reset timeout
                if attempt < max_retries - 1:
                    wait_time = wait_base * (2 ** attempt)  # 1s, 2s, 4s, 8s, 16s
                    logger.warning(f"⚠️  DNS resolution failed (attempt {attempt + 1}/{max_retries}): {gai_err}")
                    logger.info(f"⏳ Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"❌ Failed to resolve {hostname} to IPv4 after {max_retries} attempts: {gai_err}")
                    
                    # Last resort: Try gethostbyname (deprecated but sometimes works)
                    try:
                        logger.info("🔄 Trying fallback DNS resolution method (gethostbyname)...")
                        socket.setdefaulttimeout(5)
                        ipv4_address = socket.gethostbyname(hostname)
                        socket.setdefaulttimeout(None)
                        logger.info(f"✅ Fallback resolution succeeded: {hostname} -> {ipv4_address}")
                        resolved_url = f"{scheme_part}{creds_part}@{ipv4_address}:{port}{path_part}"
                        logger.info(f"✅ Using IPv4 address from fallback: {ipv4_address}:{port}")
                        return resolved_url
                    except Exception as fallback_err:
                        socket.setdefaulttimeout(None)
                        logger.error(f"❌ Fallback DNS resolution also failed: {fallback_err}")
                        
                        # Last last resort: Check if SUPABASE_IPV4 env var is set
                        fallback_ip = os.getenv("SUPABASE_IPV4")
                        if fallback_ip:
                            logger.warning(f"⚠️  Using SUPABASE_IPV4 environment variable: {fallback_ip}")
                            resolved_url = f"{scheme_part}{creds_part}@{fallback_ip}:{port}{path_part}"
                            logger.info(f"✅ Using IPv4 from SUPABASE_IPV4 env var: {fallback_ip}:{port}")
                            return resolved_url
                        else:
                            logger.error("⚠️  No SUPABASE_IPV4 env var set. Will attempt connection with hostname (may fail with IPv6)")
                        
            except socket.timeout:
                socket.setdefaulttimeout(None)
                if attempt < max_retries - 1:
                    wait_time = wait_base * (2 ** attempt)
                    logger.warning(f"⚠️  DNS resolution timed out (attempt {attempt + 1}/{max_retries})")
                    logger.info(f"⏳ Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"❌ DNS resolution timed out after {max_retries} attempts")
                    
            except Exception as resolve_err:
                socket.setdefaulttimeout(None)
                if attempt < max_retries - 1:
                    wait_time = wait_base * (2 ** attempt)
                    logger.warning(f"⚠️  Unexpected error during resolution (attempt {attempt + 1}/{max_retries}): {resolve_err}")
                    logger.info(f"⏳ Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"❌ Failed to resolve {hostname} to IPv4: {resolve_err}")
                    logger.error("⚠️  Will attempt connection with hostname (connection may fail if IPv6 unavailable)")
        
        # Final check: SUPABASE_IPV4 env var as absolute last resort
        # Extract port and path again in case we're here from timeout/other errors
        fallback_ip = os.getenv("SUPABASE_IPV4")
        if fallback_ip:
            logger.warning(f"⚠️  All DNS resolution attempts failed. Using SUPABASE_IPV4 environment variable: {fallback_ip}")
            # Re-extract components to build URL
            scheme_part = url.split("://")[0] + "://"
            rest_after_scheme = url.split("://")[1]
            creds_part = rest_after_scheme.split("@")[0]
            host_path_part = rest_after_scheme.split("@")[1]
            if "/" in host_path_part:
                host_port_part = host_path_part.split("/")[0]
                path_part = "/" + "/".join(host_path_part.split("/")[1:])
            else:
                host_port_part = host_path_part
                path_part = ""
            
            # Extract port from original URL
            if ":" in host_port_part:
                _, port_str = host_port_part.rsplit(":", 1)
                port = int(port_str)
            else:
                port = 5432
            
            resolved_url = f"{scheme_part}{creds_part}@{fallback_ip}:{port}{path_part}"
            logger.info(f"✅ Using IPv4 from SUPABASE_IPV4 env var: {fallback_ip}:{port}")
            return resolved_url
        else:
            logger.warning(f"⚠️  No SUPABASE_IPV4 environment variable set. You can set it to bypass DNS resolution.")
            logger.warning(f"⚠️  Will attempt connection with original hostname (may fail if IPv6 unavailable on Render)")
        
        return url  # Return original URL if all resolution attempts fail
    except Exception as resolve_err:
        logger.error(f"❌ Unexpected error during IPv4 resolution: {resolve_err}")
        return url  # Return original URL on any error


def _get_engine():
    """Get or create the async engine - lazy initialization"""
    global _engine_instance, _engine_lock, DATABASE_URL
    if _engine_instance is None:
        import threading
        if _engine_lock is None:
            _engine_lock = threading.Lock()
        with _engine_lock:
            if _engine_instance is None:
                # CRITICAL: Resolve to IPv4 at runtime (not import time)
                # This ensures DNS is available when we actually need it
                resolved_url = _resolve_to_ipv4_sync(_original_database_url)
                if resolved_url != _original_database_url:
                    DATABASE_URL = resolved_url
                    logger.info("✅ DATABASE_URL updated with IPv4 address")
                
                # Configure SSL for asyncpg (required for Supabase or when sslmode=require)
                connect_args = {}
                is_supabase = ".supabase.co" in DATABASE_URL or ".supabase.co" in _original_database_url
                
                if is_supabase or requires_ssl:
                    # asyncpg uses ssl context for SSL connections
                    import ssl
                    connect_args = {
                        "ssl": ssl.create_default_context()
                    }
                    if is_supabase:
                        logger.info("✅ Configured SSL for Supabase connection")
                    elif requires_ssl:
                        logger.info("✅ Configured SSL (sslmode=require was in connection string)")
                
                # Log the final URL being used (without password) for debugging
                try:
                    if "@" in DATABASE_URL:
                        final_host = DATABASE_URL.split("@")[1].split("/")[0].split(":")[0]
                        logger.info(f"🔗 Creating engine with connection target: {final_host}")
                        # Check if it's an IPv4 address
                        import ipaddress
                        try:
                            ipaddress.IPv4Address(final_host)
                            logger.info(f"✅ Using IPv4 address: {final_host}")
                        except ValueError:
                            # Not an IPv4 address - might be hostname or IPv6
                            if "." in final_host:
                                logger.warning(f"⚠️  Using hostname (not IPv4): {final_host}")
                            else:
                                logger.warning(f"⚠️  Using hostname/IPv6: {final_host}")
                except Exception as e:
                    logger.warning(f"Could not log final connection target: {e}")
                
                _engine_instance = create_async_engine(
                    DATABASE_URL,
                    echo=False,
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


async def test_connection() -> bool:
    """
    Test database connection by running SELECT 1.
    Returns True if successful, raises exception if failed.
    This is called at startup to fail fast if DB is unreachable.
    """
    try:
        from sqlalchemy import text
        engine = _get_engine()
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1"))
            result.scalar()
        logger.info("✅ Database connection test passed")
        return True
    except Exception as e:
        logger.error("=" * 80)
        logger.error("❌ CRITICAL: Database connection test FAILED")
        logger.error(f"❌ Error: {e}")
        logger.error("=" * 80)
        logger.error("❌ Application will not start until database is reachable")
        logger.error("=" * 80)
        raise
