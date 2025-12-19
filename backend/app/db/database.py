"""
Database configuration and session management
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from typing import AsyncGenerator
import os
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
    logger.info(f"📊 DATABASE_URL: {safe_url}")
else:
    logger.warning("⚠️  DATABASE_URL environment variable not set!")

# Convert postgresql:// to postgresql+asyncpg:// if needed
if raw_database_url.startswith("postgresql://"):
    DATABASE_URL = raw_database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    logger.info("Converted postgresql:// to postgresql+asyncpg://")
elif raw_database_url.startswith("postgres://"):
    DATABASE_URL = raw_database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    logger.info("Converted postgres:// to postgresql+asyncpg://")
else:
    DATABASE_URL = raw_database_url
    logger.info("Using DATABASE_URL as-is (already in correct format)")

# Log connection details (without password)
if "@" in DATABASE_URL:
    try:
        # Extract host and port for logging
        parts = DATABASE_URL.split("@")
        if len(parts) > 1:
            host_port_db = parts[1]
            if "/" in host_port_db:
                host_port = host_port_db.split("/")[0]
                logger.info(f"Attempting to connect to database at: {host_port}")
    except Exception:
        pass

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Set to False in production (was True for debugging)
    future=True,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

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

