# Visual user guide — GraphRAG

[Español (principal)](../general/USAGE_GUIDE.md) · **English** · [Index](README.md)

The goal is to turn files into a corpus you can search and explore through relationships. Follow the [quickstart](QUICKSTART.md) first. Results require processed files, vectors in the selected spaces, and graph relationships.

Screenshots show the actual app's initial navigation and configuration screens, not results or metrics from a demonstration corpus. Spanish UI labels are retained below so you can locate the controls.

## 1. Add material

Open **Ingesta → Ingesta y Agrupación**. Ingesta initially opens Control de Tareas, so switch to the grouping tab to add material.

![File or text ingestion controls](../images/ingesta.jpg)

*Archivos accepts media files; Texto accepts written content. Grouping and vector options appear after material is added.*

1. Select files or enter text.
2. Configure groups and operations: Standard processes items individually; Merge OCR groups material for text extraction.
3. Select processing appropriate to the content: text, visual representations, transcription, or memory, as available.
4. Submit the groups and inspect their status in **Control de Tareas**.

Tasks may progress through `ON_HOLD → PENDING → PROCESSING → COMPLETED`, or fail. A held task needs activation; uploading a file does not mean it is indexed. Inspect failed tasks before retrying.

Use **Cola de Revisión** to inspect proposed entities and relationships before approving them. **Generador de Nodos** supports manual work with nodes and connections.

## 2. Search

![Semantic search spaces and advanced options](../images/busqueda.jpg)

*Choose the representation to search: Texto (text), Visual, Audio, or Memoria (memory). A space only returns results if your material has vectors in it.*

In **Búsqueda → Semántica**, enter a query, choose spaces and a result limit, then press **Buscar**. **Opciones avanzadas** includes hybrid balance: alpha 0 prioritizes BM25, alpha 1 uses vector similarity, and intermediate values combine both.

| Tab | Question it helps answer |
|---|---|
| Semántica | Which files discuss this idea? |
| Visual | Which images resemble this reference? |
| Multimodal | Which content matches this image and description? |
| Grafo | Which entities have explicit connections? |
| Grafo Difuso | Which neighbors emerge from expanding a similarity search? |
| Comparativa | How do results differ between retrieval systems? |

Open the preview or original file to check a match. Retrieval scores rank matches; they do not establish that a statement is true. Hybrid-search alpha and graph relationship thresholds serve different purposes.

## 3. Connect two ideas with Pathfinder

From Inicio, choose **Conecta dos ideas**, or open `/analysis/pathfinder`. The screen is titled **Navegador Latente**.

![Pathfinder origin, destination, and path modes](../images/pathfinder.jpg)

*The selectors define the two ends of the route. The mode changes how paths are selected.*

1. Find and select an origin and a destination node; **Por Tipo** lets you browse by type.
2. Choose **Directo**, **Lateral**, or **Topológico**, and the number of paths.
3. Expand **¿Cómo funciona? · Detalles del método** to read the criteria. Directo minimizes the sum of `1 − weight`.
4. Press **Trazar Camino** and inspect the relationships and source files along the route.
5. If you save a path, revisit it through **Caminos guardados** (`/analysis/saved-paths`).

If no path exists, check the selected nodes and corpus connectivity. Not every pair is connected.

## 4. Discover and analyze

![Graph analysis tools](../images/analisis.jpg)

*The dashboard presents different views of the same knowledge: groups, connections, paths, and graph quality.*

**Serendipity** (`/analysis/serendipity`) provides exploratory walks. **Comunidades** groups concepts, while **Puentes Semánticos** helps identify connectors. Heatmaps, chord diagrams, and radial trees offer other views of relationships. Orphans and weight distributions help inspect structure.

Communities and PageRank require GDS, which the root Compose does not install. See the [quickstart](QUICKSTART.md) if these tools report errors.

## 5. Enrich and evaluate findings

**Enriquecimiento** (`/enrichment`) collects tools for adjusting weights, discovering connections, and cleaning entities. Review proposed changes and each operation's scope before modifying your graph.

Fuzzy weights express relationship strength according to the method, not verified probabilities. Check original files, available reasoning, and the [fuzzy logic reference (Spanish)](../backend/FUZZY_LOGIC.md). A suggested connection is a hypothesis to investigate.

## If there are no results

- Check that tasks completed and the selected space contains vectors.
- Review filters, thresholds, and graph connectivity.
- For API errors, inspect the backend, worker, and gateway using the [quickstart](QUICKSTART.md).
- If a file does not open, check MinIO access; host and container ports differ.

See also [troubleshooting (Spanish)](../backend/TROUBLESHOOTING.md).
