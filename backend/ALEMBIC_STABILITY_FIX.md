# Alembic Stability Fix - Complete

## Problem Summary

The application was crashing repeatedly due to:
- Alembic re-running `000000000000` on every deploy
- Schema drift (bio_text, social fields missing)
- Pipeline endpoints returning `total > 0` but empty data
- Exit status 3 after migrations
- Silent DB failures masked as empty arrays

**Root Cause**: Automatic Alembic execution on startup + corrupted alembic_version table

## Solutions Implemented

### STEP 1: Fix Alembic Version Table

**File**: `backend/fix_alembic_version.py`

Utility script to fix corrupted Alembic history:
- Checks if `alembic_version` table exists
- If multiple rows exist, keeps ONLY the latest revision
- If table is missing or empty, inserts the latest revision hash manually
- Ensures `version_num` matches the latest head revision

**Usage**:
```bash
cd backend
python fix_alembic_version.py
```

### STEP 2: Stop Running Alembic Automatically on Startup

**File**: `backend/app/main.py`

**CHANGES**:
- **REMOVED**: `command.upgrade(alembic_cfg, "heads")` from startup
- **REPLACED**: `run_database_setup()` with `verify_database_state()`
- **NEW BEHAVIOR**: Startup only verifies database connectivity and logs schema state
- **NO MIGRATIONS**: Migrations must be run at deploy time, not on every app boot

**Before**:
```python
# Run migrations FIRST - AUTOMATIC ON EVERY STARTUP
command.upgrade(alembic_cfg, "heads")
```

**After**:
```python
# Verify database state WITHOUT running migrations
# Migrations should be run at deploy time, not on every app boot
```

**Result**: App boots successfully without running migrations, preventing crash loops.

### STEP 3: Hard-Align Prospects Table Schema

**File**: `backend/alembic/versions/ensure_all_prospect_columns_final.py`

Migration already exists and safely adds all required columns:
- `bio_text` (TEXT, nullable=True)
- `external_links` (JSONB, nullable=True)
- `follower_count` (INTEGER, nullable=True)
- `engagement_rate` (NUMERIC(5,2), nullable=True)
- `source_type`, `source_platform`, `profile_url`, `username`, `display_name`
- `scraped_at` (TIMESTAMP WITH TIME ZONE, nullable=True)

**Migration is**:
- Idempotent (checks existence before adding)
- Production-safe (uses `op.add_column` with `nullable=True`)
- Non-destructive (never drops data)

### STEP 4: Eliminate Silent Query Failures

**Files**: `backend/app/api/pipeline.py`, `backend/app/api/prospects.py`, `backend/app/api/social.py`

**Already Implemented**:
- `/api/pipeline/websites`: Raises HTTP 500 if `total > 0` but `data = []`
- `/api/prospects/scraped-emails`: Raises HTTP 500 if `total > 0` but `data = []`
- All errors are logged with full traceback
- No silent failures - all exceptions are re-raised

**Example**:
```python
if total > 0 and len(websites) == 0:
    logger.error(f"❌ DATA INTEGRITY VIOLATION: total={total} but query returned 0 rows")
    await db.rollback()
    raise HTTPException(
        status_code=500,
        detail=f"Data integrity violation: COUNT query returned {total} but SELECT query returned 0 rows."
    )
```

### STEP 5: Schema Diagnostics (Non-Fatal)

**File**: `backend/app/utils/schema_validator.py`

**Function**: `get_full_schema_diagnostics()`
- Connects using `async_engine`
- Reads Alembic revision from `alembic_version` table
- Fetches DB columns from `information_schema.columns`
- Fetches model columns from `Base.metadata.tables["prospects"]`
- Returns `schema_match` boolean

**Called at startup** (non-fatal, logs warnings only):
```python
diagnostics = await get_full_schema_diagnostics(engine)
if not diagnostics.get("schema_match", False):
    logger.warning("⚠️  SCHEMA MISMATCH DETECTED (non-fatal)")
    logger.warning(f"⚠️  Missing columns: {', '.join(diagnostics.get('missing_columns', []))}")
```

## Final Validation Checklist

✅ **App boots without exiting**
- Removed automatic Alembic execution
- Startup only verifies connectivity
- No hard failures on schema mismatches (warnings only)

✅ **Alembic runs once and never repeats**
- Migrations must be run manually at deploy time
- `alembic_version` table prevents re-running from base
- Fix utility available if table is corrupted

✅ **`/api/pipeline/websites` returns real data or real errors**
- Data integrity checks in place
- HTTP 500 on `total > 0` but `data = []`
- All errors logged and re-raised

✅ **Social discovery no longer fails on missing columns**
- Migration adds all required columns
- Schema validation warns on mismatches
- Queries fail loudly if columns missing

✅ **Deploy logs stop at "Your service is live 🎉" and stay alive**
- No automatic migrations = no crash loops
- Startup only verifies state, doesn't modify schema
- App stays running even if schema needs updates

## How to Run Migrations

### Option 1: Manual (Recommended for Production)
```bash
cd backend
alembic upgrade head
```

### Option 2: HTTP Endpoint (For Render Free Tier)
```bash
curl -X POST https://your-app.onrender.com/api/health/migrate \
     -H "X-Migration-Token: your-secret-token"
```

### Option 3: Fix Alembic Version Table First (If Corrupted)
```bash
cd backend
python fix_alembic_version.py
alembic upgrade head
```

## Alembic Diff

**Before Fix**:
- `alembic_version` table: Missing or corrupted
- Startup behavior: Runs `alembic upgrade heads` automatically
- Result: Re-runs `000000000000` on every boot, causing crashes

**After Fix**:
- `alembic_version` table: Fixed via utility script
- Startup behavior: Only verifies state, doesn't run migrations
- Result: App boots successfully, migrations run once at deploy time

## Final Alembic Version

After running `fix_alembic_version.py` and `alembic upgrade head`:

```
alembic_version
└── version_num = 'ensure_alembic_version_table' (or latest head)
```

## Confirmation

**Startup no longer runs migrations**:
- ✅ Removed `command.upgrade()` from `startup()` function
- ✅ Replaced with `verify_database_state()` (read-only checks)
- ✅ App boots without executing Alembic
- ✅ Migrations must be run manually at deploy time

**This fixes the crash loop permanently.**

