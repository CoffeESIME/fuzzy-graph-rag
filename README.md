# GraphRAG Multimodal v2

Sistema de **Graph RAG multimodal** con grafo de conocimiento difuso, búsqueda semántica multimodo, herramientas de análisis avanzadas, y procesamiento distribuido con Celery.

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│              FRONTEND (React + Vite · :5173)                │
│  ┌──────────┐  ┌─────────────┐  ┌────────────────────────┐ │
│  │ Search   │  │ Ingest &    │  │ Analysis Dashboard     │ │
│  │ 6 tabs   │  │  Review 5t  │  │ 11 herramientas GDS    │ │
│  └──────────┘  └─────────────┘  └────────────────────────┘ │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP/REST
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   BACKEND (FastAPI · :8000)                  │
│  Routers: ingest, tasks, search, analysis, inbox,           │
│           graph, sidecar, lyrics                            │
└──┬──────────┬──────────┬──────────┬──────────┬──────────────┘
   │          │          │          │          │
   ▼          ▼          ▼          ▼          ▼
┌───────┐ ┌───────┐ ┌───────┐ ┌──────────┐ ┌──────────────┐
│Postgr.│ │ MinIO │ │ Redis │ │ Weaviate │ │ Neo4j + GDS  │
│(Meta) │ │(Blob) │ │(Queue)│ │(Vectors) │ │  (Graph)     │
└───────┘ └───────┘ └───┬───┘ └──────────┘ └──────────────┘
                        │
                        ▼
                 ┌──────────────┐     ┌──────────────────┐
                 │    Celery    │────►│  LLM Gateway     │
                 │  (Workers)   │     │(Ollama/Cloud API)│
                 └──────────────┘     └──────────────────┘
```

## 📁 Estructura del Proyecto

```
graphrag/
├── backend/                        # FastAPI Server
│   ├── app/
│   │   ├── models/                # SQLModel entities
│   │   ├── routers/
│   │   │   ├── __init__.py        # Ingest endpoints (upload, health)
│   │   │   ├── analysis.py        # 11 analysis tools (GDS + Cypher)
│   │   │   ├── search.py          # 5 search modes (vector, visual, graph)
│   │   │   ├── graph.py           # Graph node CRUD
│   │   │   ├── inbox.py           # Inbox & review queue
│   │   │   ├── tasks.py           # Task management & control
│   │   │   ├── sidecar.py         # Sidecar metadata editor
│   │   │   └── lyrics.py          # Lyrics lookup
│   │   ├── schemas/               # Pydantic schemas
│   │   └── services/              # Business logic
│   ├── config/                    # Settings & .env
│   ├── shared/                    # DB clients (Neo4j, MinIO, Weaviate, Postgres)
│   ├── worker/
│   │   ├── celery_app.py          # Celery config
│   │   ├── tasks.py               # All async task definitions (106KB)
│   │   ├── prompts.py             # LLM prompt templates
│   │   └── utils.py               # Shared worker utilities
│   ├── scripts/                   # DB migrations, backfill, enrichment
│   └── pyproject.toml
│
├── search-app/                     # React Frontend (Vite)
│   └── src/
│       ├── App.tsx                # Routing: /, /search, /ingest, /analysis/*
│       └── components/
│           ├── HomePage.tsx        # Landing page
│           ├── search/            # 6 search tabs + visualizers
│           ├── analysis/          # 13 analysis card components
│           └── ingest/            # 5 ingest/review tabs
│
├── frontend/                       # Streamlit Admin Panel (Legacy)
├── graph-rag/                      # Docker Compose (infrastructure)
│   └── docker-compose.yml
│
├── ARCHITECTURE.md                 # System design (este archivo)
├── USAGE_GUIDE.md                 # User manual
├── QUICK_REFERENCE.md             # Cheat sheet
└── README.md                      # This file
```

## 🚀 Quick Start

### 1. Infraestructura (Docker)

```bash
cd graph-rag
docker-compose up -d
```

| Servicio   | Puerto    | Console              |
|------------|-----------|----------------------|
| PostgreSQL | `5432`    | —                    |
| Redis      | `6379`    | —                    |
| MinIO      | `9000`    | `localhost:9001`     |
| Weaviate   | `8080`    | —                    |
| Neo4j      | `7687`    | `localhost:7474`     |
| MinIO API  | `9005`    | Presigned URLs       |

### 2. Backend (FastAPI)

```bash
cd backend
poetry install
poetry run uvicorn app:app --reload --port 8000
```

API docs: `http://localhost:8000/docs`

### 3. Worker (Celery)

```bash
cd backend
poetry run celery -A worker.celery_app worker --loglevel=info
```

### 4. Frontend (React + Vite)

```bash
cd search-app
npm install
npm run dev
```

App: `http://localhost:5173`

## 🔍 Módulo de Búsqueda (6 tabs)

| Tab | Endpoint | Descripción |
|-----|----------|-------------|
| **Semántica** | `POST /search/vectors` | Búsqueda híbrida BM25 + BGE-M3 vector. 4 espacios: TextSpace, VisualSpace, AudioSpace, MemorySpace. Soporta tag filters y alpha tuning. |
| **Visual SigLIP** | `POST /search/visual-siglip` | Búsqueda por imagen. Sube una foto y encuentra contenido visualmente similar (embeddings SigLIP 1152d). |
| **Multimodal** | `POST /search/hybrid-visual` | Fusión imagen + texto. Split view con resultados de texto, visuales y fusionados (RRF). Alpha controla el peso imagen vs texto. |
| **Grafo Crisp** | `POST /search/graph-crisp` | Traversal de Neo4j con umbral alpha-cut. Busca conceptos, personas, lugares y eventos. Visualiza topología con React Flow / D3. |
| **Grafo Fuzzy** | `POST /search/graph-fuzzy` | Vector-first + graph expansion. Busca assets similares en Weaviate, luego expande vía Neo4j para descubrir vecinos semánticos. |
| **MediaPreview** | — | Componente inline que renderiza imágenes, reproduce audio/video, y muestra descargas via presigned URLs de MinIO. |

## 📊 Módulo de Análisis (11 herramientas)

| Ruta | Herramienta | Algoritmo | Visualización |
|------|-------------|-----------|---------------|
| `/analysis/communities` | **Comunidades** | Louvain Modularity (GDS) | Nivo Circle Packing |
| `/analysis/bridges` | **Puentes Semánticos** | Heurística de diversidad (Bowtie) | Cards + badges |
| `/analysis/serendipity` | **Camino de Serendipia** | Fuzzy Random Walk | Metro-line + MediaPreview |
| `/analysis/fog-of-war` | **Fog of War** | Distribución grado vs label | Recharts bars |
| `/analysis/heatmap` | **Heatmap Jaccard** | Jaccard co-occurrence matrix | Nivo Heatmap |
| `/analysis/chord` | **Diagrama de Cuerdas** | Co-ocurrencia categorías vía Assets | Nivo Chord |
| `/analysis/radial-tree` | **Árbol Radial** | Co-occurrence expansion (BFS) | Nivo Radial Tree |
| `/analysis/abstract-concepts` | **Conceptos Abstractos** | Degree vs avg weight scatter | Nivo Scatter |
| `/analysis/pagerank` | **PageRank** | GDS PageRank | Cards + ranking |
| `/analysis/orphans` | **Nodos Huérfanos** | Grado = 0 | Cards |
| `/analysis/weight-distribution` | **Distribución de Pesos** | Histograma pesos [0-1] | Recharts |

Cada herramienta incluye:
- Panel explicativo lateral con narrativa dinámica
- Visualización interactiva con tema oscuro
- Botón de reload y estados de loading/error/empty

## 📥 Módulo de Ingesta (5 tabs)

| Tab | Descripción |
|-----|-------------|
| **Ingest Grouping** | Carga y agrupación de archivos. Operaciones: Standard (1:1), Merge OCR (N:1). Vectores: visual, audio, text, memory. |
| **Task Control** | Dashboard de tareas Celery. Estados: ON_HOLD → PENDING → PROCESSING → COMPLETED/FAILED. Activación selectiva, retry, cancel. |
| **Review Queue** | Cola de revisión de inbox: aprobación de personas, conceptos, y relaciones antes de ingresar al grafo. Visualización de sidecar metadata. |
| **Graph Generator** | Editor visual de nodos y conexiones. Crea Concepts, Persons, Locations, Events con propiedades y relaciones ponderadas. |
| **Lyrics** | Búsqueda y asociación de letras de canciones a audio assets. |

## 🎨 Tipos de Vectores

| Vector Type | Modelo | Espacio | Uso |
|-------------|--------|---------|-----|
| `visual_siglip` | SigLIP | VisualSpace | Forma, estética, objetos |
| `visual_semantic` | BGE-M3 | VisualSpace | Conceptos, significado (memes, arte) |
| `text_ocr` | Qwen3-VL | VisualSpace → TextSpace | Extracción de texto de imágenes |
| `audio_clap` | CLAP | AudioSpace | Búsqueda por sonido/música |
| `audio_transcript` | Whisper | AudioSpace | Transcripción de voz/letra |
| `text_chunk` | BGE-M3 | TextSpace | Documentos, artículos |
| `text_summary` | LLM | — | Resumen textual |
| `user_memory` | BGE-M3 | MemorySpace | Notas del usuario, contexto |

## 🔄 Pipeline de Procesamiento

```
    Upload (MinIO)
         │
         ▼
    ON_HOLD (Staging / Review)
         │  User triggers
         ▼
    PENDING (Redis Queue)
         │  Celery Worker takes
         ▼
    PROCESSING
    ├── text_summary    → LLM genera resumen
    ├── text_chunk      → Chunking + BGE-M3 embedding → Weaviate
    ├── visual_siglip   → SigLIP embedding → Weaviate
    ├── visual_semantic  → OCR + BGE-M3 → Weaviate
    ├── audio_clap      → CLAP embedding → Weaviate
    ├── audio_transcript → Whisper → BGE-M3 → Weaviate
    └── graph_sync      → Neo4j (Concepts, Persons, Relations)
         │
         ▼
    COMPLETED ← MinIO presigned URLs para preview
```

## 🧠 Modelo de Grafo (Neo4j)

```
(:DigitalAsset) -[:EVOKES_CONCEPT {weight, reasoning}]-> (:Concept)
(:DigitalAsset) -[:MENTIONS_PERSON {weight}]-> (:Person)
(:Concept)      -[:RELATED_TO {weight}]-> (:Concept)
```

- **Pesos difusos** [0–1]: El LLM asigna un grado de membresía fuzzy a cada relación
- **GDS Plugin**: Louvain, PageRank, proyecciones virtuales via aggregation functions
- **Co-ocurrencia**: Dos conceptos están vinculados si al menos un DigitalAsset los menciona a ambos

## ⚙️ Variables de Entorno

Crear `backend/.env.development`:

```env
POSTGRES_USER=graphrag
POSTGRES_PASSWORD=yourpassword
POSTGRES_SERVER=localhost
POSTGRES_PORT=5432
POSTGRES_DB=graphrag
REDIS_HOST=localhost
REDIS_PORT=6379
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=graphrag
WEAVIATE_URL=localhost
WEAVIATE_PORT=8080
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=yourpassword
LLM_GATEWAY_URL=http://localhost:11434
```

## 🧠 Enriquecimiento & Limpieza Ontológica

| Módulo | Descripción |
|--------|-------------|
| **Pesos Difusos** | Ajusta `weight` en relaciones usando similitud vectorial (BGE-M3 ↔ Weaviate). Slider de alpha, protección de pesos crisp (≥ 1.0). |
| **Navegador Latente** | Descubre conexiones inexistentes propagando relaciones entre assets vectorialmente similares. Validación opcional con LLM local. |
| **Limpieza Ontológica** | Dedup de Conceptos via LLM (merge, demote a tag). 9 estrategias de sampleo para iterar todo el corpus. |
| **Dedup de Entidades** | Fusionar, degradar, re-tipar nodos de tipo Person/Project/Location/Organization. 4 operaciones, Cypher puro (sin APOC). |

## 📚 Documentación

Ver carpeta [`docs/`](docs/README.md) para el índice completo.

| Sección | Documentos clave |
|---------|-----------------|
| **General** | [Arquitectura](docs/general/ARCHITECTURE.md) · [Diagramas Mermaid](docs/general/diagrams.md) · [Integración Backend↔Frontend](docs/general/INTEGRATION.md) · [Guía de uso](docs/general/USAGE_GUIDE.md) |
| **Backend** | [Enriquecimiento API](docs/backend/enrichment_summary.md) · [Guía Celery](docs/backend/CELERY_GUIDE.md) · [Troubleshooting](docs/backend/TROUBLESHOOTING.md) |
| **Frontend** | [File Preview](docs/frontend/FILE_PREVIEW_GUIDE.md) |

API interactiva (con servidor activo): [`http://localhost:8000/docs`](http://localhost:8000/docs)

## Licencia

Este proyecto es de código abierto y está licenciado bajo la **GNU AGPL v3**. Ver el archivo [`LICENSE`](LICENSE) para más detalles. Al ser un proyecto de investigación académica, se requiere que cualquier uso en un servicio de red (SaaS) publique sus modificaciones bajo la misma licencia.

## Cómo citar este proyecto (Citation)

Si utilizas **hechoconcafeina** o la arquitectura de Graph RAG con lógica difusa en tu investigación, por favor cita nuestro trabajo:

```bibtex
@misc{hechoconcafeina2026,
  author    = {Romero Hernandez, Fabian},
  title     = {hechoconcafeina: A Fuzzy Logic-based Multimodal Graph RAG System},
  year      = {2026},
  publisher = {GitHub / Zenodo},
  journal   = {GitHub repository},
  howpublished = {\url{https://github.com/CoffeESIME/fuzzy-graph-rag}},
  doi       = {[DOI-generado-por-Zenodo-proximamente]}
}
```
