"""
Alembic environment configuration for database migrations

ISOLATED: This file imports ONLY SQLAlchemy metadata.
It does NOT import application startup logic or create database connections.
"""
from logging.config import fileConfig
from sqlalchemy import pool
from alembic import context
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# CRITICAL: Prevent engine creation during Alembic import
# Temporarily patch create_async_engine to prevent engine creation
_original_create_async_engine = None
try:
    import sqlalchemy.ext.asyncio
    _original_create_async_engine = sqlalchemy.ext.asyncio.create_async_engine
    
    def _mock_create_async_engine(*args, **kwargs):
        """Mock function that prevents engine creation during Alembic import"""
        # Return a minimal mock object
        class MockEngine:
            def __init__(self):
                pass
        return MockEngine()
    
    # Patch before importing app.db.database
    sqlalchemy.ext.asyncio.create_async_engine = _mock_create_async_engine
    
    # Now import Base and models - engine creation will be mocked
    from app.db.database import Base
    # Import all models so Alembic can detect them for migrations
    from app.models import Prospect, Job, EmailLog, Settings, DiscoveryQuery, ScraperHistory
    from app.models.social import SocialProfile, SocialDiscoveryJob, SocialDraft, SocialMessage
    
    # Restore original function
    sqlalchemy.ext.asyncio.create_async_engine = _original_create_async_engine
    _original_create_async_engine = None
    
    # Get metadata from Base
    target_metadata = Base.metadata
    
except Exception as e:
    # Restore original function if we had it
    if _original_create_async_engine:
        import sqlalchemy.ext.asyncio
        sqlalchemy.ext.asyncio.create_async_engine = _original_create_async_engine
    
    # If imports fail, log but continue - Alembic might still work
    import logging
    logging.warning(f"Could not import models for Alembic: {e}")
    # Create minimal metadata as fallback
    from sqlalchemy.orm import declarative_base
    _fallback_base = declarative_base()
    target_metadata = _fallback_base.metadata

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Get database URL from environment
database_url = os.getenv("DATABASE_URL", "postgresql://art_outreach:art_outreach@localhost:5432/art_outreach")
# Convert asyncpg URL to psycopg2 for Alembic (Alembic uses sync engine)
if database_url.startswith("postgresql+asyncpg://"):
    database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
config.set_main_option("sqlalchemy.url", database_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    from sqlalchemy import create_engine
    
    # Use sync engine for migrations (Alembic doesn't work well with async)
    database_url = config.get_main_option("sqlalchemy.url")
    connectable = create_engine(database_url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
