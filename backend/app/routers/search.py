"""
API router for multimodal search across Weaviate collections.

Endpoints:
  1. POST /search/vectors     – Hybrid (BM25 + Vector) with optional tag filters
  2. POST /search/visual-siglip – Pure visual search via SigLIP image embeddings
  3. POST /search/hybrid-visual – Multimodal fusion (image + text, RRF merge)
  4. POST /search/graph-crisp  – Coming Soon stub
  5. POST /search/graph-fuzzy  – Coming Soon stub
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import requests
import logging
import re
import base64

from config.settings import get_settings
from shared.clients import get_weaviate_client, get_minio_client
import weaviate.classes.query as wq
from weaviate.classes.query import Filter

router = APIRouter(
    prefix="/search",
    tags=["search"]
)

logger = logging.getLogger(__name__)

settings = get_settings()
LLM_GATEWAY_BASE_URL = f"{settings.LLM_GATEWAY_URL}/v1"

# Collections and their TEXT named vectors (all BGE-M3)
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
# HELPERS
# ==========================================

def _embed_text(text: str) -> List[float]:
    """Get BGE-M3 text embedding from LLM Gateway."""
    try:
        resp = requests.post(
            f"{LLM_GATEWAY_BASE_URL}/embeddings/text",
            json={"text": text, "normalize": True},
            timeout=30,
        )
        resp.raise_for_status()
        embedding = resp.json().get("embedding", [])
        if not embedding:
            raise HTTPException(status_code=502, detail="LLM Gateway returned empty text embedding")
        return embedding
    except requests.exceptions.ConnectionError:
        raise HTTPException(status_code=502, detail="Cannot connect to LLM Gateway for text embeddings")
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="LLM Gateway text embedding request timed out")
    except requests.exceptions.HTTPError as e:
        raise HTTPException(
            status_code=e.response.status_code if e.response else 500,
            detail=f"LLM Gateway error: {str(e)}"
        )


def _embed_image(image_bytes: bytes) -> List[float]:
    """Get SigLIP image embedding from LLM Gateway."""
    try:
        resp = requests.post(
            f"{LLM_GATEWAY_BASE_URL}/embeddings/image",
            files={"file": ("image.jpg", image_bytes, "image/jpeg")},
            timeout=30,
        )
        resp.raise_for_status()
        embedding = resp.json().get("embedding", [])
        if not embedding:
            raise HTTPException(status_code=502, detail="LLM Gateway returned empty image embedding")
        return embedding
    except requests.exceptions.ConnectionError:
        raise HTTPException(status_code=502, detail="Cannot connect to LLM Gateway for image embeddings")
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="LLM Gateway image embedding request timed out")
    except requests.exceptions.HTTPError as e:
        raise HTTPException(
            status_code=e.response.status_code if e.response else 500,
            detail=f"LLM Gateway image error: {str(e)}"
        )


def _build_tag_filter(tags: Optional[List[str]]) -> Optional[Filter]:
    """Build a Weaviate Filter for tag matching."""
    if not tags:
        return None
    return Filter.by_property("tags").contains_any(tags)


def _clean_properties(obj) -> Dict[str, Any]:
    """Clean Weaviate object properties for JSON serialization."""
    clean = {}
    for k, v in obj.properties.items():
        if v is not None:
            if isinstance(v, (str, int, float, bool, list)):
                clean[k] = v
            else:
                clean[k] = str(v)
    return clean


def _enrich_with_minio(results: List["SearchResultItem"]) -> None:
    """
    Enrich search results with MinIO presigned URLs.
    Searches by file hash prefix directly in MinIO (no SQL needed).
    """
    try:
        minio_client = get_minio_client()
        bucket_name = settings.MINIO_BUCKET

        CANDIDATE_PREFIXES = [
            "raw/images/", "raw/audio/", "raw/videos/",
            "raw/documents/", "master_records/texts/"
        ]

        hash_path_cache: Dict[str, Optional[str]] = {}

        for r in results:
            props = r.properties
            file_hash = props.get("neo4j_hash") or props.get("file_hash") or props.get("hash")
            if not file_hash:
                continue

            file_hash = str(file_hash).strip().strip('"').strip("'")

            if file_hash in hash_path_cache:
                found_path = hash_path_cache[file_hash]
            else:
                found_path = None

                # Optimize prefix order by space
                prefixes_to_try = CANDIDATE_PREFIXES
                if r.space == "VisualSpace":
                    prefixes_to_try = ["raw/images/"] + [p for p in CANDIDATE_PREFIXES if p != "raw/images/"]
                elif r.space == "AudioSpace":
                    prefixes_to_try = ["raw/audio/"] + [p for p in CANDIDATE_PREFIXES if p != "raw/audio/"]
                elif r.space == "TextSpace":
                    prefixes_to_try = ["master_records/texts/", "raw/documents/"] + [
                        p for p in CANDIDATE_PREFIXES if p not in ("master_records/texts/", "raw/documents/")
                    ]

                for prefix in prefixes_to_try:
                    if prefix == "master_records/texts/":
                        search_prefix = f"{prefix}{file_hash}"
                    else:
                        search_prefix = f"{prefix}{file_hash[:8]}"

                    try:
                        response = minio_client.list_objects_v2(
                            Bucket=bucket_name, Prefix=search_prefix, MaxKeys=1
                        )
                        if 'Contents' in response:
                            found_path = response['Contents'][0]['Key']
                            break
                    except Exception as e:
                        logger.warning(f"MinIO list failed for {search_prefix}: {e}")

                hash_path_cache[file_hash] = found_path

            if found_path:
                try:
                    r.properties["minio_path"] = found_path
                    url = minio_client.generate_presigned_url(
                        'get_object',
                        Params={'Bucket': bucket_name, 'Key': found_path},
                        ExpiresIn=3600
                    )
                    # Fix URL for browser access (Docker internal → localhost)
                    new_url = re.sub(r'https?://[^/]+', 'http://localhost:9005', url)
                    r.properties["download_url"] = new_url
                except Exception as e:
                    logger.error(f"Signing failed for {found_path}: {e}")

    except Exception as e:
        logger.error(f"MinIO Discovery failed: {e}")


# ==========================================
# REQUEST / RESPONSE MODELS
# ==========================================

class VectorSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Text query to search for")
    spaces: Optional[List[str]] = Field(
        None,
        description="Spaces to search. Default: all. Options: TextSpace, VisualSpace, AudioSpace, MemorySpace"
    )
    filters: Optional[List[str]] = Field(
        None,
        description="Tag filters. Results must contain at least one of these tags."
    )
    alpha: float = Field(
        0.5, ge=0.0, le=1.0,
        description="Balance: 0=pure keyword (BM25), 1=pure vector, 0.5=balanced hybrid"
    )
    limit: int = Field(10, ge=1, le=50, description="Max results per space")


class VisualSearchRequest(BaseModel):
    image: str = Field(..., description="Base64 encoded image data")
    limit: int = Field(10, ge=1, le=50, description="Max results")


class HybridVisualRequest(BaseModel):
    image: str = Field(..., description="Base64 encoded image data")
    text_context: str = Field("", description="Optional text query for semantic fusion")
    alpha: float = Field(0.5, ge=0.0, le=1.0, description="Image vs text weight")
    limit: int = Field(10, ge=1, le=50, description="Max results")


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


class MultimodalFusionResponse(BaseModel):
    query: str
    alpha: float
    text_results: List[SearchResultItem]
    visual_results: List[SearchResultItem]
    fused_results: List[SearchResultItem]
    total_results: int
    spaces_searched: List[str]


class ComingSoonResponse(BaseModel):
    message: str = "Feature coming soon"
    results: List[Any] = []


# ==========================================
# ENDPOINT 1: HYBRID SEMANTIC SEARCH (BM25 + Vector)
# ==========================================

@router.post("/vectors", response_model=VectorSearchResponse)
def search_vectors(request: VectorSearchRequest):
    """
    Hybrid search across Weaviate vector spaces.

    Combines BM25 keyword matching with BGE-M3 vector similarity.
    Supports tag-based filtering and alpha tuning.

    **Examples:**
    ```json
    {"query": "machine learning", "alpha": 0.5, "limit": 5}
    {"query": "gato meme", "filters": ["meme", "funny"], "alpha": 0.3}
    ```
    """
    # 1. Determine target spaces
    target_spaces = request.spaces or list(SEARCHABLE_SPACES.keys())
    invalid = [s for s in target_spaces if s not in SEARCHABLE_SPACES]
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid spaces: {invalid}. Valid: {list(SEARCHABLE_SPACES.keys())}"
        )

    # 2. Embed query text via LLM Gateway (BGE-M3)
    embedding = _embed_text(request.query)

    # 3. Build tag filter
    tag_filter = _build_tag_filter(request.filters)

    # 4. Search each collection with hybrid
    all_results: List[SearchResultItem] = []
    weaviate_client = get_weaviate_client()
    spaces_actually_searched: List[str] = []

    for space_name in target_spaces:
        vector_name = SEARCHABLE_SPACES[space_name]

        if not weaviate_client.collections.exists(space_name):
            logger.warning(f"Collection {space_name} does not exist, skipping")
            continue

        spaces_actually_searched.append(space_name)

        try:
            collection = weaviate_client.collections.get(space_name)

            # Build hybrid query kwargs
            hybrid_kwargs = {
                "query": request.query,
                "vector": embedding,
                "alpha": request.alpha,
                "limit": request.limit,
                "return_metadata": wq.MetadataQuery(distance=True, score=True),
            }

            # Add target_vector for collections with named vectors
            if vector_name != "default":
                hybrid_kwargs["target_vector"] = vector_name

            # Add tag filter if provided
            if tag_filter:
                hybrid_kwargs["filters"] = tag_filter

            response = collection.query.hybrid(**hybrid_kwargs)

            for obj in response.objects:
                distance = obj.metadata.distance if obj.metadata.distance is not None else 1.0
                score = obj.metadata.score if obj.metadata.score is not None else max(0.0, 1.0 - distance)

                all_results.append(SearchResultItem(
                    space=space_name,
                    space_icon=SPACE_ICONS.get(space_name, "🔷"),
                    uuid=str(obj.uuid),
                    distance=round(distance, 6),
                    score=round(score, 4),
                    properties=_clean_properties(obj),
                ))

        except Exception as e:
            logger.error(f"Error searching {space_name}: {e}")

    # 5. Sort by score (highest first for hybrid)
    all_results.sort(key=lambda r: r.score, reverse=True)

    # 6. Enrich with MinIO presigned URLs
    _enrich_with_minio(all_results)

    return VectorSearchResponse(
        query=request.query,
        embedding_dimensions=len(embedding),
        spaces_searched=spaces_actually_searched,
        total_results=len(all_results),
        results=all_results,
    )


# ==========================================
# ENDPOINT 2: VISUAL SEARCH (SigLIP)
# ==========================================

@router.post("/visual-siglip", response_model=VectorSearchResponse)
def search_visual_siglip(request: VisualSearchRequest):
    """
    Pure visual search using SigLIP image embeddings.

    Upload a base64 image to find visually similar content in VisualSpace.
    Only searches the `visual` named vector (SigLIP, 1152d).

    **Example:**
    ```json
    {"image": "<base64_data>", "limit": 10}
    ```
    """
    # 1. Decode base64 image
    try:
        # Strip data URL prefix if present (e.g., "data:image/jpeg;base64,...")
        image_data = request.image
        if "," in image_data:
            image_data = image_data.split(",", 1)[1]
        image_bytes = base64.b64decode(image_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid base64 image: {e}")

    # 2. Get SigLIP embedding from LLM Gateway
    embedding = _embed_image(image_bytes)

    # 3. Search VisualSpace only, using the "visual" named vector
    weaviate_client = get_weaviate_client()
    all_results: List[SearchResultItem] = []

    if not weaviate_client.collections.exists("VisualSpace"):
        raise HTTPException(status_code=404, detail="VisualSpace collection not found in Weaviate")

    try:
        collection = weaviate_client.collections.get("VisualSpace")

        response = collection.query.near_vector(
            near_vector=embedding,
            target_vector="visual",  # SigLIP named vector
            limit=request.limit,
            return_metadata=wq.MetadataQuery(distance=True),
        )

        for obj in response.objects:
            distance = obj.metadata.distance if obj.metadata.distance is not None else 1.0
            score = max(0.0, 1.0 - distance)

            all_results.append(SearchResultItem(
                space="VisualSpace",
                space_icon="📸",
                uuid=str(obj.uuid),
                distance=round(distance, 6),
                score=round(score, 4),
                properties=_clean_properties(obj),
            ))

    except Exception as e:
        logger.error(f"Error in visual search: {e}")
        raise HTTPException(status_code=500, detail=f"Visual search failed: {e}")

    # 4. Sort by distance (closest first)
    all_results.sort(key=lambda r: r.distance)

    # 5. Enrich with MinIO URLs
    _enrich_with_minio(all_results)

    return VectorSearchResponse(
        query="[image]",
        embedding_dimensions=len(embedding),
        spaces_searched=["VisualSpace"],
        total_results=len(all_results),
        results=all_results,
    )


# ==========================================
# ENDPOINT 3: MULTIMODAL FUSION (Image + Text)
# ==========================================

@router.post("/hybrid-visual", response_model=MultimodalFusionResponse)
def search_hybrid_visual(request: HybridVisualRequest):
    """
    Multimodal fusion: combines image similarity (SigLIP) with text
    semantic search (BGE-M3).

    Returns three separate lists:
    - text_results: BGE-M3 cosine similarity results
    - visual_results: SigLIP cosine similarity results
    - fused_results: Reciprocal Rank Fusion merge
    """
    # 1. Decode image
    try:
        image_data = request.image
        if "," in image_data:
            image_data = image_data.split(",", 1)[1]
        image_bytes = base64.b64decode(image_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid base64 image: {e}")

    # 2. Get both embeddings
    image_embedding = _embed_image(image_bytes)
    text_embedding = _embed_text(request.text_context) if request.text_context.strip() else None

    weaviate_client = get_weaviate_client()

    # 3A. Visual search in VisualSpace (SigLIP vector)
    visual_results: List[SearchResultItem] = []
    if weaviate_client.collections.exists("VisualSpace"):
        try:
            collection = weaviate_client.collections.get("VisualSpace")
            response = collection.query.near_vector(
                near_vector=image_embedding,
                target_vector="visual",
                limit=request.limit,
                return_metadata=wq.MetadataQuery(distance=True),
            )
            for obj in response.objects:
                distance = obj.metadata.distance if obj.metadata.distance is not None else 1.0
                cosine_score = max(0.0, 1.0 - distance)
                visual_results.append(SearchResultItem(
                    space="VisualSpace",
                    space_icon="📸",
                    uuid=str(obj.uuid),
                    distance=round(distance, 6),
                    score=round(cosine_score, 4),
                    properties=_clean_properties(obj),
                ))
        except Exception as e:
            logger.error(f"Visual search leg failed: {e}")

    # Sort visual by score (highest cosine similarity first)
    visual_results.sort(key=lambda r: r.score, reverse=True)

    # 3B. Text semantic search across all spaces (if text provided)
    text_results: List[SearchResultItem] = []
    if text_embedding:
        for space_name, vector_name in SEARCHABLE_SPACES.items():
            if not weaviate_client.collections.exists(space_name):
                continue
            try:
                collection = weaviate_client.collections.get(space_name)
                nv_kwargs = {
                    "near_vector": text_embedding,
                    "limit": request.limit,
                    "return_metadata": wq.MetadataQuery(distance=True),
                }
                if vector_name != "default":
                    nv_kwargs["target_vector"] = vector_name

                response = collection.query.near_vector(**nv_kwargs)

                for obj in response.objects:
                    distance = obj.metadata.distance if obj.metadata.distance is not None else 1.0
                    cosine_score = max(0.0, 1.0 - distance)
                    text_results.append(SearchResultItem(
                        space=space_name,
                        space_icon=SPACE_ICONS.get(space_name, "🔷"),
                        uuid=str(obj.uuid),
                        distance=round(distance, 6),
                        score=round(cosine_score, 4),
                        properties=_clean_properties(obj),
                    ))
            except Exception as e:
                logger.error(f"Text search leg for {space_name} failed: {e}")

    # Sort text by score (highest cosine similarity first)
    text_results.sort(key=lambda r: r.score, reverse=True)
    text_results = text_results[:request.limit]

    # 4. Reciprocal Rank Fusion (RRF)
    K = 60
    rrf_scores: Dict[str, float] = {}
    rrf_items: Dict[str, SearchResultItem] = {}

    image_weight = request.alpha
    text_weight = 1.0 - request.alpha

    for rank, item in enumerate(visual_results):
        key = item.uuid
        rrf_scores[key] = rrf_scores.get(key, 0) + image_weight * (1.0 / (K + rank + 1))
        rrf_items[key] = item

    for rank, item in enumerate(text_results):
        key = item.uuid
        rrf_scores[key] = rrf_scores.get(key, 0) + text_weight * (1.0 / (K + rank + 1))
        if key not in rrf_items:
            rrf_items[key] = item

    fused: List[SearchResultItem] = []
    for uuid, rrf_score in sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True):
        item_copy = rrf_items[uuid].model_copy()
        item_copy.score = round(rrf_score, 6)
        fused.append(item_copy)

    fused = fused[:request.limit]

    # 5. Enrich all three lists with MinIO URLs
    _enrich_with_minio(visual_results)
    _enrich_with_minio(text_results)
    _enrich_with_minio(fused)

    query_label = f"[image] + {request.text_context}" if request.text_context else "[image]"
    all_spaces = list(set(
        [r.space for r in visual_results] +
        [r.space for r in text_results]
    ))

    return MultimodalFusionResponse(
        query=query_label,
        alpha=request.alpha,
        text_results=text_results,
        visual_results=visual_results,
        fused_results=fused,
        total_results=len(visual_results) + len(text_results),
        spaces_searched=all_spaces,
    )


# ==========================================
# ENDPOINT 4 & 5: GRAPH (COMING SOON)
# ==========================================

class GraphCrispRequest(BaseModel):
    query: str = Field(..., min_length=1)
    entity_types: Optional[List[str]] = None


class GraphFuzzyRequest(BaseModel):
    query: str = Field(..., min_length=1)
    min_confidence: float = Field(0.6, ge=0.0, le=1.0)


@router.post("/graph-crisp", response_model=ComingSoonResponse)
def search_graph_crisp(req: GraphCrispRequest):
    """Graph crisp search – coming soon."""
    return ComingSoonResponse()


@router.post("/graph-fuzzy", response_model=ComingSoonResponse)
def search_graph_fuzzy(req: GraphFuzzyRequest):
    """Graph fuzzy search – coming soon."""
    return ComingSoonResponse()
