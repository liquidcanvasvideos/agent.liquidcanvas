"""add social outreach tables

Revision ID: add_social_tables
Revises: 999_final_schema_repair
Create Date: 2025-01-20 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_social_tables'
down_revision = 'final_schema_repair'  # Chain after final_schema_repair migration
branch_labels = None
depends_on = None


def upgrade():
    # Get existing tables first (for idempotent checks)
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()
    
    # Create enum types (idempotent - only create if they don't exist)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE socialplatform AS ENUM ('linkedin', 'instagram', 'tiktok');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE qualificationstatus AS ENUM ('pending', 'qualified', 'rejected');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE messagestatus AS ENUM ('pending', 'sent', 'failed', 'delivered', 'read');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Create enum types for use in table columns (with create_type=False to avoid duplicate creation)
    socialplatform_enum = postgresql.ENUM('linkedin', 'instagram', 'tiktok', name='socialplatform', create_type=False)
    qualificationstatus_enum = postgresql.ENUM('pending', 'qualified', 'rejected', name='qualificationstatus', create_type=False)
    messagestatus_enum = postgresql.ENUM('pending', 'sent', 'failed', 'delivered', 'read', name='messagestatus', create_type=False)
    
    # Create social_discovery_jobs table (idempotent)
    if 'social_discovery_jobs' not in existing_tables:
        op.create_table(
            'social_discovery_jobs',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('platform', socialplatform_enum, nullable=False),
            sa.Column('filters', postgresql.JSON, nullable=True),
            sa.Column('status', sa.String(), nullable=False, server_default='pending'),
            sa.Column('results_count', sa.Integer(), server_default='0'),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index('ix_social_discovery_jobs_id', 'social_discovery_jobs', ['id'])
        op.create_index('ix_social_discovery_jobs_platform', 'social_discovery_jobs', ['platform'])
        op.create_index('ix_social_discovery_jobs_status', 'social_discovery_jobs', ['status'])
    
    # Create social_profiles table (idempotent)
    if 'social_profiles' not in existing_tables:
        op.create_table(
            'social_profiles',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('platform', socialplatform_enum, nullable=False),
            sa.Column('handle', sa.String(), nullable=False),
            sa.Column('profile_url', sa.Text(), nullable=False, unique=True),
            sa.Column('display_name', sa.String(), nullable=True),
            sa.Column('bio', sa.Text(), nullable=True),
            sa.Column('followers_count', sa.Integer(), server_default='0'),
            sa.Column('location', sa.String(), nullable=True),
            sa.Column('is_business', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('qualification_status', qualificationstatus_enum, nullable=False, server_default='pending'),
            sa.Column('discovery_job_id', postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['discovery_job_id'], ['social_discovery_jobs.id'], ),
        )
        op.create_index('ix_social_profiles_id', 'social_profiles', ['id'])
        op.create_index('ix_social_profiles_platform', 'social_profiles', ['platform'])
        op.create_index('ix_social_profiles_handle', 'social_profiles', ['handle'])
        op.create_index('ix_social_profiles_profile_url', 'social_profiles', ['profile_url'])
        op.create_index('ix_social_profiles_qualification_status', 'social_profiles', ['qualification_status'])
        op.create_index('ix_social_profiles_discovery_job_id', 'social_profiles', ['discovery_job_id'])
    
    # Create social_drafts table (idempotent)
    if 'social_drafts' not in existing_tables:
        op.create_table(
            'social_drafts',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('profile_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('platform', socialplatform_enum, nullable=False),
            sa.Column('draft_body', sa.Text(), nullable=False),
            sa.Column('is_followup', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('sequence_index', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['profile_id'], ['social_profiles.id'], ),
        )
        op.create_index('ix_social_drafts_id', 'social_drafts', ['id'])
        op.create_index('ix_social_drafts_profile_id', 'social_drafts', ['profile_id'])
    
    # Create social_messages table (idempotent)
    if 'social_messages' not in existing_tables:
        op.create_table(
            'social_messages',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('profile_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('platform', socialplatform_enum, nullable=False),
            sa.Column('message_body', sa.Text(), nullable=False),
            sa.Column('status', messagestatus_enum, nullable=False, server_default='pending'),
            sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['profile_id'], ['social_profiles.id'], ),
        )
        op.create_index('ix_social_messages_id', 'social_messages', ['id'])
        op.create_index('ix_social_messages_profile_id', 'social_messages', ['profile_id'])
        op.create_index('ix_social_messages_status', 'social_messages', ['status'])


def downgrade():
    op.drop_table('social_messages')
    op.drop_table('social_drafts')
    op.drop_table('social_profiles')
    op.drop_table('social_discovery_jobs')
    
    op.execute("DROP TYPE IF EXISTS messagestatus")
    op.execute("DROP TYPE IF EXISTS qualificationstatus")
    op.execute("DROP TYPE IF EXISTS socialplatform")

