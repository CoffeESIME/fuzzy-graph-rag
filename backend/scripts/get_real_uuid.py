"""
Get Real VectorStatus UUID from Database
=========================================

This script fetches a real UUID from the database to test with actual data.
"""

import sys
from shared.database import get_session
from app.models.vector_status import VectorStatus
from app.models.asset import Asset
from sqlmodel import select

def main():
    print("=" * 60)
    print("  FETCH REAL VECTORSTATUS FOR TESTING")
    print("=" * 60)
    
    session = next(get_session())
    
    try:
        # Get first ON_HOLD VectorStatus
        statement = select(VectorStatus, Asset).join(Asset).where(
            VectorStatus.status == "on_hold"
        ).limit(5)
        
        results = session.exec(statement).all()
        
        if not results:
            print("\n❌ No VectorStatus found with status='on_hold'")
            print("\nRun this SQL to create test data:")
            print("UPDATE vectorstatus SET status = 'on_hold' WHERE status != 'on_hold' LIMIT 5;")
            return 1
        
        print(f"\n✅ Found {len(results)} ON_HOLD VectorStatus:\n")
        
        for vs, asset in results:
            print(f"UUID: {vs.id}")
            print(f"  Asset: {asset.filename}")
            print(f"  VectorType: {vs.vector_type}")
            print(f"  Privacy: {asset.privacy_level}")
            print(f"  Status: {vs.status}")
            print()
        
        # Show test command
        first_uuid = results[0][0].id
        print("=" * 60)
        print("  TEST COMMAND")
        print("=" * 60)
        print(f"\npython scripts/test_dispatch.py\n")
        print("Or manually dispatch from Streamlit frontend.")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
