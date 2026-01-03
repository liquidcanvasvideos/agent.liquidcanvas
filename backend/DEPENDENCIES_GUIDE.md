# Dependencies Guide

This document explains all dependencies used in the Website Outreach and Social Outreach systems.

## Core Framework Dependencies

### FastAPI & Web Server
- **fastapi==0.104.1** - Modern web framework for building APIs
- **uvicorn[standard]==0.24.0** - ASGI server for running FastAPI
- **python-multipart==0.0.6** - Handle file uploads and form data

### Database & ORM
- **sqlalchemy>=2.0.25** - SQL toolkit and ORM
- **alembic==1.12.1** - Database migration tool
- **asyncpg==0.29.0** - Async PostgreSQL driver
- **psycopg2-binary==2.9.9** - PostgreSQL adapter (synchronous)

### Data Validation
- **pydantic==2.5.0** - Data validation using Python type annotations
- **pydantic-settings==2.1.0** - Settings management using Pydantic

## Authentication & Security

- **python-jose[cryptography]==3.3.0** - JWT token encoding/decoding
- **passlib[bcrypt]==1.7.4** - Password hashing
- **authlib==1.2.1** - OAuth 2.0 client library for social media APIs
  - Used for LinkedIn, Instagram, Facebook OAuth flows
  - Handles token refresh and management

## HTTP Clients & API Communication

- **httpx>=0.24.0,<0.25.0** - Modern async HTTP client
  - Primary HTTP client for all API calls
  - Used by DataForSEO, Gemini, social media APIs
- **requests==2.31.0** - Fallback synchronous HTTP client
  - Used by some OAuth libraries
  - Backup for libraries that don't support httpx

## Retry Logic & Resilience ⚡

### Critical for API Reliability

- **tenacity==8.2.3** - Retry decorator with exponential backoff
  - Automatically retries failed API calls
  - Configurable retry strategies
  - Used for: DataForSEO, social media APIs, email services
  
- **backoff==2.2.1** - Alternative retry library
  - Complementary to tenacity
  - Different retry strategies available

**Usage Example:**
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def api_call():
    # Will retry up to 3 times with exponential backoff
    pass
```

## Rate Limiting 🚦

### Critical for API Compliance

- **limits==3.6.0** - Rate limiting library
  - Enforces API rate limits
  - Prevents API abuse
  - Used for: LinkedIn, Instagram, Facebook, TikTok APIs
  
- **cachetools==5.3.2** - Caching utilities
  - Used by limits for caching rate limit state
  
- **asyncio-throttle==1.0.2** - Async rate limiting
  - Throttles async operations
  - Prevents overwhelming APIs

**Usage Example:**
```python
from limits import storage, strategies
from limits.storage import MemoryStorage

storage = MemoryStorage()
strategy = strategies.MovingWindowRateLimiter(storage)
```

## Date/Time Utilities

- **python-dateutil==2.8.2** - Powerful date parsing
  - Parses API response dates
  - Handles timezone conversions
  - Used for: Social media API timestamps, job scheduling

## HTML/XML Parsing

### For Web Scraping & Content Extraction

- **beautifulsoup4==4.12.2** - HTML parsing library
  - Extracts content from websites
  - Used for: Website scraping, email extraction
  
- **lxml==4.9.3** - Fast XML/HTML parser
  - Alternative to html.parser
  - Faster parsing for large documents
  
- **html5lib==1.1** - HTML5 parser
  - HTML5-compliant parsing
  - Used by BeautifulSoup

## Background Jobs & Task Queue

- **redis==5.0.1** - In-memory data store
  - Task queue backend
  - Caching
  
- **rq==1.15.1** - Simple job queue
  - Background task processing
  
- **apscheduler==3.10.4** - Advanced Python scheduler
  - Scheduled jobs
  - Cron-like scheduling

## Environment & Configuration

- **python-dotenv==1.0.0** - Load environment variables from .env files

## External Services

- **supabase==2.3.0** - Supabase client (if using Supabase)

## Email & Messaging

- **email-validator==2.1.0** - Email validation
  - Validates prospect emails
  - Ensures email format correctness

## URL & Domain Utilities

- **tldextract==5.1.0** - Extract TLD, domain, subdomain
  - Parses URLs correctly
  - Handles complex domains
  
- **urllib3==2.1.0** - HTTP library with connection pooling
  - Connection management
  - Retry logic

## JSON & Data Processing

- **orjson==3.9.10** - Fast JSON library
  - Faster JSON parsing than standard library
  - Used for: API response parsing, large data processing

## Logging & Monitoring

- **structlog==23.2.0** - Structured logging
  - Better log formatting
  - JSON logging support
  - Production-ready logging

## Web Scraping & Browser Automation

- **selenium==4.15.2** - Browser automation
  - For complex scraping scenarios
  - JavaScript-rendered content
  
- **webdriver-manager==4.0.1** - Selenium driver management
  - Automatically manages browser drivers

## Data Validation & Sanitization

- **bleach==6.1.0** - HTML sanitization
  - Cleans user-generated content
  - Prevents XSS attacks
  
- **validators==0.22.0** - URL and email validation
  - Validates URLs and emails
  - Additional validation layer

## Async Utilities

- **aiofiles==23.2.1** - Async file operations
  - Non-blocking file I/O
  - Used for: Logging, file processing

## Dependency Categories

### Essential (Must Have)
- FastAPI, Uvicorn, SQLAlchemy, Alembic
- httpx, python-dotenv
- pydantic, python-jose, passlib

### Highly Recommended (Production Ready)
- **tenacity** - Retry logic (critical for API reliability)
- **limits** - Rate limiting (critical for API compliance)
- **authlib** - OAuth support (for social media APIs)
- **beautifulsoup4** - HTML parsing (for web scraping)
- **python-dateutil** - Date parsing (for API responses)

### Optional (Enhanced Features)
- **selenium** - Browser automation (for complex scraping)
- **orjson** - Fast JSON (performance optimization)
- **structlog** - Structured logging (production monitoring)
- **validators** - Additional validation (data quality)

## Usage Recommendations

### For Website Outreach
1. **DataForSEO API** - Uses httpx (already installed)
2. **Web Scraping** - Uses beautifulsoup4, lxml
3. **Email Extraction** - Uses beautifulsoup4, regex
4. **Retry Logic** - Use tenacity for all API calls
5. **Rate Limiting** - Use limits for DataForSEO API

### For Social Outreach
1. **OAuth** - Use authlib for token management
2. **API Calls** - Use httpx with tenacity retry
3. **Rate Limiting** - Use limits for each platform
4. **Date Parsing** - Use python-dateutil for timestamps
5. **Error Handling** - Use backoff for additional resilience

## Best Practices

1. **Always use retry logic** - Wrap API calls with tenacity
2. **Implement rate limiting** - Respect API limits
3. **Validate all inputs** - Use pydantic and validators
4. **Handle errors gracefully** - Use try/except with retry
5. **Log everything** - Use structlog for structured logs

## Updating Dependencies

To update dependencies:
```bash
pip install --upgrade -r requirements.txt
```

To check for outdated packages:
```bash
pip list --outdated
```

## Security Notes

- All dependencies are pinned to specific versions for stability
- Regularly update dependencies to patch security vulnerabilities
- Review dependency licenses before production use
- Use `pip-audit` to check for known vulnerabilities

