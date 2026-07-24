"""
SERP Intent Inference Service

Analyzes DataForSEO SERP results to infer business intent before enrichment.
This prevents unnecessary Snov.io calls for blogs, media, marketplaces, etc.
"""
import re
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# Known platform domains (auto-classified as "platform")
KNOWN_PLATFORMS = {
    "youtube.com", "vimeo.com", "dailymotion.com",
    "medium.com", "substack.com", "ghost.org",
    "shopify.com", "etsy.com", "amazon.com", "ebay.com",
    "wordpress.com", "blogger.com", "tumblr.com",
    "linkedin.com", "facebook.com", "twitter.com", "instagram.com",
    "pinterest.com", "reddit.com", "quora.com",
    "wix.com", "squarespace.com", "weebly.com"
}


def infer_serp_intent(
    url: str,
    title: str,
    snippet: str | None,
    category: str,
) -> dict:
    """
    Infer business intent from SERP data (URL, title, snippet, category).
    
    Returns:
    {
        "intent": "service | brand | blog | media | marketplace | platform | unknown",
        "confidence": float (0.0-1.0),
        "signals": list[str]  # List of signals that led to this classification
    }
    
    Intent rules:
    - "service": Titles/snippets containing "services", "company", "studio", "agency", "solutions"
    - "brand": Business names, product pages, official websites
    - "blog": "blog", "guide", "tips", "ideas", "article", "post"
    - "media": "news", "press", "magazine", "journal", "publication"
    - "marketplace": "shop", "buy", "marketplace", "store", "cart", "checkout"
    - "platform": Known platform domains (YouTube, Medium, Shopify, etc.)
    - "unknown": No clear signals
    """
    signals: List[str] = []
    url_lower = url.lower()
    title_lower = title.lower() if title else ""
    snippet_lower = (snippet or "").lower()
    combined_text = f"{title_lower} {snippet_lower}".strip()
    
    # Check for known platforms first (highest confidence)
    domain = _extract_domain(url)
    if domain and domain.lower() in KNOWN_PLATFORMS:
        signals.append(f"known_platform_domain:{domain}")
        return {
            "intent": "platform",
            "confidence": 0.95,
            "signals": signals
        }
    
    # Service intent signals
    service_keywords = [
        "services", "service", "company", "studio", "agency", "solutions",
        "consulting", "consultancy", "firm", "group", "partners", "team",
        "professional", "experts", "specialists", "providers"
    ]
    service_matches = [kw for kw in service_keywords if kw in combined_text]
    if service_matches:
        signals.extend([f"service_keyword:{kw}" for kw in service_matches[:3]])  # Limit to 3
    
    # Brand intent signals (business names, official sites)
    brand_keywords = [
        "official", "homepage", "home page", "welcome", "about us",
        "our company", "our team", "who we are"
    ]
    brand_matches = [kw for kw in brand_keywords if kw in combined_text]
    if brand_matches:
        signals.extend([f"brand_keyword:{kw}" for kw in brand_matches[:2]])
    
    # Blog intent signals
    blog_keywords = [
        "blog", "guide", "tips", "ideas", "article", "post", "tutorial",
        "how to", "learn", "read", "writing", "author", "editorial"
    ]
    blog_matches = [kw for kw in blog_keywords if kw in combined_text]
    if blog_matches:
        signals.extend([f"blog_keyword:{kw}" for kw in blog_matches[:3]])
    
    # Media intent signals
    media_keywords = [
        "news", "press", "magazine", "journal", "publication", "media",
        "reporter", "journalist", "editorial", "press release"
    ]
    media_matches = [kw for kw in media_keywords if kw in combined_text]
    if media_matches:
        signals.extend([f"media_keyword:{kw}" for kw in media_matches[:2]])
    
    # Marketplace intent signals
    marketplace_keywords = [
        "shop", "buy", "marketplace", "store", "cart", "checkout",
        "purchase", "order", "product", "products", "catalog",
        "add to cart", "shopping", "retail"
    ]
    marketplace_matches = [kw for kw in marketplace_keywords if kw in combined_text]
    if marketplace_matches:
        signals.extend([f"marketplace_keyword:{kw}" for kw in marketplace_matches[:3]])
    
    # URL path patterns
    url_path = url_lower.split("/")[-1] if "/" in url_lower else ""
    if "/blog/" in url_lower or url_path in ["blog", "blogs"]:
        signals.append("url_path:blog")
    if "/shop/" in url_lower or "/store/" in url_lower or url_path in ["shop", "store"]:
        signals.append("url_path:shop")
    if "/news/" in url_lower or "/press/" in url_lower:
        signals.append("url_path:media")
    
    # Calculate intent and confidence based on signal strength
    service_score = len([s for s in signals if s.startswith("service_keyword")])
    brand_score = len([s for s in signals if s.startswith("brand_keyword")])
    blog_score = len([s for s in signals if s.startswith("blog_keyword") or "blog" in s])
    media_score = len([s for s in signals if s.startswith("media_keyword") or "media" in s])
    marketplace_score = len([s for s in signals if s.startswith("marketplace_keyword") or "shop" in s or "store" in s])
    
    # Determine intent (highest score wins, with tie-breakers)
    scores = {
        "service": service_score,
        "brand": brand_score,
        "blog": blog_score,
        "media": media_score,
        "marketplace": marketplace_score,
    }
    
    max_score = max(scores.values())
    
    if max_score == 0:
        # No clear signals
        return {
            "intent": "unknown",
            "confidence": 0.3,
            "signals": signals or ["no_signals"]
        }
    
    # Get intent with highest score
    intent = max(scores.items(), key=lambda x: x[1])[0]
    
    # Calculate confidence based on signal strength
    total_signals = len(signals)
    if total_signals == 0:
        confidence = 0.3
    elif total_signals == 1:
        confidence = 0.5
    elif total_signals == 2:
        confidence = 0.7
    elif total_signals >= 3:
        confidence = 0.85
    else:
        confidence = 0.5
    
    # Boost confidence if multiple signals of same type
    if max_score >= 2:
        confidence = min(confidence + 0.1, 0.95)
    
    return {
        "intent": intent,
        "confidence": round(confidence, 2),
        "signals": signals
    }


def _extract_domain(url: str) -> Optional[str]:
    """Extract domain from URL."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc.lower().replace("www.", "")
        return domain
    except Exception:
        return None

