"""
API router for ingestion endpoints.
"""

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from typing import List
from sqlmodel import Session
import json

from app.schemas import UploadGroup, UploadResponse, AssetResponse
from app.services.ingest import IngestService
from shared.database import get_session

router = APIRouter(
    prefix="/ingest",
    tags=["ingestion"]
)


@router.post("/upload", response_model=UploadResponse)
async def upload_files(
    files: List[UploadFile] = File(..., description="List of files to upload"),
    upload_map: str = Form(..., description="JSON string defining processing groups"),
    session: Session = Depends(get_session)
):
    """
    Upload files with custom processing instructions.
    
    **Philosophy:**
    - Nothing processes automatically - all assets start in ON_HOLD state
    - Immediately generates sidecar JSON metadata in MinIO
    - Supports data transmutation (extract & discard originals)
    - Enables grouped ingestion (multiple files → single logical asset)
    
    **Example upload_map:**
    ```json
    [
      {
        "file_indices": [0, 1, 2],
        "operation": "merge_ocr",
        "vector_types": ["text_chunk"],
        "user_notes": "Twitter thread about AI",
        "discard_original": true
      },
      {
        "file_indices": [3],
        "operation": "standard",
        "vector_types": ["visual_siglip", "visual_semantic"],
        "discard_original": false
      }
    ]
    ```
    
    **Args:**
    - files: List of uploaded files
    - upload_map: JSON array of UploadGroup objects
    
    **Returns:**
    - UploadResponse with created assets and metadata
    """
    # Validate and parse upload_map
    try:
        upload_groups_data = json.loads(upload_map)
        upload_groups = [UploadGroup(**group) for group in upload_groups_data]
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid JSON in upload_map: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid upload_map structure: {str(e)}"
        )
    
    # Validate files were uploaded
    if not files:
        raise HTTPException(
            status_code=400,
            detail="No files were uploaded"
        )
    
    # Process upload
    service = IngestService(session)
    try:
        result = await service.process_upload(files, upload_groups)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing upload: {str(e)}"
        )
    
    # Build response
    asset_responses = []
    for asset in result["assets_created"]:
        # Count vector tasks for this asset
        vector_tasks_count = len([
            group for group in upload_groups
            for _ in group.vector_types
        ])
        
        asset_responses.append(AssetResponse(
            id=asset.id,
            filename=asset.filename,
            minio_path=asset.minio_path,
            sidecar_path=asset.sidecar_path,
            is_merged=asset.is_merged,
            vector_tasks_created=vector_tasks_count,
            created_at=asset.created_at
        ))
    
    return UploadResponse(
        success=True,
        message=f"Successfully processed {result['total_files_processed']} files into {len(asset_responses)} assets",
        assets_created=asset_responses,
        total_files_processed=result["total_files_processed"]
    )


@router.get("/health")
async def health_check():
    """Simple health check endpoint for the ingestion service."""
    return {
        "status": "healthy",
        "service": "ingestion"
    }
