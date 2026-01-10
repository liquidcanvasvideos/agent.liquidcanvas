# Verify Render PostgreSQL Setup - Step by Step

## ✅ Step 1: Verify DATABASE_URL Format

Make sure your `DATABASE_URL` in Render environment variables:

1. **Starts with `postgresql+asyncpg://`** (NOT just `postgresql://`)
   - ✅ Correct: `postgresql+asyncpg://postgres:password@dpg-xxxxx-a.oregon-postgres.render.com:5432/postgres`
   - ❌ Wrong: `postgresql://postgres:password@dpg-xxxxx-a.oregon-postgres.render.com:5432/postgres`

2. **If it starts with `postgresql://`, convert it:**
   - Just change `postgresql://` to `postgresql+asyncpg://`
   - Keep everything else the same

---

## ✅ Step 2: Check Backend Deployment

1. **Go to your backend service on Render**
2. **Check the "Events" or "Logs" tab**
3. **Wait for deployment to complete** (should show "Live" status)
4. **Check logs for:**
   ```
   ✅ Async engine created successfully
   ✅ Configured SSL for Supabase connection
   🔗 Attempting to connect to: dpg-xxxxx-a.oregon-postgres.render.com:5432
   ```

   **Note:** Render PostgreSQL doesn't need SSL, so you might see different messages. That's OK!

---

## ✅ Step 3: Run Database Migrations

After your backend redeploys, you need to create the database schema:

### Option A: Use Render Shell (Easiest)

1. **Go to your backend service on Render**
2. **Click "Shell" tab** (or look for "Open Shell" in Logs)
3. **Wait for shell to connect** (may take 10-20 seconds)
4. **Run migrations:**
   ```bash
   cd backend
   alembic upgrade head
   ```
5. **Verify migrations ran:**
   ```bash
   alembic current
   ```
   Should show your latest migration revision number

### Option B: Check if Migrations Run Automatically

If you have `AUTO_MIGRATE=true` set, migrations might run automatically. Check logs for:
```
🔄 Running database migrations on startup...
✅ Database migrations completed successfully
```

---

## ✅ Step 4: Test Database Connection

### Check Health Endpoint

1. **Visit:** `https://agent-liquidcanvas.onrender.com/health/ready`
2. **Should return:**
   ```json
   {
     "status": "ready",
     "database": "connected"
   }
   ```

### Check Logs for Errors

Look for any errors like:
- ❌ `could not connect to server`
- ❌ `password authentication failed`
- ❌ `database does not exist`
- ❌ `relation does not exist` (means migrations haven't run yet)

---

## ✅ Step 5: Verify Tables Were Created

If migrations ran successfully, check that tables exist:

1. **Go to Render PostgreSQL dashboard**
2. **Click on your database**
3. **Go to "Connections" tab** (or use SQL editor if available)
4. **Or use Render Shell to check:**
   ```bash
   # In backend shell
   python -c "from app.db.database import get_engine; import asyncio; from sqlalchemy import text; asyncio.run(async def(): engine = get_engine(); async with engine.begin() as conn: result = await conn.execute(text(\"SELECT tablename FROM pg_tables WHERE schemaname='public'\")); print([row[0] for row in result]))()"
   ```

---

## Common Issues and Fixes

### Issue 1: "postgresql://" instead of "postgresql+asyncpg://"

**Fix:**
- Go to Environment variables
- Edit `DATABASE_URL`
- Change `postgresql://` to `postgresql+asyncpg://`
- Save and redeploy

### Issue 2: "Database does not exist"

**Fix:**
- Check database name in connection string matches actual database name
- Render usually uses `postgres` as default database name
- Verify in Render PostgreSQL dashboard

### Issue 3: "Password authentication failed"

**Fix:**
- Check password in connection string is correct
- Copy connection string again from Render dashboard
- Make sure no extra spaces or characters

### Issue 4: "relation does not exist" (tables missing)

**Fix:**
- Migrations haven't run yet
- Run: `alembic upgrade head` in Render Shell
- Or check if AUTO_MIGRATE is enabled

### Issue 5: "Connection timeout" or "Network unreachable"

**Fix:**
- Verify you're using **Internal Database URL** (not External)
- Check backend and database are in **same region**
- Internal URL should have `dpg-xxxxx-a.region-postgres.render.com` format

---

## Quick Verification Checklist

- [ ] `DATABASE_URL` starts with `postgresql+asyncpg://`
- [ ] Backend service redeployed successfully
- [ ] No connection errors in logs
- [ ] Ran migrations: `alembic upgrade head`
- [ ] Migrations completed without errors
- [ ] Health endpoint returns `{"database":"connected"}`
- [ ] Tables exist in database

---

## Next Steps After Verification

Once everything is working:

1. ✅ **Test your API endpoints** that query the database
2. ✅ **Import any initial data** if needed
3. ✅ **Set up any seed data** (admin users, default settings, etc.)
4. ✅ **Monitor logs** for any issues

---

**After you redeploy, check the logs and let me know:**
1. Does it show "Async engine created successfully"?
2. Any connection errors?
3. Have you run migrations yet?

Let me know what you see in the logs! 🚀

