"""
API router for semantic vector search across Weaviate collections.

Embeds a text query via the LLM Gateway, then performs near_vector search
across all (or selected) Weaviate collections that share the BGE-M3
text embedding model.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import requests
import logging

from config.settings import get_settings
from shared.clients import get_weaviate_client, get_minio_client
import weaviate.classes.query as wq

router = APIRouter(
    prefix="/search",
    tags=["search"]
)

logger = logging.getLogger(__name__)

settings = get_settings()
LLM_GATEWAY_BASE_URL = f"{settings.LLM_GATEWAY_URL}/v1"

# Collections and their text-embedding named vectors (all BGE-M3)
SEARCHABLE_SPACES: Dict[str, str] = {
    "TextSpace": "default",
    "VisualSpace": "semantic",
    "AudioSpace": "transcript_semantic",
    "MemorySpace": "default",
}

SPACE_ICONS = {
    "TextSpace": "📄",
    "VisualSpace": "📸",
    "AudioSpace": "🎵",
    "MemorySpace": "🧠",
}


# ==========================================
# REQUEST / RESPONSE MODELS
# ==========================================

class VectorSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Text query to search for")
    spaces: Optional[List[str]] = Field(
        None,
        description="List of spaces to search. Default: all. Options: TextSpace, VisualSpace, AudioSpace, MemorySpace"
    )
    limit: int = Field(5, ge=1, le=20, description="Max results per space")


class SearchResultItem(BaseModel):
    space: str
    space_icon: str
    uuid: str
    distance: float
    score: float
    properties: Dict[str, Any]


class VectorSearchResponse(BaseModel):
    query: str
    embedding_dimensions: int
    spaces_searched: List[str]
    total_results: int
    results: List[SearchResultItem]


# ==========================================
# ENDPOINT
# ==========================================

@router.post("/vectors", response_model=VectorSearchResponse)
def search_vectors(request: VectorSearchRequest):
    """
    Semantic search across Weaviate vector spaces.

    1. Embeds the query text via LLM Gateway (BGE-M3)
    2. Searches each selected Weaviate collection using near_vector
    3. Returns aggregated results sorted by distance (closest first)

    **Example:**
    ```json
    POST /search/vectors
    {
        "query": "machine learning algorithms",
        "spaces": ["TextSpace", "MemorySpace"],
        "limit": 5
    }
    ```
    """
    # 1. Determine which spaces to search
    target_spaces = request.spaces or list(SEARCHABLE_SPACES.keys())

    # Validate space names
    invalid = [s for s in target_spaces if s not in SEARCHABLE_SPACES]
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid spaces: {invalid}. Valid options: {list(SEARCHABLE_SPACES.keys())}"
        )

    # 2. Embed the query via LLM Gateway
    try:
        embed_resp = requests.post(
            f"{LLM_GATEWAY_BASE_URL}/embeddings/text",
            json={"text": request.query, "normalize": True},
            timeout=30,
        )
        embed_resp.raise_for_status()
        embedding = embed_resp.json().get("embedding", [])
        if not embedding:
            raise HTTPException(status_code=502, detail="LLM Gateway returned empty embedding")
    except requests.exceptions.ConnectionError:
        raise HTTPException(status_code=502, detail="Cannot connect to LLM Gateway for embeddings")
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="LLM Gateway embedding request timed out")
    except requests.exceptions.HTTPError as e:
        raise HTTPException(
            status_code=e.response.status_code if e.response else 500,
            detail=f"LLM Gateway error: {str(e)}"
        )

    # 3. Search each Weaviate collection
    all_results: List[SearchResultItem] = []
    weaviate_client = get_weaviate_client()
    spaces_actually_searched: List[str] = []

    for space_name in target_spaces:
        vector_name = SEARCHABLE_SPACES[space_name]

        if not weaviate_client.collections.exists(space_name):
            logger.warning(f"Collection {space_name} does not exist in Weaviate, skipping")
            continue

        spaces_actually_searched.append(space_name)

        try:
            collection = weaviate_client.collections.get(space_name)

            # Use near_vector with the correct named vector
            if vector_name == "default":
                response = collection.query.near_vector(
                    near_vector=embedding,
                    limit=request.limit,
                    return_metadata=wq.MetadataQuery(distance=True),
                )
            else:
                response = collection.query.near_vector(
                    near_vector=embedding,
                    target_vector=vector_name,
                    limit=request.limit,
                    return_metadata=wq.MetadataQuery(distance=True),
                )

            for obj in response.objects:
                distance = obj.metadata.distance if obj.metadata.distance is not None else 1.0
                score = max(0.0, 1.0 - distance)  # Convert distance to similarity score

                # Clean properties (remove None values, convert non-serializable types)
                clean_props = {}
                for k, v in obj.properties.items():
                    if v is not None:
                        if isinstance(v, (str, int, float, bool, list)):
                            clean_props[k] = v
                        else:
                            clean_props[k] = str(v)

                all_results.append(SearchResultItem(
                    space=space_name,
                    space_icon=SPACE_ICONS.get(space_name, "🔷"),
                    uuid=str(obj.uuid),
                    distance=round(distance, 6),
                    score=round(score, 4),
                    properties=clean_props,
                ))

        except Exception as e:
            logger.error(f"Error searching {space_name}: {e}")
            # Continue with other spaces even if one fails

    # 4. Sort by distance (closest first)
    all_results.sort(key=lambda r: r.distance)

    # ==========================================
    # DIRECT MINIO DISCOVERY (NO SQL)
    # ==========================================
    # User requested to bypass SQL/Weaviate and find files directly in MinIO.
    # Pattern 1 (Uploads): raw/<type>/<8char_hash>_<filename>
    # Pattern 2 (Texts): master_records/texts/<full_hash>.txt
    
    try:
        minio_client = get_minio_client()
        bucket_name = settings.MINIO_BUCKET
        
        # Prefixes to search.
        CANDIDATE_PREFIXES = [
            "raw/images/",
            "raw/audio/",
            "raw/videos/",
            "raw/documents/",
            "master_records/texts/"
        ]
        
        # Cache for hash -> minio_path
        hash_path_cache = {}
        
        for r in all_results:
            props = r.properties
            
            # 1. Get Hash & Sanitize
            file_hash = props.get("neo4j_hash") or props.get("file_hash") or props.get("hash")
            if not file_hash:
                continue
                
            # Clean hash: remove quotes, whitespace, newlines
            file_hash = str(file_hash).strip().strip('"').strip("'")
            
            # 2. Check Cache
            if file_hash in hash_path_cache:
                found_path = hash_path_cache[file_hash]
            else:
                # 3. Search in MinIO
                found_path = None
                
                # Optimization: Guess prefix based on Space
                prefixes_to_try = CANDIDATE_PREFIXES
                if r.space == "VisualSpace":
                    prefixes_to_try = ["raw/images/"] + [p for p in CANDIDATE_PREFIXES if p != "raw/images/"]
                elif r.space == "AudioSpace":
                    prefixes_to_try = ["raw/audio/"] + [p for p in CANDIDATE_PREFIXES if p != "raw/audio/"]
                elif r.space == "TextSpace":
                    prefixes_to_try = ["master_records/texts/", "raw/documents/"] + [p for p in CANDIDATE_PREFIXES if p not in ("master_records/texts/", "raw/documents/")]
                
                for prefix in prefixes_to_try:
                    # Construct search prefix
                    
                    # Case A: master_records/texts/ uses FULL hash
                    if prefix == "master_records/texts/":
                        search_prefix = f"{prefix}{file_hash}"
                    # Case B: raw/ uses SHORT hash (8 chars)
                    else:
                        short_hash = file_hash[:8]
                        search_prefix = f"{prefix}{short_hash}"
                    
                    try:
                        # List objects
                        response = minio_client.list_objects_v2(
                            Bucket=bucket_name,
                            Prefix=search_prefix,
                            MaxKeys=1
                        )
                        
                        if 'Contents' in response:
                            # Match found!
                            obj = response['Contents'][0]
                            found_path = obj['Key']
                            break # Stop checking other prefixes
                            
                    except Exception as e:
                        logger.warning(f"MinIO list failed for {search_prefix}: {e}")
                
                # Update cache
                hash_path_cache[file_hash] = found_path
            
            # 4. Generate Presigned URL
            if found_path:
                try:
                    # Update true path
                    r.properties["minio_path"] = found_path
                    
                    # Sign URL
                    url = minio_client.generate_presigned_url(
                        'get_object',
                        Params={'Bucket': bucket_name, 'Key': found_path},
                        ExpiresIn=3600
                    )
                    r.properties["download_url"] = url
                except Exception as e:
                    logger.error(f"Signing failed for {found_path}: {e}")
            
            # 5. Fix URL for Browser Access (Docker vs Host)
            # The backend might generate a URL like 'http://rag_minio_dev:9000/...' or 'http://localhost:9000/...'
            # But the user's browser needs 'http://localhost:9005/...' (as per docker-compose)
            if r.properties.get("download_url"):
                original_url = r.properties["download_url"]
                
                # Replace the authority part of the URL to point to localhost:9005
                # This handles cases where boto3 signs with the internal container name
                import re
                new_url = re.sub(r'https?://[^/]+', 'http://localhost:9005', original_url)
                
                r.properties["download_url"] = new_url
                print(f"DEBUG: URL Correction | Original: {original_url[:40]}... | New: {new_url[:40]}...")

    except Exception as e:
        logger.error(f"MinIO Discovery failed: {e}")

    return VectorSearchResponse(
        query=request.query,
        embedding_dimensions=len(embedding),
        spaces_searched=spaces_actually_searched,
        total_results=len(all_results),
        results=all_results,
    )


# ==========================================
# STUB ENDPOINTS (Mock responses)
# ==========================================

class StubSearchResult(BaseModel):
    filename: str
    score: float
    space: str
    space_icon: str
    uuid: str
    distance: float
    reasoning: str
    properties: Dict[str, Any] = {}


class StubSearchResponse(BaseModel):
    query: str
    search_type: str
    total_results: int
    results: List[StubSearchResult]


MOCK_RESULTS = [
    StubSearchResult(
        filename="research_ml_transformers.pdf",
        score=0.92,
        space="TextSpace",
        space_icon="📄",
        uuid="a1b2c3d4-e5f6-7890-abcd-ef0123456789",
        distance=0.08,
        reasoning="Alta similitud semántica con la consulta en el espacio de texto.",
        properties={
            "document_type": "research_paper", 
            "tags": ["ML", "transformers", "NLP"],
            "minio_path": "mock/research_ml_transformers.pdf"
        },
    ),
    StubSearchResult(
        filename="foto_laboratorio_001.jpg",
        score=0.78,
        space="VisualSpace",
        space_icon="📸",
        uuid="b2c3d4e5-f6a7-8901-bcde-f01234567890",
        distance=0.22,
        reasoning="Contenido visual relacionado con contexto científico.",
        properties={
            "visual_mood": "professional", 
            "ocr_text": "Lab Equipment Setup",
            "minio_path": "mock/foto_laboratorio_001.jpg"
        },
    ),
    StubSearchResult(
        filename="audio_lecture_ai.mp3",
        score=0.71,
        space="AudioSpace",
        space_icon="🎵",
        uuid="c3d4e5f6-a7b8-9012-cdef-012345678901",
        distance=0.29,
        reasoning="Transcripción del audio contiene términos relacionados.",
        properties={
            "language": "es", 
            "duration_seconds": 1820,
            "minio_path": "mock/audio_lecture_ai.mp3"
        },
    ),
    StubSearchResult(
        filename="memory_proyecto_ia.txt",
        score=0.65,
        space="MemorySpace",
        space_icon="🧠",
        uuid="d4e5f6a7-b8c9-0123-defa-123456789012",
        distance=0.35,
        reasoning="Nota personal con conexiones conceptuales a la consulta.",
        properties={
            "sentiment": "positive", 
            "connection_type": "conceptual",
            "minio_path": "mock/memory_proyecto_ia.txt"
        },
    ),
]


# --- Tab 1: Semantic Text ---
class SemanticTextRequest(BaseModel):
    query: str = Field(..., min_length=1)
    limit: int = Field(10, ge=1, le=50)

@router.post("/semantic-text", response_model=StubSearchResponse)
def search_semantic_text(req: SemanticTextRequest):
    """Stub: Semantic text search (BAAI/bge-m3)."""
    results = MOCK_RESULTS[:req.limit]
    return StubSearchResponse(
        query=req.query,
        search_type="semantic-text (bge-m3)",
        total_results=len(results),
        results=results,
    )


# --- Tab 2: Visual SigLIP ---
class VisualSigLIPRequest(BaseModel):
    image: str = Field(..., description="Base64 image or URL")
    limit: int = Field(10, ge=1, le=50)

@router.post("/visual-siglip", response_model=StubSearchResponse)
def search_visual_siglip(req: VisualSigLIPRequest):
    """Stub: Visual search (SigLIP)."""
    visual_results = [r for r in MOCK_RESULTS if r.space == "VisualSpace"]
    if not visual_results:
        visual_results = MOCK_RESULTS[:1]
    return StubSearchResponse(
        query="[image]",
        search_type="visual-siglip",
        total_results=len(visual_results),
        results=visual_results[:req.limit],
    )


# --- Tab 3: Hybrid Visual + Text ---
class HybridVisualRequest(BaseModel):
    image: str = Field(..., description="Base64 image or URL")
    text_context: str = Field("", description="Optional text context")
    alpha: float = Field(0.5, ge=0.0, le=1.0)
    limit: int = Field(10, ge=1, le=50)

@router.post("/hybrid-visual", response_model=StubSearchResponse)
def search_hybrid_visual(req: HybridVisualRequest):
    """Stub: Hybrid visual+text search (SigLIP + bge-m3)."""
    return StubSearchResponse(
        query=req.text_context or "[image+text]",
        search_type=f"hybrid-visual (alpha={req.alpha})",
        total_results=len(MOCK_RESULTS[:req.limit]),
        results=MOCK_RESULTS[:req.limit],
    )


# --- Tab 4: Graph Crisp ---
class GraphCrispRequest(BaseModel):
    query: str = Field(..., min_length=1)
    entity_types: Optional[List[str]] = None

@router.post("/graph-crisp", response_model=StubSearchResponse)
def search_graph_crisp(req: GraphCrispRequest):
    """Stub: Crisp graph search (Neo4j exact)."""
    graph_results = [
        StubSearchResult(
            filename="node:Person/Albert_Einstein",
            score=1.0,
            space="Neo4j",
            uuid="e5f6a7b8-c9d0-1234-efab-234567890123",
            reasoning=f"Coincidencia exacta en grafo para '{req.query}'.",
            properties={"node_type": "Person", "connections": 12},
        ),
        StubSearchResult(
            filename="node:Concept/Relatividad",
            score=0.95,
            space="Neo4j",
            uuid="f6a7b8c9-d0e1-2345-fabc-345678901234",
            reasoning=f"Concepto directamente relacionado con '{req.query}'.",
            properties={"node_type": "Concept", "connections": 8},
        ),
    ]
    return StubSearchResponse(
        query=req.query,
        search_type="graph-crisp (Neo4j)",
        total_results=len(graph_results),
        results=graph_results,
    )


# --- Tab 5: Graph Fuzzy ---
class GraphFuzzyRequest(BaseModel):
    query: str = Field(..., min_length=1)
    min_confidence: float = Field(0.6, ge=0.0, le=1.0)

@router.post("/graph-fuzzy", response_model=StubSearchResponse)
def search_graph_fuzzy(req: GraphFuzzyRequest):
    """Stub: Fuzzy graph search (weighted expansion)."""
    fuzzy_results = [
        StubSearchResult(
            filename="node:Concept/Mecánica_Cuántica",
            score=0.88,
            space="Neo4j",
            uuid="a7b8c9d0-e1f2-3456-abcd-456789012345",
            reasoning=f"Expansión difusa (conf={req.min_confidence}) desde '{req.query}'.",
            properties={"node_type": "Concept", "fuzzy_score": 0.88, "hops": 2},
        ),
        StubSearchResult(
            filename="node:Person/Niels_Bohr",
            score=0.72,
            space="Neo4j",
            uuid="b8c9d0e1-f2a3-4567-bcde-567890123456",
            reasoning=f"Conexión difusa a 2 hops desde la consulta.",
            properties={"node_type": "Person", "fuzzy_score": 0.72, "hops": 2},
        ),
        StubSearchResult(
            filename="node:Concept/Principio_Incertidumbre",
            score=0.61,
            space="Neo4j",
            uuid="c9d0e1f2-a3b4-5678-cdef-678901234567",
            reasoning=f"Relación conceptual encontrada con confianza mínima.",
            properties={"node_type": "Concept", "fuzzy_score": 0.61, "hops": 3},
        ),
    ]
    # Filter by min_confidence
    filtered = [r for r in fuzzy_results if r.score >= req.min_confidence]
    return StubSearchResponse(
        query=req.query,
        search_type=f"graph-fuzzy (min_conf={req.min_confidence})",
        total_results=len(filtered),
        results=filtered,
    )

