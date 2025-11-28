# Render Free Tier Setup (No Pre-Deploy Command)

## Overview

Since pre-deploy commands are a paid feature, we'll run database migrations on startup instead.

## ✅ Solution: Migrations on Startup

The backend now automatically runs migrations when it starts up. This works for the free tier!

## Settings Configuration

### Build & Deploy Settings

**Dockerfile Path:**
- Set to: `backend/Dockerfile`

**Docker Build Context Directory:**
- Set to: `backend`

**Pre-Deploy Command:**
- Leave empty (not available on free tier)

**Docker Command:**
- Leave empty (uses Dockerfile CMD)

### Environment Variables

Add all required environment variables in the **Environment** tab:

```
DATABASE_URL=postgresql://user:pass@host:port/dbname
REDIS_URL=redis://host:port
DATAFORSEO_LOGIN=your_email@example.com
DATAFORSEO_PASSWORD=your_password
HUNTER_IO_API_KEY=your_api_key
GEMINI_API_KEY=your_api_key
GMAIL_REFRESH_TOKEN=your_refresh_token
GMAIL_CLIENT_ID=your_client_id
GMAIL_CLIENT_SECRET=your_client_secret
JWT_SECRET_KEY=<generate secure random string>
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<secure password>
CORS_ORIGINS=https://agent.liquidcanvas.art,https://www.liquidcanvas.art
```

## How It Works

1. **On Startup**: Backend automatically runs `alembic upgrade head`
2. **First Deploy**: If migrations fail (database doesn't exist), it creates tables directly
3. **Subsequent Deploys**: Migrations run automatically

## Manual Migration (If Needed)

If you need to run migrations manually:

1. Go to **Render Dashboard** → **Backend Service** → **Shell** tab
2. Run:
   ```bash
   cd backend
   alembic upgrade head
   ```

## Verification

After first deploy:

1. Check logs for: `✅ Database migrations completed successfully`
2. Or: `✅ Created database tables directly`
3. Visit: `https://agent-liquidcanvas.onrender.com/docs`
4. Should see FastAPI Swagger UI

## Troubleshooting

### Migrations Fail on Startup

**First Deploy:**
- This is normal if database doesn't exist yet
- Backend will create tables directly as fallback
- Check logs for confirmation

**Subsequent Deploys:**
- Migrations should run automatically
- If they fail, run manually via Shell

### Database Connection Errors

- Verify `DATABASE_URL` is correct
- Check PostgreSQL service is running
- Ensure database exists

### Tables Not Created

- Check backend logs for errors
- Run migrations manually via Shell
- Or wait for next deploy (migrations run on startup)

## Alternative: Manual First Migration

If you prefer to run migrations manually first:

1. Deploy backend (without migrations)
2. Go to Shell tab
3. Run: `cd backend && alembic upgrade head`
4. Restart service

But the automatic startup migration should handle this!

