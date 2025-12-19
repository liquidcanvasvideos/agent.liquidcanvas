"""
Schema Validation Utility

Validates that ORM models match database schema.
FAILS FAST if mismatch detected - prevents silent failures.
"""
from sqlalchemy import text, inspect
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine
from sqlalchemy.orm import DeclarativeBase
from typing import List, Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class SchemaMismatchError(Exception):
    """Raised when ORM model doesn't match database schema"""
    pass


async def validate_prospect_schema(engine: AsyncEngine, Base: DeclarativeBase) -> Tuple[bool, List[str]]:
    """
    Validate that Prospect model matches database schema.
    
    Returns:
        (is_valid, missing_columns)
    """
    from app.models.prospect import Prospect
    
    missing_columns = []
    
    # Get columns defined in ORM model
    inspector = inspect(Prospect)
    model_columns = {col.name for col in inspector.columns}
    
    # Get columns that exist in database
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'prospects'
            ORDER BY column_name
        """))
        db_columns = {row[0] for row in result.fetchall()}
    
    # Find missing columns (in model but not in DB)
    missing = model_columns - db_columns
    
    # Find extra columns (in DB but not in model) - warn but don't fail
    extra = db_columns - model_columns
    if extra:
        logger.warning(f"⚠️  Extra columns in database (not in model): {sorted(extra)}")
    
    if missing:
        missing_columns = sorted(missing)
        logger.error(f"❌ SCHEMA MISMATCH: Missing columns in database: {missing_columns}")
        return False, missing_columns
    
    logger.info("✅ Schema validation passed: ORM model matches database")
    return True, []


async def ensure_prospect_schema(engine: AsyncEngine) -> bool:
    """
    Ensure all Prospect model columns exist in database.
    Adds missing columns if needed.
    
    Returns:
        True if schema is now correct, False if it cannot be fixed
    """
    from app.models.prospect import Prospect
    
    async with engine.begin() as conn:
        # Get columns defined in ORM model
        inspector = inspect(Prospect)
        model_columns = {col.name: col for col in inspector.columns}
        
        # Get columns that exist in database
        result = await conn.execute(text("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'prospects'
        """))
        db_columns = {row[0]: row for row in result.fetchall()}
        
        # Find missing columns
        missing = set(model_columns.keys()) - set(db_columns.keys())
        
        if not missing:
            logger.info("✅ All Prospect model columns exist in database")
            return True
        
        logger.warning(f"⚠️  Missing columns detected: {sorted(missing)}")
        logger.warning("⚠️  Attempting to add missing columns...")
        
        # Add missing columns
        for col_name in sorted(missing):
            col = model_columns[col_name]
            
            # Determine SQL type
            if hasattr(col.type, 'python_type'):
                if col.type.python_type == str:
                    sql_type = "TEXT" if col.type.length is None else f"VARCHAR({col.type.length})"
                elif col.type.python_type == int:
                    sql_type = "INTEGER"
                elif col.type.python_type == bool:
                    sql_type = "BOOLEAN"
                elif hasattr(col.type, 'as_generic') and 'UUID' in str(col.type):
                    sql_type = "UUID"
                else:
                    sql_type = "TEXT"  # Fallback
            else:
                sql_type = "TEXT"  # Fallback
            
            # Build ALTER TABLE statement
            nullable = "NULL" if col.nullable else "NOT NULL"
            default = ""
            
            if col.default is not None:
                if hasattr(col.default, 'arg'):
                    default_val = col.default.arg
                    if isinstance(default_val, str):
                        default = f"DEFAULT '{default_val}'"
                    elif isinstance(default_val, (int, float)):
                        default = f"DEFAULT {default_val}"
                    elif isinstance(default_val, bool):
                        default = f"DEFAULT {str(default_val).lower()}"
            
            alter_sql = f"ALTER TABLE prospects ADD COLUMN {col_name} {sql_type} {nullable} {default}"
            
            try:
                await conn.execute(text(alter_sql))
                logger.info(f"✅ Added column: {col_name} ({sql_type})")
                
                # Create index if needed
                if col_name in ['thread_id'] or col.index:
                    try:
                        await conn.execute(text(f"CREATE INDEX IF NOT EXISTS ix_prospects_{col_name} ON prospects({col_name})"))
                        logger.info(f"✅ Created index for: {col_name}")
                    except Exception as idx_err:
                        logger.warning(f"⚠️  Could not create index for {col_name}: {idx_err}")
                
            except Exception as e:
                logger.error(f"❌ Failed to add column {col_name}: {e}")
                return False
        
        # Verify all columns now exist
        result = await conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'prospects'
        """))
        db_columns_after = {row[0] for row in result.fetchall()}
        
        still_missing = set(model_columns.keys()) - db_columns_after
        if still_missing:
            logger.error(f"❌ Still missing columns after fix attempt: {sorted(still_missing)}")
            return False
        
        logger.info("✅ All missing columns added successfully")
        return True

