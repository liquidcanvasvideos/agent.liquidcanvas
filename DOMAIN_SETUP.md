# Domain Configuration Guide

## Your Domain

**Production URL:** `https://agent.liquidcanvas.art`

## Frontend Configuration

The frontend automatically detects your domain and uses it for API calls. However, you can explicitly set it:

### Option 1: Environment Variable (Recommended)

Create `frontend/.env.local`:

```env
NEXT_PUBLIC_API_BASE_URL=https://agent.liquidcanvas.art/api/v1
```

### Option 2: Auto-Detection (Default)

The frontend will automatically use:
- **Production**: `https://agent.liquidcanvas.art/api/v1` (when accessed via your domain)
- **Local**: `http://localhost:8000/api/v1` (when running locally)

## Backend Configuration

Make sure your backend CORS settings include your domain in `utils/config.py`:

```python
CORS_ORIGINS: List[str] = [
    "http://localhost:3000",
    "http://localhost:8000",
    "https://agent.liquidcanvas.art",
    "https://www.liquidcanvas.art"
]
```

## Login URL

**Production:**
```
https://agent.liquidcanvas.art/login
```

**Local Development:**
```
http://localhost:3000/login
```

## API Endpoints

All API endpoints are available at:
- **Production**: `https://agent.liquidcanvas.art/api/v1/...`
- **Local**: `http://localhost:8000/api/v1/...`

## Vercel Deployment

If deploying frontend to Vercel, set environment variable:

1. Go to Vercel Dashboard → Your Project → Settings → Environment Variables
2. Add: `NEXT_PUBLIC_API_BASE_URL` = `https://agent.liquidcanvas.art/api/v1`
3. Redeploy

## Render/Backend Deployment

If deploying backend to Render, make sure:
1. CORS origins include `https://agent.liquidcanvas.art`
2. Environment variables are set (ADMIN_USERNAME, ADMIN_PASSWORD, JWT_SECRET_KEY)
3. Backend URL is accessible at your domain (via reverse proxy or direct)

## Testing

1. **Local**: Visit `http://localhost:3000/login`
2. **Production**: Visit `https://agent.liquidcanvas.art/login`

Both should work with the same credentials!

