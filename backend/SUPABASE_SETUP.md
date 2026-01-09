# Quick Supabase Setup Checklist

## 1. Create Supabase Project
- [ ] Go to https://supabase.com/dashboard
- [ ] Create new project
- [ ] Save database password

## 2. Get Connection String
- [ ] Go to Project Settings → Database
- [ ] Copy "URI" connection string
- [ ] Format: `postgresql://postgres:[PASSWORD]@db.xxxxx.supabase.co:5432/postgres`

## 3. Update Environment Variables

### On Render:
- [ ] Go to Render Dashboard → Your Service → Environment
- [ ] Update `DATABASE_URL` with Supabase connection string
- [ ] Save and redeploy

### Local Development:
- [ ] Update `backend/.env`:
  ```
  DATABASE_URL=postgresql://postgres:[PASSWORD]@db.xxxxx.supabase.co:5432/postgres
  ```

## 4. Run Migrations
- [ ] Migrations will run automatically if `AUTO_MIGRATE=true`
- [ ] Or run manually: `cd backend && alembic upgrade head`

## 5. Verify
- [ ] Check backend logs for "Database connectivity verified"
- [ ] Check Supabase Table Editor - should see your tables
- [ ] Test API: `curl https://your-backend/api/health`

## That's It! ✅

Your backend is now connected to Supabase. No code changes needed - the existing code works with Supabase's PostgreSQL connection string.

