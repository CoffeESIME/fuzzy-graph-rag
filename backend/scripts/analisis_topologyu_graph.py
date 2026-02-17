import sys
import os
import pandas as pd # Usaremos pandas para mostrar tablas bonitas en consola

# Setup de imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared.clients import get_neo4j_driver

def run_topology_analysis():
    driver = get_neo4j_driver()
    
    print("\n🔬 INICIANDO ANÁLISIS DE TOPOLOGÍA DEL FUZZY GRAPH\n")

    with driver.session() as session:
        
        # ==============================================================================
        # 1. ANÁLISIS DE ENTIDADES (PERSONAS) - ¿Candidatos a Enriquecer o Borrar?
        # ==============================================================================
        print("--- [1] TOP 20 PERSONAS CONECTADAS (Hubs vs Ruido) ---")
        # Tu query mejorada: Busca conexiones entrantes y salientes
        q1 = """
        MATCH (p:Person)
        // Calculamos el grado (número de conexiones totales)
        WITH p, count{(p)--()} as degree 
        ORDER BY degree DESC LIMIT 20

        // Traemos contexto: ¿Quién lo menciona? ¿A dónde se conecta?
        MATCH (p)--(connected)
        
        RETURN 
            p.name as Nombre, 
            degree as Total_Conexiones,
            collect(distinct labels(connected)[0])[..3] as Tipos_Conectados,
            collect(distinct coalesce(connected.name, connected.original_name))[..3] as Ejemplos
        """
        result = session.run(q1)
        df1 = pd.DataFrame([r.data() for r in result])
        if not df1.empty:
            print(df1.to_string(index=False))
        else:
            print("⚠️ No se encontraron nodos Person conectados.")

        # ==============================================================================
        # 2. ANÁLISIS DE PESOS (FUZZY LOGIC) - ¿Tenemos matices?
        # ==============================================================================
        print("\n--- [2] DISTRIBUCIÓN DE PESOS DIFUSOS (Fuzzy Weights) ---")
        # Tu query para ver si tenemos pesos variados o todo es plano
        q2 = """
        MATCH ()-[r]->()
        WHERE r.weight IS NOT NULL
        RETURN 
            r.weight as Peso,
            count(r) as Frecuencia
        ORDER BY Peso DESC
        """
        result = session.run(q2)
        df2 = pd.DataFrame([r.data() for r in result])
        if not df2.empty:
            print(df2.to_string(index=False))
        else:
            print("⚠️ No se encontraron relaciones con propiedad 'weight'.")

        # ==============================================================================
        # 3. CONEXIONES FUERTES (Core Knowledge)
        # ==============================================================================
        print("\n--- [3] CONEXIONES FUERTES (Weight >= 0.85) ---")
        q3 = """
        MATCH (d:DigitalAsset)-[r]->(c:Concept)
        WHERE r.weight >= 0.85
        RETURN 
            d.original_name as Archivo, 
            r.weight as Peso, 
            c.name as Concepto_Central
        LIMIT 10
        """
        result = session.run(q3)
        df3 = pd.DataFrame([r.data() for r in result])
        if not df3.empty:
            print(df3.to_string(index=False))

        # ==============================================================================
        # 4. CONEXIONES DÉBILES / AMBIGUAS (Contexto Lateral)
        # ==============================================================================
        print("\n--- [4] CONEXIONES DIFUSAS (0.4 <= Weight <= 0.7) ---")
        q4 = """
        MATCH (d:DigitalAsset)-[r]->(c:Concept)
        WHERE r.weight >= 0.4 AND r.weight <= 0.7
        RETURN 
            d.original_name as Archivo, 
            r.weight as Peso, 
            c.name as Concepto_Lateral
        ORDER BY r.weight ASC
        LIMIT 10
        """
        result = session.run(q4)
        df4 = pd.DataFrame([r.data() for r in result])
        if not df4.empty:
            print(df4.to_string(index=False))

        # ==============================================================================
        # 5. ANÁLISIS DE PUENTES (La Joya del RAG)
        # ==============================================================================
        print("\n--- [5] PUENTES SEMÁNTICOS (Archivos conectados por Conceptos) ---")
        # Esta query nos dice: "El archivo A se parece al B porque ambos hablan de X"
        q5 = """
        MATCH (d1:DigitalAsset)-[r1]->(c:Concept)<-[r2]-(d2:DigitalAsset)
        WHERE elementId(d1) < elementId(d2) // Evitar duplicados A-B vs B-A
        
        // Calculamos la fuerza del puente (promedio de ambos pesos)
        WITH d1, d2, c, (r1.weight + r2.weight) / 2 AS Fuerza_Puente
        WHERE Fuerza_Puente > 0.6 // Solo puentes relevantes
        
        RETURN 
            d1.original_name as Asset_A, 
            '<--[' + c.name + ']-->' as Puente,
            d2.original_name as Asset_B,
            round(Fuerza_Puente, 2) as Score
        ORDER BY Fuerza_Puente DESC
        LIMIT 15
        """
        result = session.run(q5)
        df5 = pd.DataFrame([r.data() for r in result])
        if not df5.empty:
            print(df5.to_string(index=False))
        else:
            print("⚠️ No se encontraron puentes semánticos entre archivos.")

if __name__ == "__main__":
    try:
        run_topology_analysis()
    except Exception as e:
        print(f"❌ Error ejecutando análisis: {e}")