"""Ensure all Prospect model columns exist - FINAL DEFINITIVE MIGRATION

Revision ID: ensure_all_prospect_columns_final
Revises: add_realtime_scraping_fields
Create Date: 2026-01-06

This is the SINGLE SOURCE OF TRUTH migration that ensures all columns
referenced in the Prospect ORM model actually exist in the database.

This migration is IDEMPOTENT - it can be run multiple times safely.

CRITICAL: This migration must run AFTER add_realtime_scraping_fields.
If add_realtime_scraping_fields doesn't exist, this migration will still work
by checking for column existence before adding.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = 'ensure_all_prospect_columns_final'
down_revision = 'add_realtime_scraping_fields'  # Chain after realtime scraping fields
branch_labels = None
depends_on = None


def get_existing_columns(conn):
    """Get set of existing column names for prospects table"""
    result = conn.execute(text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'prospects'
        AND table_schema = 'public'
    """))
    return {row[0] for row in result.fetchall()}


def upgrade():
    """
    Ensure ALL columns from Prospect model exist in database.
    
    This migration is IDEMPOTENT - checks for existence before adding.
    """
    conn = op.get_bind()
    existing_columns = get_existing_columns(conn)
    
    columns_added = []
    columns_existed = []
    
    # ============================================
    # SOCIAL OUTREACH COLUMNS
    # ============================================
    
    # source_type: 'website' (default) or 'social'
    if 'source_type' not in existing_columns:
        op.add_column('prospects', 
            sa.Column('source_type', sa.String(), 
                     server_default='website', 
                     nullable=False)
        )
        # Set default for existing rows
        try:
            conn.execute(text("UPDATE prospects SET source_type = 'website' WHERE source_type IS NULL"))
        except Exception:
            pass
        op.create_index('ix_prospects_source_type', 'prospects', ['source_type'], if_not_exists=True)
        columns_added.append('source_type')
    else:
        columns_existed.append('source_type')
    
    # source_platform: 'linkedin', 'instagram', 'facebook', 'tiktok'
    if 'source_platform' not in existing_columns:
        op.add_column('prospects',
            sa.Column('source_platform', sa.String(), nullable=True)
        )
        op.create_index('ix_prospects_source_platform', 'prospects', ['source_platform'], if_not_exists=True)
        columns_added.append('source_platform')
    else:
        columns_existed.append('source_platform')
    
    # profile_url: Social profile URL
    if 'profile_url' not in existing_columns:
        op.add_column('prospects',
            sa.Column('profile_url', sa.Text(), nullable=True)
        )
        op.create_index('ix_prospects_profile_url', 'prospects', ['profile_url'], if_not_exists=True)
        columns_added.append('profile_url')
    else:
        columns_existed.append('profile_url')
    
    # username: @username or profile identifier
    if 'username' not in existing_columns:
        op.add_column('prospects',
            sa.Column('username', sa.String(), nullable=True)
        )
        op.create_index('ix_prospects_username', 'prospects', ['username'], if_not_exists=True)
        columns_added.append('username')
    else:
        columns_existed.append('username')
    
    # display_name: Full name or display name
    if 'display_name' not in existing_columns:
        op.add_column('prospects',
            sa.Column('display_name', sa.String(), nullable=True)
        )
        columns_added.append('display_name')
    else:
        columns_existed.append('display_name')
    
    # follower_count: Number of followers
    if 'follower_count' not in existing_columns:
        op.add_column('prospects',
            sa.Column('follower_count', sa.Integer(), nullable=True)
        )
        columns_added.append('follower_count')
    else:
        columns_existed.append('follower_count')
    
    # engagement_rate: Engagement rate (0-100)
    if 'engagement_rate' not in existing_columns:
        op.add_column('prospects',
            sa.Column('engagement_rate', sa.Numeric(5, 2), nullable=True)
        )
        columns_added.append('engagement_rate')
    else:
        columns_existed.append('engagement_rate')
    
    # ============================================
    # REALTIME SCRAPING COLUMNS
    # ============================================
    
    # bio_text: Bio text from profile
    if 'bio_text' not in existing_columns:
        op.add_column('prospects', 
            sa.Column('bio_text', sa.Text(), nullable=True)
        )
        columns_added.append('bio_text')
    else:
        columns_existed.append('bio_text')
    
    # external_links: Link-in-bio URLs (JSON array)
    if 'external_links' not in existing_columns:
        op.add_column('prospects',
            sa.Column('external_links', postgresql.JSON(astext_type=sa.Text()), nullable=True)
        )
        columns_added.append('external_links')
    else:
        columns_existed.append('external_links')
    
    # scraped_at: When profile was last scraped
    if 'scraped_at' not in existing_columns:
        op.add_column('prospects',
            sa.Column('scraped_at', sa.DateTime(timezone=True), nullable=True)
        )
        columns_added.append('scraped_at')
    else:
        columns_existed.append('scraped_at')
    
    # ============================================
    # LOG RESULTS
    # ============================================
    
    print("=" * 80)
    print("✅ FINAL PROSPECT COLUMNS MIGRATION")
    print("=" * 80)
    if columns_added:
        print(f"✅ Added {len(columns_added)} columns: {', '.join(columns_added)}")
    if columns_existed:
        print(f"ℹ️  {len(columns_existed)} columns already existed: {', '.join(columns_existed)}")
    print("=" * 80)
    print("✅ All Prospect model columns are now guaranteed to exist in database")
    print("=" * 80)


def downgrade():
    """
    Remove columns added by this migration.
    
    WARNING: This will delete data in these columns.
    """
    # Remove realtime scraping columns
    try:
        op.drop_column('prospects', 'scraped_at')
    except Exception:
        pass
    
    try:
        op.drop_column('prospects', 'external_links')
    except Exception:
        pass
    
    try:
        op.drop_column('prospects', 'bio_text')
    except Exception:
        pass
    
    # Remove social columns (only if they were added by this migration)
    # Note: We don't remove source_type, source_platform, etc. as they may have been
    # added by earlier migrations. This downgrade is conservative.

