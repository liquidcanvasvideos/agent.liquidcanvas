"""create_base_tables_jobs_prospects_email_logs

Revision ID: 000000000000
Revises: 
Create Date: 2025-12-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '000000000000'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Check if tables already exist (idempotent)
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()
    
    # Create jobs table (idempotent)
    if 'jobs' not in existing_tables:
        op.create_table(
            'jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('job_type', sa.String(), nullable=False),
        sa.Column('params', postgresql.JSON(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('result', postgresql.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), onupdate=sa.text('now()')),
    )
    op.create_index('ix_jobs_id', 'jobs', ['id'])
    op.create_index('ix_jobs_job_type', 'jobs', ['job_type'])
    op.create_index('ix_jobs_status', 'jobs', ['status'])
        op.create_index('ix_jobs_created_at', 'jobs', ['created_at'])
    
    # Create prospects table (idempotent)
    if 'prospects' not in existing_tables:
        op.create_table((
        'prospects',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('domain', sa.String(), nullable=False),
        sa.Column('page_url', sa.Text(), nullable=True),
        sa.Column('page_title', sa.Text(), nullable=True),
        sa.Column('contact_email', sa.String(), nullable=True),
        sa.Column('contact_method', sa.String(), nullable=True),
        sa.Column('da_est', sa.Numeric(5, 2), nullable=True),
        sa.Column('score', sa.Numeric(5, 2), nullable=True, server_default='0'),
        sa.Column('outreach_status', sa.String(), nullable=True, server_default='pending'),
        sa.Column('last_sent', sa.DateTime(timezone=True), nullable=True),
        sa.Column('followups_sent', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('draft_subject', sa.Text(), nullable=True),
        sa.Column('draft_body', sa.Text(), nullable=True),
        sa.Column('dataforseo_payload', postgresql.JSON(), nullable=True),
        sa.Column('hunter_payload', postgresql.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), onupdate=sa.text('now()')),
    )
    op.create_index('ix_prospects_id', 'prospects', ['id'])
    op.create_index('ix_prospects_domain', 'prospects', ['domain'])
    op.create_index('ix_prospects_contact_email', 'prospects', ['contact_email'])
    op.create_index('ix_prospects_outreach_status', 'prospects', ['outreach_status'])
        op.create_index('ix_prospects_created_at', 'prospects', ['created_at'])
    
    # Create email_logs table (idempotent)
    if 'email_logs' not in existing_tables:
        op.create_table(
            'email_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('prospect_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('subject', sa.Text(), nullable=True),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('response', postgresql.JSON(), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['prospect_id'], ['prospects.id'], ),
    )
    op.create_index('ix_email_logs_id', 'email_logs', ['id'])
    op.create_index('ix_email_logs_prospect_id', 'email_logs', ['prospect_id'])
    op.create_index('ix_email_logs_sent_at', 'email_logs', ['sent_at'])


def downgrade() -> None:
    op.drop_index('ix_email_logs_sent_at', table_name='email_logs')
    op.drop_index('ix_email_logs_prospect_id', table_name='email_logs')
    op.drop_index('ix_email_logs_id', table_name='email_logs')
    op.drop_table('email_logs')
    
    op.drop_index('ix_prospects_created_at', table_name='prospects')
    op.drop_index('ix_prospects_outreach_status', table_name='prospects')
    op.drop_index('ix_prospects_contact_email', table_name='prospects')
    op.drop_index('ix_prospects_domain', table_name='prospects')
    op.drop_index('ix_prospects_id', table_name='prospects')
    op.drop_table('prospects')
    
    op.drop_index('ix_jobs_created_at', table_name='jobs')
    op.drop_index('ix_jobs_status', table_name='jobs')
    op.drop_index('ix_jobs_job_type', table_name='jobs')
    op.drop_index('ix_jobs_id', table_name='jobs')
    op.drop_table('jobs')

