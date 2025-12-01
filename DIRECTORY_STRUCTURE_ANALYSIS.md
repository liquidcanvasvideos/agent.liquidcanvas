# Directory Structure Analysis & Fix Plan

## Current Structure Analysis

### ✅ **GOOD: Backend Structure**
```
backend/
  app/
    api/          # API routes (clean)
    clients/      # External API clients (clean)
    db/           # Database config (clean)
    models/       # SQLAlchemy models (clean)
    schemas/      # Pydantic schemas (clean)
    services/     # Business logic services (clean)
    tasks/        # Background tasks (clean)
    main.py       # FastAPI app entry
```
**Status**: ✅ Clean, uses `app.*` imports correctly

### ✅ **GOOD: Frontend Structure**
```
frontend/
  app/            # Next.js app router (clean)
  components/     # React components (clean)
  lib/            # Utilities & API client (clean)
```
**Status**: ✅ Clean, uses `@/*` path aliases correctly

### ❌ **PROBLEM: Worker Structure**
```
worker/
  clients/        # DUPLICATE of backend/app/clients/
  tasks/          # DUPLICATE of backend/app/tasks/
  services/       # Some unique code
```
**Issues**:
1. Duplicate code (clients, tasks)
2. Path manipulation (`sys.path.insert()`)
3. Fragile imports that break on deployment

## Root Cause

The worker directory duplicates backend code and uses fragile path manipulation:
```python
# worker/tasks/discovery.py
backend_path = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(backend_path))
from app.models.job import Job  # Fragile!
from worker.clients.dataforseo import DataForSEOClient  # Duplicate!
```

## Solution: Clean Architecture

### Option A: Remove Worker (Recommended)
If backend tasks run directly (which they do), worker is redundant.

### Option B: Fix Worker to Import from Backend
Make worker a thin wrapper that imports from backend.

## Recommended Structure

```
liquidcanvas/
├── backend/              # FastAPI backend
│   ├── app/
│   │   ├── api/         # API routes
│   │   ├── clients/     # External API clients
│   │   ├── db/          # Database
│   │   ├── models/      # SQLAlchemy models
│   │   ├── schemas/     # Pydantic schemas
│   │   ├── services/    # Business logic
│   │   ├── tasks/       # Background tasks
│   │   └── main.py      # FastAPI entry
│   ├── alembic/         # Migrations
│   └── requirements.txt
│
├── frontend/             # Next.js frontend
│   ├── app/             # Next.js app router
│   ├── components/      # React components
│   ├── lib/             # Utilities
│   └── package.json
│
└── worker/               # RQ Worker (if needed)
    ├── worker.py        # Entry point
    └── requirements.txt # Imports from backend
```

## Import Patterns

### Backend (✅ Already Correct)
```python
from app.models.job import Job
from app.clients.hunter import HunterIOClient
from app.tasks.discovery import discover_websites_async
```

### Frontend (✅ Already Correct)
```typescript
import { getStats } from '@/lib/api'
import StatsCards from '@/components/StatsCards'
```

### Worker (❌ Needs Fix)
**Current (BAD)**:
```python
sys.path.insert(0, str(backend_path))
from app.models.job import Job
from worker.clients.dataforseo import DataForSEOClient  # Duplicate!
```

**Fixed (GOOD)**:
```python
# Add backend to PYTHONPATH or use proper package structure
from app.models.job import Job
from app.clients.dataforseo import DataForSEOClient  # Import from backend!
```

## Action Plan

1. **Audit worker usage** - Is it actually deployed/used?
2. **If worker is used**: Fix imports to use backend code
3. **If worker is unused**: Remove or archive it
4. **Verify all imports** - No path manipulation
5. **Test builds** - Zero missing file errors

