# GraphRAG Multimodal v2

Sistema de Graph RAG multimodal con arquitectura híbrida Worker-Server, interfaz Streamlit, y procesamiento distribuido con Celery.

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────────────┐
│                    FRONTEND (Streamlit)                  │
│  - File Upload & Grouping                               │
│  - Task Management Dashboard                            │
│  - Vector Configuration                                 │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP/REST
                         ▼
┌─────────────────────────────────────────────────────────┐
│                  BACKEND (FastAPI)                       │
│  - /ingest/upload    - Asset creation                   │
│  - /tasks/*          - Task management                  │
│  - IngestService     - Business logic                   │
└──┬──────────────┬──────────────┬──────────────┬─────────┘
   │              │              │              │
   ▼              ▼              ▼              ▼
┌────────┐  ┌─────────┐  ┌──────────┐  ┌──────────────┐
│Postgres│  │  MinIO  │  │  Redis   │  │  Weaviate    │
│(Meta)  │  │(Binary) │  │(Queue)   │  │(Vectors)     │
└────────┘  └─────────┘  └─────┬────┘  └──────────────┘
                                │
                                ▼
                         ┌──────────────┐
                         │    Celery    │
                         │  (Workers)   │
                         └──────┬───────┘
                                │
                                ▼
                         ┌──────────────┐
                         │    Neo4j     │
                         │   (Graph)    │
                         └──────────────┘
```

## 📁 Estructura del Proyecto

```
graphrag/
├── backend/                    # FastAPI Server
│   ├── app/
│   │   ├── models/            # SQLModel entities
│   │   ├── routers/           # API endpoints
│   │   ├── schemas/           # Pydantic schemas
│   │   └── services/          # Business logic
│   ├── config/                # Settings
│   ├── scripts/               # Utilities
│   ├── shared/                # Database & clients
│   ├── worker/                # Celery tasks
│   └── pyproject.toml
│
├── search-app/                 # React Search Interface (New)
│   ├── src/
│   ├── public/
│   └── package.json
│
├── frontend/                   # Streamlit Admin Panel (Legacy)
│   ├── app.py                 # Main application
│   ├── .streamlit/            # Configuration
│   ├── requirements.txt
│   ├── start.bat / start.sh
│   └── README.md
│
├── graph-rag/                  # Docker Compose
│   └── docker-compose.yml     # Services stack
│
├── ARCHITECTURE.md             # System design
├── USAGE_GUIDE.md             # User manual
├── QUICK_REFERENCE.md         # Cheat sheet
├── WALKTHROUGH.md             # Implementation summary
└── README.md                  # This file
```

## 🚀 Quick Start

### 1. Iniciar Infraestructura (Docker)

```bash
cd graph-rag
docker-compose up -d
```

Servicios disponibles:
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`
- MinIO: `localhost:9000` (Console: `localhost:9001`)
- Weaviate: `localhost:8080`
- Neo4j: `localhost:7687` (Browser: `localhost:7474`)

### 2. Iniciar Backend (FastAPI)

```bash
cd backend
poetry install
poetry run uvicorn app:app --reload
```

API disponible en: `http://localhost:8000`  
Documentación: `http://localhost:8000/docs`

### 3. Iniciar Frontend de Búsqueda (React)

```bash
cd search-app
npm install
npm run dev
```

Buscador disponible en: `http://localhost:5173/search`

### 4. Iniciar Panel de Administración (Streamlit)

```bash
cd frontend

# Opción A: Script automático (Windows)
start.bat

# Opción B: Script automático (Linux/Mac)
chmod +x start.sh
./start.sh

# Opción C: Manual
python -m venv venv
venv\Scripts\activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Panel disponible en: `http://localhost:8501`

## 🎯 Funcionalidades Principales

### Frontend (Streamlit)

#### Tab 1: Ingesta y Agrupación
- 📁 **Carga de Archivos**: Múltiples archivos simultáneamente
- 🔧 **Constructor de Grupos**: 
  - Operaciones: Standard (1:1) o Merge OCR (N:1)
  - Vectores: Visual, Audio, Text, Memory
  - Opciones: Descartar originales, notas contextuales
- 📦 **Visualización**: Vista clara de grupos creados
- 🚀 **Envío Inteligente**: Mapeo automático al backend

#### Tab 2: Control de Tareas
- 📊 **Dashboard**: Lista de tareas en estado ON_HOLD
- ✅ **Activación Selectiva**: Procesar tareas específicas
- 🔄 **Refresh Manual**: Actualizar estado de tareas

### Backend (FastAPI)

#### Endpoints de Ingesta
- `POST /ingest/upload` - Subir archivos con configuración
- `GET /ingest/health` - Health check

#### Endpoints de Tareas
- `GET /tasks/on-hold` - Listar tareas en staging
- `POST /tasks/start` - Activar procesamiento
- `GET /tasks/status/{task_id}` - Estado de tarea
- `GET /tasks/health` - Health check

## 📚 Documentación

| Documento | Descripción | Audiencia |
|-----------|-------------|-----------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Diseño del sistema, flujos de datos, API contracts | Desarrolladores |
| [USAGE_GUIDE.md](USAGE_GUIDE.md) | Casos de uso, ejemplos prácticos, troubleshooting | Usuarios finales |
| [QUICK_REFERENCE.md](QUICK_REFERENCE.md) | Cheat sheet de vectores, operaciones, configuraciones | Todos |
| [WALKTHROUGH.md](WALKTHROUGH.md) | Resumen de implementación, features, roadmap | Stakeholders |
| [frontend/README.md](frontend/README.md) | Setup del frontend, instrucciones detalladas | Desarrolladores |

## 🎨 Tipos de Vectores Disponibles

| Vector Type | Uso Principal | Espacio |
|-------------|---------------|---------|
| `visual_siglip` | Forma, estética, objetos | VisualSpace |
| `visual_semantic` | Conceptos, significado (memes, arte) | VisualSpace |
| `text_ocr` | Extracción de texto de imágenes | VisualSpace → TextSpace |
| `audio_clap` | Búsqueda por sonido/música | AudioSpace |
| `audio_transcript` | Transcripción de voz/lírica | AudioSpace |
| `text_chunk` | Documentos, artículos | TextSpace |
| `text_summary` | Resumen textual | - |
| `user_memory` | Notas del usuario, contexto | MemorySpace |

## ⚙️ Operaciones de Procesamiento

### Standard (1 archivo → 1 asset)
Procesa cada archivo individualmente. Ideal para imágenes, audio, documentos independientes.

### Merge OCR (N archivos → 1 asset)
Extrae texto de múltiples imágenes y concatena. Útil para screenshots multipágina, Twitter threads, documentos escaneados.

## 🔄 Ciclo de Vida de Tareas

```
ON_HOLD (Staging)
    ↓ (User triggers)
PENDING (En cola)
    ↓ (Worker takes)
PROCESSING (Ejecutando)
    ↓
    ├── COMPLETED (Éxito)
    ├── FAILED (Error)
    └── REJECTED (Cancelado)
```

## 🧪 Testing

### Backend API
```bash
# Health checks
curl http://localhost:8000/
curl http://localhost:8000/ingest/health
curl http://localhost:8000/tasks/health

# List ON_HOLD tasks
curl http://localhost:8000/tasks/on-hold

# Upload files
curl -X POST "http://localhost:8000/ingest/upload" \
  -F "files=@test.jpg" \
  -F 'upload_map=[{"file_indices":[0],"operation":"standard","vector_types":["visual_siglip"],"discard_original":false}]'
```

### Frontend
1. Cargar archivos → Verificar aparecen en "Sin Asignar"
2. Crear grupo → Verificar desaparecen de "Sin Asignar"
3. Eliminar grupo → Verificar vuelven a "Sin Asignar"
4. Enviar al servidor → Verificar response exitosa
5. Tab 2 → Verificar tasks aparecen
6. Procesar tasks → Verificar estado cambia

## 🔧 Configuración

### Variables de Entorno (Backend)

Crear `backend/.env.development`:

```env
# API
API_HOST=0.0.0.0
API_PORT=8000

# PostgreSQL
POSTGRES_USER=graphrag
POSTGRES_PASSWORD=yourpassword
POSTGRES_SERVER=localhost
POSTGRES_PORT=5432
POSTGRES_DB=graphrag

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin

# Weaviate
WEAVIATE_URL=localhost
WEAVIATE_PORT=8080

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=yourpassword
```

### Secrets (Frontend)

Ya configurado en `frontend/.streamlit/secrets.toml`:

```toml
API_BASE_URL = "http://localhost:8000"
```

## 📋 Casos de Uso Comunes

### 1. Galería de Fotos
```
Archivos: foto1.jpg, foto2.jpg, foto3.jpg
Operación: standard (por foto)
Vectores: visual_siglip, visual_semantic
```

### 2. Merge de Screenshots
```
Archivos: screenshot1.png, screenshot2.png, screenshot3.png
Operación: merge_ocr (todas juntas)
Vectores: text_chunk
Descartar: Sí
```

### 3. Podcast
```
Archivo: podcast.mp3
Operación: standard
Vectores: audio_clap, audio_transcript
```

Ver [USAGE_GUIDE.md](USAGE_GUIDE.md) para más ejemplos.

## 🐛 Troubleshooting

### Backend no responde
```bash
# Verificar que está ejecutándose
curl http://localhost:8000/

# Revisar logs
cd backend
poetry run uvicorn app:app --reload
```

### Frontend no conecta
1. Verificar `frontend/.streamlit/secrets.toml` tiene `API_BASE_URL` correcto
2. Verificar backend está en la URL especificada
3. Revisar CORS si frontend y backend están en diferentes dominios

### Tasks no aparecen en Tab 2
1. Verificar que enviaste archivos con vectores seleccionados
2. Verificar backend tiene router de tasks registrado
3. Query directo a DB:
   ```sql
   SELECT * FROM vector_statuses WHERE status = 'on_hold';
   ```

## 🎯 Roadmap

### Completado ✅
- [x] Frontend Streamlit completo
- [x] Gestión de estado con session_state
- [x] Integración con backend FastAPI
- [x] Router de tasks (/tasks/*)
- [x] Documentación completa

### En Progreso 🔄
- [ ] Integración Celery real en /tasks/start
- [ ] Workers procesando vectorizaciones

### Futuro 📅
- [ ] Auto-refresh de Tab 2
- [ ] Filtros y paginación en task dashboard
- [ ] Interface de búsqueda semántica
- [ ] Visualización de grafo Neo4j
- [ ] Autenticación multi-usuario

## 🤝 Contribuir

1. Fork el repositorio
2. Crea una branch (`git checkout -b feature/nueva-funcionalidad`)
3. Commit tus cambios (`git commit -m 'Agrega nueva funcionalidad'`)
4. Push a la branch (`git push origin feature/nueva-funcionalidad`)
5. Abre un Pull Request

## 📄 Licencia

Este proyecto es privado. Todos los derechos reservados.

## 👥 Autores

- **Equipo GraphRAG** - Desarrollo inicial

## 🙏 Agradecimientos

- Streamlit por la excelente framework de UI
- FastAPI por el backend veloz y moderno
- SQLModel, Weaviate, Neo4j por las tecnologías de datos

---

**¿Dudas?** Consulta la [documentación completa](ARCHITECTURE.md) o abre un issue.
