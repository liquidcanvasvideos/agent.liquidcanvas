# Directory Restructure Plan

## Current State Analysis

### ✅ Backend Structure (GOOD - No Changes Needed)
```
backend/
  app/
    api/          # ✅ Clean API routes
    clients/      # ✅ External API clients  
    db/           # ✅ Database config
    models/       # ✅ SQLAlchemy models
    schemas/      # ✅ Pydantic schemas
    services/     # ✅ Business logic
    tasks/        # ✅ Background tasks (run via asyncio)
    main.py       # ✅ FastAPI entry
```
**Imports**: All use `from app.*` - ✅ Correct

### ✅ Frontend Structure (GOOD - No Changes Needed)
```
frontend/
  app/            # ✅ Next.js app router
  components/     # ✅ React components
  lib/            # ✅ Utilities & API client
```
**Imports**: All use `@/*` path aliases - ✅ Correct

### ❌ Worker Directory (LEGACY - Should be Removed/Archived)
```
worker/           # ❌ NOT USED - Backend runs tasks directly
  clients/        # ❌ Duplicate of backend/app/clients/
  tasks/          # ❌ Duplicate of backend/app/tasks/
```
**Status**: Backend uses `asyncio.create_task()`, not RQ worker

## Issues Found

1. **Worker directory is unused** - Backend runs tasks directly
2. **Unused RQ/Redis code** - Backend has RQ imports but doesn't use them
3. **No actual import issues** - Backend and frontend imports are clean

## Solution

### Phase 1: Clean Up Unused Code
1. Archive/remove worker directory (it's not used)
2. Remove unused RQ code from backend (tasks run via asyncio)
3. Keep backend and frontend structure (they're fine)

### Phase 2: Verify Imports
1. All backend imports use `app.*` ✅
2. All frontend imports use `@/*` ✅
3. No path manipulation needed ✅

## Final Clean Structure

```
liquidcanvas/
├── backend/              # FastAPI Backend
│   ├── app/
│   │   ├── api/         # API routes
│   │   ├── clients/     # External API clients
│   │   ├── db/          # Database
│   │   ├── models/      # SQLAlchemy models
│   │   ├── schemas/     # Pydantic schemas
│   │   ├── services/    # Business logic
│   │   ├── tasks/       # Background tasks (asyncio)
│   │   └── main.py      # FastAPI entry
│   ├── alembic/         # Migrations
│   └── requirements.txt
│
├── frontend/             # Next.js Frontend
│   ├── app/             # Next.js app router
│   ├── components/      # React components
│   ├── lib/             # Utilities
│   └── package.json
│
└── legacy/               # Old code (already archived)
```

## Import Patterns (Already Correct)

### Backend
```python
from app.models.job import Job
from app.clients.hunter import HunterIOClient
from app.tasks.discovery import process_discovery_job
```

### Frontend
```typescript
import { getStats } from '@/lib/api'
import StatsCards from '@/components/StatsCards'
```

## Action Items

1. ✅ Verify backend structure (DONE - it's clean)
2. ✅ Verify frontend structure (DONE - it's clean)
3. ⏳ Archive worker directory (not used)
4. ⏳ Remove unused RQ code from backend
5. ⏳ Create .gitignore for worker if keeping it

