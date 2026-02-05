
import sys
import os
import uuid
import json
from datetime import datetime

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from sqlmodel import Session, select
from app.models.asset import Asset
from app.models.enums import PrivacyLevel
from shared.database import get_session
from shared.clients import get_minio_client
from app.routers.sidecar import update_sidecar
from app.schemas.sidecar_schemas import UpdateSidecarRequest

def verify_sidecar_update():
    print("🧪 Starting Verification: Sidecar Update Logic")
    
    session = next(get_session())
    minio_client = get_minio_client()
    bucket_name = "rag-dataset"
    
    try:
        # 1. Create dummy asset
        unique_id = str(uuid.uuid4())[:8]
        sidecar_path = f"test/sidecar_{unique_id}.json"
        asset = Asset(
            filename="test_sidecar_editor.jpg",
            minio_path="test/path.jpg",
            mime_type="image/jpeg",
            size_bytes=100,
            file_hash="hash_" + unique_id,
            privacy_level=PrivacyLevel.STRICT_LOCAL.value,
            sidecar_path=sidecar_path
        )
        session.add(asset)
        session.commit()
        session.refresh(asset)
        print(f"   ✅ Created dummy Asset: {asset.id}")
        
        # 2. Upload initial sidecar to MinIO
        initial_data = {
            "original_filename": "test_sidecar_editor.jpg",
            "data_layers": {
                "intermediate_results": {
                    "ocr_text": "Old text"
                }
            }
        }
        minio_client.put_object(
            Bucket=bucket_name,
            Key=sidecar_path,
            Body=json.dumps(initial_data).encode('utf-8'),
            ContentType='application/json'
        )
        print(f"   ✅ Uploaded initial sidecar to MinIO: {sidecar_path}")
        
        # 3. Call update endpoint function directly
        updates = {
            "data_layers": {
                "intermediate_results": {
                    "ocr_text": "New updated text via editor"
                }
            },
            "user_notes": "Added notes"
        }
        req = UpdateSidecarRequest(updates=updates)
        print(f"   🔄 Calling update_sidecar for {asset.id}...")
        
        # Run async function
        import asyncio
        response = asyncio.run(update_sidecar(str(asset.id), req, session))
        
        print(f"   ✅ Response: {response}")
        
        # 4. Verify in MinIO
        obj = minio_client.get_object(Bucket=bucket_name, Key=sidecar_path)
        updated_data = json.loads(obj['Body'].read().decode('utf-8'))
        
        print(f"   🔍 Updated Data in MinIO: {json.dumps(updated_data, indent=2)}")
        
        ocr_text = updated_data.get('data_layers', {}).get('intermediate_results', {}).get('ocr_text')
        user_notes = updated_data.get('user_notes')
        
        if ocr_text == "New updated text via editor" and user_notes == "Added notes":
            print("   🎉 SUCCESS: Sidecar updated correctly")
        else:
            print(f"   ❌ FAILED: Data mismatch")
            sys.exit(1)
            
        # Cleanup
        session.delete(asset)
        session.commit()
        # minio cleanup skipped for safety/simplicity in test
        print("   🧹 DB Cleanup done")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        session.close()

if __name__ == "__main__":
    verify_sidecar_update()
