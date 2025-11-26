# Quick Authentication Setup

## 🚀 One-Command Setup

Just run this in PowerShell:

```powershell
.\generate_auth.ps1
```

Or with Python directly:

```bash
py generate_auth.py
```

## ✅ What It Does

- Generates secure random password
- Generates secure JWT secret key  
- Updates `.env` file automatically
- Shows you the login credentials

## 📋 Your Credentials

After running, you'll see:

```
Username: admin
Password: [random secure password]
```

**Save this password!** You'll need it to log in.

## 🔐 Login

**Production:**
1. Visit: `https://agent.liquidcanvas.art/login`
2. Enter credentials from above

**Local Development:**
1. Start backend: `python main.py`
2. Start frontend: `cd frontend && npm run dev`
3. Visit: `http://localhost:3000/login`
4. Enter credentials from above

## 🔄 Regenerate

To create new credentials, just run the script again:

```powershell
.\generate_auth.ps1
```

Done! 🎉

