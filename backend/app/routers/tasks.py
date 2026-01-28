"""
API router for task management endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List
from pydantic import BaseModel
from datetime import datetime
import uuid
import logging

from app.models.vector_status import VectorStatus
from app.models.asset import Asset
from app.models.enums import JobStatus, VectorType
from shared.database import get_session

# Configure logging
logger = logging.getLogger(__name__)

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
    UpdatePrivacyResponse,
    ResetToHoldRequest,
    ResetToHoldResponse
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
    # Query all assets that have ANY vector status (not just ON_HOLD)
    statement = (
        select(Asset)
        .join(VectorStatus, Asset.id == VectorStatus.asset_id)
        .distinct()
        .order_by(Asset.created_at.desc())
    )
    
    assets = session.exec(statement).all()
    
    # MinIO client for sidecar retrieval
    minio_client = get_minio_client()
    bucket_name = "rag-dataset"  # Must match bucket in shared/clients.py
    
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
        
        # Fetch sidecar data from MinIO (boto3 style)
        try:
            response = minio_client.get_object(Bucket=bucket_name, Key=asset.sidecar_path)
            sidecar_data = json_lib.loads(response['Body'].read().decode('utf-8'))
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


# ==========================================
# RETRY FAILED TASKS
# ==========================================

class RetryFailedRequest(BaseModel):
    """Request to retry failed tasks."""
    vector_status_ids: List[str]


class RetryFailedResponse(BaseModel):
    """Response from retrying failed tasks."""
    tasks_retried: int
    celery_task_ids: List[str]


@router.post("/retry-failed", response_model=RetryFailedResponse)
async def retry_failed_tasks(
    request: RetryFailedRequest,
    session: Session = Depends(get_session)
):
    """
    Retry failed tasks by resetting them to ON_HOLD and dispatching to Celery.
    
    This endpoint:
    1. Finds the specified VectorStatus entries with status=FAILED
    2. Resets them to ON_HOLD (clears error_message)
    3. Updates status to PENDING
    4. Dispatches to appropriate Celery queue
    
    Returns:
        RetryFailedResponse with count and Celery task IDs
    """
    logger.info(f"📤 RETRY-FAILED ENDPOINT: {len(request.vector_status_ids)} task(s)")
    
    # Helper for queue assignment
    def get_queue_for_vector_type(vector_type: VectorType) -> str:
        if vector_type in [VectorType.VISUAL_SEMANTIC, VectorType.TEXT_OCR]:
            return "heavy_gpu"
        return "fast_cpu"
    
    # Query the failed tasks
    statement = (
        select(VectorStatus, Asset)
        .join(Asset, VectorStatus.asset_id == Asset.id)
        .where(
            VectorStatus.id.in_(request.vector_status_ids),
            VectorStatus.status == JobStatus.FAILED
        )
    )
    
    results = session.exec(statement).all()
    logger.info(f"✅ Found {len(results)} FAILED task(s) to retry")
    
    if not results:
        return RetryFailedResponse(tasks_retried=0, celery_task_ids=[])
    
    celery_task_ids = []
    retried_count = 0
    
    for vector_status, asset in results:
        # Reset status and clear error
        vector_status.status = JobStatus.PENDING
        vector_status.error_message = None
        vector_status.updated_at = datetime.utcnow()
        
        # Dispatch to Celery
        queue_name = get_queue_for_vector_type(vector_status.vector_type)
        
        try:
            from app.core.celery_app import app as celery_app
            
            celery_task = celery_app.send_task(
                'worker.tasks.process_vector_task',
                args=[str(vector_status.id)],
                queue=queue_name
            )
            
            celery_task_ids.append(celery_task.id)
            retried_count += 1
            logger.info(f"🔄 Retrying {asset.filename} / {vector_status.vector_type.value} → {queue_name}")
            
        except Exception as e:
            logger.error(f"❌ Failed to dispatch retry: {e}")
            continue
    
    session.commit()
    
    logger.info(f"✅ RETRY-FAILED COMPLETED: {retried_count} task(s)")
    
    return RetryFailedResponse(
        tasks_retried=retried_count,
        celery_task_ids=celery_task_ids
    )


@router.post("/dispatch", response_model=DispatchTasksResponse)
async def dispatch_tasks(
    request: DispatchTasksRequest,
    session: Session = Depends(get_session)
):
    """
    2. JOIN with Asset table to retrieve privacy_level
    3. Update status from ON_HOLD → PENDING in database
    4. Determine appropriate queue based on vector_type (heavy_gpu vs fast_cpu)
    5. Simulate queue assignment (mock Celery dispatch with logging)
    6. Return count and Celery task IDs
    
    **Args:**
    - request: DispatchTasksRequest with one of: vector_status_ids, asset_ids, or dispatch_all
    
    **Returns:**
    - DispatchTasksResponse with count and Celery task IDs
    
    Dispatch vector status tasks from ON_HOLD to PENDING and send to Celery workers.
    
    Supports three modes:
    1. vector_status_ids: Dispatch specific VectorStatus IDs
    2. asset_ids: Dispatch all ON_HOLD tasks for specific assets
    3. dispatch_all: Dispatch ALL ON_HOLD tasks in the system
    
    Returns:
        DispatchTasksResponse with count of dispatched tasks and Celery task IDs
    """
    logger.info("=" * 80)
    logger.info("📤 DISPATCH ENDPOINT CALLED")
    logger.info("=" * 80)
    logger.info(f"Request payload: {request.model_dump()}")
    
    # Helper function for queue assignment
    def get_queue_for_vector_type(vector_type: VectorType) -> str:
        """Determine queue based on vector type."""
        if vector_type in [VectorType.VISUAL_SEMANTIC, VectorType.TEXT_OCR]:
            return "heavy_gpu"
        elif vector_type in [VectorType.VISUAL_SIGLIP, VectorType.TEXT_CHUNK]:
            return "fast_cpu"
        else:
            return "fast_cpu"  # Default for audio, memory, etc.
    
    # Helper: Check if TEXT_SUMMARY is approved (COMPLETED) for an asset
    # TEXT_SUMMARY is a mandatory prerequisite for all other tasks
    # It starts as REVIEW_REQUIRED after LLM analysis, then user approves → COMPLETED
    def is_text_summary_approved(asset_id) -> bool:
        """Check if TEXT_SUMMARY task has been approved (COMPLETED) for the given asset."""
        stmt = select(VectorStatus).where(
            VectorStatus.asset_id == asset_id,
            VectorStatus.vector_type == VectorType.TEXT_SUMMARY,
            VectorStatus.status == JobStatus.COMPLETED
        )
        return session.exec(stmt).first() is not None
    
    # Cache for TEXT_SUMMARY status per asset to avoid repeated DB queries
    text_summary_status_cache = {}
    
    # Validate request - at least one dispatch mode must be provided
    if not request.dispatch_all and not request.vector_status_ids and not request.asset_ids:
        raise HTTPException(
            status_code=400,
            detail="Must provide either 'dispatch_all=True', 'vector_status_ids', or 'asset_ids'"
        )
    
    celery_task_ids = []
    dispatched_count = 0
    
    # Determine which dispatch mode
    if request.vector_status_ids:
        logger.info(f"🎯 Mode: SPECIFIC IDs - {len(request.vector_status_ids)} task(s)")
        logger.debug(f"   IDs: {request.vector_status_ids}")
        
        # Query specific VectorStatus by IDs
        statement = (
            select(VectorStatus, Asset)
            .join(Asset, VectorStatus.asset_id == Asset.id)
            .where(
                VectorStatus.id.in_(request.vector_status_ids),
                VectorStatus.status == JobStatus.ON_HOLD
            )
        )
    elif request.asset_ids:
        logger.info(f"🎯 Mode: BY ASSETS - {len(request.asset_ids)} asset(s)")
        logger.debug(f"   Asset IDs: {request.asset_ids}")
        
        # Query all ON_HOLD tasks for specific assets
        statement = (
            select(VectorStatus, Asset)
            .join(Asset, VectorStatus.asset_id == Asset.id)
            .where(
                VectorStatus.asset_id.in_(request.asset_ids),
                VectorStatus.status == JobStatus.ON_HOLD
            )
        )
    elif request.dispatch_all:
        logger.info(f"🎯 Mode: DISPATCH ALL")
        
        # Query ALL ON_HOLD tasks
        statement = (
            select(VectorStatus, Asset)
            .join(Asset, VectorStatus.asset_id == Asset.id)
            .where(VectorStatus.status == JobStatus.ON_HOLD)
        )
    else:
        logger.error("❌ No dispatch mode specified")
        raise HTTPException(
            status_code=400,
            detail="Must provide vector_status_ids, asset_ids, or dispatch_all=True"
        )
    
    # Execute query
    logger.debug("🔍 Executing database query...")
    results = session.exec(statement).all()
    logger.info(f"✅ Found {len(results)} ON_HOLD task(s) in database")
    
    if not results:
        logger.warning("⚠️  No tasks found to dispatch")
        return DispatchTasksResponse(
            tasks_updated=0,
            celery_task_ids=[]
        )
    
    # Build metadata lookup for quick access
    metadata_lookup = {}
    if request.task_metadata:
        for tm in request.task_metadata:
            metadata_lookup[tm.vector_status_id] = tm
        logger.info(f"📝 Task metadata provided for {len(metadata_lookup)} task(s)")
    
    # Helper function to save metadata to sidecar
    def save_metadata_to_sidecar(asset: Asset, task_meta) -> None:
        """Save user context and audio options to sidecar in MinIO."""
        if not task_meta:
            return
        
        try:
            minio_client = get_minio_client()
            bucket_name = "rag-dataset"
            
            # Download existing sidecar
            response = minio_client.get_object(Bucket=bucket_name, Key=asset.sidecar_path)
            sidecar_data = json_lib.loads(response['Body'].read().decode('utf-8'))
            
            # Add user_context if provided
            if task_meta.user_context:
                sidecar_data['user_context'] = {
                    'content': task_meta.user_context.content,
                    'convert_to_memory': task_meta.user_context.convert_to_memory
                }
                logger.info(f"      → Added user_context to sidecar")
            
            # Add audio_processing_options if provided
            if task_meta.audio_processing_options:
                sidecar_data['audio_processing_options'] = {
                    'is_voice_note': task_meta.audio_processing_options.is_voice_note,
                    'is_song': task_meta.audio_processing_options.is_song,
                    'has_provided_lyrics': task_meta.audio_processing_options.has_provided_lyrics,
                    'provided_lyrics_text': task_meta.audio_processing_options.provided_lyrics_text,
                    'use_whisper': task_meta.audio_processing_options.use_whisper
                }
                logger.info(f"      → Added audio_processing_options to sidecar")
            
            # Upload updated sidecar
            sidecar_bytes = json_lib.dumps(sidecar_data, indent=2, default=str).encode('utf-8')
            minio_client.put_object(
                Bucket=bucket_name,
                Key=asset.sidecar_path,
                Body=sidecar_bytes,
                ContentType='application/json'
            )
            logger.info(f"      ✅ Sidecar updated: {asset.sidecar_path}")
            
        except Exception as e:
            logger.warning(f"      ⚠️ Failed to update sidecar with metadata: {e}")
            # Don't fail the dispatch, just log the warning
    
    # Process each VectorStatus
    logger.info(f"🔄 Processing {len(results)} task(s)...")
    
    for vector_status, asset in results:
        logger.info("-" * 60)
        logger.info(f"📋 Task {dispatched_count + 1}/{len(results)}")
        logger.info(f"   VectorStatus ID: {vector_status.id}")
        logger.info(f"   Asset: {asset.filename}")
        logger.info(f"   VectorType: {vector_status.vector_type}")
        logger.info(f"   Privacy: {asset.privacy_level}")
        
        # TEXT_SUMMARY prerequisite check for non-TEXT_SUMMARY tasks
        if vector_status.vector_type != VectorType.TEXT_SUMMARY:
            # Check cache first
            asset_id_str = str(asset.id)
            if asset_id_str not in text_summary_status_cache:
                text_summary_status_cache[asset_id_str] = is_text_summary_approved(asset.id)
            
            if not text_summary_status_cache[asset_id_str]:
                logger.warning(f"   ⚠️ SKIPPING: TEXT_SUMMARY not approved for this asset")
                logger.warning(f"      → TEXT_SUMMARY must be reviewed and approved before other tasks")
                continue
        
        # Check if we have metadata for this task
        task_meta = metadata_lookup.get(str(vector_status.id))
        if task_meta:
            logger.info(f"   📝 Metadata found for this task")
            save_metadata_to_sidecar(asset, task_meta)
        
        # Update status to PENDING
        logger.debug(f"   → Updating status: ON_HOLD → PENDING")
        vector_status.status = JobStatus.PENDING
        vector_status.updated_at = datetime.utcnow()
        
        # Determine queue based on vector type
        queue_name = get_queue_for_vector_type(vector_status.vector_type)
        logger.info(f"   → Queue assigned: {queue_name}")
        
        # Dispatch to Celery worker
        try:
            logger.info(f"   → Importing celery_app...")
            from app.core.celery_app import app as celery_app
            logger.debug(f"   ✅ Celery app imported: {celery_app.main}")
            
            logger.info(f"   → Sending task to Celery...")
            logger.debug(f"      Task name: worker.tasks.process_vector_task")
            logger.debug(f"      Args: ['{vector_status.id}']")
            logger.debug(f"      Queue: {queue_name}")
            
            celery_task = celery_app.send_task(
                'worker.tasks.process_vector_task',
                args=[str(vector_status.id)],
                queue=queue_name
            )
            
            logger.info(f"   ✅ Task sent to Celery!")
            logger.info(f"      Celery Task ID: {celery_task.id}")
            logger.info(f"      State: {celery_task.state}")
            
            celery_task_ids.append(celery_task.id)
            dispatched_count += 1
            
        except Exception as e:
            logger.error(f"   ❌ Failed to send task to Celery:")
            logger.error(f"      Error: {type(e).__name__}: {str(e)}")
            import traceback
            logger.error(f"      Traceback: {traceback.format_exc()}")
            # Continue with next task
            continue
    
    # Commit all status updates
    logger.info("-" * 60)
    logger.info(f"💾 Committing {dispatched_count} status update(s) to database...")
    session.commit()
    logger.info(f"✅ Database committed")
    
    logger.info("=" * 80)
    logger.info(f"✅ DISPATCH COMPLETED")
    logger.info(f"   Total dispatched: {dispatched_count}")
    logger.info(f"   Celery task IDs: {len(celery_task_ids)}")
    logger.info("=" * 80)
    
    return DispatchTasksResponse(
        tasks_updated=dispatched_count,
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


# ==========================================
# REVIEW QUEUE ENDPOINTS
# ==========================================

@router.get("/review-queue", response_model=List[AssetWithTasksResponse])
async def get_review_queue(
    session: Session = Depends(get_session)
):
    """
    Get all assets that have tasks requiring review or that failed.
    
    Returns assets with tasks in REVIEW_REQUIRED or FAILED status.
    User can review these and decide to:
    - Accept/reject REVIEW_REQUIRED tasks
    - Reset FAILED tasks back to ON_HOLD for retry
    """
    logger.info("📋 Fetching review queue (REVIEW_REQUIRED + FAILED tasks)")
    
    # Get all assets that have at least one task in REVIEW_REQUIRED or FAILED status
    statement = (
        select(Asset)
        .where(
            Asset.id.in_(
                select(VectorStatus.asset_id).where(
                    VectorStatus.status.in_([JobStatus.REVIEW_REQUIRED, JobStatus.FAILED])
                )
            )
        )
        .order_by(Asset.created_at.desc())
    )
    
    assets = session.exec(statement).all()
    logger.info(f"   Found {len(assets)} assets with review/failed tasks")
    
    result = []
    minio_client = get_minio_client()
    bucket_name = "rag-dataset"
    
    for asset in assets:
        # Get all vector statuses for this asset (only REVIEW_REQUIRED and FAILED)
        vs_statement = select(VectorStatus).where(
            VectorStatus.asset_id == asset.id,
            VectorStatus.status.in_([JobStatus.REVIEW_REQUIRED, JobStatus.FAILED])
        )
        vector_statuses = session.exec(vs_statement).all()
        
        # Get sidecar data
        sidecar_data = {}
        try:
            response = minio_client.get_object(Bucket=bucket_name, Key=asset.sidecar_path)
            sidecar_data = json_lib.loads(response['Body'].read().decode('utf-8'))
        except Exception as e:
            logger.warning(f"   Could not read sidecar for {asset.filename}: {e}")
        
        result.append(AssetWithTasksResponse(
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
            created_at=asset.created_at.isoformat() if asset.created_at else "",
            updated_at=asset.updated_at.isoformat() if asset.updated_at else "",
            vector_statuses=[
                VectorStatusDetail(
                    id=str(vs.id),
                    vector_type=vs.vector_type.value if hasattr(vs.vector_type, 'value') else str(vs.vector_type),
                    status=vs.status.value if hasattr(vs.status, 'value') else str(vs.status),
                    weaviate_uuid=str(vs.weaviate_uuid) if vs.weaviate_uuid else None,
                    error_message=vs.error_message,
                    created_at=vs.created_at.isoformat() if vs.created_at else "",
                    updated_at=vs.updated_at.isoformat() if vs.updated_at else ""
                )
                for vs in vector_statuses
            ],
            sidecar_data=sidecar_data
        ))
    
    logger.info(f"   Returning {len(result)} assets for review queue")
    return result


@router.post("/reset-to-hold", response_model=ResetToHoldResponse)
async def reset_tasks_to_hold(
    request: ResetToHoldRequest,
    session: Session = Depends(get_session)
):
    """
    Reset tasks from REVIEW_REQUIRED, FAILED, or REJECTED status back to ON_HOLD.
    
    This allows users to:
    - Re-process failed tasks after fixing issues
    - Re-send tasks that didn't pass review for re-processing
    - Clear error_message for fresh retry
    """
    logger.info(f"🔄 Resetting {len(request.vector_status_ids)} task(s) to ON_HOLD")
    
    reset_count = 0
    
    for vs_id in request.vector_status_ids:
        try:
            vs_uuid = uuid.UUID(vs_id)
            vector_status = session.get(VectorStatus, vs_uuid)
            
            if not vector_status:
                logger.warning(f"   VectorStatus {vs_id} not found")
                continue
            
            # Only reset if in allowed states
            if vector_status.status in [JobStatus.REVIEW_REQUIRED, JobStatus.FAILED, JobStatus.REJECTED]:
                old_status = vector_status.status
                vector_status.status = JobStatus.ON_HOLD
                vector_status.error_message = None  # Clear error message for fresh retry
                vector_status.updated_at = datetime.utcnow()
                reset_count += 1
                logger.info(f"   ✅ Reset {vs_id}: {old_status} → ON_HOLD")
            else:
                logger.warning(f"   ⚠️ Skipping {vs_id}: status={vector_status.status} (not resettable)")
                
        except Exception as e:
            logger.error(f"   ❌ Error resetting {vs_id}: {e}")
    
    session.commit()
    logger.info(f"   Reset {reset_count} task(s) to ON_HOLD")
    
    return ResetToHoldResponse(
        tasks_reset=reset_count,
        success=True,
        message=f"Successfully reset {reset_count} task(s) to ON_HOLD"
    )
