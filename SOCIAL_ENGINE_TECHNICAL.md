# Social Outreach Engine: Technical Overview

## Architecture & Data Flow

The engine is built on a modular adapter-service architecture designed for scale and reliability.

### 1. Discovery Phase (Adapters)
- **Primary Source:** Official Graph APIs (LinkedIn, Instagram, TikTok).
- **Fallback Source:** DataForSEO Google Organic Search API.
- **Query Strategy:** Strict constraint-based searching using Google advanced operators (`site:`, `inurl:`, `exact phrase matching`).
- **Constraint Model:** All searches MUST include `{category}` and `{location}` to ensure high-intent results.

### 2. Qualification & Scraping (Background Tasks)
- **Engine:** Playwright-based headless browser cluster.
- **Link-in-Bio Crawling:** Automatically identifies external link platforms (Linktree, Beacons, Stan.store) and crawls them for hidden contact emails.
- **Engagement Analysis:** Extracts follower counts, engagement rates, and post frequency to prioritize high-value prospects.

### 3. Pipeline Stages (Social Pipeline API)
1.  **Discovery:** Initial identification of social profiles.
2.  **Review:** Human-in-the-loop or automated approval of profiles.
3.  **Scraping:** Deep data extraction for approved profiles.
4.  **Drafting:** LLM-powered personalized message generation based on profile bio and recent content.
5.  **Sending:** Multi-platform message dispatch (DMs or Connection Requests).
6.  **Follow-up:** Automated multi-step follow-up sequences.

### 4. Messaging Engine (Services)
- **LinkedIn:** Connection requests with personalized notes.
- **Instagram/TikTok:** Direct Messaging (DM) with randomized delays.
- **Rate Limiting:** Global and per-account rate limiters to mimic human behavior and protect account longevity.

## Database Models

- `SocialProfile`: Central record for discovered creators.
- `SocialDiscoveryJob`: Tracks the status and parameters of bulk discovery operations.
- `SocialDraft`: Stores generated outreach messages.
- `SocialMessage`: Audit log of all sent communications.

## Deployment Stack

- **Framework:** FastAPI (Python 3.10+)
- **Task Queue:** Redis + Celery
- **Database:** PostgreSQL (SQLAlchemy)
- **Search Engine:** DataForSEO
- **Scraper:** Playwright (Chromium)

---
*Liquid Canvas Social Engine v2.0*
