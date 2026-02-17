import sys
import os
import pandas as pd

# Setup imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared.clients import get_neo4j_driver

def find_candidates():
    driver = get_neo4j_driver()
    print("\n🕵️  RADAR DE ENRIQUECIMIENTO (V3 - SCHEMA MATCHED)...\n")

    with driver.session() as session:
        
        # ==============================================================================
        # 1. PERSONAS / FIGURAS (Usando MENTIONS_PERSON)
        # ==============================================================================
        print("--- [1] PERSONAS VIP (Pendientes de Bio) ---")
        q_persons = """
        MATCH (p:Person)
        WHERE p.enriched IS NULL  
          AND NOT p.name IN ['Usuario', 'Admin', 'Me']
        
        // Usamos la relación correcta: MENTIONS_PERSON o CREATED_BY
        MATCH (p)<-[:MENTIONS_PERSON|:CREATED_BY]-(asset:DigitalAsset)
        
        RETURN 
            p.name as Candidato,
            count(distinct asset) as Conexiones,
            'Sidecar: Biography' as Accion
        ORDER BY Conexiones DESC
        LIMIT 10
        """
        df_p = pd.DataFrame([r.data() for r in session.run(q_persons)])
        if not df_p.empty:
            print(df_p.to_string(index=False))
        else:
            print("✅ No hay Personas pendientes.")

        # ==============================================================================
        # 2. BANDAS / MÚSICA (Detectadas por extensión de archivo)
        # ==============================================================================
        print("\n--- [2] BANDAS / ARTISTAS (Contexto Audio) ---")
        q_audio = """
        MATCH (n:Person) // A veces las bandas nacen como Person
        WHERE n.enriched IS NULL
        
        // Buscamos conexión con mp3/flac usando la propiedad correcta 'filename'
        MATCH (n)<-[:MENTIONS_PERSON|:CREATED_BY]-(asset:DigitalAsset)
        WHERE (asset.mime_type CONTAINS 'audio' OR asset.filename ENDS WITH '.mp3')
        
        RETURN 
            n.name as Candidato,
            count(distinct asset) as Tracks,
            'Sidecar: Band Profile' as Accion
        ORDER BY Tracks DESC
        LIMIT 10
        """
        df_a = pd.DataFrame([r.data() for r in session.run(q_audio)])
        if not df_a.empty:
            print(df_a.to_string(index=False))

        # ==============================================================================
        # 3. CONCEPTOS MAYORES (Usando EVOKES_CONCEPT)
        # ==============================================================================
        print("\n--- [3] CONCEPTOS ABSTRACTOS (Ismos y Logías) ---")
        # Aquí filtramos los conceptos que suenan "importantes" (terminan en ismo/logía)
        # y que ya están conectados a algo en tu grafo.
        q_concepts = """
        MATCH (c:Concept)
        WHERE c.enriched IS NULL
          AND (c.name ENDS WITH 'ismo' OR c.name ENDS WITH 'ism' OR c.name ENDS WITH 'logía')
        
        // Solo si están siendo usados en el grafo
        MATCH (c)<-[:EVOKES_CONCEPT]-(asset:DigitalAsset)
        
        RETURN 
            c.name as Concepto,
            count(distinct asset) as Referencias,
            'Sidecar: Definition' as Accion
        ORDER BY Referencias DESC
        LIMIT 10
        """
        df_c = pd.DataFrame([r.data() for r in session.run(q_concepts)])
        if not df_c.empty:
            print(df_c.to_string(index=False))

if __name__ == "__main__":
    find_candidates()