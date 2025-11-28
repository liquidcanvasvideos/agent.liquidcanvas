# Render Python Build Settings

## Quick Setup for Backend Service

Since you're using **Python build** (not Docker), here are the exact settings:

### Build & Deploy Settings

1. **Environment**: `Python 3`
2. **Build Command**: `pip install -r requirements.txt`
3. **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. **Root Directory**: `backend` (if deploying from monorepo)

### Environment Variables

Make sure these are set in Render:

- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `HUNTER_API_KEY` - Hunter.io API key
- `DATAFORSEO_LOGIN` - DataForSEO username
- `DATAFORSEO_PASSWORD` - DataForSEO password
- `GEMINI_API_KEY` - Google Gemini API key
- `GMAIL_CLIENT_ID` - Gmail OAuth client ID
- `GMAIL_CLIENT_SECRET` - Gmail OAuth client secret
- `GMAIL_REFRESH_TOKEN` - Gmail OAuth refresh token
- `PORT` - Automatically set by Render (usually 10000)

### Important Notes

✅ **Worker imports are now optional** - Backend will start even if worker code isn't available  
⚠️ **Worker service must run separately** - Jobs will fail gracefully if worker isn't running  
✅ **Database migrations run on startup** - No pre-deploy command needed (free tier compatible)

### After Deployment

1. Backend should start successfully
2. Check `/health` endpoint to verify
3. Deploy worker service separately (if needed)
4. Ensure Redis and PostgreSQL are running

