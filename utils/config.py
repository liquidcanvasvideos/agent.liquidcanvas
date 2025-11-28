"""
Configuration management using Pydantic Settings
"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application settings"""
    
    # App
    APP_NAME: str = "Autonomous Art Outreach Scraper"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "https://agent.liquidcanvas.art",
        "https://www.liquidcanvas.art"
    ]
    
    # Database
    DATABASE_URL: str = "sqlite:///./art_outreach.db"
    
    # Scraping
    SCRAPER_USER_AGENT: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    SCRAPER_TIMEOUT: int = 30
    SCRAPER_MAX_RETRIES: int = 3
    
    # Quality filtering (lowered for more results)
    MIN_QUALITY_SCORE: int = 20  # Minimum quality score (0-100) to scrape (lowered from 50)
    MIN_DOMAIN_AUTHORITY: int = 10  # Minimum domain authority (0-100) (lowered from 30)
    MIN_TRAFFIC_TIER: str = "very_low"  # Minimum traffic tier: very_low, low, medium, high, very_high
    REQUIRE_SSL: bool = False  # Require valid SSL certificate (set to False to allow HTTP sites)
    REQUIRE_VALID_DNS: bool = True  # Require valid DNS records
    
    # AI/LLM
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    AI_MODEL: str = "gpt-4"  # or "gemini-pro"
    
    # Email
    GMAIL_CLIENT_ID: str = ""
    GMAIL_CLIENT_SECRET: str = ""
    GMAIL_REFRESH_TOKEN: str = ""
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    
    # Celery/Redis
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    
    # Scheduler
    SCHEDULER_ENABLED: bool = True
    
    # Search APIs (optional - for website discovery)
    GOOGLE_SEARCH_API_KEY: str = ""
    GOOGLE_SEARCH_ENGINE_ID: str = ""
    BING_SEARCH_API_KEY: str = ""
    
    # Hunter.io API (for email finding)
    HUNTER_IO_API_KEY: str = ""
    
    # DataForSEO API (for website discovery and quality metrics)
    DATAFORSEO_LOGIN: str = ""  # Email address
    DATAFORSEO_PASSWORD: str = ""  # API token/password
    
    # Authentication
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin"
    JWT_SECRET_KEY: str = "your-secret-key-change-in-production"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"  # Ensure UTF-8 encoding
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields in .env (handles encoding issues)


settings = Settings()

