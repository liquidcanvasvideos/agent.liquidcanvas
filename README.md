# Liquid Canvas - Social Outreach Engine

A high-performance backend engine for automated social media discovery, profile scraping, and targeted outreach across LinkedIn, Instagram, TikTok, and Facebook.

## 🚀 Overview

Liquid Canvas is designed to automate the lead generation and outreach pipeline for creative professionals. It leverages platform-specific APIs and advanced Google Search operators (via DataForSEO) to find, qualify, and message prospects at scale while maintaining human-like engagement.

## 🛠️ Core Features

*   **Platform Support:** Fully integrated adapters for LinkedIn, Instagram, TikTok, and Facebook.
*   **Deep Discovery:** Advanced search logic utilizing `site:`, `inurl:`, and contact-specific operators to find profiles with visible emails or link-in-bio pages.
*   **Intelligent Fallback:** Automatically switches between official APIs and DataForSEO scraping when credentials are missing or rate limits are reached.
*   **Automated Scraping:** Playwright-based background tasks to extract bio links, engagement data, and contact information.
*   **Outreach Pipeline:** Multi-stage workflow including Discovery -> Review -> Scraping -> Drafting -> Sending -> Follow-ups.
*   **Messaging Engine:** Platform-specific message adapters for LinkedIn connections and social DMs.

## 📁 Repository Structure

```text
backend/
├── app/
│   ├── adapters/          # Social platform discovery logic
│   ├── api/               # FastAPI endpoints (pipeline, prospects, social)
│   ├── clients/           # API clients (DataForSEO, LinkedIn, etc.)
│   ├── models/            # SQLAlchemy database models
│   ├── services/          # Core business logic (sending, scraping)
│   ├── tasks/             # Celery/Background task handlers
│   └── db/                # Database connection & session management
├── Dockerfile             # Containerization config
├── alembic.ini            # Database migration config
├── requirements.txt       # Python dependencies
└── Makefile               # Development utility commands

frontend/                  # Next.js UI (Vercel Root Directory: frontend)
```

## ⚙️ Setup & Installation

### Prerequisites
*   Python 3.10+
*   PostgreSQL
*   Redis (for background tasks)

### Installation
1.  **Install dependencies:**
    ```bash
    pip install -r backend/requirements.txt
    ```
2.  **Configure Environment:**
    Copy `.env.example` to `.env` and provide:
    *   `DATABASE_URL`
    *   `REDIS_URL`
    *   `DATAFORSEO_LOGIN`/`PASSWORD`
    *   `LINKEDIN_ACCESS_TOKEN`, `INSTAGRAM_ACCESS_TOKEN`, etc.

3.  **Run the application:**
    ```bash
    cd backend
    uvicorn app.main:app --host 0.0.0.0 --port 8000
    ```

## 🧪 Search Strategy

The system uses a "Category + Location" strict constraint model. Every search query is built to strictly adhere to user-selected filters, ensuring high-quality, relevant results.

Example LinkedIn Pattern:
`site:linkedin.com/in/ "{category}" "{location}" "at gmail.com"`

## 🛡️ Rate Limiting & Safety

The engine includes built-in safety mechanisms:
*   Randomized delays between actions.
*   Per-platform rate limiting.
*   Credential health checks to prevent account flagging.

---
*Maintained by the Liquid Canvas Team.*
