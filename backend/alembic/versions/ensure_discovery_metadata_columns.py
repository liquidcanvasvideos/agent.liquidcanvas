"""ensure discovery metadata columns exist

Revision ID: ensure_discovery_metadata
Revises: ensure_draft_send_status
Create Date: 2025-12-17 21:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = 'ensure_discovery_metadata'
down_revision = 'ensure_draft_send_status'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Ensure discovery metadata columns exist.
    These columns are required for the pipeline to track where websites came from.
    This migration is idempotent - safe to run multiple times.
    """
    conn = op.get_bind()
    
    # Check and add discovery_category if missing
    result = conn.execute(text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'prospects' 
        AND column_name = 'discovery_category'
    """))
    if not result.fetchone():
        op.add_column('prospects', sa.Column('discovery_category', sa.String(), nullable=True))
    
    # Check and add discovery_location if missing
    result = conn.execute(text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'prospects' 
        AND column_name = 'discovery_location'
    """))
    if not result.fetchone():
        op.add_column('prospects', sa.Column('discovery_location', sa.String(), nullable=True))
    
    # Check and add discovery_keywords if missing
    result = conn.execute(text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'prospects' 
        AND column_name = 'discovery_keywords'
    """))
    if not result.fetchone():
        op.add_column('prospects', sa.Column('discovery_keywords', sa.Text(), nullable=True))
    
    # Check and add scraping metadata columns
    scraping_metadata = [
        ('scrape_payload', sa.dialects.postgresql.JSONB),
        ('scrape_source_url', sa.Text),
    ]
    
    for column_name, column_type in scraping_metadata:
        result = conn.execute(text(f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'prospects' 
            AND column_name = '{column_name}'
        """))
        if not result.fetchone():
            op.add_column('prospects', sa.Column(column_name, column_type, nullable=True))
    
    # Check and add verification metadata columns
    verification_metadata = [
        ('verification_confidence', sa.Numeric(precision=5, scale=2)),
        ('verification_payload', sa.dialects.postgresql.JSONB),
    ]
    
    for column_name, column_type in verification_metadata:
        result = conn.execute(text(f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'prospects' 
            AND column_name = '{column_name}'
        """))
        if not result.fetchone():
            op.add_column('prospects', sa.Column(column_name, column_type, nullable=True))
    
    # Check and add raw API response columns
    api_payload_columns = [
        ('dataforseo_payload', sa.dialects.postgresql.JSONB),
        ('snov_payload', sa.dialects.postgresql.JSONB),
    ]
    
    for column_name, column_type in api_payload_columns:
        result = conn.execute(text(f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'prospects' 
            AND column_name = '{column_name}'
        """))
        if not result.fetchone():
            op.add_column('prospects', sa.Column(column_name, column_type, nullable=True))
    
    # Check and add discovery_query_id if missing
    result = conn.execute(text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'prospects' 
        AND column_name = 'discovery_query_id'
    """))
    if not result.fetchone():
        op.add_column('prospects', sa.Column('discovery_query_id', UUID(as_uuid=True), nullable=True))
        # Create index
        op.create_index('ix_prospects_discovery_query_id', 'prospects', ['discovery_query_id'])
    else:
        # Ensure index exists
        index_check = conn.execute(text("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename = 'prospects' 
            AND indexname = 'ix_prospects_discovery_query_id'
        """))
        if not index_check.fetchone():
            op.create_index('ix_prospects_discovery_query_id', 'prospects', ['discovery_query_id'])
    
    conn.commit()


def downgrade() -> None:
    """
    Downgrade is intentionally minimal - we don't want to drop columns
    that might be in use. If you need to remove these columns, do it manually.
    """
    # Note: We don't drop columns in downgrade to avoid data loss
    # If you need to remove these columns, do it manually with proper backups
    pass

