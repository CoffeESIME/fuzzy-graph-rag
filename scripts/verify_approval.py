
import sys
import os
import uuid
from datetime import datetime

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from sqlmodel import Session, select
from app.models.asset import Asset
from app.models.vector_status import VectorStatus
from app.models.enums import JobStatus, VectorType, PrivacyLevel
from shared.database import get_session
from app.routers.tasks import approve_tasks
from app.schemas.task_schemas import ApproveTaskRequest

def verify_approval():
    print("🧪 Starting Verification: Task Approval Logic")
    
    session = next(get_session())
    
    try:
        # 1. Create dummy asset
        asset = Asset(
            filename="test_approval_asset.jpg",
            minio_path="test/path.jpg",
            mime_type="image/jpeg",
            size_bytes=100,
            file_hash="hash_" + str(uuid.uuid4()),
            privacy_level=PrivacyLevel.STRICT_LOCAL.value,
            sidecar_path="test/sidecar.json"
        )
        session.add(asset)
        session.commit()
        session.refresh(asset)
        print(f"   ✅ Created dummy Asset: {asset.id}")
        
        # 2. Create dummy vector status in REVIEW_REQUIRED
        vs = VectorStatus(
            asset_id=asset.id,
            vector_type=VectorType.TEXT_OCR,
            status=JobStatus.REVIEW_REQUIRED
        )
        session.add(vs)
        session.commit()
        session.refresh(vs)
        print(f"   ✅ Created VectorStatus in REVIEW_REQUIRED: {vs.id}")
        
        # 3. Call approve endpoint function directly
        req = ApproveTaskRequest(vector_status_ids=[str(vs.id)])
        print(f"   🔄 Calling approve_tasks for {vs.id}...")
        
        # We need to run the async function
        import asyncio
        response = asyncio.run(approve_tasks(req, session))
        
        print(f"   ✅ Response: {response}")
        
        # 4. Verify in DB
        session.refresh(vs)
        print(f"   🔍 Current Status in DB: {vs.status}")
        
        if vs.status == JobStatus.COMPLETED:
            print("   🎉 SUCCESS: Status updated to COMPLETED")
        else:
            print(f"   ❌ FAILED: Status is {vs.status}, expected COMPLETED")
            sys.exit(1)
            
        # Cleanup
        session.delete(vs)
        session.delete(asset)
        session.commit()
        print("   🧹 Cleanup done")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        session.close()

if __name__ == "__main__":
    verify_approval()
