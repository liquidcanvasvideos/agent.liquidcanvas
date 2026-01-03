#!/bin/bash
# Simple script to run migrations on Render
# This can be executed manually in Render Shell

set -e

echo "=========================================="
echo "🔍 Finding alembic.ini..."
echo "=========================================="

# Try different locations
if [ -f "alembic.ini" ]; then
    echo "✅ Found alembic.ini in current directory"
    ALEMBIC_DIR="."
elif [ -f "backend/alembic.ini" ]; then
    echo "✅ Found alembic.ini in backend/ directory"
    cd backend
    ALEMBIC_DIR="."
elif [ -f "/app/alembic.ini" ]; then
    echo "✅ Found alembic.ini in /app"
    cd /app
    ALEMBIC_DIR="."
elif [ -f "/app/backend/alembic.ini" ]; then
    echo "✅ Found alembic.ini in /app/backend"
    cd /app/backend
    ALEMBIC_DIR="."
else
    echo "❌ ERROR: Could not find alembic.ini"
    echo "Current directory: $(pwd)"
    echo "Listing files:"
    ls -la
    echo ""
    echo "Trying to find alembic.ini:"
    find . -name "alembic.ini" 2>/dev/null || echo "No alembic.ini found"
    exit 1
fi

echo ""
echo "=========================================="
echo "📊 Current migration status:"
echo "=========================================="
alembic current || echo "⚠️  Could not get current migration status"

echo ""
echo "=========================================="
echo "🚀 Running migrations: alembic upgrade head"
echo "=========================================="
alembic upgrade head

echo ""
echo "=========================================="
echo "✅ Migrations completed!"
echo "=========================================="
echo ""
echo "📊 Final migration status:"
alembic current

echo ""
echo "=========================================="
echo "🔍 Verifying social tables exist..."
echo "=========================================="
# Try to check tables (if psql is available)
if command -v psql &> /dev/null && [ -n "$DATABASE_URL" ]; then
    echo "Checking for social_* tables..."
    psql "$DATABASE_URL" -c "\dt social_*" || echo "⚠️  Could not verify tables (psql not available or DATABASE_URL not set)"
else
    echo "⚠️  psql not available or DATABASE_URL not set - cannot verify tables"
    echo "   Check tables manually: psql \$DATABASE_URL -c '\\dt social_*'"
fi

echo ""
echo "=========================================="
echo "✅ Done! Restart your Render service."
echo "=========================================="
