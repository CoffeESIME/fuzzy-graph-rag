"""
Worker Utilities
================

Helper functions for Celery tasks:
- Vector Factory: Transforms LLM JSON into embedding-ready strings
- UUID Generation: Deterministic UUIDs for Weaviate idempotency
- Graph Sync: Neo4j node MERGE operations
"""

import uuid
import hashlib
import logging
import json
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


# ==========================================
# DETERMINISTIC UUID GENERATION (WEAVIATE)
# ==========================================

def generate_uuid5(identifier: str, namespace: str = "graphrag") -> str:
    """
    Generate a deterministic UUID v5 from a string identifier.
    
    This ensures the same input always produces the same UUID,
    enabling idempotent upserts in Weaviate.
    
    Args:
        identifier: Unique string (typically file_hash or asset_id)
        namespace: Namespace string for UUID generation
        
    Returns:
        UUID string (lowercase, with hyphens)
        
    Example:
        >>> generate_uuid5("abc123")
        'a1b2c3d4-e5f6-5789-abcd-ef0123456789'
    """
    # Create a namespace UUID from our app name
    namespace_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, namespace)
    # Generate deterministic UUID from identifier
    return str(uuid.uuid5(namespace_uuid, identifier))


def generate_collection_uuid(file_hash: str, collection: str) -> str:
    """
    Generate a deterministic UUID for a specific collection.
    
    Different collections get different UUIDs for the same asset,
    allowing multiple vector types to coexist.
    
    Args:
        file_hash: Asset's file hash
        collection: Target collection name (e.g., "TextSpace", "VisualSpace")
        
    Returns:
        UUID string
    """
    combined = f"{collection}:{file_hash}"
    return generate_uuid5(combined)


# ==========================================
# VECTOR FACTORY - BUILD EMBEDDING CONTENT
# ==========================================

def build_vector_content(task_type: str, llm_json: dict, raw_text: str = "") -> str:
    """
    Transform LLM analysis JSON into optimized string for embedding.
    
    This "Super String" is specifically crafted for BGE-M3/similar models,
    prioritizing the most semantically relevant information.
    
    Args:
        task_type: One of "vision", "audio", "text"
        llm_json: The structured JSON from prior LLM analysis
        raw_text: Original raw text content (for text tasks)
        
    Returns:
        Optimized string for embedding generation
    """
    
    # 1. CASO VISUAL (Memes, Fotos, Arte)
    if task_type == "vision":
        specs = llm_json.get("visual_specifics", {})
        core = llm_json.get("graph_core", {})
        
        # Prioridad 1: El OCR (Vital para memes)
        ocr_segment = f"Text in image: '{specs.get('ocr_text')}'." if specs.get("ocr_text") else ""
        
        # Prioridad 2: Descripción y Atmósfera
        desc_segment = f"Visual Description: {core.get('summary', '')}."
        mood_segment = f"Mood: {specs.get('visual_mood', '')}."
        
        # Prioridad 3: Estilo y Tipo
        style_segment = f"Type: {specs.get('image_type', 'unknown')} style {specs.get('art_style', 'unknown')}."
        
        # Prioridad 4: Tags for additional semantic richness
        tags = core.get("tags", [])
        tags_segment = f"Tags: {', '.join(tags)}." if tags else ""
        
        return f"{style_segment} {desc_segment} {ocr_segment} {mood_segment} {tags_segment}".strip()

    # 2. CASO AUDIO (Música, Voz)
    elif task_type == "audio":
        specs = llm_json.get("audio_specifics", {})
        core = llm_json.get("graph_core", {})
        
        # Prioridad 1: Clasificación
        meta_segment = f"Audio Type: {specs.get('audio_type', 'unknown')} Genre: {specs.get('genre', 'unknown')}."
        
        # Prioridad 2: Emoción e Instrumentos (Para búsquedas por 'vibe')
        instruments = specs.get('instruments', [])
        vibe_segment = f"Emotion: {specs.get('emotional_tone', '')}. Instruments: {', '.join(instruments)}."
        
        # Prioridad 3: Contenido Lírico o Temático
        lyrics_summary = specs.get('lyrics_summary', '')
        content_segment = f"Topic: {lyrics_summary}." if lyrics_summary else ""
        
        # Prioridad 4: Resumen general
        summary = core.get('summary', '')
        
        return f"{meta_segment} {vibe_segment} {content_segment} Description: {summary}".strip()

    # 3. CASO TEXTO (Notas, Artículos) - SIN ser memoria
    elif task_type == "text" and "memory_analysis" not in llm_json:
        specs = llm_json.get("text_specifics", {})
        core = llm_json.get("graph_core", {})
        
        # Prioridad 1: Metadatos
        doc_type = specs.get('document_type', 'document')
        tone = specs.get('rhetorical_tone', '')
        meta_segment = f"Document: {doc_type} Tone: {tone}."
        
        # Prioridad 2: Resumen Inteligente
        summary = core.get('summary', '')
        summary_segment = f"Summary: {summary}." if summary else ""
        
        # Prioridad 3: Key arguments
        key_args = specs.get('key_arguments', [])
        args_segment = f"Key Points: {'; '.join(key_args)}." if key_args else ""
        
        # Prioridad 4: El Texto Original (Chunk)
        # BGE-M3 tiene una ventana grande (8k tokens), úsala. 
        original_segment = f"Content: {raw_text}" if raw_text else ""
        
        return f"{meta_segment} {summary_segment} {args_segment} {original_segment}".strip()

    # 4. CASO USER MEMORY (Con o Sin Archivo)
    elif task_type == "text" and "memory_analysis" in llm_json:
        mem_specs = llm_json.get("memory_analysis", {})
        
        # LA CLAVE: Usamos 'enriched_text'
        enriched_narrative = mem_specs.get("enriched_text", raw_text)
        
        # Agregamos la emoción explícita para ayudar a la búsqueda por sentimiento
        sentiment = mem_specs.get('sentiment', '')
        sentiment_segment = f"Sentiment: {sentiment}." if sentiment else ""
        
        # Si hay conexión con archivo, agregamos el POR QUÉ explícito
        conn_segment = ""
        if "file_connection" in mem_specs:
            conn = mem_specs["file_connection"]
            relation_type = conn.get('relation_type', '')
            reasoning = conn.get('reasoning', '')
            conn_segment = f"Relation to file: {relation_type} ({reasoning})."
            
        return f"User Memory: {enriched_narrative} {sentiment_segment} {conn_segment}".strip()

    # Fallback: Return raw text as-is
    logger.warning(f"   ⚠️ Vector Factory fallback for unknown task_type: {task_type}")
    return raw_text


# ==========================================
# COLLECTION ROUTING
# ==========================================

def determine_collection(task_type: str, llm_json: dict, sidecar_data: dict) -> str:
    """
    Determine the target Weaviate collection based on content type.
    
    Args:
        task_type: One of "vision", "audio", "text"
        llm_json: The analysis JSON
        sidecar_data: Full sidecar dictionary
        
    Returns:
        Collection name string
    """
    # Memory detection
    is_memory = (
        "memory_analysis" in llm_json or
        sidecar_data.get("is_user_memory", False) or
        sidecar_data.get("operation") == "memory_spawn" or
        sidecar_data.get("operation") == "memory_ingest"
    )
    
    if is_memory:
        return "MemorySpace"
    
    # Route by task type
    collection_map = {
        "vision": "VisualSpace",
        "audio": "AudioSpace",
        "text": "TextSpace"
    }
    
    return collection_map.get(task_type, "TextSpace")


def determine_vector_name(task_type: str, vector_type: str) -> str:
    """
    Determine the named vector to use in Weaviate.
    
    Weaviate collections can have multiple named vectors.
    This maps our task types to the correct vector name.
    
    Args:
        task_type: One of "vision", "audio", "text"
        vector_type: The VectorType enum value (e.g., "visual_siglip", "text_chunk")
        
    Returns:
        Named vector string for Weaviate
    """
    # Map VectorType to named vectors in Weaviate schema
    vector_name_map = {
        # Visual
        "visual_siglip": "visual",
        "visual_semantic": "semantic",
        # Audio
        "audio_clap": "audio_clap",
        "audio_transcript": "transcript_semantic",
        # Text
        "text_chunk": "default",
        "text_summary": "default",
        "user_memory": "default",
    }
    
    return vector_name_map.get(vector_type, "default")


# ==========================================
# NEO4J GRAPH SYNC HELPERS
# ==========================================

def ensure_digital_asset_node(driver, file_hash: str, asset_metadata: dict) -> bool:
    """
    Ensure a DigitalAsset node exists in Neo4j (idempotent MERGE).
    
    Args:
        driver: Neo4j driver instance
        file_hash: The asset's file hash (unique identifier)
        asset_metadata: Dict with properties to set on the node
        
    Returns:
        True if successful, False otherwise
    """
    query = """
    MERGE (a:DigitalAsset {file_hash: $file_hash})
    ON CREATE SET 
        a.created_at = datetime(),
        a.filename = $filename,
        a.mime_type = $mime_type,
        a.inbox_id = $inbox_id
    ON MATCH SET
        a.last_seen = datetime()
    RETURN a.file_hash as hash
    """
    
    try:
        with driver.session() as session:
            result = session.run(
                query,
                file_hash=file_hash,
                filename=asset_metadata.get("filename", "unknown"),
                mime_type=asset_metadata.get("mime_type", "unknown"),
                inbox_id=asset_metadata.get("inbox_id", None)
            )
            record = result.single()
            if record:
                logger.info(f"   ✅ Neo4j MERGE: DigitalAsset node synced (hash={file_hash[:8]}...)")
                return True
            return False
    except Exception as e:
        logger.error(f"   ❌ Neo4j MERGE failed: {e}")
        return False


def link_memory_to_parent(driver, memory_hash: str, parent_hash: str, memory_filename: str) -> bool:
    """
    Create a [:MEMORY_OF] relationship between a spawned memory and its parent asset.
    
    When a user adds a memory/note to an existing file (audio, image, etc.),
    we spawn a new memory asset. This function creates the Neo4j relationship
    connecting them.
    
    Args:
        driver: Neo4j driver instance
        memory_hash: The memory asset's file hash
        parent_hash: The parent asset's file hash (the original file)
        memory_filename: Filename of the memory for logging
        
    Returns:
        True if relationship created/exists, False on error
    """
    query = """
    MATCH (parent:DigitalAsset {file_hash: $parent_hash})
    MERGE (memory:DigitalAsset {file_hash: $memory_hash})
    ON CREATE SET
        memory.created_at = datetime(),
        memory.is_memory = true
    MERGE (memory)-[r:MEMORY_OF]->(parent)
    ON CREATE SET
        r.created_at = datetime()
    SET 
        memory.last_seen = datetime(),
        r.last_seen = datetime()
    RETURN parent.file_hash as parent, memory.file_hash as memory
    """
    
    try:
        with driver.session() as session:
            result = session.run(
                query,
                parent_hash=parent_hash,
                memory_hash=memory_hash
            )
            record = result.single()
            if record:
                logger.info(f"   🔗 Neo4j: Linked memory '{memory_filename[:20]}...' → parent {parent_hash[:8]}...")
                return True
            else:
                logger.warning(f"   ⚠️ Neo4j: Parent asset {parent_hash[:8]}... not found in graph")
                return False
    except Exception as e:
        logger.error(f"   ❌ Neo4j link_memory_to_parent failed: {e}")
        return False



def stage_suggestions_in_inbox(driver, file_hash: str, llm_json: dict) -> bool:
    """
    Stage LLM suggestions in an InboxItem node for human review.
    
    Creates/Updates an InboxItem node linked to the DigitalAsset.
    Stores the LLM's suggested entities as JSON string properties,
    separating 'entities' (physical) from 'concepts' (abstract).
    
    This is the HITL-safe alternative to link_entities_to_asset().
    The graph remains clean until human approval occurs.
    
    Args:
        driver: Neo4j driver instance
        file_hash: The asset's file hash
        llm_json: The full LLM analysis JSON
        
    Returns:
        True if successful, False otherwise
    """
    # 1. Extract and separate data from LLM
    core = llm_json.get("graph_core", {})
    all_entities = core.get("entities", {})
    summary = core.get("summary", "")
    tags = core.get("tags", [])
    
    # Separate Concepts (abstract) from Entities (physical)
    concepts_list = all_entities.get("concepts", [])
    
    # Create dict with only physical entities (Persons, Locations, Orgs)
    physical_entities = {
        "persons": all_entities.get("persons", []),
        "locations": all_entities.get("locations", []),
        "organizations": all_entities.get("organizations", [])
    }
    
    # Count suggestions for logging
    entity_count = sum(len(v) for v in physical_entities.values())
    concept_count = len(concepts_list)
    
    query = """
    MATCH (a:DigitalAsset {file_hash: $file_hash})
    MERGE (i:InboxItem {id: a.file_hash + "_inbox"})
    MERGE (a)-[:HAS_INBOX_ITEM]->(i)
    SET 
        i.processing_status = 'REVIEW_REQUIRED',
        i.ai_summary = $summary,
        i.tags = $tags,
        i.suggested_entities = $entities_json,
        i.suggested_concepts = $concepts_json,
        i.entity_count = $entity_count,
        i.concept_count = $concept_count,
        i.updated_at = datetime()
    RETURN i.id
    """
    
    try:
        with driver.session() as session:
            result = session.run(
                query, 
                file_hash=file_hash,
                summary=summary,
                tags=tags,
                entities_json=json.dumps(physical_entities),
                concepts_json=json.dumps(concepts_list),
                entity_count=entity_count,
                concept_count=concept_count
            )
            record = result.single()
            if record:
                logger.info(f"   📥 Neo4j: Staged {entity_count} entities + {concept_count} concepts in InboxItem for {file_hash[:8]}...")
                return True
            return False
    except Exception as e:
        logger.error(f"   ❌ Neo4j Inbox staging failed: {e}")
        return False


# ==========================================
# WEAVIATE UPSERT HELPERS
# ==========================================

def upsert_to_weaviate(
    client,
    collection_name: str,
    weaviate_uuid: str,
    properties: dict,
    vector: List[float],
    vector_name: str = "default"
) -> bool:
    """
    Upsert (insert or update) an object in Weaviate.
    
    Uses deterministic UUID for idempotency - running the same 
    task twice will update rather than duplicate.
    
    Args:
        client: Weaviate client instance
        collection_name: Target collection (e.g., "TextSpace")
        weaviate_uuid: Deterministic UUID for this object
        properties: Object properties dict
        vector: Embedding vector
        vector_name: Named vector to use (for multi-vector collections)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        collection = client.collections.get(collection_name)
        
        # Check if object exists
        try:
            existing = collection.query.fetch_object_by_id(weaviate_uuid)
            exists = existing is not None
        except Exception:
            exists = False
        
        if exists:
            # Update existing object
            collection.data.update(
                uuid=weaviate_uuid,
                properties=properties,
                vector={vector_name: vector} if vector_name != "default" else vector
            )
            logger.info(f"   🔄 Weaviate UPDATE: {collection_name}/{weaviate_uuid[:8]}...")
        else:
            # Insert new object
            collection.data.insert(
                uuid=weaviate_uuid,
                properties=properties,
                vector={vector_name: vector} if vector_name != "default" else vector
            )
            logger.info(f"   ➕ Weaviate INSERT: {collection_name}/{weaviate_uuid[:8]}...")
        
        return True
        
    except Exception as e:
        logger.error(f"   ❌ Weaviate upsert failed: {e}")
        return False
