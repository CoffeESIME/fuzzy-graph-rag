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

def _safe_gds_project(session, graph_name: str, project_query: str):
    """Project a GDS graph, dropping any stale version first. Retry-safe."""
    # Try dropping first (might not exist, that's fine)
    try:
        session.run(f"CALL gds.graph.drop('{graph_name}')").consume()
    except Exception:
        pass
    # Now project — if STILL fails (race condition), drop hard and retry
    try:
        session.run(project_query).consume()
    except Exception as e:
        if 'already loaded' in str(e).lower():
            # Nuclear option: list and drop, then retry
            try:
                session.run(f"CALL gds.graph.drop('{graph_name}')").consume()
            except Exception:
                pass
            session.run(project_query).consume()
        else:
            raise

def _safe_gds_drop(session, graph_name: str):
    """Safely drop a GDS graph, ignoring if not found."""
    try:
        session.run(f"CALL gds.graph.drop('{graph_name}')").consume()
    except Exception:
        pass

# 🧬 Community Detection (Louvain)
@router.post("/communities", response_model=AnalysisToolResponse)
def analyze_communities():
    driver = get_neo4j_driver()
    try:
        with driver.session() as session:
            # 1. Safe project
            _safe_gds_project(session, 'knowledgeGraph', """
                CALL gds.graph.project(
                  'knowledgeGraph',
                  ['Concept', 'Person', 'Location', 'Event'],
                  {
                    ALL_RELS: {
                      type: '*',
                      orientation: 'UNDIRECTED'
                    }
                  }
                )
            """)

            # 3. Run Louvain
            result = session.run("""
                CALL gds.louvain.stream('knowledgeGraph')
                YIELD nodeId, communityId
                WITH gds.util.asNode(nodeId) AS n, communityId
                WITH communityId, collect(n.name) AS members, count(n) as size
                ORDER BY size DESC LIMIT 10
                RETURN communityId, members[0..5] as top_members, size
            """)
            
            communities = [
                {
                    "id": record["communityId"],
                    "members": record["top_members"],
                    "size": record["size"]
                } 
                for record in result
            ]

            # Cleanup
            _safe_gds_drop(session, 'knowledgeGraph')

            return {
                "tool": "community_detection",
                "status": "success",
                "message": f"Detected {len(communities)} major communities using Louvain algorithm.",
                "mock_data": {"clusters": len(communities), "nodes": communities}
            }
            
    except Exception as e:
        return {
            "tool": "community_detection",
            "status": "error",
            "message": f"GDS Error: {str(e)}",
            "mock_data": {"nodes": [], "clusters": 0}
        }

# 🌉 Semantic Bridges (Bowtie Heuristic — no GDS needed)
@router.post("/bridges", response_model=AnalysisToolResponse)
def analyze_bridges():
    """
    Encuentra Conceptos que actúan como puentes semánticos.
    Heurística: Conceptos que conectan con la mayor diversidad de etiquetas (Labels)
    y archivos distintos. bridge_score = diversity_score * connected_nodes.
    """
    driver = get_neo4j_driver()

    cypher_query = """
    // 1. Conceptos con buena cantidad de conexiones (>= 3 assets)
    MATCH (bridge:Concept)<-[]-(a:DigitalAsset)
    WITH bridge, count(distinct a) as asset_count
    WHERE asset_count >= 3

    // 2. Ver a qué OTRAS cosas se conectan esos assets
    MATCH (bridge)<-[]-(a:DigitalAsset)-->(other)
    WHERE elementId(bridge) <> elementId(other)

    // 3. Diversidad: cuántos labels distintos une
    WITH bridge, asset_count,
         count(distinct other) as connected_nodes,
         size(collect(distinct head(
           [lbl IN labels(other) WHERE lbl IN ['Person','Organization','Location','Concept','Event','Project']]
         ))) as diversity_score

    // 4. Bridge Score
    WITH bridge.name as concept, asset_count, connected_nodes, diversity_score,
         (diversity_score * connected_nodes) as bridge_score
    ORDER BY bridge_score DESC
    LIMIT 10

    // 5. Extraer contexto (los "Dos Mundos" que une)
    MATCH (b:Concept {name: concept})<-[]-(a:DigitalAsset)-->(o)
    WHERE elementId(b) <> elementId(o)
    WITH concept, bridge_score, collect(distinct o.name)[0..5] as connected_examples

    RETURN concept as id, bridge_score as score, connected_examples as context
    ORDER BY score DESC
    """

    try:
        with driver.session() as session:
            result = session.run(cypher_query)
            bridges = [
                {"id": r["id"], "score": r["score"], "context": r["context"]}
                for r in result
            ]

            return {
                "tool": "bridges",
                "status": "success",
                "message": f"Found top {len(bridges)} semantic bridges.",
                "mock_data": {"bridges": bridges}
            }
    except Exception as e:
        print(f"🔥 Error Bridges: {e}")
        return {
            "tool": "bridges",
            "status": "error",
            "message": str(e),
            "mock_data": {"bridges": []}
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
        start.name as step1_node, 'Concept' as step1_type,
        r1.weight as edge1_weight,
        a1.filename as step2_node, 'Asset' as step2_type,
        a1.file_hash as a1_hash, a1.mime_type as a1_mime,
        r2.weight as edge2_weight,
        mid.name as step3_node, 'Concept' as step3_type,
        r3.weight as edge3_weight,
        a2.filename as step4_node, 'Asset' as step4_type,
        a2.file_hash as a2_hash, a2.mime_type as a2_mime,
        r4.weight as edge4_weight,
        end.name as step5_node, 'Concept' as step5_type
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
                {"id": record["step1_node"], "type": record["step1_type"], "weight": None},
                {
                    "id": record["step2_node"], "type": record["step2_type"],
                    "weight": _rw(record["edge1_weight"]),
                    "file_hash": record.get("a1_hash"),
                    "mime_type": record.get("a1_mime"),
                    **a1_minio,
                },
                {"id": record["step3_node"], "type": record["step3_type"], "weight": _rw(record["edge2_weight"])},
                {
                    "id": record["step4_node"], "type": record["step4_type"],
                    "weight": _rw(record["edge3_weight"]),
                    "file_hash": record.get("a2_hash"),
                    "mime_type": record.get("a2_mime"),
                    **a2_minio,
                },
                {"id": record["step5_node"], "type": record["step5_type"], "weight": _rw(record["edge4_weight"])},
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
def analyze_chord():
    """
    Genera la matriz de flujo entre Categorías (Co-ocurrencia a través de DigitalAssets).
    Usa head([lbl IN labels(n) WHERE lbl IN allowed]) para extraer label principal.
    Zeroes Concept-Concept self-reference to avoid visual domination.
    """
    driver = get_neo4j_driver()

    categories = ["Person", "Organization", "Location", "Concept", "Event", "Project"]

    cypher_query = """
    WITH $categories as allowed_labels

    MATCH (n1)<--(a:DigitalAsset)-->(n2)
    WHERE elementId(n1) < elementId(n2)

    WITH n1, n2, allowed_labels,
         head([lbl IN labels(n1) WHERE lbl IN allowed_labels]) as l1,
         head([lbl IN labels(n2) WHERE lbl IN allowed_labels]) as l2

    WHERE l1 IS NOT NULL AND l2 IS NOT NULL

    RETURN l1 as source, l2 as target, count(*) as weight
    """

    try:
        with driver.session() as session:
            result = session.run(cypher_query, categories=categories)
            records = list(result)

            matrix_map = {cat: {cat2: 0 for cat2 in categories} for cat in categories}

            for r in records:
                src = r["source"]
                tgt = r["target"]
                w = r["weight"]
                matrix_map[src][tgt] += w
                if src != tgt:
                    matrix_map[tgt][src] += w

            # Zero out Concept-Concept to prevent visual domination
            matrix_map["Concept"]["Concept"] = 0

            matrix_list = []
            for row_cat in categories:
                row_data = []
                for col_cat in categories:
                    row_data.append(matrix_map[row_cat][col_cat])
                matrix_list.append(row_data)

            return {
                "tool": "chord",
                "status": "success",
                "message": f"Category flows calculated ({len(categories)} categories).",
                "mock_data": {
                    "keys": categories,
                    "matrix": matrix_list
                }
            }

    except Exception as e:
        print(f"🔥 Error Chord: {e}")
        return {
            "tool": "chord",
            "status": "error",
            "message": f"Error: {str(e)}",
            "mock_data": {"keys": [], "matrix": []}
        }

# 🌳 Radial Tree (Co-Occurrence Expansion)
class RadialTreeRequest(BaseModel):
    root_node_name: str = None

@router.post("/radial-tree", response_model=AnalysisToolResponse)
def analyze_radial(payload: RadialTreeRequest = None):
    driver = get_neo4j_driver()
    try:
        with driver.session() as session:
            root_name = payload.root_node_name if payload and payload.root_node_name else None

            # If no root, pick highest-degree Concept
            if not root_name:
                res = session.run("""
                    MATCH (c:Concept)<--(d:DigitalAsset)
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
                        "mock_data": {"root": "", "nodes": [], "edges": []}
                    }

            # Level 1: Top 10 co-occurring concepts with root
            l1_query = """
                MATCH (root:Concept {name: $rootName})<--(a:DigitalAsset)-->(l1)
                WHERE elementId(root) <> elementId(l1)
                WITH root, l1, count(distinct a) as weight, labels(l1)[0] as ltype
                ORDER BY weight DESC LIMIT 10
                RETURN l1.name as name, weight, ltype
            """
            l1_result = session.run(l1_query, rootName=root_name)
            l1_records = list(l1_result)

            nodes_list = [{"id": root_name, "level": 0, "type": "Concept", "parent": None}]
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

            # Level 2: Top 5 co-occurring per L1 node (excluding seen)
            if l1_names:
                l2_query = """
                    UNWIND $l1Names as parentName
                    MATCH (parent {name: parentName})<--(a:DigitalAsset)-->(l2)
                    WHERE NOT l2.name IN $seen AND elementId(parent) <> elementId(l2)
                    WITH parentName, l2, count(distinct a) as weight, labels(l2)[0] as ltype
                    ORDER BY parentName, weight DESC
                    WITH parentName, collect({name: l2.name, weight: weight, ltype: ltype})[0..5] as children
                    UNWIND children as child
                    RETURN parentName, child.name as name, child.weight as weight, child.ltype as ltype
                """
                l2_result = session.run(l2_query, l1Names=l1_names, seen=list(seen))

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

            return {
                "tool": "radial_tree",
                "status": "success",
                "message": f"Expanded radial tree from '{root_name}' ({len(nodes_list)} nodes).",
                "mock_data": {"root": root_name, "nodes": nodes_list, "edges": edges_list}
            }

    except Exception as e:
        return {
            "tool": "radial_tree",
            "status": "error",
            "message": f"Error: {str(e)}",
            "mock_data": {"root": "", "nodes": [], "edges": []}
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
def analyze_pagerank():
    driver = get_neo4j_driver()
    try:
        with driver.session() as session:
            # 1. Safe project
            _safe_gds_project(session, 'pagerankGraph', """
                CALL gds.graph.project(
                    'pagerankGraph',
                    ['Concept', 'Person', 'Organization'],
                    '*'
                )
            """)
            
            # 3. Stream PageRank
            result = session.run("""
                CALL gds.pageRank.stream('pagerankGraph')
                YIELD nodeId, score
                WITH gds.util.asNode(nodeId) AS n, score
                WHERE score > 0.15
                RETURN n.name AS id, score as value, labels(n)[0] as category
                ORDER BY score DESC
                LIMIT 20
            """)
            
            data = [
                {
                    "id": record["id"],
                    "value": record["value"],
                    "category": record["category"]
                }
                for record in result
            ]
            
            # Cleanup
            _safe_gds_drop(session, 'pagerankGraph')
            
            return {
                "tool": "pagerank",
                "status": "success",
                "message": "Calculated top influencial nodes using PageRank.",
                "mock_data": {"ranking": data}
            }

    except Exception as e:
        return {
            "tool": "pagerank",
            "status": "error",
            "message": f"GDS Error: {str(e)}",
            "mock_data": {"ranking": []}
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
def analyze_heatmap():
    """
    Genera matriz de calor Jaccard.
    Versión Simplificada y Robusta: Usa nodos directos y recálculo en línea.
    """
    driver = get_neo4j_driver()

    cypher_query = """
    // 1. Obtener Top 20 Nodos (Solo los nodos, nada más)
    MATCH (c:Concept)<--(d:DigitalAsset)
    WITH c, count(d) as degree
    ORDER BY degree DESC LIMIT 20
    WITH collect(c) as topConcepts

    // 2. Producto Cartesiano (Todos contra Todos)
    UNWIND topConcepts as c1
    UNWIND topConcepts as c2
    
    // 3. Calcular Intersección (El corazón del problema)
    // Usamos COUNT subquery para aislar la lógica y forzar ejecución
    CALL {
        WITH c1, c2
        MATCH (c1)<--(a:DigitalAsset)-->(c2)
        RETURN count(distinct a) as intersection
    }

    // 4. Calcular Grados Individuales (Recálculo seguro)
    CALL {
        WITH c1
        MATCH (c1)<--(a1:DigitalAsset)
        RETURN count(distinct a1) as degree1
    }
    CALL {
        WITH c2
        MATCH (c2)<--(a2:DigitalAsset)
        RETURN count(distinct a2) as degree2
    }
    
    // 5. Matemática Jaccard
    WITH c1.name as x, c2.name as y, intersection, degree1, degree2
    WITH x, y, 
         (degree1 + degree2 - intersection) as union_count,
         intersection
    
    RETURN x, y, 
           CASE 
             WHEN x = y THEN 1.0 
             WHEN union_count = 0 THEN 0.0
             ELSE round(toFloat(intersection) / toFloat(union_count), 3)
           END as weight
    ORDER BY x, y
    """
    
    try:
        with driver.session() as session:
            result = session.run(cypher_query)
            records = list(result)

            # --- Procesamiento Python (Garantizar Matriz Cuadrada) ---
            data_map = {}
            unique_keys = set()
            
            # Primera pasada: Llenar mapa
            for r in records:
                row = r["x"]
                col = r["y"]
                val = r["weight"]
                unique_keys.add(row)
                unique_keys.add(col)
                
                if row not in data_map: data_map[row] = {}
                data_map[row][col] = val

            # Segunda pasada: Construir lista para Nivo
            sorted_keys = sorted(list(unique_keys))
            nivo_matrix = []
            
            for row_key in sorted_keys:
                data_points = []
                for col_key in sorted_keys:
                    # Si no hay dato, es 0.0
                    val = data_map.get(row_key, {}).get(col_key, 0.0)
                    data_points.append({ "x": col_key, "y": val })
                
                nivo_matrix.append({ "id": row_key, "data": data_points })

            return {
                "tool": "heatmap",
                "status": "success",
                "message": f"Generated matrix for {len(sorted_keys)} concepts.",
                "mock_data": {
                    "matrix": nivo_matrix, 
                    "keys": sorted_keys
                }
            }

    except Exception as e:
        print(f"🔥 Error en Heatmap: {e}")
        return {
            "tool": "heatmap",
            "status": "error",
            "message": str(e),
            "mock_data": {"matrix": [], "keys": []}
        }
    """
    Genera una matriz de calor basada en la Co-Ocurrencia de conceptos (Jaccard).
    Versión Optimizada: Pre-calcula grados para evitar errores de agregación.
    """
    driver = get_neo4j_driver()

    cypher_query = """
    // 1. Pre-calcular Nodos y sus Grados (Top 20)
    // Esto asegura que 'degree' es estático y correcto antes de comparar
    MATCH (c:Concept)<-[]-(:DigitalAsset)
    WITH c, count(*) as degree
    ORDER BY degree DESC 
    LIMIT 20
    WITH collect({node: c, name: c.name, degree: degree}) as topNodes

    // 2. Producto Cartesiano
    UNWIND topNodes as item1
    UNWIND topNodes as item2

    // 3. Calcular Intersección (Solo buscamos esto, el resto ya lo tenemos)
    // Usamos elementId para asegurar que macheamos el nodo correcto de la lista
    OPTIONAL MATCH (c1:Concept)<-[]-(common:DigitalAsset)-[]->(c2:Concept)
    WHERE elementId(c1) = elementId(item1.node) 
      AND elementId(c2) = elementId(item2.node)
    
    WITH item1, item2, count(distinct common) as intersection

    // 4. Fórmula Jaccard con datos pre-calculados
    WITH item1.name as x, item2.name as y, 
         intersection,
         (item1.degree + item2.degree - intersection) as union_count
    
    RETURN x, y, 
           CASE 
             WHEN x = y THEN 1.0 
             WHEN union_count = 0 THEN 0.0
             ELSE round(toFloat(intersection) / toFloat(union_count), 3)
           END as weight
    ORDER BY x, y
    """
    
    try:
        with driver.session() as session:
            result = session.run(cypher_query)
            records = list(result)

            # --- Procesamiento Robusto para Nivo Heatmap ---
            
            # 1. Recolectar todos los valores y claves únicas
            data_map = {}
            unique_keys = set()
            
            for r in records:
                row = r["x"]
                col = r["y"]
                val = r["weight"]
                
                unique_keys.add(row)
                unique_keys.add(col)
                
                if row not in data_map: data_map[row] = {}
                data_map[row][col] = val

            # 2. Ordenar claves para que la matriz se vea bonita
            sorted_keys = sorted(list(unique_keys))

            # 3. Construir la estructura densa NxN (rellenando huecos con 0)
            nivo_matrix = []
            for row_key in sorted_keys:
                data_points = []
                for col_key in sorted_keys:
                    # Si Neo4j no devolvió esa pareja (raro con UNWIND, pero posible), es 0
                    val = data_map.get(row_key, {}).get(col_key, 0.0)
                    data_points.append({ "x": col_key, "y": val })
                
                nivo_matrix.append({ "id": row_key, "data": data_points })

            return {
                "tool": "heatmap",
                "status": "success",
                "message": f"Generated Jaccard matrix for {len(sorted_keys)} concepts.",
                "mock_data": {
                    "matrix": nivo_matrix, 
                    "keys": sorted_keys # Claves únicas y ordenadas
                }
            }

    except Exception as e:
        # Log del error real para depuración
        print(f"🔥 Error en Heatmap: {e}")
        return {
            "tool": "heatmap",
            "status": "error",
            "message": f"Error computing heatmap: {str(e)}",
            "mock_data": {"matrix": [], "keys": []}
        }

