# Exact Connection String for Your Supabase Pooler

## Your Project Details
- **Project Ref**: `wlsbtxwbyqdagvrbkebl` (from your hostname)
- **Hostname**: `db.wlsbtxwbyqdagvrbkebl.supabase.co`
- **Password**: `L1qu!dcvnvs` (URL-encoded: `L1qu%21dcvnvs`)
- **Database**: `postgres`
- **Username**: `postgres`

## ✅ Connection String for Connection Pooler (Port 6543)

Since you're using the **Shared Pooler**, use this connection string format:

```
postgresql+asyncpg://postgres:L1qu%21dcvnvs@db.wlsbtxwbyqdagvrbkebl.supabase.co:6543/postgres?pgbouncer=true
```

**Key Points:**
- ✅ Port: `6543` (Connection Pooler - supports IPv4)
- ✅ Hostname: Same as your direct connection (`db.wlsbtxwbyqdagvrbkebl.supabase.co`)
- ✅ Add `?pgbouncer=true` parameter to indicate pooler mode
- ✅ Keep `+asyncpg` for async SQLAlchemy
- ✅ Password is URL-encoded: `!` becomes `%21`

---

## Alternative: If Supabase Shows Different Hostname

Sometimes Supabase uses a different hostname for the pooler. Check if there's a connection string shown in your dashboard that looks like:

```
postgresql://postgres.[something]@aws-0-[region].pooler.supabase.com:6543/postgres
```

If you see that format, use it but:
1. Add `+asyncpg` after `postgresql`
2. Replace `[password]` with your URL-encoded password: `L1qu%21dcvnvs`
3. The username might be `postgres.wlsbtxwbyqdagvrbkebl` instead of just `postgres`

---

## How to Use This on Render

1. **Go to Render Dashboard**: https://dashboard.render.com
2. **Click your backend service**
3. **Go to "Environment" tab**
4. **Find `DATABASE_URL` and click "Edit"**
5. **Replace the entire value with:**
   ```
   postgresql+asyncpg://postgres:L1qu%21dcvnvs@db.wlsbtxwbyqdagvrbkebl.supabase.co:6543/postgres?pgbouncer=true
   ```
6. **Click "Save Changes"**
7. **Delete `SUPABASE_IPV4` variable** (if it exists) - it's not needed
8. **Wait for redeploy** (2-5 minutes)

---

## Verify It's Working

After deployment, check Render logs for:
```
✅ Configured SSL for Supabase connection
✅ Async engine created successfully
✅ Database connection test passed
```

Test the API:
```
https://agent-liquidcanvas.onrender.com/health
```

Should return: `{"status":"ready","database":"connected"}`

---

## Why This Works

- **Port 5432** (direct): IPv6 only → ❌ Fails on Render
- **Port 6543** (pooler): Supports IPv4 → ✅ Works on Render

The connection pooler acts as a proxy that can accept IPv4 connections from Render and forward them to your database over IPv6 internally.

