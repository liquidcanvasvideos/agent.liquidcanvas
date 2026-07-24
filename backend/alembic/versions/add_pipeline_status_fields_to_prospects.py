"""add pipeline status fields to prospects

Revision ID: add_pipeline_status_fields
Revises: add_serp_intent_fields
Create Date: 2025-12-17 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_pipeline_status_fields'
down_revision = 'add_serp_intent_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add pipeline status fields
    op.add_column('prospects', sa.Column('discovery_status', sa.String(), nullable=True, server_default='pending'))
    op.add_column('prospects', sa.Column('approval_status', sa.String(), nullable=True, server_default='pending'))
    op.add_column('prospects', sa.Column('scrape_status', sa.String(), nullable=True, server_default='pending'))
    op.add_column('prospects', sa.Column('verification_status', sa.String(), nullable=True, server_default='pending'))
    op.add_column('prospects', sa.Column('draft_status', sa.String(), nullable=True, server_default='pending'))
    op.add_column('prospects', sa.Column('send_status', sa.String(), nullable=True, server_default='pending'))
    
    # Add discovery metadata fields
    op.add_column('prospects', sa.Column('discovery_category', sa.String(), nullable=True))
    op.add_column('prospects', sa.Column('discovery_location', sa.String(), nullable=True))
    op.add_column('prospects', sa.Column('discovery_keywords', sa.Text(), nullable=True))
    
    # Add scraping metadata fields
    op.add_column('prospects', sa.Column('scrape_payload', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    op.add_column('prospects', sa.Column('scrape_source_url', sa.Text(), nullable=True))
    
    # Add verification metadata fields
    op.add_column('prospects', sa.Column('verification_confidence', sa.Numeric(precision=5, scale=2), nullable=True))
    op.add_column('prospects', sa.Column('verification_payload', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    
    # Create indexes for status fields
    op.create_index('ix_prospects_discovery_status', 'prospects', ['discovery_status'])
    op.create_index('ix_prospects_approval_status', 'prospects', ['approval_status'])
    op.create_index('ix_prospects_scrape_status', 'prospects', ['scrape_status'])
    op.create_index('ix_prospects_verification_status', 'prospects', ['verification_status'])
    op.create_index('ix_prospects_draft_status', 'prospects', ['draft_status'])
    op.create_index('ix_prospects_send_status', 'prospects', ['send_status'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_prospects_send_status', table_name='prospects')
    op.drop_index('ix_prospects_draft_status', table_name='prospects')
    op.drop_index('ix_prospects_verification_status', table_name='prospects')
    op.drop_index('ix_prospects_scrape_status', table_name='prospects')
    op.drop_index('ix_prospects_approval_status', table_name='prospects')
    op.drop_index('ix_prospects_discovery_status', table_name='prospects')
    
    # Remove columns
    op.drop_column('prospects', 'verification_payload')
    op.drop_column('prospects', 'verification_confidence')
    op.drop_column('prospects', 'scrape_source_url')
    op.drop_column('prospects', 'scrape_payload')
    op.drop_column('prospects', 'discovery_keywords')
    op.drop_column('prospects', 'discovery_location')
    op.drop_column('prospects', 'discovery_category')
    op.drop_column('prospects', 'send_status')
    op.drop_column('prospects', 'draft_status')
    op.drop_column('prospects', 'verification_status')
    op.drop_column('prospects', 'scrape_status')
    op.drop_column('prospects', 'approval_status')
    op.drop_column('prospects', 'discovery_status')

