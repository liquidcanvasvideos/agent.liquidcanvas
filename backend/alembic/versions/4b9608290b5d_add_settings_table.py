"""add_settings_table

Revision ID: 4b9608290b5d
Revises: 
Create Date: 2025-11-29 16:14:12.577412

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4b9608290b5d'
down_revision = '000000000000'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Check if table already exists (idempotent)
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()
    
    # Create settings table (idempotent)
    if 'settings' not in existing_tables:
        op.create_table(
            'settings',
            sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('key', sa.String(), nullable=False),
            sa.Column('value', sa.dialects.postgresql.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), onupdate=sa.text('now()')),
            sa.UniqueConstraint('key', name='uq_settings_key')
        )
        op.create_index('ix_settings_key', 'settings', ['key'])


def downgrade() -> None:
    op.drop_index('ix_settings_key', table_name='settings')
    op.drop_table('settings')
