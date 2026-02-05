from pydantic import BaseModel
from typing import Dict, Any, Optional

class UpdateSidecarRequest(BaseModel):
    """
    Request to update sidecar metadata.
    
    This is used for Human-in-the-Loop editing of data layers
    (e.g. correcting OCR text, updating user context).
    """
    updates: Dict[str, Any]  # Dictionary of fields to update (supports dot notation nesting if implemented)
    
class UpdateSidecarResponse(BaseModel):
    """Response from sidecar update."""
    success: bool
    message: str
    updated_fields: Dict[str, Any]
