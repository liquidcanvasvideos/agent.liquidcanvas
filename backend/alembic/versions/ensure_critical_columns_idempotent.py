"""ensure critical columns exist (idempotent)

Revision ID: ensure_critical_columns
Revises: add_social_tables
Create Date: 2026-01-02 20:00:00.000000

CRITICAL: Ensures final_body, thread_id, sequence_index exist.
This migration is idempotent and safe to run multiple times.
Fails loudly if columns cannot be created.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = 'ensure_critical_columns'
down_revision = 'add_social_tables'  # Update to latest
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Ensure critical columns exist with proper types and defaults.
    This is idempotent - safe to run multiple times.
    """
    conn = op.get_bind()
    
    # Columns to ensure: (name, type, default, nullable, needs_index, description)
    columns_to_ensure = [
        ('final_body', 'TEXT', None, True, False, 'Final email body after sending'),
        ('thread_id', 'UUID', None, True, True, 'Thread ID for follow-up emails'),
        ('sequence_index', 'INTEGER', '0', False, False, 'Follow-up sequence (0 = initial, 1+ = follow-up)'),
    ]
    
    for col_name, col_type, default_value, nullable, needs_index, description in columns_to_ensure:
        # Check if column exists
        result = conn.execute(text(f"""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'prospects' 
            AND column_name = '{col_name}'
        """))
        
        existing = result.fetchone()
        
        if not existing:
            print(f"⚠️  Adding missing column: {col_name} ({description})")
            
            # Build ALTER TABLE statement
            if col_type == 'UUID':
                alter_sql = f"ALTER TABLE prospects ADD COLUMN {col_name} UUID"
            elif col_type == 'TEXT':
                alter_sql = f"ALTER TABLE prospects ADD COLUMN {col_name} TEXT"
            elif col_type == 'INTEGER':
                alter_sql = f"ALTER TABLE prospects ADD COLUMN {col_name} INTEGER"
            else:
                raise ValueError(f"Unsupported column type: {col_type}")
            
            # Add column
            conn.execute(text(alter_sql))
            
            # Backfill with default if NOT NULL is required
            if not nullable and default_value:
                if col_type == 'INTEGER':
                    conn.execute(text(f"UPDATE prospects SET {col_name} = {default_value} WHERE {col_name} IS NULL"))
                    conn.execute(text(f"ALTER TABLE prospects ALTER COLUMN {col_name} SET NOT NULL"))
                else:
                    raise ValueError(f"Cannot set NOT NULL for {col_type} without proper backfill")
            
            # Set default value
            if default_value:
                if col_type == 'INTEGER':
                    conn.execute(text(f"ALTER TABLE prospects ALTER COLUMN {col_name} SET DEFAULT {default_value}"))
                # TEXT and UUID don't need defaults in this case
            
            # Create index if needed
            if needs_index:
                try:
                    conn.execute(text(f"CREATE INDEX IF NOT EXISTS ix_prospects_{col_name} ON prospects({col_name})"))
                    print(f"✅ Created index for {col_name}")
                except Exception as e:
                    print(f"⚠️  Could not create index for {col_name}: {e}")
            
            print(f"✅ Added column {col_name}")
        else:
            # Verify column type matches
            existing_type = existing[1].upper()
            expected_type = col_type.upper()
            
            # PostgreSQL type mappings
            type_map = {
                'TEXT': ['TEXT', 'CHARACTER VARYING', 'VARCHAR'],
                'UUID': ['UUID'],
                'INTEGER': ['INTEGER', 'INT', 'BIGINT', 'SMALLINT'],
            }
            
            type_matches = False
            for expected in type_map.get(expected_type, [expected_type]):
                if expected in existing_type:
                    type_matches = True
                    break
            
            if not type_matches:
                print(f"⚠️  Column {col_name} exists but type mismatch: {existing_type} vs {expected_type}")
            else:
                print(f"✅ Column {col_name} already exists with correct type")
            
            # Ensure index exists if needed
            if needs_index:
                try:
                    conn.execute(text(f"CREATE INDEX IF NOT EXISTS ix_prospects_{col_name} ON prospects({col_name})"))
                except Exception as e:
                    print(f"⚠️  Could not ensure index for {col_name}: {e}")
    
    conn.commit()
    print("✅ All critical columns verified/added")


def downgrade() -> None:
    """
    WARNING: Do not remove columns if they contain data.
    This is a safety downgrade that only removes if explicitly safe.
    """
    # For safety, we don't automatically remove columns
    # Manual intervention required
    print("⚠️  Downgrade skipped - columns are not automatically removed for data safety")
    pass

