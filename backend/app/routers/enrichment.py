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

class CandidateResponse(BaseModel):
    candidates: List[CandidateNode]
    total: int

class EnrichRequest(BaseModel):
    node_ids: List[str]

class WeightPreviewResult(BaseModel):
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
    RETURN elementId(n) as id, n.name as name, labels(n)[0] as type, connections, n.enrichment_status as status, n.enrichment_error as error
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
                    error=record["error"]
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
                    # User requested formula: proposed_weight = (current_weight * 0.6) + (vector_sim * 0.4)
                    blended = (current_weight * 0.7) + (sim * 0.3)
                    proposed_weight = round(blended, 3)
        except Exception as e:
            logger.warning(f"No se pudo comparar vector para {filename} en {space}: {e}")
            
        preview_results.append(WeightPreviewResult(
            filename=filename,
            space=space,
            relation_type=asset.get("relation_type"),
            current_weight=current_weight,
            vector_similarity=vector_similarity,
            proposed_weight=proposed_weight
        ))
        
    return WeightPreviewResponse(results=preview_results)
