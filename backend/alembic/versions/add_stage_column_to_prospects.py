"""add stage column to prospects

Revision ID: add_stage_column
Revises: ensure_discovery_metadata
Create Date: 2025-01-18 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = 'add_stage_column'
down_revision = 'ensure_discovery_metadata'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add stage column to prospects table.
    This is the canonical pipeline stage field that tracks prospect progression.
    Values: DISCOVERED, SCRAPED, LEAD, VERIFIED, DRAFTED, SENT, FAILED
    """
    conn = op.get_bind()
    
    # Check if column already exists (idempotent)
    result = conn.execute(text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'prospects' 
        AND column_name = 'stage'
    """))
    
    if not result.fetchone():
        # Column doesn't exist - add it
        op.add_column('prospects', sa.Column(
            'stage',
            sa.String(),
            nullable=False,
            server_default='DISCOVERED'
        ))
        
        # Create index for performance
        op.create_index('ix_prospects_stage', 'prospects', ['stage'])
        
        # Backfill existing rows based on their current status
        # DISCOVERED: discovery_status = 'DISCOVERED'
        conn.execute(text("""
            UPDATE prospects 
            SET stage = 'DISCOVERED' 
            WHERE discovery_status = 'DISCOVERED' AND stage IS NULL
        """))
        
        # LEAD: scrape_status = 'SCRAPED' or 'ENRICHED' AND contact_email IS NOT NULL
        conn.execute(text("""
            UPDATE prospects 
            SET stage = 'LEAD' 
            WHERE (scrape_status = 'SCRAPED' OR scrape_status = 'ENRICHED') 
            AND contact_email IS NOT NULL 
            AND stage IS NULL
        """))
        
        # SCRAPED: scrape_status = 'SCRAPED' or 'ENRICHED' but no email
        conn.execute(text("""
            UPDATE prospects 
            SET stage = 'SCRAPED' 
            WHERE (scrape_status = 'SCRAPED' OR scrape_status = 'ENRICHED') 
            AND contact_email IS NULL 
            AND stage IS NULL
        """))
        
        # VERIFIED: verification_status = 'verified'
        conn.execute(text("""
            UPDATE prospects 
            SET stage = 'VERIFIED' 
            WHERE verification_status = 'verified' 
            AND stage IS NULL
        """))
        
        # FAILED: any status = 'failed'
        conn.execute(text("""
            UPDATE prospects 
            SET stage = 'FAILED' 
            WHERE scrape_status = 'failed' 
            OR verification_status = 'failed' 
            OR draft_status = 'failed' 
            OR send_status = 'failed'
            AND stage IS NULL
        """))
        
        # Set remaining NULL values to DISCOVERED (safe default)
        conn.execute(text("""
            UPDATE prospects 
            SET stage = 'DISCOVERED' 
            WHERE stage IS NULL
        """))
        
        conn.commit()
    else:
        # Column exists - ensure it has the correct default and is NOT NULL
        # Check if it's nullable
        result = conn.execute(text("""
            SELECT is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'prospects' 
            AND column_name = 'stage'
        """))
        column_info = result.fetchone()
        
        if column_info:
            is_nullable = column_info[0] == 'YES'
            
            # Backfill NULL values to DISCOVERED
            conn.execute(text("""
                UPDATE prospects 
                SET stage = 'DISCOVERED' 
                WHERE stage IS NULL
            """))
            
            # Make NOT NULL if it's currently nullable
            if is_nullable:
                conn.execute(text("""
                    ALTER TABLE prospects 
                    ALTER COLUMN stage SET NOT NULL
                """))
            
            # Ensure default is set
            conn.execute(text("""
                ALTER TABLE prospects 
                ALTER COLUMN stage SET DEFAULT 'DISCOVERED'
            """))
            
            # Ensure index exists
            index_check = conn.execute(text("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE tablename = 'prospects' 
                AND indexname = 'ix_prospects_stage'
            """))
            if not index_check.fetchone():
                op.create_index('ix_prospects_stage', 'prospects', ['stage'])
            
            conn.commit()


def downgrade() -> None:
    """
    Remove stage column (for rollback safety)
    """
    conn = op.get_bind()
    
    # Check if column exists
    result = conn.execute(text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'prospects' 
        AND column_name = 'stage'
    """))
    
    if result.fetchone():
        # Drop index first
        index_check = conn.execute(text("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename = 'prospects' 
            AND indexname = 'ix_prospects_stage'
        """))
        if index_check.fetchone():
            op.drop_index('ix_prospects_stage', table_name='prospects')
        
        # Drop column
        op.drop_column('prospects', 'stage')
        conn.commit()

