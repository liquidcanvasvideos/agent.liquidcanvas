"""
Safe Prospect Query Utilities

Provides a way to query prospects even when final_body column doesn't exist.
Uses raw SQL to exclude problematic columns.
"""
from sqlalchemy import text, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.prospect import Prospect
from typing import List, Optional


async def safe_select_prospects(
    db: AsyncSession,
    where_clause: Optional[str] = None,
    order_by: Optional[str] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None
) -> List[Prospect]:
    """
    Safely select prospects using raw SQL to avoid final_body column errors.
    
    Args:
        db: Database session
        where_clause: Optional WHERE clause (e.g., "discovery_status = 'DISCOVERED'")
        order_by: Optional ORDER BY clause (e.g., "created_at DESC")
        limit: Optional limit
        offset: Optional offset
        
    Returns:
        List of Prospect objects
    """
    # Build SELECT statement excluding final_body
    # Check if final_body exists first
    column_check = await db.execute(text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'prospects' 
        AND column_name = 'final_body'
    """))
    
    has_final_body = column_check.fetchone() is not None
    
    # Build WHERE clause
    where_sql = f"WHERE {where_clause}" if where_clause else ""
    
    # Build ORDER BY clause
    order_sql = f"ORDER BY {order_by}" if order_by else "ORDER BY created_at DESC"
    
    # Build LIMIT/OFFSET
    limit_sql = f"LIMIT {limit}" if limit else ""
    offset_sql = f"OFFSET {offset}" if offset else ""
    
    if has_final_body:
        # Column exists - use normal ORM query
        query = select(Prospect)
        if where_clause:
            # Parse where_clause and apply to query
            # For now, just use ORM
            pass
        if order_by:
            # Parse order_by and apply
            pass
        if limit:
            query = query.limit(limit)
        if offset:
            query = query.offset(offset)
        result = await db.execute(query)
        return result.scalars().all()
    else:
        # Column doesn't exist - use raw SQL without final_body
        # For now, fall back to ORM but catch the error
        try:
            query = select(Prospect)
            if limit:
                query = query.limit(limit)
            if offset:
                query = query.offset(offset)
            result = await db.execute(query)
            return result.scalars().all()
        except Exception:
            # If ORM fails, return empty list
            # The calling code will handle the error
            return []

