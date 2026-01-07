"""
Pydantic schemas for task management endpoints.
"""

from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime

from app.models.enums import PrivacyLevel, JobStatus, VectorType


# ==========================================
# VECTOR STATUS SCHEMAS
# ==========================================

class VectorStatusDetail(BaseModel):
    """Detailed vector status information."""
    id: str
    vector_type: str
    status: str
    weaviate_uuid: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str
    updated_at: str


# ==========================================
# ASSET WITH TASKS SCHEMA
# ==========================================

class AssetWithTasksResponse(BaseModel):
    """
    Complete asset information with vector statuses and sidecar data.
    Used for task matrix view.
    """
    id: str
    filename: str
    minio_path: str
    mime_type: str
    size_bytes: int
    file_hash: str
    is_merged: bool
    original_deleted: bool
    privacy_level: str
    sidecar_path: str
    created_at: str
    updated_at: str
    
    # Nested relationships
    vector_statuses: List[VectorStatusDetail]
    sidecar_data: Dict[str, Any]  # Full sidecar metadata


# ==========================================
# REQUEST/RESPONSE SCHEMAS
# ==========================================

class DispatchTasksRequest(BaseModel):
    """
    Request to dispatch vector status tasks to processing.
    
    Supports three dispatch modes:
    1. By specific vector_status_ids (original behavior)
    2. By asset_ids (dispatch all ON_HOLD tasks for specific assets)
    3. dispatch_all=True (dispatch ALL ON_HOLD tasks in system)
    
    Args:
        vector_status_ids: Optional list of specific VectorStatus UUIDs to dispatch
        asset_ids: Optional list of Asset UUIDs (dispatches all ON_HOLD tasks for these assets)
        dispatch_all: If True, dispatches ALL ON_HOLD tasks (ignores other fields)
    """
    vector_status_ids: Optional[List[str]] = None
    asset_ids: Optional[List[str]] = None
    dispatch_all: bool = False


class DispatchTasksResponse(BaseModel):
    """Response from dispatching tasks."""
    tasks_updated: int
    celery_task_ids: List[str] = []
    success: bool = True
    message: str = ""


class UpdatePrivacyRequest(BaseModel):
    """Request to update asset privacy level."""
    privacy_level: PrivacyLevel


class UpdatePrivacyResponse(BaseModel):
    """Response from privacy update."""
    success: bool
    message: str
    asset_id: str
    new_privacy_level: str
