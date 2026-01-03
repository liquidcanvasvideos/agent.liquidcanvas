# Social Outreach Schema Initialization Fix

## Root Cause Analysis

### Problem
The social outreach endpoints were returning `503 Service Unavailable` with the error message:
```
Social outreach feature is not available: social schema not initialized
```

### Root Cause
1. **Migration Chain Issues**: Multiple migration heads caused Alembic to fail when running `alembic upgrade head`
2. **Silent Migration Failures**: Migrations could fail during startup, but the app continued to start, leaving tables missing
3. **Hard Failure Mode**: Endpoints checked for schema readiness and immediately returned 503 errors instead of gracefully handling missing tables
4. **No Automatic Recovery**: If migrations failed, there was no mechanism to create tables automatically

### Where the Error Was Raised
- **Location**: `backend/app/utils/schema_validator.py` → `check_social_schema_ready()`
- **Called by**: All social pipeline endpoints (`/api/social/pipeline/*`)
- **Check Method**: SQL query to `information_schema.tables` to verify table existence
- **Tables Checked**: 
  - `social_profiles`
  - `social_discovery_jobs`
  - `social_drafts`
  - `social_messages`

## Solution Implemented (Option B - Feature-Scoped Schema Initialization)

### 1. Automatic Table Creation on Startup
**File**: `backend/app/main.py`

- After migrations run, if schema validation fails, the app now:
  - Checks if social tables are missing
  - Attempts to create them automatically using SQLAlchemy metadata
  - Logs warnings but allows the app to continue starting
  - Never exits or crashes due to missing social tables

### 2. Automatic Table Creation on Endpoint Calls
**File**: `backend/app/utils/social_schema_init.py` (NEW)

- Created new utility function `ensure_social_tables_exist()`
- Checks which social tables are missing
- Creates missing tables using `Base.metadata.create_all()` with a synchronous engine
- Returns success status and list of any tables that still don't exist

### 3. Graceful Degradation in Endpoints
**File**: `backend/app/api/social_pipeline.py`

**Before**:
```python
if not schema_status["ready"]:
    raise HTTPException(status_code=503, detail="...")
```

**After**:
```python
if not schema_status["ready"]:
    # Try to create tables automatically
    social_success, social_missing = await ensure_social_tables_exist(engine)
    if not social_success:
        # Return empty response instead of 503
        return {"success": False, "message": "...", ...}
    # Re-check and continue if successful
```

### 4. Removed All 503 Errors
- **Status endpoint** (`/api/social/pipeline/status`): Returns empty counts (0s) instead of 503
- **Discover endpoint** (`/api/social/pipeline/discover`): Returns `success=False` response instead of 503
- **Review endpoint** (`/api/social/pipeline/review`): Returns `success=False` response instead of 503
- **Draft endpoint** (`/api/social/pipeline/draft`): Returns `success=False` response instead of 503
- **Send endpoint** (`/api/social/pipeline/send`): Returns `success=False` response instead of 503
- **Followup endpoint** (`/api/social/pipeline/followup`): Returns `success=False` response instead of 503

## Migration Verification

### Alembic Migrations
Social tables are defined in these migration files:
1. `backend/alembic/versions/add_social_outreach_tables.py` - Creates base tables
2. `backend/alembic/versions/add_social_outreach_tables_complete.py` - Adds additional columns
3. `backend/alembic/versions/update_social_models_complete_schema.py` - Final schema updates

### Migration Chain
- All migrations are idempotent (can run multiple times safely)
- Base migration (`000000000000_create_base_tables.py`) is now idempotent
- All table creation migrations check for table existence before creating

### Startup Migration Execution
- Migrations run automatically on every startup via `alembic upgrade heads`
- If migrations fail, the app logs errors but continues starting
- Social table creation is attempted as a safety net if migrations fail

## Validation Checklist

After this fix, confirm:

✅ **POST /api/social/pipeline/discover** returns 200 (not 503)
- If tables missing: Returns `{"success": false, "message": "..."}`
- If tables exist: Creates discovery job successfully

✅ **GET /api/social/pipeline/status** returns 200 with zero counts
- Never returns 503
- Returns `{"discovered": 0, "reviewed": 0, ...}` if tables are empty

✅ **No 503 errors** for any social endpoints
- All endpoints return structured responses instead of HTTP errors

✅ **Restarting backend** does not break social routes
- Tables are created automatically if missing
- App starts successfully even if migrations fail

✅ **Website outreach remains untouched**
- No changes to website pipeline logic
- No changes to website table creation
- Complete separation maintained

## Architecture Guarantees

1. **Feature-Scoped**: Social schema checks only affect social endpoints
2. **Graceful Degradation**: Missing tables never cause crashes or 503 errors
3. **Automatic Recovery**: Tables are created automatically when detected as missing
4. **No Bypassing Alembic**: Migrations still run first; auto-creation is a safety net
5. **Clear Logging**: All schema operations are logged for debugging

## Files Changed

1. `backend/app/utils/social_schema_init.py` (NEW) - Automatic table creation utility
2. `backend/app/main.py` - Startup schema initialization logic
3. `backend/app/api/social_pipeline.py` - Graceful degradation in all endpoints
4. `backend/alembic/versions/000000000000_create_base_tables.py` - Made idempotent
5. `backend/alembic/versions/4b9608290b5d_add_settings_table.py` - Made idempotent
6. `backend/alembic/versions/add_discovery_query_table.py` - Made idempotent
7. `backend/alembic/versions/add_scraper_history_table.py` - Made idempotent

## Next Steps

1. **Deploy to Render** and verify migrations run successfully
2. **Test social endpoints** to confirm no 503 errors
3. **Monitor logs** for automatic table creation messages
4. **Verify data persistence** after table creation

## Notes

- This fix implements **Option B** (Feature-Scoped Schema Initialization) as recommended
- Tables are created using SQLAlchemy metadata, not raw SQL
- All operations are logged for debugging and monitoring
- The fix is backward-compatible and doesn't break existing functionality

