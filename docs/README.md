# Documentación — GraphRAG

[![DOI](https://zenodo.org/badge/1153050483.svg)](https://doi.org/10.5281/zenodo.23228850)

**Español (principal)** · [English documentation](en/README.md) · [Proyecto](../README.md)

## Empieza aquí

| Documento | Contenido |
|---|---|
| [Presentación del proyecto](../README.md) | Propósito, capacidades y vista general con capturas. |
| [Arranque](general/QUICKSTART.md) | Compose principal, dependencias de modelos, puertos y desarrollo local. |
| [Guía visual de uso](general/USAGE_GUIDE.md) | Incorporar archivos, buscar, recorrer conexiones e interpretar hallazgos. |
| [Frontend React](../search-app/README.md) | Interfaz actual, comandos y rutas. |

Estas guías de entrada están actualizadas para las rutas y el Compose actuales. Para el arranque y la navegación, tienen prioridad sobre los ejemplos históricos de las referencias técnicas.

## Referencias técnicas

| Documento | Contenido |
|---|---|
| [Arquitectura](general/ARCHITECTURE.md) | Diseño del sistema. |
| [Diagramas](general/diagrams.md) | Modelo de datos y flujos Mermaid. |
| [Integración](general/INTEGRATION.md) | Conexión entre backend y frontend. |
| [Referencia rápida](general/QUICK_REFERENCE.md) | Referencia técnica complementaria. |
| [Recorrido técnico](general/WALKTHROUGH.md) | Sesión de trabajo y procesamiento. |
| [Lógica difusa](backend/FUZZY_LOGIC.md) | Fórmulas, pesos e interpretación. |
| [Enriquecimiento](backend/enrichment_summary.md) | APIs de enriquecimiento y exploración. |
| [Entidades difusas](backend/fuzzy_concept_summary.md) | Ciclo de vida de entidades. |
| [Celery](backend/CELERY_GUIDE.md) | Procesamiento distribuido. |
| [Resolución de problemas](backend/TROUBLESHOOTING.md) | Errores y soluciones. |
| [Panel Streamlit heredado](frontend/README.md) | Documentación del frontend anterior. |
| [Previsualización de archivos](frontend/FILE_PREVIEW_GUIDE.md) | Referencia del sistema de previews. |

El [Compose principal](../docker-compose.yml) despliega aplicación e infraestructura. El [Compose alternativo](general/docker-compose.yml) es una configuración de infraestructura distinta; no mezcles sus instrucciones o puertos.

Con el backend activo: [Swagger UI](http://localhost:8000/docs), [ReDoc](http://localhost:8000/redoc) y [OpenAPI](http://localhost:8000/openapi.json).

## Idiomas y capturas

El español es el idioma principal del proyecto. La [lectura en inglés](en/README.md) incluye presentación, arranque y guía visual; las referencias aún sin traducir se identifican como contenido en español. Los nombres de los controles se conservan para encontrarlos en la app.

Las imágenes se comparten entre ambos idiomas, con texto alternativo y explicaciones traducidas. Consulta su [procedencia y actualización](images/README.md).
