"""Ensure alembic_version table exists and is properly initialized

Revision ID: ensure_alembic_version_table
Revises: ensure_all_prospect_columns_final
Create Date: 2026-01-06

CRITICAL: This migration ensures the alembic_version table exists and persists.
If this table is missing, Alembic will re-run all migrations from base, causing
schema corruption and data loss.

This migration:
1. Creates alembic_version table if it doesn't exist
2. Does NOT drop or reset it
3. Ensures it persists across deployments
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = 'ensure_alembic_version_table'
down_revision = 'ensure_all_prospect_columns_final'  # Chain after final columns migration
branch_labels = None
depends_on = None


def upgrade():
    """
    Ensure alembic_version table exists and is properly initialized.
    
    This table is CRITICAL - if it's missing, Alembic will re-run all migrations
    from base, causing schema corruption.
    """
    conn = op.get_bind()
    
    # Check if alembic_version table exists
    result = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'alembic_version'
        )
    """))
    table_exists = result.scalar()
    
    if not table_exists:
        # Create alembic_version table
        # This is the table Alembic uses to track migration state
        op.create_table(
            'alembic_version',
            sa.Column('version_num', sa.String(32), nullable=False),
            sa.PrimaryKeyConstraint('version_num')
        )
        print("✅ Created alembic_version table")
    else:
        print("ℹ️  alembic_version table already exists")
    
    # Verify the table has the correct structure
    result = conn.execute(text("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'alembic_version' 
        AND table_schema = 'public'
    """))
    columns = {row[0]: row[1] for row in result.fetchall()}
    
    if 'version_num' not in columns:
        raise Exception("alembic_version table exists but missing version_num column - table structure is corrupted")
    
    print("=" * 80)
    print("✅ alembic_version table verified and ready")
    print("=" * 80)


def downgrade():
    """
    DO NOT drop alembic_version table - it's critical for migration tracking.
    This downgrade is intentionally empty to prevent accidental data loss.
    """
    pass

