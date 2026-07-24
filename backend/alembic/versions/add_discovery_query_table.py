"""add_discovery_query_table

Revision ID: add_discovery_query
Revises: 4b9608290b5d
Create Date: 2025-11-30 17:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_discovery_query'
down_revision = '4b9608290b5d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Check if table already exists (idempotent)
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()
    
    # Create discovery_queries table (idempotent)
    if 'discovery_queries' not in existing_tables:
        op.create_table(
            'discovery_queries',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('job_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('keyword', sa.String(), nullable=False),
            sa.Column('location', sa.String(), nullable=False),
            sa.Column('location_code', sa.Integer(), nullable=True),
            sa.Column('category', sa.String(), nullable=True),
            sa.Column('status', sa.String(), nullable=False, server_default='pending'),
            sa.Column('results_found', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('results_saved', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('results_skipped_duplicate', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('results_skipped_existing', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('query_metadata', postgresql.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), onupdate=sa.text('now()')),
            sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ),
        )
        op.create_index('ix_discovery_queries_id', 'discovery_queries', ['id'])
        op.create_index('ix_discovery_queries_job_id', 'discovery_queries', ['job_id'])
        op.create_index('ix_discovery_queries_keyword', 'discovery_queries', ['keyword'])
        op.create_index('ix_discovery_queries_location', 'discovery_queries', ['location'])
        op.create_index('ix_discovery_queries_category', 'discovery_queries', ['category'])
        op.create_index('ix_discovery_queries_status', 'discovery_queries', ['status'])
        op.create_index('ix_discovery_queries_created_at', 'discovery_queries', ['created_at'])
    
    # NOTE: discovery_query_id column is added in migration 556b79de2825
    # This migration only creates the discovery_queries table


def downgrade() -> None:
    # NOTE: discovery_query_id removal is handled in migration 556b79de2825 downgrade
    
    # Drop discovery_queries table
    op.drop_index('ix_discovery_queries_created_at', table_name='discovery_queries')
    op.drop_index('ix_discovery_queries_status', table_name='discovery_queries')
    op.drop_index('ix_discovery_queries_category', table_name='discovery_queries')
    op.drop_index('ix_discovery_queries_location', table_name='discovery_queries')
    op.drop_index('ix_discovery_queries_keyword', table_name='discovery_queries')
    op.drop_index('ix_discovery_queries_job_id', table_name='discovery_queries')
    op.drop_index('ix_discovery_queries_id', table_name='discovery_queries')
    op.drop_table('discovery_queries')
