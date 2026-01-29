"""
Pydantic schemas for Sidecar JSON metadata stored in MinIO.

The sidecar is the source of truth for all metadata about an asset.
It reflects the Multimodal Pipeline: 
Intermediate Results (OCR/Whisper + User Context) -> AI Synthesis (LLM JSON) -> Human Curation.
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime

from app.models.enums import PrivacyLevel, JobStatus


# ==========================================
# 0. AI EXTRACTION SCHEMAS (The LLM Output Structure)
# ==========================================
class GraphEntity(BaseModel):
    name: str
    type: Optional[str] = None
    domain: Optional[str] = None
    definition: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

class GraphCore(BaseModel):
    summary: str
    entities: Dict[str, List[GraphEntity]]  # Key: "persons", "concepts", etc.
    tags: List[str] = []

class VisualSpecifics(BaseModel):
    image_type: str
    composition: Optional[str] = None
    lighting: Optional[str] = None
    dominant_colors: List[str] = []
    art_style: Optional[str] = None
    ocr_text: Optional[str] = None
    visual_mood: Optional[str] = None

class AudioSpecifics(BaseModel):
    audio_type: str
    genre: Optional[str] = None
    tempo: Optional[str] = None
    instruments: List[str] = []
    lyrics_summary: Optional[str] = None
    emotional_tone: Optional[str] = None

class TextSpecifics(BaseModel):
    document_type: str
    rhetorical_tone: Optional[str] = None
    key_arguments: List[str] = []
    language: Optional[str] = None
    requires_action: bool = False

class AIExtractionResult(BaseModel):
    """
    The unified structured output from the LLM analysis.
    """
    graph_core: GraphCore
    visual_specifics: Optional[VisualSpecifics] = None
    audio_specifics: Optional[AudioSpecifics] = None
    text_specifics: Optional[TextSpecifics] = None
    
    # Technical Metadata
    model_name: str = Field(description="Name of the model used (e.g. 'gemini-2.5')")
    processing_time: float = Field(default=0.0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ==========================================
# 1. INTERMEDIATE RESULTS (The Ingredients)
# ==========================================
class IntermediateResults(BaseModel):
    """
    Raw data extracted by 'blind' tools before LLM synthesis.
    Acts as a cache to avoid re-processing heavy tasks like OCR/Whisper.
    """
    ocr_text: Optional[str] = Field(
        default=None, 
        description="Raw text from Tesseract/EasyOCR or Vision Model pre-pass"
    )
    audio_transcript: Optional[str] = Field(
        default=None, 
        description="Literal transcription (Whisper) of the file content (lyrics/speech)"
    )
    # --- CAMPO AGREGADO PARA EL CONTEXTO DEL USUARIO ---
    user_context_transcript: Optional[str] = Field(
        default=None,
        description="User's voice note or text description provided at upload time."
    )
    # ---------------------------------------------------
    frame_captions: List[str] = Field(
        default_factory=list,
        description="Brief captions of individual frames (for video)"
    )
    raw_tools_output: Dict[str, Any] = Field(
        default_factory=dict,
        description="Any other raw output from helper tools"
    )


# ==========================================
# 2. PRIVACY CONFIGURATION
# ==========================================
class PrivacyConfig(BaseModel):
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
# 3. WORKFLOW STATE
# ==========================================
class WorkflowState(BaseModel):
    steps_completed: List[str] = Field(
        default_factory=list,
        description="List of pipeline steps completed (e.g., 'upload', 'ocr', 'llm_synthesis')"
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
# 4. DATA LAYERS (The Core Logic)
# ==========================================
class DataLayers(BaseModel):
    """
    Multi-layer data storage reflecting the processing pipeline.
    """
    
    # LAYER 1: INGREDIENTS (Raw inputs + User Context)
    intermediate_results: IntermediateResults = Field(
        default_factory=IntermediateResults,
        description="Raw text/data extracted to feed the LLM context"
    )

    # LAYER 2: SYNTHESIS (AI Structured Output)
    ai_synthesis: Optional[AIExtractionResult] = Field(
        default=None,
        description="The final structured knowledge graph extracted by the LLM"
    )

    # LAYER 3: HUMAN TRUTH (Curated)
    human_curated: Optional[AIExtractionResult] = Field(
        default=None,
        description="Human-approved version of the synthesis (Source of Truth)"
    )
    
    # FALLBACK: Debug Data
    raw_debug_data: Dict[str, Any] = Field(
        default_factory=dict, 
        description="Raw JSON responses from LLM in case of parsing errors"
    )

    # LAYER 4: INDEX (Vectors)
    vectors_generated: List[str] = Field(
        default_factory=list,
        description="List of vector types successfully embedded and stored"
    )


# ==========================================
# 5. COMPLETE SIDECAR METADATA
# ==========================================
class SidecarMetadata(BaseModel):
    """
    Complete sidecar JSON structure stored in MinIO.
    """
    # --- CORE IDENTITY ---
    file_hash: str = Field(description="SHA256 hash of the file(s)")
    original_filename: str = Field(description="Original filename or generated name")
    mime_type: str = Field(description="MIME type (e.g., image/jpeg, text/plain)")
    size_bytes: int = Field(description="Total file size in bytes")
    
    # --- UPLOAD METADATA ---
    upload_timestamp: datetime = Field(description="When the file was uploaded")
    operation: str = Field(description="Processing operation (standard/merge_ocr)")
    user_notes: Optional[str] = Field(default=None, description="User-provided context notes")
    discard_original: bool = Field(default=False, description="Whether to delete binary after extraction")
    
    # --- VECTORIZATION CONFIG ---
    vector_types: List[str] = Field(description="List of vector types to generate")
    
    # --- MERGE METADATA (if applicable) ---
    is_merged: bool = Field(default=False, description="True if this is a logical merged asset")
    source_files: List[Any] = Field(default_factory=list)
    batch_uuid: Optional[str] = Field(default=None)
    
    # --- PRIVACY & GOVERNANCE ---
    privacy_config: PrivacyConfig = Field(description="Privacy and compliance configuration")
    
    # --- WORKFLOW STATE ---
    workflow_state: WorkflowState = Field(description="Processing pipeline state tracking")
    
    # --- DATA LAYERS ---
    data_layers: DataLayers = Field(description="Multi-layer data storage")
    
    # --- USER CONTEXT (for memory assets) ---
    user_context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="User context for memory assets (content, convert_to_memory flag)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "file_hash": "a3f5...",
                "original_filename": "meme.jpg",
                "mime_type": "image/jpeg",
                "size_bytes": 10240,
                "upload_timestamp": "2026-01-01T12:00:00Z",
                "operation": "standard",
                "user_notes": "Funny meme about coding",
                "vector_types": ["visual_siglip"],
                "privacy_config": {"level": "strict_local", "locked": False},
                "workflow_state": {
                    "steps_completed": ["upload", "ocr", "llm_synthesis"],
                    "current_status": "COMPLETED",
                    "last_updated": "2026-01-01T12:05:00Z"
                },
                "data_layers": {
                    "intermediate_results": {
                        "ocr_text": "When code compiles first try",
                        "user_context_transcript": "This reminds me of my first project"
                    },
                    "ai_synthesis": {
                        "graph_core": {
                            "summary": "Meme about success",
                            "entities": {"concepts": [{"name": "Success", "confidence": 0.9}]},
                            "tags": ["meme", "coding"]
                        },
                        "visual_specifics": {
                            "image_type": "meme",
                            "visual_mood": "Triumphant"
                        },
                        "model_name": "gemini-2.5",
                        "processing_time": 1.2
                    },
                    "vectors_generated": ["visual_siglip"]
                }
            }
        }
