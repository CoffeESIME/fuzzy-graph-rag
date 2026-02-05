from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from typing import Dict, Any
import logging
import json
import uuid

from app.models.asset import Asset
from app.schemas.sidecar_schemas import UpdateSidecarRequest, UpdateSidecarResponse
from shared.database import get_session
from shared.clients import get_minio_client

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/sidecar",
    tags=["sidecar"]
)

@router.post("/update/{asset_id}", response_model=UpdateSidecarResponse)
async def update_sidecar(
    asset_id: str,
    request: UpdateSidecarRequest,
    session: Session = Depends(get_session)
):
    """
    Update specific fields in the asset's sidecar JSON.
    
    This endpoint:
    1. Fetches the current sidecar from MinIO
    2. Validates the updates
    3. Merges the new data
    4. Saves back to MinIO
    
    Args:
        asset_id: Asset UUID
        request: UpdateSidecarRequest with fields to update
        
    Returns:
        UpdateSidecarResponse
    """
    logger.info(f"📝 Updating sidecar for asset {asset_id}")
    
    try:
        asset_uuid = uuid.UUID(asset_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")
        
    asset = session.get(Asset, asset_uuid)
    if not asset:
        raise HTTPException(status_code=404, detail=f"Asset {asset_id} not found")
        
    minio_client = get_minio_client()
    bucket_name = "rag-dataset"
    
    # 1. Fetch current sidecar
    try:
        response = minio_client.get_object(Bucket=bucket_name, Key=asset.sidecar_path)
        sidecar_data = json.loads(response['Body'].read().decode('utf-8'))
    except Exception as e:
        logger.error(f"❌ Failed to read sidecar: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to read sidecar: {e}")
        
    # 2. Merge updates
    # Only allow updates to specific sections to prevent corruption
    # For now, we allow updating specific known safe areas or everything if needed
    # But let's follow the implementation plan: safe validation
    
    allowed_roots = ["data_layers", "user_notes", "user_context", "workflow_state", "audio_processing_options", "privacy_config"]
    updated_fields = {}
    
    for key, value in request.updates.items():
        # Validate root keys
        root_key = key.split('.')[0]
        
        # Check if key is allowed allowed in known roots OR already exists in valid sidecar
        if root_key not in allowed_roots and root_key not in sidecar_data:
             logger.warning(f"   ⚠️ Attempted to update restricted/unknown sidecar field: {root_key}")
             raise HTTPException(
                 status_code=400, 
                 detail=f"Field '{root_key}' is not allowed to be updated. Allowed roots: {allowed_roots}"
             )
        
        # Prevent completely replacing data_layers (must be partial or careful)
        # For this iteration, we allow it but log a warning if it looks destructive
        if key == "data_layers" and not isinstance(value, dict):
             raise HTTPException(status_code=400, detail="data_layers must be a dictionary")

        logger.info(f"   → Updating field: {key}")
        sidecar_data[key] = value
        updated_fields[key] = value

    # 3. Validate correctness (Basic check)
    if not isinstance(sidecar_data, dict):
        raise HTTPException(status_code=400, detail="Invalid sidecar structure (must be dict)")
        
    # 4. Save to MinIO
    try:
        sidecar_bytes = json.dumps(sidecar_data, indent=2, default=str).encode('utf-8')
        minio_client.put_object(
            Bucket=bucket_name,
            Key=asset.sidecar_path,
            Body=sidecar_bytes,
            ContentType='application/json'
        )
    except Exception as e:
        logger.error(f"❌ Failed to save sidecar: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save sidecar: {e}")
        
    logger.info(f"✅ Sidecar updated successfully for {asset.filename}")
    
    return UpdateSidecarResponse(
        success=True,
        message="Sidecar updated successfully",
        updated_fields=updated_fields
    )
