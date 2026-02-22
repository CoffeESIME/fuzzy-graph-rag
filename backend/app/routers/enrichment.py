from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List
from shared.clients import get_neo4j_driver
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/enrichment", tags=["Enrichment"])

class CandidateNode(BaseModel):
    id: str
    name: str
    type: str
    connections: int

class CandidateResponse(BaseModel):
    candidates: List[CandidateNode]
    total: int

class EnrichRequest(BaseModel):
    node_ids: List[str]

@router.get("/candidates", response_model=CandidateResponse)
def get_enrichment_candidates(node_type: str = Query("Person", description="Node type to filter (e.g., Person, Concept, Location)"), limit: int = Query(50, ge=1, le=500)):
    driver = get_neo4j_driver()
    
    # We must sanitize the node_type to prevent Cypher injection since it will be a label
    allowed_types = ["Person", "Concept", "Location", "Organization", "Event", "Project", "Device", "Method"]
    if node_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"Invalid node type. Allowed types: {', '.join(allowed_types)}")
        
    cypher_query = f"""
    MATCH (n:{node_type})
    WHERE n.enriched IS NULL
    OPTIONAL MATCH (n)<--(asset:DigitalAsset)
    WITH n, count(distinct asset) as connections
    RETURN elementId(n) as id, n.name as name, labels(n)[0] as type, connections
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
                    connections=record["connections"]
                ))
            return CandidateResponse(candidates=nodes, total=len(nodes))
    except Exception as e:
        logger.error(f"Error fetching enrichment candidates: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/enrich")
def request_enrichment(req: EnrichRequest):
    # This is a placeholder for the actual Celery task spawning
    if not req.node_ids:
        raise HTTPException(status_code=400, detail="No node IDs provided")
        
    # TODO: spawn enrichment tasks when the worker logic is ready
    logger.info(f"Received enrichment request for {len(req.node_ids)} nodes: {req.node_ids}")
    
    return {
        "status": "ok", 
        "message": f"Se han encolado {len(req.node_ids)} nodos para enriquecimiento semántico.",
        "queued_count": len(req.node_ids)
    }
