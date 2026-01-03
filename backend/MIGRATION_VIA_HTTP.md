# Run Migrations via HTTP (For Render Free Tier)

Since Render free tier doesn't provide shell access, you can run migrations via an HTTP endpoint.

## Step 1: Set Migration Token in Render

1. Go to your Render service dashboard
2. Go to **Environment** tab
3. Add a new environment variable:
   - **Key**: `MIGRATION_TOKEN`
   - **Value**: Choose a strong random string (e.g., `your-secret-migration-token-12345`)
4. Click **Save Changes**
5. Your service will automatically redeploy

## Step 2: Run Migrations via HTTP

After the service redeploys, run this command from your local terminal (or any HTTP client):

```bash
curl -X POST https://agent-liquidcanvas.onrender.com/api/health/migrate \
     -H "X-Migration-Token: your-secret-migration-token-12345"
```

**Replace `your-secret-migration-token-12345` with the token you set in Step 1.**

## Step 3: Verify Success

The response will show:
```json
{
  "status": "success",
  "message": "Migrations completed successfully",
  "schema_diagnostics": {
    "social_tables": {
      "valid": true,
      "missing": []
    }
  }
}
```

## Alternative: Use Browser or Postman

You can also use:
- **Browser**: Install a REST client extension
- **Postman**: Create a POST request to `/api/health/migrate` with header `X-Migration-Token`
- **Online tool**: Use https://reqbin.com/ or similar

## Security Note

- The migration token is required to prevent unauthorized access
- Keep your `MIGRATION_TOKEN` secret
- You can change it anytime in Render dashboard
- After changing the token, the service will redeploy automatically

## Troubleshooting

**Error: "Migration endpoint not configured"**
- Make sure `MIGRATION_TOKEN` is set in Render environment variables
- Wait for service to redeploy after adding the variable

**Error: "Invalid migration token"**
- Check that the token in your request matches the one in Render
- Make sure you're using the header name: `X-Migration-Token`

**Error: "Migration failed"**
- Check Render logs for detailed error messages
- Verify database connection is working
- Check that `DATABASE_URL` is set correctly

