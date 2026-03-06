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
| [ARCHITECTURE.md](general/ARCHITECTURE.md) | Vista de alto nivel del sistema completo |
| [USAGE_GUIDE.md](general/USAGE_GUIDE.md) | Guía de uso del sistema |
| [QUICK_REFERENCE.md](general/QUICK_REFERENCE.md) | Comandos y referencias rápidas |
| [WALKTHROUGH.md](general/WALKTHROUGH.md) | Flujo completo de una sesión de trabajo |
| [diagrams.md](general/diagrams.md) | Diagramas Mermaid del sistema (arquitectura, modelo de datos, flujos) |

---

## 🔧 Backend

| Documento | Descripción |
|-----------|-------------|
| [enrichment_summary.md](backend/enrichment_summary.md) | Referencia técnica de todos los endpoints de enriquecimiento (`/api/enrichment`, `/api/explore`) |
| [fuzzy_concept_summary.md](backend/fuzzy_concept_summary.md) | Lógica de pesos difusos en relaciones del grafo |
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
