# Sync Frontend to Separate Repository

## Problem

The frontend is deployed from a **separate GitHub repository** (`Jim-devENG/agent-frontend`), but we've been updating the frontend code in the **monorepo** (`Jim-devENG/agent.liquidcanvas`).

Vercel is deploying from `agent-frontend`, so it's still using old code with 404 errors.

## Solution: Copy Frontend Code to Separate Repo

### Step 1: Clone or Access the Frontend Repository

If you don't have it locally:

```bash
cd C:\Users\MIKENZY\Documents\Apps
git clone https://github.com/Jim-devENG/agent-frontend.git
cd agent-frontend
```

If you already have it:

```bash
cd path/to/agent-frontend
git pull origin main
```

### Step 2: Copy Updated Frontend Files

Copy all files from the monorepo's `frontend/` directory to the `agent-frontend` repository:

**Files to copy:**
- `app/` (entire directory)
- `components/` (entire directory)
- `lib/` (entire directory)
- `package.json`
- `tsconfig.json`
- `tailwind.config.js`
- `postcss.config.js`
- `next.config.js`
- `.gitignore` (if exists)

### Step 3: Commit and Push

```bash
cd agent-frontend
git add .
git commit -m "Update frontend to use new backend API endpoints"
git push origin main
```

### Step 4: Vercel Will Auto-Deploy

Vercel should automatically detect the push and redeploy. Check:
1. Go to https://vercel.com/dashboard
2. Find your `agent-frontend` project
3. Check "Deployments" tab for new deployment

### Step 5: Verify Environment Variable

In Vercel project settings → Environment Variables, ensure:

```
NEXT_PUBLIC_API_BASE_URL=https://agent-liquidcanvas.onrender.com/api
```

(No `/v1` at the end)

### Step 6: Clear Browser Cache

After Vercel redeploys:
- Hard refresh: `Ctrl+Shift+R` (Windows) or `Cmd+Shift+R` (Mac)
- Or use Incognito/Private mode

## Quick PowerShell Script to Copy Files

If you want to automate the copy:

```powershell
# Set paths
$monorepoFrontend = "C:\Users\MIKENZY\Documents\Apps\liquidcanvas\frontend"
$separateRepo = "C:\Users\MIKENZY\Documents\Apps\agent-frontend"

# Copy directories
Copy-Item -Path "$monorepoFrontend\app" -Destination "$separateRepo\app" -Recurse -Force
Copy-Item -Path "$monorepoFrontend\components" -Destination "$separateRepo\components" -Recurse -Force
Copy-Item -Path "$monorepoFrontend\lib" -Destination "$separateRepo\lib" -Recurse -Force

# Copy config files
Copy-Item -Path "$monorepoFrontend\package.json" -Destination "$separateRepo\package.json" -Force
Copy-Item -Path "$monorepoFrontend\tsconfig.json" -Destination "$separateRepo\tsconfig.json" -Force
Copy-Item -Path "$monorepoFrontend\tailwind.config.js" -Destination "$separateRepo\tailwind.config.js" -Force
Copy-Item -Path "$monorepoFrontend\postcss.config.js" -Destination "$separateRepo\postcss.config.js" -Force
Copy-Item -Path "$monorepoFrontend\next.config.js" -Destination "$separateRepo\next.config.js" -Force

Write-Host "Files copied! Now commit and push to agent-frontend repo."
```

## What Changed in the Frontend

The updated frontend code:
- ✅ Uses `getStats()` which calls `/api/prospects` (not `/api/stats`)
- ✅ Uses `listJobs()` which calls `/api/jobs` (not `/api/jobs/latest`)
- ✅ Removed calls to `/api/automation/status`
- ✅ Removed calls to `/api/discovery/status`
- ✅ Removed calls to `/api/discovery/locations`
- ✅ Removed calls to `/api/discovery/categories`
- ✅ Removed calls to `/api/activity`
- ✅ Added authentication endpoint `/api/auth/login`

## After Syncing

Once you push to `agent-frontend` and Vercel redeploys:
- ✅ 404 errors will stop
- ✅ Frontend will connect to new backend
- ✅ All features will work correctly

