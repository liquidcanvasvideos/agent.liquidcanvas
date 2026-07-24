"""Add real-time scraping fields to prospects

Revision ID: add_realtime_scraping_fields
Revises: 
Create Date: 2024-01-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_realtime_scraping_fields'
down_revision = 'add_social_columns'  # Chain after social columns migration
branch_labels = None
depends_on = None


def upgrade():
    # Check if columns already exist (idempotent)
    from sqlalchemy import text
    conn = op.get_bind()
    
    # Get existing columns
    result = conn.execute(text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'prospects'
    """))
    existing_columns = {row[0] for row in result.fetchall()}
    
    # Add bio_text field for social profiles (if not exists)
    if 'bio_text' not in existing_columns:
        op.add_column('prospects', sa.Column('bio_text', sa.Text(), nullable=True))
        print("✅ Added bio_text column")
    else:
        print("ℹ️  bio_text column already exists")
    
    # Add external_links JSON field for link-in-bio URLs (if not exists)
    if 'external_links' not in existing_columns:
        op.add_column('prospects', sa.Column('external_links', postgresql.JSON(astext_type=sa.Text()), nullable=True))
        print("✅ Added external_links column")
    else:
        print("ℹ️  external_links column already exists")
    
    # Add scraped_at timestamp (if not exists)
    if 'scraped_at' not in existing_columns:
        op.add_column('prospects', sa.Column('scraped_at', sa.DateTime(timezone=True), nullable=True))
        print("✅ Added scraped_at column")
    else:
        print("ℹ️  scraped_at column already exists")
    
    # Update scrape_status to support more granular states
    # Values: pending, scraping, complete, failed (in addition to existing DISCOVERED, SCRAPED, etc.)
    # This is already a String column, so no migration needed, just documentation


def downgrade():
    op.drop_column('prospects', 'scraped_at')
    op.drop_column('prospects', 'external_links')
    op.drop_column('prospects', 'bio_text')

