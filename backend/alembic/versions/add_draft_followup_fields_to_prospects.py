"""add draft and followup fields to prospects

Revision ID: add_draft_followup_fields
Revises: add_stage_column
Create Date: 2025-01-19 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = 'add_draft_followup_fields'
down_revision = 'add_stage_column'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add draft and follow-up fields to prospects table.
    These fields support manual input, draft-only composing, and follow-up email tracking.
    """
    conn = op.get_bind()
    
    # Check and add drafted_at column
    result = conn.execute(text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'prospects' 
        AND column_name = 'drafted_at'
    """))
    if not result.fetchone():
        op.add_column('prospects', sa.Column(
            'drafted_at',
            sa.DateTime(timezone=True),
            nullable=True
        ))
        print("✅ Added drafted_at column")
    
    # Check and add final_body column
    result = conn.execute(text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'prospects' 
        AND column_name = 'final_body'
    """))
    if not result.fetchone():
        op.add_column('prospects', sa.Column(
            'final_body',
            sa.Text(),
            nullable=True
        ))
        print("✅ Added final_body column")
    
    # Check and add thread_id column
    result = conn.execute(text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'prospects' 
        AND column_name = 'thread_id'
    """))
    if not result.fetchone():
        op.add_column('prospects', sa.Column(
            'thread_id',
            UUID(as_uuid=True),
            nullable=True
        ))
        # Create index for thread_id
        op.create_index('ix_prospects_thread_id', 'prospects', ['thread_id'])
        print("✅ Added thread_id column with index")
    
    # Check and add sequence_index column
    result = conn.execute(text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'prospects' 
        AND column_name = 'sequence_index'
    """))
    if not result.fetchone():
        op.add_column('prospects', sa.Column(
            'sequence_index',
            sa.Integer(),
            nullable=True,
            server_default='0'
        ))
        # Backfill existing rows to 0
        conn.execute(text("""
            UPDATE prospects 
            SET sequence_index = 0 
            WHERE sequence_index IS NULL
        """))
        # Make NOT NULL after backfill
        conn.execute(text("""
            ALTER TABLE prospects 
            ALTER COLUMN sequence_index SET NOT NULL,
            ALTER COLUMN sequence_index SET DEFAULT 0
        """))
        print("✅ Added sequence_index column")
    
    # Check and add is_manual column (as BOOLEAN, not String)
    result = conn.execute(text("""
        SELECT column_name, data_type
        FROM information_schema.columns 
        WHERE table_name = 'prospects' 
        AND column_name = 'is_manual'
    """))
    existing = result.fetchone()
    if not existing:
        # Column doesn't exist - add as BOOLEAN
        op.add_column('prospects', sa.Column(
            'is_manual',
            sa.Boolean(),
            nullable=True,
            server_default='false'
        ))
        # Backfill existing rows to false
        conn.execute(text("""
            UPDATE prospects 
            SET is_manual = false 
            WHERE is_manual IS NULL
        """))
        print("✅ Added is_manual column as BOOLEAN")
    elif existing[1] != 'boolean':
        # Column exists but is wrong type (String) - convert to Boolean
        print("⚠️  is_manual exists as non-boolean, converting...")
        # Convert 'true'/'false' strings to boolean
        conn.execute(text("""
            UPDATE prospects 
            SET is_manual = CASE 
                WHEN is_manual::text = 'true' THEN true
                ELSE false
            END
            WHERE is_manual IS NOT NULL
        """))
        # Drop old column and recreate as boolean
        op.drop_column('prospects', 'is_manual')
        op.add_column('prospects', sa.Column(
            'is_manual',
            sa.Boolean(),
            nullable=True,
            server_default='false'
        ))
        print("✅ Converted is_manual to BOOLEAN")
    
    # Ensure draft_subject and draft_body exist (they should, but check)
    for col_name in ['draft_subject', 'draft_body']:
        result = conn.execute(text(f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'prospects' 
            AND column_name = '{col_name}'
        """))
        if not result.fetchone():
            op.add_column('prospects', sa.Column(
                col_name,
                sa.Text(),
                nullable=True
            ))
            print(f"✅ Added {col_name} column")
    
    # Ensure last_sent and followups_sent exist
    for col_name, col_type, default in [
        ('last_sent', sa.DateTime(timezone=True), None),
        ('followups_sent', sa.Integer(), '0')
    ]:
        result = conn.execute(text(f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'prospects' 
            AND column_name = '{col_name}'
        """))
        if not result.fetchone():
            col_def = sa.Column(
                col_name,
                col_type,
                nullable=True
            )
            if default:
                col_def.server_default = default
            op.add_column('prospects', col_def)
            print(f"✅ Added {col_name} column")
    
    conn.commit()


def downgrade() -> None:
    """
    Remove draft and follow-up fields (for rollback safety)
    """
    conn = op.get_bind()
    
    # Drop indexes first
    index_check = conn.execute(text("""
        SELECT indexname 
        FROM pg_indexes 
        WHERE tablename = 'prospects' 
        AND indexname = 'ix_prospects_thread_id'
    """))
    if index_check.fetchone():
        op.drop_index('ix_prospects_thread_id', table_name='prospects')
    
    # Drop columns (only if they exist)
    columns_to_drop = ['drafted_at', 'final_body', 'thread_id', 'sequence_index', 'is_manual']
    for col_name in columns_to_drop:
        result = conn.execute(text(f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'prospects' 
            AND column_name = '{col_name}'
        """))
        if result.fetchone():
            op.drop_column('prospects', col_name)
    
    conn.commit()

