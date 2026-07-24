"""fix discovery_status not null with canonical statuses

Revision ID: fix_discovery_status_not_null
Revises: add_pipeline_status_fields
Create Date: 2025-12-17 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = 'fix_discovery_status_not_null'
down_revision = 'add_pipeline_status_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Fix discovery_status column to be NOT NULL with default 'NEW'
    Maps existing statuses to canonical values:
    - NULL, 'pending' -> 'NEW'
    - 'DISCOVERED' -> 'DISCOVERED'
    - Other values -> 'NEW' (safe fallback)
    
    Canonical statuses: NEW, DISCOVERED, SCRAPED, VERIFIED, OUTREACH_READY, CONTACTED
    """
    conn = op.get_bind()
    
    # Check if column exists (idempotent check)
    result = conn.execute(text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'prospects' 
        AND column_name = 'discovery_status'
    """))
    column_exists = result.fetchone() is not None
    
    if not column_exists:
        # Column doesn't exist - add it as NOT NULL with default
        op.add_column('prospects', sa.Column(
            'discovery_status',
            sa.String(),
            nullable=False,
            server_default='NEW'
        ))
        # Check if index already exists before creating
        result = conn.execute(text("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename = 'prospects' 
            AND indexname = 'ix_prospects_discovery_status'
        """))
        if not result.fetchone():
            op.create_index('ix_prospects_discovery_status', 'prospects', ['discovery_status'])
    else:
        # Column exists - check if it's nullable
        result = conn.execute(text("""
            SELECT is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'prospects' 
            AND column_name = 'discovery_status'
        """))
        is_nullable = result.fetchone()[0] == 'YES'
        
        if is_nullable:
            # Step 1: Backfill NULL and 'pending' values to 'NEW'
            conn.execute(text("""
                UPDATE prospects 
                SET discovery_status = 'NEW' 
                WHERE discovery_status IS NULL OR discovery_status = 'pending'
            """))
            
            # Step 2: Map 'DISCOVERED' to 'DISCOVERED' (already canonical)
            # No change needed - 'DISCOVERED' is already canonical
            
            # Step 3: Map any other unexpected values to 'NEW' (safe fallback)
            conn.execute(text("""
                UPDATE prospects 
                SET discovery_status = 'NEW' 
                WHERE discovery_status NOT IN ('NEW', 'DISCOVERED', 'SCRAPED', 'VERIFIED', 'OUTREACH_READY', 'CONTACTED')
            """))
            
            # Step 4: Alter column to NOT NULL with default
            # First, drop the existing default if any (using IF EXISTS for safety)
            conn.execute(text("""
                ALTER TABLE prospects 
                ALTER COLUMN discovery_status DROP DEFAULT
            """))
            
            # Set default to 'NEW'
            conn.execute(text("""
                ALTER TABLE prospects 
                ALTER COLUMN discovery_status SET DEFAULT 'NEW'
            """))
            
            # Make NOT NULL (this is safe because we backfilled all NULLs)
            # Check if already NOT NULL to avoid error
            result = conn.execute(text("""
                SELECT is_nullable 
                FROM information_schema.columns 
                WHERE table_name = 'prospects' 
                AND column_name = 'discovery_status'
            """))
            is_nullable = result.fetchone()[0] == 'YES'
            
            if is_nullable:
                conn.execute(text("""
                    ALTER TABLE prospects 
                    ALTER COLUMN discovery_status SET NOT NULL
                """))


def downgrade() -> None:
    """
    Revert to nullable column (for rollback safety)
    Note: This does NOT restore original values, just makes column nullable again
    """
    conn = op.get_bind()
    
    # Check if column exists
    result = conn.execute(text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'prospects' 
        AND column_name = 'discovery_status'
    """))
    
    if result.fetchone():
        # Make nullable again (remove NOT NULL constraint)
        # Check if NOT NULL first
        result = conn.execute(text("""
            SELECT is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'prospects' 
            AND column_name = 'discovery_status'
        """))
        is_nullable = result.fetchone()[0] == 'YES'
        
        if not is_nullable:
            conn.execute(text("ALTER TABLE prospects ALTER COLUMN discovery_status DROP NOT NULL"))
        
        conn.execute(text("ALTER TABLE prospects ALTER COLUMN discovery_status DROP DEFAULT"))
        conn.execute(text("ALTER TABLE prospects ALTER COLUMN discovery_status SET DEFAULT 'pending'"))

