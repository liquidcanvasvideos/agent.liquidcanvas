"""add serp_intent fields to prospects

Revision ID: add_serp_intent_fields
Revises: 556b79de2825
Create Date: 2025-12-16 22:50:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_serp_intent_fields'
down_revision = '556b79de2825'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add serp_intent column
    op.add_column('prospects', sa.Column('serp_intent', sa.String(), nullable=True))
    
    # Add serp_confidence column (Numeric(3, 2) for 0.00-1.00)
    op.add_column('prospects', sa.Column('serp_confidence', sa.Numeric(precision=3, scale=2), nullable=True))
    
    # Add serp_signals column (JSON array)
    op.add_column('prospects', sa.Column('serp_signals', postgresql.JSON(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    # Remove columns in reverse order
    op.drop_column('prospects', 'serp_signals')
    op.drop_column('prospects', 'serp_confidence')
    op.drop_column('prospects', 'serp_intent')

