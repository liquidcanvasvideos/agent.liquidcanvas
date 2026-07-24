"""merge_all_migration_heads

Revision ID: de8b5344821d
Revises: add_scraper_history, ensure_alembic_version_table, fix_scrape_status_discovered, merge_social_branches
Create Date: 2026-01-10 22:24:50.735967

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'de8b5344821d'
down_revision = ('add_scraper_history', 'ensure_alembic_version_table', 'fix_scrape_status_discovered', 'merge_social_branches')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

