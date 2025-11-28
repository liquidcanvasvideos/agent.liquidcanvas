# Quick API Keys Checklist

Use this checklist to track which API keys you've added to Render.

## ✅ Hunter.io
- [ ] `HUNTER_IO_API_KEY` = `ba71410fc6c6dcec6df42333e933a40bdf2fa1cb`
- [ ] Status: _______________

## ✅ DataForSEO
- [ ] `DATAFORSEO_LOGIN` = `jeremiah@liquidcanvas.art`
- [ ] `DATAFORSEO_PASSWORD` = `b85d55cf567939e7`
- [ ] Status: _______________

## ⏳ Google Gemini
- [ ] `GEMINI_API_KEY` = _______________________
- [ ] Get it from: https://aistudio.google.com/app/apikey
- [ ] Status: _______________

## ⏳ Gmail API
- [ ] `GMAIL_CLIENT_ID` = _______________________
- [ ] `GMAIL_CLIENT_SECRET` = _______________________
- [ ] `GMAIL_REFRESH_TOKEN` = _______________________
- [ ] Follow: `GMAIL_OAUTH_SETUP.md` for detailed instructions
- [ ] Status: _______________

## ⏳ Authentication (Optional but Recommended)
- [ ] `ADMIN_USERNAME` = `admin` (or your choice)
- [ ] `ADMIN_PASSWORD` = _______________________ (strong password!)
- [ ] `JWT_SECRET_KEY` = _______________________ (random string)
- [ ] Generate JWT secret: `openssl rand -hex 32` (or use online generator)

## ✅ Database & Redis (Auto-configured by Render)
- [x] `DATABASE_URL` - Auto-set by Render PostgreSQL
- [x] `REDIS_URL` - Auto-set by Render Redis

---

## Steps to Add Keys

1. **Go to Render Dashboard** → Your Backend Service → **Environment**
2. **Click "Add Environment Variable"** for each key above
3. **Enter Key** (exactly as shown)
4. **Enter Value** (your actual API key)
5. **Save Changes**
6. **Redeploy** the service after adding all keys

---

## After Adding Keys

1. ✅ Redeploy backend service
2. ✅ Go to `/settings` in your app
3. ✅ Click "Test Connection" on each service
4. ✅ All should show "Connected" ✅

---

## Quick Links

- **Render Dashboard:** https://dashboard.render.com
- **Hunter.io API:** https://hunter.io (Settings → API)
- **DataForSEO:** https://dataforseo.com (API → Credentials)
- **Gemini API:** https://aistudio.google.com/app/apikey
- **Gmail Setup:** See `GMAIL_OAUTH_SETUP.md`

