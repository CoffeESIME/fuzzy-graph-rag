# Lógica Difusa en GraphRAG — Guía Técnica Completa

> **Audiencia:** Investigadores, desarrolladores y revisores del sistema.  
> **Propósito:** Documentar el uso formal de la Lógica Difusa (Fuzzy Logic) dentro del sistema GraphRAG, desde la teoría básica hasta su implementación línea a línea.

---

## Índice

1. [¿Qué es la Lógica Difusa?](#1-qué-es-la-lógica-difusa)
2. [Operadores de Zadeh](#2-operadores-de-zadeh)
3. [El Operador Mínimo (Mínimo de Zadeh)](#3-el-operador-mínimo-mínimo-de-zadeh)
4. [Arquitectura Difusa del Sistema](#4-arquitectura-difusa-del-sistema)
5. [Fase 1 — Asignación de Pesos (Rubric LLM)](#5-fase-1--asignación-de-pesos-rubric-llm)
6. [Fase 2 — Almacenamiento en el Grafo (Neo4j)](#6-fase-2--almacenamiento-en-el-grafo-neo4j)
7. [Fase 3 — El Mínimo de Zadeh en el Análisis](#7-fase-3--el-mínimo-de-zadeh-en-el-análisis)
8. [Herramienta por Herramienta](#8-herramienta-por-herramienta)
9. [Peso Incremental Difuso](#9-peso-incremental-difuso)
10. [Tabla Resumen de Fórmulas](#10-tabla-resumen-de-fórmulas)
11. [¿Por qué usar el mínimo de Zadeh?](#11-por-qué-usar-el-mínimo-de-zadeh)
12. [Glosario](#12-glosario)

---

## 1. ¿Qué es la Lógica Difusa?

La **lógica clásica** (booleana) trabaja con verdades absolutas: algo es `true` (1) o `false` (0).

La **lógica difusa** (Zadeh, 1965) extiende esto al intervalo continuo `[0, 1]`, donde un valor puede ser *parcialmente* verdadero. Esto es esencial para modelar conocimiento subjetivo, artístico o interpretativo.

```
Lógica Clásica:  "Este cuadro habla de soledad"  →  true / false
Lógica Difusa:   "Este cuadro habla de soledad"  →  0.65  (probable pero no seguro)
```

En este sistema, cada arista del grafo `(DigitalAsset)-[r]->(Concept)` tiene una propiedad `r.weight ∈ [0.0, 1.0]` que representa **el grado de pertenencia** del concepto en ese documento.

---

## 2. Operadores de Zadeh

Zadeh definió operadores lógicos equivalentes a AND, OR y NOT para operar sobre valores difusos:

| Operación | Fórmula | Equivalencia Clásica |
|-----------|---------|----------------------|
| **Intersección (AND)** | `T(a, b) = min(a, b)` | `a AND b` |
| **Unión (OR)** | `S(a, b) = max(a, b)` | `a OR b` |
| **Complemento (NOT)** | `N(a) = 1 - a` | `NOT a` |

> Este sistema usa exclusivamente el operador de **intersección (mínimo)** para la composición de relaciones a través del grafo.

---

## 3. El Operador Mínimo (Mínimo de Zadeh)

### Definición formal

Dados dos conjuntos difusos `A` y `B`, su **intersección** en un punto `x` es:

```
μ_{A ∩ B}(x) = min(μ_A(x), μ_B(x))
```

### Interpretación intuitiva: "el eslabón más débil"

Si `A` dice que un concepto tiene un grado de pertenencia de `0.8`, y `B` dice que es `0.4`, la **certeza combinada** de que ambas cosas sean ciertas simultáneamente es `min(0.8, 0.4) = 0.4`.

> La información sólo es tan confiable como su eslabón más débil.

### Ejemplo numérico simple

```
Documento D:
  - EVOKES "Melancolía"  con peso 0.7   (conexión interpretativa)
  - DEFINES "Tristeza"   con peso 0.9   (conexión explícita)

¿Cuán fuerte es la conexión implícita "Melancolía ↔ Tristeza" a través de D?
  → min(0.7, 0.9) = 0.7
```

Si hubiera un segundo documento `D2` con:
```
  - EVOKES "Melancolía"  con peso 0.5
  - DEFINES "Tristeza"   con peso 0.6
  Contribución: min(0.5, 0.6) = 0.5
```

El **peso difuso total** entre "Melancolía" y "Tristeza" sería:
```
w(Melancolía, Tristeza) = min(0.7, 0.9) + min(0.5, 0.6)
                        = 0.7 + 0.5 = 1.2
```

Un valor mayor indica una co-ocurrencia fuerte y semánticamente consistente.

---

## 4. Arquitectura Difusa del Sistema

```
┌────────────────────────────────────────────────────────────────┐
│                     FLUJO DE LÓGICA DIFUSA                     │
├──────────────────┬─────────────────┬───────────────────────────┤
│  FASE 1: INGESTA │ FASE 2: GRAFO   │ FASE 3: ANÁLISIS          │
│                  │                 │                           │
│  LLM + Rubric    │  Neo4j Edges    │  Cypher/GDS               │
│  ──────────────  │  ─────────────  │  ─────────────────────    │
│  confidence ∈    │  r.weight = w   │  min(r1.w, r2.w)          │
│  [0.0, 1.0]      │  (o max si ya   │  sum(min) por documento   │
│                  │   existe)       │  → peso proyectado        │
└──────────────────┴─────────────────┴───────────────────────────┘
```

---

## 5. Fase 1 — Asignación de Pesos (Rubric LLM)

**Archivo:** `backend/worker/prompts.py` → `build_specialized_prompt()`

El LLM recibe una rubrica estructurada (`Confidence Scoring Rubric`) que determina cómo asignar el valor difuso `confidence` a cada concepto extraído.

### Escala de calibración

| Rango | Categoría | Descripción | Ejemplo |
|-------|-----------|-------------|---------|
| `1.0` | Realidad dura | Evidencia directa, físicamente observable | `"fotografía de la Torre Eiffel"` → **Location: Torre Eiffel = 1.0** |
| `0.8 – 0.9` | Concepto explícito | Tema abstracto directamente mencionado | `"el texto habla de soledad"` → **Concepto: Soledad = 0.85** |
| `0.5 – 0.7` | Interpretación / metáfora | Conexión poética, tono emocional no explícito | `"lluvia que cae lentamente"` → **Concepto: Melancolía = 0.6** |
| `0.0 – 0.4` | Ruido | Conexión muy débil o especulativa | `"el azul del cielo"` → **Concepto: Esperanza = 0.3** |

### Reglas críticas del sistema de rúbrica

1. **Techo Abstracto:** Conceptos intangibles (emociones, filosofía) **nunca reciben 1.0**. El máximo es `0.9`.

2. **Penalización por Metáfora:** Si la conexión es poética (no literal), el score **debe ser `< 0.7`**.
   ```
   "fuerte como un toro"  →  NO extraer "Toro" con 1.0
                          →  SÍ extraer "Fuerza" con 0.6
   ```

3. **Traducción de metáforas:** El sistema extrae el **atributo semántico**, no el objeto de la metáfora.

### Output del LLM (estructura JSON)

```json
{
  "concepts": [
    {
      "name": "Melancolía",
      "type": "Emotion",
      "domain": "Psychology",
      "relation_type": "EVOKES",
      "confidence": 0.65
    },
    {
      "name": "Ciudad de México",
      "type": "Location",
      "domain": "Geography",
      "relation_type": "DEFINES",
      "confidence": 1.0
    }
  ]
}
```

---

## 6. Fase 2 — Almacenamiento en el Grafo (Neo4j)

**Archivo:** `backend/app/routers/inbox.py` → `promote_inbox_to_graph()`

Cuando el usuario aprueba un item en la bandeja, se ejecuta:

```cypher
MERGE (a)-[r:{rel_type}]->(c)
ON CREATE SET r.weight = $weight
ON MATCH SET
  -- Si la relación ya existe con otro peso, conservamos el MÁXIMO
  r.weight = CASE WHEN $weight > r.weight THEN $weight ELSE r.weight END
```

> **¿Por qué `max` aquí?** En la ingesta manual, si el mismo concepto aparece en dos análisis con pesos distintos, la presencia más confiada "gana". Se conserva la evidencia más fuerte de la relación. Esto contrasta con el `min` en el análisis, donde evaluamos la cadena más débil para propagar certeza a través de documentos intermedios.

### Estructura resultante en Neo4j

```
(Doc_A: DigitalAsset) -[EVOKES {weight: 0.6}]-> (Melancolía: Concept)
(Doc_A: DigitalAsset) -[DEFINES {weight: 0.9}]-> (Tristeza: Concept)
(Doc_B: DigitalAsset) -[EVOKES {weight: 0.5}]-> (Melancolía: Concept)
(Doc_B: DigitalAsset) -[EVOKES {weight: 0.7}]-> (Tristeza: Concept)
```

---

## 7. Fase 3 — El Mínimo de Zadeh en el Análisis

**Archivo:** `backend/app/routers/analysis.py`

Esta es la implementación central del mínimo de Zadeh. La fórmula completa para calcular el **peso difuso derivado** entre dos conceptos `A` y `B` que comparten documentos es:

$$w_{A \leftrightarrow B} = \sum_{\text{docs}} \min\left(w_{A \to doc},\ w_{doc \to B}\right)$$

### Implementación en Cypher

```cypher
-- Patrón de co-ocurrencia:
MATCH (c1:Concept)<-[r1]-(a:DigitalAsset)-[r2]->(c2:Concept)
WHERE id(c1) < id(c2)

-- Aplicación del mínimo de Zadeh y suma por documento:
WITH c1, c2,
     sum(CASE WHEN r1.weight < r2.weight
              THEN r1.weight
              ELSE r2.weight
         END) AS weight
```

> `CASE WHEN r1.weight < r2.weight THEN r1.weight ELSE r2.weight END` es **exactamente `min(r1.weight, r2.weight)`** en SQL/Cypher.

### Ejemplo con los datos del paso 6

```
Calculando w(Melancolía, Tristeza):

  Documento Doc_A:
    r1.weight (Melancolía ← Doc_A) = 0.6
    r2.weight (Doc_A → Tristeza)   = 0.9
    min(0.6, 0.9)                  = 0.6  ✓

  Documento Doc_B:
    r1.weight (Melancolía ← Doc_B) = 0.5
    r2.weight (Doc_B → Tristeza)   = 0.7
    min(0.5, 0.7)                  = 0.5  ✓

  w(Melancolía, Tristeza) = 0.6 + 0.5 = 1.1
```

Este valor `1.1` es el **peso difuso de la arista proyectada** en el grafo en memoria que usa GDS para Louvain y PageRank.

---

## 8. Herramienta por Herramienta

### 8.1 Community Detection — Louvain

**Endpoint:** `POST /analysis/communities?method=fuzzy`  
**Archivos:** `analysis.py` línea 76–90

El grafo GDS se proyecta con aristas cuyo peso es `sum(min(r1, r2))`. El algoritmo Louvain usa estos pesos para crear **comunidades basadas en certeza semántica compartida**, no solo en co-aparición.

```cypher
WITH c1, c2,
     sum(CASE WHEN r1.weight < r2.weight THEN r1.weight ELSE r2.weight END) AS weight
WITH gds.graph.project('conceptCommunities', c1, c2,
  { relationshipProperties: { weight: weight } }, ...)
```

**Retorna:** Clusters de conceptos agrupados por fuerza semántica difusa.

---

### 8.2 PageRank Difuso

**Endpoint:** `POST /analysis/pagerank?method=fuzzy`  
**Archivos:** `analysis.py` línea 1146–1155

PageRank propagará más "influencia" por aristas semánticamente fuertes. Un concepto con muchas co-ocurrencias de certeza alta tendrá mayor score que uno con muchas pero inciertas.

```cypher
WITH c1, c2,
     sum(CASE WHEN r1.weight < r2.weight THEN r1.weight ELSE r2.weight END) AS weight
WITH gds.graph.project('conceptPR', c1, c2,
  { relationshipProperties: { weight: weight } })
```

**Retorna:** Ranking de los 20 conceptos más "centrales" semánticamente (no solo estructuralmente).

---

### 8.3 Chord Diagram — Intersección Difusa por Categoría

**Endpoint:** `POST /analysis/chord?method=fuzzy`  
**Archivos:** `analysis.py` línea 887–897

Mide la co-ocurrencia fuzzy entre **categorías** (Person, Concept, Location, etc.):

```cypher
RETURN l1 as source, l2 as target,
       round(sum(CASE WHEN r1.weight < r2.weight
                      THEN r1.weight ELSE r2.weight END), 2) as weight
```

**Retorna:** Matriz de categorías con pesos difusos. Un valor alto indica conexión semántica fuerte entre categorías, no solo frecuencia.

---

### 8.4 Radial Tree — Expansión Difusa

**Endpoint:** `POST /analysis/radial-tree?method=fuzzy`  
**Archivos:** `analysis.py` línea 984–992

Los vecinos del nodo raíz se priorizan por `sum(min(r1, r2))` en lugar de por conteo de documentos compartidos:

```cypher
WITH root, l1,
     sum(CASE WHEN r1.weight < r2.weight THEN r1.weight ELSE r2.weight END) AS weight
ORDER BY weight DESC LIMIT 8
```

**Retorna:** Árbol donde los conceptos más semánticamente relacionados (no solo más frecuentes) aparecen primero.

---

### 8.5 Heatmap — Fuzzy Jaccard

**Endpoint:** `POST /analysis/heatmap?method=fuzzy`  
**Archivos:** `analysis.py` línea 1344–1373

Esta herramienta implementa el **Coeficiente de Jaccard Difuso**, que es la versión extendida del Jaccard clásico para conjuntos difusos:

$$J_{\text{fuzzy}}(A, B) = \frac{\sum \min(w_A, w_B)}{\sum w_A + \sum w_B - \sum \min(w_A, w_B)}$$

```cypher
-- Intersección difusa (numerador):
RETURN sum(CASE WHEN r1.weight < r2.weight
                THEN r1.weight ELSE r2.weight END) as fuzzy_intersection

-- Unión difusa (denominador):
WITH (sum_w1 + sum_w2 - fuzzy_intersection) as fuzzy_union

-- Jaccard Difuso:
ELSE round(toFloat(fuzzy_intersection) / toFloat(fuzzy_union), 3)
```

**Ejemplo:**

```
Concepto A (Melancolía):  sum de pesos de todas sus aristas = 3.5
Concepto B (Tristeza):    sum de pesos de todas sus aristas = 4.1
Intersección difusa:      sum(min) a través de docs comunes = 1.1

J_fuzzy(A, B) = 1.1 / (3.5 + 4.1 - 1.1) = 1.1 / 6.5 ≈ 0.169
```

**Retorna:** Matriz de calor donde cada celda es la similitud difusa de Jaccard entre dos conceptos.

---

### 8.6 Semantic Bridges — Puentes Difusos

**Endpoint:** `POST /analysis/bridges?method=fuzzy`  
**Archivos:** `analysis.py` línea 188–208

El score de un puente semántico se calcula como:

```
bridge_score = sum(min(r1.weight, r2.weight) para cada vecino) × diversidad_de_tipos
```

En Cypher:
```cypher
WITH bridge, other,
     CASE WHEN r1.weight < r2.weight THEN r1.weight ELSE r2.weight END AS fuzzy_w
WITH bridge, sum(fuzzy_w) AS fuzzy_degree,
             count(distinct labels(other)) AS diversity
WITH bridge, round(fuzzy_degree * diversity, 2) AS score
```

**Retorna:** Conceptos que actúan como "bisagras" semánticas entre múltiples áreas temáticas, ponderados por la certeza de sus conexiones.

---

### 8.7 Serendipity Path — Random Walk Difuso

**Endpoint:** `POST /analysis/serendipity`  
**Archivos:** `analysis.py` línea 486–610

No usa el mínimo de Zadeh directamente, sino el **concepto inverso**: busca conexiones con pesos bajos (latentes, inesperadas):

```cypher
-- Selecciona rutas donde al menos una arista es "débil" (< 0.7)
AND (r1.weight <= 0.7 OR r2.weight <= 0.7 OR r3.weight <= 0.7 OR r4.weight <= 0.7)
```

El score de serendipia también penaliza hubs:
```cypher
rand() * exp(-0.015 * toFloat(mid_degree)) AS serendipity_score
```

**Retorna:** Un camino asociativo de 5 nodos que cruza al menos una conexión "difusa" inesperada.

---

### 8.8 Fog of War — Distribución de Pesos

**Endpoint:** `POST /analysis/fog-of-war`  
**Archivos:** `analysis.py`

No aplica el mínimo, pero analiza directamente la **distribución de todos los pesos difusos** del grafo, agrupándolos en deciles para mostrar cuánta incertidumbre tiene el conocimiento cargado.

**Retorna:** Histograma de pesos, mostrando si el grafo es mayormente "literal" (pesos altos) o "interpretativo" (pesos bajos).

---

## 9. Peso Incremental Difuso

**Archivo:** `backend/worker/tasks.py` → `apply_incremental_fuzzy_weight()` (línea 2939)

Cuando un nuevo `DigitalAsset` se conecta a un nodo que ya fue enriquecido con fuzzy (`fuzzy_applied=True`), el sistema ajusta automáticamente el peso de la nueva arista sin requerir HITL:

### Fórmula de blending

```
new_weight = (base_weight × 0.75) + (cosine_similarity × 0.25)
```

Donde `cosine_similarity` se calcula entre:
- El **vector de embedding de la descripción del nodo** (generada por LLM previo)
- El **vector del nuevo asset** almacenado en Weaviate

### Pipeline completo

```
1. Verificar si el nodo tiene fuzzy_applied=True en Neo4j
2. Si no → retornar base_weight sin cambios
3. Si sí:
   a. Vectorizar la descripción del nodo via LLM Gateway
   b. Obtener el vector del asset desde Weaviate
   c. Calcular cosine_similarity(desc_vector, asset_vector)
   d. new_weight = base_weight * 0.75 + sim * 0.25
   e. Actualizar r.weight en Neo4j
```

### Relaciones protegidas (no se modifica su peso)

```python
protected_relations = ['CREATED_BY', 'DEFINES', 'LOCATED_AT']
```

---

## 10. Tabla Resumen de Fórmulas

| Contexto | Fórmula | Archivo | Línea |
|----------|---------|---------|-------|
| **Asignación inicial de peso** | `w = LLM_confidence ∈ [0, 1]` | `prompts.py` | — |
| **Merge en Neo4j (conflicto)** | `w = max(w_nuevo, w_existente)` | `inbox.py` | — |
| **Peso difuso derivado (base)** | `min(r1.weight, r2.weight)` | `analysis.py` | 82, 897, 989, 1150, 1358 |
| **Peso difuso acumulado** | `sum(min(r1.w, r2.w)) por docs` | `analysis.py` | 82, 897, 989, 1150 |
| **Jaccard Difuso (numerador)** | `∑ min(wA, wB)` | `analysis.py` | 1358 |
| **Jaccard Difuso (denominador)** | `∑wA + ∑wB − ∑min(wA, wB)` | `analysis.py` | 1365 |
| **Jaccard Difuso (índice)** | `fuzzy_intersection / fuzzy_union` | `analysis.py` | 1371 |
| **Bridge Score** | `sum(min(r1,r2)) × diversity` | `analysis.py` | 198 |
| **Peso Incremental** | `base×0.75 + cosine_sim×0.25` | `tasks.py` | 3024 |
| **Serendipity Score** | `rand() × exp(−0.015 × hub_degree)` | `analysis.py` | 523 |

---

## 11. ¿Por qué usar el mínimo de Zadeh?

### Alternativas consideradas

| Operador | Fórmula | Problema en este contexto |
|----------|---------|--------------------------|
| **Producto probabilístico** | `a × b` | Sub-estima relaciones con pesos altos |
| **Media aritmética** | `(a + b) / 2` | No captura el concepto de "eslabón débil" |
| **Mínimo (Zadeh)** | `min(a, b)` | ✅ Conservador — la certeza no puede aumentar en una cadena |
| **Media geométrica** | `√(a × b)` | Alternativa válida, pero menos interpretable |

### Razones para elegir el mínimo de Zadeh

1. **Conservadorismo epistémico:** La certeza de una conexión transitiva no puede ser mayor que la conexión más débil en la cadena. `A→B→C` no puede ser más seguro que el eslabón `A→B`.

2. **Interpretabilidad:** El resultado es directamente legible. `min(0.9, 0.3) = 0.3` se interpreta como "aunque A conecta fuertemente con el documento, el documento conecta débilmente con B, por lo que la conexión A-B es débil".

3. **Axiomáticamente correcto:** Es una t-norma válida (operador de conjunción difusa que satisface conmutatividad, asociatividad, monotonicidad y condiciones de frontera).

4. **Apropiado para dominios artísticos/humanísticos:** En análisis de arte, una conexión temática es tan fuerte como su interpretación más incierta. El mínimo previene la sobre-estimación de relaciones especulativas.

---

## 12. Glosario

| Término | Definición en este sistema |
|---------|---------------------------|
| **Peso difuso** (`r.weight`) | Valor `∈ [0, 1]` en una arista de Neo4j. Representa la certeza/intensidad de la relación. |
| **T-norma** | Operador de conjunción difusa. En este sistema se usa `min`. |
| **Mínimo de Zadeh** | `min(a, b)` — t-norma fundamental de la lógica difusa clásica. |
| **Grado de pertenencia** | El `r.weight` de una arista indica en qué medida un asset "pertenece" al conjunto difuso definido por un concepto. |
| **Proyección GDS** | Grafo en memoria creado por Neo4j Graph Data Science para ejecutar algoritmos (Louvain, PageRank). Los pesos de este grafo son `sum(min(r1, r2))`. |
| **Jaccard Difuso** | Extensión del coeficiente de Jaccard para conjuntos difusos. Usa `min` para la intersección y la fórmula `∩/(∪)` adaptada a pesos. |
| **HITL** | Human-in-the-Loop. El usuario aprueba los conceptos propuestos por el LLM antes de persistirlos. |
| **fuzzy_applied** | Flag booleano en un nodo Neo4j que indica si ya tiene un perfil semántico enriquecido, habilitando el peso incremental automático. |

---

*Generado para el proyecto GraphRAG — Investigación Académica en Fuzzy Logic-based Multimodal Graph RAG.*  
*Leer junto a: [`fuzzy_concept_summary.md`](./fuzzy_concept_summary.md), [`enrichment_summary.md`](./enrichment_summary.md)*
