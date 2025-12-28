from enum import Enum

# ==========================================
# JOB STATUS ENUM
# ==========================================
class JobStatus(str, Enum):
    """
    Lifecycle states for asset processing tasks.
    
    Flow: ON_HOLD → PENDING → PROCESSING → COMPLETED/FAILED/REJECTED
    """
    ON_HOLD = "on_hold"           # Initial state (Staging - awaiting manual trigger)
    PENDING = "pending"           # Queued in Redis for worker processing
    PROCESSING = "processing"     # Worker is actively processing
    COMPLETED = "completed"       # Successfully finished
    FAILED = "failed"             # Error during processing
    REJECTED = "rejected"         # Cancelled by user


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
