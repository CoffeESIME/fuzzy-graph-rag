# GraphRAG Multimodal - Quick Reference

## 🎯 Vector Types Reference

| Vector Type | Espacio | Uso Principal | Named Vector (Weaviate) |
|-------------|---------|---------------|-------------------------|
| **visual_siglip** | VisualSpace | Forma, estética, objetos | `visual` |
| **visual_semantic** | VisualSpace | Conceptos, significado (memes, arte) | `semantic` |
| **text_ocr** | VisualSpace → TextSpace | Extracción de texto de imágenes | `ocr_text` (property) |
| **audio_clap** | AudioSpace | Búsqueda por sonido/música | `audio_clap` |
| **audio_transcript** | AudioSpace | Transcripción de voz/lírica | `transcript_semantic` |
| **text_chunk** | TextSpace | Documentos, artículos, texto general | `text_embedding` |
| **text_summary** | - | Resumen textual (property, no vector) | - |
| **user_memory** | MemorySpace | Notas del usuario, contexto | `memory_embedding` |

---

## ⚙️ Processing Operations

### `standard`
- **Formato:** 1 File → 1 Asset
- **Comportamiento:** Procesa cada archivo individualmente
- **Uso común:** Imágenes, audio, documentos independientes

**Ejemplo:**
```json
{
  "operation": "standard",
  "file_indices": [0],
  "vector_types": ["visual_siglip", "visual_semantic"]
}
```

### `merge_ocr`
- **Formato:** N Files → 1 Asset
- **Comportamiento:** Extrae texto de todas las imágenes y concatena
- **Uso común:** Screenshots multipágina, Twitter threads, documentos escaneados
- **Output:** Archivo `.txt` con texto combinado

**Ejemplo:**
```json
{
  "operation": "merge_ocr",
  "file_indices": [0, 1, 2, 3],
  "vector_types": ["text_chunk"],
  "discard_original": true
}
```

---

## 📊 Job Status Lifecycle

```
ON_HOLD (Staging)
    ↓
    ↓ (User triggers via /tasks/start)
    ↓
PENDING (En cola Redis)
    ↓
    ↓ (Worker toma tarea)
    ↓
PROCESSING (Worker ejecutando)
    ↓
    ├── COMPLETED (Éxito)
    ├── FAILED (Error técnico)
    └── REJECTED (Cancelado por usuario)
```

- **ON_HOLD:** Estado inicial, esperando activación manual
- **PENDING:** En cola de Celery, esperando worker disponible
- **PROCESSING:** Worker ejecutando (vectorización, upload a Weaviate)
- **COMPLETED:** Procesamiento exitoso, `weaviate_uuid` poblado
- **FAILED:** Error durante procesamiento, ver `error_message`
- **REJECTED:** Usuario canceló tarea (endpoint futuro)

---

## 🗂️ Mapeo de Tipos de Archivo

| Extension | Espacio Recomendado | Vectores Sugeridos |
|-----------|---------------------|-------------------|
| `.jpg`, `.png`, `.gif`, `.webp` | VisualSpace | `visual_siglip`, `visual_semantic`, opcionalmente `text_ocr` |
| `.mp3`, `.wav`, `.ogg`, `.m4a` | AudioSpace | `audio_clap`, `audio_transcript` |
| `.mp4`, `.mov`, `.avi` | VisualSpace + AudioSpace | `visual_siglip`, `audio_clap`, `audio_transcript` |
| `.pdf`, `.txt`, `.md`, `.docx` | TextSpace | `text_chunk`, opcionalmente `text_summary` |
| `.json`, `.csv` | TextSpace | `text_chunk` (tras pre-procesamiento) |

---

## 🔧 Configuración Rápida por Caso de Uso

### 📸 Galería de Fotos
```
Operación: standard (por foto)
Vectores: visual_siglip, visual_semantic
Descartar: No
```

### 🎨 Memes / Arte Conceptual
```
Operación: standard
Vectores: visual_siglip, visual_semantic, text_ocr
Descartar: No
```

### 📄 Escaneo de Documentos Multipágina
```
Operación: merge_ocr (todas las páginas)
Vectores: text_chunk
Descartar: Sí (si solo necesitas texto)
```

### 🎙️ Podcast / Entrevista
```
Operación: standard
Vectores: audio_clap, audio_transcript
Descartar: No (conservar audio original)
```

### 🎬 Video Educativo
```
Operación: standard
Vectores: visual_siglip, audio_transcript
Descartar: No
```

### 📝 Nota Personal / Contexto
```
Operación: standard
Vectores: user_memory
Descartar: No
```

### 🐦 Twitter Thread (Screenshots)
```
Operación: merge_ocr (todos los tweets)
Vectores: text_chunk
Descartar: Sí
Notas: Incluir contexto (autor, tema, fecha)
```

---

## 🌐 API Endpoints Cheat Sheet

### Ingesta
```bash
POST /ingest/upload
Body: multipart/form-data
  - files: List[File]
  - upload_map: JSON string

GET /ingest/health
Response: {"status": "healthy", "service": "ingestion"}
```

### Tareas
```bash
GET /tasks/on-hold
Response: List[TaskResponse]

POST /tasks/start
Body: {"task_ids": ["uuid1", "uuid2"]}
Response: ProcessTasksResponse

GET /tasks/status/{task_id}
Response: TaskResponse

GET /tasks/health
Response: {"status": "healthy", "service": "tasks"}
```

### Búsqueda (Search App)
```bash
POST /search/vectors
Body: {"query": "gato blanco", "spaces": ["VisualSpace", "TextSpace"]}
Response: VectorSearchResponse

GET /search/options
Response: SearchOptions (available spaces, models)
```

---

## 🔐 Environment Variables

### Backend (`backend/.env.development`)
```env
# API
API_HOST=0.0.0.0
API_PORT=8000

# PostgreSQL
POSTGRES_USER=graphrag
POSTGRES_PASSWORD=secret
POSTGRES_SERVER=localhost
POSTGRES_PORT=5432
POSTGRES_DB=graphrag

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_SECURE=false

# Weaviate
WEAVIATE_URL=localhost
WEAVIATE_PORT=8080
WEAVIATE_GRPC_PORT=50051

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
```

### Frontend (`frontend/.streamlit/secrets.toml`)
```toml
API_BASE_URL = "http://localhost:8000"
```

### Search App (`search-app/.env.local`)
```env
VITE_API_URL=http://localhost:8000
```

---

## 📏 Límites y Constraints

| Límite | Valor por Defecto | Configurable en |
|--------|-------------------|-----------------|
| Max upload size | 500 MB | `frontend/.streamlit/config.toml` |
| Max files per upload | Sin límite | - |
| Max groups per upload | Sin límite | - |
| Min vectors per group | 1 | Validación frontend |
| Min files per group | 1 | Validación frontend |

---

## 🐛 Common Error Codes

| Status Code | Error | Causa | Solución |
|-------------|-------|-------|----------|
| 400 | Invalid JSON in upload_map | Formato JSON incorrecto | Verificar sintaxis (frontend maneja esto) |
| 400 | No files were uploaded | Lista de files vacía | Cargar archivos primero |
| 400 | Invalid UUID format | task_id no es UUID válido | Copiar ID exacto desde tabla |
| 404 | No ON_HOLD tasks found | IDs no existen o ya procesados | Refrescar Tab 2 |
| 500 | Error processing upload | Error interno del backend | Revisar logs del servidor |

---

## 📦 Data Structures

### UploadGroup (Pydantic Schema)
```python
{
    "file_indices": [0, 1, 2],          # Índices en lista de files
    "operation": "merge_ocr",           # standard | merge_ocr
    "vector_types": ["text_chunk"],     # List[VectorType]
    "user_notes": "Optional context",   # str | null
    "discard_original": true            # bool (default: false)
}
```

### TaskResponse (API Response)
```python
{
    "id": "uuid",
    "asset_id": "uuid",
    "filename": "example.jpg",
    "vector_type": "visual_siglip",
    "status": "on_hold",
    "created_at": "ISO8601",
    "updated_at": "ISO8601"
}
```

---

## ⚡ Performance Tips

1. **Batch agrupación:** Crear todos los grupos antes de enviar
2. **Descartar grandes archivos:** Si solo necesitas metadata/texto
3. **Procesamiento selectivo:** No actives todas las tasks de inmediato
4. **Upload local:** Si backend está en red, usar archivos pequeños o comprimir
5. **Índices apropiados:** PostgreSQL indexa `status`, `asset_id` por defecto

---

## 🔄 Workflow Típico

```
1. Cargar archivos (file_uploader)
   ↓
2. Crear grupos (group builder)
   ↓
3. Revisar grupos (expandable cards)
   ↓
4. Enviar al servidor (POST /ingest/upload)
   ↓
5. [Backend] Crear Assets + VectorStatus (ON_HOLD)
   ↓
6. Tab 2: Ver tasks (GET /tasks/on-hold)
   ↓
7. Seleccionar tasks prioritarias
   ↓
8. Activar procesamiento (POST /tasks/start)
   ↓
9. [Celery] Workers procesan (status → PENDING → PROCESSING → COMPLETED)
   ↓
10. [Futuro] Query semántica sobre vectores en Weaviate
```

---

## 📚 Resources
- **Backend Docs:** `backend/README.md` (si existe)
- **Frontend Docs:** `frontend/README.md`
- **Architecture:** `ARCHITECTURE.md`
- **Usage Guide:** `USAGE_GUIDE.md`
- **This Reference:** `QUICK_REFERENCE.md`
