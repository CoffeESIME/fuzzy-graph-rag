"""
diagnose_nodes.py - Script de diagnóstico de nodos en Neo4j.

Busca nodos por nombre y muestra todas sus conexiones,
tipos de relación, propiedades de aristas y contexto de vecinos.

Uso:
    cd backend
    python -m scripts.diagnose_nodes
    
    # O con nodos personalizados:
    python -m scripts.diagnose_nodes "Nodo1" "Nodo2" "Nodo3"
"""

import sys
import os

# Asegurar que el directorio 'backend' esté en el path para importar shared/config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.clients import get_neo4j_driver


def diagnose_nodes(node_names: list[str]):
    driver = get_neo4j_driver()

    # Query quirúrgica: busca el nodo y todo lo que lo toca.
    # Extrae el TIPO de relación y las PROPIEDADES de esa relación.
    query = """
    MATCH (n)
    WHERE n.name IN $names

    // Buscar cualquier cosa conectada a 'n' (entrante o saliente)
    OPTIONAL MATCH (n)-[r]-(neighbor)

    RETURN
        n.name        AS NodeName,
        labels(n)     AS NodeLabels,
        type(r)       AS RelationType,
        properties(r) AS RelationProps,
        labels(neighbor)    AS NeighborLabels,
        neighbor.name       AS NeighborName,
        neighbor.file_path  AS SourceFile
    ORDER BY n.name
    """

    print(f"🕵️  Iniciando diagnóstico para: {node_names}\n")

    with driver.session() as session:
        result = session.run(query, names=node_names)

        current_node = ""
        found_any = False

        for record in result:
            found_any = True
            node = record["NodeName"]

            # Encabezado visual por cada nodo principal
            if node != current_node:
                print(f"\n{'='*40}")
                print(f"🧬 NODO: {node} {record['NodeLabels']}")
                print(f"{'='*40}")
                current_node = node

            # Si no tiene conexiones
            if record["RelationType"] is None:
                print(f"   ⚠️  NODO HUÉRFANO (Sin conexiones)")
                continue

            # Análisis de la conexión
            relation = record["RelationType"]
            neighbor = record["NeighborName"]
            neighbor_type = record["NeighborLabels"]

            # Intentar deducir el contexto
            context_clue = "Desconocido"
            if record["SourceFile"]:
                context_clue = f"📂 Archivo: {os.path.basename(record['SourceFile'])}"
            elif "Concept" in neighbor_type:
                context_clue = "🧠 Concepto Abstracto"
            elif "Person" in neighbor_type:
                context_clue = "👤 Relación Social"

            print(f"   |--[{relation}]--> {neighbor} ({neighbor_type})")
            print(f"   |      Contexto: {context_clue}")
            print(f"   |      Detalles Arista: {record['RelationProps']}")
            print("   |")

        if not found_any:
            print("   ❌ No se encontraron nodos con esos nombres en la base de datos.")


# --- EJECUCIÓN ---
if __name__ == "__main__":
    # Si se pasan nombres como argumentos CLI, usarlos; si no, usar lista de muestra
    if len(sys.argv) > 1:
        lista = sys.argv[1:]
    else:
        lista = ["Jesucristo", "Batman", "Hombre", "Stratovarius", "Sísifo"]

    diagnose_nodes(lista)
