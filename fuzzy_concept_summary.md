# Resumen Técnico: Implementación de Entidades Difusas en GraphRAG

El sistema de GraphRAG implementa un enfoque de lógica difusa (fuzzy logic) para la extracción y análisis de conceptos, permitiendo capturar la incertidumbre, los matices y las interpretaciones subjetivas, especialmente útil para análisis de dominios humanísticos o artísticos.

A continuación, se detalla el ciclo de vida de estas entidades difusas, desde su inyección hasta su visualización.

---

## 1. Ingesta y Extracción (LLM Analysis)

El proceso comienza en el `LLM Gateway`, guiado por las instrucciones en `prompts.py` (`build_specialized_prompt`).

### La Escala Maestra (Rubric)
El LLM es instruido estrictamente con una **Rúbrica de Calibración de Confianza (Confidence Scoring Rubric)** que define cómo asignar los pesos (weights) difusos, típicamente de `0.0` a `1.0`:
*   **1.0 (Realidad Dura):** Evidencia directa, objetos físicos, entidades nombradas (lugares, personas).
*   **0.8 - 0.9 (Conceptos Explícitos):** Temas abstractos mencionados explícitamente en el texto.
*   **0.5 - 0.7 (Interpretación / Metáforas):** Zona objetivo para el arte. Conexiones metafóricas, tonos emocionales no explícitos.
*   **0.0 - 0.4 (Ruido):** Conexiones débiles.

### Reglas Críticas (Penalizaciones)
*   **Techo Abstracto:** Los conceptos intangibles (Emociones, Filosofía) **nunca** reciben 1.0; se limitan a un máximo de 0.9.
*   **Penalización por Metáfora:** Si una conexión es poética, el score debe ser `< 0.7`.
*   **Traducción de Metáforas:** En lugar de extraer el objeto literal de una metáfora (ej. "fuerte como un toro" -> extraer "Toro"), el LLM debe extraer el atributo (ej. "Fuerza") con una confianza modificada (típicamente 0.6).

### El Output del LLM
El LLM devuelve una estructura JSON que incluye la lista de `concepts` sugeridos. Cada concepto tiene:
*   `name`: Nombre del concepto.
*   `type`: Micro-categoría.
*   `domain`: Macro-área (ej. Arts, Psychology).
*   `relation_type`: Cómo se relaciona con el activo (`EVOKES`, `EXPLORES`, `DEFINES`).
*   **`confidence`**: El valor float (el peso difuso) basado en la rúbrica.

## 2. Aprobación y Creación de Nodos (Human-in-the-Loop)

Las sugerencias del LLM no van directamente al grafo principal; primero se almacenan en un nodo `InboxItem` con estado `REVIEW_REQUIRED`. El usuario revisa estas sugerencias a través del endpoint `/inbox/pending`.

### Promoción al Grafo (`promote_inbox_to_graph` en `routers/inbox.py`)
Cuando el usuario aprueba un item (`POST /inbox/{file_hash}/approve`), se ejecutan queries Cypher para crear o actualizar los nodos y relaciones en Neo4j:

```cypher
MATCH (a:DigitalAsset {file_hash: $file_hash})
MERGE (c:Concept {name: $name})
// ... (set properties)
MERGE (a)-[r:{rel_type}]->(c)
ON CREATE SET 
    r.weight = $weight, // El peso difuso (confidence)
    r.reasoning = $reasoning
ON MATCH SET
    // Si la relación ya existe, nos quedamos con el peso más alto
    r.weight = CASE WHEN $weight > r.weight THEN $weight ELSE r.weight END
```
*   **Creación:** Un nodo `Concept` genérico y una relación dinámica (ej. `EVOKES`, que por defecto es `EVOKES_CONCEPT` en otras partes, aunque el validador lo sanea a `EVOKES`).
*   **Recalculado de Pesos en Ingesta:** Si un `DigitalAsset` ya tenía una relación con ese `Concept`, la regla actual en `inbox.py` es **toma el peso mayor (`CASE WHEN $weight > r.weight THEN $weight ELSE r.weight END`)**.

## 3. Enriquecimiento de Conceptos (Scripts asíncronos)

El script `find_candidates_enrichment.py` busca candidatos en el grafo que necesitan enriquecimiento adicional (como añadir descripciones o biografías a través de llamadas de LLM secundarias).

Para los conceptos abstractos difusos, busca nodos `Concept` vinculados a través de `EVOKES_CONCEPT` que tengan sufijos asociados a abstracciones (ej. "ismo", "logía") y genera una tarea de enriquecimiento ("Sidecar: Definition").

## 4. Recálculo y Uso en la Sección de Análisis (Dual Mode)

En la sección de Análisis (`routers/analysis.py`), la lógica difusa se vuelve central. Las herramientas de análisis soportan dos modos: **Standard** y **Fuzzy**.

La premisa fundamental del recálculo difuso para medir la "fuerza" de la relación entre dos Conceptos (que están conectados a través de un documento común) es **el mínimo de los pesos**.

### La Regla de la Cadena (El eslabón más débil)
Cuando se evalúa la conexión semántica entre el `Concepto A` y el `Concepto B` (que co-ocurren en el documento D), el "peso difuso" combinado es: `min(peso(A-D), peso(D-B))`. En Cypher se expresa como:
```cypher
CASE WHEN r1.weight < r2.weight THEN r1.weight ELSE r2.weight END
```

### Aplicaciones en Herramientas Específicas:

1.  **Chord Diagram (Co-Ocurrencia)**
    *   **Standard:** Cuenta la cantidad de documentos compartidos entre dos conceptos.
    *   **Fuzzy:** Suma los pesos difusos conjuntos (`sum(min(r1, r2))`). Filtra conexiones muy débiles usando un parámetro ajustable de la UI (`min_weight`).

2.  **Community Detection (Louvain via Cypher Projection)**
    *   Utiliza la Graph Data Science (GDS) library.
    *   **Proyección Fuzzy:** Crea un grafo temporal en memoria donde las aristas entre Conceptos tienen un peso igual a la suma de los mínimos (`sum(min(r1, r2))`), permitiendo clústeres basados en conexiones temáticas fuertes y verificadas semánticamente, en lugar de apariciones casuales.

3.  **Semantic Bridges (Bowtie Heuristic)**
    *   Calcula puentes (nodos que conectan con muchos clústeres o conceptos diversos).
    *   **Fuzzy Score:** `Sum(min(r1, r2)) * Diversidad` (número de tipos de nodos únicos con los que conecta).

4.  **Radial Tree (Expansión)**
    *   Ramificación (Level 1 y Level 2) priorizada por la suma difusa del mínimo (`sum(min(r1, r2))`).

5.  **PageRank**
    *   Evalúa la "importancia" global de un concepto en el grafo.
    *   **Fuzzy:** Modifica la proyección GDS para usar la suma difusa del mínimo como peso de la arista dirigida, propagando "influencia" basada en la certeza de la abstracción.

6.  **Fog of War**
    *   Analiza simplemente la **distribución** global de estos pesos (0.0 a 1.0) en todas las aristas, agrupándolos en deciles estadísticos para mostrar una visión de cuánta "incertidumbre" o "arte" existe en el conocimiento cargado.

## Resumen del Flujo
1. **Rubric -> LLM:** Decide el score $w_i \in [0,1]$ basado en una penalización abstracta vs literal.
2. **HITL -> Neo4j:** Almacena el nodo `Concept` y la arista `[EVOKES_CONCEPT {weight: w_i}]`. Si hay conflicto en la inyección manual misma, guarda $\max(w_{nuevo}, w_{existente})$.
3. **Análisis -> GDS/Cypher:** Recalcula el peso derivado entre dos conceptos basados en un doc común usando la regla del mínimo de Zadeh: $w_{A \to B} = \sum_{docs} \min(w_{A \to doc}, w_{doc \to B})$. Utiliza este valor $w_{A \to B}$ para clustering (Louvain), métricas de centralidad (PageRank), y agrupaciones de visualizaciones.
