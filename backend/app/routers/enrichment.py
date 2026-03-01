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
    recommended_hub_name: Optional[str] = None

class RecommendMergesResponse(BaseModel):
    recommendations: List[MergeRecommendation]
    total_clusters: int
    demote_recommendations: List[ConceptNode] = []

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
def recommend_concept_merges(strategy: str = "middle"):
    """
    Use BGE-M3 embeddings to find semantically similar concepts that should be merged.
    Supported strategies: top, bottom, middle, upper-mid, lower-mid, random
    """
    driver = get_neo4j_driver()
    try:
        with driver.session() as session:
            count_res = session.run("MATCH (c:Concept) RETURN count(c) as total")
            total_concepts = count_res.single()["total"]
            
            if total_concepts == 0:
                return {"recommendations": [], "total_clusters": 0}
                
            skip_val = 0
            order_clause = "ORDER BY refs DESC"
            
            if strategy == "top":
                skip_val = 0
            elif strategy == "bottom":
                # Or just order ASC
                order_clause = "ORDER BY refs ASC"
            elif strategy == "upper-mid":
                skip_val = max(0, (total_concepts // 4) - 100)
            elif strategy == "lower-mid":
                skip_val = max(0, (total_concepts * 3 // 4) - 100)
            elif strategy == "random":
                import random
                skip_val = random.randint(0, max(0, total_concepts - 200))
            else: # middle default
                skip_val = max(0, (total_concepts // 2) - 100)
            
            query = f"""
            MATCH (c:Concept)
            OPTIONAL MATCH (c)-[r]-()
            WITH c, count(r) as refs
            {order_clause}
            SKIP $skip
            LIMIT 250
            RETURN elementId(c) as id, c.name as name, c.domain as domain
            """
            result = session.run(query, skip=skip_val)
            concepts = [{"id": r["id"], "name": r["name"], "domain": r["domain"] or ""} for r in result]
            
        if not concepts:
            return {"recommendations": [], "total_clusters": 0}
            
        import requests
        import json
        import re
        from config.settings import get_settings
        settings = get_settings()
        LLM_GATEWAY_URL = f"{settings.LLM_GATEWAY_URL}/v1"
        
        system_prompt = """You are an expert Ontological Data Curator and Knowledge Graph Architect.
Your task is twofold:
1. STRICT DEDUPLICATION: Identify concepts that are interchangeable synonyms to merge them into a single canonical Hub.
2. ONTOLOGICAL CLASSIFICATION (DEMOTION): Identify terms that represent physical objects, generic locations, aesthetic descriptors, or media formats, and flag them to be demoted to "Metadata Tags" (they must not exist as structural Hubs in the graph).

CRITICAL DISTINCTIONS FOR MERGING: 
- Do NOT group concepts just because they are related. 
- "Evolución biológica" and "Evolución de ideas" MUST remain separate. Do not merge across different domains (e.g., Biology vs. Sociology).
- ONLY group them if a user searching for Concept A would be 100% satisfied with results for Concept B (e.g., "Muerte" and "Finitud humana", or "IA" and "Inteligencia Artificial").


Input format: A list of concepts with their indices (e.g., "1. Concept Name").
Output format: You MUST return ONLY a valid JSON object. No markdown, no explanations.

Structure:
{
  "merges": [
    {
      "hub_name": "Nombre unificado en español",
      "concept_indices": [1, 5] 
    }
  ]
}

STRICT RULES:
1. Semantic Equivalence: Only merge exact same entities. "Manipulación psicológica" and "Manipulación genética" are DIFFERENT.
2. Root Word Trap: Do not group items simply because they share a word (e.g., "Libertad" and "Libertad financiera").
3. Demotion is Crucial: Be aggressive in demoting anything that you can touch, see, or that describes a file format. Only pure knowledge, entities, and abstractions deserve to be Graph Hubs.
4. The "hub_name" MUST be in Spanish and represent the most academic/standard term for the cluster.
"""

        all_clusters = []
        demote_list = []
        global_cluster_id = 1
        
        concepts_list_text = "\n".join([f"{i+1}. {c['name']} (Domain: {c['domain'] or 'None'})" for i, c in enumerate(concepts)])
        
        user_prompt = f"Here are the concepts to analyze:\n\n{concepts_list_text}\n\nReturn ONLY the JSON object."
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        data = {
            "task": "chat",
            "privacy_mode": "flexible",
            "messages": json.dumps(messages),
            "temperature": 0.1,
        }
        
        try:
            # Send all 200 elements in a single shot
            response = requests.post(f"{LLM_GATEWAY_URL}/chat/completions", data=data, timeout=60)
            if response.status_code != 200:
                logger.error(f"LLM validation HTTP {response.status_code}: {response.text[:300]}")
                return {"recommendations": [], "total_clusters": 0}
                
            result = response.json()
            raw_content = (
                result.get("choices", [{}])[0].get("message", {}).get("content", "")
                or result.get("answer", "")
                or result.get("content", "")
                or result.get("text", "")
                or result.get("response", "")
            ).strip()
            
            parsed_json = {}
            try:
                match = re.search(r'\{.*\}', raw_content, re.DOTALL)
                if match:
                    json_str = match.group(0)
                    parsed_json = json.loads(json_str)
                else:
                    parsed_json = json.loads(raw_content)
            except Exception as e:
                logger.error(f"Failed to parse LLM JSON response: {e}")
                
            merges_data = parsed_json.get("merges", [])
            demotes_data = parsed_json.get("demote_to_tags", [])
                
            if isinstance(merges_data, list):
                for cluster_data in merges_data:
                    hub_name = cluster_data.get("hub_name")
                    indices = cluster_data.get("concept_indices", [])
                    
                    if not hub_name or not isinstance(indices, list) or len(indices) < 2:
                        continue
                        
                    cluster_concepts = []
                    for idx in indices:
                        # 1-based to 0-based local index
                        if isinstance(idx, int) and 1 <= idx <= len(concepts):
                            c = concepts[idx - 1]
                            cluster_concepts.append(ConceptNode(id=c["id"], name=c["name"], domain=c["domain"]))
                            
                    if len(cluster_concepts) > 1:
                        all_clusters.append(MergeRecommendation(
                            cluster_id=global_cluster_id,
                            concepts=cluster_concepts,
                            similarity_score=1.0,
                            recommended_hub_name=hub_name
                        ))
                        global_cluster_id += 1
            
            if isinstance(demotes_data, list):
                for idx in demotes_data:
                    if isinstance(idx, int) and 1 <= idx <= len(concepts):
                        c = concepts[idx - 1]
                        demote_list.append(ConceptNode(id=c["id"], name=c["name"], domain=c["domain"]))
                        
        except requests.exceptions.Timeout:
            logger.error(f"LLM timeout while computing recommendations")
        except Exception as e:
            logger.error(f"Error computing LLM recommendations: {e}")
                
        # Sort by size just to have the biggest clusters first        
        all_clusters.sort(key=lambda c: len(c.concepts), reverse=True)
        return {
            "recommendations": all_clusters,
            "total_clusters": len(all_clusters),
            "demote_recommendations": demote_list
        }
        
    except Exception as e:
        logger.error(f"Error in recommend_concept_merges: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class DemoteConceptsRequest(BaseModel):
    source_names: List[str]

@router.post("/concepts/demote")
def demote_concepts(request: DemoteConceptsRequest):
    """
    Demotes structural Concept Hubs to plain tags on connected nodes.
    Deletes the Concept node and pushes its name to the `tags` array of relationships.
    """
    if not request.source_names:
        raise HTTPException(status_code=400, detail="Must provide at least one source concept to demote.")
        
    driver = get_neo4j_driver()
    
    demote_query = """
    UNWIND $source_names AS source_name
    MATCH (c:Concept {name: source_name})
    
    // Find everything connected to it
    OPTIONAL MATCH (c)-[r]-(m)
    WITH c, m, source_name
    
    // If it has a connected node (like a DigitalAsset), append the concept name to its tags
    CALL apoc.do.when(
        m IS NOT NULL,
        'SET m.tags = apoc.coll.toSet(coalesce(m.tags, []) + [source_name]) RETURN m',
        'RETURN NULL AS m',
        {m: m, source_name: source_name}
    ) YIELD value
    
    // Finally detach and delete the concept node itself
    WITH c
    DETACH DELETE c
    RETURN count(c) as deletions
    """
    
    try:
        with driver.session() as session:
            result = session.run(demote_query, source_names=request.source_names)
            totals = sum([record["deletions"] for record in result])
            return {"status": "success", "message": f"Se eliminaron y transformaron {totals} conceptos en tags.", "demoted_count": totals}
    except Exception as e:
        logger.error(f"Error demoting concepts: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to demote concepts: {e}")

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
    ON CREATE SET target.domain = $target_domain, target.created_at = datetime(), target.aliases = []
    ON MATCH SET target.domain = $target_domain
    
    WITH target
    
    // 2. Find all sources
    MATCH (source:Concept)
    WHERE source.name IN $source_names AND source.name <> $target_name
    
    // 3. Keep track of how many we found and safely extract aliases
    WITH target, collect(source) as sources
    
    // 4. Extract all names and existing aliases from sources to append to target
    UNWIND sources as source_for_alias
    WITH target, sources, collect(source_for_alias.name) + 
         reduce(acc = [], s IN sources | acc + coalesce(s.aliases, [])) as all_new_aliases,
         reduce(acc = [], s IN sources | acc + coalesce(s.tags, [])) as all_new_tags
    
    // 5. Deduplicate aliases and tags, add to target
    WITH target, sources, 
         apoc.coll.toSet(coalesce(target.aliases, []) + all_new_aliases) as final_aliases,
         apoc.coll.toSet(coalesce(target.tags, []) + all_new_tags) as final_tags
    SET target.aliases = final_aliases, target.tags = final_tags
    
    // 6. Rewire all incoming relationships to the target
    WITH target, sources
    UNWIND sources as source
    OPTIONAL MATCH (other)-[r]->(source)
    
    // Only merge relation if there was actually an incoming one
    CALL apoc.do.when(
        r IS NOT NULL,
        'MERGE (o)-[new_r:EVOKES_CONCEPT]->(t) ON CREATE SET new_r = rel, new_r.weight = coalesce(rel.weight, 1.0) ON MATCH SET new_r.weight = CASE WHEN coalesce(new_r.weight, 1.0) + coalesce(rel.weight, 1.0) > 1.0 THEN 1.0 ELSE coalesce(new_r.weight, 1.0) + coalesce(rel.weight, 1.0) END DELETE rel RETURN new_r',
        '',
        {o: other, t: target, rel: r}
    ) YIELD value
    
    // 7. Delete the source node
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
