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

logger.info(f"   LLM Gateway: {LLM_GATEWAY_BASE_URL}")
logger.info(f"   MinIO Bucket: {MINIO_BUCKET}")


# ==========================================
# HELPER FUNCTIONS
# ==========================================

def get_privacy_mode(asset: Asset) -> str:
    """
    Determine privacy mode for LLM Gateway based on asset privacy level.
    
    Args:
        asset: Asset with privacy_level
        
    Returns:
        "strict" for strict_local, "flexible" for public_cloud
    """
    if asset.privacy_level == PrivacyLevel.STRICT_LOCAL.value:
        return "strict"
    else:
        return "flexible"


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
    
    # Determine privacy mode
    privacy_mode = "flexible" if asset.privacy_level == PrivacyLevel.PUBLIC_CLOUD else "strict"
    
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
    
    # Step 3: Get user context from sidecar
    minio_client = get_minio_client()
    external_context = {'document_text': text_content[:2000]}  # First 2000 chars for context
    try:
        response = minio_client.get_object(Bucket=MINIO_BUCKET, Key=asset.sidecar_path)
        sidecar_data = json.loads(response['Body'].read().decode('utf-8'))
        user_notes = sidecar_data.get('user_notes')
        if user_notes:
            external_context['user_notes'] = user_notes
    except Exception as e:
        logger.warning(f"   Could not read sidecar for context: {e}")
    
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
    
    # Determine privacy mode
    privacy_mode = get_privacy_mode(asset)
    
    # Download file from MinIO
    file_content = download_file_from_minio(asset)
    
    # Get user context from sidecar (if available)
    minio_client = get_minio_client()
    external_context = None
    try:
        response = minio_client.get_object(Bucket=MINIO_BUCKET, Key=asset.sidecar_path)
        sidecar_data = json.loads(response['Body'].read().decode('utf-8'))
        
        # Build external context from sidecar data
        user_notes = sidecar_data.get('user_notes')
        user_transcript = sidecar_data.get('data_layers', {}).get('intermediate_results', {}).get('user_context_transcript')
        
        if user_notes or user_transcript:
            external_context = {}
            if user_notes:
                external_context['user_notes'] = user_notes
            if user_transcript:
                external_context['user_voice_description'] = user_transcript
            logger.info(f"   Found user context: {list(external_context.keys())}")
    except Exception as e:
        logger.warning(f"   Could not read sidecar for context: {e}")
    
    # Build specialized vision prompt
    logger.info(f"   🔧 Building specialized prompt...")
    logger.info(f"   🔧 external_context = {external_context}")
    
    prompt = build_specialized_prompt(
        task_type="vision",
        external_context=external_context
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
    """Generate text summaries (PLACEHOLDER)."""
    logger.info(f"[PLACEHOLDER] Processing TEXT_SUMMARY for {asset.filename}")
    
    return {
        'status': 'completed',
        'weaviate_uuid': f'mock-summary-{asset.id}',
        'processing_time': 1.0
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
    
    When implemented, will:
    1. Call Whisper API for transcription -> intermediate_results.audio_transcript
    2. Call LLM with audio prompt for semantic analysis -> raw_debug_data / ai_synthesis
    3. Return REVIEW_REQUIRED for human curation
    """
    logger.info(f"[PLACEHOLDER] Processing AUDIO_TRANSCRIPT for {asset.filename}")
    
    # TODO: When Whisper integration is ready:
    # 
    # Step 1: Transcribe audio
    # transcribed_text = call_whisper_api(file_content)
    # update_sidecar_metadata(
    #     asset,
    #     'data_layers.intermediate_results.audio_transcript',
    #     transcribed_text,
    #     add_workflow_step='audio_transcript'
    # )
    # 
    # Step 2: Analyze with specialized audio prompt
    # external_context = {'lyrics_or_speech': transcribed_text}
    # if user_notes:
    #     external_context['user_notes'] = user_notes
    # 
    # prompt = build_specialized_prompt(
    #     task_type="audio",
    #     external_context=external_context
    # )
    # 
    # result = call_llm_for_audio_analysis(prompt, transcribed_text)
    # parsed_json = json.loads(result)
    # 
    # update_sidecar_metadata(
    #     asset,
    #     'data_layers.raw_debug_data.audio_analysis_json',
    #     parsed_json,
    #     add_workflow_step='audio_analysis'
    # )
    
    return {
        'status': 'completed',
        'weaviate_uuid': f'mock-transcript-{asset.id}',
        'processing_time': 3.0
    }


def process_user_memory_task(asset: Asset, vector_status: VectorStatus, session) -> dict:
    """Process user memory/notes (PLACEHOLDER)."""
    logger.info(f"[PLACEHOLDER] Processing USER_MEMORY for {asset.filename}")
    
    return {
        'status': 'completed',
        'weaviate_uuid': f'mock-memory-{asset.id}',
        'processing_time': 0.5
    }
