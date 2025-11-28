# Complete Guide: Adding API Keys to Render

This guide will walk you through adding all required API keys to your Render backend service.

## Prerequisites

- ✅ Render account (free tier works)
- ✅ Backend service already deployed on Render
- ✅ API keys/credentials for each service (see below)

## Step-by-Step Instructions

### Step 1: Access Your Render Dashboard

1. Go to **https://dashboard.render.com**
2. Sign in to your account
3. Find your backend service (usually named something like `agent-backend` or `agent-liquidcanvas`)

### Step 2: Navigate to Environment Variables

1. Click on your **backend service** to open it
2. In the left sidebar, click **"Environment"**
3. You'll see a list of current environment variables (if any)

### Step 3: Add Each API Key

Click **"Add Environment Variable"** for each key below. For each one:
- Enter the **Key** (exactly as shown)
- Enter the **Value** (your actual API key/credential)
- Click **"Save Changes"**

---

## Required API Keys

### 1. Hunter.io API Key

**Key:** `HUNTER_IO_API_KEY`  
**Value:** Your Hunter.io API key (e.g., `ba71410fc6c6dcec6df42333e933a40bdf2fa1cb`)

**How to get it:**
1. Go to https://hunter.io
2. Sign in to your account
3. Go to Settings → API
4. Copy your API key

---

### 2. DataForSEO Credentials

**Key 1:** `DATAFORSEO_LOGIN`  
**Value:** Your DataForSEO email/login (e.g., `jeremiah@liquidcanvas.art`)

**Key 2:** `DATAFORSEO_PASSWORD`  
**Value:** Your DataForSEO password/token (e.g., `b85d55cf567939e7`)

**How to get it:**
1. Go to https://dataforseo.com
2. Sign in to your account
3. Go to API → Credentials
4. Copy your login and password

**Note:** You already have these: `jeremiah@liquidcanvas.art:b85d55cf567939e7`

---

### 3. Google Gemini API Key

**Key:** `GEMINI_API_KEY`  
**Value:** Your Google Gemini API key

**How to get it:**
1. Go to https://aistudio.google.com/app/apikey
2. Sign in with your Google account
3. Click "Create API Key"
4. Copy the generated key

---

### 4. Gmail API Credentials

You need **three** environment variables for Gmail:

**Key 1:** `GMAIL_CLIENT_ID`  
**Value:** Your Gmail OAuth 2.0 Client ID

**Key 2:** `GMAIL_CLIENT_SECRET`  
**Value:** Your Gmail OAuth 2.0 Client Secret

**Key 3:** `GMAIL_REFRESH_TOKEN`  
**Value:** Your Gmail OAuth 2.0 Refresh Token

**How to get them:**
1. Go to https://console.cloud.google.com
2. Create a new project (or select existing)
3. Enable Gmail API:
   - Go to "APIs & Services" → "Library"
   - Search for "Gmail API"
   - Click "Enable"
4. Create OAuth 2.0 credentials:
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "OAuth client ID"
   - Choose "Desktop app" or "Web application"
   - Copy the Client ID and Client Secret
5. Get Refresh Token:
   - Use Google's OAuth 2.0 Playground: https://developers.google.com/oauthplayground
   - Select Gmail API scopes (e.g., `https://www.googleapis.com/auth/gmail.send`)
   - Authorize and get the refresh token

**Quick Setup Script:**
If you need help generating Gmail credentials, I can create a script to help you.

---

### 5. Authentication Credentials (Optional - for login)

**Key 1:** `ADMIN_USERNAME`  
**Value:** Your admin username (e.g., `admin`)

**Key 2:** `ADMIN_PASSWORD`  
**Value:** Your admin password (use a strong password!)

**Key 3:** `JWT_SECRET_KEY`  
**Value:** A random secret string for JWT tokens (e.g., generate with: `openssl rand -hex 32`)

**Note:** If these aren't set, defaults are used (not recommended for production).

---

### 6. Database and Redis (Already Configured)

These should already be set by Render if you're using Render's PostgreSQL and Redis services:

- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string

---

## Complete List of All Environment Variables

Copy this checklist and check off each one as you add it:

```
✅ HUNTER_IO_API_KEY=ba71410fc6c6dcec6df42333e933a40bdf2fa1cb
✅ DATAFORSEO_LOGIN=jeremiah@liquidcanvas.art
✅ DATAFORSEO_PASSWORD=b85d55cf567939e7
⏳ GEMINI_API_KEY=your_gemini_key_here
⏳ GMAIL_CLIENT_ID=your_gmail_client_id
⏳ GMAIL_CLIENT_SECRET=your_gmail_client_secret
⏳ GMAIL_REFRESH_TOKEN=your_gmail_refresh_token
⏳ ADMIN_USERNAME=admin (or your preferred username)
⏳ ADMIN_PASSWORD=your_secure_password
⏳ JWT_SECRET_KEY=your_random_secret_key
✅ DATABASE_URL=postgresql://... (auto-set by Render)
✅ REDIS_URL=redis://... (auto-set by Render)
```

---

## After Adding All Keys

### Step 4: Redeploy Your Service

After adding all environment variables:

1. Go to your service's **"Manual Deploy"** section
2. Click **"Deploy latest commit"** or **"Redeploy"**
3. Wait for deployment to complete (usually 2-5 minutes)

**Why?** Environment variable changes require a service restart to take effect.

---

## Step 5: Verify Keys Are Working

1. Go to your app: `https://agent.liquidcanvas.art/settings`
2. You should see all services listed
3. Click **"Test Connection"** on each service to verify:
   - ✅ Hunter.io
   - ✅ DataForSEO
   - ✅ Google Gemini
   - ✅ Gmail API

If a test fails, check:
- The key is correctly copied (no extra spaces)
- The key hasn't expired
- The service account has proper permissions

---

## Troubleshooting

### "Not Configured" Status

**Problem:** Service shows "Not Configured"  
**Solution:**
1. Double-check the environment variable name (must match exactly)
2. Ensure there are no extra spaces in the value
3. Redeploy the service after adding variables

### "Test Failed" Status

**Problem:** Service shows "Error" when testing  
**Solution:**
1. Verify the API key is valid and active
2. Check if the API key has the required permissions/scopes
3. For Gmail: Ensure OAuth scopes include `gmail.send`
4. Check Render logs for detailed error messages

### Service Not Appearing

**Problem:** A service doesn't show up in settings  
**Solution:**
1. Ensure the backend has been redeployed after adding the key
2. Check that the environment variable name is correct
3. Hard refresh the browser (Ctrl+Shift+R)

---

## Security Best Practices

1. **Never commit API keys to Git** - They're in `.gitignore`
2. **Use strong passwords** - For `ADMIN_PASSWORD` and `JWT_SECRET_KEY`
3. **Rotate keys regularly** - Especially if you suspect a breach
4. **Limit API key permissions** - Only grant necessary scopes/permissions
5. **Monitor usage** - Check API dashboards for unusual activity

---

## Quick Reference: Render Dashboard Path

```
Render Dashboard
  → Your Backend Service
    → Environment (left sidebar)
      → Add Environment Variable
        → Enter Key
        → Enter Value
        → Save Changes
      → Repeat for each key
    → Manual Deploy
      → Deploy latest commit
```

---

## Need Help?

If you encounter issues:
1. Check the Settings page in your app for specific error messages
2. Check Render logs: Service → Logs tab
3. Test each API key individually using the "Test Connection" button

---

## Next Steps After Setup

Once all keys are added and tested:
1. ✅ All services show "Connected" status
2. ✅ You can test discovery jobs
3. ✅ You can test email composition
4. ✅ You can send test emails
5. ✅ Full automation is ready to use

