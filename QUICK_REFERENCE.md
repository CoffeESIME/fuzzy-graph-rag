# Quick Reference — GraphRAG Multimodal v2

## 🚀 Servicios

| Servicio | Puerto | Comando |
|----------|--------|---------|
| **Infraestructura** | — | `cd graph-rag && docker-compose up -d` |
| **Backend** | `:8000` | `cd backend && poetry run uvicorn app:app --reload` |
| **Worker** | — | `cd backend && poetry run celery -A worker.celery_app worker --loglevel=info` |
| **Frontend** | `:5173` | `cd search-app && npm run dev` |
| PostgreSQL | `:5432` | Docker |
| Redis | `:6379` | Docker |
| MinIO | `:9000` / `:9001` (console) / `:9005` (presigned) | Docker |
| Weaviate | `:8080` | Docker |
| Neo4j | `:7687` / `:7474` (browser) | Docker |

## 🔍 Search Endpoints

```bash
# Búsqueda semántica híbrida
curl -X POST localhost:8000/search/vectors \
  -H "Content-Type: application/json" \
  -d '{"query": "memes de gatos", "alpha": 0.5, "limit": 10}'

# Búsqueda visual SigLIP
curl -X POST localhost:8000/search/visual-siglip \
  -d '{"image": "<base64>", "limit": 10}'

# Multimodal (imagen + texto)
curl -X POST localhost:8000/search/hybrid-visual \
  -d '{"image": "<b64>", "text_context": "gato durmiendo", "alpha": 0.5}'

# Grafo crisp (alpha-cut)
curl -X POST localhost:8000/search/graph-crisp \
  -d '{"query": "melancolía", "alpha_cut": 0.7, "limit": 20}'

# Grafo fuzzy (vector-first)
curl -X POST localhost:8000/search/graph-fuzzy \
  -d '{"query": "gothic metal", "alpha_cut": 0.5, "limit": 20}'
```

## 📊 Analysis Endpoints

```bash
# Todos son POST sin body
curl -X POST localhost:8000/analysis/communities
curl -X POST localhost:8000/analysis/bridges
curl -X POST localhost:8000/analysis/serendipity
curl -X POST localhost:8000/analysis/fog-of-war
curl -X POST localhost:8000/analysis/heatmap
curl -X POST localhost:8000/analysis/chord
curl -X POST localhost:8000/analysis/orphans
curl -X POST localhost:8000/analysis/pagerank
curl -X POST localhost:8000/analysis/weight-distribution
curl -X POST localhost:8000/analysis/abstract-concepts

# Radial tree (con nodo raíz opcional)
curl -X POST localhost:8000/analysis/radial-tree \
  -d '{"root_node_name": "melancolía"}'
```

## 📥 Ingest Endpoint

```bash
# Upload con configuración
curl -X POST "localhost:8000/ingest/upload" \
  -F "files=@foto.jpg" \
  -F 'upload_map=[{
    "file_indices": [0],
    "operation": "standard",
    "vector_types": ["visual_siglip", "text_summary"],
    "discard_original": false
  }]'
```

## 🎯 Tasks Endpoint

```bash
curl localhost:8000/tasks/on-hold           # Listar staging
curl -X POST localhost:8000/tasks/start \
  -d '{"task_ids": ["uuid1", "uuid2"]}'     # Activar
curl localhost:8000/tasks/status/{task_id}   # Estado
```

## 🎨 Vector Types

| Type | Modelo | Espacio Weaviate | Named Vector |
|------|--------|-----------------|--------------|
| `visual_siglip` | SigLIP | VisualSpace | `visual` |
| `visual_semantic` | BGE-M3 via OCR | VisualSpace | `semantic` |
| `text_chunk` | BGE-M3 | TextSpace | `default` |
| `text_summary` | LLM | — | — |
| `audio_clap` | CLAP | AudioSpace | `audio_clap` |
| `audio_transcript` | Whisper+BGE | AudioSpace | `transcript_semantic` |
| `user_memory` | BGE-M3 | MemorySpace | `default` |

## 🧠 Neo4j Labels & Relations

```
Nodes:  :Concept  :Person  :Location  :Event  :DigitalAsset
Rels:   EVOKES_CONCEPT {weight, reasoning}
        MENTIONS_PERSON {weight}
        RELATED_TO {weight}
```

**DigitalAsset properties en Neo4j**: `file_hash`, `filename`, `mime_type`, `inbox_id`, `created_at`, `last_seen`

## 📁 MinIO Folder Structure

```
graphrag/
├── raw/images/          {hash8}_filename.ext
├── raw/audio/           {hash8}_filename.ext
├── raw/videos/          {hash8}_filename.ext
├── raw/documents/       {hash8}_filename.ext
└── master_records/texts/ {full_hash}.json
```

## 🔧 Frontend Routes

| Ruta | Componente |
|------|------------|
| `/` | HomePage |
| `/search` | SearchPage (6 tabs) |
| `/ingest` | IngestControlPage (5 tabs) |
| `/analysis` | AnalysisDashboard |
| `/analysis/communities` | CommunityAnalysisCard |
| `/analysis/bridges` | BridgeAnalysisCard |
| `/analysis/serendipity` | SerendipityCard |
| `/analysis/fog-of-war` | FogOfWarCard |
| `/analysis/heatmap` | HeatmapAnalysisCard |
| `/analysis/chord` | ChordAnalysisCard |
| `/analysis/radial-tree` | RadialTreeCard |
| `/analysis/abstract-concepts` | AbstractConceptsCard |
| `/analysis/pagerank` | PageRankCard |
| `/analysis/orphans` | OrphansCard |
| `/analysis/weight-distribution` | WeightDistributionCard |

## 🐛 Quick Debug

```bash
# Health check
curl localhost:8000/

# Neo4j directo
cypher-shell -u neo4j -p pass "MATCH (n) RETURN labels(n), count(n)"

# MinIO listar
aws s3 ls s3://graphrag/ --endpoint-url http://localhost:9005

# Weaviate schema
curl localhost:8080/v2/schema

# Redis tasks
redis-cli -h localhost keys "celery*"
```
