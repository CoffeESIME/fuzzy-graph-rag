import sys
import os

# Setup imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared.clients import get_neo4j_driver

def repair_artist_links():
    driver = get_neo4j_driver()
    print("\n🩹 INICIANDO REPARACIÓN DE VÍNCULOS ARTISTA-ARCHIVO (V3 FINAL)...\n")

    with driver.session() as session:
        # 1. Traer solo archivos de AUDIO usando la propiedad correcta 'filename'
        query = """
        MATCH (d:DigitalAsset)
        WHERE d.mime_type CONTAINS 'audio' 
           OR d.filename ENDS WITH '.mp3' 
           OR d.filename ENDS WITH '.flac'
           OR d.filename ENDS WITH '.wav'
        RETURN elementId(d) as id, d.filename as filename
        """
        results = session.run(query)
        
        updates = 0
        
        for record in results:
            asset_id = record["id"]
            filename = record["filename"]
            
            # Si el filename es None (por alguna razón rara), saltar
            if not filename:
                continue

            # --- EXTRACCIÓN DE ARTISTA ---
            # Patrón: "Artista - Cancion.mp3"
            if " - " in filename:
                parts = filename.split(" - ")
                artist_name = parts[0].strip()
                
                # Ignoramos tracks numéricos (ej "01 - Intro.mp3") o muy cortos
                if artist_name.isdigit() or len(artist_name) < 2: 
                    continue

                print(f"   🔗 Conectando: '{filename}' -> Artista: '{artist_name}'")
                
                # Actualizamos en Neo4j
                # Usamos MERGE para evitar duplicados si corres el script varias veces
                update_q = """
                MATCH (d:DigitalAsset) WHERE elementId(d) = $asset_id
                
                MERGE (p:Person {name: $artist_name})
                ON CREATE SET p.created_via = 'heuristic_repair'
                
                MERGE (d)-[r:CREATED_BY]->(p)
                SET r.weight = 1.0
                """
                session.run(update_q, asset_id=asset_id, artist_name=artist_name)
                updates += 1

    if updates == 0:
        print("\n⚠️ No se encontraron archivos con el patrón 'Artista - Cancion'. Revisa tus nombres de archivo.")
    else:
        print(f"\n✅ Reparación completada. {updates} archivos conectados a sus Artistas.")

if __name__ == "__main__":
    repair_artist_links()