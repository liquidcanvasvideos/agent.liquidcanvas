"""ensure draft_status and send_status columns exist

Revision ID: ensure_draft_send_status
Revises: add_pipeline_status_fields
Create Date: 2025-12-17 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = 'ensure_draft_send_status'
down_revision = 'add_pipeline_status_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Ensure draft_status and send_status columns exist with proper defaults.
    This migration is idempotent - safe to run multiple times.
    """
    conn = op.get_bind()
    
    # Check and add draft_status if missing
    result = conn.execute(text("""
        SELECT column_name, is_nullable, column_default
        FROM information_schema.columns 
        WHERE table_name = 'prospects' 
        AND column_name = 'draft_status'
    """))
    column_row = result.fetchone()
    
    if not column_row:
        # Column doesn't exist - add it with correct default
        op.add_column('prospects', sa.Column(
            'draft_status',
            sa.String(),
            nullable=False,
            server_default='pending'
        ))
        op.create_index('ix_prospects_draft_status', 'prospects', ['draft_status'])
    else:
        # Column exists - ensure it has correct default and is NOT NULL
        is_nullable = column_row[1] == 'YES'
        current_default = column_row[2]
        
        # Backfill NULLs
        conn.execute(text("UPDATE prospects SET draft_status = 'pending' WHERE draft_status IS NULL"))
        
        # Update default if missing or incorrect
        if not current_default or "'pending'" not in str(current_default):
            conn.execute(text("ALTER TABLE prospects ALTER COLUMN draft_status DROP DEFAULT"))
            conn.execute(text("ALTER TABLE prospects ALTER COLUMN draft_status SET DEFAULT 'pending'"))
        
        # Make NOT NULL if currently nullable
        if is_nullable:
            conn.execute(text("ALTER TABLE prospects ALTER COLUMN draft_status SET NOT NULL"))
        
        # Ensure index exists
        index_check = conn.execute(text("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename = 'prospects' 
            AND indexname = 'ix_prospects_draft_status'
        """))
        if not index_check.fetchone():
            op.create_index('ix_prospects_draft_status', 'prospects', ['draft_status'])
    
    # Check and add send_status if missing
    result = conn.execute(text("""
        SELECT column_name, is_nullable, column_default
        FROM information_schema.columns 
        WHERE table_name = 'prospects' 
        AND column_name = 'send_status'
    """))
    column_row = result.fetchone()
    
    if not column_row:
        # Column doesn't exist - add it with correct default
        op.add_column('prospects', sa.Column(
            'send_status',
            sa.String(),
            nullable=False,
            server_default='pending'
        ))
        op.create_index('ix_prospects_send_status', 'prospects', ['send_status'])
    else:
        # Column exists - ensure it has correct default and is NOT NULL
        is_nullable = column_row[1] == 'YES'
        current_default = column_row[2]
        
        # Backfill NULLs
        conn.execute(text("UPDATE prospects SET send_status = 'pending' WHERE send_status IS NULL"))
        
        # Update default if missing or incorrect
        if not current_default or "'pending'" not in str(current_default):
            conn.execute(text("ALTER TABLE prospects ALTER COLUMN send_status DROP DEFAULT"))
            conn.execute(text("ALTER TABLE prospects ALTER COLUMN send_status SET DEFAULT 'pending'"))
        
        # Make NOT NULL if currently nullable
        if is_nullable:
            conn.execute(text("ALTER TABLE prospects ALTER COLUMN send_status SET NOT NULL"))
        
        # Ensure index exists
        index_check = conn.execute(text("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename = 'prospects' 
            AND indexname = 'ix_prospects_send_status'
        """))
        if not index_check.fetchone():
            op.create_index('ix_prospects_send_status', 'prospects', ['send_status'])
    
    conn.commit()


def downgrade() -> None:
    """
    Downgrade is intentionally minimal - we don't want to drop columns
    that might be in use. If you need to remove these columns, do it manually.
    """
    # Note: We don't drop columns in downgrade to avoid data loss
    # If you need to remove these columns, do it manually with proper backups
    pass

