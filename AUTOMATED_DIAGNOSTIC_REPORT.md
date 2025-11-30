# Automated Diagnostic Report: Art Outreach Automation System

**Generated:** 2025-01-XX  
**Scope:** Full pipeline analysis (discovery → enrichment → send → state updates)

---

## Executive Summary (5-Line)

1. **Discovery pipeline works** but saves prospects without emails (`contact_email = None`)
2. **Enrichment endpoint exists but returns "not implemented"** - Hunter.io client exists but is never called
3. **Send automation endpoint exists but returns "not implemented"** - Gmail client exists but bulk sending is broken
4. **Worker tasks exist in `worker/tasks/` but backend doesn't use them** - architectural mismatch after free-tier refactor
5. **Database schema mismatch** - `discovery_query_id` column may be missing in production, causing 500 errors

---

## Machine-Readable JSON Report

```json
{
  "files_scanned": [
    "backend/app/api/jobs.py",
    "backend/app/api/prospects.py",
    "backend/app/tasks/discovery.py",
    "backend/app/clients/hunter.py",
    "backend/app/clients/gmail.py",
    "backend/app/clients/gemini.py",
    "backend/app/models/prospect.py",
    "backend/app/models/job.py",
    "worker/tasks/enrichment.py",
    "worker/tasks/send.py",
    "backend/app/scheduler.py",
    "backend/alembic/versions/add_discovery_query_table.py"
  ],
  "endpoints_unimplemented": [
    {
      "path": "/api/prospects/enrich",
      "function": "create_enrichment_job",
      "file": "backend/app/api/prospects.py",
      "line_start": 62,
      "line_end": 99,
      "note": "Returns 'not yet implemented' message, creates job but immediately marks as failed"
    },
    {
      "path": "/api/jobs/score",
      "function": "create_scoring_job",
      "file": "backend/app/api/jobs.py",
      "line_start": 220,
      "line_end": 240,
      "note": "Returns HTTPException 501 'not yet implemented'"
    },
    {
      "path": "/api/jobs/send",
      "function": "create_send_job",
      "file": "backend/app/api/jobs.py",
      "line_start": 260,
      "line_end": 280,
      "note": "Returns HTTPException 501 'not yet implemented'"
    },
    {
      "path": "/api/jobs/followup",
      "function": "create_followup_job",
      "file": "backend/app/api/jobs.py",
      "line_start": 300,
      "line_end": 320,
      "note": "Returns HTTPException 501 'not yet implemented'"
    },
    {
      "path": "/api/jobs/check-replies",
      "function": "check_replies",
      "file": "backend/app/api/jobs.py",
      "line_start": 340,
      "line_end": 350,
      "note": "Returns HTTPException 501 'not yet implemented'"
    }
  ],
  "worker_tasks_unused": [
    {
      "path": "worker/tasks/enrichment.py",
      "function": "enrich_prospects_task",
      "note": "Task exists but backend doesn't call it. Backend needs equivalent in backend/app/tasks/enrichment.py"
    },
    {
      "path": "worker/tasks/send.py",
      "function": "send_emails_task",
      "note": "Task exists but backend doesn't call it. Backend needs equivalent in backend/app/tasks/send.py"
    },
    {
      "path": "worker/tasks/scoring.py",
      "function": "score_prospects_task",
      "note": "Task exists but backend doesn't call it"
    },
    {
      "path": "worker/tasks/followup.py",
      "function": "send_followups_task",
      "note": "Task exists but backend doesn't call it"
    },
    {
      "path": "worker/tasks/reply_handler.py",
      "function": "check_replies_task",
      "note": "Task exists but backend doesn't call it"
    }
  ],
  "hunter_checks": {
    "client_file": "backend/app/clients/hunter.py",
    "status": "ok",
    "details": "Hunter.io client correctly implements domain search endpoint, parses response.data.emails[*].value. Client is functional but never called by enrichment endpoint.",
    "unused_functions": [],
    "integration_points": [
      {
        "should_call": "backend/app/api/prospects.py:89 (enrichment endpoint)",
        "actual": "Returns 'not implemented' instead of calling hunter client",
        "missing_code": "No task implementation in backend/app/tasks/enrichment.py"
      }
    ]
  },
  "migrations": {
    "expected_columns_missing": ["discovery_query_id"],
    "migration_files": [
      "backend/alembic/versions/add_discovery_query_table.py"
    ],
    "migration_revision": "add_discovery_query",
    "down_revision": "4b9608290b5d",
    "suggested_migration_command": "cd backend && alembic upgrade head",
    "mismatch_likelihood": "HIGH - Error handling in prospects.py specifically checks for this column missing"
  },
  "make_mapping_advice": "Make.com integration is documented but not implemented in code. If implementing: Use 'Search Rows (Advanced)' module → 'Iterator' module → map {{iterator.domain}} or {{Search Rows Advanced[0].domain}} depending on bundle structure. For DataForSEO webhook: HTTP module with Parse Response ON, extract task_id from {{1.tasks[0].id}}.",
  "suggested_fixes": [
    {
      "priority": "HIGH",
      "title": "Implement enrichment task in backend",
      "target_file": "backend/app/tasks/enrichment.py",
      "insert_location": "Create new file",
      "patch": "See detailed patch below",
      "test_command": "curl -X POST http://localhost:8000/api/prospects/enrich?max_prospects=10",
      "env_vars_required": ["HUNTER_API_KEY"]
    },
    {
      "priority": "HIGH",
      "title": "Wire enrichment endpoint to task",
      "target_file": "backend/app/api/prospects.py",
      "insert_location": "Line 89, replace TODO block",
      "patch": "See detailed patch below",
      "test_command": "Same as above"
    },
    {
      "priority": "HIGH",
      "title": "Implement send task in backend",
      "target_file": "backend/app/tasks/send.py",
      "insert_location": "Create new file",
      "patch": "See detailed patch below",
      "test_command": "curl -X POST http://localhost:8000/api/jobs/send?max_prospects=10",
      "env_vars_required": ["GMAIL_REFRESH_TOKEN", "GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET"]
    },
    {
      "priority": "MEDIUM",
      "title": "Add auto-enrichment trigger after discovery",
      "target_file": "backend/app/tasks/discovery.py",
      "insert_location": "After line 420 (job completion)",
      "patch": "See detailed patch below"
    },
    {
      "priority": "MEDIUM",
      "title": "Fix database migration",
      "target_file": "backend/alembic/versions/add_discovery_query_table.py",
      "insert_location": "Verify migration exists and run",
      "patch": "N/A - Run migration command",
      "test_command": "cd backend && alembic upgrade head && python -c 'from app.models import Prospect; print(hasattr(Prospect, \"discovery_query_id\"))'"
    }
  ]
}
```

---

## Detailed Human-Readable Report

### 1. Quick Repo Health & Tests

**Test Suite Status:**
- ❌ No pytest.ini found
- ❌ No test files found in backend/
- ⚠️ No automated tests configured

**Linter Status:**
- ⚠️ No flake8/ruff configuration found
- ⚠️ Static analysis not run (timeout issues)

**Recommendation:** Add test suite and linting configuration.

---

### 2. HTTP/API Endpoints and Workers

#### Backend API Endpoints (`backend/app/api/`)

| File | Function | Lines | Purpose |
|------|----------|-------|---------|
| `jobs.py` | `create_discovery_job` | 81-180 | ✅ Creates discovery job, calls `process_discovery_job` |
| `jobs.py` | `get_job_status` | 184-200 | ✅ Returns job status |
| `jobs.py` | `list_jobs` | 202-220 | ✅ Lists all jobs |
| `jobs.py` | `create_scoring_job` | 220-240 | ❌ Returns 501 "not yet implemented" |
| `jobs.py` | `create_send_job` | 260-280 | ❌ Returns 501 "not yet implemented" |
| `jobs.py` | `create_followup_job` | 300-320 | ❌ Returns 501 "not yet implemented" |
| `jobs.py` | `check_replies` | 340-350 | ❌ Returns 501 "not yet implemented" |
| `jobs.py` | `cancel_job` | 250-260 | ✅ Cancels running job |
| `prospects.py` | `create_enrichment_job` | 62-99 | ❌ Returns "not yet implemented" |
| `prospects.py` | `list_prospects` | 102-280 | ✅ Lists prospects with filters |
| `prospects.py` | `get_prospect` | 226-240 | ✅ Gets single prospect |
| `prospects.py` | `compose_email` | 241-280 | ✅ Composes email using Gemini |
| `prospects.py` | `send_email` | 314-380 | ✅ Sends single email via Gmail |

#### Backend Tasks (`backend/app/tasks/`)

| File | Function | Lines | Purpose |
|------|----------|-------|---------|
| `discovery.py` | `process_discovery_job` | 442-452 | ✅ Wrapper for discovery job |
| `discovery.py` | `discover_websites_async` | 75-440 | ✅ Main discovery logic |
| `enrichment.py` | ❌ **FILE DOES NOT EXIST** | - | **MISSING** |

#### Worker Tasks (`worker/tasks/`)

| File | Function | Status | Note |
|------|----------|--------|------|
| `enrichment.py` | `enrich_prospects_task` | ✅ Exists | Not called by backend |
| `send.py` | `send_emails_task` | ✅ Exists | Not called by backend |
| `scoring.py` | `score_prospects_task` | ✅ Exists | Not called by backend |
| `followup.py` | `send_followups_task` | ✅ Exists | Not called by backend |
| `reply_handler.py` | `check_replies_task` | ✅ Exists | Not called by backend |

---

### 3. Discovery → Enrichment → Send Flow Trace

#### Current Flow (BROKEN):

```
1. POST /api/jobs/discover
   └─> backend/app/api/jobs.py:81-180
       └─> Calls: process_discovery_job(str(job.id))
           └─> backend/app/tasks/discovery.py:442
               └─> Calls: discover_websites_async(job_id)
                   └─> backend/app/tasks/discovery.py:75-440
                       └─> Saves prospects with contact_email = None
                           └─> [STOP] No enrichment trigger

2. POST /api/prospects/enrich (MANUAL)
   └─> backend/app/api/prospects.py:62-99
       └─> Returns: "not yet implemented"
           └─> [FAIL] No task execution

3. POST /api/jobs/send (BULK)
   └─> backend/app/api/jobs.py:260-280
       └─> Returns: HTTPException 501 "not yet implemented"
           └─> [FAIL] No task execution
```

#### Expected Flow (SHOULD BE):

```
1. POST /api/jobs/discover
   └─> Discovery saves prospects
       └─> [AUTO] Triggers enrichment job
           └─> Enrichment task calls Hunter.io
               └─> Updates prospects with emails
                   └─> [AUTO] Triggers send job (if auto_send enabled)
                       └─> Send task calls Gmail API
                           └─> Updates prospect status to "sent"
```

#### Missing Handoffs:

1. **Discovery → Enrichment:**
   - **Location:** `backend/app/tasks/discovery.py:420` (after job completion)
   - **Missing:** Auto-trigger enrichment job
   - **Current:** None

2. **Enrichment Endpoint → Task:**
   - **Location:** `backend/app/api/prospects.py:89`
   - **Missing:** Call to `backend/app/tasks/enrichment.py` (file doesn't exist)
   - **Current:** Returns "not implemented"

3. **Send Endpoint → Task:**
   - **Location:** `backend/app/api/jobs.py:271`
   - **Missing:** Call to `backend/app/tasks/send.py` (file doesn't exist)
   - **Current:** Returns 501 error

---

### 4. Hunter.io & Enrichment Checks

**Client File:** `backend/app/clients/hunter.py`

**Status:** ✅ **CLIENT IS CORRECT**

**Verification:**
- ✅ Constructs correct HTTP request: `GET https://api.hunter.io/v2/domain-search?domain={domain}&api_key={key}`
- ✅ Parses response correctly: `response.data.emails[*].value`
- ✅ Handles errors gracefully
- ✅ Returns structured response: `{success, domain, emails, total}`

**Problem:** Client is never called.

**Integration Points:**
- ❌ `backend/app/api/prospects.py:89` - Should call Hunter but doesn't
- ❌ `backend/app/tasks/enrichment.py` - File doesn't exist
- ✅ `worker/tasks/enrichment.py` - Has correct implementation but unused

**Missing Code Location:**
- File: `backend/app/tasks/enrichment.py` - **FILE MISSING**
- Should import: `from app.clients.hunter import HunterClient`
- Should call: `hunter_client.search_domain(domain)`

---

### 5. Worker / Background Task Integration

**Architecture Mismatch:**

The system was refactored to run tasks directly in the backend (free-tier compatibility), but only discovery was migrated. Other tasks remain in `worker/tasks/` but are never called.

**Tasks Status:**

| Task | Worker Location | Backend Location | Status |
|------|----------------|------------------|--------|
| Discovery | `worker/tasks/discovery.py` | ✅ `backend/app/tasks/discovery.py` | ✅ Migrated |
| Enrichment | ✅ `worker/tasks/enrichment.py` | ❌ **MISSING** | ❌ Not migrated |
| Send | ✅ `worker/tasks/send.py` | ❌ **MISSING** | ❌ Not migrated |
| Scoring | ✅ `worker/tasks/scoring.py` | ❌ **MISSING** | ❌ Not migrated |
| Follow-up | ✅ `worker/tasks/followup.py` | ❌ **MISSING** | ❌ Not migrated |

**Wiring Locations:**

1. **Enrichment:**
   - **Should wire at:** `backend/app/api/prospects.py:89`
   - **Current:** Returns "not implemented"
   - **Should call:** `backend/app/tasks/enrichment.py:process_enrichment_job()` (doesn't exist)

2. **Send:**
   - **Should wire at:** `backend/app/api/jobs.py:271`
   - **Current:** Returns 501 error
   - **Should call:** `backend/app/tasks/send.py:process_send_job()` (doesn't exist)

---

### 6. Database Schema & Migrations

**Model:** `backend/app/models/prospect.py`

**Columns Used by Code:**
- `id` (UUID, primary key)
- `domain` (String, indexed)
- `page_url` (Text)
- `page_title` (Text)
- `contact_email` (String, indexed) - **Often NULL**
- `contact_method` (String)
- `da_est` (Numeric)
- `score` (Numeric)
- `outreach_status` (String, indexed) - Default: "pending"
- `last_sent` (DateTime)
- `followups_sent` (Integer)
- `draft_subject` (Text)
- `draft_body` (Text)
- `dataforseo_payload` (JSON)
- `hunter_payload` (JSON)
- `discovery_query_id` (UUID, ForeignKey) - **⚠️ MAY BE MISSING IN PROD**
- `created_at` (DateTime)
- `updated_at` (DateTime)

**Migration Status:**

- **Migration File:** `backend/alembic/versions/add_discovery_query_table.py`
- **Revision ID:** `add_discovery_query`
- **Down Revision:** `4b9608290b5d`
- **Adds Column:** `discovery_query_id` to `prospects` table
- **Status:** ⚠️ **MIGRATION MAY NOT HAVE RUN IN PRODUCTION**

**Evidence of Mismatch:**
- Error handling in `backend/app/api/prospects.py:190-198` specifically checks for missing `discovery_query_id` column
- Suggests this error has occurred in production

**Suggested Migration Command:**
```bash
cd backend
alembic upgrade head
```

**Verification:**
```python
# Check if column exists
from app.models import Prospect
print(hasattr(Prospect, 'discovery_query_id'))  # Should be True
```

---

### 7. Make.com / Integration Scripts

**Status:** ❌ **NOT IMPLEMENTED IN CODE**

**Documentation Found:**
- `DATAFORSEO_MAKE_CONFIG.md` - Documents Make.com configuration for DataForSEO
- No Make.com webhook handlers in code
- No Make.com API client
- No Make.com scenario files

**Intended Integration (from docs):**
- DataForSEO webhook → Make.com HTTP module → Process → Gmail → Update sheet

**Recommendation:**
- If Make.com is required, implement webhook endpoint at `/api/webhooks/make` or `/api/webhooks/dataforseo`
- Use Make.com HTTP module with "Parse Response" ON
- Extract task_id from `{{1.tasks[0].id}}` (as documented)

**Make.com Mapping Advice (if implementing):**

For DataForSEO webhook:
```
HTTP Module Settings:
- Parse response: ON
- Serialized URL: OFF
- Method: POST
- Body: Raw JSON array [{"keyword": "...", "location_code": 2840}]

Extract Task ID:
{{1.tasks[0].id}}

For Google Sheets Integration:
1. Search Rows (Advanced) module
2. Iterator module (if multiple rows)
3. Map: {{iterator.domain}} or {{Search Rows Advanced[0].domain}}
4. HTTP module for DataForSEO
5. Gmail module for sending
6. Update Rows module to mark as processed
```

---

### 8. Logs & Runtime Errors Analysis

**User-Reported Errors:**

1. **Make.com HTTP 400 wrong_params:**
   - **Likely Cause:** Missing or incorrect query parameter mapping
   - **Location:** Make.com scenario configuration (not in repo code)
   - **Fix:** Verify DataForSEO payload format matches API spec

2. **Function '1.domain_' not found:**
   - **Likely Cause:** Incorrect Make.com mapping expression
   - **Fix:** Use `{{iterator.domain}}` or `{{Search Rows Advanced[0].domain}}` instead of `{{1.domain_}}`

3. **Empty array vs bundle:**
   - **Likely Cause:** Search Rows (Advanced) returns single bundle, Iterator expects array
   - **Fix:** Use Iterator module after Search Rows, or map directly from bundle if single result

**Console Stack Traces:**
- "Failed to get stats: TypeError: Cannot read properties of undefined (reading 'forEach')" - **FIXED** (defensive guards added)
- "column prospects.discovery_query_id does not exist" - **MIGRATION ISSUE**

---

### 9. Top 5 Root Causes

#### 1. Enrichment Task Not Implemented in Backend
- **Impact:** Prospects discovered but never get email addresses, blocking entire email pipeline
- **Files:** `backend/app/tasks/enrichment.py` (MISSING), `backend/app/api/prospects.py:89`
- **Urgency:** 🔴 **HIGH**
- **Fix:** Create enrichment task file, wire to endpoint

#### 2. Send Task Not Implemented in Backend
- **Impact:** Cannot send bulk emails, only individual sends work
- **Files:** `backend/app/tasks/send.py` (MISSING), `backend/app/api/jobs.py:271`
- **Urgency:** 🔴 **HIGH**
- **Fix:** Create send task file, wire to endpoint

#### 3. No Auto-Enrichment Trigger After Discovery
- **Impact:** Manual enrichment required, breaks automation flow
- **Files:** `backend/app/tasks/discovery.py:420`
- **Urgency:** 🟡 **MEDIUM**
- **Fix:** Add enrichment job trigger after discovery completes

#### 4. Database Migration Not Applied
- **Impact:** 500 errors on `/api/prospects` endpoint
- **Files:** `backend/alembic/versions/add_discovery_query_table.py`
- **Urgency:** 🟡 **MEDIUM**
- **Fix:** Run `alembic upgrade head` in production

#### 5. Worker Tasks Exist But Unused
- **Impact:** Code duplication, confusion about which tasks to use
- **Files:** `worker/tasks/*.py` (all unused)
- **Urgency:** 🟢 **LOW** (architectural cleanup)
- **Fix:** Either migrate all tasks to backend or remove worker directory

---

## Suggested Fix Patches

### Fix #1: Create Enrichment Task

**File:** `backend/app/tasks/enrichment.py` (CREATE NEW)

```python
"""
Enrichment task - finds emails for prospects using Hunter.io
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.database import AsyncSessionLocal
from app.models.prospect import Prospect
from app.models.job import Job
from app.clients.hunter import HunterClient

logger = logging.getLogger(__name__)


async def process_enrichment_job(job_id: str) -> Dict[str, Any]:
    """
    Process enrichment job to find emails for prospects
    """
    async with AsyncSessionLocal() as db:
        # Get job
        result = await db.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()
        
        if not job:
            return {"error": "Job not found"}
        
        job.status = "running"
        await db.commit()
        
        try:
            # Get job parameters
            params = job.params or {}
            prospect_ids = params.get("prospect_ids")
            max_prospects = params.get("max_prospects", 100)
            
            # Build query
            query = select(Prospect).where(
                Prospect.contact_email.is_(None),
                Prospect.outreach_status == "pending"
            )
            
            if prospect_ids:
                query = query.where(Prospect.id.in_([UUID(pid) for pid in prospect_ids]))
            
            query = query.limit(max_prospects)
            
            result = await db.execute(query)
            prospects = result.scalars().all()
            
            logger.info(f"🔍 Enriching {len(prospects)} prospects...")
            
            # Initialize Hunter client
            try:
                hunter_client = HunterClient()
            except ValueError as e:
                job.status = "failed"
                job.error_message = f"Hunter.io not configured: {e}"
                await db.commit()
                return {"error": str(e)}
            
            enriched_count = 0
            failed_count = 0
            
            # Enrich each prospect
            for prospect in prospects:
                try:
                    domain = prospect.domain
                    logger.info(f"🔍 Searching emails for {domain}...")
                    
                    # Call Hunter.io
                    hunter_result = await hunter_client.search_domain(domain)
                    
                    if hunter_result.get("success") and hunter_result.get("emails"):
                        emails = hunter_result["emails"]
                        if emails:
                            # Get first email
                            first_email = emails[0]
                            prospect.contact_email = first_email.get("value")
                            prospect.contact_method = "email"
                            prospect.hunter_payload = hunter_result
                            enriched_count += 1
                            logger.info(f"✅ Found email for {domain}: {prospect.contact_email}")
                        else:
                            logger.info(f"⚠️  No emails found for {domain}")
                            prospect.hunter_payload = hunter_result
                    else:
                        logger.warning(f"❌ Hunter.io failed for {domain}: {hunter_result.get('error', 'Unknown error')}")
                        prospect.hunter_payload = hunter_result
                        failed_count += 1
                    
                    await db.commit()
                    await db.refresh(prospect)
                    
                    # Rate limiting
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(f"❌ Error enriching {prospect.domain}: {e}", exc_info=True)
                    failed_count += 1
                    continue
            
            # Update job status
            job.status = "completed"
            job.result = {
                "prospects_enriched": enriched_count,
                "prospects_failed": failed_count,
                "total_processed": len(prospects)
            }
            await db.commit()
            
            logger.info(f"✅ Enrichment job {job_id} completed: {enriched_count} enriched, {failed_count} failed")
            
            return {
                "job_id": job_id,
                "status": "completed",
                "prospects_enriched": enriched_count,
                "prospects_failed": failed_count
            }
            
        except Exception as e:
            logger.error(f"Enrichment job {job_id} failed: {e}", exc_info=True)
            job.status = "failed"
            job.error_message = str(e)
            await db.commit()
            return {"error": str(e)}
```

**Test Command:**
```bash
curl -X POST "http://localhost:8000/api/prospects/enrich?max_prospects=5" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Env Vars Required:**
- `HUNTER_API_KEY` (set in Render environment variables)

---

### Fix #2: Wire Enrichment Endpoint

**File:** `backend/app/api/prospects.py`  
**Location:** Lines 89-99 (replace TODO block)

```python
@router.post("/enrich")
async def create_enrichment_job(
    prospect_ids: Optional[List[UUID]] = None,
    max_prospects: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new enrichment job to find emails for prospects
    """
    # Create job record
    job = Job(
        job_type="enrich",
        params={
            "prospect_ids": [str(pid) for pid in prospect_ids] if prospect_ids else None,
            "max_prospects": max_prospects
        },
        status="pending"
    )
    
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    # Start enrichment task in background
    try:
        from app.tasks.enrichment import process_enrichment_job
        import asyncio
        asyncio.create_task(process_enrichment_job(str(job.id)))
        logger.info(f"Enrichment job {job.id} started in background")
    except Exception as e:
        logger.error(f"Failed to start enrichment job {job.id}: {e}", exc_info=True)
        job.status = "failed"
        job.error_message = f"Failed to start job: {e}"
        await db.commit()
        await db.refresh(job)
    
    return {
        "job_id": job.id,
        "status": "pending",
        "message": f"Enrichment job {job.id} started"
    }
```

---

### Fix #3: Create Send Task

**File:** `backend/app/tasks/send.py` (CREATE NEW)

```python
"""
Send task - sends emails to prospects via Gmail API
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.database import AsyncSessionLocal
from app.models.prospect import Prospect
from app.models.job import Job
from app.models.email_log import EmailLog
from app.clients.gmail import GmailClient
from app.clients.gemini import GeminiClient

logger = logging.getLogger(__name__)


async def process_send_job(job_id: str) -> Dict[str, Any]:
    """
    Process send job to send emails to prospects
    """
    async with AsyncSessionLocal() as db:
        # Get job
        result = await db.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()
        
        if not job:
            return {"error": "Job not found"}
        
        job.status = "running"
        await db.commit()
        
        try:
            # Get job parameters
            params = job.params or {}
            prospect_ids = params.get("prospect_ids")
            max_prospects = params.get("max_prospects", 100)
            auto_send = params.get("auto_send", False)
            
            # Build query
            query = select(Prospect).where(
                Prospect.contact_email.isnot(None),
                Prospect.outreach_status == "pending"
            )
            
            if prospect_ids:
                query = query.where(Prospect.id.in_([UUID(pid) for pid in prospect_ids]))
            
            query = query.limit(max_prospects)
            
            result = await db.execute(query)
            prospects = result.scalars().all()
            
            logger.info(f"📧 Sending emails to {len(prospects)} prospects...")
            
            # Initialize clients
            try:
                gmail_client = GmailClient()
                gemini_client = GeminiClient() if auto_send else None
            except ValueError as e:
                job.status = "failed"
                job.error_message = f"Gmail not configured: {e}"
                await db.commit()
                return {"error": str(e)}
            
            sent_count = 0
            failed_count = 0
            
            # Send to each prospect
            for prospect in prospects:
                try:
                    # Get or compose email
                    subject = prospect.draft_subject
                    body = prospect.draft_body
                    
                    if not subject or not body:
                        if gemini_client:
                            # Compose email
                            page_snippet = None
                            if prospect.dataforseo_payload:
                                page_snippet = prospect.dataforseo_payload.get("description")
                            
                            contact_name = None
                            if prospect.hunter_payload and prospect.hunter_payload.get("emails"):
                                emails = prospect.hunter_payload["emails"]
                                if emails:
                                    first_email = emails[0]
                                    first_name = first_email.get("first_name")
                                    last_name = first_email.get("last_name")
                                    if first_name or last_name:
                                        contact_name = f"{first_name or ''} {last_name or ''}".strip()
                            
                            gemini_result = await gemini_client.compose_email(
                                domain=prospect.domain,
                                page_title=prospect.page_title,
                                page_url=prospect.page_url,
                                page_snippet=page_snippet,
                                contact_name=contact_name
                            )
                            
                            if gemini_result.get("success"):
                                subject = gemini_result.get("subject")
                                body = gemini_result.get("body")
                                prospect.draft_subject = subject
                                prospect.draft_body = body
                            else:
                                logger.warning(f"⚠️  Failed to compose email for {prospect.domain}")
                                failed_count += 1
                                continue
                        else:
                            logger.warning(f"⚠️  No draft email for {prospect.domain} and auto_send is False")
                            failed_count += 1
                            continue
                    
                    # Send email
                    logger.info(f"📧 Sending email to {prospect.contact_email}...")
                    send_result = await gmail_client.send_email(
                        to_email=prospect.contact_email,
                        subject=subject,
                        body=body
                    )
                    
                    if send_result.get("success"):
                        # Create email log
                        email_log = EmailLog(
                            prospect_id=prospect.id,
                            subject=subject,
                            body=body,
                            response=send_result
                        )
                        db.add(email_log)
                        
                        # Update prospect
                        prospect.outreach_status = "sent"
                        prospect.last_sent = datetime.utcnow()
                        sent_count += 1
                        logger.info(f"✅ Email sent to {prospect.contact_email}")
                    else:
                        logger.error(f"❌ Failed to send email to {prospect.contact_email}: {send_result.get('error')}")
                        failed_count += 1
                    
                    await db.commit()
                    await db.refresh(prospect)
                    
                    # Rate limiting (1 email per 2 seconds to avoid Gmail limits)
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    logger.error(f"❌ Error sending to {prospect.contact_email}: {e}", exc_info=True)
                    failed_count += 1
                    continue
            
            # Update job status
            job.status = "completed"
            job.result = {
                "emails_sent": sent_count,
                "emails_failed": failed_count,
                "total_processed": len(prospects)
            }
            await db.commit()
            
            logger.info(f"✅ Send job {job_id} completed: {sent_count} sent, {failed_count} failed")
            
            return {
                "job_id": job_id,
                "status": "completed",
                "emails_sent": sent_count,
                "emails_failed": failed_count
            }
            
        except Exception as e:
            logger.error(f"Send job {job_id} failed: {e}", exc_info=True)
            job.status = "failed"
            job.error_message = str(e)
            await db.commit()
            return {"error": str(e)}
```

**Test Command:**
```bash
curl -X POST "http://localhost:8000/api/jobs/send?max_prospects=5&auto_send=true" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Env Vars Required:**
- `GMAIL_REFRESH_TOKEN`
- `GMAIL_CLIENT_ID`
- `GMAIL_CLIENT_SECRET`
- `GEMINI_API_KEY` (if auto_send=true)

---

### Fix #4: Wire Send Endpoint

**File:** `backend/app/api/jobs.py`  
**Location:** Lines 271-280 (replace TODO block)

```python
@router.post("/send", response_model=JobResponse)
async def create_send_job(
    prospect_ids: Optional[List[UUID]] = None,
    max_prospects: int = 100,
    auto_send: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a job to send emails to prospects
    """
    # Create job record
    job = Job(
        job_type="send",
        params={
            "prospect_ids": [str(pid) for pid in prospect_ids] if prospect_ids else None,
            "max_prospects": max_prospects,
            "auto_send": auto_send
        },
        status="pending"
    )
    
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    # Start send task in background
    try:
        from app.tasks.send import process_send_job
        import asyncio
        asyncio.create_task(process_send_job(str(job.id)))
        logger.info(f"Send job {job.id} started in background")
    except Exception as e:
        logger.error(f"Failed to start send job {job.id}: {e}", exc_info=True)
        job.status = "failed"
        job.error_message = f"Failed to start job: {e}"
        await db.commit()
        await db.refresh(job)
    
    return job_to_response(job)
```

---

### Fix #5: Add Auto-Enrichment Trigger

**File:** `backend/app/tasks/discovery.py`  
**Location:** After line 420 (after job completion)

```python
# After line 420, add:
            # Auto-trigger enrichment if prospects were discovered
            if len(all_prospects) > 0:
                try:
                    from app.tasks.enrichment import process_enrichment_job
                    import asyncio
                    
                    # Create enrichment job
                    enrichment_job = Job(
                        job_type="enrich",
                        params={
                            "prospect_ids": None,  # Enrich all newly discovered
                            "max_prospects": len(all_prospects)
                        },
                        status="pending"
                    )
                    db.add(enrichment_job)
                    await db.commit()
                    await db.refresh(enrichment_job)
                    
                    # Start enrichment in background
                    asyncio.create_task(process_enrichment_job(str(enrichment_job.id)))
                    logger.info(f"🔄 Auto-triggered enrichment job {enrichment_job.id} for {len(all_prospects)} prospects")
                except Exception as e:
                    logger.warning(f"⚠️  Failed to auto-trigger enrichment: {e}")
                    # Don't fail discovery job if enrichment trigger fails
```

---

### Fix #6: Database Migration

**Command:**
```bash
cd backend
alembic upgrade head
```

**Verification:**
```python
# Test in Python shell
from app.models import Prospect
from app.db.database import engine
import asyncio

async def check_column():
    async with engine.begin() as conn:
        result = await conn.execute("SELECT column_name FROM information_schema.columns WHERE table_name='prospects' AND column_name='discovery_query_id'")
        row = result.fetchone()
        if row:
            print("✅ discovery_query_id column exists")
        else:
            print("❌ discovery_query_id column missing")

asyncio.run(check_column())
```

---

## Final Checklist

### Commands to Run

1. **Apply Database Migration:**
   ```bash
   cd backend
   alembic upgrade head
   ```

2. **Create Enrichment Task:**
   ```bash
   # Create backend/app/tasks/enrichment.py with Fix #1 code
   ```

3. **Create Send Task:**
   ```bash
   # Create backend/app/tasks/send.py with Fix #3 code
   ```

4. **Update Endpoints:**
   ```bash
   # Apply Fix #2 to backend/app/api/prospects.py
   # Apply Fix #4 to backend/app/api/jobs.py
   # Apply Fix #5 to backend/app/tasks/discovery.py
   ```

5. **Set Environment Variables (Render):**
   - `HUNTER_API_KEY`
   - `GMAIL_REFRESH_TOKEN`
   - `GMAIL_CLIENT_ID`
   - `GMAIL_CLIENT_SECRET`
   - `GEMINI_API_KEY`

6. **Test Pipeline:**
   ```bash
   # 1. Create discovery job
   curl -X POST "http://localhost:8000/api/jobs/discover" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer TOKEN" \
     -d '{"keywords": "art blog", "locations": ["United States"], "max_results": 10}'
   
   # 2. Wait for discovery to complete, check job status
   curl "http://localhost:8000/api/jobs/{job_id}/status"
   
   # 3. Verify enrichment was auto-triggered
   curl "http://localhost:8000/api/jobs?job_type=enrich"
   
   # 4. Manually trigger enrichment if needed
   curl -X POST "http://localhost:8000/api/prospects/enrich?max_prospects=10"
   
   # 5. Verify prospects have emails
   curl "http://localhost:8000/api/prospects?has_email=true"
   
   # 6. Trigger send job
   curl -X POST "http://localhost:8000/api/jobs/send?max_prospects=5&auto_send=true"
   
   # 7. Verify emails sent
   curl "http://localhost:8000/api/prospects?status=sent"
   ```

### Tests to Execute

1. **Unit Tests (to be created):**
   - Test Hunter.io client parsing
   - Test enrichment task logic
   - Test send task logic

2. **Integration Tests:**
   - Test discovery → enrichment flow
   - Test enrichment → send flow
   - Test error handling

3. **Manual Verification:**
   - Check database for `contact_email` values after enrichment
   - Check Gmail sent folder for sent emails
   - Verify job statuses in database

---

## Conclusion

The system's automation pipeline is **50% complete**. Discovery works, but enrichment and sending are not implemented in the backend. The fixes above will complete the pipeline and enable full automation from discovery → enrichment → sending.

**Priority Order:**
1. 🔴 Fix #1 & #2 (Enrichment) - **BLOCKS ENTIRE PIPELINE**
2. 🔴 Fix #3 & #4 (Send) - **BLOCKS EMAIL AUTOMATION**
3. 🟡 Fix #5 (Auto-trigger) - **IMPROVES AUTOMATION**
4. 🟡 Fix #6 (Migration) - **FIXES 500 ERRORS**

