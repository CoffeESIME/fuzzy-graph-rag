from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
import uuid

class Asset(SQLModel, table=True):
    """
    Core inventory table for tracking uploaded files and logical merged assets.
    
    Philosophy:
    - Represents both physical files (is_merged=False) and logical assets (is_merged=True)
    - file_hash ensures no duplicate uploads
    - sidecar_path points to source of truth metadata in MinIO
    - original_deleted=True means binary was purged after data extraction (transmutation)
    """
    __tablename__ = "assets"
    
    # --- PRIMARY KEY ---
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    
    # --- BASE METADATA ---
    filename: str = Field(index=True, description="Original filename or generated name for merged assets")
    minio_path: str = Field(description="Full path in MinIO bucket (e.g., raw/images/abc123.jpg)")
    mime_type: str = Field(description="MIME type (e.g., image/jpeg, application/pdf)")
    size_bytes: int = Field(description="Total file size in bytes")
    file_hash: str = Field(unique=True, index=True, description="SHA256 hash for deduplication")
    
    # --- CONTROL FLAGS ---
    is_merged: bool = Field(default=False, description="True if this asset is a fusion of multiple files")
    original_deleted: bool = Field(default=False, description="True if binary was deleted after data extraction")
    requires_user_memory: bool = Field(
        default=False, 
        description="True if asset requires user memory context before TEXT_SUMMARY can complete"
    )
    
    # --- PRIVACY & GOVERNANCE ---
    privacy_level: str = Field(
        default="strict_local",
        description="Data governance level controlling processing location (strict_local or public_cloud)",
        sa_column_kwargs={"server_default": "strict_local"}
    )
    
    # --- SIDECAR REFERENCE ---
    sidecar_path: str = Field(description="Path to JSON sidecar in MinIO (master_records/sidecars/)")
    
    # --- TIMESTAMPS ---
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "filename": "screenshot_merge_001.txt",
                "minio_path": "raw/temp/batch_uuid_123/merged.txt",
                "mime_type": "text/plain",
                "size_bytes": 15420,
                "file_hash": "a3f5d8e9c2b1...",
                "is_merged": True,
                "original_deleted": True,
                "sidecar_path": "master_records/sidecars/a3f5d8e9c2b1.json"
            }
        }
