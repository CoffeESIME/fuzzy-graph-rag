# Arquitectura del Sistema — GraphRAG Multimodal v2

## Visión General

GraphRAG es un sistema de **Retrieval-Augmented Generation** multimodal que combina:

- **Grafo de conocimiento difuso** (Neo4j + GDS) con pesos de membresía [0–1]
- **Búsqueda vectorial multimodo** (Weaviate) con 4 espacios: texto, visual, audio, memoria
- **Procesamiento distribuido** (Celery + Redis) con pipeline de LLM
- **Frontend React** con 3 módulos: búsqueda (6 tabs), análisis (11 herramientas), ingesta (5 tabs)

---

## Backend (FastAPI · `:8000`)

### Routers

| Router | Archivo | Prefijo | Descripción |
|--------|---------|---------|-------------|
| **Ingest** | `__init__.py` | `/ingest` | Upload de archivos a MinIO + creación de DigitalAsset en Postgres |
| **Tasks** | `tasks.py` | `/tasks` | CRUD de tareas Celery: on-hold, start, status, retry, cancel |
| **Search** | `search.py` | `/search` | 5 modos de búsqueda (vectorial, visual, multimodal, grafo crisp/fuzzy) |
| **Analysis** | `analysis.py` | `/analysis` | 11 herramientas de análisis con Neo4j GDS |
| **Inbox** | `inbox.py` | `/inbox` | Review queue: aprobar/rechazar conceptos y personas antes del grafo |
| **Graph** | `graph.py` | `/graph` | CRUD manual de nodos y conexiones en Neo4j |
| **Sidecar** | `sidecar.py` | `/sidecar` | Editor de sidecar metadata JSON por asset |
| **Lyrics** | `lyrics.py` | `/lyrics` | Lookup de letras para audio assets |

### Search Endpoints (search.py)

```
POST /search/vectors        → Hybrid BM25 + BGE-M3 vector (4 espacios)
POST /search/visual-siglip  → Visual SigLIP embeddings (1152d)
POST /search/hybrid-visual  → Multimodal fusion (imagen + texto, RRF)
POST /search/graph-crisp    → Neo4j traversal con alpha-cut threshold
POST /search/graph-fuzzy    → Vector-first + graph expansion (descubrimiento)
```

Todos los endpoints de búsqueda enriquecen resultados con **presigned URLs de MinIO** para preview inline (imágenes, audio, video).

### Analysis Endpoints (analysis.py)

```
POST /analysis/communities         → Louvain Modularity (GDS cypher projection)
POST /analysis/bridges             → Puentes semánticos (heurística diversidad)
POST /analysis/serendipity         → Fuzzy random walk con presigned URLs
POST /analysis/fog-of-war          → Distribución de grado por label
POST /analysis/heatmap             → Jaccard co-occurrence matrix
POST /analysis/chord               → Co-ocurrencia categorías vía DigitalAssets
POST /analysis/radial-tree         → Co-occurrence BFS expansion tree
POST /analysis/abstract-concepts   → Degree vs avg weight scatter plot
POST /analysis/pagerank            → GDS PageRank top nodos
POST /analysis/orphans             → Nodos sin conexiones (degree = 0)
POST /analysis/weight-distribution → Histograma de pesos de relaciones [0-1]
```

### Helpers compartidos

- **`_safe_gds_project()`**: Drop + project con retry para race conditions de GDS
- **`_safe_gds_drop()`**: Drop silencioso de grafos en memoria GDS
- **`_resolve_minio_url()`**: Búsqueda por file_hash prefix en MinIO + presigned URL
- **`_enrich_with_minio()`**: Enriquece search results con download_url + minio_path

---

## Worker (Celery)

### Pipeline de Procesamiento

```
DigitalAsset creado en Postgres + MinIO
    │
    ▼ (User triggers via /tasks/start)
┌────────────────────────────────────────┐
│ Celery Worker                          │
│                                        │
│  text_summary_task                     │
│    └─ LLM genera resumen del asset     │
│                                        │
│  process_text_chunk_task               │
│    └─ Chunking + BGE-M3 → Weaviate    │
│                                        │
│  process_visual_siglip_task            │
│    └─ SigLIP embedding → Weaviate     │
│                                        │
│  process_visual_semantic_task          │
│    └─ OCR (Qwen3-VL) + BGE-M3         │
│                                        │
│  process_audio_clap_task               │
│    └─ CLAP embedding → Weaviate       │
│                                        │
│  process_audio_transcript_task         │
│    └─ Whisper → BGE-M3 → Weaviate     │
│                                        │
│  sync_to_neo4j (post-LLM)             │
│    └─ Crear Concepts, Persons,         │
│       Locations, Events + relations    │
└────────────────────────────────────────┘
```

### LLM Gateway

El worker se comunica con modelos LLM vía un gateway configurable:

| Tarea | Modelo Default | Task Type |
|-------|---------------|-----------|
| Resumen de texto | `llama3.2` | `chat` |
| OCR de imágenes | `qwen3-vl:8b` | `vision` |
| Extracción de conceptos | `llama3.2` | `chat` |
| Transcripción audio | `whisper` | `transcribe` |

---

## Frontend (React + Vite · `:5173`)

### Routing

```
/                   → HomePage (landing)
/search             → SearchPage (6 tabs de búsqueda)
/ingest             → IngestControlPage (5 tabs de ingesta/review)
/analysis           → AnalysisDashboard (grid de herramientas)
/analysis/:tool     → Card individual de cada herramienta
```

### Módulo de Búsqueda (`search/`)

| Componente | Descripción |
|------------|-------------|
| `SemanticTextTab` | Búsqueda vectorial con filtros, alpha slider, resultados por espacio |
| `VisualSigLIPTab` | Upload de imagen, búsqueda visual |
| `HybridVisualTab` | Split view: texto vs visual vs fusión RRF |
| `GraphCrispTab` | Grafo interactivo Neo4j con alpha-cut + panel de nodo |
| `GraphFuzzyTab` | Vector-first expansion con 3D/2D graph visualizers |
| `MediaPreview` | Renderiza imágenes, audio, video inline via presigned URLs |
| `TextPreviewModal` | Modal para vista previa de texto completo |
| `SearchResults` | Lista de resultados con scores, properties, download |
| `GraphVisualizer*` | 3 visualizadores: Three.js 3D, D3 2D, React Flow |

### Módulo de Análisis (`analysis/`)

| Componente | Librería de Visualización |
|------------|---------------------------|
| `CommunityAnalysisCard` | `@nivo/circle-packing` — Circle Packing jerárquico |
| `BridgeAnalysisCard` | Cards con badges y métricas |
| `SerendipityCard` | Metro-line custom + `MediaPreview` integrado |
| `FogOfWarCard` | `recharts` — Bar chart |
| `HeatmapAnalysisCard` | `@nivo/heatmap` |
| `ChordAnalysisCard` | `@nivo/chord` |
| `RadialTreeCard` | `@nivo/radial-bar` |
| `AbstractConceptsCard` | `@nivo/scatterplot` |
| `PageRankCard` | Cards con ranking y badges |
| `OrphansCard` | Cards simples |
| `WeightDistributionCard` | `recharts` — Bar chart |

### Módulo de Ingesta (`ingest/`)

| Componente | Descripción |
|------------|-------------|
| `IngestGroupingTab` | Drag & drop archivos, crear grupos, seleccionar vectores |
| `TaskControlTab` | Dashboard de tareas Celery con progreso en tiempo real |
| `ReviewQueueTab` | Aprobación de entidades extraídas por LLM (conceptos, personas) |
| `GraphGeneratorTab` | Editor visual para crear nodos/conexiones manualmente |

---

## Modelo de Datos

### Neo4j (Grafo de Conocimiento Difuso)

```cypher
(:DigitalAsset {filename, file_hash, mime_type, inbox_id, created_at})
  -[:EVOKES_CONCEPT {weight: 0.0-1.0, reasoning: "..."}]->
(:Concept {name})

(:DigitalAsset)
  -[:MENTIONS_PERSON {weight: 0.0-1.0}]->
(:Person {name})

(:Concept) -[:RELATED_TO {weight}]-> (:Concept)
```

**Propiedades clave de DigitalAsset en Neo4j**: `file_hash`, `filename`, `mime_type`, `inbox_id`, `created_at`, `last_seen`.

> ⚠️ `download_url`, `minio_path`, y `text` **NO** son propiedades de Neo4j — se resuelven en runtime via MinIO.

### Weaviate (4 Espacios Vectoriales)

| Collection | Named Vectors | Modelo |
|------------|---------------|--------|
| `TextSpace` | `default` (BGE-M3) | Texto chunked |
| `VisualSpace` | `semantic` (BGE-M3), `visual` (SigLIP) | Imágenes |
| `AudioSpace` | `transcript_semantic` (BGE-M3), `audio_clap` (CLAP) | Audio |
| `MemorySpace` | `default` (BGE-M3) | Notas del usuario |

### PostgreSQL (Metadata)

- `digital_assets`: Registro maestro de archivos
- `vector_statuses`: Estado de vectorización por tipo
- `task_metadata`: Configuración de tareas (prompts, opciones)
- `sidecar_data`: JSON metadata editables por asset

### MinIO (Almacenamiento de Objetos)

```
graphrag/
├── raw/images/       {hash8}_filename.ext
├── raw/audio/        {hash8}_filename.ext
├── raw/videos/       {hash8}_filename.ext
├── raw/documents/    {hash8}_filename.ext
└── master_records/texts/  {full_hash}.json
```

Las **presigned URLs** se generan en runtime con `generate_presigned_url()` y se reescriben a `localhost:9005` para acceso desde el navegador.

---

## Dependencias npm (search-app)

| Paquete | Uso |
|---------|-----|
| `react`, `react-dom` | Core UI |
| `react-router-dom` | Routing SPA |
| `axios` | HTTP client |
| `recharts` | Bar charts, histogramas |
| `@nivo/circle-packing` | Circle Packing (Comunidades) |
| `@nivo/heatmap` | Heatmap (Jaccard) |
| `@nivo/chord` | Chord diagram (Co-ocurrencia) |
| `@nivo/radial-bar` | Radial tree |
| `@nivo/scatterplot` | Scatter plot (Abstractos) |
| `lucide-react` | Iconos |
| `three`, `@react-three/fiber` | 3D graph visualizer |
| `reactflow` | React Flow graph visualizer |
