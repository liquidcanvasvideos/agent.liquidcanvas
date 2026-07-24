"""
Social Outreach Schema Initialization

Feature-scoped schema initialization for social outreach tables.
If migrations fail or tables are missing, this ensures they exist.

This is a safety net - migrations should handle table creation,
but this provides graceful degradation if migrations fail.
"""
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
import logging
import os
from typing import Tuple, List

logger = logging.getLogger(__name__)


async def ensure_social_tables_exist(engine: AsyncEngine) -> Tuple[bool, List[str]]:
    """
    Ensure social outreach tables exist.
    
    If tables are missing, create them using SQLAlchemy metadata.
    This is a safety net for when migrations fail or haven't run.
    
    Returns:
        (success, missing_tables)
        - success: True if all tables now exist
        - missing_tables: List of tables that still don't exist (empty if success)
    """
    required_tables = {
        'social_profiles',
        'social_discovery_jobs',
        'social_drafts',
        'social_messages'
    }
    
    try:
        # Check which tables exist
        async with engine.begin() as conn:
            tables_tuple = tuple(required_tables)
            result = await conn.execute(
                text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = ANY(:tables)
                """),
                {"tables": tables_tuple}
            )
            existing_tables = {row[0] for row in result.fetchall()}
            missing_tables = required_tables - existing_tables
        
        if not missing_tables:
            logger.info("✅ All social outreach tables exist")
            return (True, [])
        
        logger.warning(f"⚠️  Missing social tables: {', '.join(missing_tables)}")
        logger.warning("⚠️  Attempting to create missing tables using SQLAlchemy metadata...")
        
        # Create missing tables using SQLAlchemy metadata
        # This requires a synchronous engine for Base.metadata.create_all()
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            logger.error("❌ DATABASE_URL not set - cannot create tables")
            return (False, list(missing_tables))
        
        # Convert asyncpg URL to psycopg2 for synchronous operations
        if database_url.startswith("postgresql+asyncpg://"):
            sync_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
        else:
            sync_url = database_url
        
        # Import social models to register them with Base.metadata
        from app.models.social import (
            SocialProfile,
            SocialDiscoveryJob,
            SocialDraft,
            SocialMessage
        )
        from app.db.database import Base
        
        # Create synchronous engine for table creation
        sync_engine = create_engine(sync_url, echo=False)
        
        try:
            # Create only social tables
            # We need to filter Base.metadata.tables to only include social tables
            social_table_names = {
                'social_profiles',
                'social_discovery_jobs',
                'social_drafts',
                'social_messages'
            }
            
            # Create tables that are missing
            with sync_engine.begin() as sync_conn:
                inspector = inspect(sync_engine)
                existing = set(inspector.get_table_names())
                
                for table_name in social_table_names:
                    if table_name not in existing and table_name in Base.metadata.tables:
                        logger.info(f"📝 Creating table: {table_name}")
                        Base.metadata.tables[table_name].create(sync_conn, checkfirst=True)
                        logger.info(f"✅ Created table: {table_name}")
            
            # Verify tables were created
            async with engine.begin() as conn:
                result = await conn.execute(
                    text("""
                        SELECT table_name 
                        FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = ANY(:tables)
                    """),
                    {"tables": tables_tuple}
                )
                existing_tables_after = {row[0] for row in result.fetchall()}
                still_missing = required_tables - existing_tables_after
            
            if still_missing:
                logger.error(f"❌ Failed to create tables: {', '.join(still_missing)}")
                return (False, list(still_missing))
            else:
                logger.info("✅ All social outreach tables created successfully")
                return (True, [])
                
        finally:
            sync_engine.dispose()
            
    except Exception as e:
        logger.error(f"❌ Failed to ensure social tables exist: {e}", exc_info=True)
        return (False, list(required_tables))

