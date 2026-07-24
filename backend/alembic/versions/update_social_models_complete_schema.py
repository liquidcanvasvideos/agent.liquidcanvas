"""update social models - complete schema

Revision ID: update_social_complete
Revises: add_social_tables_complete
Create Date: 2026-01-03 00:00:00.000000

This migration updates social models to match new requirements:
- Add username, full_name, category, engagement_score to social_profiles
- Add discovery_status and outreach_status enums
- Add Facebook platform support
- Update SocialDiscoveryJob with categories, locations, keywords arrays
- Update SocialMessage with message_type enum and thread_id
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'update_social_complete'
down_revision = 'add_social_tables_complete'  # Chain after existing social migration
branch_labels = None
depends_on = None


def upgrade():
    """Update social tables to match new schema requirements"""
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # Check if social_profiles table exists
    if 'social_profiles' not in inspector.get_table_names():
        # If table doesn't exist, this migration will be skipped
        # The initial migration should have created it
        return
    
    existing_columns = {col['name'] for col in inspector.get_columns('social_profiles')}
    
    # Add new columns to social_profiles
    if 'username' not in existing_columns:
        op.add_column('social_profiles', sa.Column('username', sa.String(255), nullable=True))
        # Backfill from handle if it exists
        op.execute("""
            UPDATE social_profiles 
            SET username = handle 
            WHERE username IS NULL AND handle IS NOT NULL
        """)
        # Make it NOT NULL after backfill
        op.alter_column('social_profiles', 'username', nullable=False)
        op.create_index('ix_social_profiles_username', 'social_profiles', ['username'])
    
    if 'full_name' not in existing_columns:
        op.add_column('social_profiles', sa.Column('full_name', sa.String(255), nullable=True))
        # Backfill from display_name if it exists
        op.execute("""
            UPDATE social_profiles 
            SET full_name = display_name 
            WHERE full_name IS NULL AND display_name IS NOT NULL
        """)
    
    if 'category' not in existing_columns:
        op.add_column('social_profiles', sa.Column('category', sa.String(50), nullable=True))
        op.create_index('ix_social_profiles_category', 'social_profiles', ['category'])
    
    if 'engagement_score' not in existing_columns:
        op.add_column('social_profiles', sa.Column('engagement_score', sa.Float(), nullable=False, server_default='0.0'))
    
    # Create new enum types
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE socialdiscoverystatus AS ENUM ('discovered', 'reviewed', 'qualified', 'rejected');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE socialoutreachstatus AS ENUM ('pending', 'drafted', 'sent', 'followup', 'closed');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE messagetype AS ENUM ('initial', 'followup');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Update platform enum to include Facebook
    op.execute("""
        DO $$ BEGIN
            ALTER TYPE socialplatform ADD VALUE IF NOT EXISTS 'facebook';
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Add discovery_status column if it doesn't exist
    if 'discovery_status' not in existing_columns:
        op.add_column('social_profiles', sa.Column(
            'discovery_status',
            postgresql.ENUM('discovered', 'reviewed', 'qualified', 'rejected', name='socialdiscoverystatus'),
            nullable=False,
            server_default='discovered'
        ))
        op.create_index('ix_social_profiles_discovery_status', 'social_profiles', ['discovery_status'])
    else:
        # If column exists, ensure it uses the correct enum type
        # This is idempotent - won't fail if already correct
        pass
    
    # Add outreach_status column if it doesn't exist
    if 'outreach_status' not in existing_columns:
        op.add_column('social_profiles', sa.Column(
            'outreach_status',
            postgresql.ENUM('pending', 'drafted', 'sent', 'followup', 'closed', name='socialoutreachstatus'),
            nullable=False,
            server_default='pending'
        ))
        op.create_index('ix_social_profiles_outreach_status', 'social_profiles', ['outreach_status'])
    
    # Update social_discovery_jobs table
    if 'social_discovery_jobs' in inspector.get_table_names():
        job_columns = {col['name'] for col in inspector.get_columns('social_discovery_jobs')}
        
        if 'categories' not in job_columns:
            op.add_column('social_discovery_jobs', sa.Column('categories', postgresql.ARRAY(sa.String()), nullable=True))
        
        if 'locations' not in job_columns:
            op.add_column('social_discovery_jobs', sa.Column('locations', postgresql.ARRAY(sa.String()), nullable=True))
        
        if 'keywords' not in job_columns:
            op.add_column('social_discovery_jobs', sa.Column('keywords', postgresql.ARRAY(sa.String()), nullable=True))
        
        if 'parameters' not in job_columns:
            op.add_column('social_discovery_jobs', sa.Column('parameters', postgresql.JSONB(), nullable=True))
    
    # Update social_messages table
    if 'social_messages' in inspector.get_table_names():
        msg_columns = {col['name'] for col in inspector.get_columns('social_messages')}
        
        if 'message_type' not in msg_columns:
            op.add_column('social_messages', sa.Column(
                'message_type',
                postgresql.ENUM('initial', 'followup', name='messagetype'),
                nullable=False,
                server_default='initial'
            ))
            op.create_index('ix_social_messages_message_type', 'social_messages', ['message_type'])
        else:
            # Ensure it uses the correct enum type
            pass
        
        if 'thread_id' not in msg_columns:
            op.add_column('social_messages', sa.Column('thread_id', postgresql.UUID(as_uuid=True), nullable=True))
            op.create_index('ix_social_messages_thread_id', 'social_messages', ['thread_id'])
        
        if 'draft_body' not in msg_columns:
            op.add_column('social_messages', sa.Column('draft_body', sa.Text(), nullable=True))
        
        if 'sent_body' not in msg_columns:
            # Rename message_body to sent_body if message_body exists
            if 'message_body' in msg_columns:
                op.alter_column('social_messages', 'message_body', new_column_name='sent_body')
            else:
                op.add_column('social_messages', sa.Column('sent_body', sa.Text(), nullable=True))


def downgrade():
    """Revert schema changes"""
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    
    if 'social_profiles' not in inspector.get_table_names():
        return
    
    existing_columns = {col['name'] for col in inspector.get_columns('social_profiles')}
    
    # Remove new columns from social_profiles
    if 'username' in existing_columns:
        op.drop_index('ix_social_profiles_username', 'social_profiles')
        op.drop_column('social_profiles', 'username')
    
    if 'full_name' in existing_columns:
        op.drop_column('social_profiles', 'full_name')
    
    if 'category' in existing_columns:
        op.drop_index('ix_social_profiles_category', 'social_profiles')
        op.drop_column('social_profiles', 'category')
    
    if 'engagement_score' in existing_columns:
        op.drop_column('social_profiles', 'engagement_score')
    
    if 'discovery_status' in existing_columns:
        op.drop_index('ix_social_profiles_discovery_status', 'social_profiles')
        op.drop_column('social_profiles', 'discovery_status')
    
    if 'outreach_status' in existing_columns:
        op.drop_index('ix_social_profiles_outreach_status', 'social_profiles')
        op.drop_column('social_profiles', 'outreach_status')
    
    # Update social_discovery_jobs
    if 'social_discovery_jobs' in inspector.get_table_names():
        job_columns = {col['name'] for col in inspector.get_columns('social_discovery_jobs')}
        
        if 'categories' in job_columns:
            op.drop_column('social_discovery_jobs', 'categories')
        
        if 'locations' in job_columns:
            op.drop_column('social_discovery_jobs', 'locations')
        
        if 'keywords' in job_columns:
            op.drop_column('social_discovery_jobs', 'keywords')
        
        if 'parameters' in job_columns:
            op.drop_column('social_discovery_jobs', 'parameters')
    
    # Update social_messages
    if 'social_messages' in inspector.get_table_names():
        msg_columns = {col['name'] for col in inspector.get_columns('social_messages')}
        
        if 'message_type' in msg_columns:
            op.drop_index('ix_social_messages_message_type', 'social_messages')
            op.drop_column('social_messages', 'message_type')
        
        if 'thread_id' in msg_columns:
            op.drop_index('ix_social_messages_thread_id', 'social_messages')
            op.drop_column('social_messages', 'thread_id')
        
        if 'draft_body' in msg_columns:
            op.drop_column('social_messages', 'draft_body')
        
        if 'sent_body' in msg_columns and 'message_body' not in msg_columns:
            op.alter_column('social_messages', 'sent_body', new_column_name='message_body')

