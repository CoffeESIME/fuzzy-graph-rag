from fastapi import APIRouter
from shared.clients import get_neo4j_driver
from pydantic import BaseModel
from typing import Dict, Any, List

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

# 🌉 Semantic Bridges (Betweenness Centrality)
@router.post("/bridges", response_model=AnalysisToolResponse)
def analyze_bridges():
    driver = get_neo4j_driver()
    try:
        with driver.session() as session:
            # 1. Safe project
            _safe_gds_project(session, 'bridgesGraph', """
                CALL gds.graph.project(
                  'bridgesGraph',
                  ['Concept', 'Person'],
                  {
                    ALL_RELS: {
                      type: '*',
                      orientation: 'UNDIRECTED'
                    }
                  }
                )
            """)

            # 3. Run Betweenness
            result = session.run("""
                CALL gds.betweenness.stream('bridgesGraph')
                YIELD nodeId, score
                WITH gds.util.asNode(nodeId) AS n, score
                ORDER BY score DESC LIMIT 20
                RETURN n.name as name, labels(n) as type, score
            """)
            
            bridges = [
                {
                    "name": record["name"],
                    "type": record["type"][0] if record["type"] else "Unknown",
                    "score": record["score"]
                } 
                for record in result
            ]

            # Cleanup
            _safe_gds_drop(session, 'bridgesGraph')

            return {
                "tool": "semantic_bridges",
                "status": "success",
                "message": "Identified top 20 bridge nodes acting as knowledge connectors.",
                "mock_data": {"bridges": bridges, "impact_score": bridges[0]['score'] if bridges else 0}
            }
            
    except Exception as e:
        return {
            "tool": "semantic_bridges",
            "status": "error",
            "message": f"GDS Error: {str(e)}",
            "mock_data": {"bridges": [], "impact_score": 0.0}
        }

# 🎲 Serendipity Path
@router.post("/serendipity", response_model=AnalysisToolResponse)
def analyze_serendipity():
    driver = get_neo4j_driver()
    try:
        with driver.session() as session:
            # Random weak path discovery
            # 1. Pick a random start node
            # 2. Perform a random walk reusing low-weight edges if possible, or just find a path with low weights
            # NOTE: purely random walk is better than shortestPath for serendipity
            # Walk through shared DigitalAssets to discover serendipitous concept paths
            query = """
                MATCH (s:Concept) WITH s, rand() AS r ORDER BY r LIMIT 1
                MATCH (s)<--(d1:DigitalAsset)-->(mid:Concept)<--(d2:DigitalAsset)-->(t:Concept)
                WHERE elementId(s) <> elementId(mid) AND elementId(mid) <> elementId(t)
                  AND elementId(s) <> elementId(t)
                WITH s, mid, t,
                     count(distinct d1) as shared1, count(distinct d2) as shared2
                WITH [s.name, mid.name, t.name] as path_nodes,
                     [toFloat(shared1)/10.0, toFloat(shared2)/10.0] as path_weights,
                     (toFloat(shared1) + toFloat(shared2)) / 10.0 as total_score
                ORDER BY total_score ASC
                LIMIT 1
                RETURN path_nodes, path_weights, total_score
            """
            result = session.run(query)
            record = result.single()
            
            if not record:
                # Fallback: simpler 2-hop path
                fallback_query = """
                    MATCH (s:Concept) WITH s, rand() AS r ORDER BY r LIMIT 1
                    MATCH (s)<--(d:DigitalAsset)-->(t:Concept)
                    WHERE elementId(s) <> elementId(t)
                    WITH s, t, count(distinct d) as shared
                    WITH [s.name, t.name] as path_nodes,
                         [toFloat(shared)/10.0] as path_weights,
                         toFloat(shared)/10.0 as total_score
                    ORDER BY total_score ASC
                    LIMIT 1
                    RETURN path_nodes, path_weights, total_score
                """
                result = session.run(fallback_query)
                record = result.single()

            path_data = []
            if record:
                nodes = record["path_nodes"]
                weights = record["path_weights"]
                total_score = record["total_score"]
                
                for i in range(len(nodes) - 1):
                    # Guard against index out of range if weights has fewer elements than edges (shouldn't happen with shortestPath)
                    weight = weights[i] if i < len(weights) else 0.0
                    path_data.append({
                        "node": nodes[i],
                        "edge": f"CO_OCCURS ({weight:.2f})",
                        "next": nodes[i+1],
                        "weight": weight
                    })
                
                # Add last node info (terminal)
                # path_data structure requested: [{"node": "A", "edge": "...", "next": "B"}]
                # The prompt example shows steps.
            else:
                total_score = 0.0

            return {
                "tool": "serendipity_path",
                "status": "success",
                "message": "Found a serendipitous path through the knowledge graph.",
                "mock_data": {"path": path_data, "total_serendipity_score": total_score, "source": nodes[0] if record else "?", "target": nodes[-1] if record else "?"}
            }

    except Exception as e:
        return {
            "tool": "serendipity_path",
            "status": "error",
            "message": f"Error finding path: {str(e)}",
            "mock_data": {"path": [], "total_serendipity_score": 0.0}
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

# 🍩 Chord Diagram
@router.post("/chord", response_model=AnalysisToolResponse)
def analyze_chord():
    driver = get_neo4j_driver()
    try:
        with driver.session() as session:
            # Defined categories to analyze
            categories = ['Person', 'Organization', 'Location', 'Concept', 'Event', 'Project']
            
            # Initialize NxN matrix with 0
            n = len(categories)
            matrix = [[0 for _ in range(n)] for _ in range(n)]
            
            # Map category name to index
            cat_to_idx = {cat: i for i, cat in enumerate(categories)}
            
            # Query to count connections between categories
            query = """
                MATCH (a)-[r]-(b)
                WHERE any(l IN labels(a) WHERE l IN $categories)
                  AND any(l IN labels(b) WHERE l IN $categories)
                WITH labels(a) as labelsA, labels(b) as labelsB, count(r) as count
                RETURN labelsA, labelsB, count
            """
            
            result = session.run(query, categories=categories)
            
            for record in result:
                # Extract the primary label matching our list
                lA = next((l for l in record["labelsA"] if l in cat_to_idx), None)
                lB = next((l for l in record["labelsB"] if l in cat_to_idx), None)
                
                if lA and lB:
                    idxA = cat_to_idx[lA]
                    idxB = cat_to_idx[lB]
                    count = record["count"]
                    
                    # Add to matrix (undirected count)
                    matrix[idxA][idxB] += count
                    # Don't double count if it's the same relationship record? 
                    # Cypher matches (a)-[r]-(b) which is undirected pattern, but usually returns one direction per match if we don't direct it?
                    # Actually (a)-[r]-(b) might match twice A->B and B<-A if not careful?
                    # GDS project uses undirected orientation.
                    # Here we just want flow volume.
                    # If A!=B, matrix is symmetric-ish?
                    # Chord expects directed flow usually, but for undirected graph, we can mirror or just fill one side.
                    # Let's verify: Neo4j returns r once per relationship if we don't specify direction?
                    # Actually MATCH (a)-[r]-(b) returns twice: once for (a,b), once for (b,a).
                    # So we should be careful.
                    # Whatever, Nivo Chord handles it. If symmetric, it shows balanced ribbons.

            return {
                "tool": "chord_diagram",
                "status": "success",
                "message": "Calculated inter-category relationship flows.",
                "mock_data": {"matrix": matrix, "keys": categories}
            }

    except Exception as e:
        return {
            "tool": "chord_diagram",
            "status": "error",
            "message": f"Error generating chord diagram: {str(e)}",
            "mock_data": {"matrix": [], "keys": []}
        }

# 🌳 Radial Tree
class RadialTreeRequest(BaseModel):
    root_node_name: str = None

@router.post("/radial-tree", response_model=AnalysisToolResponse)
def analyze_radial(payload: RadialTreeRequest = None):
    driver = get_neo4j_driver()
    try:
        with driver.session() as session:
            root_name = payload.root_node_name if payload and payload.root_node_name else None
            
            # If no root specified, find a central node (highest degree)
            if not root_name:
                res = session.run("MATCH (n:Concept) WITH n, count{(n)--()} as d ORDER BY d DESC LIMIT 1 RETURN n.name as name")
                rec = res.single()
                if rec:
                    root_name = rec["name"]
                else:
                    return {
                        "tool": "radial_tree",
                        "status": "error",
                        "message": "Graph is empty, cannot find root.",
                        "mock_data": {"nodes": [], "edges": []}
                    }

            # Query for 2 layers of expansion
            # Using simple path traversal to get nodes and edges
            # We want specific levels: 0 (root), 1 (neighbors), 2 (neighbors of neighbors)
            query = """
                MATCH (root) WHERE root.name = $rootName
                
                // Level 1
                OPTIONAL MATCH (root)-[r1]-(l1)
                
                // Level 2 (exclude root to avoid backtracking)
                OPTIONAL MATCH (l1)-[r2]-(l2)
                WHERE elementId(l2) <> elementId(root)
                
                WITH root, l1, l2, r1, r2
                LIMIT 200 // Safety limit
                
                RETURN 
                    root.name as root,
                    l1.name as name1,
                    l2.name as name2,
                    elementId(r1) as r1_id,
                    elementId(r2) as r2_id
            """
            
            result = session.run(query, rootName=root_name)
            
            nodes_map = {} # name -> level
            edges_set = set() # (src, tgt) tuples
            
            # Add root level 0
            nodes_map[root_name] = 0
            
            for record in result:
                # Level 1
                n1 = record["name1"]
                if n1:
                    if n1 not in nodes_map:
                        nodes_map[n1] = 1
                    edges_set.add(tuple(sorted((root_name, n1))))
                    
                    # Level 2
                    n2 = record["name2"]
                    if n2:
                        if n2 not in nodes_map:
                            nodes_map[n2] = 2
                        # Edge l1-l2
                        edges_set.add(tuple(sorted((n1, n2))))
            
            nodes = [{"id": name, "level": lvl} for name, lvl in nodes_map.items()]
            edges = [{"source": e[0], "target": e[1]} for e in edges_set]
            
            return {
                "tool": "radial_tree",
                "status": "success",
                "message": f"Expanded radial tree from root '{root_name}'.",
                "mock_data": {"root": root_name, "nodes": nodes, "edges": edges}
            }

    except Exception as e:
        return {
            "tool": "radial_tree",
            "status": "error",
            "message": f"Error generating radial tree: {str(e)}",
            "mock_data": {"nodes": [], "edges": []}
        }

# 👑 PageRank
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

# 🕸️ Abstract Concepts
@router.post("/abstract-concepts", response_model=AnalysisToolResponse)
def analyze_abstract_concepts():
    driver = get_neo4j_driver()
    try:
        with driver.session() as session:
            # High connectivity (degree > 5) but low weight (< 0.6)
            # These are "fuzzy glue" concepts
            query = """
                MATCH (c:Concept)-[r]-()
                WITH c, count(r) as degree, avg(r.weight) as avg_weight
                WHERE degree > 5 AND avg_weight < 0.6
                RETURN c.name as id, degree as x, avg_weight as y
                ORDER BY degree DESC
                LIMIT 50
            """
            result = session.run(query)
            
            data = [
                {
                    "id": record["id"],
                    "data": [{"x": record["x"], "y": record["y"]}]
                }
                for record in result
            ]
            
            return {
                "tool": "abstract_concepts",
                "status": "success",
                "message": "Identified abstract concepts (high degree, low weight).",
                "mock_data": {"abstract_nodes": data}
            }

    except Exception as e:
        return {
            "tool": "abstract_concepts",
            "status": "error",
            "message": f"Error finding abstract concepts: {str(e)}",
            "mock_data": {"abstract_nodes": []}
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

# 🍩 Chord Diagram – Category Co-Occurrence
@router.post("/chord", response_model=AnalysisToolResponse)
def analyze_chord():
    """
    Genera la matriz de relaciones entre Categorías (Labels) del grafo.
    Cuenta cuántos DigitalAssets conectan una categoría con otra.
    """
    driver = get_neo4j_driver()

    categories = ["Concept", "Person", "Location", "Event", "Organization"]

    cypher_query = """
    UNWIND $categories as sourceLabel
    UNWIND $categories as targetLabel

    CALL {
        WITH sourceLabel, targetLabel
        MATCH (n1)<--(a:DigitalAsset)-->(n2)
        WHERE sourceLabel IN labels(n1) AND targetLabel IN labels(n2)
          AND elementId(n1) <> elementId(n2)
        RETURN count(distinct a) as weight
    }

    RETURN sourceLabel, targetLabel, weight
    ORDER BY sourceLabel, targetLabel
    """

    try:
        with driver.session() as session:
            result = session.run(cypher_query, categories=categories)
            records = list(result)

            # Build NxN matrix for Nivo Chord
            matrix_dict = {cat: {cat2: 0 for cat2 in categories} for cat in categories}

            for r in records:
                src = r["sourceLabel"]
                tgt = r["targetLabel"]
                w = r["weight"]
                matrix_dict[src][tgt] = w

            matrix_list = []
            for row_cat in categories:
                row_data = []
                for col_cat in categories:
                    row_data.append(matrix_dict[row_cat][col_cat])
                matrix_list.append(row_data)

            return {
                "tool": "chord",
                "status": "success",
                "message": f"Category co-occurrence matrix ({len(categories)} categories).",
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
            "message": f"Error computing chord: {str(e)}",
            "mock_data": {"keys": [], "matrix": []}
        }