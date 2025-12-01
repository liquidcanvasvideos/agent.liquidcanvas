-- ============================================================================
-- Safe Migration: Add discovery_query_id column to prospects table
-- ============================================================================
-- This script safely adds the discovery_query_id column to the prospects table.
-- It checks if the column exists before adding it, making it idempotent.
-- The column is nullable to ensure existing queries continue to work.
-- ============================================================================

-- Step 1: Check if column exists, and add it if it doesn't
DO $$
BEGIN
    -- Check if column already exists
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'prospects' 
        AND column_name = 'discovery_query_id'
    ) THEN
        -- Add the column as nullable (safe for existing data)
        ALTER TABLE prospects 
        ADD COLUMN discovery_query_id UUID;
        
        RAISE NOTICE '✅ Added discovery_query_id column to prospects table';
    ELSE
        RAISE NOTICE 'ℹ️  Column discovery_query_id already exists, skipping';
    END IF;
END $$;

-- Step 2: Create index if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM pg_indexes 
        WHERE tablename = 'prospects' 
        AND indexname = 'ix_prospects_discovery_query_id'
    ) THEN
        CREATE INDEX ix_prospects_discovery_query_id 
        ON prospects(discovery_query_id);
        
        RAISE NOTICE '✅ Created index on discovery_query_id';
    ELSE
        RAISE NOTICE 'ℹ️  Index ix_prospects_discovery_query_id already exists, skipping';
    END IF;
END $$;

-- Step 3: Add foreign key constraint if discovery_queries table exists
DO $$
BEGIN
    -- Check if discovery_queries table exists
    IF EXISTS (
        SELECT 1 
        FROM information_schema.tables 
        WHERE table_name = 'discovery_queries'
    ) THEN
        -- Check if foreign key constraint doesn't exist
        IF NOT EXISTS (
            SELECT 1 
            FROM information_schema.table_constraints 
            WHERE constraint_name = 'fk_prospects_discovery_query_id'
            AND table_name = 'prospects'
        ) THEN
            ALTER TABLE prospects
            ADD CONSTRAINT fk_prospects_discovery_query_id
            FOREIGN KEY (discovery_query_id)
            REFERENCES discovery_queries(id)
            ON DELETE SET NULL;  -- If discovery_query is deleted, set to NULL
            
            RAISE NOTICE '✅ Created foreign key constraint';
        ELSE
            RAISE NOTICE 'ℹ️  Foreign key constraint already exists, skipping';
        END IF;
    ELSE
        RAISE NOTICE '⚠️  discovery_queries table does not exist, skipping foreign key creation';
    END IF;
END $$;

-- ============================================================================
-- Verification Queries
-- ============================================================================

-- Query 1: Verify column exists and check its properties
SELECT 
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'prospects'
AND column_name = 'discovery_query_id';

-- Query 2: Verify index exists
SELECT 
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'prospects'
AND indexname = 'ix_prospects_discovery_query_id';

-- Query 3: Verify foreign key constraint exists (if discovery_queries table exists)
SELECT 
    tc.constraint_name,
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
AND tc.table_name = 'prospects'
AND tc.constraint_name = 'fk_prospects_discovery_query_id';

-- Query 4: Test inserting/updating with a UUID reference (example)
-- This query shows how to use the column with a UUID reference
-- Replace '00000000-0000-0000-0000-000000000000' with an actual discovery_query UUID
/*
UPDATE prospects 
SET discovery_query_id = '00000000-0000-0000-0000-000000000000'::UUID
WHERE id = 'your-prospect-id-here'::UUID
AND EXISTS (
    SELECT 1 FROM discovery_queries 
    WHERE id = '00000000-0000-0000-0000-000000000000'::UUID
);
*/

-- Query 5: Count prospects with and without discovery_query_id
SELECT 
    COUNT(*) as total_prospects,
    COUNT(discovery_query_id) as prospects_with_query_id,
    COUNT(*) - COUNT(discovery_query_id) as prospects_without_query_id
FROM prospects;

-- Query 6: Example query joining prospects with discovery_queries
/*
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
*/

