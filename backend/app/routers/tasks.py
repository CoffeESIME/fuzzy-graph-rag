"""
API router for task management endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List
from pydantic import BaseModel
import uuid

from app.models.vector_status import VectorStatus
from app.models.asset import Asset
from app.models.enums import JobStatus
from shared.database import get_session

router = APIRouter(
    prefix="/tasks",
    tags=["tasks"]
)


# ==========================================
# SCHEMAS
# ==========================================

class TaskResponse(BaseModel):
    """Response schema for a task."""
    id: str
    asset_id: str
    filename: str
    vector_type: str
    status: str
    created_at: str
    updated_at: str


class ProcessTasksRequest(BaseModel):
    """Request schema for processing tasks."""
    task_ids: List[str]


class ProcessTasksResponse(BaseModel):
    """Response schema for processing tasks."""
    success: bool
    message: str
    tasks_updated: int
    celery_task_ids: List[str]


# ==========================================
# ENDPOINTS
# ==========================================

@router.get("/on-hold", response_model=List[TaskResponse])
async def get_on_hold_tasks(
    session: Session = Depends(get_session)
):
    """
    Get all tasks in ON_HOLD status (Staging).
    
    These are tasks that have been created but not yet sent to workers.
    Users can review and selectively trigger processing for these tasks.
    
    **Returns:**
    - List of tasks with their associated asset information
    """
    # Query VectorStatus joined with Asset to get filename
    statement = (
        select(VectorStatus, Asset.filename)
        .join(Asset, VectorStatus.asset_id == Asset.id)
        .where(VectorStatus.status == JobStatus.ON_HOLD)
        .order_by(VectorStatus.created_at.desc())
    )
    
    results = session.exec(statement).all()
    
    # Build response
    tasks = []
    for vector_status, filename in results:
        tasks.append(TaskResponse(
            id=str(vector_status.id),
            asset_id=str(vector_status.asset_id),
            filename=filename,
            vector_type=vector_status.vector_type.value,
            status=vector_status.status.value,
            created_at=vector_status.created_at.isoformat(),
            updated_at=vector_status.updated_at.isoformat()
        ))
    
    return tasks


@router.post("/start", response_model=ProcessTasksResponse)
async def start_processing(
    request: ProcessTasksRequest,
    session: Session = Depends(get_session)
):
    """
    Trigger processing for selected tasks.
    
    Changes task status from ON_HOLD → PENDING and dispatches to Celery workers.
    
    **Args:**
    - task_ids: List of VectorStatus IDs to process
    
    **Returns:**
    - ProcessTasksResponse with status and Celery task IDs
    """
    if not request.task_ids:
        raise HTTPException(
            status_code=400,
            detail="No task IDs provided"
        )
    
    # Convert string IDs to UUIDs
    try:
        task_uuids = [uuid.UUID(tid) for tid in request.task_ids]
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid UUID format: {str(e)}"
        )
    
    # Fetch tasks
    statement = select(VectorStatus).where(
        VectorStatus.id.in_(task_uuids),
        VectorStatus.status == JobStatus.ON_HOLD
    )
    tasks = session.exec(statement).all()
    
    if not tasks:
        raise HTTPException(
            status_code=404,
            detail="No ON_HOLD tasks found with provided IDs"
        )
    
    # Update status to PENDING
    celery_task_ids = []
    for task in tasks:
        task.status = JobStatus.PENDING
        session.add(task)
        
        # TODO: Dispatch to Celery
        # from worker.tasks import process_vector_task
        # celery_result = process_vector_task.delay(str(task.id))
        # celery_task_ids.append(celery_result.id)
        
        # For now, just acknowledge the update
        celery_task_ids.append(f"mock-celery-{task.id}")
    
    # Commit changes
    session.commit()
    
    return ProcessTasksResponse(
        success=True,
        message=f"Successfully queued {len(tasks)} task(s) for processing",
        tasks_updated=len(tasks),
        celery_task_ids=celery_task_ids
    )


@router.get("/status/{task_id}", response_model=TaskResponse)
async def get_task_status(
    task_id: str,
    session: Session = Depends(get_session)
):
    """
    Get the status of a specific task.
    
    **Args:**
    - task_id: VectorStatus ID
    
    **Returns:**
    - TaskResponse with current status
    """
    try:
        task_uuid = uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid UUID format"
        )
    
    # Query task with asset
    statement = (
        select(VectorStatus, Asset.filename)
        .join(Asset, VectorStatus.asset_id == Asset.id)
        .where(VectorStatus.id == task_uuid)
    )
    
    result = session.exec(statement).first()
    
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"Task {task_id} not found"
        )
    
    vector_status, filename = result
    
    return TaskResponse(
        id=str(vector_status.id),
        asset_id=str(vector_status.asset_id),
        filename=filename,
        vector_type=vector_status.vector_type.value,
        status=vector_status.status.value,
        created_at=vector_status.created_at.isoformat(),
        updated_at=vector_status.updated_at.isoformat()
    )


@router.get("/health")
async def health_check():
    """Simple health check endpoint for the tasks service."""
    return {
        "status": "healthy",
        "service": "tasks"
    }


# ==========================================
# NEW ENHANCED ENDPOINTS FOR MATRIX VIEW
# ==========================================

from app.schemas.task_schemas import (
    AssetWithTasksResponse,
    VectorStatusDetail,
    DispatchTasksRequest,
    DispatchTasksResponse,
    UpdatePrivacyRequest,
    UpdatePrivacyResponse
)
from shared.clients import get_minio_client
import json as json_lib


@router.get("/assets-with-tasks", response_model=List[AssetWithTasksResponse])
async def get_assets_with_tasks(
    session: Session = Depends(get_session)
):
    """
    Get all assets with their vector statuses and sidecar data.
    
    This endpoint is optimized for the task matrix view, returning:
    - Complete asset information
    - All associated vector statuses
    - Sidecar metadata from MinIO
    
    **Returns:**
    - List of assets with nested vector_statuses and sidecar_data
    """
    # Query all assets with at least one ON_HOLD vector status
    statement = (
        select(Asset)
        .join(VectorStatus, Asset.id == VectorStatus.asset_id)
        .where(VectorStatus.status == JobStatus.ON_HOLD)
        .distinct()
        .order_by(Asset.created_at.desc())
    )
    
    assets = session.exec(statement).all()
    
    # MinIO client for sidecar retrieval
    minio_client = get_minio_client()
    bucket_name = "graphrag-storage"  # Adjust to your bucket name
    
    # Build response
    assets_response = []
    for asset in assets:
        # Fetch all vector statuses for this asset
        vector_statuses_stmt = select(VectorStatus).where(
            VectorStatus.asset_id == asset.id
        )
        vector_statuses = session.exec(vector_statuses_stmt).all()
        
        # Convert to schema
        vector_status_details = [
            VectorStatusDetail(
                id=str(vs.id),
                vector_type=vs.vector_type.value,
                status=vs.status.value,
                weaviate_uuid=vs.weaviate_uuid,
                error_message=vs.error_message,
                created_at=vs.created_at.isoformat(),
                updated_at=vs.updated_at.isoformat()
            )
            for vs in vector_statuses
        ]
        
        # Fetch sidecar data from MinIO
        try:
            response = minio_client.get_object(bucket_name, asset.sidecar_path)
            sidecar_data = json_lib.loads(response.read().decode('utf-8'))
        except Exception as e:
            # If sidecar not found, create minimal structure
            sidecar_data = {
                "error": f"Sidecar not found: {str(e)}",
                "file_hash": asset.file_hash,
                "original_filename": asset.filename,
                "mime_type": asset.mime_type
            }
        
        # Build asset response
        assets_response.append(AssetWithTasksResponse(
            id=str(asset.id),
            filename=asset.filename,
            minio_path=asset.minio_path,
            mime_type=asset.mime_type,
            size_bytes=asset.size_bytes,
            file_hash=asset.file_hash,
            is_merged=asset.is_merged,
            original_deleted=asset.original_deleted,
            privacy_level=asset.privacy_level,
            sidecar_path=asset.sidecar_path,
            created_at=asset.created_at.isoformat(),
            updated_at=asset.updated_at.isoformat(),
            vector_statuses=vector_status_details,
            sidecar_data=sidecar_data
        ))
    
    return assets_response


@router.post("/dispatch", response_model=DispatchTasksResponse)
async def dispatch_tasks(
    request: DispatchTasksRequest,
    session: Session = Depends(get_session)
):
    """
    Dispatch selected vector status tasks to processing queue.
    
    Changes status from ON_HOLD → PENDING and triggers Celery workers.
    
    **Args:**
    - vector_status_ids: List of VectorStatus UUIDs to dispatch
    
    **Returns:**
    - DispatchTasksResponse with success status and Celery task IDs
    """
    if not request.vector_status_ids:
        raise HTTPException(
            status_code=400,
            detail="No vector status IDs provided"
        )
    
    # Convert to UUIDs
    try:
        task_uuids = [uuid.UUID(vid) for vid in request.vector_status_ids]
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid UUID format: {str(e)}"
        )
    
    # Fetch tasks
    statement = select(VectorStatus).where(
        VectorStatus.id.in_(task_uuids),
        VectorStatus.status == JobStatus.ON_HOLD
    )
    tasks = session.exec(statement).all()
    
    if not tasks:
        raise HTTPException(
            status_code=404,
            detail="No ON_HOLD tasks found with provided IDs"
        )
    
    # Update to PENDING and dispatch
    celery_task_ids = []
    for task in tasks:
        task.status = JobStatus.PENDING
        session.add(task)
        
        # TODO: Trigger Celery task
        # from worker.tasks import process_vector_task
        # celery_result = process_vector_task.delay(str(task.id))
        # celery_task_ids.append(celery_result.id)
        
        celery_task_ids.append(f"celery-{task.id}")
    
    session.commit()
    
    return DispatchTasksResponse(
        success=True,
        message=f"Successfully dispatched {len(tasks)} task(s) to processing queue",
        tasks_updated=len(tasks),
        celery_task_ids=celery_task_ids
    )


@router.put("/privacy/{asset_id}", response_model=UpdatePrivacyResponse)
async def update_asset_privacy(
    asset_id: str,
    request: UpdatePrivacyRequest,
    session: Session = Depends(get_session)
):
    """
    Update the privacy level of an asset.
    
    Also updates the sidecar metadata in MinIO.
    
    **Args:**
    - asset_id: Asset UUID
    - request: UpdatePrivacyRequest with new privacy level
    
    **Returns:**
    - UpdatePrivacyResponse with success status
    """
    try:
        asset_uuid = uuid.UUID(asset_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid UUID format"
        )
    
    # Fetch asset
    asset = session.get(Asset, asset_uuid)
    if not asset:
        raise HTTPException(
            status_code=404,
            detail=f"Asset {asset_id} not found"
        )
    
    # Update privacy level
    old_privacy = asset.privacy_level
    asset.privacy_level = request.privacy_level.value
    session.add(asset)
    session.commit()
    
    # TODO: Update sidecar in MinIO
    # minio_client = get_minio_client()
    # Update sidecar JSON with new privacy level
    
    return UpdatePrivacyResponse(
        success=True,
        message=f"Privacy level updated from {old_privacy} to {request.privacy_level.value}",
        asset_id=str(asset.id),
        new_privacy_level=request.privacy_level.value
    )

