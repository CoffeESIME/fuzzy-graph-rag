# Auditoría de recorridos — The Associative Engine

Fecha: 6 de octubre de 2026. Corpus local actual; sin cambios en Home, corpus, pesos ni Saved Paths.

## Dictamen

**A. CURRENT CORPUS IS SUFFICIENT**, para una demostración **acotada de varias rutas interpretables**, con procedencia mixta explícita. Recomiendo **Libre albedrío y responsabilidad ↔ Laberinto sin Salida**. Hay un camino corto literario, otro filosófico-musical y otro que atraviesa probabilidad, matemáticas y humor visual. Sus conexiones existen actualmente y sus fuentes son inspeccionables.

Esto **no** demuestra que bajar un umbral produzca automáticamente más diversidad semántica, ni que todos los vínculos hayan sido descubiertos automáticamente. La ruta matemática contiene una conexión manual y dos transferencias semánticas aprobadas mediante el explorador. La implementación actual tampoco garantiza rutas sin ciclos, alternativas semánticamente diversas ni respuestas rápidas. No recomiendo ampliar el corpus antes de corregir esas limitaciones de evaluación y presentación.

## 1. Mecanismos actuales, verificados en código

### Pathfinder

[Implementación](../../../backend/app/routers/analysis.py), `PathfinderRequest` y `pathfind`, líneas 314–577:

- Recorre relaciones **sin dirección ni filtro de tipo**, con un límite de **8 saltos**. `k_paths` se limita a 1–10; el valor inicial es 3. No es Yen ni otro algoritmo especializado de k caminos simples: enumera patrones Cypher, ordena y toma `LIMIT k`.
- **Direct:** minimiza `Σ(1 − peso)`. Un peso ausente se sustituye por 0.5. Esto busca menor coste, **no menor número de saltos**. Una arista de peso 1 cuesta cero: añadirla no penaliza longitud. Se observaron recorridos que repiten nodos y dos resultados con idéntica secuencia de nombres por relaciones paralelas.
- **Lateral:** suma un coste por arista de 2 si `w > t`, 1.5 si `w < t − 0.3`, y `1 − w` en el intervalo. Añade `0.5 × log10(grado + 1)` por cada nodo Concept del recorrido. Con `t=0.85`, favorece la banda 0.55–0.85. **No es un corte alfa** y no elimina las relaciones exteriores a esa banda.
- **Topological, umbral 0:** `allShortestPaths`, hasta k resultados de longitud mínima. No busca después rutas más largas si solo existe una mínima.
- **Topological, umbral >0:** exige `coalesce(toFloat(weight),1) ≥ α` para todas las aristas, ordena por saltos y toma k. Aquí sí hay un corte alfa. Puede devolver caminos más largos después del mínimo.
- No hay penalización por solapamiento entre rutas ni evaluación de diversidad semántica. La penalización de hubs es por ruta, no entre alternativas. No hay desempate estable explícito.
- La respuesta **fusiona** nodos y aristas de todos los resultados, descarta `totalCost` y la pertenencia/orden por ruta. `path_length` es el **máximo** de saltos entre las rutas encontradas. Deduplica aristas por origen, destino y tipo, no por identidad de relación.

La [UI Pathfinder](../../../search-app/src/components/analysis/PathfinderCard.tsx) permite elegir modo, k y los dos umbrales; muestra el grafo combinado. Por tanto, ya admite múltiples resultados para los mismos extremos, pero no conserva una comparación explícita ruta por ruta.

### Serendipity

[Código](../../../backend/app/routers/analysis.py), líneas 580–708: elige aleatoriamente un Concept con alguna relación entrante de un DigitalAsset de peso <0.9. Busca exactamente:

`Concept → Asset → Concept → Asset → Concept`

Exige conceptos y activos distintos y al menos una arista ≤0.79. Ordena candidatos por `rand() × exp(−0.015 × grado_del_concepto_intermedio)` y devuelve uno. Es una selección aleatoria de un patrón de cuatro saltos, no una caminata general ni una comparación de extremos elegidos. No expone control alfa ni k; descarta el score aleatorio y los tipos de relación al responder. El campo llamado `mock_data` contiene resultados de Neo4j, no datos simulados, en esta implementación.

### Búsqueda difusa y pesos

La [búsqueda Graph Fuzzy](../../../backend/app/routers/search.py), desde línea 887, parte de activos recuperados semánticamente. Filtra la primera relación por α y el producto de dos relaciones por α para descubrir otros activos. El score combina relevancia de la semilla, pesos, una penalización 0.3 a relaciones estructurales y `exp(−0.015 × grado)` del hub. Este α tiene semántica distinta del mínimo por arista de Pathfinder. No se ejecutaron embeddings ni llamadas a modelos en esta auditoría.

Los pesos son propiedades `weight` de relaciones Neo4j y tienen varios orígenes:

1. Extracción: el modelo propone `confidence` y `reasoning` con una [rúbrica](../../../backend/worker/prompts.py). La [promoción de Inbox](../../../backend/app/routers/inbox.py) convierte ese valor en peso. Algunas fusiones suman contribuciones y saturan en 1; otras conservan el máximo. Un peso alto puede reflejar agregación, no mayor sustento documental.
2. [Enriquecimiento de pesos](../../../backend/app/routers/enrichment.py): mezcla el peso actual con similitud coseno normalizada entre 0.15 y 0.75; la proporción es configurable. Protege `CREATED_BY`, `DEFINES` y `LOCATED_AT`.
3. Existe una función de [actualización incremental](../../../backend/worker/tasks.py), `apply_incremental_fuzzy_weight`, que propone `0.75 × base + 0.25 × similitud`; no equivale exactamente a la normalización anterior. No se encontraron llamadas a esta función en el repositorio: no se asume que esté activa ni que explique los pesos actuales.
4. [Explorador de relaciones](../../../backend/app/routers/explore.py), `approve_latent_connection`: persiste conexiones aprobadas con `source=interactive_latent_explorer`. Puede representar transferencia semántica o conexión manual. También existe `enrichment_llm`.

Ninguno de estos mecanismos establece probabilidades de verdad. La misma escala contiene procedencias y cálculos distintos; no es una medida homogénea calibrada.

Tipos actuales: `EVOKES` (asociación evocada), `EXPLORES` (tema desarrollado), `DEFINES` (definición), `EVOKES_CONCEPT` (vínculo conceptual usado también en fusiones y exploración), `CREATED_BY`, `MENTIONS`, `DEPICTS`, `LOCATED_AT`, `PARTICIPATED_IN`, `MENTIONS_PROJECT`, `MENTIONS_EVENT` y `HAS_INBOX_ITEM`. Son etiquetas de extracción/almacenamiento, **no garantías** de contenido. Los recorridos invierten libremente su dirección; compartir autor o género no constituye por sí solo una analogía. `HAS_INBOX_ITEM` es una relación operativa, también admitida por el patrón sin filtro de Pathfinder.

### Qué conservan Saved Paths

Los JSON se descargan desde el navegador. La API lista/lee archivos de `backend/data/saved_paths`; estos handlers no implementan persistencia automática de las descargas. Véanse los exports en [PathfinderCard](../../../search-app/src/components/analysis/PathfinderCard.tsx), [SerendipityCard](../../../search-app/src/components/analysis/SerendipityCard.tsx) y los handlers al final de [analysis.py](../../../backend/app/routers/analysis.py).

| Campo | Pathfinder | Serendipity |
|---|---|---|
| Extremos | IDs y etiquetas explícitos | Primer/último nodo |
| Intermedios | Unión de nodos; orden por ruta perdido | Secuencia ordenada |
| Tipos/pesos de aristas | Sí, pesos redondeados | Peso entrante por paso, redondeado a 2 decimales; tipo perdido |
| Modo | Sí | `tool=serendipity_path` |
| Parámetros | Umbral lateral y privacidad | Privacidad |
| k, corte topológico, versión algoritmo | No | No |
| Fuentes | Nombre, hash, MIME cuando existen | Nombre, hash, MIME cuando existen |
| Timestamp | Exportación | Campo `generated_at`, asignado al exportar |
| Score por ruta | No | No |
| Notas/etiqueta curatorial | No hay campo dedicado | No hay campo dedicado |
| Explicación | Texto LLM opcional | Texto LLM opcional |

La explicación LLM guardada es interpretación, no prueba documental ni registro completo de procedencia. IDs `elementId` tampoco garantizan identidad estable después de reconstruir una base.

## 2. Inventario y vigencia

[Inventario estructurado de los 50 archivos](saved-inventory.json). La copia tabular generada se excluye del repositorio para evitar duplicar estos datos.

- **24 Pathfinder + 26 Serendipity**, agrupados en **36 pares exactos** no dirigidos; **9 pares repetidos**.
- Snapshot actual: **3,403 nodos y 5,967 relaciones**. Incluye 1,630 conceptos, 457 activos y 456 nodos InboxItem. Los activos incluyen 260 textos, 88 audios, 108 imágenes y uno sin MIME. No hay video identificado por MIME en este snapshot.
- 39 archivos conservan coincidencia actual para todas sus aristas; 11 tienen al menos una referencia sin coincidencia. Son **27 referencias de arista** contando repeticiones entre archivos, no 27 aristas únicas necesariamente. No puede atribuirse automáticamente a borrado: pueden haber cambiado IDs o tipos por fusiones.
- Una diferencia adicional supera la tolerancia de redondeo de 0.011: el archivo `...vida_despu_s...1772952009617.json` conserva 0.899 donde la relación actual vale 1.0.
- Se conservan los SHA-256 de cada archivo; los originales no fueron modificados.

| Par repetido | Archivos | Modos |
|---|---:|---|
| Libre albedrío y responsabilidad ↔ Laberinto sin Salida | 5 | Topológico, directo, lateral ×2, Serendipity |
| Ambientalismo ↔ François de La Rochefoucauld | 3 | Directo, lateral ×2 |
| Espécimen ↔ Ich verlasse heut' dein Herz | 3 | Directo ×2, lateral |
| Células y Biología Celular ↔ Comunicación Industrial | 2 | Directo/lateral |
| Ciclos Temporales y Naturales ↔ Lógica Difusa | 2 | Directo/lateral |
| Inmortalidad ↔ Automatización y Control de Sistemas | 2 | Directo/lateral |
| Misticismo, Esoterismo y Fenómenos Espirituales ↔ Automatización y Control de Sistemas | 2 | Directo/lateral |
| Sepultura – Territory ↔ François de La Rochefoucauld | 2 | Directo/lateral |
| Tagore ↔ Volcán en erupción | 2 | Directo/lateral |

Los dos registros laterales de Ambientalismo repiten el mismo subgrafo; los dos directos de Espécimen también. Los dos laterales de libre albedrío son una unión con varias alternativas y un subconjunto de una sola ruta, no dos descubrimientos independientes.

**Extremos cercanos y regiones:** Aislamiento y Soledad llega a Miseria existencial vía Hipocresía social y The Smiths, y a Crítica a Internet vía Pérdida de Identidad y Bad Religion. Otro Serendipity llega a esa misma crítica desde Soledad del preso político, vía Rancid y Control y Poder. Son regiones relacionadas por una lectura humana, no endpoints equivalentes certificados. Inmortalidad, Misticismo y Vida después de la Muerte comparten destinos de control/comunicación industrial. En libre albedrío, Serendipity y Pathfinder topológico reproducen **exactamente la misma ruta**, así que cambiar de herramienta no demuestra diversidad por sí solo.

## 3. Pruebas sobre el corpus actual

Se ejecutaron **24 consultas**, extrayendo el Cypher activo del código sin cambiar su lógica: cuatro pares × topológico, directo, lateral y cortes 0.8/0.6/0.4; k=3. Se conservaron los registros individuales antes de la fusión del API. **11 terminaron; 13 agotaron el límite de auditoría de 20 segundos**. La aplicación permite 300 segundos: estos timeouts no prueban inexistencia de caminos ni fracaso con el timeout completo. No se ejecutaron consultas de escritura ni explicaciones LLM.

[Consultas, tiempos, errores y rutas](live-pathfinder-probes.json) · [script reproducible](probe.py).

Para separar el coste de enumeración de la existencia de rutas, se hizo además un corte alfa sobre el snapshot completo, con las mismas aristas y pesos y búsqueda de caminos mínimos simples no dirigidos de hasta 8 saltos. Se distinguen estos **resultados calculados sobre el snapshot actual** de las **salidas del Cypher de Pathfinder**. Al comprobar existencia por secuencia de nodos, se representa cada par de nodos por su arista calificante de mayor peso; no se cuentan variantes de aristas paralelas como diversidad.

[Cortes alfa independientes](snapshot-thresholds.json) · [enumeración completa de 22 rutas simples de hasta 6 saltos del candidato principal](canonical-six-hop-routes.json). El mínimo de pesos que se informa abajo es un diagnóstico de supervivencia al corte, **no un score nativo guardado**.

## 4. Candidatos y rutas reales

Todas las rutas de esta sección son **REAL CURRENT CORPUS RESULT**. Los nombres breves de fuentes entre corchetes son alias editoriales de los activos identificados abajo, no nodos nuevos.

### Candidato 1 — Libre albedrío y responsabilidad ↔ Laberinto sin Salida

**Corto/topológico, 4 saltos; también Serendipity guardado:**

`Libre albedrío y responsabilidad → [Goethe, 001fdf7f] → Autodestrucción → Metallica – Master of Puppets → Laberinto sin Salida`

Pesos: **0.70, 0.90, 0.90, 0.70**. La propia responsabilidad y la autodestrucción llevan a una metáfora musical de pérdida de control.

**Alternativa lateral filosófico-musical, 6 saltos; salida actual lateral t=0.85:**

`Libre albedrío y responsabilidad → [Séneca, 9b95204d] → Condición Humana → Haggard – Awaking the Centuries → Desesperación → Metallica – Master of Puppets → Laberinto sin Salida`

Pesos: **0.85, 1.00, 0.80, 0.695, 0.85, 0.70**. Pasa de una reflexión sobre elección y condición humana a imágenes apocalípticas y desesperación. Coste lateral nativo: **5.005907584290718**.

**Lateral matemática/visual, 6 saltos; salida actual lateral t=0.85:**

`Libre albedrío y responsabilidad → [Transcripción Markov–Nekrasov, d1d2577c] → Matemáticas → [Meme de autovalores, FB_IMG_1743639238757.jpg] → Desesperación → Metallica – Master of Puppets → Laberinto sin Salida`

Pesos: **0.865, 0.783, 0.763, 0.621, 0.85, 0.70**. La discusión del libre albedrío en probabilidad llega al humor de perder el control al estudiar matemáticas y después al texto musical. Coste lateral: **5.250854373921332**. Los resultados segundo y tercero del Cypher repiten esta secuencia mediante variantes de relaciones: se cuenta como **una sola interpretación**.

Las dos rutas largas comparten el tramo final, pero sus primeros cuatro saltos atraviesan fuentes y ámbitos distintos. La conexión matemática no es una inserción decorativa en el mismo relato.

**Control: “directo” ponderado no es la ruta obvia.** El menor coste observado, 0.491, devuelve 8 saltos: Séneca → Mortalidad → Slayer – Unit 731 → Slayer → **Unit 731 de nuevo** → Thrash Metal → Master of Puppets, entre los mismos extremos. Un tercer resultado pasa por Ride the Lightning y Metallica. Son puentes de autor/género, con coste cero en varias aristas; no los recomiendo como interpretación fuerte. El camino de cuatro saltos tiene coste directo derivado 0.8: ser más corto no lo hace ganador ponderado.

### Candidato 2 — Ciclos Temporales y Naturales ↔ Lógica Difusa

**Directo ponderado, 8 saltos, coste 0; salida actual:**

`Ciclos Temporales y Naturales → [Transcripción calendario, 27058fbf] → Cosmología y Astronomía → [Ensayo Eppur Si Muove, 7e7470ec] → Isaac Newton → [Ensayo Leibniz/Voltaire, b28471b0] → Automatización y Control de Sistemas → Screenshot 2026-02-24 104006.png → Lógica Difusa`

Los ocho pesos son **1.0**. Sus tres variantes superiores cambian una captura o un texto cercano; no son tres regiones semánticas distintas.

**Lateral, 6 saltos, coste 4.94101447721026; salida actual:**

`Ciclos Temporales y Naturales → [Transcripción calendario] → Virtud → [Du Châtelet, d6544adc] → Lógica → Screenshot 2026-02-24 142603.png → Lógica Difusa`

Pesos: **1, 0.8, 0.8, 0.718, 0.803, 0.802**.

**Lateral distinta, 8 saltos, coste 5.716972775494078; salida actual:**

`Ciclos Temporales y Naturales → [Emerson sobre estaciones, dab32400] → Símbolo → [Emerson sobre física y ética, 83b6af8d] → Física → Haggard – The Observer → Lógica → Screenshot 2026-02-24 142603.png → Lógica Difusa`

Pesos: **1, 0.842, 0.828, 0.808, 0.845, 0.811, 0.803, 0.802**.

Hay diversidad literaria/científica real. Sin embargo, la interpretación exige explicar muchas conexiones y el camino mínimo actual usa otro texto, `96aa4e98`, que equipara cognición analógica, embeddings y lógica difusa sin aportar validación en el activo. No debe usarse ese contenido como prueba de la tesis del proyecto. La fuente de Du Châtelet habla de virtud y razón; eso hace investigable la asociación con Lógica, pero no prueba una relación técnica con lógica difusa. **No recomendado como ejemplo principal.**

### Candidato 3 — Inmortalidad ↔ Automatización y Control de Sistemas

**Corte alto α=0.9, 6 saltos; verificación sobre snapshot actual:**

`Inmortalidad → text_173d7547.txt → Poesía → Rancid – Arrested in Shanghai → Punk → [Ensayo Espécimen, 20df6016] → Automatización y Control de Sistemas`

Pesos: **0.9, 0.919, 0.9, 1, 1, 1**. Es uno de cuatro mínimos distintos a ese corte, verificado sobre aristas actuales. No se presenta como salida del API ni como ganador ponderado: esa consulta agotó el tiempo. Los otros tres están en `snapshot-thresholds.json`. El puente de género Punk requiere especial cautela: compartir género no explica por sí solo una relación entre inmortalidad y automatización.

**Alternativas actuales de 4 saltos; salida topológica del Cypher:**

- `Inmortalidad → Nach – Mil Vidas → Opresión e Injusticia → [Ensayo Espécimen, 20df6016] → Automatización y Control de Sistemas` — **0.8, 0.861, 0.787, 1**.
- `Inmortalidad → Nach – Mil Vidas → Rebeldía y Revolución → [Ensayo Espécimen, 20df6016] → Automatización y Control de Sistemas` — **0.8, 1, 1, 1**.
- `Inmortalidad → Nach – Mil Vidas → Libertad → [Ensayo Laplace, 4241fa5d] → Automatización y Control de Sistemas` — **0.8, 0.877, 0.867, 0.9**.

Las dos primeras son variantes próximas del mismo relato. La tercera cambia de fuente y región. Los ensayos ya hacen explícitos puentes entre música, control, filosofía y ciencia; no se conoce aquí su autoría o independencia editorial. Demuestra asociaciones presentes en el corpus, pero no permite atribuir esa síntesis a la recuperación. Los directos y laterales actuales no terminaron en 20 segundos; los guardados no se presentan como rankings actuales. **No recomendado como ejemplo principal.**

### Comparación con el ejemplo actual de Home

Para **Aislamiento y Soledad ↔ Crítica a Internet y la Era Digital**, el mínimo actual tiene solo dos saltos:

- vía **Bad Religion – I Love My Computer**: **1.0, 0.85**;
- vía **The Motorleague – Everyone Is Digital**: **0.7, 0.7999**.

El recorrido de Home pasa por ambos audios y Pérdida de Identidad, pero permanece en una misma región temática. Es legible y está respaldado; por sí solo muestra menos diversidad que comparar literatura, filosofía/música y matemáticas/humor entre extremos fijos. La auditoría no cambia esa tarjeta.

## 5. Fuentes y procedencia del candidato recomendado

Se recuperaron **28 previews de activos**, se verificó acceso HTTP 200 a los 28 objetos originales y se leyeron los textos relevantes. Para audio se inspeccionó la transcripción disponible, no se realizó una nueva escucha/transcripción. Se abrió y examinó visualmente el meme de autovalores. La autenticidad bibliográfica de las atribuciones de Tumblr no se verificó externamente.

[Previews, textos disponibles y rutas de almacenamiento](source-previews.json). No se guardaron URLs firmadas ni credenciales. Las propiedades exactas de cada arista —IDs, tipo, peso, reasoning, source y fechas cuando existen— están en [los resultados actuales](live-pathfinder-probes.json).

| Transición | Evidencia y evaluación |
|---|---|
| Libre albedrío ↔ Goethe (0.70) ↔ Autodestrucción (0.90) | El texto atribuido a Goethe trata a la persona como causa de su propia expulsión del paraíso. Respalda una lectura de responsabilidad/autodestrucción; es interpretación metafórica, no una definición literal ni atribución autenticada. |
| Autodestrucción ↔ Master of Puppets (0.90) | La transcripción trata pérdida de control y autodestrucción. El título y la interpretación popular no sustituyeron la inspección de la transcripción. |
| Libre albedrío ↔ Séneca (0.85) ↔ Condición Humana (1.00) | El activo contiene explícitamente elección, responsabilidad y condición humana. Se trata de un fragmento sobre la muerte; el camino no constituye una recomendación normativa. |
| Condición Humana ↔ Haggard (0.80) ↔ Desesperación (0.695) | El reasoning señala humanidad, destrucción, oscuridad y muerte; la transcripción contiene ese contexto. Desesperación es una inferencia temática plausible, no un hecho medido. |
| Libre albedrío ↔ transcripción Markov/Nekrasov (0.865) | `source=interactive_latent_explorer`, reasoning de conexión manual. La transcripción sí describe la disputa sobre si la probabilidad fundamenta libre albedrío/religión: buena sustentación local, **procedencia manual**. |
| Transcripción ↔ Matemáticas (0.783) | Transferencia semántica aprobada desde otra imagen, con similitud declarada 65%. La lectura del documento confirma contenido matemático explícito. Ese 65% no es la probabilidad de que el vínculo sea verdadero. |
| Matemáticas ↔ meme (0.763) | Transferencia semántica aprobada, similitud declarada 56%. La imagen realmente muestra autovalores, autovectores y una ecuación: evidencia visual independiente del reasoning. |
| Meme ↔ Desesperación (0.621) | Reasoning basado en expresión facial y pérdida de control de la propia vida. La imagen confirma el chiste. Es una asociación débil e interpretativa, no diagnóstico psicológico. |
| Desesperación ↔ Master of Puppets (0.85) ↔ Laberinto sin Salida (0.70) | El reasoning de extracción y la transcripción sostienen desesperación y metáfora de laberinto. El último concepto proviene de esa metáfora, no de un laberinto físico. |

Hashes/fuentes principales: Goethe `001fdf7f…`, Séneca `9b95204d…`, transcripción `d1d2577c…`, Haggard `b6faf6e0…`, Master of Puppets `379716c7…`. Los hashes completos y nombres están en los JSON e inventario. En aristas sin `source`, el contenido de `reasoning` y el código son compatibles con extracción, pero **no reconstruyen con certeza todo el historial de revisiones**. No se atribuye automáticamente su peso actual a un único modelo.

## 6. Qué demuestran realmente los umbrales

### El mínimo no cambia automáticamente de relato

Comprobación independiente del snapshot, hasta 8 saltos:

| Par | α=0.9 | α=0.8 | α=0.6 | α=0.4 |
|---|---|---|---|---|
| Libre albedrío ↔ Laberinto | Sin camino | Sin camino | Mismo mínimo de 4 saltos | Mismo mínimo de 4 saltos |
| Aislamiento ↔ Crítica a Internet | Sin camino | 1 mínimo de 2 saltos | 2 mínimos de 2 saltos | Los mismos 2 |
| Ciclos ↔ Lógica Difusa | 3 mínimos de 6 saltos | 1 mínimo de 4 saltos | El mismo mínimo | El mismo mínimo |
| Inmortalidad ↔ Control | 4 mínimos de 6 saltos | 7 mínimos de 4 saltos | 9 mínimos de 4 saltos | Los mismos 9 |

Las consultas Cypher a 0.6/0.4 agotaron el límite; estas celdas se basan en el snapshot, **no en respuestas exitosas de esas consultas**. Un corte menor amplía el conjunto permitido; no obliga al selector de mínimos a mostrar las novedades.

### Supervivencia de las tres rutas elegidas

Todas comparten la llegada al laberinto con peso 0.70. Por eso **no existe una ruta convencional de peso mínimo ≥0.8** para este par. No sería honesto dibujar una.

| Corte α | Rutas seleccionadas que sobreviven | Total de secuencias simples ≤6 saltos |
|---|---|---:|
| 0.80 | Ninguna | 0 |
| 0.70 | Corta literaria | 9 |
| 0.695 | Corta + filosófico-musical | 11 |
| 0.65 | Las anteriores | 21 |
| 0.621 | Las anteriores + matemática/visual | 22 |
| 0.60 / 0.40 | Las mismas tres | 22 |

Los recuentos son exhaustivos **solo para rutas simples de hasta seis saltos y secuencias de nodos**, no para todos los recorridos de ocho saltos del API. No se eliminó ninguna arista del corpus: el filtrado ocurrió en memoria.

En 0.65 aparecen muchas variantes de Mortalidad/Nihilismo que no deben contarse como nuevos relatos independientes. También existe una alternativa actual no elegida por el top-3 lateral: transcripción Markov/Nekrasov → Determinismo y Ausencia de Libre Albedrío → Bad Religion – Shattered Faith → Nihilismo → Master of Puppets. Está registrada como **ruta del snapshot**, pendiente de una revisión de fuentes equivalente a las tres recomendadas. No se la presenta como salida del API ni como un cuarto ejemplo validado.

**Frontera de ruido:** no se establece un α universal. Entre 0.695 y 0.65 crece sobre todo la redundancia temática, pero a 0.621 aparece la ruta matemática, que sí añade una región interpretable. Por debajo de 0.621 no aparecen nuevas secuencias en este ensayo de seis saltos. Eso es saturación de esta muestra, no prueba de que toda relación inferior sea ruido. La corrupción de pesos y los ciclos son problemas distintos de la debilidad semántica.

## 7. Comparación cualitativa y límites

Las valoraciones siguientes son juicio editorial tras inspeccionar las fuentes indicadas, no métricas calculadas ni validación externa.

| Candidato | Directitud del mínimo | Sorpresa lateral | Coherencia | Diversidad | Valor del peso difuso | Explicabilidad | Calidad/procedencia de fuentes | Valor de demo |
|---|---|---|---|---|---|---|---|---|
| Libre albedrío ↔ Laberinto | Media | Alta | Media–alta | Alta entre las tres elegidas | Alto para habilitar rutas; selector limitado | Alta localmente | Media: fuentes accesibles, atribuciones/revisiones incompletas | Alto con contexto sensible |
| Ciclos ↔ Lógica Difusa | Media | Alta | Media | Alta | Medio | Media | Media–baja: ensayos sin autoría comprobada y afirmaciones fuertes | Medio |
| Inmortalidad ↔ Control | Baja | Alta | Media | Media | Medio | Media | Media–baja: puentes ya narrados en ensayos | Medio–bajo |
| Aislamiento ↔ Crítica a Internet | Alta | Baja–media | Alta | Baja | Bajo–medio | Alta localmente | Media | Alto en legibilidad, bajo en contraste multipath |

Limitaciones comprobadas:

- **Corpus multimodal pero sesgado:** predominan textos, música y memes; las tres rutas recomendadas convergen en un mismo audio. No prueban generalización a otros corpus.
- **Historial parcial:** 5,059 relaciones no tienen propiedad `source`; 904 declaran `interactive_latent_explorer` y 4 `enrichment_llm`. Hay `reasoning` en 4,878 relaciones, pero una justificación textual no sustituye el historial del cálculo del peso.
- **Calidad numérica:** 44 pesos se almacenan como strings; 5 son malformados, por ejemplo concatenaciones `1.01.0` y `0.90.9`. No se corrigieron. La conversión `toFloat` puede dar null; el ensayo alfa independiente los excluyó como hace ese predicado.
- **Pesos fuertes no siempre son evidencia fuerte:** agregación, fusiones y aristas de autor/género favorecen cadenas de coste cero. La escala necesita auditoría de procedencia.
- **Duplicados/ciclos:** k resultados no equivale a k interpretaciones. Se observaron repeticiones de nodos y variantes por relaciones paralelas.
- **Saved Paths pierde información:** no conserva pertenencia a rutas, costes, k, corte topológico ni versión del método. Sus explicaciones pueden convertir asociaciones en afirmaciones demasiado categóricas.
- **Fuentes intermedias ya sintetizan puentes:** varios ensayos actuales conectan de manera explícita ciencia, música y filosofía. No se determinó cómo se redactaron; no se afirma que sean generados ni que su presencia invalide el corpus, pero dificultan atribuir la síntesis al algoritmo.
- **Acceso no es autenticidad:** objetos originales disponibles y transcripciones legibles no certifican citas, letras, autores ni exactitud histórica. El texto `96aa4e98` contiene afirmaciones sobre cognición que no deberían trasladarse al relato del sistema.
- **Sensibilidad editorial:** el candidato principal contiene autodestrucción, referencias a muerte y pérdida de control. Sirve para investigación y evaluación; su idoneidad como portada general debe decidirse aparte de su mérito técnico.

## 8. Recomendación operativa

Conservar **Libre albedrío y responsabilidad ↔ Laberinto sin Salida** como ejemplo canónico de investigación, con las tres rutas revisadas y sus fuentes, **sin cambiar Home todavía**. Frente a una demo convencional, mostrar solo la ruta corta enseña conectividad; la comparación revela tres formas documentables de atravesar responsabilidad, condición humana y pérdida de control, incluyendo un desvío matemático/visual que la ruta mínima no muestra.

Antes de publicarlo como demostración interactiva:

1. Preservar secuencias, IDs de arista, parámetros, costes y snapshot/versiones por ruta; identificar claramente conexiones manuales y transferidas.
2. Separar “más corto”, “menor coste ponderado” y “lateral”; no llamar fuerte a un camino solo por ser mínimo ni comparar costes de modos diferentes como una misma escala.
3. Evitar ciclos y contar variantes semánticas después de deduplicar; excluir relaciones operativas del selector y revisar pesos malformados, **en una tarea posterior autorizada**.
4. Mostrar qué rutas habilita cada corte junto a las que efectivamente devuelve el ranking. La selección lateral y el corte alfa responden a preguntas distintas.
5. Mantener una evaluación humana de cada transición con acceso a fuente y procedencia. No usar la explicación generada como evidencia de sí misma.

**No se propone expansión en esta fase:** la conclusión A se limita a que ya existe material suficiente para esta comparación verificable. No se afirma que la hipótesis general de diversidad creciente esté demostrada. Añadir documentos ahora podría ocultar problemas del selector que se pueden estudiar con los datos actuales.

## Evidencia y reproducción

- [Snapshot Neo4j](current-graph.json): nodos y relaciones con propiedades; lectura en transacción sin escritura.
- [Inventario JSON](saved-inventory.json): los 50 archivos, endpoints, unión/secuencia, aristas, pesos, parámetros, fuentes, timestamps y hashes.
- [Pruebas del Cypher actual](live-pathfinder-probes.json): 24 intentos, con errores conservados.
- [Cortes alfa](snapshot-thresholds.json) y [22 rutas cortas del candidato](canonical-six-hop-routes.json): cálculos independientes sobre evidencia actual, no simulaciones ni respuestas del API.
- [Inspección de fuentes](source-previews.json): previews y originales de texto disponibles; no incluye URLs firmadas.

Scripts de auditoría: `audit.py`, `probe.py`, `thresholds.py`, `diversity.py`, `sources.py`. Se ejecutan desde la raíz con Python y las dependencias locales `neo4j`, `python-dotenv`, `networkx` y `requests`. Usan el servicio local y la configuración de desarrollo sin imprimir credenciales. Reejecutar cambia los artefactos de evidencia, no el corpus. El snapshot y el inventario deben capturarse antes de los análisis dependientes. Las consultas de Pathfinder no tienen desempate estable, por lo que rankings empatados pueden variar.
