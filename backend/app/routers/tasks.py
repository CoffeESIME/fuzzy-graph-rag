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
