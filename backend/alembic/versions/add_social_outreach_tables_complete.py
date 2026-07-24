"""add social outreach tables - COMPLETE SCHEMA

Revision ID: add_social_tables_complete
Revises: add_social_tables
Create Date: 2025-01-21 12:00:00.000000

This migration adds all required columns for social outreach functionality.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_social_tables_complete'
down_revision = 'add_social_tables'  # Chain after existing social tables migration
branch_labels = None
depends_on = None


def upgrade():
    """Add missing columns to social_profiles and social_messages tables"""
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # Check if social_profiles table exists
    if 'social_profiles' in inspector.get_table_names():
        # Get existing columns
        existing_columns = {col['name'] for col in inspector.get_columns('social_profiles')}
        
        # Add missing columns to social_profiles
        if 'engagement_rate' not in existing_columns:
            op.add_column('social_profiles', sa.Column('engagement_rate', sa.Float(), nullable=True))
        
        if 'category' not in existing_columns:
            op.add_column('social_profiles', sa.Column('category', sa.String(), nullable=True))
        
        # Create enum types for status fields if they don't exist
        op.execute("""
            DO $$ BEGIN
                CREATE TYPE socialdiscoverystatus AS ENUM ('pending', 'discovered', 'qualified', 'rejected');
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """)
        
        op.execute("""
            DO $$ BEGIN
                CREATE TYPE socialdraftstatus AS ENUM ('none', 'drafting', 'drafted', 'reviewing');
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """)
        
        op.execute("""
            DO $$ BEGIN
                CREATE TYPE socialsendstatus AS ENUM ('none', 'sending', 'sent', 'failed');
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """)
        
        if 'discovery_status' not in existing_columns:
            op.add_column('social_profiles', sa.Column('discovery_status', sa.Enum('pending', 'discovered', 'qualified', 'rejected', name='socialdiscoverystatus'), nullable=True, server_default='pending'))
            op.create_index('ix_social_profiles_discovery_status', 'social_profiles', ['discovery_status'])
        
        if 'draft_status' not in existing_columns:
            op.add_column('social_profiles', sa.Column('draft_status', sa.Enum('none', 'drafting', 'drafted', 'reviewing', name='socialdraftstatus'), nullable=True, server_default='none'))
            op.create_index('ix_social_profiles_draft_status', 'social_profiles', ['draft_status'])
        
        if 'send_status' not in existing_columns:
            op.add_column('social_profiles', sa.Column('send_status', sa.Enum('none', 'sending', 'sent', 'failed', name='socialsendstatus'), nullable=True, server_default='none'))
            op.create_index('ix_social_profiles_send_status', 'social_profiles', ['send_status'])
        
        if 'followups_sent' not in existing_columns:
            op.add_column('social_profiles', sa.Column('followups_sent', sa.Integer(), nullable=False, server_default='0'))
        
        if 'last_contacted' not in existing_columns:
            op.add_column('social_profiles', sa.Column('last_contacted', sa.DateTime(timezone=True), nullable=True))
        
        if 'thread_id' not in existing_columns:
            op.add_column('social_profiles', sa.Column('thread_id', sa.Text(), nullable=True))
            op.create_index('ix_social_profiles_thread_id', 'social_profiles', ['thread_id'])
    
    # Check if social_messages table exists
    if 'social_messages' in inspector.get_table_names():
        existing_msg_columns = {col['name'] for col in inspector.get_columns('social_messages')}
        
        # Create message_type enum if it doesn't exist
        op.execute("""
            DO $$ BEGIN
                CREATE TYPE socialmessagetype AS ENUM ('draft', 'followup', 'initial');
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """)
        
        if 'message_type' not in existing_msg_columns:
            op.add_column('social_messages', sa.Column('message_type', sa.Enum('draft', 'followup', 'initial', name='socialmessagetype'), nullable=True, server_default='initial'))
            op.create_index('ix_social_messages_message_type', 'social_messages', ['message_type'])
    
    # Ensure social_discovery_jobs has completed_at if missing
    if 'social_discovery_jobs' in inspector.get_table_names():
        existing_job_columns = {col['name'] for col in inspector.get_columns('social_discovery_jobs')}
        if 'completed_at' not in existing_job_columns:
            op.add_column('social_discovery_jobs', sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True))
        
        # Rename filters to payload if needed (or add payload if filters exists)
        if 'payload' not in existing_job_columns and 'filters' in existing_job_columns:
            # Keep filters, but also add payload as alias
            op.add_column('social_discovery_jobs', sa.Column('payload', postgresql.JSON, nullable=True))
            # Copy data from filters to payload
            op.execute("UPDATE social_discovery_jobs SET payload = filters WHERE filters IS NOT NULL")


def downgrade():
    """Remove added columns"""
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    
    if 'social_profiles' in inspector.get_table_names():
        existing_columns = {col['name'] for col in inspector.get_columns('social_profiles')}
        
        if 'thread_id' in existing_columns:
            op.drop_index('ix_social_profiles_thread_id', 'social_profiles')
            op.drop_column('social_profiles', 'thread_id')
        if 'last_contacted' in existing_columns:
            op.drop_column('social_profiles', 'last_contacted')
        if 'followups_sent' in existing_columns:
            op.drop_column('social_profiles', 'followups_sent')
        if 'send_status' in existing_columns:
            op.drop_index('ix_social_profiles_send_status', 'social_profiles')
            op.drop_column('social_profiles', 'send_status')
        if 'draft_status' in existing_columns:
            op.drop_index('ix_social_profiles_draft_status', 'social_profiles')
            op.drop_column('social_profiles', 'draft_status')
        if 'discovery_status' in existing_columns:
            op.drop_index('ix_social_profiles_discovery_status', 'social_profiles')
            op.drop_column('social_profiles', 'discovery_status')
        if 'category' in existing_columns:
            op.drop_column('social_profiles', 'category')
        if 'engagement_rate' in existing_columns:
            op.drop_column('social_profiles', 'engagement_rate')
    
    if 'social_messages' in inspector.get_table_names():
        existing_msg_columns = {col['name'] for col in inspector.get_columns('social_messages')}
        if 'message_type' in existing_msg_columns:
            op.drop_index('ix_social_messages_message_type', 'social_messages')
            op.drop_column('social_messages', 'message_type')
    
    if 'social_discovery_jobs' in inspector.get_table_names():
        existing_job_columns = {col['name'] for col in inspector.get_columns('social_discovery_jobs')}
        if 'completed_at' in existing_job_columns:
            op.drop_column('social_discovery_jobs', 'completed_at')
        if 'payload' in existing_job_columns:
            op.drop_column('social_discovery_jobs', 'payload')
    
    # Drop enum types
    op.execute("DROP TYPE IF EXISTS socialmessagetype")
    op.execute("DROP TYPE IF EXISTS socialsendstatus")
    op.execute("DROP TYPE IF EXISTS socialdraftstatus")
    op.execute("DROP TYPE IF EXISTS socialdiscoverystatus")

