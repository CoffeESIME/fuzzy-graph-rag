"""
API router for multimodal search across Weaviate collections.

Endpoints:
  1. POST /search/vectors     – Hybrid (BM25 + Vector) with optional tag filters
  2. POST /search/visual-siglip – Pure visual search via SigLIP image embeddings
  3. POST /search/hybrid-visual – Multimodal fusion (image + text, RRF merge)
  4. POST /search/graph-crisp  – Crisp graph traversal (Neo4j, alpha-cut)
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


def _sanitize_neo4j_props(props: Dict[str, Any]) -> Dict[str, Any]:
    """Clean Neo4j node properties for JSON serialization (handle DateTime, etc)."""
    clean = {}
    for k, v in props.items():
        if v is None:
            continue
        if isinstance(v, (str, int, float, bool)):
            clean[k] = v
        elif isinstance(v, list):
            # Recursively clean list? No, just ISO format for dates in list
            clean[k] = [x.iso_format() if hasattr(x, "iso_format") else x for x in v]
        elif hasattr(v, "iso_format"):  # datetime, date, time
            clean[k] = v.iso_format()
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
# ENDPOINT 4: GRAPH CRISP SEARCH (Neo4j)
# ==========================================

class GraphCrispRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Text query to resolve against Concept nodes")
    alpha_cut: float = Field(0.9, ge=0.0, le=1.0, description="Minimum relationship weight (crisp threshold)")
    limit: int = Field(20, ge=1, le=100, description="Max results")


class GraphCrispResultItem(SearchResultItem):
    matched_concept: str
    relation_type: str


class GraphNode(BaseModel):
    """A node in the graph topology for frontend visualization."""
    id: str = Field(..., description="Unique node ID (elementId or hash)")
    label: str = Field(..., description="Display label for the node")
    type: str = Field(..., description="Node label/type: Concept, DigitalAsset, Person, etc.")
    properties: Dict[str, Any] = Field(default_factory=dict, description="All node properties")


class GraphEdge(BaseModel):
    """An edge in the graph topology for frontend visualization."""
    source: str = Field(..., description="Source node ID")
    target: str = Field(..., description="Target node ID")
    type: str = Field(..., description="Relationship type: EVOKES, EXPLORES, DEFINES, etc.")
    weight: float = Field(..., description="Fuzzy membership weight [0-1]")
    reasoning: Optional[str] = Field(None, description="Why this connection exists")


class GraphTopology(BaseModel):
    """Full graph structure for frontend rendering (e.g. D3, Cytoscape, React Flow)."""
    nodes: List[GraphNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)


class GraphCrispResponse(BaseModel):
    query: str
    concepts_matched: List[str]
    alpha_cut: float
    total_results: int
    results: List[GraphCrispResultItem]
    graph_topology: GraphTopology = Field(
        ..., description="Nodes and edges for dynamic graph visualization"
    )


# ==========================================
# ENDPOINT 4: GRAPH CRISP SEARCH
# ==========================================

@router.post("/graph-crisp", response_model=GraphCrispResponse)
def search_graph_crisp(req: GraphCrispRequest):
    """
    Graph crisp search v2 (Multi-Entity).
    
    Ahora busca coincidencias no solo en Conceptos, sino también en Personas, 
    Lugares y Eventos, aprovechando la ontología rica del sistema.
    """
    from shared.clients import get_neo4j_driver
    driver = get_neo4j_driver()

    cypher_query = """
    // 1. Búsqueda Omnisciente (Conceptos, Personas, Lugares, Eventos, Proyectos)
    MATCH (n)
    WHERE (n:Concept OR n:Person OR n:Location OR n:Organization OR n:Event OR n:Project)
      AND toLower(n.name) CONTAINS toLower($user_query)

    // 2. Expansión Polimórfica
    // Buscamos cualquier activo conectado a este nodo encontrado
    MATCH (d:DigitalAsset)-[r]->(n)
    
    // 3. Filtro de Relaciones Válidas (Ontología Completa)
    WHERE type(r) IN [
        'EVOKES', 'EXPLORES', 'DEFINES', 'EVOKES_CONCEPT', 'EMBODIES', // Conceptos
        'MENTIONS_PERSON', 'CREATED_BY',                               // Personas
        'MENTIONS_LOCATION', 'LOCATED_AT',                             // Lugares
        'MENTIONS_ORG',                                                // Organizaciones
        'MENTIONS_EVENT', 'HAPPENED_AT',                               // Eventos
        'MENTIONS_PROJECT'                                             // Proyectos
    ]
    AND r.weight >= $alpha_cut

    // 4. Retorno enriquecido con el tipo de nodo encontrado (Label)
    RETURN d, n, r,
           elementId(d) AS d_id,
           elementId(n) AS c_id,
           r.weight AS score,
           r.reasoning AS reasoning,
           n.name AS matched_node_name,
           labels(n) AS matched_node_labels,
           type(r) AS rel_type
    ORDER BY score DESC
    LIMIT $limit
    """

    try:
        with driver.session() as session:
            result = session.run(
                cypher_query,
                user_query=req.query,
                alpha_cut=req.alpha_cut,
                limit=req.limit,
            )
            records = list(result)
    except Exception as e:
        logger.error(f"Neo4j graph-crisp query failed: {e}")
        raise HTTPException(status_code=500, detail=f"Graph query failed: {e}")

    # ── Map results ──
    seen_results: Dict[str, GraphCrispResultItem] = {}
    concepts_matched: set = set()
    topo_nodes: Dict[str, GraphNode] = {}
    topo_edges: List[GraphEdge] = []
    seen_edges: set = set()

    for record in records:
        # Extraer datos
        asset_node = record["d"]
        found_node = record["n"] # Ya no es solo 'concept', puede ser cualquiera
        found_labels = record["matched_node_labels"]
        score = record["score"]
        node_name = record["matched_node_name"]
        rel_type = record["rel_type"]
        d_id = record["d_id"]
        c_id = record["c_id"] # ID del nodo encontrado (Concept/Person/etc)

        concepts_matched.add(node_name)

        # Determinar el tipo de nodo encontrado para el Frontend
        # Neo4j devuelve una lista de labels, tomamos el más relevante que no sea 'Base'
        primary_type = "Concept" # Default
        for label in found_labels:
            if label in ["Person", "Location", "Organization", "Event", "Project"]:
                primary_type = label
                break
        
        # ── Topology: Found Node (Antes Concept Node) ──
        if c_id not in topo_nodes:
            node_props = _sanitize_neo4j_props(dict(found_node.items()))
            topo_nodes[c_id] = GraphNode(
                id=c_id,
                label=node_name,
                type=primary_type, # ¡Ahora el frontend sabrá si pintar una Persona o un Concepto!
                properties=node_props,
            )

        # ── Topology: DigitalAsset node ──
        file_hash = asset_node.get("hash") or asset_node.get("file_hash") or d_id
        filename = asset_node.get("filename", "unknown")
        asset_props = _sanitize_neo4j_props(dict(asset_node.items()))

        if d_id not in topo_nodes:
            topo_nodes[d_id] = GraphNode(
                id=d_id,
                label=filename,
                type="DigitalAsset",
                properties=asset_props,
            )

        # ── Topology: Edge ──
        edge_key = (d_id, c_id, rel_type)
        if edge_key not in seen_edges:
            seen_edges.add(edge_key)
            topo_edges.append(GraphEdge(
                source=d_id,
                target=c_id,
                type=rel_type,
                weight=round(score, 4),
                reasoning=record["reasoning"],
            ))

        # ── Flat result ──
        if file_hash not in seen_results or score > seen_results[file_hash].score:
            seen_results[file_hash] = GraphCrispResultItem(
                space="GraphSpace",
                space_icon="🔗",
                uuid=file_hash,
                filename=filename,
                score=round(score, 4),
                matched_concept=f"{node_name} ({primary_type})", # Feedback visual útil: "Elon Musk (Person)"
                relation_type=rel_type,
                distance=0.0,
                properties=asset_props,
            )

    formatted = list(seen_results.values())
    formatted.sort(key=lambda r: r.score, reverse=True)

    # ── Enrich with MinIO presigned URLs ──
    _enrich_with_minio(formatted)

    # Copy enriched URLs back to topology nodes
    url_by_hash: Dict[str, Dict[str, str]] = {}
    for item in formatted:
        props = item.properties
        if "download_url" in props:
            # Normalize hash lookups
            h = item.uuid
            url_by_hash[h] = {"download_url": props["download_url"]}
            if "minio_path" in props:
                url_by_hash[h]["minio_path"] = props["minio_path"]

    for node in topo_nodes.values():
        if node.type == "DigitalAsset":
            node_hash = node.properties.get("hash") or node.properties.get("file_hash")
            if node_hash and node_hash in url_by_hash:
                node.properties.update(url_by_hash[node_hash])

    return GraphCrispResponse(
        query=req.query,
        concepts_matched=sorted(concepts_matched),
        alpha_cut=req.alpha_cut,
        total_results=len(formatted),
        results=formatted,
        graph_topology=GraphTopology(
            nodes=list(topo_nodes.values()),
            edges=topo_edges,
        ),
    )


# ==========================================
# ENDPOINT 5: GRAPH FUZZY SEARCH (COMING SOON)
# ==========================================

@router.post("/graph-fuzzy", response_model=GraphCrispResponse)
def search_graph_fuzzy(req: GraphCrispRequest):
    """
    Graph Fuzzy Search (Vector-First Graph Expansion).

    Flow:
    1. **Vector Search**: Find top DigitalAssets semantically similar to query (alpha=1.0).
    2. **Graph Seeding**: Use found assets as seeds in Neo4j.
    3. **Fuzzy Expansion**: Expand from seeds to connected entities (Concept, Person, etc.) 
       filtering by relationship weight (alpha_cut).
    4. **Discovery**: Optionally find 'sibling' assets connected to those entities.

    Returns the topology of this "semantic neighborhood".
    """
    from shared.clients import get_neo4j_driver
    
    # ── 1. Vector Search (Simulated via Weaviate) ──
    # We manually run a vector search to get seeds. 
    # Not using search_vectors internal func to avoid overhead/pydantic wrapping, 
    # but reusing checks.
    
    embedding = _embed_text(req.query)
    
    # Search all spaces for seeds
    # We focus on DigitalAssets, so TextSpace, VisualSpace, AudioSpace.
    # MemorySpace might be relevant too? Let's include all.
    seed_uuids = set()
    seed_hashes = set()
    weaviate_client = get_weaviate_client()
    
    for space_name, vector_name in SEARCHABLE_SPACES.items():
        if not weaviate_client.collections.exists(space_name):
            continue
        try:
            collection = weaviate_client.collections.get(space_name)
            
            # Use Hybrid Search (Vector + BM25) for better seed selection
            # alpha=0.9 implies strong vector preference but allows keyword matches
            hybrid_kwargs = {
                "query": req.query,
                "vector": embedding,
                "alpha": 0.9, 
                "limit": 5, 
                "return_metadata": wq.MetadataQuery(distance=True, score=True),
                # "return_properties": ... (Let Weaviate return default)
            }
            if vector_name != "default":
                hybrid_kwargs["target_vector"] = vector_name

            response = collection.query.hybrid(**hybrid_kwargs)
            for obj in response.objects:
                seed_uuids.add(str(obj.uuid))
                # Robust extraction of hash from Weaviate
                props = obj.properties
                found_hash = props.get("file_hash") or props.get("hash") or props.get("neo4j_hash")
                if found_hash:
                    seed_hashes.add(found_hash)
                
        except Exception as e:
            logger.warning(f"Vector seed search failed for {space_name}: {e}")

    if not seed_uuids and not seed_hashes:
        # No semantic matches found
        return GraphCrispResponse(
            query=req.query,
            concepts_matched=[],
            alpha_cut=req.alpha_cut,
            total_results=0,
            results=[],
            graph_topology=GraphTopology(nodes=[], edges=[])
        )

    # ── 2. Neo4j Expansion ──
    # Notes: 
    # - Neo4j 'DigitalAsset' nodes use 'file_hash' as primary key usually.
    # - 'uuid' property might be missing in Neo4j, causing warnings.
    # - We rely on 'file_hash' for linking Weaviate -> Neo4j.
    
    driver = get_neo4j_driver()
    
    cypher_query = """
    // A. Encontrar los nodos semilla
    MATCH (seed:DigitalAsset)
    WHERE seed.file_hash IN $seed_hashes
    
    // B. Expandir a Entidades Conectadas (Puente)
    MATCH (seed)-[r]->(target)
    WHERE (target:Concept OR target:Person OR target:Location OR target:Organization OR target:Event OR target:Project)
      AND r.weight >= $alpha_cut
    
    // C. Expandir 'Hermanos' (Discovery) con Decaimiento
    // Aquí está el truco: Multiplicamos los pesos. 
    // Si r=0.8 y r2=0.7 -> Total=0.56. Si alpha=0.6, esto se filtra.
    OPTIONAL MATCH (target)<-[r2]-(discovery:DigitalAsset)
    WHERE discovery.file_hash <> seed.file_hash 
      AND (r.weight * r2.weight) >= $alpha_cut

    // D. Retornar y Ordenar por Fuerza Total del Camino
    RETURN seed, r, target, r2, discovery,
           elementId(seed) as seed_id,
           elementId(target) as target_id,
           elementId(discovery) as disc_id,
           r.weight as w1,
           r2.weight as w2
    
    // Ordenamos priorizando descubrimientos fuertes, luego conexiones directas fuertes
    ORDER BY (CASE WHEN r2 IS NOT NULL THEN r.weight * r2.weight ELSE r.weight END) DESC
    LIMIT $limit
    """
    try:
        with driver.session() as session:
            result = session.run(
                cypher_query,
                seed_uuids=list(seed_uuids),
                seed_hashes=list(seed_hashes),
                alpha_cut=req.alpha_cut,
                limit=req.limit * 2
            )
            records = list(result)
    except Exception as e:
        logger.error(f"Neo4j graph-fuzzy query failed: {e}")
        raise HTTPException(status_code=500, detail=f"Graph fuzzy query failed: {e}")

    # ── 3. Build Topology ──
    seen_results: Dict[str, GraphCrispResultItem] = {} # Keyed by hash/uuid
    topo_nodes: Dict[str, GraphNode] = {}
    topo_edges: List[GraphEdge] = []
    seen_edges: set = set()
    concepts_matched: set = set()
    
    for record in records:
        seed = record["seed"]
        target = record["target"] # Entity
        discovery = record["discovery"] # Optional
        
        seed_id = record["seed_id"]
        target_id = record["target_id"]
        disc_id = record["disc_id"]
        
        w1 = record["w1"]
        w2 = record["w2"] # Can be None
        
        rel1 = record["r"]
        rel2 = record["r2"] # Optional
        
        target_name = target.get("name", "Unknown")
        concepts_matched.add(target_name)
        
        # Determine Target Type
        target_labels = list(target.labels)
        primary_type = "Concept"
        for label in target_labels:
            if label in ["Person", "Location", "Organization", "Event", "Project"]:
                primary_type = label
                break
                
        # ── Nodes ──
        
        # Target (Center)
        if target_id not in topo_nodes:
            topo_nodes[target_id] = GraphNode(
                id=target_id,
                label=target_name,
                type=primary_type,
                properties=_sanitize_neo4j_props(dict(target.items()))
            )

        # Seed (Source)
        seed_hash = seed.get("hash") or seed.get("file_hash") or seed_id
        if seed_id not in topo_nodes:
            props = _sanitize_neo4j_props(dict(seed.items()))
            props["is_seed"] = True # Marking as seed
            topo_nodes[seed_id] = GraphNode(
                id=seed_id,
                label=seed.get("filename", "Seed"),
                type="DigitalAsset",
                properties=props
            )
            
        # ── Edges ──
        
        # Edge 1: Seed -> Target
        edge1_key = (seed_id, target_id, type(rel1).__name__)
        if edge1_key not in seen_edges:
            seen_edges.add(edge1_key)
            topo_edges.append(GraphEdge(
                source=seed_id,
                target=target_id,
                type=rel1.type,
                weight=round(w1, 4),
                reasoning="Vector Seed Match"
            ))
            
            # Result Item for Seed
            if seed_hash not in seen_results or w1 > seen_results[seed_hash].score:
                 seen_results[seed_hash] = GraphCrispResultItem(
                    space="GraphSpace",
                    space_icon="🌱", # Seed icon
                    uuid=seed_hash,
                    filename=seed.get("filename", "Seed"),
                    score=round(w1, 4),
                    matched_concept=f"{target_name} ({primary_type})",
                    relation_type=rel1.type,
                    distance=0.0,
                    properties=_sanitize_neo4j_props(dict(seed.items()))
                )

        # Discovery (Optional)
        if discovery:
            disc_hash = discovery.get("hash") or discovery.get("file_hash") or disc_id
            
            # Node
            if disc_id not in topo_nodes:
                props = _sanitize_neo4j_props(dict(discovery.items()))
                props["is_discovery"] = True
                topo_nodes[disc_id] = GraphNode(
                    id=disc_id,
                    label=discovery.get("filename", "Discovery"),
                    type="DigitalAsset",
                    properties=props
                )
                
            # Edge 2: Discovery -> Target
            edge2_key = (disc_id, target_id, type(rel2).__name__)
            if edge2_key not in seen_edges:
                seen_edges.add(edge2_key)
                topo_edges.append(GraphEdge(
                    source=disc_id,
                    target=target_id,
                    type=rel2.type,
                    weight=round(w2, 4),
                    reasoning="Graph Discovery"
                ))
                
                # Result Item for Discovery
                if disc_hash not in seen_results or w2 > seen_results[disc_hash].score:
                     seen_results[disc_hash] = GraphCrispResultItem(
                        space="GraphSpace",
                        space_icon="🔭", # Telescope
                        uuid=disc_hash,
                        filename=discovery.get("filename", "Discovery"),
                        score=round(w2, 4),
                        matched_concept=f"{target_name} ({primary_type})",
                        relation_type=rel2.type,
                        distance=0.0,
                        properties=_sanitize_neo4j_props(dict(discovery.items()))
                    )

    # ── Finalize ──
    formatted = list(seen_results.values())
    formatted.sort(key=lambda r: r.score, reverse=True)
    
    _enrich_with_minio(formatted)
    
    # Enriched URLs propagation (reuse logic)
    url_by_hash = {}
    for item in formatted:
        props = item.properties
        if "download_url" in props:
            url_by_hash[item.uuid] = {"download_url": props["download_url"]}
            if "minio_path" in props:
                url_by_hash[item.uuid]["minio_path"] = props["minio_path"]

    for node in topo_nodes.values():
        if node.type == "DigitalAsset":
            node_hash = node.properties.get("hash") or node.properties.get("file_hash")
            if node_hash and node_hash in url_by_hash:
                node.properties.update(url_by_hash[node_hash])

    return GraphCrispResponse(
        query=req.query,
        concepts_matched=sorted(concepts_matched),
        alpha_cut=req.alpha_cut,
        total_results=len(formatted),
        results=formatted,
        graph_topology=GraphTopology(
            nodes=list(topo_nodes.values()),
            edges=topo_edges,
        ),
    )

