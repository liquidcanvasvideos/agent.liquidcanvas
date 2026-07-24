"""fix discovery_query_id column - add if missing

Revision ID: fix_discovery_query_id
Revises: add_social_tables
Create Date: 2026-01-10 23:50:00.000000

CRITICAL: Adds discovery_query_id column if it's missing.
This column is required by the Prospect ORM model but may not exist
if migrations were run out of order or on a fresh database.

This migration is idempotent - safe to run multiple times.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = 'fix_discovery_query_id'
down_revision = 'add_social_tables'  # Chain after latest migration
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add discovery_query_id column if it's missing.
    This is idempotent - checks for existence before adding.
    """
    conn = op.get_bind()
    
    # Check if column exists
    result = conn.execute(text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'prospects' 
        AND column_name = 'discovery_query_id'
        AND table_schema = 'public'
    """))
    
    if not result.fetchone():
        print("⚠️  Adding missing column: discovery_query_id")
        
        # Add column
        op.add_column(
            'prospects',
            sa.Column(
                'discovery_query_id',
                postgresql.UUID(as_uuid=True),
                nullable=True,
                comment='Foreign key reference to discovery_queries.id'
            )
        )
        
        # Create index
        op.create_index(
            'ix_prospects_discovery_query_id',
            'prospects',
            ['discovery_query_id'],
            if_not_exists=True
        )
        
        print("✅ Added discovery_query_id column and index")
    else:
        print("✅ Column discovery_query_id already exists")
        # Ensure index exists even if column exists
        try:
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_prospects_discovery_query_id 
                ON prospects (discovery_query_id)
            """))
            print("✅ Verified discovery_query_id index exists")
        except Exception as e:
            print(f"⚠️  Could not ensure index: {e}")
    
    conn.commit()
    print("✅ discovery_query_id column fix complete")


def downgrade() -> None:
    """
    Remove discovery_query_id column (for rollback safety).
    WARNING: Only use if absolutely necessary - will break queries.
    """
    conn = op.get_bind()
    
    # Check if column exists before removing
    result = conn.execute(text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'prospects' 
        AND column_name = 'discovery_query_id'
        AND table_schema = 'public'
    """))
    
    if result.fetchone():
        try:
            # Drop index first
            conn.execute(text("DROP INDEX IF EXISTS ix_prospects_discovery_query_id"))
            # Drop column
            op.drop_column('prospects', 'discovery_query_id')
            print("✅ Removed discovery_query_id column")
        except Exception as e:
            print(f"⚠️  Could not remove discovery_query_id column: {e}")
    
    conn.commit()

