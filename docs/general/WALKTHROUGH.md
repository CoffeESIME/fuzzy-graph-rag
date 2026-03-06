# Walkthrough — GraphRAG Multimodal v2

## Resumen del Sistema

GraphRAG es un cerebro digital que ingiere archivos multimodales (texto, imagen, audio, video), los analiza con LLMs, genera embeddings vectoriales, construye un grafo de conocimiento difuso, y expone todo via una interfaz React con búsqueda semántica y herramientas de análisis.

## Stack Tecnológico

| Capa | Tecnología | Rol |
|------|-----------|-----|
| Frontend | React + Vite + TypeScript | SPA con 3 módulos |
| Visualización | Nivo, Recharts, Three.js, React Flow | Gráficos, grafos, heatmaps |
| Backend | FastAPI (Python) | REST API, 8 routers |
| Workers | Celery + Redis | Procesamiento async de LLM/embeddings |
| LLM | Ollama (llama3.2, qwen3-vl, whisper) | Resúmenes, OCR, transcripción |
| Vectores | Weaviate | 4 espacios, 7 named vectors |
| Grafo | Neo4j + GDS Plugin | Louvain, PageRank, proyecciones |
| Objetos | MinIO (S3-compatible) | Almacenamiento de archivos raw |
| Metadata | PostgreSQL | Registro de assets, tareas, sidecars |

## Flujo de Datos Completo

```
1. Upload → MinIO almacena archivo, Postgres registra DigitalAsset
2. Staging → Tarea queda ON_HOLD en review queue
3. Review → Usuario aprueba conceptos/personas extraídos
4. Processing → Celery: LLM resumen, embeddings, graph sync
5. Ready → Archivo buscable en Weaviate, conectado en Neo4j
6. Búsqueda → 6 modos: semántica, visual, multimodal, grafo×2
7. Análisis → 11 herramientas GDS para entender la estructura
```

## Módulos Frontend

### Búsqueda (6 tabs)
- Semántica (BM25+vector), Visual (SigLIP), Multimodal (RRF fusion)
- Grafo Crisp (alpha-cut traversal), Grafo Fuzzy (vector→graph expansion)
- MediaPreview inline para imágenes, audio, video

### Análisis (11 herramientas)
- Comunidades (Louvain Circle Packing), Puentes, Serendipia
- Fog of War, Heatmap Jaccard, Chord Co-ocurrencia
- Radial Tree, Conceptos Abstractos, PageRank
- Huérfanos, Distribución de Pesos

### Ingesta (5 tabs)
- Upload con agrupación, Control de tareas, Review queue
- Graph Generator manual, Lyrics lookup
