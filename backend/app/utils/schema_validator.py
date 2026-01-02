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
    
    CRITICAL COLUMNS that MUST exist:
    - draft_subject TEXT
    - draft_body TEXT  
    - final_body TEXT
    - thread_id UUID
    - sequence_index INTEGER DEFAULT 0
    
    Returns:
        True if schema is now correct, False if it cannot be fixed
    """
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
            
            # Determine SQL type with better handling
            type_str = str(col.type)
            
            # Handle UUID type
            if 'UUID' in type_str or 'uuid' in type_str.lower():
                sql_type = "UUID"
            # Handle Numeric types
            elif 'NUMERIC' in type_str.upper() or 'DECIMAL' in type_str.upper():
                # Extract precision and scale if available
                if hasattr(col.type, 'precision') and hasattr(col.type, 'scale'):
                    sql_type = f"NUMERIC({col.type.precision},{col.type.scale})"
                else:
                    sql_type = "NUMERIC"
            # Handle Integer types
            elif 'INTEGER' in type_str.upper() or 'INT' in type_str.upper() or 'BIGINT' in type_str.upper():
                sql_type = "INTEGER"
            # Handle Boolean types
            elif 'BOOLEAN' in type_str.upper() or 'BOOL' in type_str.upper():
                sql_type = "BOOLEAN"
            # Handle JSON types
            elif 'JSON' in type_str.upper():
                sql_type = "JSONB"  # PostgreSQL uses JSONB
            # Handle DateTime types
            elif 'DATETIME' in type_str.upper() or 'TIMESTAMP' in type_str.upper():
                sql_type = "TIMESTAMP WITH TIME ZONE"
            # Handle String/Text types
            elif hasattr(col.type, 'python_type'):
                if col.type.python_type == str:
                    sql_type = "TEXT" if col.type.length is None else f"VARCHAR({col.type.length})"
                elif col.type.python_type == int:
                    sql_type = "INTEGER"
                elif col.type.python_type == bool:
                    sql_type = "BOOLEAN"
                else:
                    sql_type = "TEXT"  # Fallback
            else:
                sql_type = "TEXT"  # Fallback
            
            # Build ALTER TABLE statement
            # Add column as nullable first, then set constraints if needed
            alter_sql = f"ALTER TABLE prospects ADD COLUMN {col_name} {sql_type}"
            
            try:
                # Step 1: Add column (nullable first)
                await conn.execute(text(alter_sql))
                logger.info(f"✅ Added column: {col_name} ({sql_type})")
                
                # Step 2: Backfill with default if NOT NULL is required
                if not col.nullable and col.default is not None:
                    default_val = None
                    if hasattr(col.default, 'arg'):
                        default_val = col.default.arg
                    elif hasattr(col.default, 'value'):
                        default_val = col.default.value
                    
                    if default_val is not None:
                        if sql_type == "INTEGER":
                            await conn.execute(text(f"UPDATE prospects SET {col_name} = {default_val} WHERE {col_name} IS NULL"))
                        elif sql_type == "BOOLEAN":
                            await conn.execute(text(f"UPDATE prospects SET {col_name} = {str(default_val).lower()} WHERE {col_name} IS NULL"))
                        else:
                            await conn.execute(text(f"UPDATE prospects SET {col_name} = '{default_val}' WHERE {col_name} IS NULL"))
                        
                        # Step 3: Set NOT NULL after backfill
                        await conn.execute(text(f"ALTER TABLE prospects ALTER COLUMN {col_name} SET NOT NULL"))
                        logger.info(f"✅ Set {col_name} as NOT NULL with default backfill")
                
                # Step 4: Set default value if specified
                if col.default is not None:
                    default_val = None
                    if hasattr(col.default, 'arg'):
                        default_val = col.default.arg
                    elif hasattr(col.default, 'value'):
                        default_val = col.default.value
                    
                    if default_val is not None:
                        if sql_type == "INTEGER":
                            await conn.execute(text(f"ALTER TABLE prospects ALTER COLUMN {col_name} SET DEFAULT {default_val}"))
                        elif sql_type == "BOOLEAN":
                            await conn.execute(text(f"ALTER TABLE prospects ALTER COLUMN {col_name} SET DEFAULT {str(default_val).lower()}"))
                        else:
                            await conn.execute(text(f"ALTER TABLE prospects ALTER COLUMN {col_name} SET DEFAULT '{default_val}'"))
                        logger.info(f"✅ Set default value for {col_name}")
                
                # Step 5: Create index if needed
                if col_name in ['thread_id'] or (hasattr(col, 'index') and col.index):
                    try:
                        await conn.execute(text(f"CREATE INDEX IF NOT EXISTS ix_prospects_{col_name} ON prospects({col_name})"))
                        logger.info(f"✅ Created index for: {col_name}")
                    except Exception as idx_err:
                        logger.warning(f"⚠️  Could not create index for {col_name}: {idx_err}")
                
            except Exception as e:
                logger.error(f"❌ Failed to add column {col_name}: {e}", exc_info=True)
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

