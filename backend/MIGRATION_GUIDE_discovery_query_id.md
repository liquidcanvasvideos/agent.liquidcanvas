# Migration Guide: Add discovery_query_id to prospects table

## Overview

This migration safely adds the `discovery_query_id` column to the `prospects` table. The column is a **UUID** (not integer) that references the `discovery_queries.id` column.

**Note:** The model uses UUID, not integer, to match the existing schema where both `prospects.id` and `discovery_queries.id` are UUIDs.

## Migration Options

### Option 1: Using Alembic (Recommended)

Run the Alembic migration:

```bash
cd backend
alembic upgrade head
```

The migration file is: `alembic/versions/556b79de2825_add_discovery_query_id_to_prospects_safe.py`

**Features:**
- ✅ Idempotent (safe to run multiple times)
- ✅ Checks if column exists before adding
- ✅ Creates index automatically
- ✅ Creates foreign key constraint if `discovery_queries` table exists
- ✅ Column is nullable (won't break existing queries)

### Option 2: Using Raw SQL

Run the SQL script directly:

```bash
psql -d your_database_name -f backend/add_discovery_query_id_column.sql
```

Or using Python:

```python
import psycopg2

conn = psycopg2.connect("your_connection_string")
with open('backend/add_discovery_query_id_column.sql', 'r') as f:
    conn.cursor().execute(f.read())
conn.commit()
```

## Column Details

- **Name:** `discovery_query_id`
- **Type:** `UUID` (PostgreSQL UUID type)
- **Nullable:** `YES` (allows NULL values)
- **Foreign Key:** References `discovery_queries.id`
- **Index:** `ix_prospects_discovery_query_id` (for fast lookups)
- **On Delete:** `SET NULL` (if discovery_query is deleted, column is set to NULL)

## Safety Features

1. **Nullable Column:** Existing queries won't break because the column allows NULL
2. **Idempotent:** Can be run multiple times safely
3. **Checks Before Adding:** Verifies column/index/constraint don't exist first
4. **No Data Loss:** All existing data remains intact

## Verification Queries

After running the migration, verify it worked:

### 1. Check Column Exists

```sql
SELECT 
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'prospects'
AND column_name = 'discovery_query_id';
```

**Expected Result:**
```
column_name          | data_type | is_nullable
---------------------+-----------+------------
discovery_query_id   | uuid      | YES
```

### 2. Check Index Exists

```sql
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'prospects'
AND indexname = 'ix_prospects_discovery_query_id';
```

### 3. Check Foreign Key Constraint

```sql
SELECT 
    tc.constraint_name,
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
AND tc.table_name = 'prospects'
AND tc.constraint_name = 'fk_prospects_discovery_query_id';
```

### 4. Test Storing a UUID Reference

```sql
-- First, get a valid discovery_query UUID
SELECT id FROM discovery_queries LIMIT 1;

-- Then update a prospect (replace with actual UUIDs)
UPDATE prospects 
SET discovery_query_id = 'your-discovery-query-uuid-here'::UUID
WHERE id = 'your-prospect-uuid-here'::UUID
AND EXISTS (
    SELECT 1 FROM discovery_queries 
    WHERE id = 'your-discovery-query-uuid-here'::UUID
)
RETURNING id, domain, discovery_query_id;
```

### 5. Count Prospects with/without Query ID

```sql
SELECT 
    COUNT(*) as total_prospects,
    COUNT(discovery_query_id) as prospects_with_query_id,
    COUNT(*) - COUNT(discovery_query_id) as prospects_without_query_id
FROM prospects;
```

### 6. Join Prospects with Discovery Queries

```sql
SELECT 
    p.id,
    p.domain,
    p.outreach_status,
    dq.keyword,
    dq.location,
    dq.status as query_status
FROM prospects p
LEFT JOIN discovery_queries dq ON p.discovery_query_id = dq.id
WHERE p.discovery_query_id IS NOT NULL
LIMIT 10;
```

## Example Usage in Application Code

### Python (SQLAlchemy)

```python
from app.models import Prospect, DiscoveryQuery

# Create a prospect with discovery_query_id
prospect = Prospect(
    domain="example.com",
    discovery_query_id=discovery_query.id  # UUID from DiscoveryQuery
)

# Query prospects by discovery_query_id
prospects = session.query(Prospect).filter(
    Prospect.discovery_query_id == query_id
).all()

# Join with discovery_query
prospects = session.query(Prospect).join(
    DiscoveryQuery
).filter(
    DiscoveryQuery.keyword == "art gallery"
).all()
```

### Raw SQL

```sql
-- Insert a prospect with discovery_query_id
INSERT INTO prospects (domain, discovery_query_id, outreach_status)
VALUES ('example.com', 'uuid-here'::UUID, 'pending');

-- Query prospects by discovery_query_id
SELECT * FROM prospects 
WHERE discovery_query_id = 'uuid-here'::UUID;

-- Join with discovery_queries
SELECT p.*, dq.keyword, dq.location
FROM prospects p
JOIN discovery_queries dq ON p.discovery_query_id = dq.id
WHERE dq.status = 'completed';
```

## Rollback

If you need to rollback the migration:

### Using Alembic

```bash
alembic downgrade -1
```

### Using SQL

```sql
-- Remove foreign key constraint
ALTER TABLE prospects 
DROP CONSTRAINT IF EXISTS fk_prospects_discovery_query_id;

-- Remove index
DROP INDEX IF EXISTS ix_prospects_discovery_query_id;

-- Remove column
ALTER TABLE prospects 
DROP COLUMN IF EXISTS discovery_query_id;
```

## Troubleshooting

### Error: "column does not exist"

If you see this error, the migration hasn't been run yet. Run one of the migration options above.

### Error: "relation discovery_queries does not exist"

The foreign key constraint requires the `discovery_queries` table to exist first. The migration will skip the foreign key creation if the table doesn't exist, but you can add it later:

```sql
ALTER TABLE prospects
ADD CONSTRAINT fk_prospects_discovery_query_id
FOREIGN KEY (discovery_query_id)
REFERENCES discovery_queries(id)
ON DELETE SET NULL;
```

### Error: "duplicate key value violates unique constraint"

This shouldn't happen with this migration, but if you see constraint errors, check that the migration ran correctly using the verification queries above.

## Notes

- The column uses **UUID**, not integer, to match the existing schema
- The column is **nullable** to ensure backward compatibility
- All existing queries will continue to work (they just won't use this column)
- New queries can optionally use this column to link prospects to discovery queries

