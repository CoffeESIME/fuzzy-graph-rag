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
from typing import List, Optional, Dict, Any
import logging
import math
import json
import re
import requests
from shared.clients import get_neo4j_driver, get_weaviate_client, get_minio_client
from worker.utils import generate_collection_uuid
import weaviate.classes.query as wq
from config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/explore", tags=["ExploreLatentConnections"])

# ----------------------------
# Models
# ----------------------------

class SeedNode(BaseModel):
    id: str
    name: str
    type: str
    connections: int

class SeedResponse(BaseModel):
    seeds: List[SeedNode]
    total: int

class LatentConnectionSuggestion(BaseModel):
    asset_id: str
    asset_name: str
    target_concept_id: str
    target_concept_name: str
    relation_type: str
    current_weight: float
    cosine_similarity: float
    proposed_weight: float
    direction: str
    reasoning: str

class LatentConnectionResponse(BaseModel):
    seed_id: str
    seed_name: str
    suggestions: List[LatentConnectionSuggestion]

class ApproveConnectionRequest(BaseModel):
    asset_id: str
    target_concept_id: str
    relation_type: str
    proposed_weight: float
    reasoning: str

class AssetPreviewResponse(BaseModel):
    id: str
    name: str
    type: str
    tags: List[str]
    content: str
    mime_type: Optional[str] = None
    minio_path: Optional[str] = None
    download_url: Optional[str] = None

class ValidateConnectionSuggestion(BaseModel):
    key: str           # unique identifier: asset_id-target_concept_id-relation_type-direction
    asset_name: str
    target_concept_name: str
    relation_type: str
    direction: str
    reasoning: str

class ValidateConnectionsRequest(BaseModel):
    asset_name: str
    asset_content: str  # text content or empty for media; tags as comma-separated string
    asset_mime_type: Optional[str] = None
    suggestions: List[ValidateConnectionSuggestion]

class ValidateConnectionsResponse(BaseModel):
    valid_keys: List[str]
    removed_count: int
    llm_explanation: str

# Helper functions
def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = sum(a * a for a in v1) ** 0.5
    norm2 = sum(b * b for b in v2) ** 0.5
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)

# ----------------------------
# Endpoints
# ----------------------------

@router.post("/validate-connections", response_model=ValidateConnectionsResponse)
def validate_connections_with_llm(req: ValidateConnectionsRequest):
    """
    Sends the asset context + proposed latent connections to the local LLM.
    The LLM validates which connections semantically make sense and returns
    only the valid ones as a JSON array. Invalid/noise connections are filtered out.
    """
    llm_url = f"{settings.LLM_GATEWAY_URL}/v1/chat/completions"

    is_image = req.asset_mime_type and req.asset_mime_type.startswith("image/")
    is_audio = req.asset_mime_type and req.asset_mime_type.startswith("audio/")

    # Build asset context block
    if is_image:
        asset_context = f"Asset: \"{req.asset_name}\" (image)\nContextual tags/description: {req.asset_content or 'none'}"
    elif is_audio:
        asset_context = f"Asset: \"{req.asset_name}\" (audio file)\nContextual tags/description: {req.asset_content or 'none'}"
    else:
        content_snippet = req.asset_content[:1200] if req.asset_content else "no content available"
        asset_context = f"Asset: \"{req.asset_name}\"\nContent snippet:\n---\n{content_snippet}\n---"

    # Build numbered connection list using SHORT INDICES (not full keys!)
    # This keeps the LLM response tiny â€” it only needs to return numbers, not 100-char Neo4j IDs
    connection_lines = []
    for i, s in enumerate(req.suggestions):
        direction_label = "asset â†’ concept" if s.direction == "seed_to_neighbor" else "concept â†’ asset"
        connection_lines.append(
            f'{i+1}. [{direction_label}] {s.relation_type}: "{s.target_concept_name}"'
        )
    connections_text = "\n".join(connection_lines)

    system_prompt = """You are a strict semantic knowledge graph validator.
Your job: decide which proposed connections between an asset and semantic concepts are GENUINELY supported by the asset's actual content.

APPROVE a connection only if the concept:
- Is explicitly mentioned or directly discussed in the asset, OR
- Is a core subject/technology/entity the asset is clearly about.

REJECT a connection if it requires:
- Metaphorical or allegorical interpretation ("spy animals evoke Sisyphus")
- Symbolic or mythological stretch ("craftiness â†’ Odysseus")
- Indirect thematic association ("endless tasks â†’ frustration â†’ Greek myth")
- Concepts from a different domain that are not actually present in the asset.

Be very strict. When in doubt, reject.
Return ONLY valid JSON: {"valid_indices": [1, 3, 5, ...], "explanation": "one sentence"}
Use 1-based index numbers. Do NOT include any text outside the JSON."""

    user_prompt = f"""{asset_context}

Proposed connections (use the number to refer to each):
{connections_text}

Return JSON only: {{"valid_indices": [1, 2, ...], "explanation": "..."}}"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    data = {
        "task": "chat",
        "privacy_mode": "flexible",
        "messages": json.dumps(messages),
        "temperature": 0.1,
        "max_tokens": 512,  # Small: only needs to return numbers like [1,3,5,...]
    }

    all_keys = [s.key for s in req.suggestions]

    try:
        response = requests.post(llm_url, data=data, timeout=60)
        if response.status_code != 200:
            logger.error(f"LLM validation HTTP {response.status_code}: {response.text[:300]}")
            raise HTTPException(status_code=502, detail=f"LLM gateway error: HTTP {response.status_code}")

        result = response.json()

        # Log the actual response structure for diagnosis
        logger.info(f"LLM gateway response keys: {list(result.keys())}")
        logger.info(f"LLM gateway response preview: {str(result)[:300]}")

        # Try every possible response field â€” OpenAI format, SynthesizeResponse, plain content
        raw_content = (
            result.get("choices", [{}])[0].get("message", {}).get("content", "")
            or result.get("answer", "")
            or result.get("content", "")
            or result.get("text", "")
            or result.get("response", "")
        ).strip()

        logger.info(f"Extracted raw_content ({len(raw_content)} chars): {raw_content[:200]}")

        # Parse JSON from LLM response â€” robust multi-attempt strategy
        parsed = None
        try:
            parsed = json.loads(raw_content)
        except json.JSONDecodeError as decode_err:
            logger.warning(f"First json.loads failed ({decode_err}), trying find/rfind extraction ({len(raw_content)} chars)")
            start = raw_content.find('{')
            end = raw_content.rfind('}')
            if start != -1 and end != -1 and end > start:
                candidate = raw_content[start:end + 1]
                try:
                    parsed = json.loads(candidate)
                except json.JSONDecodeError as decode_err2:
                    logger.warning(f"Extraction also failed ({decode_err2}): {candidate[:200]}")

        if parsed is None:
            logger.warning(f"Could not parse LLM JSON â€” returning all keys. Raw: {raw_content[:200]}")
            return ValidateConnectionsResponse(
                valid_keys=all_keys,
                removed_count=0,
                llm_explanation="No se pudo parsear la respuesta del LLM. Se devuelven todas las conexiones."
            )

        # Map 1-based indices back to actual keys
        raw_indices = parsed.get("valid_indices", None)
        if raw_indices is None:
            # Fallback: if model returned valid_keys strings instead of indices, try that
            raw_keys = parsed.get("valid_keys", None)
            if raw_keys is not None:
                valid_keys = [k for k in raw_keys if k in set(all_keys)]
            else:
                valid_keys = all_keys  # could not determine â€” keep all
        else:
            valid_keys = []
            for idx in raw_indices:
                try:
                    i = int(idx) - 1  # convert 1-based to 0-based
                    if 0 <= i < len(all_keys):
                        valid_keys.append(all_keys[i])
                except (ValueError, TypeError):
                    pass

        explanation = parsed.get("explanation", "ValidaciÃ³n completada.")
        removed = len(all_keys) - len(valid_keys)
        logger.info(f"LLM validation: {len(valid_keys)} valid / {removed} removed from {len(all_keys)} suggestions")

        return ValidateConnectionsResponse(
            valid_keys=valid_keys,
            removed_count=removed,
            llm_explanation=explanation,
        )

    except requests.Timeout:
        raise HTTPException(status_code=504, detail="LLM gateway timeout during validation")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in validate_connections_with_llm: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/seeds", response_model=SeedResponse)
def get_explorable_seeds(
    node_type: str = Query("Person", description="Node type to search for seeds"),
    limit: int = Query(50, ge=1, le=200),
    sort_by: str = Query("top_connected", description="Sorting strategy: top_connected | random | least_connected"),
    search: str = Query("", description="Text filter on asset name/filename/title"),
):
    """
    Returns eligible DigitalAsset nodes for latent exploration.
    sort_by options:
      - top_connected   â†’ most connections first (default, same as before)
      - random          â†’ random sample each time using rand()
      - least_connected â†’ assets with fewest graph connections (underexplored)
    search filters by substring on name/filename/title (case-insensitive).
    """
    driver = get_neo4j_driver()

    search_clause = ""
    if search.strip():
        search_clause = "AND toLower(coalesce(n.name, n.filename, n.title, '')) CONTAINS toLower($search)"

    if sort_by == "random":
        order_clause = "ORDER BY rand()"
    elif sort_by == "least_connected":
        order_clause = "ORDER BY connections ASC"
    else:  # top_connected (default)
        order_clause = "ORDER BY connections DESC"

    query = f"""
    MATCH (n:DigitalAsset)
    OPTIONAL MATCH (n)--(nb)
    WITH n, count(nb) as connections
    WHERE 1=1 {search_clause}
    RETURN elementId(n) as id,
           coalesce(n.name, n.filename, n.title, 'Unknown') as name,
           labels(n)[0] as type,
           connections
    {order_clause}
    LIMIT $limit
    """

    try:
        with driver.session() as session:
            result = session.run(query, limit=limit, search=search.strip())
            nodes = [
                SeedNode(
                    id=record["id"],
                    name=record["name"],
                    type=record["type"],
                    connections=record["connections"]
                ) for record in result
            ]
            return {"seeds": nodes, "total": len(nodes)}
    except Exception as e:
        logger.error(f"Error fetching seeds: {e}")
        raise HTTPException(status_code=500, detail="Database Error")

@router.get("/latent-connections/{node_id}", response_model=LatentConnectionResponse)
def get_latent_connections(
    node_id: str,
    top_k: int = Query(5, ge=1, le=20),
    alpha: float = Query(0.3, ge=0.0, le=1.0, description="Weight of vector similarity in fuzzy calculation")
):
    """
    Finds latent connection suggestions for a given seed node.
    It takes the relationships from the seed, finds semantic neighbors of the seed,
    and proposes inheriting those relationships to the neighbors if they don't exist yet.
    """
    driver = get_neo4j_driver()
    weaviate_client = get_weaviate_client()
    
    # 1. Fetch seed node info + vector info
    query_seed = """
    MATCH (n) WHERE elementId(n) = $node_id
    RETURN coalesce(n.name, n.title, n.filename) as name, labels(n)[0] as type, n.file_hash as hash
    """
    
    seed_name = ""
    seed_type = ""
    seed_hash = None
    
    try:
        with driver.session() as session:
            r_seed = session.run(query_seed, node_id=node_id).single()
            if not r_seed:
                raise HTTPException(status_code=404, detail="Seed node not found")
            seed_name = r_seed["name"]
            seed_type = r_seed["type"]
            seed_hash = r_seed["hash"]
            
            # Fetch relationships OF the seed to external concepts
            query_rels = """
            MATCH (seed)-[r]->(target)
            WHERE elementId(seed) = $node_id AND (target:Concept OR target:Event OR target:Organization OR target:Person OR target:Location OR target:Project)
            RETURN elementId(target) as target_id, coalesce(target.name, target.title) as target_name, 
                   type(r) as relation_type, coalesce(toFloat(r.weight), 1.0) as current_weight
            """
            seed_relations = [dict(record) for record in session.run(query_rels, node_id=node_id)]
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching seed details: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving graph relationships")

    if not seed_relations:
        # Optimization: no relations to inherit
        return {"seed_id": node_id, "seed_name": seed_name, "suggestions": []}

    # 2. Get Seed Vector from Weaviate (Currently assuming DigitalAssets are seeds mainly)
    # If the seed is a DigitalAsset, we expect it to be in TextSpace, AudioSpace, VisualSpace
    # If it's a concept, we need a way to look it up in Concept embeddings if they exist.
    # For now, let's look up all spaces where it could reside based on file_hash or UUID.
    
    target_vector = None
    target_vector_name = None
    collection = None
    
    if seed_hash:
        spaces_to_check = ["TextSpace", "VisualSpace", "AudioSpace", "MemorySpace"]
        for space in spaces_to_check:
            try:
                coll = weaviate_client.collections.get(space)
                uid = generate_collection_uuid(seed_hash, space)
                obj = coll.query.fetch_object_by_id(uid, include_vector=True)
                if obj and obj.vector:
                    if space == "VisualSpace" and isinstance(obj.vector, dict) and "semantic" in obj.vector:
                        target_vector = obj.vector["semantic"]
                        target_vector_name = "semantic"
                    elif space == "AudioSpace" and isinstance(obj.vector, dict) and "transcript_semantic" in obj.vector:
                        target_vector = obj.vector["transcript_semantic"]
                        target_vector_name = "transcript_semantic"
                    elif isinstance(obj.vector, dict) and "default" in obj.vector:
                        target_vector = obj.vector["default"]
                        target_vector_name = "default"
                    elif isinstance(obj.vector, dict):
                        # Fallback to whatever is available, but this is dangerous for cross-space search
                        vec_key = list(obj.vector.keys())[0]
                        target_vector = obj.vector[vec_key]
                        target_vector_name = vec_key
                    else:
                        target_vector = obj.vector
                        target_vector_name = "default"
                    
                    if target_vector:
                        collection = coll
                        break
            except Exception:
                pass
                
    if not target_vector:
        raise HTTPException(status_code=400, detail="Cannot calculate vector similarity: Seed has no vector representation yet (must be an embedded DigitalAsset).")

    # Guardrail: Ensure we have a semantic text vector (1024 dimensions typically) for cross-space searches.
    # If it's an image without a "semantic" text vector, it likely only has its 1152-dim multimodal vector.
    if len(target_vector) != 1024:
        raise HTTPException(
            status_code=400, 
            detail=f"El archivo estÃ¡ incompleto (faltan los vectores textuales/semÃ¡nticos). Por favor usa el botÃ³n Re-Analizar en la vista previa del archivo padre para regenerar su metadata semÃ¡ntica. (EncontrÃ© un vector de {len(target_vector)} dimensiones, pero se necesitan 1024 para la bÃºsqueda transversal)."
        )

    # 3. Find top K vector neighbors globally across all spaces
    all_neighbors = []
    try:
        spaces_to_search = ["TextSpace", "VisualSpace", "AudioSpace", "MemorySpace"]
        for s in spaces_to_search:
            try:
                col = weaviate_client.collections.get(s)
                
                # Determine target_vector dynamically based on the space being searched
                target_vector_local = "default"
                if s == "VisualSpace": target_vector_local = "semantic" # BGE-M3 text equivalent
                elif s == "AudioSpace": target_vector_local = "transcript_semantic" # BGE-M3 text equivalent
                
                response = col.query.near_vector(
                    near_vector=target_vector,
                    limit=top_k + 1,  # +1 because the query will return the seed itself
                    return_properties=["neo4j_hash"],
                    target_vector=target_vector_local,
                    return_metadata=wq.MetadataQuery(distance=True)
                )
                
                for o in response.objects:
                    n_hash = o.properties.get("neo4j_hash")
                    if not n_hash or n_hash == seed_hash:
                        continue # skip self or invalid entries
                    
                    distance = o.metadata.distance if o.metadata.distance is not None else 1.0
                    sim = max(0.0, 1.0 - distance)
                    
                    all_neighbors.append({"file_hash": n_hash, "name": "Unknown", "sim": sim, "space": s})
                    
            except Exception as ex:
                logger.warning(f"Error querying space {s}: {ex}")
                pass
                
        # Sort globally by similarity descending and slice top_K
        all_neighbors = sorted(all_neighbors, key=lambda x: x["sim"], reverse=True)[:top_k]

    except Exception as e:
        logger.error(f"Error finding vector neighbors: {e}")
        raise HTTPException(status_code=500, detail="Weaviate query failed")

    if not all_neighbors:
        return {"seed_id": node_id, "seed_name": seed_name, "suggestions": []}

    # 4. Resolve neighbor hashes to Neo4j Element IDs + compute Bilateral Transfer
    suggestions = []
    try:
        with driver.session() as session:
            for neighbor in all_neighbors:
                n_hash = neighbor["file_hash"]
                n_sim = neighbor["sim"]
                space = neighbor["space"]
                
                # Fetch Neo4j node for neighbor (Force it to be a DigitalAsset)
                q_neighbor = "MATCH (n:DigitalAsset) WHERE n.file_hash = $hash RETURN elementId(n) as id, coalesce(n.name, n.filename) as name"
                r_neigh = session.run(q_neighbor, hash=n_hash).single()
                
                if not r_neigh:
                    continue
                    
                neigh_id = r_neigh["id"]
                neigh_name = r_neigh["name"]
                
                # We propose transferring ontology concepts symmetrically between the two Assets
                # NEVER Asset -> Asset directly. Target is ALWAYS concept/person/etc.
                
                # Direction 1: Seed -> Neighbor (Neighbor adopts Seed's concepts)
                q_seed_to_neighbor = """
                MATCH (seed:DigitalAsset)-[r]->(concept)
                WHERE elementId(seed) = $seed_id 
                  AND (concept:Concept OR concept:Event OR concept:Organization OR concept:Person OR concept:Location OR concept:Project)
                  AND NOT (concept)<-[:CREATED_BY|PARTICIPATED_IN|LOCATED_AT|CONTAINS]-()
                
                // Check that neighbor DOES NOT already have this concept
                OPTIONAL MATCH (neighbor:DigitalAsset)-[existing_r]->(concept)
                WHERE elementId(neighbor) = $neigh_id
                
                WITH concept, r, existing_r
                WHERE existing_r IS NULL

                // Count hub degree for penalty calculation
                CALL {
                    WITH concept
                    RETURN count { (concept)<--(:DigitalAsset) } AS concept_degree
                }
                
                RETURN elementId(concept) as concept_id, coalesce(concept.name, concept.title) as concept_name,
                       type(r) as relation_type, coalesce(toFloat(r.weight), 1.0) as current_weight,
                       concept_degree
                """
                
                seed_to_neigh_results = session.run(q_seed_to_neighbor, seed_id=node_id, neigh_id=neigh_id)
                for record in seed_to_neigh_results:
                    c_id = record["concept_id"]
                    c_name = record["concept_name"]
                    r_type = record["relation_type"]
                    c_weight = record["current_weight"]
                    c_degree = record.get("concept_degree", 0)
                    hub_penalty = math.exp(-0.015 * float(c_degree))
                    
                    beta = 1.0 - alpha
                    prop_weight = round((c_weight * beta) + (n_sim * alpha), 3)
                    prop_weight = round(prop_weight * hub_penalty, 4)  # apply hub penalty
                    
                    if prop_weight >= 0.5:
                        sugg = LatentConnectionSuggestion(
                            asset_id=neigh_id,
                            asset_name=neigh_name,
                            target_concept_id=c_id,
                            target_concept_name=c_name,
                            relation_type=r_type,
                            current_weight=c_weight,
                            cosine_similarity=round(n_sim, 3),
                            proposed_weight=max(min(prop_weight, 1.0), 0.0),
                            direction="seed_to_neighbor",
                            reasoning=f"Similarity: {round(n_sim*100)}% ({space}). Hub degree: {c_degree} (penalty: {round(hub_penalty,2)}x). Transfer: [{seed_name}] -> [{neigh_name}]."
                        )
                        suggestions.append(sugg)

                # Direction 2: Neighbor -> Seed (Seed adopts Neighbor's concepts)
                q_neighbor_to_seed = """
                MATCH (neighbor:DigitalAsset)-[r]->(concept)
                WHERE elementId(neighbor) = $neigh_id 
                  AND (concept:Concept OR concept:Event OR concept:Organization OR concept:Person OR concept:Location OR concept:Project)
                  AND NOT (concept)<-[:CREATED_BY|PARTICIPATED_IN|LOCATED_AT|CONTAINS]-()
                
                // Check that seed DOES NOT already have this concept
                OPTIONAL MATCH (seed:DigitalAsset)-[existing_r]->(concept)
                WHERE elementId(seed) = $seed_id
                
                WITH concept, r, existing_r
                WHERE existing_r IS NULL

                // Count hub degree for penalty calculation
                CALL {
                    WITH concept
                    RETURN count { (concept)<--(:DigitalAsset) } AS concept_degree
                }
                
                RETURN elementId(concept) as concept_id, coalesce(concept.name, concept.title) as concept_name,
                       type(r) as relation_type, coalesce(toFloat(r.weight), 1.0) as current_weight,
                       concept_degree
                """

                neigh_to_seed_results = session.run(q_neighbor_to_seed, seed_id=node_id, neigh_id=neigh_id)
                for record in neigh_to_seed_results:
                    c_id = record["concept_id"]
                    c_name = record["concept_name"]
                    r_type = record["relation_type"]
                    c_weight = record["current_weight"]
                    c_degree = record.get("concept_degree", 0)
                    hub_penalty = math.exp(-0.015 * float(c_degree))
                    
                    beta = 1.0 - alpha
                    prop_weight = round((c_weight * beta) + (n_sim * alpha), 3)
                    prop_weight = round(prop_weight * hub_penalty, 4)  # apply hub penalty
                    
                    if prop_weight >= 0.5:
                        sugg = LatentConnectionSuggestion(
                            asset_id=node_id,
                            asset_name=seed_name,
                            target_concept_id=c_id,
                            target_concept_name=c_name,
                            relation_type=r_type,
                            current_weight=c_weight,
                            cosine_similarity=round(n_sim, 3),
                            proposed_weight=max(min(prop_weight, 1.0), 0.0),
                            direction="neighbor_to_seed",
                            reasoning=f"Similarity: {round(n_sim*100)}% ({space}). Hub degree: {c_degree} (penalty: {round(hub_penalty,2)}x). Transfer: [{neigh_name}] -> [{seed_name}]."
                        )
                        suggestions.append(sugg)

    except Exception as e:
        logger.error(f"Error mapping latent suggestions in graph: {e}")
        raise HTTPException(status_code=500, detail="Error computing latent graph bridges")

    return {"seed_id": node_id, "seed_name": seed_name, "suggestions": suggestions}

@router.post("/approve-connection")
def approve_latent_connection(req: ApproveConnectionRequest):
    """
    Creates a new relationship in Neo4j based on an approved latent suggestion.
    """
    driver = get_neo4j_driver()
    
    query = f"""
    MATCH (s:DigitalAsset) WHERE elementId(s) = $asset_id
    MATCH (c) WHERE elementId(c) = $concept_id
    MERGE (s)-[r:`{req.relation_type}`]->(c)
    ON CREATE SET 
        r.weight = $weight,
        r.reasoning = $reasoning,
        r.source = 'interactive_latent_explorer',
        r.created_at = datetime()
    ON MATCH SET 
        r.weight = $weight,
        r.reasoning = $reasoning,
        r.updated_at = datetime()
    RETURN id(r) as rel_id
    """
    
    try:
        with driver.session() as session:
            result = session.run(query, 
                asset_id=req.asset_id, 
                concept_id=req.target_concept_id, 
                weight=req.proposed_weight,
                reasoning=req.reasoning
            ).single()
            
            if not result:
                raise HTTPException(status_code=400, detail="Could not create relationship (Nodes might be missing)")
                
            return {"status": "success", "message": f"Connection {req.relation_type} established."}
            
    except Exception as e:
        logger.error(f"Failed to save approved connection: {e}")
        raise HTTPException(status_code=500, detail="Database write error")

@router.get("/asset-preview/{asset_id}", response_model=AssetPreviewResponse)
def get_asset_preview(asset_id: str):
    """
    Fetches basic metadata and content of a DigitalAsset for previewing in the Latent Explorer.
    """
    driver = get_neo4j_driver()
    
    query = """
    MATCH (n:DigitalAsset)
    WHERE elementId(n) = $asset_id
    RETURN elementId(n) as id, 
           coalesce(n.name, n.filename, n.title, 'Unknown Asset') as name, 
           labels(n)[0] as type, 
           coalesce(n.tags, []) as tags, 
           coalesce(n.text_content, n.transcript, coalesce(n.caption, n.visual_description), 'No textual content available') as content,
           coalesce(n.neo4j_hash, n.file_hash, n.hash, '') as file_hash,
           coalesce(n.mime_type, '') as mime_type
    """
    
    try:
        with driver.session() as session:
            result = session.run(query, asset_id=asset_id).single()
            if not result:
                raise HTTPException(status_code=404, detail="Asset not found")
                
            res_dict = {
                "id": result["id"],
                "name": result["name"],
                "type": result["type"],
                "tags": result["tags"],
                "content": result["content"][:800] + ("..." if len(result["content"]) > 800 else ""),
                "mime_type": result["mime_type"] if result["mime_type"] else None,
                "minio_path": None,
                "download_url": None
            }
            
            # Resolve MinIO URL if file_hash exists
            file_hash = str(result["file_hash"]).strip().strip('"').strip("'")
            if file_hash:
                import re
                import json
                try:
                    minio_client = get_minio_client()
                    bucket = settings.MINIO_BUCKET if hasattr(settings, 'MINIO_BUCKET') else "rag-dataset"
                    
                    found_path = None
                    CANDIDATE_PREFIXES = [
                        "raw/images/", "raw/audio/", "raw/videos/",
                        "raw/documents/", "master_records/texts/"
                    ]
                    
                    for prefix in CANDIDATE_PREFIXES:
                        search_prefix = f"{prefix}{file_hash}" if prefix == "master_records/texts/" else f"{prefix}{file_hash[:8]}"
                        response = minio_client.list_objects_v2(
                            Bucket=bucket,
                            Prefix=search_prefix,
                            MaxKeys=1
                        )
                        if "Contents" in response and len(response["Contents"]) > 0:
                            found_path = response["Contents"][0]["Key"]
                            break
                    
                    if found_path:
                        # Generate presigned URL
                        url = minio_client.generate_presigned_url(
                            'get_object',
                            Params={'Bucket': bucket, 'Key': found_path},
                            ExpiresIn=3600
                        )
                        new_url = re.sub(r'https?://[^/]+', 'http://localhost:9005', url)
                        res_dict["minio_path"] = found_path
                        res_dict["download_url"] = new_url
                        
                        # NEW: If it's a raw text file, download it and use it as content!
                        if (res_dict["content"] == 'No textual content available' or not res_dict["content"]) and (found_path.endswith('.txt') or found_path.endswith('.md')):
                            try:
                                text_obj = minio_client.get_object(Bucket=bucket, Key=found_path)
                                raw_text = text_obj['Body'].read().decode('utf-8', errors='replace')
                                res_dict["content"] = raw_text[:5000] + ("..." if len(raw_text) > 5000 else "")
                                logger.info(f"   ðŸ“„ Loaded raw text from MinIO: {len(raw_text)} chars")
                            except Exception as text_err:
                                logger.warning(f"Failed to read raw text for {found_path}: {text_err}")
                        
                    # 2. Text Content Injection (Fallback for Graph results)
                    if res_dict["content"] == 'No textual content available' or not res_dict["content"]:
                        sidecar_path = f"master_records/sidecars/{file_hash}.json"
                        sidecar_response = minio_client.get_object(Bucket=bucket, Key=sidecar_path)
                        sidecar_data = json.loads(sidecar_response['Body'].read().decode('utf-8'))
                        
                        fallback_text = sidecar_data.get("text")
                        if not fallback_text:
                            data_layers = sidecar_data.get('data_layers', {})
                            fallback_text = (
                                data_layers.get('intermediate_results', {}).get('audio_transcript') or
                                data_layers.get('intermediate_results', {}).get('ocr_text') or
                                sidecar_data.get('user_notes')
                            )
                            
                        if fallback_text:
                            res_dict["content"] = fallback_text[:3000] + ("..." if len(fallback_text) > 3000 else "")
                            
                except Exception as minio_err:
                    logger.warning(f"Failed to resolve MinIO link or sidecar for {file_hash}: {minio_err}")

            return AssetPreviewResponse(**res_dict)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch asset preview: {e}")
        raise HTTPException(status_code=500, detail="Database read error")
