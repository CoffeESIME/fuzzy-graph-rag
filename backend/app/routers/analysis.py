from fastapi import APIRouter
from shared.clients import get_neo4j_driver, get_minio_client
from config.settings import get_settings
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import re
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

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
    # Now project — if STILL fails (race condition), drop hard and retry
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

# 🧬 Community Detection (Louvain via Cypher Projection)
@router.post("/communities", response_model=AnalysisToolResponse)
def analyze_communities(method: str = "standard", min_weight: float = 0.9):
    """
    Detecta comunidades usando GDS Louvain con soporte Dual (Standard y Fuzzy).
    Standard: aristas = conteo de archivos compartidos, nodos = count(archivos).
    Fuzzy: aristas = sum(min(w1,w2)), nodos = sum(pesos relaciones).
    Aplica el filtro MIN_WEIGHT.
    """
    driver = get_neo4j_driver()

    # --- Proyección según método ---
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

    # --- Louvain + enriquecer con tamaño real ---
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
                comm_name = f"Tema: {r['top_members'][0]['name']}" if r['top_members'] else f"Clúster {idx + 1}"

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
                "message": f"{mode_name} detectó {len(communities_data)} comunidades.",
                "mock_data": {
                    "packing_data": nivo_data,
                    "method": method,
                },
            }

    except Exception as e:
        print(f"🔥 Error Communities: {e}")
        return {
            "tool": "communities",
            "status": "error",
            "message": f"GDS Error: {str(e)}",
            "mock_data": {"packing_data": {}}
        }

# 🌉 Semantic Bridges (Bowtie Heuristic — no GDS needed)
@router.post("/bridges", response_model=AnalysisToolResponse)
def analyze_bridges(method: str = "standard", min_weight: float = 0.9):
    """
    Puentes Semánticos Dual: Standard (conteo) vs Fuzzy (pesos difusos).
    bridge_score = diversity × degree (standard) o diversity × fuzzy_weight (fuzzy).
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
        print(f"🔥 Error Bridges ({method}): {e}")
        return {
            "tool": "bridges",
            "status": "error",
            "message": str(e),
            "mock_data": {"bridges": [], "method": method},
        }

# ── MinIO helpers ──
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


# 🎲 Serendipity Path (Fuzzy Random Walk)
@router.post("/serendipity", response_model=AnalysisToolResponse)
def analyze_serendipity():
    """
    Genera un camino asociativo (Serendipia) saltando entre Conceptos y Assets.
    Favorece caminos que incluyen al menos una conexión 'difusa' (weight < 0.9).
    """
    driver = get_neo4j_driver()

    cypher_query = """
    // 1. Elegir un nodo de inicio aleatorio que tenga conexiones difusas
    MATCH (start:Concept)<-[r]-(:DigitalAsset)
    WHERE r.weight < 0.9
    WITH start ORDER BY rand() LIMIT 1

    // 2. Trazar un camino de 2 Assets de profundidad
    MATCH path = (start)<-[r1]-(a1:DigitalAsset)-[r2]->(mid:Concept)<-[r3]-(a2:DigitalAsset)-[r4]->(end:Concept)

    // 3. Evitar bucles
    WHERE elementId(start) <> elementId(mid)
      AND elementId(mid) <> elementId(end)
      AND elementId(start) <> elementId(end)
      AND elementId(a1) <> elementId(a2)

    // 4. Factor Serendipia: Al menos una relación verdaderamente difusa
      AND (r1.weight <= 0.7 OR r2.weight <= 0.7 OR r3.weight <= 0.7 OR r4.weight <= 0.7)

    // 5. Elegir un camino al azar
    WITH path, start, a1, mid, a2, end, r1, r2, r3, r4
    ORDER BY rand()
    LIMIT 1

    // 6. Formatear como secuencia de pasos (incluir propiedades de Asset)
    RETURN
        elementId(start) as step1_id, start.name as step1_node, 'Concept' as step1_type,
        r1.weight as edge1_weight,
        elementId(a1) as step2_id, coalesce(a1.name, a1.filename) as step2_node, 'Asset' as step2_type,
        a1.file_hash as a1_hash, a1.mime_type as a1_mime,
        r2.weight as edge2_weight,
        elementId(mid) as step3_id, mid.name as step3_node, 'Concept' as step3_type,
        r3.weight as edge3_weight,
        elementId(a2) as step4_id, coalesce(a2.name, a2.filename) as step4_node, 'Asset' as step4_type,
        a2.file_hash as a2_hash, a2.mime_type as a2_mime,
        r4.weight as edge4_weight,
        elementId(end) as step5_id, end.name as step5_node, 'Concept' as step5_type
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
                {"id": record["step3_id"], "name": record["step3_node"], "type": record["step3_type"], "weight": _rw(record["edge2_weight"])},
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
        print(f"🔥 Error Serendipity: {e}")
        return {
            "tool": "serendipity",
            "status": "error",
            "message": str(e),
            "mock_data": {"path": []}
        }

# 🌫️ Fog of War (Distribution)
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
            
            labels = ["Ruido/Latente", "Muy Débil", "Débil", "Baja", "Media-Baja", "Media", "Media-Alta", "Alta", "Muy Alta", "Datos Duros"]
            
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

# 🧮 Old Heatmap removed — replaced by Jaccard Co-Occurrence version at bottom of file

# 🍩 Chord Diagram (Category Co-Occurrence via DigitalAssets)
@router.post("/chord", response_model=AnalysisToolResponse)
def analyze_chord(method: str = "standard", min_weight: float = 0.0):
    """
    Chord Dual: Standard (conteo de archivos) vs Fuzzy (intersección difusa).
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
                "message": f"{mode_name} chord: {len(categories)} categorías.",
                "mock_data": {
                    "keys": categories,
                    "matrix": matrix_list,
                    "method": method,
                },
            }

    except Exception as e:
        print(f"🔥 Error Chord ({method}): {e}")
        return {
            "tool": "chord",
            "status": "error",
            "message": f"Error: {str(e)}",
            "mock_data": {"keys": [], "matrix": [], "method": method},
        }

# 🌳 Radial Tree (Co-Occurrence Expansion)
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
        print(f"🔥 Error Radial ({method}): {e}")
        return {
            "tool": "radial_tree",
            "status": "error",
            "message": f"Error: {str(e)}",
            "mock_data": {"root": "", "nodes": [], "edges": [], "method": method},
        }

# �️ Abstract Concepts (Scatter Plot)
@router.post("/abstract-concepts", response_model=AnalysisToolResponse)
def analyze_abstract_concepts():
    """
    Scatter Plot: X=Grado (Cantidad), Y=Peso Promedio (Calidad/Certeza).
    Filtro relajado (degree >= 2) para visualizar datos incluso en datasets pequeños.
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

# �👑 PageRank
@router.post("/pagerank", response_model=AnalysisToolResponse)
def analyze_pagerank(method: str = "standard", min_weight: float = 0.0):
    """
    PageRank Dual: Standard (conteo de archivos) vs Fuzzy (pesos semánticos).
    Usa proyección dirigida para que PageRank distribuya influencia correctamente.
    """
    driver = get_neo4j_driver()

    # --- Proyección según método (dirigida, sin undirected para PageRank) ---
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
        print(f"🔥 Error PageRank ({method}): {e}")
        return {
            "tool": "pagerank",
            "status": "error",
            "message": f"GDS Error: {str(e)}",
            "mock_data": {"ranking": [], "method": method},
        }

# 🏚️ Orphan Nodes
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

# 📊 Weight Distribution
@router.post("/weight-distribution", response_model=AnalysisToolResponse)
def analyze_weight_distribution():
    driver = get_neo4j_driver()
    try:
        with driver.session() as session:
            # Histogram of edge weights
            query = """
                MATCH ()-[r]->()
                WHERE r.weight IS NOT NULL
                WITH toInteger(r.weight * 10) as bucket, count(*) as count
                RETURN bucket, count
                ORDER BY bucket ASC
            """
            result = session.run(query)
            
            # Initialize 10 bins
            bins = [{"range": f"{i/10:.1f}-{(i+1)/10:.1f}", "count": 0, "bucket": i} for i in range(10)]
            
            for record in result:
                b = record["bucket"]
                if 0 <= b < 10:
                    bins[b]["count"] = record["count"]
            
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

    # Query para Jaccard Estándar (Basado en conteo de archivos)
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
        print(f"🔥 Error en Heatmap ({method}): {e}")
        return {
            "tool": "heatmap",
            "status": "error",
            "message": str(e),
            "mock_data": {"matrix": [], "keys": [], "method": method},
        }

