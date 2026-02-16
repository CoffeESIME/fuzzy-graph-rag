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
import re
from celery import Task
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
from pathlib import Path

from app.core.celery_app import app
from app.models.enums import VectorType, JobStatus, PrivacyLevel
from app.models.vector_status import VectorStatus
from app.models.asset import Asset
from shared.database import get_session
from shared.clients import get_minio_client, get_neo4j_driver, get_weaviate_client
from worker.prompts import build_specialized_prompt
from worker.utils import (
    build_vector_content,
    generate_collection_uuid,
    determine_collection,
    determine_vector_name,
    ensure_digital_asset_node,
    link_memory_to_parent,
    stage_suggestions_in_inbox,
    upsert_to_weaviate
)

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
LLM_REQUEST_TIMEOUT = _settings.LLM_REQUEST_TIMEOUT  # Configurable timeout for long inference

logger.info(f"   LLM Gateway: {LLM_GATEWAY_BASE_URL}")
logger.info(f"   MinIO Bucket: {MINIO_BUCKET}")
logger.info(f"   Whisper API: {WHISPER_API_URL}")
logger.info(f"   LLM Timeout: {LLM_REQUEST_TIMEOUT}s")

# ==============================================================================
# TODO [OPTIMIZATION - LOCAL LLM PERFORMANCE]
# ==============================================================================
# Current State: Single 'heavy_gpu' queue for all inference tasks.
# Problem: Mixing Text (Llama3) and Vision (Llava/Qwen) tasks causes Ollama 
#          to constantly unload/reload models in VRAM ("Model Thrashing").
#
# FUTURE IMPLEMENTATION (Task Routing):
# 1. Define explicit routes in app.conf.task_routes:
#    - 'worker.tasks.process_text_rag' -> 'gpu_text_queue'
#    - 'worker.tasks.analyze_image'    -> 'gpu_vision_queue'
#
# 2. Update Worker Start Command to prioritize batching:
#    - command: celery -A app worker -Q gpu_text_queue,gpu_vision_queue,...
#    - This forces the worker to drain one queue (one model) before switching.
#
# Note: Skip this if migrating to Cloud APIs (OpenAI/Anthropic) as they auto-scale.
# ==============================================================================

# ==========================================
# IMAGE OPTIMIZATION FOR VLM
# ==========================================

def optimize_image_for_vlm(image_bytes: bytes, max_dimension: int = 1024) -> bytes:
    """
    Resize and optimize image for VLM to prevent ContextWindowExceeded.
    
    Qwen-VL uses dynamic resolution - large images (4K/HD) generate thousands of
    visual tokens, saturating context window and causing empty responses.
    
    Args:
        image_bytes: Original image bytes
        max_dimension: Maximum size for longest edge (default 1024px)
        
    Returns:
        Optimized image bytes (JPEG, quality 85)
    """
    try:
        from PIL import Image
        
        # Open image from bytes
        img = Image.open(io.BytesIO(image_bytes))
        original_size = img.size
        original_mode = img.mode
        
        # Convert to RGB for JPEG compatibility (handles RGBA, P, etc.)
        if img.mode in ('RGBA', 'P', 'LA', 'L'):
            # Create white background for transparent images
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = background
            else:
                img = img.convert('RGB')
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Resize if image exceeds max dimension
        width, height = img.size
        resized = False
        if width > max_dimension or height > max_dimension:
            img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
            resized = True
        
        # Compress to JPEG with quality 85
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85, optimize=True)
        optimized_bytes = buffer.getvalue()
        
        # Log optimization stats
        compression_ratio = len(optimized_bytes) / len(image_bytes) * 100
        logger.info(f"   🖼️ Image optimized for VLM:")
        logger.info(f"      Original: {original_size[0]}x{original_size[1]} ({original_mode}), {len(image_bytes):,} bytes")
        logger.info(f"      Optimized: {img.size[0]}x{img.size[1]} (RGB/JPEG), {len(optimized_bytes):,} bytes ({compression_ratio:.1f}%)")
        if resized:
            logger.info(f"      ⚠️ Resized from {original_size} to {img.size}")
        
        return optimized_bytes
        
    except ImportError:
        logger.warning("⚠️ PIL/Pillow not installed. Using original image (may cause context overflow).")
        return image_bytes
    except Exception as e:
        logger.warning(f"⚠️ Image optimization failed: {e}. Using original image.")
        return image_bytes


def optimize_image_for_ocr(image_bytes: bytes, max_dimension: int = 1024) -> bytes:
    """
    Optimize image specifically for OCR with aggressive preprocessing.
    
    Applies:
    1. Grayscale conversion - simplifies for text detection
    2. High contrast enhancement - removes shadows from curved pages
    3. Binarization (thresholding) - makes text black on white
    4. Resize to max dimension
    
    Args:
        image_bytes: Original image bytes
        max_dimension: Maximum size for longest edge (default 1024px)
        
    Returns:
        Optimized image bytes (JPEG, quality 95 for text clarity)
    """
    try:
        from PIL import Image, ImageEnhance
        
        # Open image from bytes
        img = Image.open(io.BytesIO(image_bytes))
        original_size = img.size
        original_mode = img.mode
        
        logger.info(f"   📄 OCR preprocessing: {original_size[0]}x{original_size[1]} ({original_mode})")
        
        # Step 1: Convert to Grayscale
        img = img.convert('L')
        logger.info(f"      → Converted to grayscale")
        
        # Step 2: Aggressive contrast enhancement (factor 2.5)
        # This removes shadows from curved book pages and defines letters
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.5)
        logger.info(f"      → Applied contrast enhancement (2.5x)")
        
        # Step 3: Binarization (Thresholding)
        # Converts everything not dark black to pure white
        # Threshold 128 is a good middle ground
        img = img.point(lambda p: 255 if p > 128 else 0)
        logger.info(f"      → Applied binarization (threshold=128)")
        
        # Step 4: Resize if image exceeds max dimension
        width, height = img.size
        resized = False
        if width > max_dimension or height > max_dimension:
            img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
            resized = True
            logger.info(f"      → Resized from {original_size} to {img.size}")
        
        # Convert back to RGB for JPEG (grayscale L mode works but RGB is more compatible)
        img = img.convert('RGB')
        
        # Compress to JPEG with high quality for text clarity
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=95, optimize=True)
        optimized_bytes = buffer.getvalue()
        
        # Log stats
        compression_ratio = len(optimized_bytes) / len(image_bytes) * 100
        logger.info(f"   📄 OCR image ready: {img.size[0]}x{img.size[1]}, {len(optimized_bytes):,} bytes ({compression_ratio:.1f}%)")
        
        return optimized_bytes
        
    except ImportError:
        logger.warning("⚠️ PIL/Pillow not installed. Using standard VLM optimization for OCR.")
        return optimize_image_for_vlm(image_bytes, max_dimension)
    except Exception as e:
        logger.warning(f"⚠️ OCR image optimization failed: {e}. Using standard VLM optimization.")
        return optimize_image_for_vlm(image_bytes, max_dimension)


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


def extract_json_from_llm_response(response: str) -> Tuple[Optional[Dict], str]:
    """
    Extract JSON from LLM response, handling common formatting issues.
    
    Many LLMs wrap their JSON responses in markdown code blocks or add
    explanatory text before/after the JSON. This function cleans that up.
    
    Handles:
    - Markdown code blocks (```json ... ``` or ``` ... ```)
    - Leading/trailing whitespace
    - Text before/after JSON object
    - Nested JSON objects (finds the outermost one)
    
    Args:
        response: Raw LLM response text
        
    Returns:
        Tuple of (parsed_dict, status_message):
        - If successful: (dict, "success")
        - If failed: (None, "error description")
    """
    if not response or not response.strip():
        return None, "Empty response"
    
    original_response = response
    
    # Step 1: Remove markdown code blocks
    # Pattern: ```json\n...\n``` or ```\n...\n```
    cleaned = response.strip()
    
    # Remove opening code block with optional language specifier
    cleaned = re.sub(r'^```(?:json|JSON)?\s*\n?', '', cleaned)
    # Remove closing code block
    cleaned = re.sub(r'\n?```\s*$', '', cleaned)
    cleaned = cleaned.strip()
    
    # Step 2: Try direct parse
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            logger.debug("   ✅ JSON parsed after markdown cleanup")
            return parsed, "success"
    except json.JSONDecodeError:
        pass
    
    # Step 3: Try to extract JSON object from text
    # Find the first { and last } to extract potential JSON
    first_brace = cleaned.find('{')
    last_brace = cleaned.rfind('}')
    
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        potential_json = cleaned[first_brace:last_brace + 1]
        try:
            parsed = json.loads(potential_json)
            if isinstance(parsed, dict):
                logger.debug("   ✅ JSON extracted from surrounding text")
                return parsed, "success"
        except json.JSONDecodeError:
            pass
    
    # Step 4: Try regex to find JSON object pattern (handles nested braces)
    # This is more aggressive - finds content between first { and matching }
    try:
        # Use a more sophisticated approach: count braces
        depth = 0
        start_idx = None
        for i, char in enumerate(cleaned):
            if char == '{':
                if depth == 0:
                    start_idx = i
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0 and start_idx is not None:
                    potential_json = cleaned[start_idx:i + 1]
                    try:
                        parsed = json.loads(potential_json)
                        if isinstance(parsed, dict):
                            logger.debug("   ✅ JSON extracted via brace matching")
                            return parsed, "success"
                    except json.JSONDecodeError:
                        continue
    except Exception as e:
        logger.debug(f"   Brace matching failed: {e}")
    
    # Step 5: Return failure with context
    preview = original_response[:200] + "..." if len(original_response) > 200 else original_response
    return None, f"Could not extract valid JSON. Response preview: {preview}"

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
    
    user_context = sidecar_data.get("user_context") or {}
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


def spawn_memory_asset(
    memory_content: str,
    parent_asset: Asset,
    session
) -> Optional[Asset]:
    """
    Create a new text Asset for user memory content.
    
    Replicates the `ingest_text` pattern from IngestService:
    1. Hash the content for deduplication
    2. Save text to master_records/texts/{hash}.txt
    3. Create sidecar in master_records/sidecars/{hash}.json
    4. Create Asset record
    5. Create VectorStatus records (TEXT_SUMMARY, USER_MEMORY) in ON_HOLD
    
    Args:
        memory_content: The user's note/memory text
        parent_asset: The original asset this memory is associated with
        session: Database session
        
    Returns:
        Created Asset or None if content already exists
    """
    import hashlib
    from datetime import datetime
    from sqlmodel import select
    from app.models import Asset, VectorStatus
    from app.models.enums import VectorType, JobStatus, PrivacyLevel
    
    logger.info(f"   🧠 Spawning memory asset from {parent_asset.filename}")
    
    # Calculate hash of content
    content_bytes = memory_content.encode('utf-8')
    content_hash = hashlib.sha256(content_bytes).hexdigest()
    
    # Check for duplicate content
    existing_asset = session.exec(
        select(Asset).where(Asset.file_hash == content_hash)
    ).first()
    
    if existing_asset:
        logger.info(f"   ⚠️ Memory content already exists as asset {existing_asset.id}")
        return None
    
    # Generate filename (with memory prefix and hash)
    safe_parent_name = "".join(c for c in parent_asset.filename if c.isalnum() or c in (' ', '-', '_')).strip()
    safe_parent_name = safe_parent_name.replace(' ', '_')[:30]
    filename = f"memory_{safe_parent_name}_{content_hash[:8]}.txt"
    
    # Save to MinIO
    minio_client = get_minio_client()
    text_path = f"master_records/texts/{content_hash}.txt"
    
    minio_client.put_object(
        Bucket=MINIO_BUCKET,
        Key=text_path,
        Body=content_bytes,
        ContentType="text/plain; charset=utf-8"
    )
    logger.info(f"   ✅ Saved memory text to MinIO: {text_path}")
    
    # Create sidecar JSON
    sidecar_path = f"master_records/sidecars/{content_hash}.json"
    sidecar_data = {
        "file_hash": content_hash,
        "original_filename": filename,
        "mime_type": "text/plain",
        "size_bytes": len(content_bytes),
        "upload_timestamp": datetime.utcnow().isoformat(),
        "operation": "memory_spawn",
        "user_notes": None,
        "discard_original": False,
        "vector_types": [VectorType.TEXT_SUMMARY.value, VectorType.USER_MEMORY.value],
        "is_merged": False,
        "source_files": [],
        "parent_asset_id": str(parent_asset.id),
        "parent_filename": parent_asset.filename,
        "privacy_config": {
            "level": PrivacyLevel.STRICT_LOCAL.value,
            "locked": True,
            "locked_reason": "User memory - always strict"
        },
        "workflow_state": {
            "steps_completed": ["memory_spawned"],
            "current_status": JobStatus.ON_HOLD.value
        },
        "data_layers": {
            "intermediate_results": {},
            "raw_debug_data": {}
        },
        "user_context": {
            "content": memory_content,
            "convert_to_memory": True
        }
    }
    
    sidecar_bytes = json.dumps(sidecar_data, indent=2, default=str).encode('utf-8')
    minio_client.put_object(
        Bucket=MINIO_BUCKET,
        Key=sidecar_path,
        Body=sidecar_bytes,
        ContentType="application/json"
    )
    logger.info(f"   ✅ Created sidecar: {sidecar_path}")
    
    # Create Asset record
    memory_asset = Asset(
        filename=filename,
        minio_path=text_path,
        mime_type="text/plain",
        size_bytes=len(content_bytes),
        file_hash=content_hash,
        is_merged=False,
        original_deleted=False,
        privacy_level=PrivacyLevel.STRICT_LOCAL.value,
        sidecar_path=sidecar_path
    )
    
    session.add(memory_asset)
    session.commit()
    session.refresh(memory_asset)
    logger.info(f"   ✅ Created Asset record: {memory_asset.id}")
    
    # Create VectorStatus records in ON_HOLD
    for vt in [VectorType.TEXT_SUMMARY, VectorType.USER_MEMORY]:
        vs = VectorStatus(
            asset_id=memory_asset.id,
            vector_type=vt,
            status=JobStatus.ON_HOLD
        )
        session.add(vs)
    session.commit()
    
    logger.info(f"   ✅ Created VectorStatus records (TEXT_SUMMARY, USER_MEMORY) in ON_HOLD")
    logger.info(f"   🧠 Memory asset spawned successfully: {memory_asset.filename}")
    
    return memory_asset



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
        "temperature": 0.0 if task_type == "ocr" else 0.5  # Lower temp for more consistent JSON
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
        response = requests.post(url, data=data, files=files, timeout=LLM_REQUEST_TIMEOUT)
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
        logger.error(f"❌ LLM Gateway timeout after {LLM_REQUEST_TIMEOUT} seconds")
        raise Exception(f"LLM Gateway timeout after {LLM_REQUEST_TIMEOUT}s - consider increasing LLM_REQUEST_TIMEOUT")
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

@app.task(
    bind=True, 
    base=DatabaseTask, 
    max_retries=3,
    soft_time_limit=900,  # 15 minutes - soft limit allows graceful cleanup
    time_limit=1000       # ~16.6 minutes - hard kill if soft limit fails
)
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
            # VISUAL_SEMANTIC consumes TEXT_SUMMARY analysis to create semantic embeddings
            handler_name = "process_text_chunk_task (via VISUAL_SEMANTIC)"
            logger.info(f"→ Routing VISUAL_SEMANTIC to process_text_chunk_task")
            result = process_text_chunk_task(asset, vector_status, session)
        
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
            # AUDIO_TRANSCRIPT consumes TEXT_SUMMARY analysis to create transcript embeddings
            handler_name = "process_text_chunk_task (via AUDIO_TRANSCRIPT)"
            logger.info(f"→ Routing AUDIO_TRANSCRIPT to process_text_chunk_task")
            result = process_text_chunk_task(asset, vector_status, session)
        
        elif vector_status.vector_type == VectorType.USER_MEMORY:
            # USER_MEMORY consumes TEXT_SUMMARY analysis to create memory embeddings
            handler_name = "process_text_chunk_task (via USER_MEMORY)"
            logger.info(f"→ Routing USER_MEMORY to process_text_chunk_task")
            result = process_text_chunk_task(asset, vector_status, session)
        
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
        elif final_status == 'waiting_user_input':
            # Asset requires user memory but none provided
            vector_status.status = JobStatus.REVIEW_REQUIRED
            vector_status.error_message = result.get('message', 'User memory input required')
            logger.info(f"⏸️ VectorStatus {vector_status_id} WAITING FOR USER INPUT")
            logger.info(f"   → User must provide memory context to continue")
        elif final_status == 'ON_HOLD':
            # Keep in ON_HOLD (e.g., dependency not yet ready)
            vector_status.status = JobStatus.ON_HOLD
            vector_status.error_message = result.get('message', 'Task kept on hold')
            logger.info(f"⏸️ VectorStatus {vector_status_id} kept ON_HOLD")
            logger.info(f"   → {result.get('message', 'Waiting for dependencies')}")
        elif final_status == 'FAILED':
            vector_status.status = JobStatus.FAILED
            vector_status.error_message = result.get('error_message', 'Task failed')
            logger.error(f"❌ VectorStatus {vector_status_id} FAILED")
            logger.error(f"   → {result.get('error_message')}")
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
    
    This is a PURE EMBEDDING task - no LLM analysis, no entity extraction.
    SigLIP generates visual embeddings directly from the image bytes.
    
    Flow:
    A. Download image from MinIO
    B. Neo4j MERGE: Ensure DigitalAsset node exists
    C. Call SigLIP embedding API
    D. Weaviate UPSERT with deterministic UUID (VisualSpace, vector: 'visual')
    E. Return COMPLETED
    """
    logger.info(f"📸 Processing VISUAL_SIGLIP for {asset.filename}")
    
    # ========================================
    # STEP A: DOWNLOAD IMAGE FROM MINIO
    # ========================================
    logger.debug(f"   → Downloading from MinIO: {asset.minio_path}")
    file_content = download_file_from_minio(asset)
    logger.info(f"   ✅ Downloaded {len(file_content)} bytes")
    
    # ========================================
    # STEP B: NEO4J MERGE - ENSURE DIGITAL ASSET NODE EXISTS
    # ========================================
    try:
        neo4j_driver = get_neo4j_driver()
        asset_metadata = {
            "filename": asset.filename,
            "mime_type": asset.mime_type,
            "inbox_id": str(asset.id)
        }
        ensure_digital_asset_node(neo4j_driver, asset.file_hash, asset_metadata)
    except Exception as e:
        logger.warning(f"   ⚠️ Neo4j sync failed (non-fatal): {e}")
        # Continue processing even if Neo4j fails
    
    # ========================================
    # STEP C: CALL SIGLIP EMBEDDING API
    # ========================================
    logger.info(f"   → Calling LLM Gateway: POST /v1/embeddings/image")
    result = call_image_embeddings_api(file_content, asset.filename)
    embedding_vector = result.get('embedding', [])
    
    if not embedding_vector:
        logger.error(f"   ❌ No embedding returned from SigLIP API")
        return {
            'status': 'FAILED',
            'error_message': 'SigLIP API returned empty vector'
        }
    
    logger.info(f"   ✅ SigLIP embedding generated: {len(embedding_vector)} dimensions")
    
    # ========================================
    # STEP D: WEAVIATE UPSERT WITH DETERMINISTIC UUID
    # ========================================
    collection_name = "VisualSpace"
    weaviate_uuid = generate_collection_uuid(asset.file_hash, collection_name)
    vector_name = "visual"  # Named vector for SigLIP embeddings
    
    try:
        weaviate_client = get_weaviate_client()
        
        properties = {
            "neo4j_hash": asset.file_hash,
            "inbox_id": str(asset.id),
            "filename": asset.filename,
            "mime_type": asset.mime_type,
            "file_size": len(file_content)
        }
        
        upsert_success = upsert_to_weaviate(
            client=weaviate_client,
            collection_name=collection_name,
            weaviate_uuid=weaviate_uuid,
            properties=properties,
            vector=embedding_vector,
            vector_name=vector_name
        )
        
        if upsert_success:
            logger.info(f"   💾 Weaviate UPSERT successful: {collection_name}/{weaviate_uuid[:8]}...")
        else:
            logger.warning(f"   ⚠️ Weaviate UPSERT returned False")
            
    except Exception as e:
        logger.error(f"   ❌ Weaviate upsert failed: {e}")
        return {
            'status': 'FAILED',
            'error_message': f'Weaviate upsert failed: {e}'
        }
    
    logger.info(f"   ✅ VISUAL_SIGLIP completed successfully")
    
    return {
        'status': 'COMPLETED',
        'weaviate_uuid': weaviate_uuid,
        'collection': collection_name,
        'vector_dimensions': len(embedding_vector),
        'message': f'SigLIP embedding stored in {collection_name}'
    }


def process_text_chunk_task(asset: Asset, vector_status: VectorStatus, session) -> dict:
    """
    Process text chunks: PURE CONSUMER of pre-existing LLM analysis.
    
    IMPORTANT: This task does NOT call the LLM. It assumes a prior task 
    (TEXT_SUMMARY) already generated the analysis JSON in the sidecar.
    
    Flow:
    A. Validate sidecar has analysis_json (dependency check)
    B. Read raw text content from MinIO
    C. Neo4j MERGE: Ensure DigitalAsset node exists
    D. Build Super String with Vector Factory
    E. Generate embedding from Super String
    F. Weaviate UPSERT with deterministic UUID
    G. Neo4j: Link extracted entities to asset
    H. Update sidecar with vector info
    I. Return COMPLETED
    """
    logger.info(f"Processing TEXT_CHUNK for {asset.filename}")
    
    # ========================================
    # STEP A: DEPENDENCY VALIDATION
    # ========================================
    sidecar_data = get_sidecar_data(asset)
    
    if not sidecar_data:
        logger.error(f"   ❌ No sidecar found for asset {asset.id}")
        return {
            'status': 'FAILED',
            'error_message': 'Missing sidecar - cannot process without metadata'
        }
    
    # Look for analysis JSON in common locations (Prioritize H-I-T-L manual outputs)
    data_layers = sidecar_data.get('data_layers', {})
    analysis_json = (
        data_layers.get('analysis_json') or 
        data_layers.get('raw_debug_data', {}).get('visual_semantic_json') or  # <--- H-I-T-L Visual
        data_layers.get('raw_debug_data', {}).get('memory_analysis_json') or  # <--- H-I-T-L Memory
        data_layers.get('text_summary_analysis') or                           # <--- Auto-Ingest
        data_layers.get('raw_debug_data', {}).get('text_analysis_json')
    )
    
    # Extract graph_core early to prevent UnboundLocalError
    graph_core = analysis_json.get('graph_core', {}) if analysis_json else {}
    
    if not analysis_json:
        logger.error(f"   ❌ No prior analysis found in sidecar for asset {asset.id}")
        logger.error(f"   💡 TEXT_SUMMARY must run before TEXT_CHUNK")
        return {
            'status': 'FAILED',
            'error_message': 'Missing dependency: No analysis_json in sidecar. Run TEXT_SUMMARY first.'
        }
    
    logger.info(f"   ✅ Found prior analysis with keys: {list(analysis_json.keys())}")
    
    # ========================================
    # STEP B: READ RAW CONTENT (TEXT ONLY)
    # ========================================
    # For images/audio, we don't need the raw file - just the analysis_json
    # Only text files need to be read and decoded
    text_content = ""
    
    # Detect content type from analysis_json to decide if we need raw text
    is_text_content = "text_specifics" in analysis_json or "memory_analysis" in analysis_json
    is_audio_with_transcript = "audio_specifics" in analysis_json
    
    # SAFETY CHECK: If asset is binary (image/audio), do NOT try to read it as text
    # even if analysis_json hints at text (LLM hallucination or schema mismatch)
    is_binary_asset = asset.mime_type and (asset.mime_type.startswith("image/") or asset.mime_type.startswith("audio/"))
    
    if is_text_content and not is_binary_asset:
        # Text files: decode as UTF-8
        try:
            text_content = download_file_from_minio(asset).decode('utf-8')
            logger.info(f"   📄 Read text content: {len(text_content)} chars")
        except Exception as e:
            logger.error(f"   ❌ Failed to read text: {e}")
            raise
    elif is_audio_with_transcript:
        # Audio files: try to get transcript from sidecar or intermediate results
        data_layers = sidecar_data.get('data_layers', {})
        text_content = (
            data_layers.get('intermediate_results', {}).get('audio_transcript', '') or
            analysis_json.get('audio_specifics', {}).get('lyrics_summary', '')
        )
        logger.info(f"   🎵 Using transcript from sidecar: {len(text_content)} chars")
    else:
        # Images: no raw text needed - use OCR if available
        ocr_text = analysis_json.get('visual_specifics', {}).get('ocr_text', '')
        text_content = ocr_text or ""
        logger.info(f"   🖼️ Image file - using OCR text: {len(text_content)} chars")
    
    # ========================================
    # STEP C: NEO4J MERGE - ENSURE DIGITAL ASSET NODE EXISTS
    # ========================================
    neo4j_driver = None
    try:
        neo4j_driver = get_neo4j_driver()
        asset_metadata = {
            "filename": asset.filename,
            "mime_type": asset.mime_type,
            "inbox_id": str(asset.id)  # Using asset ID as inbox reference
        }
        ensure_digital_asset_node(neo4j_driver, asset.file_hash, asset_metadata)
        
        # Check if this is a spawned memory with a parent asset
        is_memory_spawn = sidecar_data.get("operation") == "memory_spawn"
        parent_hash = None
        
        if is_memory_spawn:
            # Get parent asset hash from sidecar
            parent_asset_id = sidecar_data.get("parent_asset_id")
            if parent_asset_id:
                # Fetch parent asset to get its file_hash
                from sqlmodel import select
                parent_asset = session.exec(
                    select(Asset).where(Asset.id == parent_asset_id)
                ).first()
                
                if parent_asset:
                    parent_hash = parent_asset.file_hash
                    # Link memory to parent in Neo4j
                    link_memory_to_parent(
                        neo4j_driver, 
                        memory_hash=asset.file_hash, 
                        parent_hash=parent_hash,
                        memory_filename=asset.filename
                    )
                else:
                    logger.warning(f"   ⚠️ Parent asset {parent_asset_id} not found in DB")
                    
    except Exception as e:
        logger.warning(f"   ⚠️ Neo4j sync failed (non-fatal): {e}")
        # Continue processing even if Neo4j fails
    
    # ========================================
    # STEP D: DETERMINE TASK TYPE, COLLECTION & BUILD SUPER STRING
    # ========================================
    # Auto-detect task_type from analysis_json structure
    if "visual_specifics" in analysis_json:
        task_type = "vision"
    elif "audio_specifics" in analysis_json:
        task_type = "audio"
    else:
        task_type = "text"  # Includes text_specifics and memory_analysis
    
    collection_name = determine_collection(task_type, analysis_json, sidecar_data)
    
    logger.info(f"   🎯 Detected: task_type={task_type}, collection={collection_name}")
    
    vector_string = build_vector_content(
        task_type=task_type,
        llm_json=analysis_json,
        raw_text=text_content
    )
    
    # Debug logging - critical for verification
    preview = vector_string[:150].replace('\n', ' ')
    logger.info(f"   🧬 [VECTOR FACTORY] Super String built ({len(vector_string)} chars)")
    logger.debug(f"   Preview: {preview}...")
    
    # ========================================
    # STEP E: GENERATE EMBEDDING FROM SUPER STRING
    # ========================================
    embedding_result = call_text_embeddings_api(vector_string)
    embedding_vector = embedding_result.get('embedding', [])
    
    if not embedding_vector:
        logger.error(f"   ❌ No embedding returned from API")
        return {
            'status': 'FAILED',
            'error_message': 'Embedding API returned empty vector'
        }
    
    logger.info(f"   ✅ Embedding generated: {len(embedding_vector)} dimensions")
    
    # ========================================
    # STEP F: WEAVIATE UPSERT WITH CONDITIONAL METADATA MAPPING
    # ========================================
    weaviate_uuid = generate_collection_uuid(asset.file_hash, collection_name)
    
    # === LÓGICA DE MAPEO DE METADATOS (Hybrid Search Ready) ===
    
    properties = {
        "neo4j_hash": asset.file_hash,
        "inbox_id": str(asset.id),
        "tags": graph_core.get("tags", []),
        "filename": asset.filename,
        "minio_path": asset.minio_path,
        "mime_type": asset.mime_type
    }
    
    # 2. Selección de Vector Name y Campos Específicos
    target_vector_name = "default"
    
    # CASO A: MEMORIA DE USUARIO
    if "memory_analysis" in analysis_json:
        specs = analysis_json.get("memory_analysis", {})
        conn = specs.get("file_connection", {})
        
        properties.update({
            "text": specs.get("enriched_text", text_content[:2000]),
            "sentiment": specs.get("sentiment", "neutral"),
            "emotional_intensity": float(specs.get("emotional_intensity", 0.0)),
            "connection_type": conn.get("relation_type", "NONE"),
            "related_file_uuids": [asset.file_hash]  # Self-reference for now
        })
        target_vector_name = "default"
        logger.info(f"   📝 Mapped as MEMORY: sentiment={properties['sentiment']}")

    # CASO B: VISUAL (Si la tarea es para VisualSpace con semantic)
    elif "visual_specifics" in analysis_json:
        specs = analysis_json.get("visual_specifics", {})
        
        properties.update({
            "description_ai": graph_core.get("summary", ""),
            "ocr_text": specs.get("ocr_text") or "",
            "image_type": specs.get("image_type", "unknown"),
            "art_style": specs.get("art_style", ""),
            "visual_mood": specs.get("visual_mood", ""),
            "dominant_colors": specs.get("dominant_colors", [])
        })
        target_vector_name = "semantic"  # BGE-M3 goes to "semantic" named vector
        logger.info(f"   🖼️ Mapped as VISUAL: type={properties['image_type']}")

    # CASO C: AUDIO
    elif "audio_specifics" in analysis_json:
        specs = analysis_json.get("audio_specifics", {})
        
        properties.update({
            "transcript": text_content[:5000],  # Full transcript
            "lyrics_summary": specs.get("lyrics_summary") or "",
            "audio_type": specs.get("audio_type", "unknown"),
            "genre": specs.get("genre", ""),
            "emotion": specs.get("emotional_tone", ""),
            "instruments": specs.get("instruments", []),
            "tempo": specs.get("tempo", "")
        })
        target_vector_name = "transcript_semantic"  # BGE-M3 goes here
        logger.info(f"   🎵 Mapped as AUDIO: type={properties['audio_type']}")

    # CASO D: DOCUMENTO DE TEXTO (Default)
    elif "text_specifics" in analysis_json:
        specs = analysis_json.get("text_specifics", {})
        
        properties.update({
            "content": text_content[:5000],
            "ai_summary": graph_core.get("summary", ""),
            "document_type": specs.get("document_type", "unknown"),
            "rhetorical_tone": specs.get("rhetorical_tone", "neutral")
        })
        target_vector_name = "default"
        logger.info(f"   📄 Mapped as TEXT: type={properties['document_type']}")
    
    # FALLBACK: Unknown content type
    else:
        properties.update({
            "content": text_content[:5000],
            "ai_summary": graph_core.get("summary", "")
        })
        target_vector_name = "default"
        logger.warning(f"   ⚠️ Fallback mapping - no specific schema found")
    
    logger.info(f"   🎯 Target: {collection_name}/{target_vector_name}")
    
    # === WEAVIATE UPSERT ===
    try:
        weaviate_client = get_weaviate_client()
        
        upsert_success = upsert_to_weaviate(
            client=weaviate_client,
            collection_name=collection_name,
            weaviate_uuid=weaviate_uuid,
            properties=properties,
            vector=embedding_vector,
            vector_name=target_vector_name
        )
        
        if upsert_success:
            logger.info(f"   💾 Weaviate UPSERT successful: {collection_name}/{weaviate_uuid[:8]}...")
        else:
            logger.warning(f"   ⚠️ Weaviate UPSERT returned False")
            
    except Exception as e:
        logger.error(f"   ❌ Weaviate upsert failed: {e}")
        # Continue to update sidecar even if Weaviate fails
    
    # ========================================
    # STEP G: NEO4J - STAGE SUGGESTIONS FOR HUMAN REVIEW (HITL SAFETY)
    # ========================================
    staged_count = 0
    try:
        # Stage entities/concepts in InboxItem for human review
        # This keeps the graph clean until approval
        stage_success = stage_suggestions_in_inbox(neo4j_driver, asset.file_hash, analysis_json)
        if stage_success:
            graph_core = analysis_json.get('graph_core', {})
            entities = graph_core.get('entities', {})
            staged_count = sum(len(v) for v in entities.values() if isinstance(v, list))
    except Exception as e:
        logger.warning(f"   ⚠️ Neo4j inbox staging failed (non-fatal): {e}")
    
    # ========================================
    # STEP H: UPDATE SIDECAR WITH VECTOR INFO
    # ========================================
    # Detect content type for logging
    content_type = "text"
    if "memory_analysis" in analysis_json:
        content_type = "memory"
    elif "visual_specifics" in analysis_json:
        content_type = "visual"
    elif "audio_specifics" in analysis_json:
        content_type = "audio"
    
    update_sidecar_metadata(
        asset,
        'data_layers.vectors_generated',
        {
            'vector_type': content_type,
            'collection': collection_name,
            'weaviate_uuid': weaviate_uuid,
            'vector_dimensions': len(embedding_vector),
            'super_string_length': len(vector_string),
            'vector_name': target_vector_name
        },
        add_workflow_step=f'{content_type}_embedding'
    )
    
    # Save debug vector string for verification (optional but useful)
    update_sidecar_metadata(
        asset,
        'data_layers.vectors.semantic_debug',
        vector_string[:2000],  # Limit for storage
        add_workflow_step='vector_debug_saved'
    )
    
    logger.info(f"   ✅ TEXT_CHUNK completed successfully")
    
    return {
        'status': 'COMPLETED',
        'weaviate_uuid': weaviate_uuid,
        'collection': collection_name,
        'suggestions_staged': staged_count,
        'message': f'Embedding stored in {collection_name}. {staged_count} suggestions staged for review.'
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
    
    # Optimize image for VLM to prevent ContextWindowExceeded
    # Large images (4K/HD) generate thousands of visual tokens in Qwen-VL
    logger.info(f"   🖼️ Optimizing image for VLM...")
    file_content = optimize_image_for_vlm(file_content, max_dimension=1024)
    
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
    
    # Try to parse as JSON for validation using helper function
    parsed_json, status = extract_json_from_llm_response(generated_text)
    if parsed_json:
        logger.info(f"   ✅ LLM returned valid JSON with keys: {list(parsed_json.keys())}")
        # Store parsed JSON in raw_debug_data for now
        update_sidecar_metadata(
            asset, 
            'data_layers.raw_debug_data.visual_semantic_json', 
            parsed_json,
            add_workflow_step='visual_semantic'
        )
    else:
        logger.warning(f"   ⚠️ LLM: {status}")
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
                
                # Optimize each image for OCR (binarization + contrast)
                content = optimize_image_for_ocr(content, max_dimension=1024)
                
                files_data.append({
                    'filename': filename,
                    'content': content
                })
                logger.info(f"   ✅ Downloaded and optimized {len(content)} bytes: {filename}")
            
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
        
        # Optimize image for OCR (binarization + contrast)
        file_content = optimize_image_for_ocr(file_content, max_dimension=1024)
        
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
    
    # Clean up OCR response - remove markdown artifacts that LLMs add by inertia
    extracted_text = extracted_text.replace("### ", "").replace("## ", "").replace("# ", "").strip()
    logger.info(f"   📄 Cleaned OCR text: {len(extracted_text)} chars")
    
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
    
    # Check if this asset requires mandatory user memory but none provided
    # Read from Asset model (SQL database)
    if asset.requires_user_memory and not user_context.get("content"):
        logger.info(f"   ⏸️ Asset requires user memory but none provided - setting to REVIEW_REQUIRED")
        return {
            "status": "waiting_user_input",
            "requires_user_memory_input": True,
            "message": "Asset requires user memory context before processing can continue"
        }
    
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
        # IMAGE FILES - Check for OCR first, then Vision
        # ============================================
        if asset.mime_type and asset.mime_type.startswith("image/"):
            # Check if OCR text is available in sidecar
            ocr_text = None
            if sidecar_data:
                ocr_text = sidecar_data.get('data_layers', {}).get('intermediate_results', {}).get('ocr_text')
            
            if ocr_text:
                # OCR text exists - use TEXT analysis (chat) instead of vision
                logger.info("   📄 Image with OCR text - using Chat LLM (text analysis)")
                logger.info(f"   OCR text length: {len(ocr_text)} chars")
                
                # Build external context with OCR text
                external_context = {'document_text': ocr_text[:4000]}
                if user_context["content"]:
                    external_context['user_context'] = user_context["content"]
                user_notes = sidecar_data.get('user_notes')
                if user_notes:
                    external_context['user_notes'] = user_notes
                
                # Build specialized text prompt
                prompt = build_specialized_prompt(
                    task_type="text",
                    external_context=external_context
                )
                logger.info(f"   Built text analysis prompt: {len(prompt)} chars")
                
                # Call LLM for text analysis (chat, not vision)
                url = f"{LLM_GATEWAY_BASE_URL}/chat/completions"
                messages = [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"Analyze this OCR-extracted text and return structured JSON:\n\n{ocr_text[:4000]}"}
                ]
                
                data = {
                    "task": "chat",  # TEXT task, not vision!
                    "privacy_mode": privacy_mode,
                    "messages": json.dumps(messages),
                    "temperature": 0.5,
                    "response_format": json.dumps({"type": "json_object"})
                }
                
                response = requests.post(url, data=data, timeout=120)
                
                if response.status_code == 200:
                    result = response.json()
                    llm_response = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                    
                    parsed_json, status = extract_json_from_llm_response(llm_response)
                    if parsed_json:
                        analysis_result = parsed_json
                        summary_text = analysis_result.get('graph_core', {}).get('summary', str(analysis_result)[:200])
                        logger.info(f"   ✅ OCR+Text LLM returned JSON with keys: {list(analysis_result.keys())}")
                    else:
                        analysis_result = {"raw_response": llm_response}
                        summary_text = llm_response[:200]
                        logger.warning(f"   ⚠️ OCR+Text LLM: {status}")
                else:
                    raise Exception(f"OCR text analysis LLM returned {response.status_code}")
            else:
                # No OCR text - use Vision LLM
                logger.info("   🖼️ Image file (no OCR) - calling Vision LLM")
                
                # Download file from MinIO
                file_content = download_file_from_minio(asset)
                logger.info(f"   Downloaded {len(file_content)} bytes")
                
                # Optimize image for VLM to prevent context overflow
                file_content = optimize_image_for_vlm(file_content, max_dimension=1024)
                
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
                    parsed_json, status = extract_json_from_llm_response(generated_text)
                    if parsed_json:
                        analysis_result = parsed_json
                        # Summary is inside graph_core as per our prompt schema
                        summary_text = analysis_result.get('graph_core', {}).get('summary', str(analysis_result)[:200])
                        logger.info(f"   ✅ Vision LLM returned JSON with keys: {list(analysis_result.keys())}")
                    else:
                        analysis_result = {"raw_response": generated_text}
                        summary_text = generated_text[:200]
                        logger.warning(f"   ⚠️ Vision LLM: {status}")
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
            
            # Detect if this is a User Memory asset
            is_user_memory = False
            if sidecar_data:
                is_user_memory = (
                    sidecar_data.get("is_user_memory", False) or
                    sidecar_data.get("operation") == "memory_spawn" or
                    sidecar_data.get("operation") == "memory_ingest" or
                    asset.filename.startswith("memory_")
                )
            
            if is_user_memory:
                logger.info("   🧠 USER MEMORY detected - using memory_analysis schema")
            
            # Build external context
            external_context = {'document_text': text_content[:2000]}
            if sidecar_data:
                user_notes = sidecar_data.get('user_notes')
                if user_notes:
                    external_context['user_notes'] = user_notes
                if user_context["content"]:
                    external_context['user_context'] = user_context["content"]
            
            # Build specialized text prompt (with memory flag)
            prompt = build_specialized_prompt(
                task_type="text",
                external_context=external_context,
                is_user_memory=is_user_memory,
                raw_text=text_content
            )
            logger.info(f"   Built {'memory' if is_user_memory else 'text'} analysis prompt: {len(prompt)} chars")
            
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
                "temperature": 0.5,
                "response_format": json.dumps({"type": "json_object"})
            }
            
            response = requests.post(url, data=data, timeout=120)
            
            if response.status_code == 200:
                result = response.json()
                llm_response = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                
                parsed_json, status = extract_json_from_llm_response(llm_response)
                if parsed_json:
                    analysis_result = parsed_json
                    # Summary is inside graph_core as per our prompt schema
                    summary_text = analysis_result.get('graph_core', {}).get('summary', str(analysis_result)[:200])
                    logger.info(f"   ✅ Text LLM returned JSON with keys: {list(analysis_result.keys())}")
                else:
                    analysis_result = {"raw_response": llm_response}
                    summary_text = llm_response[:200]
                    logger.warning(f"   ⚠️ Text LLM: {status}")
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
            
            # Check if transcription/lyrics are valid (not a system error message)
            is_valid_transcript = (
                transcribed_text 
                and not transcribed_text.startswith("[Transcription failed") 
                and not transcribed_text.startswith("[No transcription available")
            )

            # Build context for audio analysis
            external_context = {}
            if is_valid_transcript:
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
            
            if is_valid_transcript:
                url = f"{LLM_GATEWAY_BASE_URL}/chat/completions"
                messages = [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"Analyze this audio transcript:\n\n{transcribed_text[:4000]}"}
                ]
                
                data = {
                    "task": "chat",
                    "privacy_mode": privacy_mode,
                    "messages": json.dumps(messages),
                    "temperature": 0.5,
                    "response_format": json.dumps({"type": "json_object"})
                }
                
                response = requests.post(url, data=data, timeout=120)
                
                if response.status_code == 200:
                    result = response.json()
                    llm_response = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                    
                    parsed_json, status = extract_json_from_llm_response(llm_response)
                    if parsed_json:
                        analysis_result = parsed_json
                        # No longer duplicating transcript here
                        summary_text = analysis_result.get('graph_core', {}).get('summary', str(analysis_result)[:200])
                        logger.info(f"   ✅ Audio LLM returned JSON with keys: {list(analysis_result.keys())}")
                    else:
                        analysis_result = {"raw_response": llm_response}
                        summary_text = llm_response[:200]
                        logger.warning(f"   ⚠️ Audio LLM: {status}")
                else:
                    analysis_result = {"error": f"LLM returned {response.status_code}"}
                    summary_text = transcribed_text[:200]
            else:
                analysis_result = {}
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
        
        # ============================================
        # RESOLVE USER_MEMORY_REQUIRED FLAG
        # ============================================
        # If this asset required user memory and we got it, mark the flag as COMPLETED
        if asset.requires_user_memory and user_context.get("content"):
            from sqlmodel import select
            umr_status = session.exec(
                select(VectorStatus).where(
                    VectorStatus.asset_id == asset.id,
                    VectorStatus.vector_type == VectorType.USER_MEMORY_REQUIRED
                )
            ).first()
            if umr_status:
                umr_status.status = JobStatus.COMPLETED
                umr_status.updated_at = datetime.utcnow()
                session.commit()
                logger.info(f"   ✅ USER_MEMORY_REQUIRED flag resolved → COMPLETED")
            else:
                logger.debug(f"   ℹ️ No USER_MEMORY_REQUIRED VectorStatus found (already resolved?)")
        
        logger.info(f"   ✅ TEXT_SUMMARY completed: {summary_text[:100]}...")
        
        # ============================================
        # SPAWN MEMORY ASSET (if convert_to_memory=True)
        # ============================================
        if user_context.get("convert_to_memory") and user_context.get("content"):
            logger.info(f"   🧠 convert_to_memory=True - spawning memory asset...")
            try:
                memory_asset = spawn_memory_asset(
                    memory_content=user_context["content"],
                    parent_asset=asset,
                    session=session
                )
                if memory_asset:
                    logger.info(f"   🧠 Memory asset created: {memory_asset.filename}")
                    # Record the spawned memory in parent sidecar
                    update_sidecar_metadata(
                        asset,
                        'data_layers.spawned_memory_asset_id',
                        str(memory_asset.id),
                        add_workflow_step='memory_spawned'
                    )
                else:
                    logger.info(f"   🧠 Memory already exists (duplicate content)")
            except Exception as spawn_error:
                logger.error(f"   ❌ Failed to spawn memory asset: {spawn_error}")
                # Non-fatal - continue with main task
        
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


def process_user_memory_task(asset: Asset, vector_status: VectorStatus, session) -> dict:
    """
    Process user memory/notes - extracts insights for UserMemory.
    
    Flow (Modified):
    1. Read user_context/notes
    2. Call LLM (STRICT mode) for metadata extraction & summary
    3. Save generated summary/insight to MinIO as .txt
    4. Store analysis in sidecar
    5. Return REVIEW_REQUIRED (Human must approve before Weaviate storage)
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
    
    logger.info(f"   📝 Memory content source: {len(memory_content)} chars")
    
    # Step 1: Call LLM for metadata extraction & Summary (always strict)
    external_context = {
        'user_memory': memory_content,
        'associated_file': asset.filename
    }
    
    prompt = build_specialized_prompt(
        task_type="text",  # Use text analysis for memories
        external_context=external_context
    )
    
    analysis_result = {}
    summary_text = ""
    
    try:
        url = f"{LLM_GATEWAY_BASE_URL}/chat/completions"
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Extract structured metadata and a clear summary from this personal memory/note:\n\n{memory_content[:4000]}"}
        ]
        
        data = {
            "task": "chat",
            "privacy_mode": privacy_mode,  # Always strict
            "messages": json.dumps(messages),
            "temperature": 0.5,
            "response_format": json.dumps({"type": "json_object"})
        }
        
        response = requests.post(url, data=data, timeout=120)
        
        if response.status_code == 200:
            result = response.json()
            llm_response = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            
            parsed_json, status = extract_json_from_llm_response(llm_response)
            if parsed_json:
                analysis_result = parsed_json
                # Extract summary from graph_core or fall back to description
                summary_text = analysis_result.get('graph_core', {}).get('summary', str(analysis_result)[:500])
                
                logger.info(f"   ✅ LLM extracted metadata: {list(analysis_result.keys())}")
                
                # Update sidecar with JSON analysis
                update_sidecar_metadata(
                    asset,
                    'data_layers.raw_debug_data.memory_analysis_json',
                    analysis_result,
                    add_workflow_step='memory_analysis'
                )
            else:
                logger.warning(f"   ⚠️ LLM: {status}")
                analysis_result = {"raw_response": llm_response}
                summary_text = llm_response[:500]
                
                update_sidecar_metadata(
                    asset,
                    'data_layers.raw_debug_data.memory_analysis_raw',
                    llm_response,
                    add_workflow_step='memory_analysis'
                )
        else:
            logger.warning(f"   ⚠️ LLM call failed: {response.status_code}")
            analysis_result = {"error": f"LLM returned {response.status_code}"}
            summary_text = f"Error processing memory: LLM {response.status_code}"
            
    except Exception as e:
        logger.warning(f"   ⚠️ LLM analysis failed (non-fatal): {e}")
        summary_text = f"Error analyzing memory: {str(e)}"

    # Step 2: Save generated summary to MinIO (as requested)
    if summary_text:
        try:
            minio_client = get_minio_client()
            memory_filename = f"processed/memories/memory_{asset.file_hash[:8]}.txt"
            
            minio_client.put_object(
                Bucket=MINIO_BUCKET,
                Key=memory_filename,
                Body=summary_text.encode('utf-8'),
                ContentType='text/plain'
            )
            logger.info(f"   ✅ Saved memory summary to MinIO: {memory_filename}")
            
            # Link this file in sidecar
            update_sidecar_metadata(
                asset,
                'data_layers.intermediate_results.memory_summary_path',
                memory_filename,
                add_workflow_step='memory_file_generated'
            )
        except Exception as e:
            logger.error(f"   ❌ Failed to save memory summary to MinIO: {e}")

    # Step 3: Return REVIEW_REQUIRED (Deferring Weaviate embedding/storage)
    logger.info(f"   ✅ USER_MEMORY analyzed - awaiting human review")
    
    return {
        'status': 'REVIEW_REQUIRED',
        'weaviate_uuid': None,
        'processing_time': 3.0,
        'message': 'Memory analyzed and drafted. Review required before storage.'
    }

