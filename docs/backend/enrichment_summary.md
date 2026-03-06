# Resumen Técnico — Sección de Enriquecimiento

Tres módulos activos (excluyendo Salud de Música y Arte).

---

## 1. Enriquecimiento Semántico (Pesos Difusos)

**Propósito**: Ajustar el `weight` de las relaciones `(DigitalAsset)-[r]->(Concepto/Persona/etc.)` usando similitud vectorial entre el embedding de la descripción del nodo hub y el embedding del activo en Weaviate.

**Flujo completo**:
1. Filtrar nodos → `GET /api/enrichment/candidates?node_type=Concept&status_filter=UNAPPLIED&limit=50`
2. Encolar enriquecimiento semántico → `POST /api/enrichment/enrich` `{ "node_ids": ["4:abc..."] }` — el Celery worker genera `n.description` vía LLM.
3. Previsualizar pesos → `GET /api/enrichment/{node_id}/preview-weights?semantic_weight=0.3` — vectoriza la descripción del nodo en memoria y calcula similitud coseno contra cada activo en Weaviate.
4. Aplicar pesos → `POST /api/enrichment/{node_id}/apply-weights` `{ "updates": [{"file_hash": "abc", "new_weight": 0.72}] }` — hace UNWIND en Neo4j y marca `n.fuzzy_applied = true`.

**Fórmula de fusión** (`enrichment.py:235`):
```python
# MIN_SIM = 0.15, MAX_SIM = 0.75  (ajustado por usuario)
sim_normalizada = clamp((cosine_sim - 0.15) / (0.75 - 0.15), 0, 1)
blended = (current_weight * (1 - semantic_weight)) + (sim_normalizada * semantic_weight)
```
- `semantic_weight` = slider del usuario (default 0.3)
- Relaciones **protegidas** (peso intacto):
  - Tipos fijos: `CREATED_BY`, `DEFINES`, `LOCATED_AT`
  - Cualquier relación con `current_weight >= 1.0` (verdad absoluta del grafo)

**Query Neo4j de diagnóstico**:
```cypher
// Ver todos los conceptos con/sin pesos difusos aplicados
MATCH (n:Concept)
RETURN n.name, n.fuzzy_applied, n.enrichment_status, n.description IS NOT NULL as has_desc
ORDER BY n.fuzzy_applied DESC
LIMIT 50

// Resetear fuzzy_applied para re-calcular (fuerza re-aparición del botón "Re-calc")
MATCH (n:Concept) WHERE n.fuzzy_applied = true
SET n.fuzzy_applied = false
RETURN count(n) as reset_count

// Ver distribución actual de pesos en relaciones
MATCH ()-[r:EVOKES_CONCEPT]-()
RETURN min(r.weight), avg(r.weight), max(r.weight), count(r)
```

**Filtros de estado disponibles**: `PENDING` · `PROCESSING` · `COMPLETED` · `UNAPPLIED` (completados sin fuzzy) · `FAILED` · `ALL`

---

## 2. Búsqueda Latente (Latent Explorer)

**Propósito**: Descubrir conexiones ontológicas **inexistentes** en el grafo, propagando relaciones entre activos vectorialmente similares. Actúa sobre `DigitalAsset`, no sobre hubs.

**Flujo completo**:
1. Cargar seeds → `GET /api/explore/seeds?node_type=DigitalAsset&limit=40&sort_by=top_connected|random|least_connected&search=texto`
2. Seleccionar un seed y explorar → `GET /api/explore/latent-connections/{node_id}?top_k=5&alpha=0.3`
   - Fetch del vector del seed desde Weaviate (TextSpace/VisualSpace/AudioSpace/MemorySpace).
   - Búsqueda `near_vector` en los 4 espacios y merge global de los top K vecinos.
   - Para cada vecino: propaga las relaciones del seed al vecino (y viceversa) si **no existen ya**.
3. (Opcional) Validar con LLM → `POST /api/explore/validate-connections` — el LLM local filtra conexiones semánticamente inválidas con índices 1-based.
4. Aprobar conexión → `POST /api/explore/approve-connection` `{ "asset_id", "target_concept_id", "relation_type", "proposed_weight", "reasoning" }` → crea `MERGE (s)-[r:RELATION_TYPE]->(c)` en Neo4j con `r.source = 'interactive_latent_explorer'`.

**Fórmula de peso propuesto** (`explore.py:515`):
```python
hub_penalty = exp(-0.015 * concept_degree)  # penaliza hubs muy conectados
prop_weight = (current_weight * (1 - alpha)) + (cosine_sim * alpha)
prop_weight = prop_weight * hub_penalty
# Solo sugerida si prop_weight >= 0.5
```

**Restricción de dimensiones**: el seed **debe** tener vector de 1024 dims (BGE-M3 semántico); imágenes sin texto semántico son rechazadas.

**Query Neo4j de diagnóstico**:
```cypher
// Ver conexiones creadas por el Latent Explorer
MATCH ()-[r]-() WHERE r.source = 'interactive_latent_explorer'
RETURN type(r), r.weight, r.reasoning, r.created_at
ORDER BY r.created_at DESC LIMIT 20

// Assets con menos conexiones (candidatos ideales para explorar)
MATCH (a:DigitalAsset)
OPTIONAL MATCH (a)--(nb)
WITH a, count(nb) as refs
ORDER BY refs ASC LIMIT 20
RETURN a.filename, refs

// Verificar que un seed tiene vector en Weaviate antes de explorar
// (hacerlo desde Python/Weaviate client, no desde Neo4j)
```

**Conexión manual**: desde la UI en cada tarjeta de activo, buscar cualquier `Concept` del grafo y vincular directamente con peso libre `EVOKES_CONCEPT`.

---

## 3. Limpieza Ontológica (Ontological Cleanup)

**Propósito**: Deduplicar y normalizar nodos `Concept` usando el LLM local para detectar sinónimos (merge) y limpiar conceptos que no deberían ser hubs del grafo (demote).

**Flujo completo**:
1. Cargar todos los conceptos → `GET /api/enrichment/concepts` → devuelve todos los `Concept` con `name` y `domain`.
2. Recomendar merges → `POST /api/enrichment/concepts/recommend-merges?strategy=middle|top|bottom|upper-mid|lower-mid|random|high-low|high-mid|mid-low`
   - Selecciona un batch de ~200-250 conceptos según la estrategia de sampleo.
   - Envía al LLM con system prompt estricto, que devuelve `{"merges": [{"hub_name", "concept_indices"}]}` y opcionalmente `demote_to_tags`.
3. Hacer merge → `POST /api/enrichment/concepts/merge` `{ "target_name": "Hub canónico", "target_domain": "Filosofía", "source_names": ["alias1", "alias2"] }` — APOC rewire de todas las relaciones `EVOKES_CONCEPT` y `DETACH DELETE` de las fuentes.
4. Demote → `POST /api/enrichment/concepts/demote` `{ "source_names": ["Concepto a bajar"] }` — mueve el nombre del concept al array `tags[]` de sus activos conectados y elimina el nodo.

**Query Neo4j de diagnóstico**:
```cypher
// Ver concepts más conectados (worth keeping as hubs)
MATCH (c:Concept)<-[r]-(:DigitalAsset)
WITH c, count(r) as degree
ORDER BY degree DESC LIMIT 30
RETURN c.name, c.domain, degree

// Detectar concepts duplicados manualmente (misma raíz)
MATCH (c:Concept)
WITH toLower(c.name) as lname, collect(c.name) as names, count(*) as cnt
WHERE cnt > 1
RETURN names, cnt ORDER BY cnt DESC

// Ver aliases almacenados tras merges previos
MATCH (c:Concept) WHERE size(c.aliases) > 0
RETURN c.name, c.aliases, c.domain LIMIT 20

// Ver qué concepts han sido degradados a tags en activos
MATCH (a:DigitalAsset) WHERE size(coalesce(a.tags, [])) > 0
RETURN a.filename, a.tags LIMIT 20
```

**Estrategias de sampleo** (para iterar sobre todo el corpus):

| Estrategia | Qué selecciona |
|-----------|---------------|
| `top` | Los 250 con más relaciones |
| `bottom` | Los 250 con menos relaciones |
| `middle` | Los 250 del medio (default) |
| `upper-mid` | Cuarto superior |
| `lower-mid` | Cuarto inferior |
| `random` | Skip aleatorio en cada llamada |
| `high-low` | 125 top + 125 bottom |
| `high-mid` | 125 top + 125 mid |
| `mid-low` | 125 mid + 125 bottom |

> [!TIP]
> Para limpiar todo el corpus ejecutar rondas con `top` → `upper-mid` → `middle` → `lower-mid` → `bottom`, luego varias rondas con `random` para capturar los que se repitan en cruces.

> [!IMPORTANT]
> El merge usa APOC (`apoc.do.when`). Si APOC no está disponible en tu instancia Neo4j, el endpoint fallará con un error de procedimiento desconocido.

---

## 4. Dedup de Entidades (Entity Dedup)

**Propósito**: Deduplicar, fusionar, degradar y re-tipar nodos de entidades estructurales del grafo (`Person`, `Project`, `Location`, `Organization`, `Event`, `Device`, `Method`) desde la pestaña **"Dedup Entidades"** en Limpieza Ontológica.

### Endpoints

#### `GET /api/enrichment/entities`
Lista entidades de un tipo, ordenadas por número de conexiones.
```
?node_type=Person|Project|Location|Organization|Event|Device|Method
&search=texto    # filtro substring sobre name/title
&limit=200
```

#### `POST /api/enrichment/entities/merge`
Fusiona N nodos fuente en un hub superviviente usando Cypher puro (sin APOC).
```json
{
  "node_type": "Person",
  "target_name": "ByteByteGo",
  "source_ids": ["4:uuid:11", "4:uuid:22"],
  "keep_id":   "4:uuid:33"
}
```
Flujo: fetch relaciones del source → `MERGE` en hub → `DETACH DELETE` source. Compatible con merge cruzado de tipos (el `node_type` solo valida la whitelist).

#### `POST /api/enrichment/entities/demote`
Convierte entidades en tags de sus `DigitalAsset` conectados y las elimina.
```json
{ "node_type": "Person", "source_ids": ["4:uuid:11"] }
```
Cypher interno: `SET a.tags = a.tags + [e.name]` → `DETACH DELETE e`.

#### `POST /api/enrichment/entities/retype`
Cambia la etiqueta Neo4j de un nodo (ej. `Person` → `Organization`). Conserva todas sus relaciones.
```json
{ "node_id": "4:uuid:44", "from_type": "Person", "to_type": "Organization" }
```
Cypher: `MATCH (n:Person) WHERE elementId(n) = $id REMOVE n:Person SET n:Organization`.
Solo permite tipos de la whitelist. Usa Cypher interpolado con guarda de whitelist — no hay riesgo de inyección.

#### `GET /api/enrichment/entities/relation-types`
Devuelve todos los tipos de relación existentes en el grafo (para referencias y UI futura).
```json
{ "relation_types": ["CREATED_BY", "EVOKES_CONCEPT", ...], "count": 12 }
```

### Queries Neo4j de diagnóstico
```cypher
// Ver entidades por tipo con su grado de conexión
MATCH (n:Person)
OPTIONAL MATCH (n)--(nb)
RETURN coalesce(n.name, n.title) as nombre, count(distinct nb) as conexiones
ORDER BY conexiones DESC LIMIT 30

// Entidades posiblemente duplicadas (nombre similar)
MATCH (n:Person)
WITH toLower(coalesce(n.name,'')) as lname, collect(coalesce(n.name,'')) as names, count(*) as cnt
WHERE cnt > 1
RETURN names, cnt ORDER BY cnt DESC

// Ver tags generados por demotes previos
MATCH (a:DigitalAsset) WHERE size(coalesce(a.tags,[])) > 0
RETURN a.filename, a.tags LIMIT 20

// Búsqueda cross-type: buscar cualquier entidad por nombre
MATCH (n)
WHERE (n:Person OR n:Project OR n:Location OR n:Organization OR n:Event OR n:Device OR n:Method)
  AND toLower(coalesce(n.name,'')) CONTAINS toLower('bytebytego')
OPTIONAL MATCH (n)-[r]-(a:DigitalAsset)
RETURN labels(n)[0] as tipo, n.name, count(a) as activos
ORDER BY activos DESC
```

### UI en el frontend (4 pestañas en "Dedup Entidades")

| Pestaña | Acción | Endpoint |
|---------|--------|----------|
| **Fusionar Duplicados** | Multi-select mismo tipo → hub con crown | `POST /entities/merge` |
| **Fusión Cruzada** | Origen (tipo A) + destino (tipo B) + tipo final | `POST /entities/merge` + `POST /entities/retype` |
| **Degradar a Tag** | Selección múltiple → convierte en tag de activos | `POST /entities/demote` |
| **Cambiar Tipo** | Un nodo → nueva etiqueta Neo4j | `POST /entities/retype` |
