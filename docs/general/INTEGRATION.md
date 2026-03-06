# Integración Backend ↔ Frontend

Referencia de cómo se conectan los servicios React (Vite) con FastAPI.

---

## URLs base

| Servicio | URL | Timeout |
|----------|-----|---------|
| API principal | `http://localhost:8000` | 30s |
| Explore (Latent Explorer) | `http://localhost:8000/api/explore` | 60s |
| Analysis (Pathfinder) | `http://localhost:8000/analysis` | 120s |

Configurados en `search-app/src/lib/api.ts` como instancias Axios independientes.

---

## Módulos API → Componentes

| Módulo Backend | Router | Componente Frontend principal |
|----------------|--------|-------------------------------|
| `/search` | `search.py` | `SearchPage.tsx` → tabs (GraphFuzzy, Semantic, Visual…) |
| `/ingest` | `ingest.py` | `IngestControlPage.tsx` |
| `/api/enrichment` | `enrichment.py` | `EnrichmentDashboard.tsx` → `OntologicalCleanup.tsx`, `EntityDedup.tsx` |
| `/api/explore` | `explore.py` | `LatentExplorer.tsx` |
| `/analysis` | `analysis.py` | `AnalysisDashboard.tsx` → `PathfinderCard.tsx`, `SerendipityCard.tsx`… |
| `/inbox` | `inbox.py` | `ReviewQueueTab.tsx` |

---

## Flujo de datos típico

```
Usuario  →  React Component
         →  api.ts (Axios)
         →  FastAPI Router
         →  Neo4j / Weaviate / MinIO
         →  FastAPI response
         →  api.ts
         →  Component state (useState / useEffect)
         →  UI re-render
```

Para tareas largas (enriquecimiento, ingesta):

```
React → POST /enrich → FastAPI → Celery enqueue → Redis
                              ← { task_id }
React → GET /tasks/{id}/status (polling)
Celery Worker → LLM / Weaviate / Neo4j
              → task COMPLETED
React → re-fetch data
```

---

## Autenticación

Actualmente sin autenticación (desarrollo local). Para producción, añadir JWT middleware en FastAPI y headers `Authorization: Bearer <token>` en las instancias Axios de `api.ts`.

---

## CORS

Configurado en `backend/app/main.py`:
```python
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], ...)
```
Ajustar `allow_origins` para despliegues en red o producción.

---

## Manejo de errores

Frontend (`api.ts`): los errores de red y HTTP 4xx/5xx se propagan como excepciones Axios. Los componentes deben manejarlos con `try/catch` y mostrar el detalle via `err.response?.data?.detail`.

Backend (`enrichment.py`, etc.): todos los errores devuelven `HTTPException(status_code=500, detail=str(e))` con logging previo.

---

## Variables de entorno relevantes

| Variable | Dónde | Descripción |
|----------|-------|-------------|
| `NEO4J_URI` | backend `.env` | URI de Neo4j (bolt://localhost:7687) |
| `WEAVIATE_URL` | backend `.env` | URL del cluster Weaviate |
| `MINIO_ENDPOINT` | backend `.env` | Endpoint MinIO |
| `CELERY_BROKER_URL` | backend `.env` | Redis URL para Celery |
| `VITE_API_BASE_URL` | search-app `.env` | Opcional: override de la URL base de la API |
