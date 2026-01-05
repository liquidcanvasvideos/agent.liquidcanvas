"""Add social outreach columns to prospects table

Revision ID: add_social_columns
Revises: ensure_draft_send_status_columns
Create Date: 2026-01-03

This migration adds minimal columns to support social profiles in the existing prospects table.
No new tables are created - we reuse the prospects table for both website and social outreach.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = 'add_social_columns'
# Chain from add_serp_intent_fields which is the last migration in the current chain
down_revision = 'add_serp_intent_fields'
branch_labels = None
depends_on = None


def upgrade():
    """
    Add social outreach columns to prospects table.
    These columns are nullable to preserve existing website outreach data.
    """
    # Check if columns already exist (idempotent)
    conn = op.get_bind()
    
    # Get existing columns
    result = conn.execute(text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'prospects'
    """))
    existing_columns = {row[0] for row in result.fetchall()}
    
    # Add source_type column (website or social)
    if 'source_type' not in existing_columns:
        op.add_column('prospects', 
            sa.Column('source_type', sa.String(), 
                     server_default='website', 
                     nullable=False)
        )
        # Set default for existing rows
        try:
            op.execute(text("UPDATE prospects SET source_type = 'website' WHERE source_type IS NULL"))
        except Exception as e:
            print(f"⚠️  Warning setting default for source_type: {e}")
        # Add CHECK constraint (drop first if exists)
        try:
            op.execute(text("ALTER TABLE prospects DROP CONSTRAINT IF EXISTS check_source_type"))
        except Exception:
            pass
        try:
            op.execute(text("""
                ALTER TABLE prospects 
                ADD CONSTRAINT check_source_type 
                CHECK (source_type IN ('website', 'social'))
            """))
        except Exception as e:
            print(f"⚠️  Warning adding check_source_type constraint: {e}")
        # Create index (drop first if exists)
        try:
            op.drop_index('ix_prospects_source_type', table_name='prospects')
        except Exception:
            pass
        try:
            op.create_index('ix_prospects_source_type', 'prospects', ['source_type'])
        except Exception as e:
            print(f"⚠️  Warning creating index: {e}")
        print("✅ Added source_type column")
    else:
        print("ℹ️  source_type column already exists")
    
    # Add source_platform column (linkedin, instagram, facebook, tiktok)
    if 'source_platform' not in existing_columns:
        op.add_column('prospects',
            sa.Column('source_platform', sa.String(), nullable=True)
        )
        # Add CHECK constraint (drop first if exists)
        try:
            op.execute(text("ALTER TABLE prospects DROP CONSTRAINT IF EXISTS check_source_platform"))
        except:
            pass
        op.execute(text("""
            ALTER TABLE prospects 
            ADD CONSTRAINT check_source_platform 
            CHECK (source_platform IS NULL OR source_platform IN ('linkedin', 'instagram', 'facebook', 'tiktok'))
        """))
        # Create index (drop first if exists)
        try:
            op.drop_index('ix_prospects_source_platform', table_name='prospects')
        except:
            pass
        op.create_index('ix_prospects_source_platform', 'prospects', ['source_platform'])
        print("✅ Added source_platform column")
    else:
        print("ℹ️  source_platform column already exists")
    
    # Add profile_url column (for social profiles)
    if 'profile_url' not in existing_columns:
        op.add_column('prospects',
            sa.Column('profile_url', sa.Text(), nullable=True)
        )
        op.create_index('ix_prospects_profile_url', 'prospects', ['profile_url'])
        print("✅ Added profile_url column")
    else:
        print("ℹ️  profile_url column already exists")
    
    # Add username column (for social profiles)
    if 'username' not in existing_columns:
        op.add_column('prospects',
            sa.Column('username', sa.String(), nullable=True)
        )
        op.create_index('ix_prospects_username', 'prospects', ['username'])
        print("✅ Added username column")
    else:
        print("ℹ️  username column already exists")
    
    # Add display_name column (for social profiles)
    if 'display_name' not in existing_columns:
        op.add_column('prospects',
            sa.Column('display_name', sa.String(), nullable=True)
        )
        print("✅ Added display_name column")
    else:
        print("ℹ️  display_name column already exists")
    
    # Add follower_count column
    if 'follower_count' not in existing_columns:
        op.add_column('prospects',
            sa.Column('follower_count', sa.Integer(), nullable=True)
        )
        print("✅ Added follower_count column")
    else:
        print("ℹ️  follower_count column already exists")
    
    # Add engagement_rate column
    if 'engagement_rate' not in existing_columns:
        op.add_column('prospects',
            sa.Column('engagement_rate', sa.Numeric(5, 2), nullable=True)
        )
        print("✅ Added engagement_rate column")
    else:
        print("ℹ️  engagement_rate column already exists")
    
    print("=" * 60)
    print("✅ Social columns added to prospects table")
    print("=" * 60)


def downgrade():
    """
    Remove social outreach columns from prospects table.
    WARNING: This will delete all social profile data.
    """
    # Remove indexes first
    conn = op.get_bind()
    
    try:
        op.drop_index('ix_prospects_engagement_rate', table_name='prospects')
    except:
        pass
    
    try:
        op.drop_index('ix_prospects_follower_count', table_name='prospects')
    except:
        pass
    
    try:
        op.drop_index('ix_prospects_display_name', table_name='prospects')
    except:
        pass
    
    try:
        op.drop_index('ix_prospects_username', table_name='prospects')
    except:
        pass
    
    try:
        op.drop_index('ix_prospects_profile_url', table_name='prospects')
    except:
        pass
    
    try:
        op.drop_index('ix_prospects_source_platform', table_name='prospects')
    except:
        pass
    
    try:
        op.drop_index('ix_prospects_source_type', table_name='prospects')
    except:
        pass
    
    # Drop constraints
    try:
        op.execute(text("ALTER TABLE prospects DROP CONSTRAINT IF EXISTS check_source_platform"))
    except:
        pass
    
    try:
        op.execute(text("ALTER TABLE prospects DROP CONSTRAINT IF EXISTS check_source_type"))
    except:
        pass
    
    # Drop columns
    try:
        op.drop_column('prospects', 'engagement_rate')
    except:
        pass
    
    try:
        op.drop_column('prospects', 'follower_count')
    except:
        pass
    
    try:
        op.drop_column('prospects', 'display_name')
    except:
        pass
    
    try:
        op.drop_column('prospects', 'username')
    except:
        pass
    
    try:
        op.drop_column('prospects', 'profile_url')
    except:
        pass
    
    try:
        op.drop_column('prospects', 'source_platform')
    except:
        pass
    
    try:
        op.drop_column('prospects', 'source_type')
    except:
        pass
    
    print("✅ Social columns removed from prospects table")

