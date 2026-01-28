"""
Celery Worker Tasks
===================

This module defines all asynchronous tasks for processing vector embeddings and AI operations.
Integrates with LLM Gateway API for embeddings and generative tasks, MinIO for file storage,
and implements dual-flow processing (automatic embeddings vs human-in-the-loop generation).
"""

import logging
import requests
import json
import io
from celery import Task
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path

from app.core.celery_app import app
from app.models.enums import VectorType, JobStatus, PrivacyLevel
from app.models.vector_status import VectorStatus
from app.models.asset import Asset
from shared.database import get_session
from shared.clients import get_minio_client
from worker.prompts import build_specialized_prompt

# ==========================================
# LOGGING CONFIGURATION
# ==========================================

# Configure logging at module level
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(asctime)s: %(levelname)s/%(name)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Log module load
logger.info("=" * 60)
logger.info("worker.tasks module loaded successfully")
logger.info("=" * 60)

# LLM Gateway Configuration - loaded from settings
from config.settings import get_settings
_settings = get_settings()
LLM_GATEWAY_BASE_URL = f"{_settings.LLM_GATEWAY_URL}/v1"
MINIO_BUCKET = _settings.MINIO_BUCKET
WHISPER_API_URL = _settings.WHISPER_API_URL

logger.info(f"   LLM Gateway: {LLM_GATEWAY_BASE_URL}")
logger.info(f"   MinIO Bucket: {MINIO_BUCKET}")
logger.info(f"   Whisper API: {WHISPER_API_URL}")


# ==========================================
# HELPER FUNCTIONS
# ==========================================

def get_privacy_mode(asset: Asset, force_strict: bool = False) -> str:
    """
    Determine privacy mode for LLM Gateway based on asset privacy level.
    
    Args:
        asset: Asset with privacy_level
        force_strict: If True, always return "strict" (used when user_context.convert_to_memory=True)
        
    Returns:
        "strict" for strict_local or when forced, "flexible" for public_cloud
    """
    if force_strict:
        return "strict"
    if asset.privacy_level == PrivacyLevel.STRICT_LOCAL.value:
        return "strict"
    else:
        return "flexible"


def get_sidecar_data(asset: Asset) -> Optional[Dict[str, Any]]:
    """
    Download and parse sidecar JSON from MinIO.
    
    Args:
        asset: Asset with sidecar_path
        
    Returns:
        Parsed sidecar dict or None if failed
    """
    minio_client = get_minio_client()
    try:
        response = minio_client.get_object(Bucket=MINIO_BUCKET, Key=asset.sidecar_path)
        return json.loads(response['Body'].read().decode('utf-8'))
    except Exception as e:
        logger.warning(f"Could not read sidecar {asset.sidecar_path}: {e}")
        return None


def get_user_context_from_sidecar(sidecar_data: Optional[Dict]) -> Dict[str, Any]:
    """
    Extract user_context from sidecar data.
    
    Returns dict with:
        - content: str or None
        - convert_to_memory: bool
        - force_strict: bool (True if convert_to_memory is True)
    """
    if not sidecar_data:
        return {"content": None, "convert_to_memory": False, "force_strict": False}
    
    user_context = sidecar_data.get("user_context", {})
    content = user_context.get("content")
    convert_to_memory = user_context.get("convert_to_memory", False)
    
    return {
        "content": content,
        "convert_to_memory": convert_to_memory,
        "force_strict": convert_to_memory  # If convert_to_memory, force strict mode
    }


def get_audio_options_from_sidecar(sidecar_data: Optional[Dict]) -> Dict[str, Any]:
    """
    Extract audio_processing_options from sidecar data.
    
    Returns dict with audio options or empty dict if not present.
    """
    if not sidecar_data:
        return {}
    
    return sidecar_data.get("audio_processing_options", {})


def call_whisper_api(file_content: bytes, filename: str) -> str:
    """
    Call Whisper API (speaches) to transcribe audio file.
    
    Uses OpenAI-compatible API format:
    POST /v1/audio/transcriptions
    
    Args:
        file_content: Audio file bytes
        filename: Original filename (for extension detection)
        
    Returns:
        Transcribed text string
        
    Raises:
        Exception: If API call fails
    """
    logger.info(f"🎙️ Calling Whisper API for transcription...")
    logger.debug(f"   File size: {len(file_content)} bytes")
    logger.debug(f"   Filename: {filename}")
    
    url = f"{WHISPER_API_URL}/v1/audio/transcriptions"
    
    # Prepare multipart form data
    files = {
        'file': (filename, file_content, 'audio/mpeg')
    }
    
    data = {
        'model': 'whisper-1',  # Default model for speaches
        'response_format': 'json',
        'language': 'es'  # Spanish - adjust as needed
    }
    
    try:
        response = requests.post(
            url,
            files=files,
            data=data,
            timeout=300  # 5 minutes for long audio files
        )
        
        if response.status_code == 200:
            result = response.json()
            transcribed_text = result.get('text', '')
            logger.info(f"   ✅ Whisper transcription successful: {len(transcribed_text)} chars")
            return transcribed_text
        else:
            error_msg = f"Whisper API error: {response.status_code} - {response.text}"
            logger.error(f"   ❌ {error_msg}")
            raise Exception(error_msg)
            
    except requests.exceptions.Timeout:
        error_msg = "Whisper API timeout - audio file may be too long"
        logger.error(f"   ❌ {error_msg}")
        raise Exception(error_msg)
    except requests.exceptions.ConnectionError:
        error_msg = f"Cannot connect to Whisper API at {WHISPER_API_URL}"
        logger.error(f"   ❌ {error_msg}")
        raise Exception(error_msg)
    except Exception as e:
        logger.error(f"   ❌ Whisper API call failed: {e}")
        raise


def download_file_from_minio(asset: Asset) -> bytes:
    """
    Download file content from MinIO.
    
    Args:
        asset: Asset with minio_path
        
    Returns:
        File content as bytes
        
    Raises:
        Exception: If file download fails
    """
    minio_client = get_minio_client()
    
    try:
        logger.debug(f"📦 Downloading from MinIO bucket={MINIO_BUCKET}, path={asset.minio_path}")
        # Note: get_minio_client() returns a boto3 S3 client, so we use Bucket/Key params
        response = minio_client.get_object(Bucket=MINIO_BUCKET, Key=asset.minio_path)
        file_content = response['Body'].read()
        
        logger.info(f"✅ Downloaded {len(file_content)} bytes from MinIO: {asset.minio_path}")
        return file_content
    except Exception as e:
        logger.error(f"❌ Failed to download from MinIO: {asset.minio_path}")
        logger.error(f"   Error: {type(e).__name__}: {e}")
        raise Exception(f"MinIO download failed: {str(e)}")


def update_sidecar_metadata(
    asset: Asset, 
    field_path: str, 
    value: Any,
    add_workflow_step: Optional[str] = None
) -> None:
    """
    Update sidecar JSON metadata in MinIO.
    
    Supports nested path updates using dot notation:
    - 'data_layers.intermediate_results.ocr_text'
    - 'data_layers.raw_debug_data.llm_response'
    
    Args:
        asset: Asset with sidecar_path
        field_path: Dot-separated path to field (e.g., 'data_layers.intermediate_results.ocr_text')
        value: Value to set
        add_workflow_step: Optional step name to add to workflow_state.steps_completed
    """
    minio_client = get_minio_client()
    
    try:
        # Download existing sidecar (boto3 style)
        response = minio_client.get_object(Bucket=MINIO_BUCKET, Key=asset.sidecar_path)
        sidecar_data = json.loads(response['Body'].read().decode('utf-8'))
        
        # Navigate to nested field using dot notation
        keys = field_path.split('.')
        target = sidecar_data
        for key in keys[:-1]:
            if key not in target:
                target[key] = {}
            target = target[key]
        
        # Set the value
        target[keys[-1]] = value
        
        # Update workflow state
        if add_workflow_step:
            if 'workflow_state' not in sidecar_data:
                sidecar_data['workflow_state'] = {'steps_completed': []}
            if 'steps_completed' not in sidecar_data['workflow_state']:
                sidecar_data['workflow_state']['steps_completed'] = []
            if add_workflow_step not in sidecar_data['workflow_state']['steps_completed']:
                sidecar_data['workflow_state']['steps_completed'].append(add_workflow_step)
            sidecar_data['workflow_state']['last_updated'] = datetime.utcnow().isoformat()
        
        # Upload updated sidecar (boto3 style)
        sidecar_bytes = json.dumps(sidecar_data, indent=2, default=str).encode('utf-8')
        minio_client.put_object(
            Bucket=MINIO_BUCKET,
            Key=asset.sidecar_path,
            Body=sidecar_bytes,
            ContentType='application/json'
        )
        
        logger.info(f"Updated sidecar {asset.sidecar_path}: {field_path}")
        if add_workflow_step:
            logger.info(f"   Added workflow step: {add_workflow_step}")
    except Exception as e:
        logger.error(f"Failed to update sidecar: {asset.sidecar_path} - {e}")
        raise


# ==========================================
# LLM GATEWAY API CALLS
# ==========================================

def call_image_embeddings_api(file_content: bytes, filename: str) -> Dict[str, Any]:
    """
    Call LLM Gateway image embeddings endpoint.
    
    Args:
        file_content: Image file bytes
        filename: Original filename
        
    Returns:
        API response dict with embedding
        
    Raises:
        Exception: If API call fails
    """
    url = f"{LLM_GATEWAY_BASE_URL}/embeddings/image"
    
    files = {
        'file': (filename, file_content, 'image/*')
    }
    params = {
        'normalize': 'true'
    }
    
    logger.info(f"📡 Calling Image Embeddings API: {url}")
    logger.debug(f"   Filename: {filename}, Size: {len(file_content)} bytes")
    
    try:
        response = requests.post(url, files=files, params=params, timeout=30)
        logger.debug(f"   Response status: {response.status_code}")
        
        if response.status_code != 200:
            error_detail = response.text[:500] if response.text else "No response body"
            logger.error(f"❌ Image embeddings API returned {response.status_code}")
            logger.error(f"   Response: {error_detail}")
            raise Exception(f"Image embeddings API returned {response.status_code}: {error_detail}")
        
        result = response.json()
        logger.info(f"✅ Image embeddings API success")
        return result
    except requests.exceptions.ConnectionError as e:
        logger.error(f"❌ Cannot connect to LLM Gateway at {url}")
        logger.error(f"   Is the LLM Gateway running? Try: http://localhost:8765/health")
        raise Exception(f"LLM Gateway connection failed - is it running at localhost:8765?")
    except requests.exceptions.Timeout as e:
        logger.error(f"❌ LLM Gateway timeout after 30 seconds")
        raise Exception(f"LLM Gateway timeout - server may be overloaded")
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Image embeddings API failed: {type(e).__name__}: {e}")
        raise Exception(f"Image embeddings API error: {str(e)}")


def call_text_embeddings_api(text: str) -> Dict[str, Any]:
    """
    Call LLM Gateway text embeddings endpoint.
    
    Args:
        text: Text to embed
        
    Returns:
        API response dict with embedding
        
    Raises:
        Exception: If API call fails
    """
    url = f"{LLM_GATEWAY_BASE_URL}/embeddings/text"
    
    payload = {
        'text': text,
        'normalize': True
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Text embeddings API failed: {e}")
        raise Exception(f"Text embeddings API error: {str(e)}")


def call_chat_completions_api(
    file_content: bytes,
    filename: str,
    task_type: str,
    privacy_mode: str,
    prompt: str
) -> Dict[str, Any]:
    """
    Call LLM Gateway chat completions endpoint for vision/OCR tasks.
    
    Uses multipart/form-data format with:
    - messages as JSON string (system + user)
    - files as file uploads
    - file_index to reference uploaded files in messages
    
    Args:
        file_content: Image file bytes
        filename: Original filename
        task_type: "ocr" or "vision"
        privacy_mode: "strict" or "flexible"
        prompt: System prompt with instructions for the model
        
    Returns:
        API response dict with generated text
        
    Raises:
        Exception: If API call fails
    """
    url = f"{LLM_GATEWAY_BASE_URL}/chat/completions"
    
    # Build messages with system prompt + user image
    # System message contains the instructions/schema
    # User message contains the image to analyze
    
    # Different user message based on task type
    if task_type == "ocr":
        user_text = "Extract all visible text from this image."
    else:
        user_text = "Analyze this image and return the structured JSON."
    
    messages = [
        {
            "role": "system",
            "content": prompt
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_text},
                {"type": "image", "file_index": 0}  # Reference first file
            ]
        }
    ]
    
    # Form data - messages must be JSON string
    data = {
        "task": task_type,
        "privacy_mode": privacy_mode,
        "messages": json.dumps(messages),
        "temperature": 0.0 if task_type == "ocr" else 0.3  # Lower temp for more consistent JSON
    }
    
    # Only request JSON format for vision tasks, not OCR
    if task_type == "vision":
        data["response_format"] = json.dumps({"type": "json_object"})
    
    # Determine mime type from filename
    ext = filename.lower().split('.')[-1]
    mime_types = {
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'gif': 'image/gif',
        'webp': 'image/webp'
    }
    mime_type = mime_types.get(ext, 'image/jpeg')
    
    # Files as list of tuples
    files = [
        ("files", (filename, file_content, mime_type))
    ]
    
    # ==========================================
    # DEBUG LOGGING - Detailed request info
    # ==========================================
    logger.info(f"📡 Calling Chat Completions API: {url}")
    logger.info(f"   Task: {task_type}, Privacy: {privacy_mode}")
    logger.info(f"   Temperature: {data.get('temperature')}")
    logger.info(f"   Response Format: {data.get('response_format', 'None')}")
    logger.info(f"   File: {filename} ({len(file_content)} bytes, {mime_type})")
    
    # Log prompt details
    logger.info(f"   📝 PROMPT LENGTH: {len(prompt)} characters")
    logger.info(f"   📝 PROMPT FIRST 200 CHARS: {prompt[:200]}...")
    logger.info(f"   📝 PROMPT LAST 100 CHARS: ...{prompt[-100:]}")
    
    # Parse messages to verify structure
    parsed_messages = json.loads(data["messages"])
    logger.info(f"   📨 MESSAGES COUNT: {len(parsed_messages)}")
    for i, msg in enumerate(parsed_messages):
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        if isinstance(content, str):
            content_preview = content[:150] + "..." if len(content) > 150 else content
            logger.info(f"   📨 MESSAGE[{i}] role={role}, content_length={len(content)}")
            logger.info(f"      Content preview: {content_preview}")
        elif isinstance(content, list):
            logger.info(f"   📨 MESSAGE[{i}] role={role}, content_type=multimodal, parts={len(content)}")
            for j, part in enumerate(content):
                logger.info(f"      Part[{j}]: {part}")
    
    # Log full data dict (except messages which we already logged)
    logger.debug(f"   📦 FULL DATA KEYS: {list(data.keys())}")
    # ==========================================
    
    try:
        response = requests.post(url, data=data, files=files, timeout=120)
        logger.info(f"   Response status: {response.status_code}")
        
        if response.status_code != 200:
            error_detail = response.text[:500] if response.text else "No response body"
            logger.error(f"❌ Chat completions API returned {response.status_code}")
            logger.error(f"   Response: {error_detail}")
            raise Exception(f"Chat completions API returned {response.status_code}: {error_detail}")
        
        result = response.json()
        
        # Log response details
        response_content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
        logger.info(f"✅ Chat completions API success")
        logger.info(f"   📥 RESPONSE LENGTH: {len(response_content)} chars")
        logger.info(f"   📥 RESPONSE FIRST 300 CHARS: {response_content[:300]}...")
        
        return result
    except requests.exceptions.ConnectionError as e:
        logger.error(f"❌ Cannot connect to LLM Gateway at {url}")
        logger.error(f"   Is the LLM Gateway running? Try: http://localhost:8765/health")
        raise Exception(f"LLM Gateway connection failed - is it running at localhost:8765?")
    except requests.exceptions.Timeout as e:
        logger.error(f"❌ LLM Gateway timeout after 120 seconds")
        raise Exception(f"LLM Gateway timeout - server may be overloaded")
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Chat completions API failed: {type(e).__name__}: {e}")
        raise Exception(f"Chat completions API error: {str(e)}")


# ==========================================
# BASE TASK CLASS
# ==========================================

class DatabaseTask(Task):
    """Base task class with database session management."""
    
    def __call__(self, *args, **kwargs):
        """Execute task with automatic session cleanup."""
        return super().__call__(*args, **kwargs)


# ==========================================
# MAIN TASK PROCESSOR
# ==========================================

@app.task(bind=True, base=DatabaseTask, max_retries=3)
def process_vector_task(self, vector_status_id: str):
    """
    Main task processor that routes to specific handlers based on VectorType.
    
    This is the entry point called by the dispatcher endpoint.
    It updates the VectorStatus, performs the AI processing, and stores results.
    
    Workflow:
    1. Fetch VectorStatus and Asset from DB
    2. Update status to PROCESSING
    3. Route to appropriate handler based on VectorType
    4. Update status to COMPLETED or REVIEW_REQUIRED
    5. Handle errors with retry logic
    
    Args:
        vector_status_id: UUID of the VectorStatus to process
        
    Returns:
        dict: Processing results with status and metadata
        
    Raises:
        Exception: Propagates processing errors for retry logic
    """
    logger.info("=" * 80)
    logger.info(f"🚀 TASK RECEIVED - Starting processing for VectorStatus: {vector_status_id}")
    logger.info("=" * 80)
    
    # Get database session
    logger.debug("📊 Getting database session...")
    session = next(get_session())
    vector_status = None  # Initialize here to avoid UnboundLocalError
    
    try:
        # Fetch VectorStatus and Asset
        logger.debug(f"🔍 Fetching VectorStatus from database: {vector_status_id}")
        vector_status = session.get(VectorStatus, vector_status_id)
        
        if not vector_status:
            logger.error(f"❌ VectorStatus NOT FOUND in database: {vector_status_id}")
            raise ValueError(f"VectorStatus {vector_status_id} not found")
        
        logger.info(f"✅ VectorStatus found: {vector_status.id}")
        logger.info(f"   - Current status: {vector_status.status}")
        logger.info(f"   - Vector type: {vector_status.vector_type}")
        logger.info(f"   - Asset ID: {vector_status.asset_id}")
        
        logger.debug(f"🔍 Fetching Asset from database: {vector_status.asset_id}")
        asset = session.get(Asset, vector_status.asset_id)
        
        if not asset:
            logger.error(f"❌ Asset NOT FOUND in database: {vector_status.asset_id}")
            raise ValueError(f"Asset {vector_status.asset_id} not found")
        
        logger.info(f"✅ Asset found: {asset.id}")
        logger.info(f"   - Filename: {asset.filename}")
        logger.info(f"   - Privacy level: {asset.privacy_level}")
        logger.info(f"   - MIME type: {asset.mime_type}")
        logger.info(f"   - MinIO path: {asset.minio_path}")
        
        # Update status to PROCESSING
        logger.info(f"📝 Updating VectorStatus to PROCESSING...")
        old_status = vector_status.status
        vector_status.status = JobStatus.PROCESSING
        vector_status.updated_at = datetime.utcnow()
        session.commit()
        logger.info(f"✅ Status updated: {old_status} → PROCESSING")
        
        logger.info(
            f"🎯 Processing Asset {asset.id} ({asset.filename}) | "
            f"VectorType: {vector_status.vector_type.value} | "
            f"Privacy: {asset.privacy_level}"
        )
        
        # Route to specific processor based on VectorType
        result = None
        handler_name = None
        
        logger.info(f"🔀 Routing to handler based on VectorType: {vector_status.vector_type}")
        
        if vector_status.vector_type == VectorType.VISUAL_SIGLIP:
            handler_name = "process_visual_siglip_task"
            logger.info(f"→ Calling {handler_name}")
            result = process_visual_siglip_task(asset, vector_status, session)
        elif vector_status.vector_type == VectorType.VISUAL_SEMANTIC:
            handler_name = "process_visual_semantic_task"
            logger.info(f"→ Calling {handler_name}")
            result = process_visual_semantic_task(asset, vector_status, session)
        elif vector_status.vector_type == VectorType.TEXT_OCR:
            handler_name = "process_text_ocr_task"
            logger.info(f"→ Calling {handler_name}")
            result = process_text_ocr_task(asset, vector_status, session)
        elif vector_status.vector_type == VectorType.TEXT_CHUNK:
            handler_name = "process_text_chunk_task"
            logger.info(f"→ Calling {handler_name}")
            result = process_text_chunk_task(asset, vector_status, session)
        elif vector_status.vector_type == VectorType.TEXT_SUMMARY:
            handler_name = "process_text_summary_task"
            logger.info(f"→ Calling {handler_name}")
            result = process_text_summary_task(asset, vector_status, session)
        elif vector_status.vector_type == VectorType.AUDIO_CLAP:
            handler_name = "process_audio_clap_task"
            logger.info(f"→ Calling {handler_name}")
            result = process_audio_clap_task(asset, vector_status, session)
        elif vector_status.vector_type == VectorType.AUDIO_TRANSCRIPT:
            handler_name = "process_audio_transcript_task"
            logger.info(f"→ Calling {handler_name}")
            result = process_audio_transcript_task(asset, vector_status, session)
        elif vector_status.vector_type == VectorType.USER_MEMORY:
            handler_name = "process_user_memory_task"
            logger.info(f"→ Calling {handler_name}")
            result = process_user_memory_task(asset, vector_status, session)
        else:
            logger.error(f"❌ Unknown VectorType: {vector_status.vector_type}")
            raise ValueError(f"Unknown VectorType: {vector_status.vector_type}")
        
        logger.info(f"✅ Handler {handler_name} completed")
        logger.debug(f"   Result: {result}")
        
        # Result contains: status, weaviate_uuid (optional), processing_time
        final_status = result.get('status', 'COMPLETED')
        
        logger.info(f"📝 Updating final status to: {final_status}")
        
        if final_status == 'REVIEW_REQUIRED':
            vector_status.status = JobStatus.REVIEW_REQUIRED
            logger.info(f"✅ VectorStatus {vector_status_id} moved to REVIEW_REQUIRED")
            logger.info(f"   → Human review needed before Weaviate insertion")
        else:
            vector_status.status = JobStatus.COMPLETED
            vector_status.weaviate_uuid = result.get('weaviate_uuid')
            logger.info(f"✅ VectorStatus {vector_status_id} COMPLETED")
            logger.info(f"   → Weaviate UUID: {result.get('weaviate_uuid')}")
        
        vector_status.updated_at = datetime.utcnow()
        session.commit()
        logger.info(f"✅ Database updated successfully")
        
        logger.info("=" * 80)
        logger.info(f"✅ TASK COMPLETED SUCCESSFULLY - {vector_status_id}")
        logger.info("=" * 80)
        
        return {
            'status': final_status,
            'vector_status_id': vector_status_id,
            'weaviate_uuid': result.get('weaviate_uuid'),
            'processing_time': result.get('processing_time', 0)
        }
        
    except Exception as exc:
        logger.error("=" * 80)
        logger.error(f"❌ TASK FAILED - {vector_status_id}")
        logger.error(f"   Error type: {type(exc).__name__}")
        logger.error(f"   Error message: {str(exc)}")
        logger.error("=" * 80)
        
        # Log full stack trace
        import traceback
        logger.error("Full traceback:")
        logger.error(traceback.format_exc())
        
        # Update status to FAILED
        if vector_status:
            logger.info(f"📝 Updating VectorStatus to FAILED...")
            vector_status.status = JobStatus.FAILED
            vector_status.error_message = str(exc)[:500]  # Limit length
            vector_status.updated_at = datetime.utcnow()
            session.commit()
            logger.info(f"✅ Error message saved to database")
        else:
            logger.warning(f"⚠️  Cannot update VectorStatus (not found in DB)")
        
        # Calculate retry delay
        retry_count = self.request.retries
        retry_delay = 60 * (2 ** retry_count)
        logger.warning(f"🔄 Retry #{retry_count + 1} scheduled in {retry_delay} seconds")
        
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=retry_delay)
    
    finally:
        logger.debug("🔒 Closing database session")
        session.close()


# ==========================================
# AUTOMATIC FLOW - EMBEDDINGS (SIGLIP, TEXT_CHUNK)
# ==========================================

def process_visual_siglip_task(asset: Asset, vector_status: VectorStatus, session) -> dict:
    """
    Process visual embeddings using SigLIP model via LLM Gateway.
    
    Flow: AUTOMATIC - Embeddings → Weaviate → COMPLETED
    """
    logger.info(f"📸 Processing VISUAL_SIGLIP for {asset.filename}")
    
    # Download file from MinIO
    logger.debug(f"   → Downloading from MinIO: {asset.minio_path}")
    file_content = download_file_from_minio(asset)
    logger.info(f"   ✅ Downloaded {len(file_content)} bytes")
    
    # Call LLM Gateway image embeddings API
    logger.info(f"   → Calling LLM Gateway: POST /v1/embeddings/image")
    result = call_image_embeddings_api(file_content, asset.filename)
    logger.info(f"   ✅ API call successful")
    logger.debug(f"   Response: {result}")
    
    # TODO: Store embedding in Weaviate
    # For now, simulate Weaviate storage
    weaviate_uuid = f"weaviate-siglip-{asset.id}"
    logger.info(f"   [SIMULATED] Storing in Weaviate...")
    logger.info(f"   ✅ Stored SigLIP embedding: {weaviate_uuid}")
    
    return {
        'status': 'completed',
        'weaviate_uuid': weaviate_uuid,
        'processing_time': result.get('processing_time', 0.5)
    }


def process_text_chunk_task(asset: Asset, vector_status: VectorStatus, session) -> dict:
    """
    Process text chunks: embedding + LLM metadata extraction.
    
    Flow:
    1. Read text content from MinIO
    2. Generate text embedding → store in Weaviate (TextChunks collection)
    3. Call LLM with text prompt for metadata extraction (entities, tags, summary)
    4. Store result in sidecar.data_layers.raw_debug_data
    5. Return REVIEW_REQUIRED for human curation
    """
    logger.info(f"Processing TEXT_CHUNK for {asset.filename}")
    
    # Get sidecar data and user context
    sidecar_data = get_sidecar_data(asset)
    user_context = get_user_context_from_sidecar(sidecar_data)
    
    # Determine privacy mode - force strict if user wants to convert to memory
    privacy_mode = get_privacy_mode(asset, force_strict=user_context["force_strict"])
    if user_context["force_strict"]:
        logger.info(f"   🔒 Privacy forced to STRICT (convert_to_memory=True)")
    
    # Step 1: Read text content from MinIO
    try:
        text_content = download_file_from_minio(asset).decode('utf-8')
        logger.info(f"   Read text content: {len(text_content)} chars")
    except Exception as e:
        logger.error(f"   Failed to read text: {e}")
        raise
    
    # Step 2: Generate embedding and store in Weaviate
    embedding_result = call_text_embeddings_api(text_content)
    weaviate_uuid = f"weaviate-text-{asset.id}"
    logger.info(f"   [SIMULATED] Stored text embedding in Weaviate: {weaviate_uuid}")
    
    # Update sidecar with embedding info
    update_sidecar_metadata(
        asset,
        'data_layers.vectors_generated',
        ['text_chunk'],
        add_workflow_step='embedding'
    )
    
    # Step 3: Build external context for prompt
    external_context = {'document_text': text_content[:2000]}  # First 2000 chars for context
    
    if sidecar_data:
        user_notes = sidecar_data.get('user_notes')
        if user_notes:
            external_context['user_notes'] = user_notes
        
        # Add new user_context content
        if user_context["content"]:
            external_context['user_context'] = user_context["content"]
    
    # Step 4: Call LLM with text prompt for metadata extraction
    prompt = build_specialized_prompt(
        task_type="text",
        external_context=external_context
    )
    logger.info(f"   Built text analysis prompt: {len(prompt)} chars")
    
    # For text, we send the content via a simple chat completion (no files)
    try:
        url = f"{LLM_GATEWAY_BASE_URL}/chat/completions"
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Analyze this text and extract structured metadata:\n\n{text_content[:4000]}"}
        ]
        
        data = {
            "task": "chat",
            "privacy_mode": privacy_mode,
            "messages": json.dumps(messages),
            "temperature": 0.3,
            "response_format": json.dumps({"type": "json_object"})
        }
        
        response = requests.post(url, data=data, timeout=120)
        
        if response.status_code == 200:
            result = response.json()
            llm_response = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            
            # Try to parse as JSON
            try:
                parsed_json = json.loads(llm_response)
                logger.info(f"   ✅ LLM returned valid JSON with keys: {list(parsed_json.keys())}")
                update_sidecar_metadata(
                    asset,
                    'data_layers.raw_debug_data.text_analysis_json',
                    parsed_json,
                    add_workflow_step='text_analysis'
                )
            except json.JSONDecodeError:
                logger.warning(f"   ⚠️ LLM returned non-JSON, storing as raw")
                update_sidecar_metadata(
                    asset,
                    'data_layers.raw_debug_data.text_analysis_raw',
                    llm_response,
                    add_workflow_step='text_analysis'
                )
        else:
            logger.error(f"   LLM analysis failed: {response.status_code}")
            update_sidecar_metadata(
                asset,
                'data_layers.raw_debug_data.text_analysis_error',
                f"LLM returned {response.status_code}",
                add_workflow_step='text_analysis_failed'
            )
    except Exception as e:
        logger.error(f"   LLM text analysis failed: {e}")
    
    logger.info(f"   Text chunk processed - awaiting human review")
    
    return {
        'status': 'REVIEW_REQUIRED',
        'weaviate_uuid': weaviate_uuid,
        'message': 'Embedding stored, LLM metadata extracted - awaiting review'
    }


# ==========================================
# HUMAN-IN-THE-LOOP FLOW - GENERATIVE (VISUAL_SEMANTIC, OCR)
# ==========================================

def process_visual_semantic_task(asset: Asset, vector_status: VectorStatus, session) -> dict:
    """
    Process visual semantic understanding using multimodal LLM via LLM Gateway.
    
    Uses specialized vision prompt for structured JSON extraction.
    Flow: VISION ANALYSIS → Sidecar (raw_debug_data) → REVIEW_REQUIRED
    """
    logger.info(f"Processing VISUAL_SEMANTIC for {asset.filename}")
    
    # Get sidecar data and user context
    sidecar_data = get_sidecar_data(asset)
    user_context = get_user_context_from_sidecar(sidecar_data)
    
    # Determine privacy mode - force strict if user wants to convert to memory
    privacy_mode = get_privacy_mode(asset, force_strict=user_context["force_strict"])
    if user_context["force_strict"]:
        logger.info(f"   🔒 Privacy forced to STRICT (convert_to_memory=True)")
    
    # Download file from MinIO
    file_content = download_file_from_minio(asset)
    
    # Build external context for prompt
    external_context = {}
    
    # Add user notes from old field (backwards compat)
    if sidecar_data:
        user_notes = sidecar_data.get('user_notes')
        if user_notes:
            external_context['user_notes'] = user_notes
        
        # Add user context content (new field)
        if user_context["content"]:
            external_context['user_context'] = user_context["content"]
        
        # Add user voice description if available
        user_transcript = sidecar_data.get('data_layers', {}).get('intermediate_results', {}).get('user_context_transcript')
        if user_transcript:
            external_context['user_voice_description'] = user_transcript
    
    if external_context:
        logger.info(f"   Found user context: {list(external_context.keys())}")
    
    # Build specialized vision prompt
    logger.info(f"   🔧 Building specialized prompt...")
    logger.info(f"   🔧 external_context = {external_context}")
    
    prompt = build_specialized_prompt(
        task_type="vision",
        external_context=external_context if external_context else None
    )
    
    logger.info(f"   ✅ PROMPT BUILT: {len(prompt)} chars")
    logger.info(f"   🔍 PROMPT TYPE: {type(prompt)}")
    logger.info(f"   🔍 PROMPT IS EMPTY: {len(prompt) == 0}")
    if len(prompt) > 0:
        logger.info(f"   🔍 PROMPT STARTS WITH: '{prompt[:100]}'")
    else:
        logger.error(f"   ❌ PROMPT IS EMPTY! This is the bug!")
    
    # Call LLM Gateway chat completions API
    logger.info(f"   📤 Calling call_chat_completions_api with:")
    logger.info(f"      - file_content: {len(file_content)} bytes")
    logger.info(f"      - filename: {asset.filename}")
    logger.info(f"      - task_type: vision")
    logger.info(f"      - privacy_mode: {privacy_mode}")
    logger.info(f"      - prompt length: {len(prompt)}")
    
    result = call_chat_completions_api(
        file_content=file_content,
        filename=asset.filename,
        task_type="vision",
        privacy_mode=privacy_mode,
        prompt=prompt
    )
    
    # Extract generated text (should be JSON)
    generated_text = result.get('choices', [{}])[0].get('message', {}).get('content', '')
    
    if not generated_text:
        raise Exception("No content generated by LLM")
    
    # Try to parse as JSON for validation
    try:
        parsed_json = json.loads(generated_text)
        logger.info(f"   ✅ LLM returned valid JSON with keys: {list(parsed_json.keys())}")
        # Store parsed JSON in raw_debug_data for now
        update_sidecar_metadata(
            asset, 
            'data_layers.raw_debug_data.visual_semantic_json', 
            parsed_json,
            add_workflow_step='visual_semantic'
        )
    except json.JSONDecodeError:
        logger.warning(f"   ⚠️ LLM returned non-JSON text, storing as raw")
        # Store raw text if not valid JSON
        update_sidecar_metadata(
            asset, 
            'data_layers.raw_debug_data.visual_semantic_raw', 
            generated_text,
            add_workflow_step='visual_semantic'
        )
    
    logger.info(f"Stored visual semantic result in sidecar for Asset {asset.id} - awaiting human review")
    
    return {
        'status': 'REVIEW_REQUIRED',
        'weaviate_uuid': None,
        'processing_time': result.get('processing_time', 2.5)
    }


def process_text_ocr_task(asset: Asset, vector_status: VectorStatus, session) -> dict:
    """
    Extract text from images using OCR via LLM Gateway.
    
    Handles both:
    - Single file OCR (standard asset)
    - Multi-file OCR (merged asset with is_merged=True)
    
    For merged assets, downloads all source files and sends them together.
    
    Flow: HUMAN-IN-THE-LOOP - OCR → Sidecar (ai_draft) → REVIEW_REQUIRED
    """
    logger.info(f"Processing TEXT_OCR for {asset.filename}")
    logger.info(f"   is_merged: {asset.is_merged}")
    
    # Determine privacy mode
    privacy_mode = get_privacy_mode(asset)
    
    minio_client = get_minio_client()
    
    if asset.is_merged:
        # Multi-file OCR: Get source files from sidecar
        logger.info("📂 Merged asset detected - downloading multiple source files")
        
        try:
            # Read sidecar to get source_files
            response = minio_client.get_object(Bucket=MINIO_BUCKET, Key=asset.sidecar_path)
            sidecar_data = json.loads(response['Body'].read().decode('utf-8'))
            source_files = sidecar_data.get('source_files', [])
            
            if not source_files:
                raise Exception("No source_files found in sidecar for merged asset")
            
            logger.info(f"   Found {len(source_files)} source files in sidecar")
            
            # Download all source files
            files_data = []
            for sf in source_files:
                file_path = sf.get('path') if isinstance(sf, dict) else sf
                filename = sf.get('filename', file_path.split('/')[-1]) if isinstance(sf, dict) else file_path.split('/')[-1]
                
                logger.debug(f"   → Downloading: {file_path}")
                file_response = minio_client.get_object(Bucket=MINIO_BUCKET, Key=file_path)
                content = file_response['Body'].read()
                
                files_data.append({
                    'filename': filename,
                    'content': content
                })
                logger.info(f"   ✅ Downloaded {len(content)} bytes: {filename}")
            
            # Call OCR API with multiple files
            result = call_chat_completions_api_multi_file(
                files_data=files_data,
                task_type="ocr",
                privacy_mode=privacy_mode,
                prompt="Extrae TODO el texto visible de estas imágenes. Combina el texto en orden y mantén el formato natural de lectura."
            )
            
        except Exception as e:
            logger.error(f"❌ Failed to process merged OCR: {e}")
            raise
    else:
        # Single file OCR
        file_content = download_file_from_minio(asset)
        
        prompt = "Extrae TODO el texto visible en esta imagen. Mantén el formato y orden de lectura natural."
        result = call_chat_completions_api(
            file_content=file_content,
            filename=asset.filename,
            task_type="ocr",
            privacy_mode=privacy_mode,
            prompt=prompt
        )
    
    # Extract generated text
    extracted_text = result.get('choices', [{}])[0].get('message', {}).get('content', '')
    
    if not extracted_text:
        raise Exception("No text extracted by OCR")
    
    # Update sidecar with OCR text in intermediate_results layer
    update_sidecar_metadata(
        asset, 
        'data_layers.intermediate_results.ocr_text', 
        extracted_text,
        add_workflow_step='ocr'
    )
    
    logger.info(f"Stored OCR text in intermediate_results for Asset {asset.id} - awaiting LLM synthesis")
    
    return {
        'status': 'REVIEW_REQUIRED',
        'weaviate_uuid': None,
        'processing_time': result.get('processing_time', 1.5)
    }


def call_chat_completions_api_multi_file(
    files_data: list,
    task_type: str,
    privacy_mode: str,
    prompt: str
) -> dict:
    """
    Call LLM Gateway chat completions with multiple files.
    
    Args:
        files_data: List of dicts with 'filename' and 'content' keys
        task_type: "ocr" or "vision"
        privacy_mode: "strict" or "flexible"
        prompt: System prompt with instructions
        
    Returns:
        API response dict
    """
    url = f"{LLM_GATEWAY_BASE_URL}/chat/completions"
    
    # Different user message based on task type
    if task_type == "ocr":
        user_text = "Extract all visible text from these images."
    else:
        user_text = "Analyze these images and return the structured JSON."
    
    # Build user content with multiple file_index references
    user_content = [{"type": "text", "text": user_text}]
    for i in range(len(files_data)):
        user_content.append({"type": "image", "file_index": i})
    
    # System message for instructions, user message for images
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": user_content}
    ]
    
    # Form data
    data = {
        "task": task_type,
        "privacy_mode": privacy_mode,
        "messages": json.dumps(messages),
        "temperature": 0.0 if task_type == "ocr" else 0.3
    }
    
    # Only request JSON format for vision tasks, not OCR
    if task_type == "vision":
        data["response_format"] = json.dumps({"type": "json_object"})
    
    # Files as list of tuples
    files = []
    for fd in files_data:
        ext = fd['filename'].lower().split('.')[-1]
        mime_types = {
            'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
            'png': 'image/png', 'gif': 'image/gif', 'webp': 'image/webp'
        }
        mime = mime_types.get(ext, 'image/jpeg')
        files.append(("files", (fd['filename'], fd['content'], mime)))
    
    logger.info(f"📡 Calling Chat Completions API (multi-file): {url}")
    logger.info(f"   Task: {task_type}, Privacy: {privacy_mode}, Files: {len(files_data)}")
    
    try:
        response = requests.post(url, data=data, files=files, timeout=180)  # Longer timeout for multi-file
        logger.debug(f"   Response status: {response.status_code}")
        
        if response.status_code != 200:
            error_detail = response.text[:500] if response.text else "No response body"
            logger.error(f"❌ Chat completions API returned {response.status_code}")
            logger.error(f"   Response: {error_detail}")
            raise Exception(f"Chat completions API returned {response.status_code}: {error_detail}")
        
        result = response.json()
        logger.info(f"✅ Chat completions API (multi-file) success")
        return result
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Chat completions API failed: {e}")
        raise Exception(f"Chat completions API error: {str(e)}")


# ==========================================
# PLACEHOLDER PROCESSORS (NOT YET IMPLEMENTED)
# ==========================================

def process_text_summary_task(asset: Asset, vector_status: VectorStatus, session) -> dict:
    """
    Generate text summary and LLM analysis for the asset (MANDATORY PREREQUISITE).
    
    This is the FIRST task that runs for ALL assets.
    Other tasks cannot be dispatched until TEXT_SUMMARY is COMPLETED.
    
    Based on MIME type, this task:
    - Images: Calls vision LLM with specialized prompt (like VISUAL_SEMANTIC)
    - Text: Calls chat LLM with text analysis prompt (like TEXT_CHUNK)
    - Audio: Transcribes with Whisper + calls chat LLM with audio prompt (like AUDIO_TRANSCRIPT)
    
    All analysis results are stored in sidecar.data_layers.text_summary_analysis
    """
    logger.info(f"Processing TEXT_SUMMARY for {asset.filename}")
    logger.info(f"   MIME type: {asset.mime_type}")
    
    # Get sidecar data and user context
    sidecar_data = get_sidecar_data(asset)
    user_context = get_user_context_from_sidecar(sidecar_data)
    
    # Determine privacy mode
    privacy_mode = get_privacy_mode(asset, force_strict=user_context["force_strict"])
    if user_context["force_strict"]:
        logger.info(f"   🔒 Privacy forced to STRICT (convert_to_memory=True)")
    else:
        logger.info(f"   Privacy mode: {privacy_mode}")
    
    analysis_result = {}
    summary_text = ""
    
    try:
        # ============================================
        # IMAGE FILES - Use Vision LLM
        # ============================================
        if asset.mime_type and asset.mime_type.startswith("image/"):
            logger.info("   🖼️ Image file detected - calling Vision LLM")
            
            # Download file from MinIO
            file_content = download_file_from_minio(asset)
            logger.info(f"   Downloaded {len(file_content)} bytes")
            
            # Build external context
            external_context = {}
            if sidecar_data:
                user_notes = sidecar_data.get('user_notes')
                if user_notes:
                    external_context['user_notes'] = user_notes
                if user_context["content"]:
                    external_context['user_context'] = user_context["content"]
            
            # Build specialized vision prompt
            prompt = build_specialized_prompt(
                task_type="vision",
                external_context=external_context if external_context else None
            )
            logger.info(f"   Built vision prompt: {len(prompt)} chars")
            
            # Call LLM Gateway with vision task
            result = call_chat_completions_api(
                file_content=file_content,
                filename=asset.filename,
                task_type="vision",
                privacy_mode=privacy_mode,
                prompt=prompt
            )
            
            # Extract response
            generated_text = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            
            if generated_text:
                try:
                    analysis_result = json.loads(generated_text)
                    summary_text = analysis_result.get('summary', analysis_result.get('description', str(analysis_result)[:200]))
                    logger.info(f"   ✅ Vision LLM returned JSON with keys: {list(analysis_result.keys())}")
                except json.JSONDecodeError:
                    analysis_result = {"raw_response": generated_text}
                    summary_text = generated_text[:200]
                    logger.warning(f"   ⚠️ Vision LLM returned non-JSON, storing raw")
            else:
                raise Exception("No content generated by Vision LLM")
        
        # ============================================
        # TEXT FILES - Use Text Analysis LLM
        # ============================================
        elif asset.mime_type and asset.mime_type.startswith("text/"):
            logger.info("   📄 Text file detected - calling Text Analysis LLM")
            
            # Download and read text
            text_content = download_file_from_minio(asset).decode('utf-8')
            logger.info(f"   Read {len(text_content)} chars")
            
            # Build external context
            external_context = {'document_text': text_content[:2000]}
            if sidecar_data:
                user_notes = sidecar_data.get('user_notes')
                if user_notes:
                    external_context['user_notes'] = user_notes
                if user_context["content"]:
                    external_context['user_context'] = user_context["content"]
            
            # Build specialized text prompt
            prompt = build_specialized_prompt(
                task_type="text",
                external_context=external_context
            )
            logger.info(f"   Built text analysis prompt: {len(prompt)} chars")
            
            # Call LLM for text analysis
            url = f"{LLM_GATEWAY_BASE_URL}/chat/completions"
            messages = [
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Analyze this text and extract structured metadata:\n\n{text_content[:4000]}"}
            ]
            
            data = {
                "task": "chat",
                "privacy_mode": privacy_mode,
                "messages": json.dumps(messages),
                "temperature": 0.3,
                "response_format": json.dumps({"type": "json_object"})
            }
            
            response = requests.post(url, data=data, timeout=120)
            
            if response.status_code == 200:
                result = response.json()
                llm_response = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                
                try:
                    analysis_result = json.loads(llm_response)
                    summary_text = analysis_result.get('summary', analysis_result.get('description', str(analysis_result)[:200]))
                    logger.info(f"   ✅ Text LLM returned JSON with keys: {list(analysis_result.keys())}")
                except json.JSONDecodeError:
                    analysis_result = {"raw_response": llm_response}
                    summary_text = llm_response[:200]
                    logger.warning(f"   ⚠️ Text LLM returned non-JSON")
            else:
                raise Exception(f"Text analysis LLM returned {response.status_code}")
        
        # ============================================
        # AUDIO FILES - Transcribe + Analysis LLM
        # ============================================
        elif asset.mime_type and asset.mime_type.startswith("audio/"):
            logger.info("   🎵 Audio file detected - transcribing + analysis")
            
            # Get audio options from sidecar
            audio_options = get_audio_options_from_sidecar(sidecar_data)
            logger.info(f"   Audio options: {audio_options}")
            
            # Get transcription
            transcribed_text = None
            
            if audio_options.get("has_provided_lyrics") and audio_options.get("provided_lyrics_text"):
                transcribed_text = audio_options["provided_lyrics_text"]
                logger.info(f"   📜 Using user-provided transcript ({len(transcribed_text)} chars)")
            elif audio_options.get("use_whisper", True):  # Default to Whisper
                logger.info(f"   🎙️ Calling Whisper API for transcription...")
                try:
                    file_content = download_file_from_minio(asset)
                    transcribed_text = call_whisper_api(file_content, asset.filename)
                    logger.info(f"   ✅ Whisper completed: {len(transcribed_text)} chars")
                except Exception as e:
                    logger.error(f"   ❌ Whisper failed: {e}")
                    transcribed_text = f"[Transcription failed: {str(e)}]"
            else:
                transcribed_text = "[No transcription available - Whisper disabled]"
            
            # Store transcript
            update_sidecar_metadata(
                asset,
                'data_layers.intermediate_results.audio_transcript',
                transcribed_text,
                add_workflow_step='audio_transcript'
            )
            
            # Build context for audio analysis
            external_context = {}
            if transcribed_text and not transcribed_text.startswith("["):
                external_context['lyrics_or_speech'] = transcribed_text
            
            if audio_options.get("is_voice_note"):
                external_context['audio_type'] = 'voice_note'
            elif audio_options.get("is_song"):
                external_context['audio_type'] = 'song'
            
            if user_context["content"]:
                external_context['user_context'] = user_context["content"]
            if sidecar_data and sidecar_data.get('user_notes'):
                external_context['user_notes'] = sidecar_data['user_notes']
            
            # Build audio prompt and call LLM
            prompt = build_specialized_prompt(
                task_type="audio",
                external_context=external_context if external_context else None
            )
            logger.info(f"   Built audio analysis prompt: {len(prompt)} chars")
            
            if transcribed_text and not transcribed_text.startswith("["):
                url = f"{LLM_GATEWAY_BASE_URL}/chat/completions"
                messages = [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"Analyze this audio transcript:\n\n{transcribed_text[:4000]}"}
                ]
                
                data = {
                    "task": "chat",
                    "privacy_mode": privacy_mode,
                    "messages": json.dumps(messages),
                    "temperature": 0.3,
                    "response_format": json.dumps({"type": "json_object"})
                }
                
                response = requests.post(url, data=data, timeout=120)
                
                if response.status_code == 200:
                    result = response.json()
                    llm_response = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                    
                    try:
                        analysis_result = json.loads(llm_response)
                        analysis_result['transcript'] = transcribed_text
                        summary_text = analysis_result.get('summary', transcribed_text[:200])
                        logger.info(f"   ✅ Audio LLM returned JSON with keys: {list(analysis_result.keys())}")
                    except json.JSONDecodeError:
                        analysis_result = {"raw_response": llm_response, "transcript": transcribed_text}
                        summary_text = llm_response[:200]
                else:
                    analysis_result = {"transcript": transcribed_text, "error": f"LLM returned {response.status_code}"}
                    summary_text = transcribed_text[:200]
            else:
                analysis_result = {"transcript": transcribed_text}
                summary_text = transcribed_text[:200] if transcribed_text else "Audio file (no transcript)"
        
        # ============================================
        # VIDEO FILES - Basic metadata (no vision yet)
        # ============================================
        elif asset.mime_type and asset.mime_type.startswith("video/"):
            logger.info("   🎬 Video file detected - creating metadata summary")
            analysis_result = {
                "type": "video",
                "filename": asset.filename,
                "size_bytes": asset.size_bytes,
                "mime_type": asset.mime_type
            }
            summary_text = f"Video file: {asset.filename} ({asset.size_bytes} bytes)"
        
        # ============================================
        # OTHER FILES - Generic handling
        # ============================================
        else:
            logger.info("   📎 Unknown type - creating generic summary")
            analysis_result = {
                "type": "unknown",
                "filename": asset.filename,
                "size_bytes": asset.size_bytes,
                "mime_type": asset.mime_type or "unknown"
            }
            summary_text = f"File: {asset.filename} ({asset.size_bytes} bytes)"
        
        # Store analysis result in sidecar
        update_sidecar_metadata(
            asset,
            'data_layers.text_summary_analysis',
            analysis_result,
            add_workflow_step='text_summary_analysis'
        )
        
        # Store summary text
        update_sidecar_metadata(
            asset,
            'data_layers.text_summary',
            summary_text,
            add_workflow_step='text_summary'
        )
        
        logger.info(f"   ✅ TEXT_SUMMARY completed: {summary_text[:100]}...")
        
    except Exception as e:
        logger.error(f"   ❌ TEXT_SUMMARY processing error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
        # Store error info in sidecar for debugging
        analysis_result = {"error": str(e)}
        summary_text = f"Error processing {asset.filename}: {str(e)[:100]}"
        
        try:
            update_sidecar_metadata(
                asset,
                'data_layers.text_summary_analysis',
                analysis_result,
                add_workflow_step='text_summary_error'
            )
            update_sidecar_metadata(
                asset,
                'data_layers.text_summary',
                summary_text,
                add_workflow_step='text_summary_error'
            )
        except Exception as sidecar_error:
            logger.warning(f"   Could not update sidecar with error: {sidecar_error}")
        
        # RE-RAISE the exception so the task goes to FAILED status
        raise
    
    return {
        'status': 'REVIEW_REQUIRED',
        'weaviate_uuid': None,
        'processing_time': 2.0
    }


def process_audio_clap_task(asset: Asset, vector_status: VectorStatus, session) -> dict:
    """Process audio using CLAP model (PLACEHOLDER)."""
    logger.info(f"[PLACEHOLDER] Processing AUDIO_CLAP for {asset.filename}")
    
    return {
        'status': 'completed',
        'weaviate_uuid': f'mock-clap-{asset.id}',
        'processing_time': 2.0
    }


def process_audio_transcript_task(asset: Asset, vector_status: VectorStatus, session) -> dict:
    """
    Transcribe audio to text and analyze using specialized audio prompt.
    
    Uses audio_processing_options from sidecar:
    - use_whisper: If True, call Whisper API for auto transcription
    - has_provided_lyrics: If True, use provided_lyrics_text instead of Whisper
    - is_voice_note / is_song: Affects LLM analysis prompt
    """
    logger.info(f"Processing AUDIO_TRANSCRIPT for {asset.filename}")
    
    # Get sidecar data and contexts
    sidecar_data = get_sidecar_data(asset)
    user_context = get_user_context_from_sidecar(sidecar_data)
    audio_options = get_audio_options_from_sidecar(sidecar_data)
    
    # Determine privacy mode - force strict if user wants to convert to memory
    privacy_mode = get_privacy_mode(asset, force_strict=user_context["force_strict"])
    if user_context["force_strict"]:
        logger.info(f"   🔒 Privacy forced to STRICT (convert_to_memory=True)")
    
    # Log audio options
    logger.info(f"   🎵 Audio options: {audio_options}")
    
    # Determine transcription source
    transcribed_text = None
    
    if audio_options.get("has_provided_lyrics") and audio_options.get("provided_lyrics_text"):
        # User provided the lyrics/transcript
        transcribed_text = audio_options["provided_lyrics_text"]
        logger.info(f"   📜 Using user-provided transcript ({len(transcribed_text)} chars)")
    elif audio_options.get("use_whisper"):
        # Call Whisper API (speaches)
        logger.info(f"   🎙️ Calling Whisper API for transcription...")
        try:
            file_content = download_file_from_minio(asset)
            transcribed_text = call_whisper_api(file_content, asset.filename)
            logger.info(f"   ✅ Whisper transcription completed: {len(transcribed_text)} chars")
        except Exception as e:
            logger.error(f"   ❌ Whisper transcription failed: {e}")
            transcribed_text = f"[Whisper transcription failed: {str(e)}]"
    else:
        logger.warning(f"   ⚠️ No transcript source specified (use_whisper=False, no provided lyrics)")
        transcribed_text = "[No transcription available]"
    
    # Store transcript in sidecar
    if transcribed_text:
        update_sidecar_metadata(
            asset,
            'data_layers.intermediate_results.audio_transcript',
            transcribed_text,
            add_workflow_step='audio_transcript'
        )
    
    # Build external context for LLM analysis
    external_context = {}
    
    if transcribed_text and transcribed_text != "[No transcription available]":
        external_context['lyrics_or_speech'] = transcribed_text
    
    if audio_options.get("is_voice_note"):
        external_context['audio_type'] = 'voice_note'
    elif audio_options.get("is_song"):
        external_context['audio_type'] = 'song'
    
    if user_context["content"]:
        external_context['user_context'] = user_context["content"]
    
    if sidecar_data:
        user_notes = sidecar_data.get('user_notes')
        if user_notes:
            external_context['user_notes'] = user_notes
    
    # Build specialized audio prompt
    prompt = build_specialized_prompt(
        task_type="audio",
        external_context=external_context if external_context else None
    )
    logger.info(f"   Built audio analysis prompt: {len(prompt)} chars")
    
    # Call LLM for audio analysis
    if transcribed_text and transcribed_text != "[No transcription available]":
        try:
            url = f"{LLM_GATEWAY_BASE_URL}/chat/completions"
            messages = [
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Analyze this audio transcript:\n\n{transcribed_text[:4000]}"}
            ]
            
            data = {
                "task": "chat",
                "privacy_mode": privacy_mode,
                "messages": json.dumps(messages),
                "temperature": 0.3,
                "response_format": json.dumps({"type": "json_object"})
            }
            
            response = requests.post(url, data=data, timeout=120)
            
            if response.status_code == 200:
                result = response.json()
                llm_response = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                
                try:
                    parsed_json = json.loads(llm_response)
                    logger.info(f"   ✅ LLM extracted audio metadata: {list(parsed_json.keys())}")
                    update_sidecar_metadata(
                        asset,
                        'data_layers.raw_debug_data.audio_analysis_json',
                        parsed_json,
                        add_workflow_step='audio_analysis'
                    )
                except json.JSONDecodeError:
                    logger.warning(f"   ⚠️ LLM returned non-JSON, storing raw")
                    update_sidecar_metadata(
                        asset,
                        'data_layers.raw_debug_data.audio_analysis_raw',
                        llm_response,
                        add_workflow_step='audio_analysis'
                    )
            else:
                logger.warning(f"   ⚠️ LLM call failed: {response.status_code}")
        except Exception as e:
            logger.warning(f"   ⚠️ LLM analysis failed: {e}")
    
    logger.info(f"   ✅ AUDIO_TRANSCRIPT processed - awaiting review")
    
    return {
        'status': 'REVIEW_REQUIRED',
        'weaviate_uuid': f'mock-transcript-{asset.id}',
        'processing_time': 3.0
    }


def process_user_memory_task(asset: Asset, vector_status: VectorStatus, session) -> dict:
    """
    Process user memory/notes - stores personal context in Weaviate UserMemory collection.
    
    USER_MEMORY tasks are ALWAYS processed with STRICT privacy mode.
    
    Flow:
    1. Read user_context from sidecar
    2. Generate text embedding of user context → store in Weaviate (UserMemory collection)
    3. Call LLM with strict mode for metadata extraction (tags, entities, summary)
    4. Store analysis in sidecar
    5. Return COMPLETED
    """
    logger.info(f"Processing USER_MEMORY for {asset.filename}")
    
    # USER_MEMORY is ALWAYS strict - no cloud processing for personal memories
    privacy_mode = "strict"
    logger.info(f"   🔒 USER_MEMORY always uses STRICT mode")
    
    # Get sidecar data
    sidecar_data = get_sidecar_data(asset)
    user_context = get_user_context_from_sidecar(sidecar_data)
    
    if not user_context["content"]:
        logger.warning(f"   ⚠️ No user_context.content found in sidecar")
        # Try to get from user_notes as fallback
        user_notes = sidecar_data.get("user_notes", "") if sidecar_data else ""
        if not user_notes:
            logger.error(f"   ❌ No user content found for USER_MEMORY task")
            return {
                'status': 'FAILED',
                'weaviate_uuid': None,
                'error': 'No user content found'
            }
        memory_content = user_notes
    else:
        memory_content = user_context["content"]
    
    logger.info(f"   📝 Memory content: {len(memory_content)} chars")
    
    # Step 1: Generate embedding of memory content
    try:
        embedding_result = call_text_embeddings_api(memory_content)
        logger.info(f"   ✅ Generated embedding for memory content")
    except Exception as e:
        logger.error(f"   ❌ Failed to generate embedding: {e}")
        raise
    
    # Step 2: Store in Weaviate UserMemory collection
    weaviate_uuid = f"weaviate-memory-{asset.id}-{vector_status.id}"
    logger.info(f"   [SIMULATED] Stored in Weaviate UserMemory: {weaviate_uuid}")
    
    # Step 3: Call LLM for metadata extraction (always strict)
    external_context = {
        'user_memory': memory_content,
        'associated_file': asset.filename
    }
    
    prompt = build_specialized_prompt(
        task_type="text",  # Use text analysis for memories
        external_context=external_context
    )
    
    try:
        url = f"{LLM_GATEWAY_BASE_URL}/chat/completions"
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Extract metadata from this personal memory/note:\n\n{memory_content[:4000]}"}
        ]
        
        data = {
            "task": "chat",
            "privacy_mode": privacy_mode,  # Always strict
            "messages": json.dumps(messages),
            "temperature": 0.3,
            "response_format": json.dumps({"type": "json_object"})
        }
        
        response = requests.post(url, data=data, timeout=120)
        
        if response.status_code == 200:
            result = response.json()
            llm_response = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            
            try:
                parsed_json = json.loads(llm_response)
                logger.info(f"   ✅ LLM extracted metadata: {list(parsed_json.keys())}")
                update_sidecar_metadata(
                    asset,
                    'data_layers.raw_debug_data.memory_analysis_json',
                    parsed_json,
                    add_workflow_step='memory_analysis'
                )
            except json.JSONDecodeError:
                logger.warning(f"   ⚠️ LLM returned non-JSON, storing raw")
                update_sidecar_metadata(
                    asset,
                    'data_layers.raw_debug_data.memory_analysis_raw',
                    llm_response,
                    add_workflow_step='memory_analysis'
                )
        else:
            logger.warning(f"   ⚠️ LLM call failed: {response.status_code}")
    except Exception as e:
        logger.warning(f"   ⚠️ LLM analysis failed (non-fatal): {e}")
    
    logger.info(f"   ✅ USER_MEMORY processed successfully")
    
    return {
        'status': 'COMPLETED',
        'weaviate_uuid': weaviate_uuid,
        'processing_time': 1.0
    }

