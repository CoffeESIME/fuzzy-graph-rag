# Copyright (C) 2026 Fabian Romero Hernandez
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License v3.0.
#
# This project is part of an independent academic research on Fuzzy Logic-based
# Multimodal Graph RAG systems (hechoconcafeina).
# Full license: https://www.gnu.org/licenses/agpl-3.0

from fastapi import APIRouter
from shared.clients import get_neo4j_driver, get_minio_client
from config.settings import get_settings
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import re
import logging
import json
import requests

logger = logging.getLogger(__name__)
settings = get_settings()

LLM_GATEWAY_URL = settings.LLM_GATEWAY_URL

router = APIRouter(
    prefix="/analysis",
    tags=["analysis"]
)

class AnalysisToolResponse(BaseModel):
    tool: str
    status: str
    message: str
    mock_data: Dict[str, Any]

def _safe_gds_project(session, graph_name: str, project_query: str, **kwargs):
    """Project a GDS graph, dropping any stale version first. Retry-safe."""
    # Try dropping first (might not exist, that's fine)
    try:
        session.run(f"CALL gds.graph.drop('{graph_name}')").consume()
    except Exception:
        pass
    # Now project â€” if STILL fails (race condition), drop hard and retry
    try:
        session.run(project_query, **kwargs).consume()
    except Exception as e:
        if 'already loaded' in str(e).lower():
            # Nuclear option: list and drop, then retry
            try:
                session.run(f"CALL gds.graph.drop('{graph_name}')").consume()
            except Exception:
                pass
            session.run(project_query, **kwargs).consume()
        else:
            raise

def _safe_gds_drop(session, graph_name: str):
    """Safely drop a GDS graph, ignoring if not found."""
    try:
        session.run(f"CALL gds.graph.drop('{graph_name}')").consume()
    except Exception:
        pass

# ðŸ§¬ Community Detection (Louvain via Cypher Projection)
@router.post("/communities", response_model=AnalysisToolResponse)
def analyze_communities(method: str = "standard", min_weight: float = 0.9):
    """
    Detecta comunidades usando GDS Louvain con soporte Dual (Standard y Fuzzy).
    Standard: aristas = conteo de archivos compartidos, nodos = count(archivos).
    Fuzzy: aristas = sum(min(w1,w2)), nodos = sum(pesos relaciones).
    Aplica el filtro MIN_WEIGHT.
    """
    driver = get_neo4j_driver()

    # --- ProyecciÃ³n segÃºn mÃ©todo ---
    if method == "fuzzy":
        query_project = """
        MATCH (c1:Concept)<-[r1]-(a:DigitalAsset)-[r2]->(c2:Concept)
        WHERE id(c1) < id(c2) 
          AND coalesce(r1.weight, 1.0) >= $min_weight 
          AND coalesce(r2.weight, 1.0) >= $min_weight
        WITH c1, c2, sum(CASE WHEN r1.weight < r2.weight THEN r1.weight ELSE r2.weight END) AS weight
        WITH gds.graph.project(
          'conceptCommunities',
          c1, c2,
          { relationshipProperties: { weight: weight } },
          { undirectedRelationshipTypes: ['*'] }
        ) AS g
        RETURN g.graphName AS graphName, g.nodeCount AS nodeCount, g.relationshipCount AS relationshipCount
        """
        node_size_clause = "MATCH (n)<-[r]-(:DigitalAsset) WHERE coalesce(r.weight, 1.0) >= $min_weight WITH n, communityId, round(sum(r.weight), 2) AS degree"
    else:
        query_project = """
        MATCH (c1:Concept)<-[r1]-(a:DigitalAsset)-[r2]->(c2:Concept)
        WHERE id(c1) < id(c2)
          AND coalesce(r1.weight, 1.0) >= $min_weight 
          AND coalesce(r2.weight, 1.0) >= $min_weight
        WITH c1, c2, count(a) AS weight
        WITH gds.graph.project(
          'conceptCommunities',
          c1, c2,
          { relationshipProperties: { weight: weight } },
          { undirectedRelationshipTypes: ['*'] }
        ) AS g
        RETURN g.graphName AS graphName, g.nodeCount AS nodeCount, g.relationshipCount AS relationshipCount
        """
        node_size_clause = "MATCH (n)<-[r]-(a:DigitalAsset) WHERE coalesce(r.weight, 1.0) >= $min_weight WITH n, communityId, count(distinct a) AS degree"

    # --- Louvain + enriquecer con tamaÃ±o real ---
    query_louvain = f"""
    CALL gds.louvain.stream('conceptCommunities', {{ relationshipWeightProperty: 'weight' }})
    YIELD nodeId, communityId
    WITH gds.util.asNode(nodeId) AS n, communityId

    {node_size_clause}
    ORDER BY degree DESC

    WITH communityId, collect({{name: n.name, degree: degree}}) AS members, count(n) AS size
    WHERE size > 1
    RETURN communityId, members[0..25] AS top_members, size
    ORDER BY size DESC
    LIMIT 12
    """

    try:
        with driver.session() as session:
            _safe_gds_project(session, 'conceptCommunities', query_project, min_weight=min_weight)
            result = session.run(query_louvain, min_weight=min_weight)
            records = list(result)
            _safe_gds_drop(session, 'conceptCommunities')

            # --- Formateo para Nivo Circle Packing ---
            communities_data = []
            for idx, r in enumerate(records):
                comm_name = f"Tema: {r['top_members'][0]['name']}" if r['top_members'] else f"ClÃºster {idx + 1}"

                children_nodes = [
                    {
                        "name": member["name"],
                        "loc": member["degree"],
                        "degree": member["degree"],
                    }
                    for member in r["top_members"]
                ]

                communities_data.append({
                    "name": comm_name,
                    "children": children_nodes,
                    "color": f"hsl({(idx * 50) % 360}, 70%, 50%)",
                    "total_size": r["size"],
                })

            nivo_data = {
                "name": "Knowledge Graph",
                "children": communities_data
            }

            mode_name = "Fuzzy Louvain" if method == "fuzzy" else "Standard Louvain"
            return {
                "tool": "communities",
                "status": "success",
                "message": f"{mode_name} detectÃ³ {len(communities_data)} comunidades.",
                "mock_data": {
                    "packing_data": nivo_data,
                    "method": method,
                },
            }

    except Exception as e:
        print(f"ðŸ”¥ Error Communities: {e}")
        return {
            "tool": "communities",
            "status": "error",
            "message": f"GDS Error: {str(e)}",
            "mock_data": {"packing_data": {}}
        }

# ðŸŒ‰ Semantic Bridges (Bowtie Heuristic â€” no GDS needed)
@router.post("/bridges", response_model=AnalysisToolResponse)
def analyze_bridges(method: str = "standard", min_weight: float = 0.9):
    """
    Puentes SemÃ¡nticos Dual: Standard (conteo) vs Fuzzy (pesos difusos).
    bridge_score = diversity Ã— degree (standard) o diversity Ã— fuzzy_weight (fuzzy).
    Aplica el filtro MIN_WEIGHT.
    """
    driver = get_neo4j_driver()

    if method == "fuzzy":
        cypher_query = """
        MATCH (bridge:Concept)<-[r1]-(a:DigitalAsset)-[r2]->(other)
        WHERE elementId(bridge) <> elementId(other)
          AND coalesce(r1.weight, 1.0) >= $min_weight 
          AND coalesce(r2.weight, 1.0) >= $min_weight
        WITH bridge, other,
             CASE WHEN coalesce(r1.weight, 1.0) < coalesce(r2.weight, 1.0) THEN coalesce(r1.weight, 1.0) ELSE coalesce(r2.weight, 1.0) END AS fuzzy_w
        WITH bridge, sum(fuzzy_w) AS fuzzy_degree,
             count(distinct labels(other)) AS diversity
        WITH bridge, round(fuzzy_degree * diversity, 2) AS score
        ORDER BY score DESC LIMIT 10

        MATCH (bridge)<-[r1]-(:DigitalAsset)-[r2]->(o)
        WHERE elementId(bridge) <> elementId(o)
          AND coalesce(r1.weight, 1.0) >= $min_weight 
          AND coalesce(r2.weight, 1.0) >= $min_weight
        RETURN bridge.name AS id, score,
               collect(distinct o.name)[0..6] AS context
        ORDER BY score DESC
        """
    else:
        cypher_query = """
        MATCH (bridge:Concept)<-[r1]-(a:DigitalAsset)-[r2]->(other)
        WHERE elementId(bridge) <> elementId(other)
          AND coalesce(r1.weight, 1.0) >= $min_weight 
          AND coalesce(r2.weight, 1.0) >= $min_weight
        WITH bridge, count(distinct other) AS degree,
             count(distinct labels(other)) AS diversity
        WITH bridge, round(toFloat(degree * diversity), 2) AS score
        ORDER BY score DESC LIMIT 10

        MATCH (bridge)<-[r1]-(:DigitalAsset)-[r2]->(o)
        WHERE elementId(bridge) <> elementId(o)
          AND coalesce(r1.weight, 1.0) >= $min_weight 
          AND coalesce(r2.weight, 1.0) >= $min_weight
        RETURN bridge.name AS id, score,
               collect(distinct o.name)[0..6] AS context
        ORDER BY score DESC
        """

    try:
        with driver.session() as session:
            result = session.run(cypher_query, min_weight=min_weight)
            bridges = [
                {"id": r["id"], "score": r["score"], "context": r["context"]}
                for r in result
            ]

            mode_name = "Fuzzy Bridges" if method == "fuzzy" else "Standard Bridges"
            return {
                "tool": "bridges",
                "status": "success",
                "message": f"{mode_name}: top {len(bridges)} puentes detectados.",
                "mock_data": {
                    "bridges": bridges,
                    "method": method,
                },
            }
    except Exception as e:
        print(f"ðŸ”¥ Error Bridges ({method}): {e}")
        return {
            "tool": "bridges",
            "status": "error",
            "message": str(e),
            "mock_data": {"bridges": [], "method": method},
        }

# â”€â”€ MinIO helpers â”€â”€
CANDIDATE_PREFIXES = [
    "raw/images/", "raw/audio/", "raw/videos/",
    "raw/documents/", "master_records/texts/"
]

def _resolve_minio_url(file_hash: Optional[str], mime_type: Optional[str] = None) -> dict:
    """
    Given a file_hash, search MinIO for the actual object and return
    {download_url, minio_path} or empty dict.
    """
    if not file_hash:
        return {}
    try:
        minio_client = get_minio_client()
        bucket = settings.MINIO_BUCKET

        # Optimize prefix order by mime
        prefixes = list(CANDIDATE_PREFIXES)
        if mime_type:
            if mime_type.startswith("image"):
                prefixes = ["raw/images/"] + [p for p in CANDIDATE_PREFIXES if p != "raw/images/"]
            elif mime_type.startswith("audio"):
                prefixes = ["raw/audio/"] + [p for p in CANDIDATE_PREFIXES if p != "raw/audio/"]
            elif mime_type.startswith("video"):
                prefixes = ["raw/videos/"] + [p for p in CANDIDATE_PREFIXES if p != "raw/videos/"]
            elif mime_type.startswith("text") or "pdf" in (mime_type or ""):
                prefixes = ["master_records/texts/", "raw/documents/"] + [
                    p for p in CANDIDATE_PREFIXES if p not in ("master_records/texts/", "raw/documents/")
                ]

        found_path = None
        for prefix in prefixes:
            search_prefix = f"{prefix}{file_hash}" if prefix == "master_records/texts/" else f"{prefix}{file_hash[:8]}"
            try:
                response = minio_client.list_objects_v2(
                    Bucket=bucket, Prefix=search_prefix, MaxKeys=1
                )
                if "Contents" in response:
                    found_path = response["Contents"][0]["Key"]
                    break
            except Exception:
                pass

        if found_path:
            url = minio_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": found_path},
                ExpiresIn=3600,
            )
            download_url = re.sub(r"https?://[^/]+", "http://localhost:9005", url)
            return {"download_url": download_url, "minio_path": found_path}
    except Exception as e:
        logger.warning(f"MinIO resolve failed for {file_hash}: {e}")
    return {}


# ðŸ§­ Pathfinder (Navegador Latente)
class PathfinderRequest(BaseModel):
    source_element_id: str
    target_element_id: str
    mode: str = "direct"  # "direct" | "lateral"
    threshold: float = 0.85

class PathfinderNodeData(BaseModel):
    id: str
    label: str
    node_type: str  # "Concept", "DigitalAsset", "Person", etc.
    weight_to_next: Optional[float] = None
    file_hash: Optional[str] = None
    mime_type: Optional[str] = None
    download_url: Optional[str] = None
    minio_path: Optional[str] = None

class PathfinderEdgeData(BaseModel):
    source: str
    target: str
    weight: Optional[float]
    rel_type: str

class PathfinderResponse(BaseModel):
    status: str
    message: str
    nodes: List[PathfinderNodeData]
    edges: List[PathfinderEdgeData]
    path_length: int
    mode: str

@router.post("/pathfinder", response_model=PathfinderResponse)
def pathfind(request: PathfinderRequest):
    """
    K-Shortest Paths entre dos nodos (hasta 3 rutas distintas).
    mode='direct'  â†’ minimiza 1 - weight (prefiere aristas fuertes).
    mode='lateral' â†’ aplica penalizaciÃ³n extra a aristas con weight > 0.85,
                     forzando rutas creativas/serendÃ­picas.
    """
    driver = get_neo4j_driver()

    if request.mode == "lateral":
        cypher = """
        MATCH (src), (tgt)
        WHERE elementId(src) = $source AND elementId(tgt) = $target
        MATCH p = (src)-[*1..8]-(tgt)
        WITH p,
             // Costo de aristas: penaliza aristas fuertes (> umbral) para forzar rutas creativas
             REDUCE(cost = 0.0, r IN relationships(p) |
               cost + (1.0 - coalesce(r.weight, 0.5))
                    + CASE WHEN coalesce(r.weight, 0.5) > $threshold THEN 2.0 ELSE 0.0 END
             ) AS edgeCost,
             // Costo de nodos: penaliza Conceptos hub (muchas conexiones)
             // size([(n)<--(:DigitalAsset)|1]) cuenta el grado sin CALL{}
             // Formula: 1 - exp(-0.015 * degree) â†’ 0.0 para nichos, ~0.99 para mega-hubs
             REDUCE(hubCost = 0.0, n IN [x IN nodes(p) WHERE x:Concept] |
               hubCost + (1.0 - exp(-0.015 * toFloat(size([(n)<--(:DigitalAsset) | 1]))))
             ) AS hubCost
        WITH p, edgeCost + hubCost AS totalCost
        ORDER BY totalCost ASC
        LIMIT 3
        RETURN nodes(p) AS path_nodes, relationships(p) AS path_rels, totalCost
        """
    else:
        cypher = """
        MATCH (src), (tgt)
        WHERE elementId(src) = $source AND elementId(tgt) = $target
        MATCH p = (src)-[*1..8]-(tgt)
        WITH p,
             REDUCE(cost = 0.0, r IN relationships(p) |
               cost + (1.0 - coalesce(r.weight, 0.5))
             ) AS totalCost
        ORDER BY totalCost ASC
        LIMIT 3
        RETURN nodes(p) AS path_nodes, relationships(p) AS path_rels, totalCost
        """

    # 5-minute transaction timeout so Neo4j does not kill long variable-path queries.
    # Neo4j Python driver v5: timeout is set via begin_transaction(timeout=N) in seconds.
    _PATHFINDER_TIMEOUT_S = 300  # 5 minutes

    try:
        with driver.session() as session:
            with session.begin_transaction(timeout=_PATHFINDER_TIMEOUT_S) as tx:
                result = tx.run(
                    cypher,
                    source=request.source_element_id,
                    target=request.target_element_id,
                    threshold=request.threshold,
                )
                records = list(result)

            if not records:
                return PathfinderResponse(
                    status="not_found",
                    message=f"No path found in '{request.mode}' mode. Try 'direct' mode or select closer nodes.",
                    nodes=[], edges=[], path_length=0, mode=request.mode
                )

            # â”€â”€ Deduplicate across all K paths â”€â”€
            seen_nodes: dict = {}     # elementId str â†’ PathfinderNodeData
            seen_edge_keys: set = set()
            out_edges: List[PathfinderEdgeData] = []
            total_hops = 0

            for record in records:
                path_nodes = record["path_nodes"]
                path_rels = record["path_rels"]
                total_hops = max(total_hops, len(path_rels))

                # Build a local id map for this path so edges match exactly
                local_id_map: dict = {}  # neo4j internal id â†’ our string elementId key

                for n in path_nodes:
                    nid = str(n.element_id)
                    local_id_map[n.element_id] = nid

                    if nid not in seen_nodes:
                        node_labels = list(n.labels)
                        node_type = "Concept"
                        for lbl in node_labels:
                            if lbl in ["DigitalAsset", "Person", "Location", "Organization", "Event", "Project"]:
                                node_type = lbl
                                break

                        file_hash = n.get("file_hash") or n.get("neo4j_hash") or n.get("hash")
                        mime_type = n.get("mime_type")
                        minio_data = {}
                        if node_type == "DigitalAsset" and file_hash:
                            minio_data = _resolve_minio_url(file_hash, mime_type)

                        seen_nodes[nid] = PathfinderNodeData(
                            id=nid,
                            label=n.get("name") or n.get("filename") or n.get("title") or "?",
                            node_type=node_type,
                            file_hash=file_hash,
                            mime_type=mime_type,
                            **minio_data
                        )

                for rel in path_rels:
                    src_id = str(rel.start_node.element_id)
                    tgt_id = str(rel.end_node.element_id)
                    edge_key = (src_id, tgt_id, rel.type)
                    if edge_key not in seen_edge_keys:
                        seen_edge_keys.add(edge_key)
                        w = rel.get("weight")
                        out_edges.append(PathfinderEdgeData(
                            source=src_id,
                            target=tgt_id,
                            weight=round(w, 3) if w is not None else None,
                            rel_type=rel.type
                        ))

            out_nodes = list(seen_nodes.values())
            num_paths = len(records)

            return PathfinderResponse(
                status="success",
                message=f"{num_paths} camino(s) encontrado(s): {len(out_nodes)} nodos Ãºnicos, {len(out_edges)} aristas Ãºnicas.",
                nodes=out_nodes,
                edges=out_edges,
                path_length=total_hops,
                mode=request.mode
            )

    except Exception as e:
        logger.error(f"ðŸ”¥ Pathfinder error: {e}")
        return PathfinderResponse(
            status="error",
            message=str(e),
            nodes=[], edges=[], path_length=0, mode=request.mode
        )


# ðŸŽ² Serendipity Path (Fuzzy Random Walk)
@router.post("/serendipity", response_model=AnalysisToolResponse)
def analyze_serendipity():
    """
    Genera un camino asociativo (Serendipia) saltando entre Conceptos y Assets.
    Favorece caminos que incluyen al menos una conexiÃ³n 'difusa' (weight < 0.9).
    """
    driver = get_neo4j_driver()

    cypher_query = """
    // 1. Elegir un nodo de inicio aleatorio con al menos una conexiÃ³n no obvia
    MATCH (start:Concept)<-[r]-(:DigitalAsset)
    WHERE coalesce(r.weight, 1.0) < 0.9
    WITH start ORDER BY rand() LIMIT 1

    // 2. Trazar el camino de 5 nodos: Concept -> Asset -> Concept -> Asset -> Concept
    MATCH path = (start)<-[r1]-(a1:DigitalAsset)-[r2]->(mid:Concept)<-[r3]-(a2:DigitalAsset)-[r4]->(end:Concept)

    // 3. Evitar bucles estructurales
    WHERE elementId(start) <> elementId(mid)
      AND elementId(start) <> elementId(end)
      AND elementId(mid)   <> elementId(end)
      AND elementId(a1)    <> elementId(a2)
      // Factor Serendipia: al menos una arista dÃ©bil/latente
      AND (coalesce(r1.weight, 1.0) <= 0.7 OR coalesce(r2.weight, 1.0) <= 0.7
        OR coalesce(r3.weight, 1.0) <= 0.7 OR coalesce(r4.weight, 1.0) <= 0.7)

    // 4. Calcular el grado del nodo puente (hub) â€” penaliza mega-hubs
    CALL {
        WITH mid
        RETURN count { (mid)<--(:DigitalAsset) } AS mid_degree
    }

    // 5. Random Walk Penalizado: rand() Ã— exp(-0.015 Ã— mid_degree)
    //    Hub de 200 conexiones â†’ penaltyâ‰ˆ0.05, incluso rand=0.99 da 0.049
    //    Concepto nicho de 3 conexiones â†’ penaltyâ‰ˆ0.96, fÃ¡cilmente gana
    WITH path, start, a1, mid, a2, end, r1, r2, r3, r4, mid_degree,
         rand() * exp(-0.015 * toFloat(mid_degree)) AS serendipity_score
    ORDER BY serendipity_score DESC
    LIMIT 1

    // 6. Retornar cada nodo/arista con nombre explÃ­cito (compatible con parser Python)
    RETURN
        elementId(start)            AS step1_id,
        start.name                  AS step1_node,
        'Concept'                   AS step1_type,
        coalesce(r1.weight, 1.0)   AS edge1_weight,
        elementId(a1)               AS step2_id,
        coalesce(a1.name, a1.filename) AS step2_node,
        'Asset'                     AS step2_type,
        a1.file_hash                AS a1_hash,
        a1.mime_type                AS a1_mime,
        coalesce(r2.weight, 1.0)   AS edge2_weight,
        elementId(mid)              AS step3_id,
        mid.name                    AS step3_node,
        'Concept'                   AS step3_type,
        mid_degree                  AS mid_hub_degree,
        coalesce(r3.weight, 1.0)   AS edge3_weight,
        elementId(a2)               AS step4_id,
        coalesce(a2.name, a2.filename) AS step4_node,
        'Asset'                     AS step4_type,
        a2.file_hash                AS a2_hash,
        a2.mime_type                AS a2_mime,
        coalesce(r4.weight, 1.0)   AS edge4_weight,
        elementId(end)              AS step5_id,
        end.name                    AS step5_node,
        'Concept'                   AS step5_type
    """

    try:
        with driver.session() as session:
            result = session.run(cypher_query)
            record = result.single()

            if not record:
                return {
                    "tool": "serendipity",
                    "status": "success",
                    "message": "No fuzzy path found. Try again or add more data.",
                    "mock_data": {"path": []}
                }

            def _rw(val):
                return round(val, 2) if val is not None else None

            # Resolve MinIO presigned URLs for each asset
            a1_minio = _resolve_minio_url(record.get("a1_hash"), record.get("a1_mime"))
            a2_minio = _resolve_minio_url(record.get("a2_hash"), record.get("a2_mime"))

            path_sequence = [
                {"id": record["step1_id"], "name": record["step1_node"], "type": record["step1_type"], "weight": None},
                {
                    "id": record["step2_id"],
                    "name": record["step2_node"], "type": record["step2_type"],
                    "weight": _rw(record["edge1_weight"]),
                    "file_hash": record.get("a1_hash"),
                    "mime_type": record.get("a1_mime"),
                    **a1_minio,
                },
                {"id": record["step3_id"], "name": record["step3_node"], "type": record["step3_type"], "weight": _rw(record["edge2_weight"]), "hub_degree": record.get("mid_hub_degree")},
                {
                    "id": record["step4_id"],
                    "name": record["step4_node"], "type": record["step4_type"],
                    "weight": _rw(record["edge3_weight"]),
                    "file_hash": record.get("a2_hash"),
                    "mime_type": record.get("a2_mime"),
                    **a2_minio,
                },
                {"id": record["step5_id"], "name": record["step5_node"], "type": record["step5_type"], "weight": _rw(record["edge4_weight"])},
            ]

            return {
                "tool": "serendipity",
                "status": "success",
                "message": f"Conectado '{record['step1_node']}' con '{record['step5_node']}'",
                "mock_data": {"path": path_sequence}
            }
    except Exception as e:
        print(f"ðŸ”¥ Error Serendipity: {e}")
        return {
            "tool": "serendipity",
            "status": "error",
            "message": str(e),
            "mock_data": {"path": []}
        }


# ðŸ§  Explainer (LLM Path Narrative)
class PathExplanationRequest(BaseModel):
    tool_name: str  # 'serendipity' or 'pathfinder'
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    privacy_mode: bool = False

class PathExplanationResponse(BaseModel):
    explanation: str
    status: str

@router.post("/explain-path", response_model=PathExplanationResponse)
def explain_analytical_path(req: PathExplanationRequest):
    """
    Takes a graph path (nodes + edges) and asks the LLM to write a narrative 
    explanation of how and why the start node connects to the end node.
    """
    if not req.nodes or not req.edges:
        return PathExplanationResponse(status="error", explanation="El camino estÃ¡ vacÃ­o.")

    try:
        # 1. Reconstruct path as a readable string
        path_str_parts = []
        node_map = {n.get("id"): n for n in req.nodes}
        
        # Sort edges assuming they are mostly sequential, but handle flexibly
        for edge in req.edges:
            src = node_map.get(edge.get("source"), {})
            tgt = node_map.get(edge.get("target"), {})
            
            src_name = src.get("name") or src.get("label") or "Unknown"
            tgt_name = tgt.get("name") or tgt.get("label") or "Unknown"
            src_type = src.get("type") or src.get("node_type") or "Node"
            tgt_type = tgt.get("type") or tgt.get("node_type") or "Node"
            
            rel = edge.get("rel_type") or edge.get("type") or "CONECTADO_A"
            weight = edge.get("weight")
            w_str = f" (peso: {weight})" if weight is not None else ""
            
            step = f"♦ Conexión: [{src_type}] '{src_name}' <---({rel}){w_str}---> [{tgt_type}] '{tgt_name}'"
            path_str_parts.append(step)

        path_context = "\n".join(path_str_parts)

        # 1.5 Fetch minio sidecars for contextual richness
        minio_contexts = []
        try:
            from shared.clients import get_minio_client
            minio_client = get_minio_client()
            bucket = settings.MINIO_BUCKET if hasattr(settings, 'MINIO_BUCKET') else "rag-dataset"
            
            for n in req.nodes:
                # Handle both 'Asset' (from serendipity UI mapper) and 'DigitalAsset' (from pathfinder)
                n_type = n.get("node_type") or n.get("type") or ""
                labels = n.get("labels", [])
                
                if n_type in ("DigitalAsset", "Asset") or "DigitalAsset" in labels:
                    props = n.get("properties", {})
                    f_hash = n.get("file_hash") or props.get("file_hash") or props.get("hash") or n.get("id")
                    
                    if f_hash and len(str(f_hash)) > 10: # Rough check for hex hash
                        # Prevent using neo4j element Ids as minio paths
                        if ":" in str(f_hash):
                            continue
                            
                        try:
                            sidecar_path = f"master_records/sidecars/{f_hash}.json"
                            response = minio_client.get_object(Bucket=bucket, Key=sidecar_path)
                            sidecar_data = json.loads(response['Body'].read().decode('utf-8'))
                            
                            data_layers = sidecar_data.get('data_layers', {})
                            analysis_json = (
                                data_layers.get('analysis_json') or 
                                data_layers.get('raw_debug_data', {}).get('visual_semantic_json') or 
                                data_layers.get('raw_debug_data', {}).get('memory_analysis_json') or 
                                data_layers.get('text_summary_analysis') or 
                                data_layers.get('raw_debug_data', {}).get('text_analysis_json') or 
                                {}
                            )
                            
                            # Content extraction - combine everything available
                            summary = analysis_json.get('graph_core', {}).get('summary') or ""
                            
                            text_content = sidecar_data.get("text") or data_layers.get('intermediate_results', {}).get('ocr_text') or ""
                            
                            # Fallback: if it's a text file and we have no text, try to read the original object directly
                            if not text_content and sidecar_data.get("mime_type", "").startswith("text/"):
                                try:
                                    orig_key = n.get("minio_path") or props.get("minio_path")
                                    
                                    # Try the explicit minio_path first
                                    try:
                                        if orig_key:
                                            orig_resp = minio_client.get_object(Bucket=bucket, Key=orig_key)
                                            text_content = orig_resp['Body'].read().decode('utf-8')
                                    except Exception:
                                        text_content = ""
                                        
                                    if not text_content:
                                        # Fallback to standard text storage path
                                        orig_name = sidecar_data.get("original_filename", "")
                                        candidates = [
                                            f"master_records/texts/{f_hash}.txt",
                                            f"master_records/texts/{f_hash}_{orig_name}",
                                            f"master_records/binaries/{f_hash}_{orig_name}"
                                        ]
                                        for cand_key in candidates:
                                            try:
                                                orig_resp = minio_client.get_object(Bucket=bucket, Key=cand_key)
                                                text_content = orig_resp['Body'].read().decode('utf-8')
                                                break
                                            except Exception:
                                                continue
                                                
                                except Exception as e_orig:
                                    logger.debug(f"Could not read original binary for {f_hash}: {e_orig}")

                            if text_content and len(text_content) > 1000:
                                text_content = text_content[:1000] + "... [Texto Truncado]"
                                
                            transcript = data_layers.get('intermediate_results', {}).get('audio_transcript', '') or ""
                            if transcript and len(transcript) > 1000:
                                transcript = transcript[:1000] + "... [Transcript Truncado]"
                                
                            visual_spec = analysis_json.get('visual_specifics', {})
                            ocr = visual_spec.get('ocr_text', '') or visual_spec.get('text_content', '') or ""
                            img_desc = f"{visual_spec.get('composition', '')} {visual_spec.get('visual_mood', '')}".strip()
                            
                            lyrics = analysis_json.get("audio_specifics", {}).get('lyrics_summary', '') or ""
                            
                            content_parts = []
                            if summary: content_parts.append(f"Resumen: {summary}")
                            if text_content: content_parts.append(f"Contenido texto: {text_content}")
                            if transcript: content_parts.append(f"TranscripciÃ³n de audio: {transcript}")
                            if ocr: content_parts.append(f"Texto ocr: {ocr}")
                            if img_desc: content_parts.append(f"DescripciÃ³n de imagen: {img_desc}")
                            if lyrics: content_parts.append(f"Letra de canciÃ³n: {lyrics}")
                            
                            content = "\n".join(content_parts)
                            
                            if content:
                                if len(content) > 3000:
                                    content = content[:3000] + "..."
                                
                                minio_contexts.append(f"Archivo '{n.get('name') or n.get('label', 'Unknown')}':\n{content}")
                        except Exception as inner_e:
                            logger.debug(f"Could not load minio sidecar for {f_hash}: {inner_e}")
        except Exception as e:
            logger.debug(f"Minio client error: {e}")
            
        context_block = ""
        if minio_contexts:
            joined_contexts = "\n\n---\n\n".join(minio_contexts)
            context_block = f"\n\n<CONTEXTO_ARCHIVOS>\n{joined_contexts}\n</CONTEXTO_ARCHIVOS>\n\nUsa este contexto de los archivos para explicar mÃ¡s a fondo DE QUÃ‰ tratan y dar sentido narrativo a las asociaciones conceptuales."

        # 2. Build Prompt
        system_prompt = f"""Eres un analista de datos y experto en grafos de conocimiento.
                            Tu tarea es explicar un camino asociativo (serendipia) descubierto por la herramienta '{req.tool_name}'.

                            CRÍTICO: Los caminos en un grafo de conocimiento no siempre son narrativamente lineales. Aunque recibas los nodos en un orden específico (del Nodo A al Nodo Z), la relación causal, psicológica o lógica puede explicarse mejor en sentido inverso (del Nodo Z al Nodo A) o partiendo del centro hacia los extremos.

                            Instrucciones:
                            1. Analiza el camino completo y EVALÚA cuál es la dirección narrativa más coherente (causa -> efecto, problema -> síntoma, o de lo mundano a lo profundo). 
                            2. Construye tu explicación siguiendo la dirección que elegiste como la más lógica, indicando claramente desde qué punto estás partiendo y hacia dónde te diriges.
                            3. Usa la información de <CONTEXTO_ARCHIVOS> para fundamentar la conexión (ej. letras de canciones, descripciones de imágenes, resúmenes). Es vital utilizar este contenido.
                            4. Escribe una narrativa fluida explicando paso a paso la conexión en la dirección seleccionada.
                            5. Menciona los pesos (weights) si son bajos (< 0.8), indicando que es una conexión "latente", "débil" o "sorprendente".
                            6. Si el camino pasa por un Concepto central (hub), menciónalo como el "puente conceptual".
                            7. OBLIGATORIO: Finaliza con un párrafo llamado "Conclusión del Subsistema" resumiendo el hallazgo general, la idea central que une todo el camino y justificando brevemente por qué la dirección narrativa elegida tiene sentido.
                            8. Mantén un tono analítico, profundo y fluido.
                            9. Responde en Español.
                            """

        user_prompt = f"Aquí tienes el conjunto de conexiones no direccionales extraídas del grafo de conocimiento:\n\n{path_context}{context_block}\n\nAnaliza este conjunto en su totalidad. Determina libremente cuál es la dirección narrativa o causal más lógica y explica detalladamente la cadena de asociaciones siguiendo esa dirección elegida, integrando la información de los archivos."

        # 3. Request to LLM Gateway
        url = f"{LLM_GATEWAY_URL}/v1/chat/completions"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        data = {
            "task": "chat",
            "privacy_mode": "strict" if req.privacy_mode else "flexible",
            "messages": json.dumps(messages),
            "temperature": 0.6,
            "provider": "openai" # Default explicitly to cloud for better reasoning
        }
        
        logger.info(f"Requesting path explanation for {len(req.nodes)} nodes via {LLM_GATEWAY_URL}")
        response = requests.post(url, data=data, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            answer = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            if not answer:
                answer = "Error: El LLM devolviÃ³ una respuesta vacÃ­a."
            return PathExplanationResponse(status="success", explanation=answer)
        else:
            logger.error(f"LLM Gateway error: HTTP {response.status_code} - {response.text}")
            return PathExplanationResponse(status="error", explanation=f"Error del LLM: HTTP {response.status_code}.")

    except requests.exceptions.Timeout:
        return PathExplanationResponse(status="error", explanation="El LLM tardÃ³ demasiado en responder (Timeout).")
    except Exception as e:
        logger.error(f"Error generating path explanation: {e}", exc_info=True)
        return PathExplanationResponse(status="error", explanation=f"Error interno: {str(e)}")


# ðŸŒ«ï¸ Fog of War (Distribution)
@router.post("/fog-distribution", response_model=AnalysisToolResponse)
def analyze_fog_of_war():
    driver = get_neo4j_driver()
    try:
        with driver.session() as session:
            query = """
                MATCH ()-[r]->()
                WHERE r.weight IS NOT NULL
                WITH toInteger(r.weight * 10) as decile, count(r) as c
                RETURN decile, c ORDER BY decile
            """
            result = session.run(query)
            
            distribution = []
            total_edges = 0
            
            # Initialize all deciles to 0
            decile_map = {i: 0 for i in range(10)} # 0-9
            
            for record in result:
                d = record["decile"]
                c = record["c"]
                if d is not None and 0 <= d <= 9:
                    decile_map[d] = c
                    total_edges += c
            
            labels = ["Ruido/Latente", "Muy DÃ©bil", "DÃ©bil", "Baja", "Media-Baja", "Media", "Media-Alta", "Alta", "Muy Alta", "Datos Duros"]
            
            for i in range(10):
                lower = i / 10.0
                upper = (i + 1) / 10.0
                count = decile_map[i]
                distribution.append({
                    "range": f"{lower:.1f}-{upper:.1f}",
                    "count": count,
                    "label": labels[i]
                })

            return {
                "tool": "fog_of_war",
                "status": "success",
                "message": "Calculated edge weight distribution.",
                "mock_data": {"distribution": distribution, "total_edges": total_edges}
            }

    except Exception as e:
        return {
            "tool": "fog_of_war",
            "status": "error",
            "message": f"Error calculating distribution: {str(e)}",
            "mock_data": {"distribution": [], "total_edges": 0}
        }

# Old Heatmap removed â€” replaced by Jaccard Co-Occurrence version at bottom of file

# Chord Diagram (Category Co-Occurrence via DigitalAssets)
@router.post("/chord", response_model=AnalysisToolResponse)
def analyze_chord(method: str = "standard", min_weight: float = 0.0):
    """
    Chord Dual: Standard (conteo de archivos) vs Fuzzy (intersecciÃ³n difusa).
    Zeroes Concept-Concept self-reference to avoid visual domination.
    """
    driver = get_neo4j_driver()

    categories = ["Person", "Organization", "Location", "Concept", "Event", "Project"]

    if method == "fuzzy":
        cypher_query = """
        WITH $categories as allowed_labels
        MATCH (n1)<-[r1]-(a:DigitalAsset)-[r2]->(n2)
        WHERE elementId(n1) < elementId(n2) AND coalesce(r1.weight, 1.0) >= $min_weight AND coalesce(r2.weight, 1.0) >= $min_weight
        WITH n1, n2, r1, r2, allowed_labels,
             head([lbl IN labels(n1) WHERE lbl IN allowed_labels]) as l1,
             head([lbl IN labels(n2) WHERE lbl IN allowed_labels]) as l2
        WHERE l1 IS NOT NULL AND l2 IS NOT NULL
        RETURN l1 as source, l2 as target,
               round(sum(CASE WHEN r1.weight < r2.weight THEN r1.weight ELSE r2.weight END), 2) as weight
        """
    else:
        cypher_query = """
        WITH $categories as allowed_labels
        MATCH (n1)<-[r1]-(a:DigitalAsset)-[r2]->(n2)
        WHERE elementId(n1) < elementId(n2) AND coalesce(r1.weight, 1.0) >= $min_weight AND coalesce(r2.weight, 1.0) >= $min_weight
        WITH n1, n2, a, allowed_labels,
             head([lbl IN labels(n1) WHERE lbl IN allowed_labels]) as l1,
             head([lbl IN labels(n2) WHERE lbl IN allowed_labels]) as l2
        WHERE l1 IS NOT NULL AND l2 IS NOT NULL
        RETURN l1 as source, l2 as target, count(distinct a) as weight
        """

    try:
        with driver.session() as session:
            result = session.run(cypher_query, categories=categories, min_weight=min_weight)
            records = list(result)

            matrix_map = {cat: {cat2: 0 for cat2 in categories} for cat in categories}

            for r in records:
                src, tgt, w = r["source"], r["target"], r["weight"]
                matrix_map[src][tgt] += w
                if src != tgt:
                    matrix_map[tgt][src] += w

            # Zero out Concept-Concept to prevent visual domination
            matrix_map["Concept"]["Concept"] = 0

            matrix_list = [[matrix_map[row][col] for col in categories] for row in categories]

            mode_name = "Fuzzy" if method == "fuzzy" else "Standard"
            return {
                "tool": "chord",
                "status": "success",
                "message": f"{mode_name} chord: {len(categories)} categorÃ­as.",
                "mock_data": {
                    "keys": categories,
                    "matrix": matrix_list,
                    "method": method,
                },
            }

    except Exception as e:
        print(f"ðŸ”¥ Error Chord ({method}): {e}")
        return {
            "tool": "chord",
            "status": "error",
            "message": f"Error: {str(e)}",
            "mock_data": {"keys": [], "matrix": [], "method": method},
        }

# ðŸŒ³ Radial Tree (Co-Occurrence Expansion)
class RadialTreeRequest(BaseModel):
    root_node_name: str = None

@router.post("/radial-tree", response_model=AnalysisToolResponse)
def analyze_radial(payload: RadialTreeRequest = None, method: str = "standard", min_weight: float = 0.0):
    """
    Radial Tree Dual: Standard (conteo archivos) vs Fuzzy (pesos difusos).
    L1 = 8 vecinos top, L2 = 3 vecinos por L1.
    """
    driver = get_neo4j_driver()
    try:
        with driver.session() as session:
            root_name = payload.root_node_name if payload and payload.root_node_name else None

            # If no root, pick highest-degree Concept
            if not root_name:
                res = session.run("""
                    MATCH (c)<--(d:DigitalAsset)
                    WITH c, count(d) as deg ORDER BY deg DESC LIMIT 1
                    RETURN c.name as name
                """)
                rec = res.single()
                if rec:
                    root_name = rec["name"]
                else:
                    return {
                        "tool": "radial_tree",
                        "status": "error",
                        "message": "Graph is empty.",
                        "mock_data": {"root": "", "nodes": [], "edges": [], "method": method}
                    }

            # --- Level 1: Top 8 neighbors ---
            if method == "fuzzy":
                l1_query = """
                    MATCH (root {name: $rootName})<-[r1]-(a:DigitalAsset)-[r2]->(l1)
                    WHERE elementId(root) <> elementId(l1) AND coalesce(r1.weight, 1.0) >= $min_weight AND coalesce(r2.weight, 1.0) >= $min_weight
                    WITH root, l1,
                         sum(CASE WHEN r1.weight < r2.weight THEN r1.weight ELSE r2.weight END) AS weight,
                         labels(l1)[0] AS ltype
                    ORDER BY weight DESC LIMIT 8
                    RETURN l1.name AS name, round(weight, 2) AS weight, ltype
                """
            else:
                l1_query = """
                    MATCH (root {name: $rootName})<-[r1]-(a:DigitalAsset)-[r2]->(l1)
                    WHERE elementId(root) <> elementId(l1) AND coalesce(r1.weight, 1.0) >= $min_weight AND coalesce(r2.weight, 1.0) >= $min_weight
                    WITH root, l1, count(distinct a) AS weight, labels(l1)[0] AS ltype
                    ORDER BY weight DESC LIMIT 8
                    RETURN l1.name AS name, weight, ltype
                """
            l1_result = session.run(l1_query, rootName=root_name, min_weight=min_weight)
            l1_records = list(l1_result)

            # Determine root type
            root_res = session.run("MATCH (r {name: $rootName}) RETURN labels(r)[0] as rtype", rootName=root_name)
            root_rec = root_res.single()
            root_type = root_rec["rtype"] if (root_rec and root_rec["rtype"]) else "Concept"

            nodes_list = [{"id": root_name, "level": 0, "type": root_type, "parent": None}]
            edges_list = []
            seen = {root_name}

            l1_names = []
            for r in l1_records:
                n = r["name"]
                if n and n not in seen:
                    seen.add(n)
                    l1_names.append(n)
                    nodes_list.append({
                        "id": n, "level": 1,
                        "type": r["ltype"] or "Concept",
                        "parent": root_name
                    })
                    edges_list.append({"source": root_name, "target": n})

            # --- Level 2: Top 3 per L1 node ---
            if l1_names:
                if method == "fuzzy":
                    l2_query = """
                        UNWIND $l1Names AS parentName
                        MATCH (parent {name: parentName})<-[r1]-(a:DigitalAsset)-[r2]->(l2)
                        WHERE NOT l2.name IN $seen AND elementId(parent) <> elementId(l2) AND coalesce(r1.weight, 1.0) >= $min_weight AND coalesce(r2.weight, 1.0) >= $min_weight
                        WITH parentName, l2,
                             sum(CASE WHEN r1.weight < r2.weight THEN r1.weight ELSE r2.weight END) AS weight,
                             labels(l2)[0] AS ltype
                        ORDER BY parentName, weight DESC
                        WITH parentName, collect({name: l2.name, weight: round(weight, 2), ltype: ltype})[0..3] AS children
                        UNWIND children AS child
                        RETURN parentName, child.name AS name, child.weight AS weight, child.ltype AS ltype
                    """
                else:
                    l2_query = """
                        UNWIND $l1Names AS parentName
                        MATCH (parent {name: parentName})<-[r1]-(a:DigitalAsset)-[r2]->(l2)
                        WHERE NOT l2.name IN $seen AND elementId(parent) <> elementId(l2) AND coalesce(r1.weight, 1.0) >= $min_weight AND coalesce(r2.weight, 1.0) >= $min_weight
                        WITH parentName, l2, count(distinct a) AS weight, labels(l2)[0] AS ltype
                        ORDER BY parentName, weight DESC
                        WITH parentName, collect({name: l2.name, weight: weight, ltype: ltype})[0..3] AS children
                        UNWIND children AS child
                        RETURN parentName, child.name AS name, child.weight AS weight, child.ltype AS ltype
                    """
                l2_result = session.run(l2_query, l1Names=l1_names, seen=list(seen), min_weight=min_weight)

                for r in l2_result:
                    n = r["name"]
                    parent = r["parentName"]
                    if n and n not in seen:
                        seen.add(n)
                        nodes_list.append({
                            "id": n, "level": 2,
                            "type": r["ltype"] or "Concept",
                            "parent": parent
                        })
                        edges_list.append({"source": parent, "target": n})

            mode_name = "Fuzzy" if method == "fuzzy" else "Standard"
            return {
                "tool": "radial_tree",
                "status": "success",
                "message": f"{mode_name} radial tree from '{root_name}' ({len(nodes_list)} nodes).",
                "mock_data": {
                    "root": root_name,
                    "nodes": nodes_list,
                    "edges": edges_list,
                    "method": method,
                },
            }

    except Exception as e:
        print(f"ðŸ”¥ Error Radial ({method}): {e}")
        return {
            "tool": "radial_tree",
            "status": "error",
            "message": f"Error: {str(e)}",
            "mock_data": {"root": "", "nodes": [], "edges": [], "method": method},
        }

# ï¿½ï¸ Abstract Concepts (Scatter Plot)
@router.post("/abstract-concepts", response_model=AnalysisToolResponse)
def analyze_abstract_concepts():
    """
    Scatter Plot: X=Grado (Cantidad), Y=Peso Promedio (Calidad/Certeza).
    Filtro relajado (degree >= 2) para visualizar datos incluso en datasets pequeÃ±os.
    """
    driver = get_neo4j_driver()

    cypher_query = """
    MATCH (c:Concept)<-[r]-(a:DigitalAsset)
    WITH c, count(r) as degree, avg(r.weight) as avg_weight
    WHERE degree >= 2
    RETURN c.name as id, degree as x, round(avg_weight, 2) as y
    ORDER BY degree DESC
    LIMIT 100
    """

    try:
        with driver.session() as session:
            result = session.run(cypher_query)
            data_points = [
                {"x": r["x"], "y": r["y"], "name": r["id"]}
                for r in result
            ]

            return {
                "tool": "abstract_concepts",
                "status": "success",
                "message": f"Found {len(data_points)} concepts.",
                "mock_data": {
                    "series": [
                        {
                            "id": "Conceptos",
                            "data": data_points
                        }
                    ]
                }
            }
    except Exception as e:
        return {
            "tool": "abstract_concepts",
            "status": "error",
            "message": str(e),
            "mock_data": {"series": []}
        }

# ï¿½ðŸ‘‘ PageRank
@router.post("/pagerank", response_model=AnalysisToolResponse)
def analyze_pagerank(method: str = "standard", min_weight: float = 0.0):
    """
    PageRank Dual: Standard (conteo de archivos) vs Fuzzy (pesos semÃ¡nticos).
    Usa proyecciÃ³n dirigida para que PageRank distribuya influencia correctamente.
    """
    driver = get_neo4j_driver()

    # --- ProyecciÃ³n segÃºn mÃ©todo (dirigida, sin undirected para PageRank) ---
    if method == "fuzzy":
        query_project = """
        MATCH (c1:Concept)<-[r1]-(a:DigitalAsset)-[r2]->(c2:Concept)
        WHERE elementId(c1) <> elementId(c2) AND coalesce(r1.weight, 1.0) >= $min_weight AND coalesce(r2.weight, 1.0) >= $min_weight
        WITH c1, c2, sum(CASE WHEN r1.weight < r2.weight THEN r1.weight ELSE r2.weight END) AS weight
        WITH gds.graph.project(
          'conceptPR', c1, c2,
          { relationshipProperties: { weight: weight } }
        ) AS g
        RETURN g.graphName AS graphName, g.nodeCount AS nodeCount, g.relationshipCount AS relationshipCount
        """
    else:
        query_project = """
        MATCH (c1:Concept)<-[r1]-(a:DigitalAsset)-[r2]->(c2:Concept)
        WHERE elementId(c1) <> elementId(c2) AND coalesce(r1.weight, 1.0) >= $min_weight AND coalesce(r2.weight, 1.0) >= $min_weight
        WITH c1, c2, count(a) AS weight
        WITH gds.graph.project(
          'conceptPR', c1, c2,
          { relationshipProperties: { weight: weight } }
        ) AS g
        RETURN g.graphName AS graphName, g.nodeCount AS nodeCount, g.relationshipCount AS relationshipCount
        """

    query_pagerank = """
    CALL gds.pageRank.stream('conceptPR', { relationshipWeightProperty: 'weight' })
    YIELD nodeId, score
    WITH gds.util.asNode(nodeId) AS n, score
    ORDER BY score DESC
    LIMIT 20
    RETURN n.name AS id, round(score, 4) AS value
    """

    try:
        with driver.session() as session:
            _safe_gds_project(session, 'conceptPR', query_project, min_weight=min_weight)
            result = session.run(query_pagerank)
            data = [{"id": r["id"], "value": r["value"]} for r in result]
            _safe_gds_drop(session, 'conceptPR')

            mode_name = "Fuzzy PageRank" if method == "fuzzy" else "Standard PageRank"
            return {
                "tool": "pagerank",
                "status": "success",
                "message": f"{mode_name} calculado para top {len(data)} conceptos.",
                "mock_data": {
                    "ranking": data,
                    "method": method,
                },
            }

    except Exception as e:
        print(f"ðŸ”¥ Error PageRank ({method}): {e}")
        return {
            "tool": "pagerank",
            "status": "error",
            "message": f"GDS Error: {str(e)}",
            "mock_data": {"ranking": [], "method": method},
        }

# ðŸšï¸ Orphan Nodes
@router.post("/orphans", response_model=AnalysisToolResponse)
def analyze_orphans():
    driver = get_neo4j_driver()
    try:
        with driver.session() as session:
            # Find DigitalAssets with no relationships
            query = """
                MATCH (d:DigitalAsset)
                WHERE NOT (d)--()
                RETURN d.filename as filename, elementId(d) as uuid
                LIMIT 50
            """
            result = session.run(query)
            
            nodes = [
                {"filename": record["filename"], "uuid": record["uuid"]}
                for record in result
            ]
            
            return {
                "tool": "orphan_nodes",
                "status": "success",
                "message": f"Found {len(nodes)} orphan assets.",
                "mock_data": {"count": len(nodes), "nodes": nodes}
            }
            
    except Exception as e:
         return {
            "tool": "orphan_nodes",
            "status": "error",
            "message": f"Error auditing orphan nodes: {str(e)}",
            "mock_data": {"count": 0, "nodes": []}
        }

# ðŸ“Š Weight Distribution
@router.post("/weight-distribution", response_model=AnalysisToolResponse)
def analyze_weight_distribution(step: float = 0.1):
    driver = get_neo4j_driver()
    try:
        # Determine multiplier based on step (0.1 -> 10, 0.05 -> 20)
        multiplier = int(1.0 / step)
        
        with driver.session() as session:
            # Histogram of edge weights
            query = f"""
                MATCH ()-[r]->()
                WHERE r.weight IS NOT NULL
                WITH toInteger(toFloat(r.weight) * {multiplier}) as bucket, count(*) as count
                RETURN bucket, count
                ORDER BY bucket ASC
            """
            result = session.run(query)
            
            # Initialize bins based on multiplier
            bins = []
            for i in range(multiplier):
                start_val = i * step
                end_val = (i + 1) * step
                # Special formatting for exact 0.05 vs 0.10 boundaries
                if step == 0.1:
                    range_label = f"{start_val:.1f}-{end_val:.1f}"
                else:
                    range_label = f"{start_val:.2f}-{end_val:.2f}"
                
                bins.append({"range": range_label, "count": 0, "bucket": i})
            
            for record in result:
                b = record["bucket"]
                
                if b is not None:
                    # The bucket could theoretically be exactly the multiplier if weight is 1.0
                    # Handle edge case where weight is 1.000 
                    if b >= multiplier:
                        b = multiplier - 1
                        
                    if 0 <= b < multiplier:
                        bins[b]["count"] += record["count"]
            
            # Format for Nivo Bar
            # data = [{ range: "0.0-0.1", count: 123 }, ...]
            
            return {
                "tool": "weight_distribution",
                "status": "success",
                "message": "Calculated edge weight histogram.",
                "mock_data": {"histogram": bins}
            }

    except Exception as e:
        return {
            "tool": "weight_distribution",
            "status": "error",
            "message": f"Error calculating weight distribution: {str(e)}",
            "mock_data": {"histogram": []}
        }

@router.post("/heatmap", response_model=AnalysisToolResponse)
def analyze_heatmap(method: str = "standard", min_weight: float = 0.0):
    """
    Genera matriz de calor Jaccard con soporte Dual (Standard y Fuzzy).
    """
    driver = get_neo4j_driver()

    # Query para Jaccard EstÃ¡ndar (Basado en conteo de archivos)
    query_standard = """
    MATCH (c:Concept)<--(d:DigitalAsset)
    // In standard, we might not have explicit weights on all relations, but if we do, filter them
    OPTIONAL MATCH (c)<-[r]-(d)
    WITH c, d, coalesce(r.weight, 1.0) as w
    WHERE w >= $min_weight
    WITH c, count(d) as degree
    ORDER BY degree DESC LIMIT 20
    WITH collect(c) as topConcepts

    UNWIND topConcepts as c1
    UNWIND topConcepts as c2
    
    CALL {
        WITH c1, c2
        MATCH (c1)<-[r1]-(a:DigitalAsset)-[r2]->(c2)
        WHERE coalesce(r1.weight, 1.0) >= $min_weight AND coalesce(r2.weight, 1.0) >= $min_weight
        RETURN count(distinct a) as intersection
    }

    CALL { WITH c1 MATCH (c1)<-[r1]-(a1:DigitalAsset) WHERE coalesce(r1.weight, 1.0) >= $min_weight RETURN count(distinct a1) as degree1 }
    CALL { WITH c2 MATCH (c2)<-[r2]-(a2:DigitalAsset) WHERE coalesce(r2.weight, 1.0) >= $min_weight RETURN count(distinct a2) as degree2 }
    
    WITH c1.name as x, c2.name as y, intersection, degree1, degree2
    WITH x, y, (degree1 + degree2 - intersection) as union_count, intersection
    
    RETURN x, y, 
           CASE 
             WHEN x = y THEN 1.0 
             WHEN union_count = 0 THEN 0.0
             ELSE round(toFloat(intersection) / toFloat(union_count), 3)
           END as weight
    ORDER BY x, y
    """

    # Query para Fuzzy Jaccard (Basado en pesos de relaciones difusas)
    query_fuzzy = """
    MATCH (c:Concept)<-[r]-(d:DigitalAsset)
    WHERE coalesce(r.weight, 1.0) >= $min_weight
    WITH c, sum(r.weight) as weighted_degree
    ORDER BY weighted_degree DESC LIMIT 20
    WITH collect(c) as topConcepts

    UNWIND topConcepts as c1
    UNWIND topConcepts as c2
    
    CALL {
        WITH c1, c2
        MATCH (c1)<-[r1]-(a:DigitalAsset)-[r2]->(c2)
        WHERE coalesce(r1.weight, 1.0) >= $min_weight AND coalesce(r2.weight, 1.0) >= $min_weight
        RETURN sum(CASE WHEN r1.weight < r2.weight THEN r1.weight ELSE r2.weight END) as fuzzy_intersection
    }

    CALL { WITH c1 MATCH (c1)<-[r1]-(:DigitalAsset) WHERE coalesce(r1.weight, 1.0) >= $min_weight RETURN sum(r1.weight) as sum_w1 }
    CALL { WITH c2 MATCH (c2)<-[r2]-(:DigitalAsset) WHERE coalesce(r2.weight, 1.0) >= $min_weight RETURN sum(r2.weight) as sum_w2 }
    
    WITH c1.name as x, c2.name as y, fuzzy_intersection, sum_w1, sum_w2
    WITH x, y, (sum_w1 + sum_w2 - fuzzy_intersection) as fuzzy_union, fuzzy_intersection
    
    RETURN x, y, 
           CASE 
             WHEN x = y THEN 1.0 
             WHEN fuzzy_union = 0 THEN 0.0
             ELSE round(toFloat(fuzzy_intersection) / toFloat(fuzzy_union), 3)
           END as weight
    ORDER BY x, y
    """

    cypher_query = query_fuzzy if method == "fuzzy" else query_standard

    try:
        with driver.session() as session:
            result = session.run(cypher_query, min_weight=min_weight)
            records = list(result)

            data_map = {}
            unique_keys = set()

            for r in records:
                row, col, val = r["x"], r["y"], r["weight"]
                unique_keys.add(row)
                unique_keys.add(col)
                if row not in data_map:
                    data_map[row] = {}
                data_map[row][col] = val

            sorted_keys = sorted(list(unique_keys))
            nivo_matrix = []

            for row_key in sorted_keys:
                data_points = []
                for col_key in sorted_keys:
                    val = data_map.get(row_key, {}).get(col_key, 0.0)
                    data_points.append({"x": col_key, "y": val})
                nivo_matrix.append({"id": row_key, "data": data_points})

            mode_name = "Fuzzy Jaccard" if method == "fuzzy" else "Standard Jaccard"
            return {
                "tool": "heatmap",
                "status": "success",
                "message": f"Generated {mode_name} matrix for {len(sorted_keys)} concepts.",
                "mock_data": {
                    "matrix": nivo_matrix,
                    "keys": sorted_keys,
                    "method": method,
                },
            }

    except Exception as e:
        print(f"ðŸ”¥ Error en Heatmap ({method}): {e}")
        return {
            "tool": "heatmap",
            "status": "error",
            "message": str(e),
            "mock_data": {"matrix": [], "keys": [], "method": method},
        }

# ==========================================
# 📂 SAVED PATHS (Serendipity & Pathfinder)
# ==========================================

import os
import json
from fastapi import HTTPException
from pathlib import Path

SAVED_PATHS_DIR = Path("data/saved_paths")

@router.get("/saved-paths")
def list_saved_paths():
    """Lists all JSON files in the saved_paths directory."""
    if not SAVED_PATHS_DIR.exists():
        try:
            SAVED_PATHS_DIR.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        return {"files": []}
        
    files = []
    for filepath in SAVED_PATHS_DIR.glob("*.json"):
        try:
            # We peek into the JSON to get the tool type or mode so the frontend can display a nice icon
            with open(filepath, 'r', encoding='utf-8') as f:
                content = json.load(f)
                
            tool_type = content.get("tool", "")
            if not tool_type and "mode" in content:
                tool_type = "pathfinder" if content.get("path_length") is not None else "unknown"
                
            files.append({
                "filename": filepath.name,
                "tool_type": tool_type,
                "created_at": content.get("generated_at") or content.get("exported_at") or "",
                "size_bytes": filepath.stat().st_size
            })
        except Exception as e:
            # If a file is malformed, we just return its name
            files.append({
                "filename": filepath.name,
                "tool_type": "unknown",
                "created_at": "",
                "size_bytes": filepath.stat().st_size
            })
            
    # Sort by newest first based on file modified time
    files.sort(key=lambda x: SAVED_PATHS_DIR.joinpath(x["filename"]).stat().st_mtime, reverse=True)
    return {"files": files}

@router.get("/saved-paths/{filename}")
def get_saved_path(filename: str):
    """Retrieves the exact JSON content of a highly specific saved path."""
    if not filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Filename must end with .json")
        
    filepath = SAVED_PATHS_DIR / filename
    
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found")
        
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading file: {str(e)}")
