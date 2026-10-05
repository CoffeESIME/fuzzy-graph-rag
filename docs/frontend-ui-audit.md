# Auditoría y estandarización del frontend

Fecha: 2026-10-04. Alcance: presentación en `search-app`, componentes visuales y documentación. No se modificaron backend, endpoints, contratos, tipos de API, stores de búsqueda, esquemas, parámetros ni algoritmos. El cambio previo en `.gitignore` pertenece al estado inicial del workspace.

## 1. Arquitectura encontrada

React 19 + TypeScript + Vite; React Router para navegación, Zustand y TanStack Query para estado/datos. Tailwind 4 convive con una cantidad importante de estilos inline. Iconografía Lucide React ya instalada. React Flow 11 + Dagre en Pathfinder, Saved Paths, árbol radial, puentes y búsqueda; Serendipity usaba una composición HTML propia. Nivo SVG en comunidades, chord, heatmap, PageRank, distribución de pesos y conceptos abstractos; Recharts en cobertura. Canvas con react-force-graph-2d en búsqueda; Three.js está presente, pero no seleccionado por las pantallas actuales de búsqueda.

`index.css` y `useTheme.ts` ya ofrecían tokens y selección de tema. No se creó una segunda gestión global de temas. Se ampliaron sus tokens y se mantuvo la preferencia persistida. `lib/api.ts`, `types/search.ts`, hooks de búsqueda y stores permanecen sin cambios.

## 2. Problemas e inconsistencias

- Canvas blanco de Pathfinder dentro de la aplicación oscura; colores y texto de varios gráficos fijados al tema oscuro.
- DigitalAsset verde en búsqueda, azul en Pathfinder y representaciones diferentes en caminos guardados y Serendipity.
- Saved Paths tenía tarjetas genéricas y distribución básica; Serendipity una línea HTML sin navegación espacial.
- Inspectores y previews duplicados; Pathfinder desplazaba la atención a un panel inferior grande.
- Emojis y caracteres pictográficos en controles y leyendas, junto con Lucide.
- Gradientes, sombras, tamaños de letra pequeños y radios arbitrarios; transiciones aplicadas globalmente incluso sobre visualizadores.
- Ausencia de exportación científica común, figura limpia y controles coherentes de fullscreen.
- JSON presentado directamente en explicaciones; labels de comunidades densos y poco útiles a distancia.

## 3. Componentes compartidos creados

En `search-app/src/components/graph`:

| Componente | Responsabilidad |
|---|---|
| `VisualizationFrame` | Marco, fullscreen local al viewport, presets, Figure Mode, Escape y contención de foco |
| `GraphCanvas` | React Flow compartido, nodos, aristas, layouts, búsqueda/focus, labels, pesos y controles |
| `GraphLegend` / `TypeGlyph` | Leyenda derivada de tipos presentes y formas SVG |
| `AssetInspector` / `AssetViewer` | Inspector lateral colapsable y diálogo nativo de contenido |
| `ChartFrame` | Marco sobre gráficos SVG existentes, zoom/pan visual y exportación |
| `Explanation` | Markdown o estructura anidada recibida, con datos técnicos expandibles |
| `MethodDetails` | Descripciones verificadas en código existente |
| `visualSystem` | Tipos canónicos y metadatos visuales; no transforma los resultados |
| `figureExport` | Exportación SVG vectorial y rasterización PNG |

`useCanvasTheme` resuelve tokens CSS a colores concretos para Canvas. No es un segundo almacén de tema. Se retiraron las presentaciones duplicadas de nodos de Pathfinder/Serendipity y los paneles de assets de los tres visualizadores de caminos. Quedan helpers/imports históricos no utilizados en algunos componentes; su limpieza integral no es una refactorización funcional necesaria para este cambio.

## 4. Design system y tokens

Dirección: observatorio de conocimiento, superficies sobrias azul grisáceo, bordes definidos, controles compactos y jerarquía tipográfica. Tipografía local Segoe UI con fallback Source Sans 3/sans-serif, sin nueva dependencia de fuentes remotas.

| Token | Dark | Light / Paper |
|---|---|---|
| background | `#10161e` | `#fafbfc` |
| background-secondary | `#151e28` | `#f0f3f6` |
| surface | `#19232e` | `#ffffff` |
| surface-elevated | `#23313e` | `#edf1f5` |
| border | `#354554` | `#bcc8d1` |
| border-active | `#89b4ce` | `#2c6385` |
| text-primary | `#e9edf1` | `#1b2b38` |
| text-secondary | `#b8c6d1` | `#41576a` |
| text-muted | `#96a8b8` | `#536779` |
| accent | `#82b6d4` | `#285d7d` |
| success | `#80c6a7` | `#21674f` |
| warning | `#e4bc75` | `#845800` |
| danger | `#ec9292` | `#a9303c` |
| graph-edge | `#91a5b8` | `#586e81` |

Los nombres anteriores `bg-*`, `border-*`, `text-*` se conservan como aliases. Escala de radios 5/7/10/12 px. El nuevo marco usa espacios de 6/12/16/24 px y controles con altura mínima de 32 px. Se retiraron pictogramas emoji del código de presentación y se redujeron gradientes; el contenido del corpus o de IA no se filtra.

## 5. Sistema de nodos

Concept `#8974b5`, DigitalAsset/Document `#5289b5`, Person/Author `#bc7b51`, Book `#9c8051`, Image `#ad6e96`, Audio `#698f8d`, Video `#7c82ba`, Tag `#8b819f`, Event `#b18b45`; Location, Organization, Project, Device y Method también tienen entradas en el registro compartido. `Asset` es un alias exclusivamente visual de DigitalAsset. Tipos desconocidos conservan su nombre.

Tarjeta compacta de 200 px, tipo de 11 px y label de 14 px (16 en Presentation), borde semántico y hasta dos líneas visibles. Label completo en tooltip/inspector. Concept se identifica con círculo SVG, Person/Author con rombo y otras entidades con cuadrado más texto explícito de tipo. Canvas usa esas formas como siluetas. Selección añade un contorno, sin sustituir el color del tipo. Origen/destino se identifican por texto cuando están disponibles. No se asignan papeles por adivinar el orden del array.

## 6. Sistema de aristas

Relación normal continua; relación cuyo nombre identifica explícitamente Fuzzy, discontinua; recorrido Serendipity, punteado. No se deduce que una relación es fuzzy exclusivamente de un peso bajo. Peso cero se conserva. Grosor visual `1.5 + 2 × clamp(peso,0,1)`; el valor numérico no se normaliza ni reemplaza. Sin peso se utiliza solo un grosor de presentación. Las relaciones incidentes a la selección resaltan y las demás se atenúan. Las flechas se conservan cuando el renderer de origen las proporcionaba. No se inventa dirección para una conexión recibida sin ella. Se eliminaron animaciones permanentes en las aristas compartidas.

## 7. Visualizaciones y cobertura

| Vista | Cambio |
|---|---|
| Pathfinder | GraphCanvas, layouts Horizontal/Vertical/Radial/Auto, fullscreen, labels/pesos, exportación, inspector lateral |
| Serendipity | Mismo renderer; recorrido punteado; occurrences con IDs locales para no perder pasos repetidos; explicación estructurada |
| Saved Paths | Mismo renderer e inspector; layout automático inicial; explicación compartida |
| Árbol radial | Conserva posiciones iniciales y acción de navegación; marco y nodos compartidos |
| Puentes | Marco y renderer compartidos; datos/acciones anteriores |
| Búsqueda React Flow | Misma gramática visual y controles; callback original conservado |
| Búsqueda Canvas | Tokens, formas, zoom/fit, labels, fullscreen, Paper e inspector; PNG a resolución real |
| Comunidades | Nivo conservado; selección accesible por select, atenuación, focus nativo, zoom/pan, conceptos del grupo en panel y labels por nivel |
| Chord/heatmap/PageRank/pesos/abstractos/cobertura | Renderers originales dentro de ChartFrame, sin alterar sus series |
| Three.js | Fondo y líneas reaccionan al tema, colores de tipos compartidos; integración avanzada pendiente, ya que no es una vista activa |

## 8. Publicación y exportación

Screen conserva el tema global; Paper establece un ámbito claro independiente, suprime la trama del fondo de React Flow y mantiene la legibilidad. Presentation amplía labels del renderer compartido. Figure Mode ocupa el viewport y conserva el grafo y la leyenda; oculta navegación, toolbar, inspectores y controles. Escape sale; el botón de salida aparece al hover/foco y se excluye al imprimir. Fullscreen usa un contenedor fijo, no requiere permisos de la Fullscreen API.

React Flow: SVG compuesto con formas y texto nativos, sin `foreignObject` ni captura de HTML. Mantiene nodos, conexiones, posiciones, tipos, pesos y dirección disponible; reconstruye conectores rectos y no pretende reproducir exactamente las curvas/intersecciones del renderer. PNG rasteriza ese SVG a ×3, limitado a 8192 px en el lado mayor; admite fondo transparente. Labels largos se abrevian visualmente, con contenido completo en `<title>`. La selección no elimina nodos de la exportación.

Nivo/Recharts: se serializa el SVG actual con estilos computados, título y texto de leyenda cuando existe. Se conserva el dominio/datos del gráfico. El zoom/pan del contenedor no se convierte en recorte del archivo: se exporta el gráfico completo, salvo el focus nativo de Nivo. No se reemplazaron las librerías.

Canvas: PNG a su resolución real; no se anuncia SVG ni alta resolución que no genera. La alternativa vectorial es la vista React Flow existente. Three.js: no se añade exportación SVG, pues su escena WebGL no es vectorial.

## 9. Inspector, accesibilidad y movimiento

Hover ofrece identidad mínima, click abre inspector, Open Asset abre un diálogo amplio y Details expone metadata. Imagen, audio, video, texto y PDF aprovechan URLs y contenido ya recibidos; PDF depende del soporte del navegador y mantiene enlace de apertura. Audio/video permiten seek sobre timestamps literales `mm:ss` / `hh:mm:ss` existentes en el contenido; no se generan timestamps ni nuevas transcripciones. Las razones contextuales se derivan exclusivamente de relaciones incidentes, vecinos y pesos recibidos. No se produce ninguna explicación adicional con IA.

Foco visible, botones con nombres accesibles en controles nuevos, select de comunidades accesible por teclado, foco contenido en fullscreen y diálogo nativo, Escape y restauración de foco. Motion de estados de 180–220 ms; reduced-motion desactiva las transiciones CSS y duración de navegación de React Flow. Nivo comunidades deja de animarse. No se certifica accesibilidad WCAG completa: quedan controles históricos que requieren revisión específica.

## 10. Fórmulas verificadas y límites

Fuentes leídas, no modificadas: `backend/app/routers/analysis.py` (`analyze_communities`, `pathfind`) y búsqueda de fórmulas en `routers/explore.py`, `routers/search.py`, `routers/enrichment.py`.

- Pathfinder directo suma `1 - coalesce(weight,0.5)` y ordena por coste.
- Lateral suma coste por arista: 2 si `w > t`, 1.5 si `w < t - 0.3`, `1-w` en otro caso; más `0.5 log10(grado+1)` de cada Concept del camino.
- Topológico minimiza saltos; con umbral positivo exige peso mínimo y usa 1 como fallback en ese filtro. Las consultas admiten hasta 8 saltos.
- Comunidades Standard cuenta archivos compartidos; Fuzzy suma mínimos de pesos. Louvain utiliza ese peso proyectado. La respuesta está limitada a 12 comunidades y 25 miembros por comunidad: el frontend no recupera miembros adicionales ni cambia ese límite.
- No se publica una fórmula general de «fuzzy similarity» que mezcle ramas distintas de búsqueda/enriquecimiento. Una explicación completa por endpoint requiere una auditoría separada; no se inventó.

## 11. Validación y limitaciones restantes

- TypeScript y build de producción ejecutados. Lint de los componentes compartidos y useCanvasTheme sin errores. Vite advierte sobre el tamaño del bundle; se conserva la arquitectura de carga existente.
- Tres pruebas en `tests/figure-export.test.mjs`: escape XML del corpus, preservación de pesos cero/dirección/tipos y ausencia de mutación; visibilidad y transparencia; tipos desconocidos/pesos ausentes.
- Fixture local `tests/ui-fixture.html` sin llamadas a APIs: revisión en navegador de Paper, layout vertical, nodos, selección, evidencia contextual, Figure Mode, Escape y menú/generación PNG.
- Corregido durante QA: propagación de dimensiones de nodos controlados de React Flow, que inicialmente los dejaba invisibles.
- No se validaron end-to-end todos los medios del corpus ni resultados de servicios reales. La galería real no devolvió caminos visibles durante la revisión. La fixture es sintética y no es una ruta de producción.
- Persisten estilos inline históricos, callbacks/estados de selección de búsqueda que pueden mostrar información adicional a su inspector, controles antiguos sin nombres accesibles y palettes específicas de algunas gráficas. El sistema compartido cubre los caminos y los marcos; no equivale a una certificación de cada estado de cada pantalla.
- Exportación de grafos muy densos puede requerir layout manual: no se implementó un algoritmo nuevo de eliminación de colisiones. Presentation de charts Nivo no redefine automáticamente todas sus escalas tipográficas. El visor compartido no reemplaza todos los previews de listas/tablas de búsqueda.
- Comprobación de alcance con `git diff`: los cambios del trabajo se limitan a frontend, tests y estos documentos; no se alteraron backend ni contratos de API.
