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


# Import text ingest schemas
from app.schemas import TextIngestRequest, TextIngestResponse


@router.post("/text", response_model=TextIngestResponse)
async def ingest_text(
    request: TextIngestRequest,
    session: Session = Depends(get_session)
):
    """
    Ingest raw text content without file upload.
    
    **Philosophy:**
    - For notes, ideas, text copied from other sources
    - Text is stored in master_records/texts/{hash}.txt
    - Sidecar created in master_records/sidecars/{hash}.json
    - All tasks start in ON_HOLD state
    
    **Example request:**
    ```json
    {
        "content": "Este es el texto que quiero guardar...",
        "title": "Notas de reunión",
        "vector_types": ["text_chunk", "user_memory"],
        "privacy_level": "strict_local",
        "user_notes": "Importante: contiene info confidencial"
    }
    ```
    
    **Args:**
    - content: The raw text to ingest (required)
    - title: Optional title (used for filename)
    - vector_types: Which vectorizations to apply (default: text_chunk)
    - privacy_level: Data governance level (default: strict_local)
    - user_notes: Optional context notes
    
    **Returns:**
    - TextIngestResponse with created asset info
    """
    # Process text ingestion
    service = IngestService(session)
    try:
        asset = service.ingest_text(
            content=request.content,
            title=request.title,
            vector_types=request.vector_types,
            privacy_level=request.privacy_level,
            user_notes=request.user_notes,
            is_user_memory=request.is_user_memory
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error ingesting text: {str(e)}"
        )
    
    # Count vector tasks (if None, defaults are applied in service: 1 type + TEXT_SUMMARY)
    vector_tasks_count = len(request.vector_types) + 1 if request.vector_types else 2
    
    return TextIngestResponse(
        success=True,
        message=f"Text ingested successfully as '{asset.filename}'",
        asset=AssetResponse(
            id=asset.id,
            filename=asset.filename,
            minio_path=asset.minio_path,
            sidecar_path=asset.sidecar_path,
            is_merged=False,
            vector_tasks_created=vector_tasks_count,
            created_at=asset.created_at
        )
    )
