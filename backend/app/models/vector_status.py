from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime
import uuid

from app.models.enums import JobStatus, VectorType

class VectorStatus(SQLModel, table=True):
    """
    Task tracking table for managing vectorization jobs.
    
    Philosophy:
    - One row per (Asset, VectorType) combination
    - Tracks the lifecycle from ON_HOLD → PENDING → PROCESSING → COMPLETED/FAILED
    - Stores weaviate_uuid after successful insertion
    - Captures error_message on failure for debugging
    """
    __tablename__ = "vector_statuses"
    
    # --- PRIMARY KEY ---
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    
    # --- FOREIGN KEY ---
    asset_id: uuid.UUID = Field(foreign_key="assets.id", index=True)
    
    # --- TASK DEFINITION ---
    vector_type: VectorType = Field(description="Which AI intelligence to apply")
    
    # --- STATUS TRACKING ---
    status: JobStatus = Field(default=JobStatus.ON_HOLD, index=True)
    
    # --- RESULTS ---
    weaviate_uuid: Optional[str] = Field(default=None, description="UUID in Weaviate after successful insertion")
    error_message: Optional[str] = Field(default=None, description="Error details if status=FAILED")
    
    # --- TIMESTAMPS ---
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "asset_id": "550e8400-e29b-41d4-a716-446655440000",
                "vector_type": "visual_siglip",
                "status": "on_hold",
                "weaviate_uuid": None,
                "error_message": None
            }
        }
