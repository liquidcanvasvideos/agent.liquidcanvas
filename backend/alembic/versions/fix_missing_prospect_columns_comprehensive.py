"""fix missing prospect columns comprehensive

Revision ID: fix_missing_prospect_columns
Revises: add_draft_followup_fields
Create Date: 2025-01-19 12:00:00.000000

This migration ensures ALL columns referenced in the ORM model and queries exist.
Fixes: "column prospects.final_body does not exist" and other schema mismatches.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = 'fix_missing_prospect_columns'
down_revision = 'add_draft_followup_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add ALL missing columns that are referenced in ORM model and queries.
    This fixes schema drift causing SELECT queries to fail.
    """
    conn = op.get_bind()
    
    # CRITICAL: All columns that ORM model expects (from app/models/prospect.py)
    # These columns MUST exist or SELECT queries will fail
    
    columns_to_add = [
        # Draft and send fields
        ('final_body', 'TEXT', None, True),
        ('draft_subject', 'TEXT', None, True),
        ('draft_body', 'TEXT', None, True),
        
        # Pipeline status fields (required for /api/pipeline/status)
        ('verification_status', 'VARCHAR', 'UNVERIFIED', False),
        ('draft_status', 'VARCHAR', 'pending', False),
        ('send_status', 'VARCHAR', 'pending', False),
        ('stage', 'VARCHAR', 'DISCOVERED', False),
        ('outreach_status', 'VARCHAR', 'pending', True),
        
        # Follow-up fields
        ('thread_id', 'UUID', None, True),
        ('sequence_index', 'INTEGER', '0', False),
        ('is_manual', 'BOOLEAN', 'false', True),
        
        # Timestamps
        ('last_sent', 'TIMESTAMP WITH TIME ZONE', None, True),
        ('followups_sent', 'INTEGER', '0', False),
    ]
    
    for col_name, col_type, default_value, nullable in columns_to_add:
        # Check if column exists
        result = conn.execute(text(f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'prospects' 
            AND column_name = '{col_name}'
        """))
        
        if not result.fetchone():
            print(f"⚠️  Missing column {col_name} - adding now...")
            
            # Build ALTER TABLE statement
            alter_sql = f"ALTER TABLE prospects ADD COLUMN {col_name} {col_type}"
            
            if not nullable:
                # For NOT NULL columns, add as nullable first, backfill, then set NOT NULL
                alter_sql = f"ALTER TABLE prospects ADD COLUMN {col_name} {col_type}"
                conn.execute(text(alter_sql))
                
                # Backfill with default value
                if default_value:
                    if col_type == 'BOOLEAN':
                        # Handle boolean defaults
                        if default_value == 'false':
                            conn.execute(text(f"UPDATE prospects SET {col_name} = false WHERE {col_name} IS NULL"))
                        else:
                            conn.execute(text(f"UPDATE prospects SET {col_name} = true WHERE {col_name} IS NULL"))
                    elif col_type == 'INTEGER':
                        conn.execute(text(f"UPDATE prospects SET {col_name} = {default_value} WHERE {col_name} IS NULL"))
                    else:
                        conn.execute(text(f"UPDATE prospects SET {col_name} = '{default_value}' WHERE {col_name} IS NULL"))
                
                # Set NOT NULL after backfill
                conn.execute(text(f"ALTER TABLE prospects ALTER COLUMN {col_name} SET NOT NULL"))
                
                # Set default
                if default_value:
                    if col_type == 'BOOLEAN':
                        conn.execute(text(f"ALTER TABLE prospects ALTER COLUMN {col_name} SET DEFAULT {default_value}"))
                    elif col_type == 'INTEGER':
                        conn.execute(text(f"ALTER TABLE prospects ALTER COLUMN {col_name} SET DEFAULT {default_value}"))
                    else:
                        conn.execute(text(f"ALTER TABLE prospects ALTER COLUMN {col_name} SET DEFAULT '{default_value}'"))
            else:
                # Nullable column
                conn.execute(text(alter_sql))
                if default_value:
                    if col_type == 'BOOLEAN':
                        conn.execute(text(f"ALTER TABLE prospects ALTER COLUMN {col_name} SET DEFAULT {default_value}"))
                    elif col_type == 'INTEGER':
                        conn.execute(text(f"ALTER TABLE prospects ALTER COLUMN {col_name} SET DEFAULT {default_value}"))
                    else:
                        conn.execute(text(f"ALTER TABLE prospects ALTER COLUMN {col_name} SET DEFAULT '{default_value}'"))
            
            # Create index for status/stage columns
            if col_name in ['verification_status', 'draft_status', 'send_status', 'stage', 'outreach_status']:
                try:
                    conn.execute(text(f"CREATE INDEX IF NOT EXISTS ix_prospects_{col_name} ON prospects({col_name})"))
                except Exception as e:
                    print(f"⚠️  Could not create index for {col_name}: {e}")
            
            print(f"✅ Added column {col_name}")
        else:
            print(f"✅ Column {col_name} already exists")
    
    # Ensure thread_id has index
    try:
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_prospects_thread_id ON prospects(thread_id)"))
    except Exception:
        pass  # Index might already exist
    
    conn.commit()
    print("✅ All required columns verified/added")


def downgrade() -> None:
    """
    Remove columns (for rollback safety)
    Note: This will fail if columns are referenced elsewhere
    """
    conn = op.get_bind()
    
    # Only drop columns that were added by this migration
    columns_to_remove = ['final_body']  # Only remove if we're sure it's safe
    
    for col_name in columns_to_remove:
        result = conn.execute(text(f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'prospects' 
            AND column_name = '{col_name}'
        """))
        if result.fetchone():
            try:
                op.drop_column('prospects', col_name)
                print(f"✅ Removed column {col_name}")
            except Exception as e:
                print(f"⚠️  Could not remove column {col_name}: {e}")
    
    conn.commit()

