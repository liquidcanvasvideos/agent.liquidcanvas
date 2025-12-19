"""final schema repair - CRITICAL MIGRATION

Revision ID: final_schema_repair
Revises: add_final_body_thread_id
Create Date: 2025-12-19 12:00:00.000000

CRITICAL: This migration ensures ALL columns referenced in ORM model exist.
This is the definitive fix for schema drift causing UndefinedColumnError.

This migration:
1. Adds final_body, thread_id, sequence_index if missing
2. Is idempotent (safe to run multiple times)
3. Preserves all existing data
4. Creates required indexes

After this migration, ORM model MUST match database schema exactly.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = 'final_schema_repair'
down_revision = 'add_final_body_thread_id'  # Chain after existing migration
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add ALL missing columns that ORM model expects.
    This is the definitive fix - no more workarounds needed.
    """
    conn = op.get_bind()
    
    # CRITICAL: All columns that Prospect model references
    # These MUST exist or SELECT queries will fail
    columns_to_ensure = [
        {
            'name': 'final_body',
            'type': 'TEXT',
            'nullable': True,
            'default': None,
            'index': False
        },
        {
            'name': 'thread_id',
            'type': 'UUID',
            'nullable': True,
            'default': None,
            'index': True  # Has index in model
        },
        {
            'name': 'sequence_index',
            'type': 'INTEGER',
            'nullable': False,
            'default': '0',
            'index': False
        }
    ]
    
    for col_def in columns_to_ensure:
        col_name = col_def['name']
        
        # Check if column exists
        result = conn.execute(text(f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'prospects' 
            AND column_name = '{col_name}'
        """))
        
        if not result.fetchone():
            print(f"⚠️  Adding missing column: {col_name}")
            
            # Build ALTER TABLE statement
            if col_def['type'] == 'UUID':
                alter_sql = f"ALTER TABLE prospects ADD COLUMN {col_name} UUID"
            elif col_def['type'] == 'TEXT':
                alter_sql = f"ALTER TABLE prospects ADD COLUMN {col_name} TEXT"
            elif col_def['type'] == 'INTEGER':
                alter_sql = f"ALTER TABLE prospects ADD COLUMN {col_name} INTEGER"
            else:
                alter_sql = f"ALTER TABLE prospects ADD COLUMN {col_name} {col_def['type']}"
            
            # Add column (nullable first if NOT NULL is required)
            conn.execute(text(alter_sql))
            
            # Backfill and set NOT NULL if required
            if not col_def['nullable'] and col_def['default']:
                # Backfill with default
                if col_def['type'] == 'INTEGER':
                    conn.execute(text(f"UPDATE prospects SET {col_name} = {col_def['default']} WHERE {col_name} IS NULL"))
                else:
                    conn.execute(text(f"UPDATE prospects SET {col_name} = '{col_def['default']}' WHERE {col_name} IS NULL"))
                
                # Set NOT NULL
                conn.execute(text(f"ALTER TABLE prospects ALTER COLUMN {col_name} SET NOT NULL"))
            
            # Set default value
            if col_def['default']:
                if col_def['type'] == 'INTEGER':
                    conn.execute(text(f"ALTER TABLE prospects ALTER COLUMN {col_name} SET DEFAULT {col_def['default']}"))
                else:
                    conn.execute(text(f"ALTER TABLE prospects ALTER COLUMN {col_name} SET DEFAULT '{col_def['default']}'"))
            
            # Create index if needed
            if col_def['index']:
                try:
                    conn.execute(text(f"CREATE INDEX IF NOT EXISTS ix_prospects_{col_name} ON prospects({col_name})"))
                    print(f"✅ Created index for {col_name}")
                except Exception as e:
                    print(f"⚠️  Could not create index for {col_name}: {e}")
            
            print(f"✅ Added column {col_name}")
        else:
            print(f"✅ Column {col_name} already exists")
    
    # Ensure thread_id index exists (even if column already existed)
    try:
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_prospects_thread_id ON prospects(thread_id)"))
        print("✅ Verified thread_id index exists")
    except Exception as e:
        print(f"⚠️  Could not ensure thread_id index: {e}")
    
    conn.commit()
    print("✅ Schema repair complete - all required columns verified")


def downgrade() -> None:
    """
    Remove columns (for rollback safety)
    WARNING: Only use if absolutely necessary - will break queries
    """
    conn = op.get_bind()
    
    # Only remove if we're sure it's safe
    # In production, prefer keeping columns for backward compatibility
    columns_to_remove = []  # Empty by default - don't remove in production
    
    for col_name in columns_to_remove:
        result = conn.execute(text(f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'prospects' 
            AND column_name = '{col_name}'
        """))
        if result.fetchone():
            try:
                # Drop index first
                try:
                    conn.execute(text(f"DROP INDEX IF EXISTS ix_prospects_{col_name}"))
                except Exception:
                    pass
                
                op.drop_column('prospects', col_name)
                print(f"✅ Removed column {col_name}")
            except Exception as e:
                print(f"⚠️  Could not remove column {col_name}: {e}")
    
    conn.commit()

