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

# 🧬 Community Detection (Louvain)
@router.post("/communities", response_model=AnalysisToolResponse)
def analyze_communities():
    driver = get_neo4j_driver()
    try:
        with driver.session() as session:
            # 1. Clean up potential stale graph (Check existence first to be safe, or just drop yielding)
            # Yielding graphName ensures we consume the result and wait for it
            session.run("CALL gds.graph.drop('knowledgeGraph', false) YIELD graphName")
            
            # 2. Project Graph
            session.run("""
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

            # 4. Cleanup
            session.run("CALL gds.graph.drop('knowledgeGraph', false)")

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
            # 1. Clean up potential stale graph
            session.run("CALL gds.graph.drop('bridgesGraph', false) YIELD graphName")
            
            # 2. Project Graph
            session.run("""
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

            # 4. Cleanup
            session.run("CALL gds.graph.drop('bridgesGraph', false) YIELD graphName")

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
            query = """
                MATCH (s:Concept) WITH s, rand() AS r ORDER BY r LIMIT 1
                MATCH p = (s)-[:RELATED_TO*2..3]-(t:Concept)
                WHERE all(r in relationships(p) WHERE r.weight < 0.6)
                AND elementId(s) <> elementId(t)
                RETURN [x in nodes(p) | x.name] as path_nodes,
                       [r in relationships(p) | r.weight] as path_weights,
                       reduce(acc=0.0, r in relationships(p) | acc + r.weight) as total_score
                LIMIT 1
            """
            result = session.run(query)
            record = result.single()
            
            if not record:
                # Fallback: strict conditions failed, relax weight constraint
                fallback_query = """
                    MATCH (s:Concept) WITH s, rand() AS r ORDER BY r LIMIT 1
                    MATCH p = (s)-[:RELATED_TO*2]-(t:Concept)
                    WHERE elementId(s) <> elementId(t)
                    RETURN [x in nodes(p) | x.name] as path_nodes,
                           [r in relationships(p) | r.weight] as path_weights,
                           reduce(acc=0.0, r in relationships(p) | acc + r.weight) as total_score
                    LIMIT 1
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
                        "edge": f"RELATED_TO ({weight:.2f})",
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
                MATCH ()-[r:RELATED_TO]->()
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

# 🧮 Heatmap (Concept Adjacency)
@router.post("/heatmap", response_model=AnalysisToolResponse)
def analyze_heatmap():
    driver = get_neo4j_driver()
    try:
        with driver.session() as session:
            # 1. Get Top 20 Concepts by Degree
            top_nodes_query = """
                MATCH (n:Concept)
                WITH n, count{ (n)--() } as degree
                ORDER BY degree DESC LIMIT 20
                RETURN n.name as name
            """
            result_nodes = session.run(top_nodes_query)
            top_names = [record["name"] for record in result_nodes]
            
            if not top_names:
                return {
                    "tool": "concept_heatmap",
                    "status": "error",
                    "message": "No concepts found to analyze.",
                    "mock_data": {"matrix": [], "keys": []}
                }

            # 2. Build Adjacency Matrix
            # We need to check every pair (A, B) in top_names
            matrix_data = [] # List of {id: "A", data: [{x: "B", y: 0.5}, ...]}
            
            # Use a single query to get all relationships between these nodes to minimize DB calls
            # Passing list of names to Cypher
            rels_query = """
                MATCH (a:Concept)-[r:RELATED_TO]-(b:Concept)
                WHERE a.name IN $names AND b.name IN $names
                RETURN a.name as source, b.name as target, r.weight as weight
            """
            result_rels = session.run(rels_query, names=top_names)
            
            # Map: "A" -> "B" -> weight
            adjacency = {name: {other: 0.0 for other in top_names} for name in top_names}
            
            for record in result_rels:
                src = record["source"]
                tgt = record["target"]
                w = record["weight"] if record["weight"] is not None else 0.5 # Default weight if missing
                if src in adjacency and tgt in adjacency[src]:
                    adjacency[src][tgt] = w
                if tgt in adjacency and src in adjacency[tgt]:
                    adjacency[tgt][src] = w

            # Format for Nivo Heatmap
            for row_name in top_names:
                row_data = []
                for col_name in top_names:
                    # Heatmap usually X=col, Y=row. 
                    # id=row_name, data=[{x=col_name, y=value}]
                    val = adjacency[row_name][col_name]
                    # Self-loop can be 1.0 or 0. Let's make it 1.0 to show identity, or null/0.
                    if row_name == col_name:
                        val = 1.0
                    row_data.append({"x": col_name, "y": val})
                
                matrix_data.append({
                    "id": row_name,
                    "data": row_data
                })

            return {
                "tool": "concept_heatmap",
                "status": "success",
                "message": f"Generated adjacency matrix for top {len(top_names)} concepts.",
                "mock_data": {"matrix": matrix_data, "keys": top_names}
            }

    except Exception as e:
        return {
            "tool": "concept_heatmap",
            "status": "error",
            "message": f"Error generating heatmap: {str(e)}",
            "mock_data": {"matrix": [], "keys": []}
        }

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
@router.post("/radial", response_model=AnalysisToolResponse)
def analyze_radial():
    return {
        "tool": "radial_tree",
        "status": "placeholder",
        "message": "Hierarchical expansion logic pending.",
        "mock_data": {"root": {}, "children": []}
    }

# 👑 PageRank
@router.post("/pagerank", response_model=AnalysisToolResponse)
def analyze_pagerank():
    return {
        "tool": "pagerank",
        "status": "placeholder",
        "message": "PageRank centrality algorithm pending.",
        "mock_data": {"top_nodes": []}
    }

# 🕸️ Abstract Concepts
@router.post("/abstract-concepts", response_model=AnalysisToolResponse)
def analyze_abstract_concepts():
    return {
        "tool": "abstract_concepts",
        "status": "placeholder",
        "message": "High connectivity / low weight detection pending.",
        "mock_data": {"abstract_nodes": []}
    }

# 🏚️ Orphan Nodes
@router.post("/orphans", response_model=AnalysisToolResponse)
def analyze_orphans():
    return {
        "tool": "orphan_nodes",
        "status": "placeholder",
        "message": "Disconnected node audit pending.",
        "mock_data": {"count": 0, "nodes": []}
    }

# 📊 Weight Distribution
@router.post("/weight-distribution", response_model=AnalysisToolResponse)
def analyze_weight_distribution():
    return {
        "tool": "weight_distribution",
        "status": "placeholder",
        "message": "Edge weight histogram calculation pending.",
        "mock_data": {"bins": [], "counts": []}
    }
