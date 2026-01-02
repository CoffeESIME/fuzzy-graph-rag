"""
Pydantic schemas for Sidecar JSON metadata stored in MinIO.

The sidecar is the source of truth for all metadata about an asset.
It contains privacy config, workflow state, and layered data (AI drafts + human curation).
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime

from app.models.enums import PrivacyLevel, JobStatus, VectorType


# ==========================================
# PRIVACY CONFIGURATION
# ==========================================
class PrivacyConfig(BaseModel):
    """
    Privacy and governance configuration for an asset.
    """
    level: PrivacyLevel = Field(
        description="Governance level controlling where data can be processed"
    )
    locked: bool = Field(
        default=False,
        description="If True, privacy level cannot be changed (compliance lock)"
    )
    locked_reason: Optional[str] = Field(
        default=None,
        description="Reason for privacy lock (e.g., 'GDPR compliance', 'Legal hold')"
    )


# ==========================================
# WORKFLOW STATE
# ==========================================
class WorkflowState(BaseModel):
    """
    Tracks the processing pipeline state for this asset.
    """
    steps_completed: List[str] = Field(
        default_factory=list,
        description="List of pipeline steps completed (e.g., 'upload', 'ocr', 'embedding')"
    )
    current_status: JobStatus = Field(
        description="Current overall status of asset processing"
    )
    last_updated: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp of last workflow update"
    )
    error_log: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="History of errors/retries during processing"
    )


# ==========================================
# DATA LAYERS
# ==========================================
class DataLayers(BaseModel):
    """
    Multi-layer data storage for AI-generated and human-curated content.
    
    Philosophy:
    - raw_ai_drafts: Workers write here (OCR text, image captions, etc.)
    - human_curated: Users validate and edit AI drafts, moving to this layer
    - vectors_generated: List of vector embeddings created and stored in Weaviate
    """
    raw_ai_drafts: Dict[str, Any] = Field(
        default_factory=dict,
        description="AI-generated content awaiting human review (e.g., {'ocr_text': '...', 'caption': '...'})"
    )
    human_curated: Dict[str, Any] = Field(
        default_factory=dict,
        description="Human-validated/edited content (source of truth for final data)"
    )
    vectors_generated: List[str] = Field(
        default_factory=list,
        description="List of vector types successfully embedded (e.g., ['visual_siglip', 'text_chunk'])"
    )


# ==========================================
# COMPLETE SIDECAR METADATA
# ==========================================
class SidecarMetadata(BaseModel):
    """
    Complete sidecar JSON structure stored in MinIO.
    
    This is the master record for all metadata about an asset.
    PostgreSQL Asset table contains minimal fields; sidecar has the full details.
    """
    # --- CORE IDENTITY ---
    file_hash: str = Field(description="SHA256 hash of the file(s)")
    original_filename: str = Field(description="Original filename or generated name for merged assets")
    mime_type: str = Field(description="MIME type (e.g., image/jpeg, text/plain)")
    size_bytes: int = Field(description="Total file size in bytes")
    
    # --- UPLOAD METADATA ---
    upload_timestamp: datetime = Field(description="When the file was uploaded")
    operation: str = Field(description="Processing operation (standard/merge_ocr)")
    user_notes: Optional[str] = Field(default=None, description="User-provided context notes")
    discard_original: bool = Field(default=False, description="Whether to delete binary after extraction")
    
    # --- VECTORIZATION CONFIG ---
    vector_types: List[str] = Field(description="List of vector types to generate (e.g., ['visual_siglip', 'text_chunk'])")
    
    # --- MERGE METADATA (if applicable) ---
    is_merged: bool = Field(default=False, description="True if this is a logical merged asset")
    source_files: List[Any] = Field(
        default_factory=list,
        description="List of source file metadata (for merge_ocr: [{'filename': ..., 'path': ..., 'hash': ...}])"
    )
    batch_uuid: Optional[str] = Field(default=None, description="Batch UUID for merged assets")
    
    # --- PRIVACY & GOVERNANCE ---
    privacy_config: PrivacyConfig = Field(description="Privacy and compliance configuration")
    
    # --- WORKFLOW STATE ---
    workflow_state: WorkflowState = Field(description="Processing pipeline state tracking")
    
    # --- DATA LAYERS ---
    data_layers: DataLayers = Field(description="Multi-layer data storage (AI drafts + human curation)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "file_hash": "a3f5d8e9c2b1...",
                "original_filename": "screenshot_merge_001.txt",
                "mime_type": "text/plain",
                "size_bytes": 15420,
                "upload_timestamp": "2025-12-28T17:00:00Z",
                "operation": "merge_ocr",
                "user_notes": "Twitter thread about AI",
                "discard_original": True,
                "vector_types": ["text_chunk"],
                "is_merged": True,
                "source_files": [
                    {"filename": "tweet1.jpg", "path": "raw/temp/batch_uuid/...", "hash": "..."},
                    {"filename": "tweet2.jpg", "path": "raw/temp/batch_uuid/...", "hash": "..."}
                ],
                "batch_uuid": "550e8400-e29b-41d4-a716-446655440000",
                "privacy_config": {
                    "level": "strict_local",
                    "locked": False,
                    "locked_reason": None
                },
                "workflow_state": {
                    "steps_completed": ["upload", "ocr"],
                    "current_status": "review_required",
                    "last_updated": "2025-12-28T17:05:00Z",
                    "error_log": []
                },
                "data_layers": {
                    "raw_ai_drafts": {
                        "ocr_text": "This is the extracted text from the screenshots...",
                        "detected_language": "en"
                    },
                    "human_curated": {},
                    "vectors_generated": ["text_chunk"]
                }
            }
        }
