from enum import Enum

# ==========================================
# PRIVACY LEVEL ENUM
# ==========================================
class PrivacyLevel(str, Enum):
    """
    Data governance levels for asset handling.
    
    Controls where and how data can be processed:
    - strict_local: Data never leaves local infrastructure (no cloud AI)
    - public_cloud: Data can be sent to external APIs (OpenAI, etc.)
    """
    STRICT_LOCAL = "strict_local"       # Local processing only (sensitive data)
    PUBLIC_CLOUD = "public_cloud"       # Allow external API calls (public data)


# ==========================================
# JOB STATUS ENUM
# ==========================================
class JobStatus(str, Enum):
    """
    Lifecycle states for asset processing tasks.
    
    Flow: ON_HOLD → PENDING → PROCESSING → COMPLETED/FAILED/REJECTED
    
    NOTE: Values must match PostgreSQL enum 'jobstatus' exactly (UPPERCASE).
    """
    ON_HOLD = "ON_HOLD"                     # Initial state (Staging - awaiting manual trigger)
    PENDING = "PENDING"                     # Queued in Redis for worker processing
    PROCESSING = "PROCESSING"               # Worker is actively processing
    REVIEW_REQUIRED = "REVIEW_REQUIRED"     # AI finished, wait for human review
    COMPLETED = "COMPLETED"                 # Successfully finished
    FAILED = "FAILED"                       # Error during processing
    REJECTED = "REJECTED"                   # Cancelled by user


# ==========================================
# VECTOR TYPE ENUM
# ==========================================
class VectorType(str, Enum):
    """
    Defines which AI intelligence/vectorization to apply to an asset.
    Maps to Weaviate Named Vectors and collection spaces.
    """
    
    # --- VISUAL SPACE (Images, Memes, Screenshots) ---
    VISUAL_SIGLIP = "visual_siglip"         # Aesthetic/Form (Named Vector: 'visual')
    VISUAL_SEMANTIC = "visual_semantic"     # Meaning/Concept (Named Vector: 'semantic') 
                                            # Used for memes, art, visual poetry
    TEXT_OCR = "text_ocr"                   # Text extraction (Property 'ocr_text' or transmutation to TextSpace)
    
    # --- AUDIO SPACE (Music, Voice, Sound) ---
    AUDIO_CLAP = "audio_clap"               # Sound/Vibration (Named Vector: 'audio_clap')
    AUDIO_TRANSCRIPT = "audio_transcript"   # Speech/Lyrics (Named Vector: 'transcript_semantic')
    
    # --- TEXT & MEMORY ---
    TEXT_CHUNK = "text_chunk"               # TextSpace (Documents, articles)
    TEXT_SUMMARY = "text_summary"           # Summary text (Property, not vector)
    USER_MEMORY = "user_memory"             # MemorySpace (User notes, context)
    USER_MEMORY_REQUIRED = "user_memory_required"  # Marker: File requires user memory context (ON_HOLD until provided)

