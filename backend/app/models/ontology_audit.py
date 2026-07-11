import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlmodel import Field, SQLModel
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB

class OntologyAudit(SQLModel, table=True):
    __tablename__ = "ontology_audit"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
    
    # E.g., 'merge_concepts', 'merge_entities', 'demote_concept', 'demote_entity', 'retype_entity'
    operation_type: str = Field(nullable=False, index=True)
    
    # Store the names of the affected source nodes
    source_names: List[str] = Field(sa_column=Column(JSONB), default=[])
    
    # The name of the target node (if applicable)
    target_name: Optional[str] = Field(default=None)
    
    # Store any additional snapshot details (weights, original properties, etc.)
    details: Dict[str, Any] = Field(sa_column=Column(JSONB), default={})
