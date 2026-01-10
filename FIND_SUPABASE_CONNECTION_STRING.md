# How to Find Supabase Connection Pooler Connection String

## The Connection Strings Are Not in Settings → Database

You're looking at **Settings → Database** which shows the pooler **configuration**, but **not the connection strings**. 

The connection strings are in a **different location**.

---

## Step 1: Find the "Connect" Button

1. **In your Supabase Dashboard**, look for a **"Connect"** button
   - It's usually at the top of the page
   - Or in the left sidebar
   - Or in the project overview page

2. **Click "Connect"** - this opens a modal/dialog with connection strings

## Step 2: Look for Connection Pooling Tab

In the "Connect" modal, you should see **tabs** like:
- **Direct Connection** (port 5432)
- **Connection Pooling** or **Transaction Mode** (port 6543) ← **This is what we need!**
- **Session Mode** (optional)

**Click on the "Connection Pooling" or "Transaction Mode" tab**

## Step 3: Copy the Connection String

You should see connection strings in different formats:
- URI format
- JDBC format
- Other formats

**Copy the URI format** - it will look something like:
```
postgresql://postgres.wlsbtxwbyqdagvrbkebl:[YOUR-PASSWORD]@aws-0-us-east-1.pooler.supabase.com:6543/postgres
```

OR

```
postgresql://postgres:[YOUR-PASSWORD]@db.wlsbtxwbyqdagvrbkebl.supabase.co:6543/postgres?pgbouncer=true
```

---

## Alternative: Check Project Settings → Connection String

If you can't find "Connect" button:

1. Go to: **Settings** (gear icon in left sidebar)
2. Look for **"Connection String"** or **"Database URL"** section
3. There might be a dropdown or tabs showing:
   - Direct connection
   - Connection pooling
   - Transaction mode

---

## If You Still Can't Find It: Manual Construction

If Supabase Free tier doesn't show pooler connection strings, we can **construct it manually**:

### Option A: Same Hostname with Port 6543

If your direct connection is:
```
postgresql://postgres:L1qu!dcvnvs@db.wlsbtxwbyqdagvrbkebl.supabase.co:5432/postgres
```

Change port to 6543 and add pooler parameter:
```
postgresql+asyncpg://postgres:L1qu%21dcvnvs@db.wlsbtxwbyqdagvrbkebl.supabase.co:6543/postgres?pgbouncer=true
```

### Option B: Pooler Hostname Format (if supported)

Some Supabase projects use a different hostname format:
```
postgresql+asyncpg://postgres.wlsbtxwbyqdagvrbkebl:L1qu%21dcvnvs@aws-0-us-east-1.pooler.supabase.com:6543/postgres
```

**Note**: The username might need to include project ref: `postgres.wlsbtxwbyqdagvrbkebl`

---

## What to Do Right Now

1. **Look for "Connect" button** in your Supabase dashboard (top of page or sidebar)
2. **Click it** and look for **"Connection Pooling"** or **"Transaction Mode"** tab
3. **Copy the connection string** shown there
4. **Share it with me** (you can mask the password) so I can format it correctly for Render

**If you can't find it**, try:
- Scrolling through all tabs in the Connect modal
- Looking in Settings → API or Settings → General
- Or share a screenshot of what you see when you click "Connect"

---

## Quick Test: Try Manual Format First

While you're looking for the official connection string, you can **try this on Render**:

**Update your `DATABASE_URL` on Render to:**
```
postgresql+asyncpg://postgres:L1qu%21dcvnvs@db.wlsbtxwbyqdagvrbkebl.supabase.co:6543/postgres?pgbouncer=true
```

**Key changes:**
- Port changed from `5432` to `6543`
- Added `?pgbouncer=true` at the end
- Keep `+asyncpg` after `postgresql`
- Password is URL-encoded: `L1qu%21dcvnvs`

**Save and redeploy**. This might work even if Supabase doesn't explicitly show this format.

---

## Still Having Issues?

If the connection pooler connection strings aren't available in your Supabase dashboard, it's possible:
1. **Free tier** might have limited pooler access
2. **Pooler might not be enabled** for your project
3. **Different UI** - Supabase might have updated their interface

**In that case**, contact Supabase support and ask:
- "How do I connect to the connection pooler for my project?"
- "Is connection pooling available on the Free tier?"
- "What is the pooler connection string for project wlsbtxwbyqdagvrbkebl?"

---

**Please try clicking the "Connect" button and let me know what connection strings you see!**

