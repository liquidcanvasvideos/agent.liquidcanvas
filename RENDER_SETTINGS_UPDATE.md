# Render Settings Update - Quick Fix

## Current Error
```
error: failed to read dockerfile: open Dockerfile: no such file or directory
```

## Solution: Update Render Settings

### Option 1: Use Docker (After Dockerfile is Pushed)

1. **Dockerfile Path**: Set to `backend/Dockerfile`
2. **Docker Build Context Directory**: Set to `backend`
3. **Pre-Deploy Command**: Leave empty (free tier)
4. Deploy after code is pushed

### Option 2: Switch to Python Build (Easier, Recommended)

Since you're on free tier, Python build is simpler:

1. Go to **Settings** → **Build & Deploy**
2. Change **Environment** from "Docker" to **"Python 3"**
3. **Build Command**: `pip install -r requirements.txt`
4. **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. **Clear/Remove**:
   - Dockerfile Path (leave empty)
   - Docker Build Context Directory (leave empty)
6. Click **Save Changes**
7. Go to **Manual Deploy** → **Deploy latest commit**

## Recommended: Python Build

For free tier, Python build is:
- ✅ Simpler
- ✅ Faster builds
- ✅ No Docker complexity
- ✅ Works perfectly for FastAPI

## After Update

Once you switch to Python build and deploy, the backend should start successfully!

