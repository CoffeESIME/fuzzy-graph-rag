from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from shared.clients import get_neo4j_driver, get_weaviate_client
from worker.utils import generate_collection_uuid
from worker.tasks import call_text_embeddings_api
import logging
import math

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/enrichment", tags=["Enrichment"])

class CandidateNode(BaseModel):
    id: str
    name: str
    type: str
    connections: int
    status: Optional[str] = None
    error: Optional[str] = None
    fuzzy_applied: Optional[bool] = None

class CandidateResponse(BaseModel):
    candidates: List[CandidateNode]
    total: int

class EnrichRequest(BaseModel):
    node_ids: List[str]

class WeightPreviewResult(BaseModel):
    file_hash: str
    filename: str
    space: str
    relation_type: Optional[str] = None
    current_weight: float
    vector_similarity: Optional[float] = None
    proposed_weight: Optional[float]

class WeightPreviewResponse(BaseModel):
    results: List[WeightPreviewResult]

@router.get("/candidates", response_model=CandidateResponse)
def get_enrichment_candidates(
    node_type: str = Query("Person", description="Node type to filter"), 
    limit: int = Query(50, ge=1, le=500),
    status_filter: str = Query("PENDING", description="Filter by state (PENDING, PROCESSING, COMPLETED, FAILED, ALL)")
):
    driver = get_neo4j_driver()
    
    # We must sanitize the node_type to prevent Cypher injection since it will be a label
    allowed_types = ["Person", "Concept", "Location", "Organization", "Event", "Project", "Device", "Method"]
    if node_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"Invalid node type. Allowed types: {', '.join(allowed_types)}")
        
    where_clause = ""
    if status_filter == "PENDING":
        where_clause = "WHERE n.enriched IS NULL AND (n.enrichment_status IS NULL OR n.enrichment_status = 'PENDING')"
    elif status_filter == "PROCESSING":
        where_clause = "WHERE n.enrichment_status = 'PROCESSING'"
    elif status_filter == "COMPLETED":
        where_clause = "WHERE n.enrichment_status = 'COMPLETED' OR n.enriched = true"
    elif status_filter == "FAILED":
        where_clause = "WHERE n.enrichment_status = 'FAILED'"

    cypher_query = f"""
    MATCH (n:{node_type})
    {where_clause}
    OPTIONAL MATCH (n)<--(asset:DigitalAsset)
    WITH n, count(distinct asset) as connections
    RETURN elementId(n) as id, coalesce(n.name, n.title) as name, labels(n)[0] as type, connections, n.enrichment_status as status, n.enrichment_error as error, n.fuzzy_applied as fuzzy_applied
    ORDER BY connections DESC
    LIMIT $limit
    """
    
    try:
        with driver.session() as session:
            result = session.run(cypher_query, limit=limit)
            nodes = []
            for record in result:
                nodes.append(CandidateNode(
                    id=record["id"],
                    name=record["name"] or "Unknown",
                    type=record["type"],
                    connections=record["connections"],
                    status=record["status"],
                    error=record["error"],
                    fuzzy_applied=record["fuzzy_applied"]
                ))
            return CandidateResponse(candidates=nodes, total=len(nodes))
    except Exception as e:
        logger.error(f"Error fetching enrichment candidates: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/enrich", status_code=202)
def request_enrichment(req: EnrichRequest):
    if not req.node_ids:
        raise HTTPException(status_code=400, detail="No node IDs provided")
        
    logger.info(f"Received enrichment request for {len(req.node_ids)} nodes: {req.node_ids}")
    
    from worker.tasks import enrich_node_task
    
    # Dispatch a Celery task for each node_id
    for node_id in req.node_ids:
        enrich_node_task.delay(node_id)
        
    return {
        "status": "accepted", 
        "message": f"Se han encolado {len(req.node_ids)} nodos para enriquecimiento semántico.",
        "queued_count": len(req.node_ids)
    }

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = sum(a * a for a in v1) ** 0.5
    norm2 = sum(b * b for b in v2) ** 0.5
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)

@router.get("/{node_id}/preview-weights", response_model=WeightPreviewResponse)
def get_preview_weights(node_id: str):
    driver = get_neo4j_driver()
    
    query = """
    MATCH (n) WHERE elementId(n) = $node_id
    WITH n, n.description AS description
    OPTIONAL MATCH (n)-[r]-(asset:DigitalAsset)
    RETURN description, collect({
        file_hash: asset.file_hash,
        filename: asset.filename,
        mime_type: asset.mime_type,
        is_memory: coalesce(asset.is_memory, false),
        weight: coalesce(r.weight, 1.0),
        relation_type: type(r)
    }) AS assets
    """
    
    try:
        with driver.session() as session:
            result = session.run(query, node_id=node_id)
            record = result.single()
            
            if not record:
                raise HTTPException(status_code=404, detail="Nodo no encontrado")
            
            description = record["description"]
            if not description:
                raise HTTPException(status_code=400, detail="Este nodo aún no ha sido enriquecido (no tiene 'description').")
                
            assets = record["assets"]
            # filter out empty 
            valid_assets = [a for a in assets if a.get("file_hash")]
            
            if not valid_assets:
                return WeightPreviewResponse(results=[])
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error Neo4j query for preview weights: {e}")
        raise HTTPException(status_code=500, detail="Error de base de datos")

    # Vectorize the node description (in memory only)
    try:
        emb_res = call_text_embeddings_api(description)
        desc_vector = emb_res.get("embedding")
        if not desc_vector and "data" in emb_res:
            desc_vector = emb_res["data"][0].get("embedding")
            
        if not desc_vector:
            raise Exception("Formato inesperado del LLM Gateway")
    except Exception as e:
        logger.error(f"Error vectorizing description: {e}")
        raise HTTPException(status_code=500, detail="Error conectando al modelo vectorizador local")

    weaviate_client = get_weaviate_client()
    preview_results = []
    
    for asset in valid_assets:
        file_hash = asset["file_hash"]
        filename = asset["filename"]
        mime = asset.get("mime_type", "")
        is_memory = asset.get("is_memory", False)
        current_weight = float(asset["weight"])
        
        # Determine space and named vector
        if is_memory:
            space = "MemorySpace"
            vector_name = "default"
        elif mime.startswith("image/"):
            space = "VisualSpace"
            vector_name = "semantic"
        elif mime.startswith("audio/"):
            space = "AudioSpace"
            vector_name = "transcript_semantic"
        else:
            space = "TextSpace"
            vector_name = "default"
            
        weaviate_uuid = generate_collection_uuid(file_hash, space)
        
        proposed_weight = None
        vector_similarity = None
        try:
            collection = weaviate_client.collections.get(space)
            # Fetch object with its specific vector
            obj = collection.query.fetch_object_by_id(
                weaviate_uuid, 
                include_vector=[vector_name] if vector_name != "default" else True
            )
            
            if obj and obj.vector:
                # obj.vector can be a dict inside python v4 client
                target_vector = obj.vector.get(vector_name) if isinstance(obj.vector, dict) else obj.vector
                if target_vector:
                    sim = cosine_similarity(desc_vector, target_vector)
                    vector_similarity = round(sim, 3)
                    
                    relation_type = asset.get("relation_type")
                    protected_relations = ['CREATED_BY', 'DEFINES', 'LOCATED_AT']
                    
                    if relation_type in protected_relations:
                        proposed_weight = round(current_weight, 3)
                    else:
                        blended = (current_weight * 0.7) + (sim * 0.3)
                        proposed_weight = round(blended, 3)
        except Exception as e:
            logger.warning(f"No se pudo comparar vector para {filename} en {space}: {e}")
            
        preview_results.append(WeightPreviewResult(
            file_hash=file_hash,
            filename=filename,
            space=space,
            relation_type=asset.get("relation_type"),
            current_weight=current_weight,
            vector_similarity=vector_similarity,
            proposed_weight=proposed_weight
        ))
        
    return WeightPreviewResponse(results=preview_results)

class WeightUpdateItem(BaseModel):
    file_hash: str
    new_weight: float

class ApplyWeightsRequest(BaseModel):
    updates: List[WeightUpdateItem]

@router.post("/{node_id}/apply-weights")
def apply_preview_weights(node_id: str, req: ApplyWeightsRequest):
    """
    Applies the approved new semantic weights to the relationships in Neo4j.
    Uses UNWIND for efficient bulk updates.
    """
    if not req.updates:
        raise HTTPException(status_code=400, detail="No updates provided")
        
    driver = get_neo4j_driver()
    
    # Very fast UNWIND transaction
    cypher_query = """
    MATCH (n) WHERE elementId(n) = $node_id
    SET n.fuzzy_applied = true, n.fuzzy_applied_at = datetime()
    WITH n
    UNWIND $updates AS row
    MATCH (asset:DigitalAsset {file_hash: row.file_hash})
    MATCH (n)-[r]-(asset)
    SET r.weight = row.new_weight
    RETURN count(r) as updated_count
    """
    
    try:
        with driver.session() as session:
            updates_list = [{"file_hash": u.file_hash, "new_weight": u.new_weight} for u in req.updates]
            result = session.run(cypher_query, node_id=node_id, updates=updates_list)
            record = result.single()
            count = record["updated_count"] if record else 0
            
            logger.info(f"Updated {count} edge weights for node {node_id}")
            return {"status": "success", "message": f"Se actualizaron {count} pesos correctamente.", "updated_count": count}
    except Exception as e:
        logger.error(f"Error applying weights for node {node_id}: {e}")
        raise HTTPException(status_code=500, detail="Error actualizando los pesos en la base de datos de grafos.")

# ==========================================
# ONTOLOGICAL CLEANUP ENDPOINTS
# ==========================================

class ConceptNode(BaseModel):
    id: str
    name: str
    domain: Optional[str] = None

class ConceptListResponse(BaseModel):
    concepts: List[ConceptNode]
    total: int

class MergeRecommendation(BaseModel):
    cluster_id: int
    concepts: List[ConceptNode]
    similarity_score: float

class RecommendMergesResponse(BaseModel):
    recommendations: List[MergeRecommendation]
    total_clusters: int

class MergeConceptsRequest(BaseModel):
    target_name: str
    target_domain: str
    source_names: List[str]

@router.get("/concepts", response_model=ConceptListResponse)
def get_all_concepts():
    """
    Fetch all Concept nodes from Neo4j for ontological cleanup.
    """
    driver = get_neo4j_driver()
    query = """
    MATCH (c:Concept)
    RETURN elementId(c) as id, c.name as name, c.domain as domain
    ORDER BY c.name ASC
    """
    try:
        with driver.session() as session:
            result = session.run(query)
            concepts = [
                ConceptNode(
                    id=record["id"],
                    name=record["name"],
                    domain=record["domain"]
                )
                for record in result
            ]
            return {"concepts": concepts, "total": len(concepts)}
    except Exception as e:
        logger.error(f"Error fetching concepts: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if driver:
            driver.close()

@router.post("/concepts/recommend-merges", response_model=RecommendMergesResponse)
def recommend_concept_merges():
    """
    Use BGE-M3 embeddings to find semantically similar concepts that should be merged.
    """
    # 1. Fetch all concepts
    driver = get_neo4j_driver()
    try:
        with driver.session() as session:
            result = session.run("MATCH (c:Concept) RETURN elementId(c) as id, c.name as name, c.domain as domain")
            concepts = [{"id": r["id"], "name": r["name"], "domain": r["domain"] or ""} for r in result]
            
        if not concepts:
            return {"recommendations": [], "total_clusters": 0}
            
        # 2. Get Embeddings (Batching if necessary, but LLM Gateway handles it)
        import requests
        from config.settings import get_settings
        settings = get_settings()
        LLM_GATEWAY_URL = f"{settings.LLM_GATEWAY_URL}/v1"
        
        # Prepare text strings for embedding: "Name (Domain)"
        texts = [f"{c['name']} ({c['domain']})" if c['domain'] else c['name'] for c in concepts]
        
        embeddings = []
        # Process in batches of 50 to avoid gateway limits
        batch_size = 50
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i+batch_size]
            try:
                resp = requests.post(
                    f"{LLM_GATEWAY_URL}/embeddings/text/batch",
                    json={"texts": batch_texts, "normalize": True},
                    timeout=60
                )
                
                # Fallback to individual calls if batch fails (or endpoint doesn't exist)
                if resp.status_code == 404:
                    for text in batch_texts:
                        single_resp = requests.post(
                            f"{LLM_GATEWAY_URL}/embeddings/text",
                            json={"text": text, "normalize": True},
                            timeout=30
                        )
                        single_resp.raise_for_status()
                        embeddings.append(single_resp.json().get("embedding", []))
                else:
                    resp.raise_for_status()
                    batch_embs = resp.json().get("embeddings", [])
                    embeddings.extend(batch_embs)
            except Exception as e:
                logger.error(f"Error getting embeddings for batch: {e}")
                
        if len(embeddings) != len(concepts):
            logger.warning("Could not get embeddings for all concepts. Skipping clustering.")
            return {"recommendations": [], "total_clusters": 0}
            
        # 3. Compute pairwise similarities and group clusters (cosine similarity > 0.85)
        # Using a simple greedy clustering algorithm
        import numpy as np
        emb_matrix = np.array(embeddings)
        
        # Check if matrix is valid
        if len(emb_matrix) == 0 or len(emb_matrix.shape) < 2:
            return {"recommendations": [], "total_clusters": 0}
            
        # Normalize just in case
        norms = np.linalg.norm(emb_matrix, axis=1, keepdims=True)
        # Avoid division by zero
        norms[norms == 0] = 1 
        emb_matrix = emb_matrix / norms
        
        # Dot product gives cosine similarity for normalized vectors
        similarity_matrix = np.dot(emb_matrix, emb_matrix.T)
        
        clusters = []
        visited = set()
        SIMILARITY_THRESHOLD = 0.85
        
        for i in range(len(concepts)):
            if i in visited:
                continue
                
            cluster = [i]
            visited.add(i)
            
            for j in range(i + 1, len(concepts)):
                if j not in visited and similarity_matrix[i, j] > SIMILARITY_THRESHOLD:
                    cluster.append(j)
                    visited.add(j)
                    
            # Only keep clusters with > 1 item
            if len(cluster) > 1:
                # Calculate avg internal similarity
                sub_matrix = similarity_matrix[np.ix_(cluster, cluster)]
                # Average ignoring the diagonal (self-similarity = 1)
                n = len(cluster)
                avg_sim = (np.sum(sub_matrix) - n) / (n * (n - 1)) if n > 1 else 1.0
                
                cluster_concepts = [
                    ConceptNode(id=concepts[idx]["id"], name=concepts[idx]["name"], domain=concepts[idx]["domain"])
                    for idx in cluster
                ]
                
                clusters.append(MergeRecommendation(
                    cluster_id=len(clusters) + 1,
                    concepts=cluster_concepts,
                    similarity_score=round(float(avg_sim), 4)
                ))
                
        # Sort clusters by similarity score and size
        clusters.sort(key=lambda c: (len(c.concepts), c.similarity_score), reverse=True)
        
        return {"recommendations": clusters, "total_clusters": len(clusters)}
        
    except Exception as e:
        logger.error(f"Error in recommend_concept_merges: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if driver:
            driver.close()

@router.post("/concepts/merge")
def merge_concepts(request: MergeConceptsRequest):
    """
    Merge multiple source concepts into a single target concept.
    Rewires all EVOKES_CONCEPT relationships and drops the old nodes.
    """
    if not request.source_names:
        raise HTTPException(status_code=400, detail="Must provide at least one source concept to merge.")
        
    driver = get_neo4j_driver()
    
    # Using pure Cypher
    merge_query = """
    // 1. Ensure target node exists
    MERGE (target:Concept {name: $target_name})
    ON CREATE SET target.domain = $target_domain, target.created_at = datetime()
    ON MATCH SET target.domain = $target_domain
    
    WITH target
    
    // 2. Find all sources
    MATCH (source:Concept)
    WHERE source.name IN $source_names AND source.name <> $target_name
    
    // 3. Keep track of how many we found
    WITH target, collect(source) as sources
    
    // 4. Rewire all incoming relationships to the target
    UNWIND sources as source
    MATCH (other)-[r]->(source)
    
    // Use APOC if available for generic relationship merge, 
    // but here we know it's always EVOKES_CONCEPT or similar incoming links
    MERGE (other)-[new_r:EVOKES_CONCEPT]->(target)
    ON CREATE SET new_r = r, new_r.weight = coalesce(r.weight, 1.0)
    
    // 5. Delete the old relationship
    DELETE r
    
    // 6. Delete the source node
    WITH sources
    UNWIND sources as source
    // Use DETACH DELETE just to be completely safe against dangling edges
    DETACH DELETE source
    
    RETURN size(sources) as merged_count
    """
    
    try:
        with driver.session() as session:
            result = session.run(
                merge_query, 
                target_name=request.target_name, 
                target_domain=request.target_domain,
                source_names=request.source_names
            )
            record = result.single()
            merged_count = record["merged_count"] if record else 0
            
            return {
                "status": "success", 
                "message": f"Successfully merged {merged_count} concepts into '{request.target_name}'.",
                "merged_count": merged_count
            }
    except Exception as e:
        logger.error(f"Error merging concepts: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if driver:
            driver.close()
