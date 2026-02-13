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
from shared.clients import get_weaviate_client
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

    return VectorSearchResponse(
        query=request.query,
        embedding_dimensions=len(embedding),
        spaces_searched=spaces_actually_searched,
        total_results=len(all_results),
        results=all_results,
    )
