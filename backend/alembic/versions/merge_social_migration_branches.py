"""merge social migration branches

Revision ID: merge_social_branches
Revises: ('update_social_complete', 'ensure_critical_columns')
Create Date: 2026-01-03 12:00:00.000000

This migration merges the two social migration branches:
- update_social_complete (adds new social model fields)
- ensure_critical_columns (ensures website prospect columns exist)

After this merge, there will be a single head revision.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'merge_social_branches'
down_revision = ('update_social_complete', 'ensure_critical_columns')  # Merge both branches
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Merge migration - no schema changes needed.
    Both branches have already applied their changes.
    This just creates a single head for future migrations.
    """
    # No-op migration - just merges the branches
    pass


def downgrade() -> None:
    """
    Downgrade - no-op since this is just a merge point.
    """
    pass

