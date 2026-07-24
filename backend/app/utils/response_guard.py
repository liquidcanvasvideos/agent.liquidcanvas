"""
Response Guard Utility

Prevents returning {items: [], total > 0} which is a data integrity violation.
This guard ensures list endpoints never lie about data existence.
"""
from typing import Dict, Any, List
from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)


def validate_list_response(response: Dict[str, Any], endpoint_name: str) -> Dict[str, Any]:
    """
    Validate that list response doesn't violate data integrity.
    
    Raises HTTPException if:
    - data/items is empty but total > 0
    - This indicates a query failure that was silently swallowed
    
    Args:
        response: Response dictionary with 'data' or 'items' and 'total' keys
        endpoint_name: Name of endpoint for error messages
        
    Returns:
        Validated response (unchanged if valid)
        
    Raises:
        HTTPException: If data integrity violation detected
    """
    # Get data array (could be 'data' or 'items')
    data_key = None
    if 'data' in response:
        data_key = 'data'
    elif 'items' in response:
        data_key = 'items'
    
    if data_key is None:
        # No data key found - not a list response, skip validation
        return response
    
    data = response.get(data_key, [])
    total = response.get('total', 0)
    
    # CRITICAL: If total > 0 but data is empty, this is a data integrity violation
    # This means a query failed but was silently swallowed
    if total > 0 and len(data) == 0:
        error_msg = (
            f"Data integrity violation in {endpoint_name}: "
            f"total={total} but data array is empty. "
            "This indicates a query failure that was silently swallowed. "
            "Check logs for database errors."
        )
        logger.error(f"❌ {error_msg}")
        raise HTTPException(
            status_code=500,
            detail=error_msg
        )
    
    return response


