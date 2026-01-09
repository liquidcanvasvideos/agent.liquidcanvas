# Supabase Migration Guide

This guide will help you migrate your backend from Render PostgreSQL to Supabase.

## Prerequisites

1. **Supabase Account**: Sign up at https://supabase.com
2. **Supabase Project**: Create a new project (or use existing)
3. **Backend Repository**: Already connected to `liquidcanvasvideos/agent.liquidcanvas`

## Step 1: Create Supabase Project

1. Go to https://supabase.com/dashboard
2. Click **"New Project"**
3. Fill in:
   - **Name**: `liquid-canvas-agent` (or your preferred name)
   - **Database Password**: Create a strong password (save it!)
   - **Region**: Choose closest to your users
   - **Pricing Plan**: Free tier is fine to start
4. Click **"Create new project"**
5. Wait 2-3 minutes for project to be ready

## Step 2: Get Supabase Connection Details

Once your project is ready:

1. Go to **Project Settings** → **Database**
2. Find **"Connection string"** section
3. Copy the **"URI"** connection string (looks like: `postgresql://postgres:[YOUR-PASSWORD]@db.xxxxx.supabase.co:5432/postgres`)
4. Also note:
   - **Host**: `db.xxxxx.supabase.co`
   - **Port**: `5432` (usually)
   - **Database**: `postgres`
   - **User**: `postgres`
   - **Password**: The one you created

### For API Access (Optional - for Supabase Auth):

1. Go to **Project Settings** → **API**
2. Copy:
   - **Project URL**: `https://xxxxx.supabase.co`
   - **anon/public key**: `eyJhbGc...` (starts with `eyJ`)
   - **service_role key**: `eyJhbGc...` (keep this secret!)

## Step 3: Update Environment Variables

### Option A: Update Render Environment Variables

If your backend is still on Render:

1. Go to Render Dashboard → Your Backend Service
2. Navigate to **Environment** tab
3. Update `DATABASE_URL`:
   ```
   postgresql://postgres:[YOUR-PASSWORD]@db.xxxxx.supabase.co:5432/postgres
   ```
   Replace `[YOUR-PASSWORD]` with your actual Supabase database password.

4. (Optional) If using Supabase Auth, add:
   ```
   SUPABASE_URL=https://xxxxx.supabase.co
   SUPABASE_SERVICE_ROLE_KEY=eyJhbGc... (service_role key)
   SUPABASE_ANON_KEY=eyJhbGc... (anon key)
   ```

5. Click **"Save Changes"**
6. Render will automatically redeploy

### Option B: Update Local .env File

For local development:

```bash
# In backend/.env
DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.xxxxx.supabase.co:5432/postgres

# Optional: Supabase Auth
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGc...
SUPABASE_ANON_KEY=eyJhbGc...
```

## Step 4: Run Database Migrations

The existing Alembic migrations will work with Supabase since it's PostgreSQL-compatible.

### On Render (Automatic):

If `AUTO_MIGRATE=true` or smart auto-migrate is enabled, migrations will run automatically on startup.

### Manual Migration:

```bash
cd backend
alembic upgrade head
```

This will create all your tables in Supabase.

## Step 5: Verify Connection

1. **Check Backend Logs**:
   - Render: Go to your service → Logs
   - Look for: `✅ Database connectivity verified`
   - Should see: `Attempting to connect to database at: db.xxxxx.supabase.co:5432`

2. **Test API Endpoint**:
   ```bash
   curl https://your-backend-url/api/health
   ```
   Should return `{"status": "healthy", "database": "connected"}`

3. **Check Supabase Dashboard**:
   - Go to **Table Editor** in Supabase
   - You should see all your tables: `prospects`, `jobs`, `email_logs`, etc.

## Step 6: (Optional) Enable Supabase Auth

If you want to use Supabase Authentication instead of custom JWT:

1. **Update Backend Code**:
   In `backend/app/main.py`, change:
   ```python
   # FROM:
   from app.api import auth
   app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
   
   # TO:
   from app.api import auth_supabase
   app.include_router(auth_supabase.router, prefix="/api/auth", tags=["auth"])
   ```

2. **Set Environment Variables** (already done in Step 3)

3. **Update Frontend**:
   - Install Supabase JS client: `npm install @supabase/supabase-js`
   - Update authentication code to use Supabase client

## Step 7: Data Migration (If Needed)

If you have existing data in Render PostgreSQL:

### Option A: pg_dump and pg_restore

```bash
# Export from Render
pg_dump -h [render-host] -U [user] -d [database] > backup.sql

# Import to Supabase
psql -h db.xxxxx.supabase.co -U postgres -d postgres < backup.sql
```

### Option B: Supabase Dashboard

1. Go to **Database** → **Backups** in Supabase
2. Use **"Restore from backup"** if you have a backup file

## Connection String Format

Supabase provides connection strings in this format:
```
postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
```

The backend code automatically converts this to:
```
postgresql+asyncpg://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
```

So you can use the Supabase connection string directly - no code changes needed!

## Troubleshooting

### Connection Refused

- **Check password**: Make sure password is correct (no extra spaces)
- **Check host**: Verify the host is `db.xxxxx.supabase.co` (not `xxxxx.supabase.co`)
- **Check firewall**: Supabase allows connections from anywhere by default

### SSL Required

If you get SSL errors, add `?sslmode=require` to connection string:
```
postgresql://postgres:[PASSWORD]@db.xxxxx.supabase.co:5432/postgres?sslmode=require
```

### Migration Errors

- **Check Alembic version**: Run `alembic current` to see current migration
- **Check logs**: Look for specific error messages
- **Reset if needed**: `alembic downgrade base` then `alembic upgrade head` (⚠️ deletes data!)

## Benefits of Supabase

1. **Free Tier**: 500MB database, 2GB bandwidth
2. **Automatic Backups**: Daily backups included
3. **Real-time**: Can enable real-time subscriptions
4. **Auth Built-in**: Optional Supabase Auth integration
5. **Dashboard**: Nice UI for viewing data
6. **API**: REST and GraphQL APIs auto-generated

## Next Steps

1. ✅ Create Supabase project
2. ✅ Update `DATABASE_URL` environment variable
3. ✅ Run migrations
4. ✅ Verify connection
5. ✅ (Optional) Enable Supabase Auth
6. ✅ Test all API endpoints

Your backend will now use Supabase as the database! 🎉

