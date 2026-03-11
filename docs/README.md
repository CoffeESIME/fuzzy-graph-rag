# 📚 Documentación — GraphRAG

Documentación técnica del sistema multimodal de recuperación aumentada por grafos.

---

## 📁 Estructura

```
docs/
├── general/          ← Arquitectura del sistema y guías transversales
├── backend/          ← APIs, workers, enriquecimiento
└── frontend/         ← Componentes UI, guías de uso visual
```

---

## 🌐 General

| Documento | Descripción |
|-----------|-------------|
| [QUICKSTART.md](general/QUICKSTART.md) | ⚡ Arranque rápido de toda la infraestructura con Docker |
| [docker-compose.yml](general/docker-compose.yml) | Compose con Neo4j + Weaviate + MinIO + Redis + PostgreSQL |
| [ARCHITECTURE.md](general/ARCHITECTURE.md) | Vista de alto nivel del sistema completo |
| [USAGE_GUIDE.md](general/USAGE_GUIDE.md) | Guía de uso del sistema |
| [QUICK_REFERENCE.md](general/QUICK_REFERENCE.md) | Comandos y referencias rápidas |
| [WALKTHROUGH.md](general/WALKTHROUGH.md) | Flujo completo de una sesión de trabajo |
| [diagrams.md](general/diagrams.md) | Diagramas Mermaid del sistema (arquitectura, modelo de datos, flujos) |
| [INTEGRATION.md](general/INTEGRATION.md) | Conexión Backend ↔ Frontend: URLs, módulos, CORS, env vars |

---

## 🔧 Backend

| Documento | Descripción |
|-----------|-------------|
| [enrichment_summary.md](backend/enrichment_summary.md) | Referencia técnica de todos los endpoints de enriquecimiento (`/api/enrichment`, `/api/explore`) |
| [FUZZY_LOGIC.md](backend/FUZZY_LOGIC.md) | 🧮 **Guía técnica completa** — Mínimo de Zadeh, fórmulas, ejemplos, uso por herramienta |
| [fuzzy_concept_summary.md](backend/fuzzy_concept_summary.md) | Resumen ejecutivo del ciclo de vida de entidades difusas |
| [CELERY_GUIDE.md](backend/CELERY_GUIDE.md) | Configuración y uso del worker Celery |
| [TROUBLESHOOTING.md](backend/TROUBLESHOOTING.md) | Errores comunes y soluciones |

**API interactiva (con servidor corriendo):**
- Swagger UI → `http://localhost:8000/docs`
- ReDoc → `http://localhost:8000/redoc`
- OpenAPI JSON → `http://localhost:8000/openapi.json`

---

## 🖥️ Frontend

| Documento | Descripción |
|-----------|-------------|
| [FILE_PREVIEW_GUIDE.md](frontend/FILE_PREVIEW_GUIDE.md) | Sistema de previsualización de archivos multimedia |
| [README.md](frontend/README.md) | Setup y estructura del proyecto React/Vite |
