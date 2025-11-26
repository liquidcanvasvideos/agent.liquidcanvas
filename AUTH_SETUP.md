# Authentication Setup Guide

## Quick Setup

### Option 1: Automatic (Recommended)

Run the automatic credential generator:

**PowerShell:**
```powershell
.\generate_auth.ps1
```

**Or directly with Python:**
```bash
py generate_auth.py
# or
python generate_auth.py
```

This will:
- ✅ Generate a secure random password
- ✅ Generate a secure JWT secret key
- ✅ Update your `.env` file automatically
- ✅ Display your login credentials

### Option 2: Manual Setup

1. **Open `.env` file** in the project root

2. **Add these lines:**
```env
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_secure_password_here
JWT_SECRET_KEY=your_jwt_secret_key_here
```

3. **Generate secure values:**
   - Use a strong password (at least 16 characters)
   - Use a random string for JWT_SECRET_KEY (at least 32 characters)

## Default Credentials

After running `generate_auth.py`, you'll see output like:

```
Username: admin
Password: 0gR*vjKLx8N3N0ug
```

**⚠️ IMPORTANT:** Save these credentials! You'll need them to log in.

## Using the Login

1. **Start your backend server:**
   ```bash
   python main.py
   # or
   uvicorn main:app --reload
   ```

2. **Start your frontend:**
   ```bash
   cd frontend
   npm run dev
   ```

3. **Visit the login page:**
   ```
   https://agent.liquidcanvas.art/login
   ```
   
   (For local development: `http://localhost:3000/login`)

4. **Enter your credentials:**
   - Username: `admin` (or your custom username)
   - Password: (the generated password)

5. **You'll be redirected to the dashboard** after successful login.

## Security Best Practices

1. **Change default password** - Don't use "admin" in production
2. **Use strong passwords** - At least 16 characters with mixed case, numbers, and symbols
3. **Keep JWT_SECRET_KEY secret** - Never commit it to version control
4. **Rotate credentials** - Change passwords periodically
5. **Use environment variables** - Never hardcode credentials in code

## Regenerating Credentials

To generate new credentials:

```bash
py generate_auth.py
```

This will update your `.env` file with new credentials. **Make sure to save the new password!**

## Troubleshooting

### "Could not validate credentials" error
- Check that `.env` file exists and has `ADMIN_USERNAME`, `ADMIN_PASSWORD`, and `JWT_SECRET_KEY`
- Restart your backend server after updating `.env`
- Verify credentials match what you're entering

### "Unauthorized" error
- Your token may have expired (tokens last 7 days)
- Log out and log back in
- Clear browser localStorage if needed

### Can't find `.env` file
- Make sure you're in the project root directory
- Run `generate_auth.py` to create it automatically
- Or create `.env` manually and add the required variables

## Environment Variables Reference

```env
# Authentication (Required)
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_secure_password
JWT_SECRET_KEY=your_jwt_secret_key

# Optional: Token expiration (default: 7 days)
# ACCESS_TOKEN_EXPIRE_MINUTES=10080
```

## Production Deployment

For production (Vercel, Render, etc.):

1. **Set environment variables** in your hosting platform's dashboard
2. **Use strong, unique values** for each environment
3. **Never use default credentials** in production
4. **Enable HTTPS** to protect credentials in transit

Example for Render:
- Go to your service → Environment
- Add: `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `JWT_SECRET_KEY`
- Use strong, randomly generated values

