"""
Discovery Adapters

Adapter pattern for platform-specific discovery logic.
Each adapter normalizes results into a common Prospect shape.
"""
from typing import Protocol, List, Dict, Any
from app.models.prospect import Prospect

class DiscoveryAdapter(Protocol):
    """Common interface for all discovery adapters"""
    
    async def discover(self, params: Dict[str, Any]) -> List[Prospect]:
        """
        Discover prospects for this platform.
        
        Args:
            params: Platform-specific discovery parameters
            
        Returns:
            List of Prospect objects normalized to common shape
        """
        ...

