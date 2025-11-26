# Quick Hunter.io Setup

Your Hunter.io API key has been configured!

## API Key
```
ba71410fc6c6dcec6df42333e933a40bdf2fa1cb
```

## What Happens Now

1. **Automatic Integration**: The system will automatically use Hunter.io when:
   - Scraping new websites
   - Extracting contacts
   - The API key is detected

2. **Enhanced Email Finding**: The system now:
   - Searches Hunter.io's database for domain emails
   - Extracts from footers, headers, and contact forms
   - Checks 50+ contact page variations
   - Verifies email deliverability

3. **Better Results**: You should see:
   - More emails found per website
   - Emails not visible on the website
   - Verified, deliverable emails
   - Enriched data (names, positions, social links)

## Testing

To test if it's working:

1. **Restart your backend server** (if running locally)
2. **Scrape a website** using the frontend or API
3. **Check the logs** - you should see:
   ```
   Hunter.io client initialized
   Extracting from contact page: ...
   Email extraction sources: {'hunter_io': [...], 'footer': [...], ...}
   ```

## API Limits

- **Free Plan**: 25 searches/month
- Your current usage will be tracked in Hunter.io dashboard

## Troubleshooting

**If emails aren't being found:**
- Check backend logs for "Hunter.io" messages
- Verify the API key is in `.env` file
- Check your Hunter.io account for remaining searches
- Some domains may not have emails in Hunter.io's database

**To verify the key is loaded:**
- Run: `py test_hunter_io.py`
- Should show: "✅ Hunter.io client initialized"

## Next Steps

1. ✅ API key is configured
2. Restart backend server (if running)
3. Start scraping websites - Hunter.io will be used automatically!

