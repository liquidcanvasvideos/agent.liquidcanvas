"""
Automatically generate authentication credentials and update .env file
"""
import os
import secrets
import string
from pathlib import Path

def generate_secure_password(length=16):
    """Generate a secure random password"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    password = ''.join(secrets.choice(alphabet) for i in range(length))
    return password

def generate_jwt_secret(length=64):
    """Generate a secure JWT secret key"""
    alphabet = string.ascii_letters + string.digits
    secret = ''.join(secrets.choice(alphabet) for i in range(length))
    return secret

def update_env_file(env_path=".env", username=None, password=None, jwt_secret=None):
    """Update or create .env file with authentication credentials"""
    
    # Generate credentials if not provided
    if not username:
        username = "admin"
    
    if not password:
        password = generate_secure_password()
    
    if not jwt_secret:
        jwt_secret = generate_jwt_secret()
    
    # Read existing .env if it exists
    env_vars = {}
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
    
    # Update authentication variables
    env_vars['ADMIN_USERNAME'] = username
    env_vars['ADMIN_PASSWORD'] = password
    env_vars['JWT_SECRET_KEY'] = jwt_secret
    
    # Write back to .env file
    with open(env_path, 'w') as f:
        # Write existing variables (excluding auth vars we're updating)
        for key, value in env_vars.items():
            if key not in ['ADMIN_USERNAME', 'ADMIN_PASSWORD', 'JWT_SECRET_KEY']:
                f.write(f"{key}={value}\n")
        
        # Write authentication section
        f.write("\n# ============================================\n")
        f.write("# AUTHENTICATION (Auto-generated)\n")
        f.write("# ============================================\n")
        f.write(f"ADMIN_USERNAME={username}\n")
        f.write(f"ADMIN_PASSWORD={password}\n")
        f.write(f"JWT_SECRET_KEY={jwt_secret}\n")
    
    return username, password, jwt_secret

def main():
    """Main function to generate and display credentials"""
    print("=" * 60)
    print("Authentication Credentials Generator")
    print("=" * 60)
    print()
    
    # Check if .env exists
    env_path = ".env"
    if not os.path.exists(env_path):
        print(f"⚠️  {env_path} not found. Creating new file...")
        print()
    
    # Generate credentials
    print("Generating secure credentials...")
    username, password, jwt_secret = update_env_file(env_path)
    
    print("✅ Credentials generated and saved to .env file!")
    print()
    print("=" * 60)
    print("YOUR LOGIN CREDENTIALS")
    print("=" * 60)
    print(f"Username: {username}")
    print(f"Password: {password}")
    print()
    print("⚠️  IMPORTANT: Save these credentials securely!")
    print("⚠️  You will need them to log into the dashboard.")
    print()
    print("=" * 60)
    print("NEXT STEPS")
    print("=" * 60)
    print("1. Restart your backend server to load new credentials")
    print("2. Visit https://agent.liquidcanvas.art/login")
    print("   (For local dev: http://localhost:3000/login)")
    print("3. Use the credentials above to log in")
    print()
    print("✅ Done! Your authentication is now configured.")

if __name__ == "__main__":
    main()

