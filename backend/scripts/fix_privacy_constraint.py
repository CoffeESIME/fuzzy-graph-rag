"""
Quick script to fix the privacy_level constraint.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from config.settings import get_settings

def fix_constraint():
    settings = get_settings()
    
    conn = psycopg2.connect(
        host=settings.POSTGRES_SERVER,
        port=settings.POSTGRES_PORT,
        database=settings.POSTGRES_DB,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD
    )
    
    try:
        cursor = conn.cursor()
        
        print("🔄 Dropping old constraint...")
        cursor.execute("ALTER TABLE assets DROP CONSTRAINT IF EXISTS privacy_level_check")
        
        print("✅ Creating new constraint...")
        cursor.execute("""
            ALTER TABLE assets 
            ADD CONSTRAINT privacy_level_check 
            CHECK (privacy_level IN ('strict_local', 'public_cloud'))
        """)
        
        conn.commit()
        print("✅ Constraint fixed successfully!")
        
        # Verify
        cursor.execute("""
            SELECT conname, pg_get_constraintdef(oid) 
            FROM pg_constraint 
            WHERE conname = 'privacy_level_check'
        """)
        
        result = cursor.fetchone()
        if result:
            print(f"\n✓ Constraint name: {result[0]}")
            print(f"✓ Definition: {result[1]}")
        
        cursor.close()
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Failed: {str(e)}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    fix_constraint()
