"""
Script to apply database migrations.

Usage:
    python scripts/migrate.py
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from config.settings import get_settings

def run_migration():
    settings = get_settings()
    
    # Connect to PostgreSQL
    conn = psycopg2.connect(
        host=settings.POSTGRES_SERVER,
        port=settings.POSTGRES_PORT,
        database=settings.POSTGRES_DB,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD
    )
    
    try:
        cursor = conn.cursor()
        
        # Read migration file
        migration_file = os.path.join(
            os.path.dirname(__file__),
            "..",
            "migrations",
            "001_add_privacy_level.sql"
        )
        
        with open(migration_file, 'r') as f:
            sql = f.read()
        
        print("🔄 Applying migration: 001_add_privacy_level.sql")
        
        # Execute migration
        cursor.execute(sql)
        conn.commit()
        
        print("✅ Migration applied successfully!")
        print("\n📊 Verifying column exists:")
        
        # Verify
        cursor.execute("""
            SELECT column_name, data_type, column_default, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'assets' AND column_name = 'privacy_level';
        """)
        
        result = cursor.fetchone()
        if result:
            print(f"   ✓ Column: {result[0]}")
            print(f"   ✓ Type: {result[1]}")
            print(f"   ✓ Default: {result[2]}")
            print(f"   ✓ Nullable: {result[3]}")
        else:
            print("   ✗ Column not found!")
        
        cursor.close()
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Migration failed: {str(e)}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    run_migration()
