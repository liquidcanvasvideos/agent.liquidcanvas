"""add_discovery_query_id_to_prospects_safe

Revision ID: 556b79de2825
Revises: add_discovery_query
Create Date: 2025-12-01 03:44:16.926631

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = '556b79de2825'
down_revision = 'add_discovery_query'
branch_labels = None
depends_on = None


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table"""
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def index_exists(table_name: str, index_name: str) -> bool:
    """Check if an index exists"""
    bind = op.get_bind()
    inspector = inspect(bind)
    indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
    return index_name in indexes


def constraint_exists(table_name: str, constraint_name: str) -> bool:
    """Check if a foreign key constraint exists"""
    bind = op.get_bind()
    inspector = inspect(bind)
    foreign_keys = [fk['name'] for fk in inspector.get_foreign_keys(table_name)]
    return constraint_name in foreign_keys


def upgrade() -> None:
    """
    Safely add discovery_query_id column to prospects table.
    This migration is idempotent - it checks if the column exists before adding it.
    """
    # Check if column already exists
    if not column_exists('prospects', 'discovery_query_id'):
        # Add the column as nullable to ensure existing queries don't break
        op.add_column(
            'prospects',
            sa.Column(
                'discovery_query_id',
                postgresql.UUID(as_uuid=True),
                nullable=True,  # Nullable ensures no existing data breaks
                comment='Foreign key reference to discovery_queries.id'
            )
        )
        print("✅ Added discovery_query_id column to prospects table")
    else:
        print("ℹ️  Column discovery_query_id already exists, skipping")
    
    # Add index if it doesn't exist
    if not index_exists('prospects', 'ix_prospects_discovery_query_id'):
        op.create_index(
            'ix_prospects_discovery_query_id',
            'prospects',
            ['discovery_query_id']
        )
        print("✅ Created index on discovery_query_id")
    else:
        print("ℹ️  Index ix_prospects_discovery_query_id already exists, skipping")
    
    # Add foreign key constraint if it doesn't exist
    # First check if discovery_queries table exists
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = inspector.get_table_names()
    
    if 'discovery_queries' in tables:
        if not constraint_exists('prospects', 'fk_prospects_discovery_query_id'):
            op.create_foreign_key(
                'fk_prospects_discovery_query_id',
                'prospects',
                'discovery_queries',
                ['discovery_query_id'],
                ['id'],
                ondelete='SET NULL'  # If discovery_query is deleted, set to NULL
            )
            print("✅ Created foreign key constraint")
        else:
            print("ℹ️  Foreign key constraint already exists, skipping")
    else:
        print("⚠️  discovery_queries table does not exist, skipping foreign key creation")


def downgrade() -> None:
    """
    Safely remove discovery_query_id column from prospects table.
    This is also idempotent.
    """
    # Remove foreign key constraint if it exists
    if constraint_exists('prospects', 'fk_prospects_discovery_query_id'):
        op.drop_constraint('fk_prospects_discovery_query_id', 'prospects', type_='foreignkey')
        print("✅ Dropped foreign key constraint")
    
    # Remove index if it exists
    if index_exists('prospects', 'ix_prospects_discovery_query_id'):
        op.drop_index('ix_prospects_discovery_query_id', table_name='prospects')
        print("✅ Dropped index")
    
    # Remove column if it exists
    if column_exists('prospects', 'discovery_query_id'):
        op.drop_column('prospects', 'discovery_query_id')
        print("✅ Dropped discovery_query_id column")

