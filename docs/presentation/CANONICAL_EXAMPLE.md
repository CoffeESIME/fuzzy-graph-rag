# Curaduría del ejemplo público

La presentación describe comportamientos existentes. No modifica búsquedas,
selección de rutas, pesos, corpus ni Serendipity. La elección es editorial;
no se basa en el menor coste ni demuestra validez general del sistema.

## Comparación y recomendación

| Candidato | Home | README / demo | Ejemplo técnico |
|---|---|---|---|
| A · Libre albedrío y responsabilidad ↔ Laberinto sin Salida | No como portada | Reserva para una audiencia informada | **Principal:** cruza literatura, filosofía/música y matemáticas/imagen |
| B · Astrónomo ciego ↔ Guerra | Secundario | **Demo secundaria:** matices después de un tronco compartido | Útil para distinguir registros y secuencias |
| C · Astrónomo ciego ↔ Abandono de lo superficial | **Principal** | **Demo principal:** registros 1 y 3 | Permite contrastar relaciones explícitas, inferidas y enriquecidas |

| Criterio | A | B | C |
|---|---|---|---|
| Comprensión inmediata | Extremos abstractos; necesita contexto | Extremos reconocibles, vínculo poco evidente | Extremos evocadores y pregunta fácil de formular |
| Claridad visual | Dominios divergentes; unión densa | Tronco inicial largo; divergencia posterior | Dos ramas condensables y convergencia visible en Amor |
| Diversidad conceptual | La más marcada entre dominios | Resignación, Esperanza, Salud y Enfermedad, Autenticidad | Ausencia/duelo o tristeza/resignación; varias rutas comparten conceptos |
| Procedencia | Incluye relaciones manuales/enriquecidas | Seis relaciones únicas con marcador de enriquecimiento | Dos relaciones únicas con marcador de enriquecimiento; una aparece en la rama pública 3 |
| Sensibilidad | Autodestrucción, desesperación, pérdida de control | Guerra; algunos títulos y fuentes requieren contexto | Duelo y muerte; Metallica y Warcry también contienen material sensible |
| Explicación requerida | Alta | Media-alta | Media: el gráfico reducido sirve de entrada, no sustituye las fuentes |
| Primera visita | Mejor después de aprender a leer rutas | Mejor como contraste posterior | Mejor punto de entrada, sin presentarlo como ejemplo libre de temas difíciles |

C conserva la prioridad del addendum. No hay un fallo de procedencia que
impida mostrarlo como exploración, siempre que se explicite el origen
enriquecido de una relación. Su menor carga en los extremos no elimina la
sensibilidad de los archivos intermedios.

## Evidencia revisada

Se leyeron los exports originales y se consultó Neo4j en modo lectura, sin
ejecutar nuevas búsquedas de rutas ni generar contenido. Los IDs, etiquetas,
extremos de relaciones, tipos y pesos coincidieron con el grafo consultado.
Los siguientes archivos se encuentran en `backend/data/saved_paths/`:

| Candidato | Archivo | Registros / secuencias | Nodos / relaciones únicos verificados |
|---|---|---|---|
| A | `pathfinder_libre_albedr_o_y_responsabilidad_to_laberinto_sin_salida_1791345427661.json` | 5 / 4 | 15 / 18 |
| B | `pathfinder_astr_nomo_ciego_to_guerra_1791346817628.json` | 5 / 4 | 15 / 18 |
| C | `pathfinder_astr_nomo_ciego_to_abandono_de_lo_superficial_1791347443292.json` | 5 / 5 | 14 / 17 |

SHA-256 de los exports revisados:

```text
A d766813365e32d1e819e3f3283bb775fe4a38ad1bad8ccbb0e6f07687ff5219f
B 980c41f0e3daa610e657d50cbf2a3682327014113ea45c4bd916ea1405a91a00
C a7e0a6b95f8f5d4104599b51d611b3dda6c3c9bf0d2f4ab7867d872abbd14df0
```

En A, el resultado actual también incluye una ruta por David Bowie y Legado.
No debe confundirse con el fixture anterior de tres rutas procedentes de dos
consultas. En B, los registros 1 y 2 repiten la secuencia de nodos. En C,
las cinco secuencias tienen ocho saltos; los registros 1 y 2 difieren por el
archivo musical, pero su condensación conceptual es la misma. Cinco
secuencias no significa cinco interpretaciones independientes.

La revisión de fuentes para publicación se concentró en los registros 1 y 3
de C: previews locales de los cinco activos y lectura de los tres textos
originales (HTTP 200). Para las canciones se revisó el texto asociado, no se
realizó una nueva transcripción ni una escucha crítica. A y B se compararon
estructuralmente y por procedencia registrada; no se certifica aquí cada
atribución bibliográfica de sus fuentes.

## Los dos recorridos públicos, completos

**Registro 1 · `route-1-c39324b8f0ea`:** Astrónomo ciego → texto atribuido a
Mia Couto (`text_Tumblr_Post_-_159517803909html_a0cc15b3.txt`) → Ausencia →
texto atribuido a Albert Caraco (`text_2ee2a56e.txt`) → Duelo y Pérdida →
Warcry — Capitán Lawrence → Amor → texto atribuido a Tagore / Gitanjali
(`text_Tumblr_Post_-_190221726333html_c6ac4846.txt`) → Abandono de lo superficial.

**Registro 3 · `route-3-bf6db450d548`:** Astrónomo ciego → el mismo texto de
Mia Couto → Tristeza y Melancolía → Metallica — Fade To Black → Resignación →
Warcry — Capitán Lawrence → Amor → el mismo texto de Tagore → Abandono de lo superficial.

La Home conserva conceptos de estos dos registros y omite los DigitalAssets.
Cada línea punteada resume **dos relaciones a través de un archivo**, no una
arista directa entre conceptos. El rótulo «Vista conceptual de recorridos
reales» y el enlace a Saved Paths forman parte de la representación.
No se mezclan ramas para inventar una tercera ruta. No se muestran pesos
agregados, puntuaciones de creatividad ni etiquetas de dominios generadas.

## Lectura de fuentes y origen epistemológico

«Explícito» aquí describe contenido observable en la fuente, no certifica que
la arista haya sido anotada por una persona. `reasoning` es una justificación
registrada, no una validación independiente. Las relaciones sin `source`
conservan fecha y justificación, pero no una cadena completa de modelo,
versión y autor de anotación. No se debe inventar esa procedencia.

Todos los IDs de relación siguientes comparten el prefijo
`5:efba7236-ddba-4937-a2b8-5b780ed8279a:`. La tabla muestra su sufijo.

| Vínculo con el archivo | ID / peso | Lectura curatorial y origen registrado |
|---|---|---|
| Couto — Astrónomo ciego | 5360 / .9 | **Explícito:** la imagen del astrónomo está en el texto. La atribución a Couto proviene del post local. |
| Couto — Ausencia | 5361 / .7 | **Inferido:** se lee una capacidad que falta; el concepto Ausencia no es una demostración ni una cita literal. |
| Caraco — Ausencia | 1250 / .9 | **Inferido, con apoyo textual:** objetos que permanecen y espera de una madre ausente. El `reasoning` lo llama explícito; la curaduría distingue el contenido de su etiqueta conceptual. |
| Caraco — Duelo y Pérdida | 637 / .78 | **Inferido:** la pregunta por la muerte y la permanencia de sus objetos permiten una lectura de duelo. |
| Warcry — Duelo y Pérdida | 1529 / .837 | **Inferido:** despedida, separación y muerte en la narrativa de la canción. |
| Warcry — Amor | 2930 / .796 | **Explícito:** el texto asociado se dirige afectivamente a una persona amada. |
| Tagore — Amor | 5008 / .8 | El texto contiene amor y una invocación al corazón; **la lectura devocional es inferida**, como reconoce el `reasoning`. No confundir ambos niveles. |
| Tagore — Abandono de lo superficial | 1775 / .9 | **Explícito en el motivo:** rechazo de adornos; el nombre del concepto es una abstracción de ese pasaje. |
| Couto — Tristeza y Melancolía | 5358 / 1 | **Explícito para tristeza**; el nombre compuesto del concepto amplía esa categoría. Peso 1 no equivale a certeza. |
| Metallica — Tristeza y Melancolía | 4986 / .85 | **Inferido:** el texto asociado expresa pérdida y desesperanza. La justificación menciona rasgos musicales que esta revisión no validó mediante escucha. |
| Metallica — Resignación | 1390 / .7138 | **Latente/enriquecido:** `source=interactive_latent_explorer`; transferencia desde Warcry mediante AudioSpace, similitud registrada 74%, penalización de hub .91. No es una mención textual comprobada de Resignación. |
| Warcry — Resignación | 2937 / .8 | **Inferido:** lectura de una decisión final y aceptación del destino en la canción. |

El registro 3 no prueba una equivalencia entre las canciones: la transferencia
es precisamente una pista que requiere evaluación. C también contiene otra
relación enriquecida (4615, hacia Rafael Lechowski) en el registro 4, no
seleccionado para la condensación de Home.

El texto de Caraco se firma localmente «Post Morten». No se ha cotejado una
edición; no normalizar esa atribución como verificación bibliográfica. Couto
y Tagore también se presentan como atribuciones de las fuentes ingestas.
No se hizo verificación externa de autoría o traducciones.

## Explicación breve para el público

La imagen del astrónomo ciego presenta la tristeza a través de una capacidad
que falta. Un recorrido lee esa ausencia junto a un texto atribuido a Albert
Caraco, donde los objetos permanecen tras la pérdida de la madre; después,
una canción de Warcry enlaza despedida y amor. Otro pasa por la melancolía de
Metallica y una relación con Resignación incorporada mediante exploración
latente, que merece una revisión propia. Ambos llegan a un texto atribuido a
Tagore, donde el amor acompaña un rechazo explícito de los adornos. No es una
demostración de equivalencia entre obras: son dos maneras de atravesar este
corpus. Los archivos permiten valorar qué conexiones están expresadas, cuáles
son interpretaciones y cuáles proceden de enriquecimiento.

## Límites de publicación

Usar paráfrasis, títulos y artistas. No reproducir letras completas ni grandes
fragmentos literarios en README, Home o capturas. La fuente local permite
inspección, pero su disponibilidad no acredita permiso de republicación.
La tarjeta no muestra citas ni previews. Si el export no está disponible en
otra instalación, informa de su ausencia y enlaza Pathfinder; no inventa un
resultado de sustitución. Los tres exports seleccionados se mantienen como candidatos a versionar; los
resultados personales nuevos se excluyen de Git. El enlace requiere que el
backend de la demo tenga el archivo nombrado.
