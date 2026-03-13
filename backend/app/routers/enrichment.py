# Copyright (C) 2026 Fabian Romero Hernandez
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License v3.0.
#
# This project is part of an independent academic research on Fuzzy Logic-based
# Multimodal Graph RAG systems (hechoconcafeina).
# Full license: https://www.gnu.org/licenses/agpl-3.0

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from shared.clients import get_neo4j_driver, get_weaviate_client
from worker.utils import generate_collection_uuid
# NOTE: call_text_embeddings_api is imported locally inside the endpoint
# to avoid the circular import: worker.tasks → app → enrichment → worker.tasks
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
    elif status_filter == "UNAPPLIED":
        where_clause = "WHERE (n.enrichment_status = 'COMPLETED' OR n.enriched = true) AND coalesce(n.fuzzy_applied, false) = false"
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
        "message": f"Se han encolado {len(req.node_ids)} nodos para enriquecimiento semÃƒÂ¡ntico.",
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
def get_preview_weights(
    node_id: str,
    semantic_weight: float = Query(0.3, ge=0.0, le=1.0, description="Weight of the semantic/vector similarity component (0=ignore vectors, 1=use only vectors)")
):
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
                raise HTTPException(status_code=400, detail="Este nodo aÃƒÂºn no ha sido enriquecido (no tiene 'description').")
                
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
        from worker.tasks import call_text_embeddings_api  # local import to avoid circular dependency
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
                        MIN_SIM = 0.15
                        MAX_SIM = 0.75
                        sim_normalizada = (sim - MIN_SIM) / (MAX_SIM - MIN_SIM)
                        sim_normalizada = max(0.0, min(1.0, sim_normalizada))
                        blended = (current_weight * (1.0 - semantic_weight)) + (sim_normalizada * semantic_weight)
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
                
            if strategy in ["high-low", "high-mid", "mid-low"]:
                # Mixed strategies logic
                mid_skip = max(0, (total_concepts // 2) - 62)
                
                parts = strategy.split("-")
                part_queries = []
                
                for p in parts:
                    if p == "high":
                        part_queries.append({"order": "ORDER BY refs DESC", "skip": 0})
                    elif p == "low":
                        part_queries.append({"order": "ORDER BY refs ASC", "skip": 0})
                    elif p == "mid":
                        part_queries.append({"order": "ORDER BY refs DESC", "skip": mid_skip})
                        
                concepts = []
                seen_ids = set()
                
                for p_idx, p_args in enumerate(part_queries):
                    q = f"""
                    MATCH (c:Concept)
                    OPTIONAL MATCH (c)-[r]-()
                    WITH c, count(r) as refs
                    {p_args['order']}
                    SKIP $skip
                    LIMIT 125
                    RETURN elementId(c) as id, c.name as name, c.domain as domain
                    """
                    result = session.run(q, skip=p_args["skip"])
                    for r in result:
                        if r["id"] not in seen_ids:
                            seen_ids.add(r["id"])
                            concepts.append({"id": r["id"], "name": r["name"], "domain": r["domain"] or ""})
            else:
                # Standard strategies logic
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
- "EvoluciÃƒÂ³n biolÃƒÂ³gica" and "EvoluciÃƒÂ³n de ideas" MUST remain separate. Do not merge across different domains (e.g., Biology vs. Sociology).
- ONLY group them if a user searching for Concept A would be 100% satisfied with results for Concept B (e.g., "Muerte" and "Finitud humana", or "IA" and "Inteligencia Artificial").


Input format: A list of concepts with their indices (e.g., "1. Concept Name").
Output format: You MUST return ONLY a valid JSON object. No markdown, no explanations.

Structure:
{
  "merges": [
    {
      "hub_name": "Nombre unificado en espaÃƒÂ±ol",
      "concept_indices": [1, 5] 
    }
  ]
}

STRICT RULES:
1. Semantic Equivalence: Only merge exact same entities. "ManipulaciÃƒÂ³n psicolÃƒÂ³gica" and "ManipulaciÃƒÂ³n genÃƒÂ©tica" are DIFFERENT.
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

# ==========================================
# ENTITY DEDUP ENDPOINTS
# ==========================================

class EntityNode(BaseModel):
    id: str
    name: str
    type: str
    connections: int

class EntityListResponse(BaseModel):
    entities: List[EntityNode]
    total: int

class MergeEntitiesRequest(BaseModel):
    node_type: str
    target_name: str
    source_ids: List[str]   # element IDs of nodes to delete after rewiring
    keep_id: str            # element ID of the surviving hub node

@router.get("/entities", response_model=EntityListResponse)
def get_entities(
    node_type: str = Query("Person", description="Entity type: Person|Project|Location|Organization|Event|Device|Method"),
    search: str = Query("", description="Case-insensitive substring filter on name"),
    limit: int = Query(200, ge=1, le=1000)
):
    """
    Lists all nodes of a given structural entity type, ordered by connection count.
    Supports substring search on name.
    """
    allowed_types = ["Person", "Project", "Location", "Organization", "Event", "Device", "Method"]
    if node_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"Invalid node_type. Allowed: {', '.join(allowed_types)}")

    driver = get_neo4j_driver()
    search_clause = "AND toLower(coalesce(n.name, n.title, '')) CONTAINS toLower($search)" if search.strip() else ""

    cypher = f"""
    MATCH (n:{node_type})
    OPTIONAL MATCH (n)--(nb)
    WITH n, count(distinct nb) as connections
    WHERE 1=1 {search_clause}
    RETURN elementId(n) as id, coalesce(n.name, n.title, 'Unknown') as name, labels(n)[0] as type, connections
    ORDER BY connections DESC
    LIMIT $limit
    """

    try:
        with driver.session() as session:
            result = session.run(cypher, search=search.strip(), limit=limit)
            entities = [
                EntityNode(
                    id=record["id"],
                    name=record["name"],
                    type=record["type"],
                    connections=record["connections"]
                )
                for record in result
            ]
            return EntityListResponse(entities=entities, total=len(entities))
    except Exception as e:
        logger.error(f"Error fetching entities of type {node_type}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/entities/merge")
def merge_entity_nodes(req: MergeEntitiesRequest):
    """
    Merges duplicate entity nodes into a single hub.
    For each source_id (not the keep_id):
      1. Rewires all incoming and outgoing relationships to the hub (keep_id).
      2. Renames the hub to target_name.
      3. DETACH DELETEs the duplicate node.
    Uses pure Cypher (no APOC dependency).
    """
    allowed_types = ["Person", "Project", "Location", "Organization", "Event", "Device", "Method"]
    if req.node_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"Invalid node_type. Allowed: {', '.join(allowed_types)}")

    if not req.target_name.strip():
        raise HTTPException(status_code=400, detail="target_name cannot be empty")

    source_ids = [sid for sid in req.source_ids if sid != req.keep_id]
    if not source_ids:
        raise HTTPException(status_code=400, detail="No source_ids to merge (after excluding keep_id)")

    driver = get_neo4j_driver()
    total_merged = 0

    try:
        with driver.session() as session:
            # Step 1: Rename the hub node
            session.run(
                "MATCH (hub) WHERE elementId(hub) = $keep_id SET hub.name = $name",
                keep_id=req.keep_id,
                name=req.target_name.strip()
            )

            for source_id in source_ids:
                # Fetch outgoing relationships
                out_rels = list(session.run(
                    """
                    MATCH (src)-[r]->(tgt)
                    WHERE elementId(src) = $source_id
                    RETURN type(r) as rtype, elementId(tgt) as tgt_id, properties(r) as rprops
                    """,
                    source_id=source_id
                ))

                # Fetch incoming relationships
                in_rels = list(session.run(
                    """
                    MATCH (src)<-[r]-(tgt)
                    WHERE elementId(src) = $source_id
                    RETURN type(r) as rtype, elementId(tgt) as tgt_id, properties(r) as rprops
                    """,
                    source_id=source_id
                ))

                # Recreate outgoing: hub -[rtype]-> tgt
                for rel in out_rels:
                    tgt_id = rel["tgt_id"]
                    if tgt_id == req.keep_id:
                        continue  # avoid self-loop
                    rtype = rel["rtype"]
                    rprops = dict(rel["rprops"])
                    try:
                        session.run(
                            f"""
                            MATCH (hub) WHERE elementId(hub) = $keep_id
                            MATCH (tgt)  WHERE elementId(tgt)  = $tgt_id
                            MERGE (hub)-[r:`{rtype}`]->(tgt)
                            SET r += $rprops
                            """,
                            keep_id=req.keep_id, tgt_id=tgt_id, rprops=rprops
                        )
                    except Exception as re:
                        logger.warning(f"Could not recreate outgoing {rtype} for {source_id}: {re}")

                # Recreate incoming: tgt -[rtype]-> hub
                for rel in in_rels:
                    tgt_id = rel["tgt_id"]
                    if tgt_id == req.keep_id:
                        continue  # avoid self-loop
                    rtype = rel["rtype"]
                    rprops = dict(rel["rprops"])
                    try:
                        session.run(
                            f"""
                            MATCH (hub) WHERE elementId(hub) = $keep_id
                            MATCH (tgt)  WHERE elementId(tgt)  = $tgt_id
                            MERGE (tgt)-[r:`{rtype}`]->(hub)
                            SET r += $rprops
                            """,
                            keep_id=req.keep_id, tgt_id=tgt_id, rprops=rprops
                        )
                    except Exception as re:
                        logger.warning(f"Could not recreate incoming {rtype} for {source_id}: {re}")

                # DETACH DELETE the duplicate node
                session.run(
                    "MATCH (src) WHERE elementId(src) = $source_id DETACH DELETE src",
                    source_id=source_id
                )
                total_merged += 1
                logger.info(f"Merged entity {source_id} into hub {req.keep_id} ({req.target_name})")

        return {
            "status": "success",
            "message": f"Se fusionaron {total_merged} nodo(s) en '{req.target_name}'. Todas sus relaciones fueron transferidas.",
            "merged_count": total_merged
        }
    except Exception as e:
        logger.error(f"Error merging entity nodes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class DemoteEntitiesRequest(BaseModel):
    node_type: str
    source_ids: List[str]

@router.post("/entities/demote")
def demote_entity_nodes(req: DemoteEntitiesRequest):
    """
    Demotes entity nodes to tags on their connected DigitalAssets.
    For each source node:
      1. Reads its name.
      2. Appends the name to the `tags` array of every connected DigitalAsset.
      3. DETACH DELETEs the entity node.
    """
    allowed_types = ["Person", "Project", "Location", "Organization", "Event", "Device", "Method"]
    if req.node_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"Invalid node_type. Allowed: {', '.join(allowed_types)}")
    if not req.source_ids:
        raise HTTPException(status_code=400, detail="source_ids cannot be empty")

    driver = get_neo4j_driver()
    total_demoted = 0

    try:
        with driver.session() as session:
            for source_id in req.source_ids:
                # Get and store the name as tag on connected DigitalAssets 
                session.run(
                    """
                    MATCH (e) WHERE elementId(e) = $source_id
                    OPTIONAL MATCH (e)--(a:DigitalAsset)
                    WITH e, collect(a) as assets
                    FOREACH (a IN assets |
                        SET a.tags = CASE
                            WHEN a.tags IS NULL THEN [coalesce(e.name, e.title, '')]
                            ELSE a.tags + [coalesce(e.name, e.title, '')]
                        END
                    )
                    WITH e
                    DETACH DELETE e
                    """,
                    source_id=source_id
                )
                total_demoted += 1
                logger.info(f"Demoted entity {source_id} to tags")

        return {
            "status": "success",
            "message": f"Se degradaron {total_demoted} entidad(es) a tags en los activos conectados.",
            "demoted_count": total_demoted
        }
    except Exception as e:
        logger.error(f"Error demoting entity nodes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class RetypeEntityRequest(BaseModel):
    node_id: str
    from_type: str
    to_type: str

@router.post("/entities/retype")
def retype_entity_node(req: RetypeEntityRequest):
    """
    Changes the Neo4j label of an entity node (e.g., Person â†’ Organization).
    Keeps all existing relationships intact.
    Uses string-interpolated Cypher with a whitelist guard for safety.
    """
    allowed_types = ["Person", "Project", "Location", "Organization", "Event", "Device", "Method"]
    if req.from_type not in allowed_types or req.to_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"Invalid type. Allowed: {', '.join(allowed_types)}")
    if req.from_type == req.to_type:
        raise HTTPException(status_code=400, detail="from_type and to_type must be different")

    driver = get_neo4j_driver()
    try:
        with driver.session() as session:
            result = session.run(
                f"""
                MATCH (n:{req.from_type}) WHERE elementId(n) = $node_id
                REMOVE n:{req.from_type}
                SET n:{req.to_type}
                RETURN coalesce(n.name, n.title) as name
                """,
                node_id=req.node_id
            )
            record = result.single()
            if not record:
                raise HTTPException(status_code=404, detail=f"Node not found or not of type {req.from_type}")
            name = record["name"]
            logger.info(f"Retyped entity '{name}' from {req.from_type} to {req.to_type}")
            return {
                "status": "success",
                "message": f"'{name}' ahora es de tipo {req.to_type} (era {req.from_type}).",
                "name": name
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retyping entity node: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entities/relation-types")
def get_graph_relation_types():
    """
    Returns all distinct relationship types currently present in the graph.
    Used by the cross-type merge UI to let users inspect/remap relationship types.
    """
    driver = get_neo4j_driver()
    try:
        with driver.session() as session:
            result = session.run("CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType ORDER BY relationshipType")
            types = [r["relationshipType"] for r in result]
            return {"relation_types": types, "count": len(types)}
    except Exception as e:
        logger.error(f"Error fetching relation types: {e}")
        raise HTTPException(status_code=500, detail=str(e))
