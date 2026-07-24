"""fix scrape_status default to DISCOVERED

Revision ID: fix_scrape_status_discovered
Revises: fix_discovery_status_not_null
Create Date: 2025-12-17 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = 'fix_scrape_status_discovered'
down_revision = 'fix_discovery_status_not_null'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Fix scrape_status column to default to 'DISCOVERED' instead of 'PENDING'
    Lifecycle: DISCOVERED → SCRAPED → ENRICHED → EMAILED
    Backfills existing rows safely
    """
    conn = op.get_bind()
    
    # Check if column exists
    result = conn.execute(text("""
        SELECT column_name, is_nullable, column_default
        FROM information_schema.columns 
        WHERE table_name = 'prospects' 
        AND column_name = 'scrape_status'
    """))
    column_row = result.fetchone()
    
    if not column_row:
        # Column doesn't exist - add it with correct default
        op.add_column('prospects', sa.Column(
            'scrape_status',
            sa.String(),
            nullable=False,
            server_default='DISCOVERED'
        ))
        op.create_index('ix_prospects_scrape_status', 'prospects', ['scrape_status'])
    else:
        # Column exists - update default and backfill
        # Step 1: Backfill NULL and 'PENDING' values to 'DISCOVERED'
        conn.execute(text("""
            UPDATE prospects 
            SET scrape_status = 'DISCOVERED' 
            WHERE scrape_status IS NULL OR scrape_status = 'PENDING' OR scrape_status = 'pending'
        """))
        
        # Step 2: Update default to 'DISCOVERED'
        conn.execute(text("ALTER TABLE prospects ALTER COLUMN scrape_status DROP DEFAULT"))
        conn.execute(text("ALTER TABLE prospects ALTER COLUMN scrape_status SET DEFAULT 'DISCOVERED'"))
        
        # Step 3: Ensure NOT NULL (backfill ensures this is safe)
        is_nullable = column_row[1] == 'YES'
        if is_nullable:
            conn.execute(text("ALTER TABLE prospects ALTER COLUMN scrape_status SET NOT NULL"))
        
        # Step 4: Ensure index exists
        index_check = conn.execute(text("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename = 'prospects' 
            AND indexname = 'ix_prospects_scrape_status'
        """))
        if not index_check.fetchone():
            op.create_index('ix_prospects_scrape_status', 'prospects', ['scrape_status'])
        
        conn.commit()


def downgrade() -> None:
    """
    Revert to 'PENDING' default (for rollback safety)
    """
    conn = op.get_bind()
    
    # Backfill to 'PENDING'
    conn.execute(text("""
        UPDATE prospects 
        SET scrape_status = 'PENDING' 
        WHERE scrape_status = 'DISCOVERED'
    """))
    
    # Update default
    conn.execute(text("ALTER TABLE prospects ALTER COLUMN scrape_status DROP DEFAULT"))
    conn.execute(text("ALTER TABLE prospects ALTER COLUMN scrape_status SET DEFAULT 'PENDING'"))
    conn.commit()

