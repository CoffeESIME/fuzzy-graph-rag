"""
Pydantic schemas for the ingestion API.
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from enum import Enum
from datetime import datetime
import uuid

from app.models.enums import VectorType, PrivacyLevel

# ==========================================
# PROCESSING OPERATION ENUM
# ==========================================
class ProcessingOperation(str, Enum):
    """
    Defines how files should be processed.
    """
    STANDARD = "standard"       # 1 File = 1 Asset (normal upload)
    MERGE_OCR = "merge_ocr"     # N Files = 1 Asset (concatenated text from OCR)


# ==========================================
# UPLOAD GROUP SCHEMA
# ==========================================
class UploadGroup(BaseModel):
    """
    Defines a group of files to be processed together.
    
    Example:
    {
        "file_indices": [0, 1, 2],
        "operation": "merge_ocr",
        "vector_types": ["text_chunk"],
        "privacy_level": "strict_local",
        "user_notes": "Twitter thread about AI",
        "discard_original": true
    }
    """
    file_indices: List[int] = Field(
        description="Indices of files in the upload list that belong to this group",
        min_length=1
    )
    operation: ProcessingOperation = Field(
        description="How to process this group of files"
    )
    vector_types: List[VectorType] = Field(
        description="Which AI intelligences to apply to the resulting asset(s)",
        min_length=1
    )
    privacy_level: PrivacyLevel = Field(
        default=PrivacyLevel.STRICT_LOCAL,
        description="Data governance level for this group"
    )
    user_notes: Optional[str] = Field(
        default=None,
        description="Optional user notes/context for this group"
    )
    discard_original: bool = Field(
        default=False,
        description="If True, delete binary files after successful data extraction"
    )
    
    @field_validator('file_indices')
    @classmethod
    def validate_indices(cls, v):
        """Ensure indices are non-negative"""
        if any(idx < 0 for idx in v):
            raise ValueError("File indices must be non-negative")
        return v


# ==========================================
# RESPONSE SCHEMAS
# ==========================================
class AssetResponse(BaseModel):
    """Response schema for a created asset"""
    id: uuid.UUID
    filename: str
    minio_path: str
    sidecar_path: str
    is_merged: bool
    vector_tasks_created: int
    created_at: datetime


class UploadResponse(BaseModel):
    """Response schema for the upload endpoint"""
    success: bool
    message: str
    assets_created: List[AssetResponse]
    total_files_processed: int
