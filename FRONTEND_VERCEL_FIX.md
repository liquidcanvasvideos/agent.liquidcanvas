# Fix Vercel Next.js Detection Error

## Problem
Vercel can't detect Next.js even though `package.json` has `next` as a dependency.

## Root Cause
The `agent-frontend` repository is being deployed, and Vercel needs to know where the Next.js app is located.

## Solution Options

### Option 1: Set Root Directory in Vercel Dashboard (RECOMMENDED)

1. Go to https://vercel.com
2. Open your project (agent-frontend)
3. Go to **Settings** → **General**
4. Find **Root Directory**
5. Set it to: `frontend`
6. Click **Save**
7. Trigger a new deployment

This tells Vercel to treat the `frontend/` directory as the root of your Next.js app.

### Option 2: Update vercel.json in agent-frontend repo

If the `agent-frontend` repo has a `frontend/` subdirectory structure, ensure `vercel.json` is in the root of that repo with:

```json
{
  "buildCommand": "cd frontend && npm ci && npm run build",
  "outputDirectory": "frontend/.next",
  "installCommand": "cd frontend && npm ci",
  "framework": "nextjs"
}
```

**Note:** Remove `rootDirectory` if it exists - it's not a valid property.

### Option 3: If agent-frontend root IS the frontend

If the `agent-frontend` repository root already contains the `package.json` with Next.js (not in a `frontend/` subdirectory), then:

1. Set Root Directory in Vercel to: `/` (root)
2. Update `vercel.json` to:
```json
{
  "buildCommand": "npm ci && npm run build",
  "outputDirectory": ".next",
  "installCommand": "npm ci",
  "framework": "nextjs"
}
```

## Verify

After fixing, the build should:
- ✅ Detect Next.js automatically
- ✅ Run `npm ci` in the correct directory
- ✅ Build successfully

