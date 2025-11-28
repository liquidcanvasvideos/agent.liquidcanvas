# Gmail OAuth 2.0 Setup Guide

This guide will help you set up Gmail API credentials for sending emails.

## Step 1: Create Google Cloud Project

1. Go to **https://console.cloud.google.com**
2. Click **"Select a project"** → **"New Project"**
3. Enter project name: `Art Outreach Automation` (or any name)
4. Click **"Create"**
5. Wait for project creation, then select it

## Step 2: Enable Gmail API

1. In Google Cloud Console, go to **"APIs & Services"** → **"Library"**
2. Search for **"Gmail API"**
3. Click on **"Gmail API"**
4. Click **"Enable"**
5. Wait for it to enable

## Step 3: Create OAuth 2.0 Credentials

1. Go to **"APIs & Services"** → **"Credentials"**
2. Click **"Create Credentials"** → **"OAuth client ID"**
3. If prompted, configure OAuth consent screen:
   - User Type: **External** (or Internal if you have Google Workspace)
   - App name: `Art Outreach Automation`
   - User support email: Your email
   - Developer contact: Your email
   - Click **"Save and Continue"**
   - Scopes: Click **"Add or Remove Scopes"**
     - Search for and add: `https://www.googleapis.com/auth/gmail.send`
     - Click **"Update"** → **"Save and Continue"**
   - Test users: Add your email address
   - Click **"Save and Continue"** → **"Back to Dashboard"**
4. Create OAuth Client ID:
   - Application type: **"Web application"**
   - Name: `Art Outreach Gmail Client`
   - Authorized redirect URIs: Add `https://developers.google.com/oauthplayground`
   - Click **"Create"**
5. **Copy the Client ID and Client Secret** - You'll need these!

## Step 4: Get Refresh Token

1. Go to **https://developers.google.com/oauthplayground**
2. Click the **gear icon** (⚙️) in top right
3. Check **"Use your own OAuth credentials"**
4. Enter your **Client ID** and **Client Secret** from Step 3
5. In the left panel, find **"Gmail API v1"**
6. Expand it and check: **`https://www.googleapis.com/auth/gmail.send`**
7. Click **"Authorize APIs"**
8. Sign in with the Gmail account you want to use
9. Click **"Allow"** to grant permissions
10. In the right panel, click **"Exchange authorization code for tokens"**
11. **Copy the "Refresh token"** - This is what you need!

## Step 5: Add to Render

Add these three environment variables to your Render backend:

1. **`GMAIL_CLIENT_ID`** = Your Client ID from Step 3
2. **`GMAIL_CLIENT_SECRET`** = Your Client Secret from Step 3
3. **`GMAIL_REFRESH_TOKEN`** = Your Refresh Token from Step 4

## Step 6: Test

1. Redeploy your backend service on Render
2. Go to your app → Settings page
3. Click **"Test Connection"** on Gmail API
4. Should show "Connected" if everything is correct!

## Troubleshooting

### "Invalid Grant" Error
- Refresh token may have expired
- Regenerate it using OAuth Playground (Step 4)

### "Access Denied" Error
- Check that OAuth consent screen is published (for production)
- Or add your email as a test user (for testing)

### "Redirect URI Mismatch"
- Make sure `https://developers.google.com/oauthplayground` is in authorized redirect URIs

