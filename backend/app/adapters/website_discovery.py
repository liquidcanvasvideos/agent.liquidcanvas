"""
Website Discovery Adapter

Reuses existing website discovery logic.
"""
from typing import List, Dict, Any
from app.models.prospect import Prospect
from app.tasks.discovery import discover_websites_async
import logging

logger = logging.getLogger(__name__)


class WebsiteDiscoveryAdapter:
    """Adapter for website discovery - reuses existing logic"""
    
    async def discover(self, params: Dict[str, Any]) -> List[Prospect]:
        """
        Discover websites using existing discovery logic.
        
        Params:
            categories: List[str] - Art categories
            locations: List[str] - Geographic locations
            keywords: Optional[str] - Search keywords
            max_results: int - Maximum results to return
        """
        categories = params.get('categories', [])
        locations = params.get('locations', [])
        keywords = params.get('keywords')
        max_results = params.get('max_results', 100)
        
        logger.info(f"🌐 [WEBSITE DISCOVERY] Starting discovery: categories={categories}, locations={locations}")
        
        # Use existing discovery task
        # This will create prospects with source_type='website' (default)
        prospects = await discover_websites_async(
            categories=categories,
            locations=locations,
            keywords=keywords,
            max_results=max_results
        )
        
        # Ensure all prospects have source_type='website'
        for prospect in prospects:
            if not prospect.source_type:
                prospect.source_type = 'website'
        
        logger.info(f"✅ [WEBSITE DISCOVERY] Discovered {len(prospects)} websites")
        return prospects

