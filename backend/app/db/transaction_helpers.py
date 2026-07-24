"""
Transaction helper utilities for safe database operations
Prevents PendingRollbackError and InFailedSQLTransaction errors
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import PendingRollbackError, OperationalError

logger = logging.getLogger(__name__)


async def safe_commit(db: AsyncSession, context: str = "operation") -> bool:
    """
    Safely commit a database transaction with automatic rollback on failure.
    
    Args:
        db: AsyncSession to commit
        context: Description of the operation for logging
        
    Returns:
        True if commit succeeded, False if it failed
    """
    try:
        await db.commit()
        return True
    except PendingRollbackError as e:
        logger.warning(f"⚠️  [TRANSACTION] PendingRollbackError in {context}, rolling back: {e}")
        try:
            await db.rollback()
            logger.info(f"✅ [TRANSACTION] Rollback successful for {context}")
        except Exception as rollback_err:
            logger.error(f"❌ [TRANSACTION] Rollback failed for {context}: {rollback_err}", exc_info=True)
        return False
    except OperationalError as e:
        error_str = str(e).lower()
        if "in failed sql transaction" in error_str or "pending rollback" in error_str:
            logger.warning(f"⚠️  [TRANSACTION] Failed SQL transaction in {context}, rolling back: {e}")
            try:
                await db.rollback()
                logger.info(f"✅ [TRANSACTION] Rollback successful for {context}")
            except Exception as rollback_err:
                logger.error(f"❌ [TRANSACTION] Rollback failed for {context}: {rollback_err}", exc_info=True)
        else:
            logger.error(f"❌ [TRANSACTION] OperationalError in {context}: {e}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"❌ [TRANSACTION] Unexpected error committing {context}: {e}", exc_info=True)
        try:
            await db.rollback()
            logger.info(f"✅ [TRANSACTION] Rollback successful after error for {context}")
        except Exception as rollback_err:
            logger.error(f"❌ [TRANSACTION] Rollback failed after error for {context}: {rollback_err}", exc_info=True)
        return False


async def safe_flush(db: AsyncSession, context: str = "operation") -> bool:
    """
    Safely flush a database session with automatic rollback on failure.
    
    Args:
        db: AsyncSession to flush
        context: Description of the operation for logging
        
    Returns:
        True if flush succeeded, False if it failed
    """
    try:
        await db.flush()
        return True
    except PendingRollbackError as e:
        logger.warning(f"⚠️  [TRANSACTION] PendingRollbackError during flush in {context}, rolling back: {e}")
        try:
            await db.rollback()
            logger.info(f"✅ [TRANSACTION] Rollback successful after flush error for {context}")
        except Exception as rollback_err:
            logger.error(f"❌ [TRANSACTION] Rollback failed after flush error for {context}: {rollback_err}", exc_info=True)
        return False
    except OperationalError as e:
        error_str = str(e).lower()
        if "in failed sql transaction" in error_str or "pending rollback" in error_str:
            logger.warning(f"⚠️  [TRANSACTION] Failed SQL transaction during flush in {context}, rolling back: {e}")
            try:
                await db.rollback()
                logger.info(f"✅ [TRANSACTION] Rollback successful after flush error for {context}")
            except Exception as rollback_err:
                logger.error(f"❌ [TRANSACTION] Rollback failed after flush error for {context}: {rollback_err}", exc_info=True)
        else:
            logger.error(f"❌ [TRANSACTION] OperationalError during flush in {context}: {e}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"❌ [TRANSACTION] Unexpected error flushing {context}: {e}", exc_info=True)
        try:
            await db.rollback()
            logger.info(f"✅ [TRANSACTION] Rollback successful after flush error for {context}")
        except Exception as rollback_err:
            logger.error(f"❌ [TRANSACTION] Rollback failed after flush error for {context}: {rollback_err}", exc_info=True)
        return False

