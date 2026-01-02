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
    """Request to dispatch vector status tasks to processing."""
    vector_status_ids: List[str]


class DispatchTasksResponse(BaseModel):
    """Response from dispatching tasks."""
    success: bool
    message: str
    tasks_updated: int
    celery_task_ids: List[str] = []


class UpdatePrivacyRequest(BaseModel):
    """Request to update asset privacy level."""
    privacy_level: PrivacyLevel


class UpdatePrivacyResponse(BaseModel):
    """Response from privacy update."""
    success: bool
    message: str
    asset_id: str
    new_privacy_level: str
