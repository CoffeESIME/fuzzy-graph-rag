# Guía de Uso — GraphRAG Multimodal v2

## 🔍 Búsqueda

### Tab 1: Búsqueda Semántica (`/search`)

**Qué hace:** Encuentra archivos por significado, no por texto exacto. Combina BM25 (keywords) con BGE-M3 (vectores semánticos).

**Cómo usarlo:**
1. Escribe tu consulta en el campo de texto (ej: "memes de gatos")
2. Ajusta el **slider Alpha**:
   - `α = 0.0` → Solo keywords (BM25)
   - `α = 0.5` → Balanceado (recomendado)
   - `α = 1.0` → Solo vectorial (significado puro)
3. Selecciona los **espacios** a buscar (Text, Visual, Audio, Memory)
4. Opcionalmente agrega **tags** para filtrar
5. Los resultados muestran: score, propiedades, y preview multimedia via MinIO

### Tab 2: Búsqueda Visual SigLIP

**Qué hace:** Sube una imagen y encuentra contenido visualmente similar usando embeddings SigLIP (1152 dimensiones).

**Cómo usarlo:**
1. Arrastra o selecciona una imagen
2. El sistema codifica la imagen con SigLIP
3. Busca en VisualSpace por similitud coseno
4. Resultados: imágenes similares con score de distancia

### Tab 3: Búsqueda Multimodal

**Qué hace:** Fusiona búsqueda por imagen + texto usando Reciprocal Rank Fusion (RRF).

**Cómo usarlo:**
1. Sube una imagen + escribe contexto textual
2. Ajusta alpha (peso imagen vs texto)
3. Vista dividida: resultados de texto (izq), visuales (der), fusionados (centro)
4. Los archivos que aparecen en ambas columnas se marcan como "Perfect Match"

### Tab 4: Grafo Crisp (`/search` → Grafo Crisp)

**Qué hace:** Traversal del grafo Neo4j con un umbral de corte alpha. Solo muestra relaciones con peso ≥ alpha.

**Cómo usarlo:**
1. Escribe un concepto (ej: "melancolía")
2. Ajusta el **alpha-cut** (ej: 0.7 = solo relaciones con peso ≥ 0.7)
3. El grafo se renderiza con React Flow / D3
4. Click en un nodo para ver sus propiedades, preview multimedia, y texto

### Tab 5: Grafo Fuzzy

**Qué hace:** Primero busca vectorialmente los assets más similares, luego expande vía Neo4j para descubrir conceptos y personas conectados.

**Cómo usarlo:**
1. Escribe una consulta
2. El sistema busca en Weaviate → usa los assets encontrados como semillas en Neo4j
3. Expande a conceptos, personas, y assets vecinos
4. Visualizado en 3D (Three.js) o 2D (D3)

---

## 📊 Análisis

Navega a `/analysis` para ver el dashboard con todas las herramientas. Click en cualquier card para abrir la herramienta.

### Comunidades (Louvain)
**Ruta:** `/analysis/communities`
**Qué ves:** Burbujas agrupadas (Circle Packing). Cada burbuja grande es un clúster temático, las pequeñas son conceptos.
**Usa:** Neo4j GDS Louvain Modularity sobre un grafo virtual de co-ocurrencia (Concepto ← Asset → Concepto).
**Interpretación:** Si ves un clúster "Meme, Humor, Ironía" y otro "Melancolía, Dualidad, Gothic Metal", el sistema está entendiendo la estructura temática de tu mente.

### Puentes Semánticos
**Ruta:** `/analysis/bridges`
**Qué ves:** Cards con conceptos que actúan como puentes entre mundos temáticos.
**Interpretación:** Un concepto con alto "bridge score" conecta comunidades distintas — es un concepto bisagra.

### Camino de Serendipia
**Ruta:** `/analysis/serendipity`
**Qué ves:** Una línea de metro con conceptos (💡) y assets (📄) conectados por pesos difusos.
**Interacción:** Click en un asset para ver preview multimedia + metadatos (hash, MIME type, nombre).
**Interpretación:** Las conexiones naranjas (✨ < 0.8) son las serendipias — asociaciones débiles pero reales.

### Fog of War
**Ruta:** `/analysis/fog-of-war`
**Qué ves:** Distribución de nodos por grado de conectividad.
**Interpretación:** Los nodos con bajo grado están en la "niebla" — áreas poco exploradas de tu conocimiento.

### Heatmap Jaccard
**Ruta:** `/analysis/heatmap`
**Qué ves:** Matriz de calor con similitud Jaccard entre conceptos.
**Interpretación:** Celdas calientes = conceptos que co-ocurren frecuentemente.

### Diagrama de Cuerdas
**Ruta:** `/analysis/chord`
**Qué ves:** Flujos entre categorías (Concept, Person, etc.) basados en co-ocurrencia via DigitalAssets.
**Interpretación:** Las cuerdas gruesas indican categorías que frecuentemente aparecen juntas.

### Árbol Radial
**Ruta:** `/analysis/radial-tree`
**Qué ves:** Árbol expandido desde un nodo raíz, mostrando co-ocurrencias en anillos concéntricos.
**Interacción:** Puedes cambiar el nodo raíz para explorar diferentes regiones del grafo.

### Conceptos Abstractos
**Ruta:** `/analysis/abstract-concepts`
**Qué ves:** Scatter plot con Grado (X) vs Peso Promedio (Y).
**Interpretación:** Conceptos arriba-derecha = bien conectados Y con alta certeza. Abajo-izquierda = poco conectados Y difusos.

### PageRank
**Ruta:** `/analysis/pagerank`
**Qué ves:** Ranking de nodos por importancia estructural (algoritmo GDS PageRank).
**Interpretación:** Los nodos con mayor PageRank son los más "influyentes" en tu grafo.

### Nodos Huérfanos
**Ruta:** `/analysis/orphans`
**Qué ves:** Lista de conceptos sin conexiones (grado = 0).
**Interpretación:** Estos nodos están aislados y podrían beneficiarse de más contexto o relaciones.

### Distribución de Pesos
**Ruta:** `/analysis/weight-distribution`
**Qué ves:** Histograma de pesos de relaciones [0–1].
**Interpretación:** Si la mayoría de pesos están > 0.8, el LLM está muy seguro. Si hay muchos < 0.5, hay alta incertidumbre.

---

## 📥 Ingesta

### Tab 1: Carga y Agrupación

1. **Arrastra archivos** al panel de carga
2. **Crea grupos** con la configuración deseada:
   - **Operación**: Standard (1 archivo → 1 asset) o Merge OCR (N → 1)
   - **Vectores**: Selecciona qué tipos de embeddings generar
   - **Opciones**: Descartar originales, notas contextuales
3. **Enviar** al servidor — crea DigitalAssets y tareas en staging

### Tab 2: Control de Tareas

- Ver estado de todas las tareas: `ON_HOLD → PENDING → PROCESSING → COMPLETED`
- **Activar** tareas individualmente o en batch
- **Retry** tareas fallidas
- **Cancel** tareas pendientes

### Tab 3: Cola de Revisión (Review Queue)

- Antes de ingresar al grafo, los conceptos/personas extraídos pasan por aprobación humana
- **Aprobar**: Crea el nodo y relaciones en Neo4j
- **Rechazar**: Descarta la sugerencia
- **Editar**: Modifica el nombre o peso antes de aprobar

### Tab 4: Graph Generator

- Crear nodos manualmente: Concept, Person, Location, Event
- Crear conexiones con peso y tipo de relación
- Buscar nodos existentes para vincular

---

## 📋 Casos de Uso

### Galería de Fotos
```
Archivos: foto1.jpg, foto2.jpg, foto3.jpg
Operación: standard
Vectores: visual_siglip, visual_semantic
→ Busca por similitud visual o por conceptos extraídos vía OCR
```

### Screenshots de Documentos
```
Archivos: screenshot1.png, screenshot2.png
Operación: merge_ocr
Vectores: text_chunk
→ Extrae texto con Qwen3-VL, chunked en Weaviate
```

### Podcast / Audio
```
Archivo: podcast.mp3
Vectores: audio_clap, audio_transcript
→ Busca por sonido (CLAP) o por transcripción (Whisper + BGE-M3)
```

### Notas Personales
```
Texto: "Hoy aprendí sobre grafos difusos..."
Vectores: user_memory
→ Almacena en MemorySpace, incluye contexto del usuario
```

### Exploración del Grafo
```
1. Busca "melancolía" en Grafo Crisp → ve conexiones fuertes
2. Busca en Grafo Fuzzy → descubre assets y conceptos vecinos
3. Usa Serendipia → encuentra caminos inesperados
4. Ve Comunidades → valida clusters temáticos
```
