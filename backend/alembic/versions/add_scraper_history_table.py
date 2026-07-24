"""add_scraper_history_table

Revision ID: add_scraper_history
Revises: 556b79de2825
Create Date: 2025-12-01 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_scraper_history'
down_revision = '556b79de2825'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Check if table already exists (idempotent)
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()
    
    # Create scraper_history table (idempotent)
    if 'scraper_history' not in existing_tables:
        op.create_table(
            'scraper_history',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('triggered_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('success_count', sa.Integer(), default=0),
            sa.Column('failed_count', sa.Integer(), default=0),
            sa.Column('duration_seconds', sa.Numeric(10, 2), nullable=True),
            sa.Column('status', sa.String(), default='running', nullable=False),
            sa.Column('error_message', sa.String(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        )
        op.create_index('ix_scraper_history_id', 'scraper_history', ['id'])
        op.create_index('ix_scraper_history_triggered_at', 'scraper_history', ['triggered_at'])
        op.create_index('ix_scraper_history_status', 'scraper_history', ['status'])
        op.create_index('ix_scraper_history_created_at', 'scraper_history', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_scraper_history_created_at', table_name='scraper_history')
    op.drop_index('ix_scraper_history_status', table_name='scraper_history')
    op.drop_index('ix_scraper_history_triggered_at', table_name='scraper_history')
    op.drop_index('ix_scraper_history_id', table_name='scraper_history')
    op.drop_table('scraper_history')
