# 📚 How to Run Database Migrations

## What is a Migration?

A **migration** is a script that changes your database structure (adds columns, creates tables, etc.) in a safe, trackable way.

Think of it like version control for your database:
- Each migration is a "commit" that changes the database
- Alembic tracks which migrations have been applied
- You can roll back if something goes wrong

## What is "alembic upgrade head"?

**Alembic** is the tool that manages database migrations.

**`upgrade head`** means:
- `upgrade` = Apply migrations (move forward)
- `head` = Apply ALL pending migrations up to the latest one

So `alembic upgrade head` = "Apply all migrations that haven't been run yet"

## What Will Happen

When you run the migration, it will:

1. **Check current state**: "What migrations have already been applied?"
2. **Find new migrations**: "What migrations exist but haven't been run?"
3. **Apply them in order**: Run each migration's `upgrade()` function
4. **Update tracking**: Mark migrations as applied in the `alembic_version` table

For the new pipeline migration, it will:
- Add `discovery_status` column
- Add `approval_status` column
- Add `scrape_status` column
- Add `verification_status` column
- Add `draft_status` column
- Add `send_status` column
- Add metadata columns (category, location, keywords, etc.)
- Create indexes for performance

## How to Run It

### Option 1: Automatic (Recommended)

**The migration runs automatically when you start the backend!**

Your `backend/app/main.py` has this code:
```python
@app.on_event("startup")
async def startup():
    # Runs migrations automatically on server start
    command.upgrade(alembic_cfg, "head")
```

So if you:
1. Start your backend server
2. The migration will run automatically
3. Check the logs to see if it succeeded

### Option 2: Manual (If you want to run it yourself)

#### On Windows (PowerShell):
```powershell
cd C:\Users\MIKENZY\Documents\Apps\liquidcanvas\backend
alembic upgrade head
```

#### On Mac/Linux:
```bash
cd backend
alembic upgrade head
```

## What You'll See

### Success:
```
INFO  [alembic.runtime.migration] Running upgrade add_serp_intent_fields -> add_pipeline_status_fields, add pipeline status fields to prospects
✅ Migration completed successfully!
```

### If Already Applied:
```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade add_serp_intent_fields -> add_pipeline_status_fields, add pipeline status fields to prospects
✅ All migrations are up to date!
```

### If Error:
```
ERROR [alembic.runtime.migration] Migration failed: ...
```

## Verify It Worked

After running the migration, you can check:

1. **Check migration version:**
   ```sql
   SELECT * FROM alembic_version;
   ```
   Should show: `add_pipeline_status_fields`

2. **Check if columns exist:**
   ```sql
   SELECT column_name 
   FROM information_schema.columns 
   WHERE table_name = 'prospects' 
   AND column_name IN ('discovery_status', 'approval_status', 'scrape_status');
   ```
   Should return all 3 columns.

## Troubleshooting

### "Command not found: alembic"
**Solution:** Install Alembic:
```bash
pip install alembic
```

### "No module named 'alembic'"
**Solution:** Make sure you're in a virtual environment with dependencies installed:
```bash
cd backend
pip install -r requirements.txt
```

### "Migration already applied"
**This is fine!** It means the migration already ran. Your database is up to date.

### "Table already exists" or "Column already exists"
**This is also fine!** It means the columns were added manually or by a previous migration. Alembic will skip them.

## Summary

**TL;DR:**
- Migrations run **automatically** when you start the backend
- Or run manually: `cd backend && alembic upgrade head`
- It adds the new status columns to your `prospects` table
- Check logs to confirm it worked

**You don't need to do anything manually** - the backend will handle it on startup! 🚀

