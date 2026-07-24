"""
API endpoint to mark all scraped prospects as verified
"""
from fastapi import HTTPException, Depends, APIRouter
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, func
from app.db.database import get_db
from app.models.prospect import Prospect, VerificationStatus

router = APIRouter()

@router.post("/mark-all-verified")
async def mark_all_verified(db: AsyncSession = Depends(get_db)):
    """Mark all scraped prospects with emails as verified"""
    try:
        # Update all scraped prospects with emails to be verified
        stmt = (
            update(Prospect)
            .where(
                and_(
                    Prospect.scrape_status.in_(['SCRAPED', 'ENRICHED']),
                    Prospect.contact_email.isnot(None),
                    Prospect.verification_status != VerificationStatus.VERIFIED.value
                )
            )
            .values(verification_status=VerificationStatus.VERIFIED.value)
        )
        
        result = await db.execute(stmt)
        await db.commit()
        
        # Verify the update
        count_stmt = select(func.count(Prospect.id)).where(
            and_(
                Prospect.scrape_status.in_(['SCRAPED', 'ENRICHED']),
                Prospect.contact_email.isnot(None),
                Prospect.verification_status == VerificationStatus.VERIFIED.value
            )
        )
        
        verified_count = await db.execute(count_stmt)
        
        return {
            "success": True,
            "marked_verified": result.rowcount,
            "total_verified": verified_count.scalar()
        }
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to mark prospects as verified: {str(e)}")
