# Backend API Service

FastAPI backend for art outreach automation system.

## Setup

1. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set environment variables (create `.env` file):
```
DATABASE_URL=postgresql://user:pass@localhost:5432/art_outreach
REDIS_URL=redis://localhost:6379/0
DATAFORSEO_LOGIN=your_email@example.com
DATAFORSEO_PASSWORD=your_password
HUNTER_IO_API_KEY=your_api_key
GEMINI_API_KEY=your_api_key
GMAIL_CLIENT_ID=your_client_id
GMAIL_CLIENT_SECRET=your_client_secret
GMAIL_REFRESH_TOKEN=your_refresh_token
JWT_SECRET_KEY=your_secret_key
```

4. Run database migrations:
```bash
alembic upgrade head
```

5. Start the server:
```bash
uvicorn main:app --reload
```

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI app entry point
│   ├── models/              # SQLAlchemy models
│   ├── schemas/             # Pydantic schemas
│   ├── api/                 # API route handlers
│   ├── clients/             # Third-party API clients
│   ├── services/            # Business logic
│   └── db/                  # Database configuration
├── alembic/                 # Database migrations
├── tests/                   # Test files
├── scripts/                 # Utility scripts
├── requirements.txt
└── README.md
```

## Verifying Hunter.io API Key

Run:

```bash
make test-hunter
```

Or directly:

```bash
python3 scripts/test_hunter_api.py
```

This tests:
- Whether the API key is loaded correctly from `HUNTER_IO_API_KEY` environment variable
- Whether Hunter accepts it (account endpoint)
- Whether the account is restricted
- Whether domain search functionality works
- Whether network/DNS issues affect API connectivity

The script will:
- ✅ Show success if the key is active and both endpoints work
- ❌ Show error if the account is restricted or key is invalid
- ⚠️ Show warning if rate limited (but key is valid)
- Exit with code 0 (success), 1 (error), or 2 (missing key)

