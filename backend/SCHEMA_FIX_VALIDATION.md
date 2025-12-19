# Schema Fix Validation Checklist

## Problem Summary
Backend queries were failing with `UndefinedColumnError` for:
- `prospects.final_body`
- `prospects.thread_id`
- `prospects.sequence_index`

This caused:
- All SELECT queries to fail
- Empty result sets despite existing data
- Pipeline verify endpoint returning 500 errors
- Aborted transactions

## Solution Implemented

### 1. Database Schema Audit ✅
**Identified Missing Columns:**
- `final_body` TEXT (nullable) - Final sent email body
- `thread_id` UUID (nullable, indexed) - Thread ID for follow-up emails
- `sequence_index` INTEGER (default 0, not null) - Follow-up sequence index

**Migration Created:**
- `backend/alembic/versions/add_final_body_thread_id_sequence_index.py`
- Idempotent: Safe to run multiple times
- Checks for column existence before adding
- Properly handles defaults and NOT NULL constraints

### 2. ORM Model Restored ✅
**Files Updated:**
- `backend/app/models/prospect.py`: Uncommented `final_body` column
- `backend/app/schemas/prospect.py`: Uncommented `final_body` in response schema
- `backend/app/tasks/send.py`: Restored `final_body` assignment after sending
- `backend/app/api/prospects.py`: Restored ORM queries for `final_body`

### 3. Transaction Safety ✅
**Already Implemented:**
All endpoints have proper rollback handling:
- `backend/app/api/pipeline.py`: All endpoints have `await db.rollback()` in except blocks
- `backend/app/api/prospects.py`: All endpoints have `await db.rollback()` in except blocks
- `backend/app/api/jobs.py`: All endpoints have `await db.rollback()` in except blocks
- `backend/app/db/database.py`: `get_db()` dependency has rollback in exception handler

### 4. Migration Application
**To Apply Migration:**
```bash
cd backend
alembic upgrade head
```

**Or let startup event apply automatically:**
The `startup()` event in `backend/app/main.py` runs migrations automatically on server start.

### 5. Validation Checklist

#### After Migration Runs:

- [ ] **Database Schema:**
  - [ ] `final_body` column exists in `prospects` table
  - [ ] `thread_id` column exists in `prospects` table
  - [ ] `sequence_index` column exists in `prospects` table
  - [ ] `thread_id` has index `ix_prospects_thread_id`

- [ ] **List Endpoints Return Data:**
  - [ ] `GET /api/prospects` returns rows (status 200, non-empty array)
  - [ ] `GET /api/prospects/leads` returns rows (status 200, non-empty array)
  - [ ] `GET /api/prospects/scraped-emails` returns rows (status 200, non-empty array)
  - [ ] `GET /api/pipeline/websites` returns rows (status 200, non-empty array)

- [ ] **Pipeline Actions Work:**
  - [ ] `POST /api/pipeline/verify` executes without error (status 200)
  - [ ] Verification updates `verification_status` correctly
  - [ ] No `UndefinedColumnError` in logs

- [ ] **UI Displays Data:**
  - [ ] Existing prospects appear in UI tabs
  - [ ] Pipeline counts update correctly
  - [ ] Verify step unlocks Drafting step
  - [ ] No empty tabs despite data existing

- [ ] **No Errors in Logs:**
  - [ ] No `column prospects.final_body does not exist` errors
  - [ ] No `column prospects.thread_id does not exist` errors
  - [ ] No `column prospects.sequence_index does not exist` errors
  - [ ] No `InFailedSQLTransactionError` errors

## Migration SQL (for manual application if needed)

```sql
-- Add final_body column
ALTER TABLE prospects ADD COLUMN IF NOT EXISTS final_body TEXT;

-- Add thread_id column
ALTER TABLE prospects ADD COLUMN IF NOT EXISTS thread_id UUID;
CREATE INDEX IF NOT EXISTS ix_prospects_thread_id ON prospects(thread_id);

-- Add sequence_index column
ALTER TABLE prospects ADD COLUMN IF NOT EXISTS sequence_index INTEGER;
UPDATE prospects SET sequence_index = 0 WHERE sequence_index IS NULL;
ALTER TABLE prospects ALTER COLUMN sequence_index SET NOT NULL;
ALTER TABLE prospects ALTER COLUMN sequence_index SET DEFAULT 0;
```

## Model Diff

### Before:
```python
# final_body = Column(Text)  # REMOVED: Column doesn't exist
thread_id = Column(UUID(as_uuid=True), index=True)
sequence_index = Column(Integer, default=0)
```

### After:
```python
final_body = Column(Text, nullable=True)
thread_id = Column(UUID(as_uuid=True), nullable=True, index=True)
sequence_index = Column(Integer, default=0, nullable=False)
```

## Next Steps

1. **Restart Backend:** Migration will run automatically on startup
2. **Verify Migration:** Check logs for "✅ Added column final_body" messages
3. **Test Endpoints:** Use the validation checklist above
4. **Monitor Logs:** Ensure no more `UndefinedColumnError` messages

## Rollback (if needed)

If migration causes issues:
```bash
cd backend
alembic downgrade -1
```

Or manually:
```sql
ALTER TABLE prospects DROP COLUMN IF EXISTS final_body;
ALTER TABLE prospects DROP COLUMN IF EXISTS thread_id;
ALTER TABLE prospects DROP COLUMN IF EXISTS sequence_index;
DROP INDEX IF EXISTS ix_prospects_thread_id;
```

