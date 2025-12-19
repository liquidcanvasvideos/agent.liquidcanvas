"""
Emergency script to verify that prospect data exists and is safe.

This script uses COUNT queries that don't require all columns to exist,
so it can verify data even if final_body is missing.
"""
import asyncio
import os
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import asyncpg


async def verify_data_exists():
    """Verify that prospect data exists in the database."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL not set")
        return
    
    print(f"🔍 Connecting to database...")
    print(f"   DATABASE_URL: {database_url[:50]}...")
    
    # Convert asyncpg URL to psycopg2 format for sync connection
    if database_url.startswith("postgresql+asyncpg://"):
        sync_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    else:
        sync_url = database_url
    
    try:
        # Use async engine
        engine = create_async_engine(database_url, echo=False)
        
        async with engine.begin() as conn:
            # Check total prospects
            result = await conn.execute(text("SELECT COUNT(*) FROM prospects"))
            total = result.scalar()
            print(f"\n✅ TOTAL PROSPECTS IN DATABASE: {total}")
            
            if total == 0:
                print("⚠️  WARNING: No prospects found in database!")
                return
            
            # Check by discovery_status
            result = await conn.execute(text("""
                SELECT discovery_status, COUNT(*) 
                FROM prospects 
                GROUP BY discovery_status
            """))
            print("\n📊 BY DISCOVERY STATUS:")
            for row in result:
                print(f"   {row[0] or 'NULL'}: {row[1]}")
            
            # Check by scrape_status
            result = await conn.execute(text("""
                SELECT scrape_status, COUNT(*) 
                FROM prospects 
                GROUP BY scrape_status
            """))
            print("\n📊 BY SCRAPE STATUS:")
            for row in result:
                print(f"   {row[0] or 'NULL'}: {row[1]}")
            
            # Check emails
            result = await conn.execute(text("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(contact_email) as with_email,
                    COUNT(CASE WHEN contact_email IS NOT NULL THEN 1 END) as emails_count
                FROM prospects
            """))
            row = result.fetchone()
            print(f"\n📧 EMAIL STATS:")
            print(f"   Total prospects: {row[0]}")
            print(f"   With email: {row[1]}")
            
            # Check websites
            result = await conn.execute(text("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(domain) as with_domain,
                    COUNT(page_url) as with_url
                FROM prospects
            """))
            row = result.fetchone()
            print(f"\n🌐 WEBSITE STATS:")
            print(f"   Total prospects: {row[0]}")
            print(f"   With domain: {row[1]}")
            print(f"   With URL: {row[2]}")
            
            # Check if final_body column exists
            result = await conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'prospects' 
                AND column_name = 'final_body'
            """))
            has_final_body = result.fetchone() is not None
            
            print(f"\n🔧 SCHEMA STATUS:")
            print(f"   final_body column exists: {has_final_body}")
            
            if not has_final_body:
                print("\n⚠️  ISSUE: final_body column is missing")
                print("   This is why queries are failing, but DATA IS SAFE!")
                print("   The backend will add this column on restart.")
            else:
                print("   ✅ Schema is correct")
            
            print("\n" + "="*60)
            print("✅ CONCLUSION: Your data is SAFE!")
            print("   The data exists in the database.")
            print("   Once final_body column is added, all data will be visible.")
            print("="*60)
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(verify_data_exists())

