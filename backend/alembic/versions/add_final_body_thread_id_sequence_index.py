"""add final_body thread_id sequence_index

Revision ID: add_final_body_thread_id
Revises: fix_missing_prospect_columns
Create Date: 2025-12-19 03:00:00.000000

CRITICAL: Adds missing columns that cause UndefinedColumnError:
- final_body TEXT (nullable)
- thread_id UUID (nullable, indexed)
- sequence_index INTEGER (default 0, not null)

This migration is idempotent and safe to run multiple times.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = 'add_final_body_thread_id'
# NOTE: There are two migrations with down_revision='add_draft_followup_fields'
# This one and fix_missing_prospect_columns. This creates a branch.
# We'll make this one depend on fix_missing_prospect_columns instead.
down_revision = 'fix_missing_prospect_columns'  # Chain after the comprehensive fix
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add final_body, thread_id, and sequence_index columns to prospects table.
    These columns are referenced in the ORM model but may not exist in the database.
    """
    conn = op.get_bind()
    
    # List of columns to add: (name, type, default, nullable, needs_index)
    columns_to_add = [
        ('final_body', 'TEXT', None, True, False),
        ('thread_id', 'UUID', None, True, True),  # Needs index
        ('sequence_index', 'INTEGER', '0', False, False),
    ]
    
    for col_name, col_type, default_value, nullable, needs_index in columns_to_add:
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
            if col_type == 'UUID':
                # UUID type in PostgreSQL
                alter_sql = f"ALTER TABLE prospects ADD COLUMN {col_name} UUID"
            elif col_type == 'TEXT':
                alter_sql = f"ALTER TABLE prospects ADD COLUMN {col_name} TEXT"
            elif col_type == 'INTEGER':
                alter_sql = f"ALTER TABLE prospects ADD COLUMN {col_name} INTEGER"
            else:
                alter_sql = f"ALTER TABLE prospects ADD COLUMN {col_name} {col_type}"
            
            # Add column as nullable first
            conn.execute(text(alter_sql))
            
            # Backfill with default if needed
            if not nullable and default_value:
                if col_type == 'INTEGER':
                    conn.execute(text(f"UPDATE prospects SET {col_name} = {default_value} WHERE {col_name} IS NULL"))
                elif col_type == 'BOOLEAN':
                    conn.execute(text(f"UPDATE prospects SET {col_name} = {default_value} WHERE {col_name} IS NULL"))
                else:
                    conn.execute(text(f"UPDATE prospects SET {col_name} = '{default_value}' WHERE {col_name} IS NULL"))
                
                # Set NOT NULL after backfill
                conn.execute(text(f"ALTER TABLE prospects ALTER COLUMN {col_name} SET NOT NULL"))
            
            # Set default value
            if default_value:
                if col_type == 'INTEGER':
                    conn.execute(text(f"ALTER TABLE prospects ALTER COLUMN {col_name} SET DEFAULT {default_value}"))
                elif col_type == 'BOOLEAN':
                    conn.execute(text(f"ALTER TABLE prospects ALTER COLUMN {col_name} SET DEFAULT {default_value}"))
                else:
                    conn.execute(text(f"ALTER TABLE prospects ALTER COLUMN {col_name} SET DEFAULT '{default_value}'"))
            
            # Create index if needed
            if needs_index:
                try:
                    conn.execute(text(f"CREATE INDEX IF NOT EXISTS ix_prospects_{col_name} ON prospects({col_name})"))
                    print(f"✅ Created index for {col_name}")
                except Exception as e:
                    print(f"⚠️  Could not create index for {col_name}: {e}")
            
            print(f"✅ Added column {col_name}")
        else:
            print(f"✅ Column {col_name} already exists")
    
    # Ensure thread_id has index (even if column already existed)
    try:
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_prospects_thread_id ON prospects(thread_id)"))
    except Exception as e:
        print(f"⚠️  Could not ensure thread_id index: {e}")
    
    conn.commit()
    print("✅ All required columns verified/added")


def downgrade() -> None:
    """
    Remove columns (for rollback safety)
    WARNING: This will fail if columns are referenced in queries
    """
    conn = op.get_bind()
    
    columns_to_remove = ['final_body', 'thread_id', 'sequence_index']
    
    for col_name in columns_to_remove:
        result = conn.execute(text(f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'prospects' 
            AND column_name = '{col_name}'
        """))
        if result.fetchone():
            try:
                # Drop index first if it exists
                try:
                    conn.execute(text(f"DROP INDEX IF EXISTS ix_prospects_{col_name}"))
                except Exception:
                    pass
                
                op.drop_column('prospects', col_name)
                print(f"✅ Removed column {col_name}")
            except Exception as e:
                print(f"⚠️  Could not remove column {col_name}: {e}")
    
    conn.commit()

