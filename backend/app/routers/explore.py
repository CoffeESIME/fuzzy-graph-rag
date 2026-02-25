from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
import logging
import math
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

@router.get("/seeds", response_model=SeedResponse)
def get_explorable_seeds(
    node_type: str = Query("Person", description="Node type to search for seeds"),
    limit: int = Query(50, ge=1, le=200)
):
    """
    Returns eligible nodes to be used as 'seeds' for latent exploration.
    Eligible nodes: DigitalAssets or enriched Concept/Person/etc.
    Sorted by connectivity.
    """
    driver = get_neo4j_driver()
    
    allowed_types = ["Person", "Concept", "Location", "Organization", "Event", "Project", "Device", "Method", "DigitalAsset"]
    if node_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"Invalid node type. Allowed types: {', '.join(allowed_types)}")

    # DigitalAsset is implicitly eligible, others need enriched = true
    # V2: We strictly limit to DigitalAsset to avoid cyclic Asset->Asset relationships implicitly
    query = f"""
    MATCH (n:DigitalAsset)
    OPTIONAL MATCH (n)--()
    WITH n, count(*) as connections
    RETURN elementId(n) as id, coalesce(n.name, n.title, n.filename, 'Unknown') as name, labels(n)[0] as type, connections
    ORDER BY connections DESC
    LIMIT $limit
    """
    
    try:
        with driver.session() as session:
            result = session.run(query, limit=limit)
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
                   type(r) as relation_type, coalesce(r.weight, 1.0) as current_weight
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
            detail=f"El archivo está incompleto (faltan los vectores textuales/semánticos). Por favor usa el botón Re-Analizar en la vista previa del archivo padre para regenerar su metadata semántica. (Encontré un vector de {len(target_vector)} dimensiones, pero se necesitan 1024 para la búsqueda transversal)."
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
                
                RETURN elementId(concept) as concept_id, coalesce(concept.name, concept.title) as concept_name,
                       type(r) as relation_type, coalesce(r.weight, 1.0) as current_weight
                """
                
                seed_to_neigh_results = session.run(q_seed_to_neighbor, seed_id=node_id, neigh_id=neigh_id)
                for record in seed_to_neigh_results:
                    c_id = record["concept_id"]
                    c_name = record["concept_name"]
                    r_type = record["relation_type"]
                    c_weight = record["current_weight"]
                    
                    beta = 1.0 - alpha
                    prop_weight = round((c_weight * beta) + (n_sim * alpha), 3)
                    
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
                            reasoning=f"Similarity: {round(n_sim*100)}% in Weaviate ({space}). Semantic Transfer: [{seed_name}] -> [{neigh_name}]."
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
                
                RETURN elementId(concept) as concept_id, coalesce(concept.name, concept.title) as concept_name,
                       type(r) as relation_type, coalesce(r.weight, 1.0) as current_weight
                """

                neigh_to_seed_results = session.run(q_neighbor_to_seed, seed_id=node_id, neigh_id=neigh_id)
                for record in neigh_to_seed_results:
                    c_id = record["concept_id"]
                    c_name = record["concept_name"]
                    r_type = record["relation_type"]
                    c_weight = record["current_weight"]
                    
                    beta = 1.0 - alpha
                    prop_weight = round((c_weight * beta) + (n_sim * alpha), 3)
                    
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
                            reasoning=f"Similarity: {round(n_sim*100)}% in Weaviate ({space}). Semantic Transfer: [{neigh_name}] -> [{seed_name}]."
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
                        
                    # 2. Text Content Injection (Fallback for Graph results)
                    if res_dict["content"] == 'No textual content available' or not res_dict["content"]:
                        sidecar_path = f"master_records/sidecars/{file_hash}.json"
                        sidecar_response = minio_client.get_object(Bucket=bucket, Key=sidecar_path)
                        sidecar_data = json.loads(sidecar_response['Body'].read().decode('utf-8'))
                        
                        fallback_text = sidecar_data.get("text")
                        if not fallback_text:
                            data_layers = sidecar_data.get('data_layers', {})
                            fallback_text = data_layers.get('intermediate_results', {}).get('audio_transcript')
                            
                        if fallback_text:
                            res_dict["content"] = fallback_text[:800] + ("..." if len(fallback_text) > 800 else "")
                            
                except Exception as minio_err:
                    logger.warning(f"Failed to resolve MinIO link or sidecar for {file_hash}: {minio_err}")

            return AssetPreviewResponse(**res_dict)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch asset preview: {e}")
        raise HTTPException(status_code=500, detail="Database read error")
