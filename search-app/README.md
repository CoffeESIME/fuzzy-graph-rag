# Frontend React — GraphRAG

**Español** · [English project guide](../README.en.md) · [Documentación](../docs/README.md)

Interfaz principal del observatorio: React, TypeScript y Vite. Incluye búsqueda multimodal, ingesta y revisión, análisis de grafos y enriquecimiento. El panel Streamlit de `frontend/` es heredado.

## Desarrollo

Desde esta carpeta:

```bash
npm ci
npm run dev
```

Abre [http://localhost:5173](http://localhost:5173). Vite reenvía `/api/*` a `http://localhost:8000`, eliminando `/api`. Para configurar backend y almacenamiento, consulta el [arranque](../docs/general/QUICKSTART.md).

```bash
npm run build
npm run lint
```

`build` comprueba TypeScript y genera `dist/`. `preview` permite servir esa compilación, pero no configura el proxy de desarrollo de `server.proxy`; para usar la API en el despliegue, el contenedor incluye Nginx y su proxy `/api`.

## Rutas

| Ruta | Pantalla |
|---|---|
| `/` | Inicio: Serendipity, Pathfinder y accesos al corpus. |
| `/search` | Semántica, Visual, Multimodal, Grafo, Grafo Difuso y Comparativa. |
| `/ingest` | Ingesta y Agrupación, Control de Tareas, Cola de Revisión y Generador de Nodos. |
| `/analysis` | Catálogo de herramientas de análisis. |
| `/analysis/pathfinder` | Navegador Latente: caminos entre dos nodos. |
| `/analysis/serendipity` | Recorridos exploratorios. |
| `/analysis/saved-paths` | Caminos guardados. |
| `/enrichment` | Enriquecimiento y limpieza del grafo. |

Las rutas están declaradas en `src/App.tsx`. La [guía visual](../docs/general/USAGE_GUIDE.md) explica cómo usar la interfaz; [la versión inglesa](../docs/en/USAGE_GUIDE.md) conserva los nombres de botones en español.
