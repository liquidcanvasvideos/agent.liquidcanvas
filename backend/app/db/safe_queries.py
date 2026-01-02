"""
Safe query helpers that handle missing columns gracefully.

These functions use explicit column selection to prevent SELECT * failures
when optional columns are missing from the database schema.
"""
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.models.prospect import Prospect
from app.db.safe_columns import PROSPECT_SAFE_LIST_COLUMNS, PROSPECT_FULL_COLUMNS
import logging

logger = logging.getLogger(__name__)


async def safe_select_prospects(
    db: AsyncSession,
    where_clause=None,
    order_by=None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    include_optional: bool = False
) -> List[Prospect]:
    """
    Safely select prospects using explicit column list.
    
    This prevents failures when optional columns (final_body, thread_id, etc.)
    don't exist in the database.
    
    Args:
        db: Database session
        where_clause: SQLAlchemy where clause
        order_by: SQLAlchemy order_by clause
        limit: Limit results
        offset: Offset results
        include_optional: If True, includes optional columns (only after schema validation)
    
    Returns:
        List of Prospect objects
    """
    try:
        # First try ORM query (fastest if schema is correct)
        query = select(Prospect)
        if where_clause is not None:
            query = query.where(where_clause)
        if order_by is not None:
            query = query.order_by(order_by)
        if offset is not None:
            query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)
        
        result = await db.execute(query)
        return result.scalars().all()
    except Exception as e:
        error_msg = str(e).lower()
        if 'column' in error_msg or 'does not exist' in error_msg:
            # Schema mismatch - use raw SQL with explicit columns
            logger.warning(f"⚠️  Schema mismatch detected, using safe column list: {e}")
            columns = PROSPECT_FULL_COLUMNS if include_optional else PROSPECT_SAFE_LIST_COLUMNS
            
            # Build WHERE clause
            where_sql = ""
            if where_clause is not None:
                # Convert SQLAlchemy where clause to SQL string
                # This is a simplified version - for complex clauses, use ORM
                where_sql = "WHERE " + str(where_clause.compile(compile_kwargs={"literal_binds": True}))
            
            # Build ORDER BY
            order_sql = ""
            if order_by is not None:
                order_sql = "ORDER BY " + str(order_by.compile(compile_kwargs={"literal_binds": True}))
            
            # Build LIMIT/OFFSET
            limit_sql = ""
            if limit is not None:
                limit_sql = f"LIMIT {limit}"
            if offset is not None:
                limit_sql += f" OFFSET {offset}"
            
            # Execute raw SQL
            sql = f"""
                SELECT {', '.join(columns)}
                FROM prospects
                {where_sql}
                {order_sql}
                {limit_sql}
            """
            
            result = await db.execute(text(sql))
            rows = result.fetchall()
            
            # Convert rows to Prospect-like objects
            prospects = []
            for row in rows:
                p = Prospect()
                for i, col_name in enumerate(columns):
                    if i < len(row):
                        setattr(p, col_name, row[i])
                prospects.append(p)
            
            return prospects
        else:
            # Re-raise non-schema errors
            raise


async def check_column_exists(db: AsyncSession, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table"""
    try:
        result = await db.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = :table_name 
            AND column_name = :column_name
        """), {"table_name": table_name, "column_name": column_name})
        return result.fetchone() is not None
    except Exception:
        return False

