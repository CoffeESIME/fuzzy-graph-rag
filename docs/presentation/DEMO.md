# Demo de The Associative Engine · 4 minutos

Objetivo: presentar un observatorio experimental que permite inspeccionar
asociaciones. No demostrar verdad, cognición humana ni superioridad de un
algoritmo. Preparar el ejemplo [curado](CANONICAL_EXAMPLE.md) y la
[lista de capturas](CAPTURES.md). La implementación permanece congelada.

## Preparación

Usar el corpus local existente y mantener abiertas Home, búsqueda, el resultado
canónico de Pathfinder y un resultado guardado de Serendipity. No depender de
una inferencia LLM durante la presentación. Comprobar que el backend puede
servir el export canónico y que los assets abren. La aplicación no incluye ese
corpus para todas las instalaciones. Si falta un archivo, explicarlo; no
recrear material ni ajustar pesos para obtener una mejor demostración.

## Guion

| Tiempo | Pantalla y acción | Qué decir |
|---|---|---|
| 0:00–0:25 | **Home.** Mostrar el hero y las dos ramas. | «Esto comenzó con una pregunta: ¿puede un sistema de conocimiento ayudarnos a encontrar relaciones que no sabíamos que estábamos buscando? Conservamos la búsqueda por relevancia y dejamos espacio para asociaciones inesperadas». |
| 0:25–1:00 | **Buscar.** Consulta «astrónomo ciego», modo Semántica; mostrar el texto correspondiente si la búsqueda lo recupera. | «Sigue siendo un Graph RAG multimodal: puedo recuperar archivos por palabras, significado o conexiones. Este resultado es una puerta de entrada al corpus». No prometer un orden concreto de resultados. |
| 1:00–2:15 | **Pathfinder.** Desde Home, abrir «Inspeccionar las rutas completas». Mostrar Todas, después Ruta 1 y Ruta 3. | «Aquí elegimos ambos extremos. Lo interesante no es solo que A y B estén conectados, sino que existen varias maneras de atravesar este corpus. Son cinco secuencias guardadas, no cinco descubrimientos independientes». Usar la explicación breve de la curaduría. |
| 2:15–3:05 | **Serendipity.** Abrir su herramienta y después el resultado guardado indicado abajo. | «Aquí dejo abierto el destino. Serendipity utiliza sus propias reglas para favorecer asociaciones menos obvias y limitar el paso por conceptos muy centrales. No es otra versión de Pathfinder: no necesito reproducir este recorrido eligiendo sus dos extremos». |
| 3:05–3:40 | **Inspección.** Volver a la Ruta 3 de Pathfinder; desplegar la relación Metallica–Resignación, ID terminado en 1390. Abrir el inspector del texto final de Tagore, sin proyectar todo el contenido. | «Esta relación fue transferida mediante exploración latente; esta otra lectura se apoya en un rechazo de adornos presente en el texto. Son orígenes epistemológicos distintos. El peso expresa fuerza según un método, no probabilidad de verdad». |
| 3:40–4:00 | **Cierre.** Volver a la tarjeta de Home. | «El sistema no decide si la asociación es verdadera o útil. Hace visible el recorrido y sus fuentes para que una persona decida si merece seguirlo». |

Para tres minutos, acortar búsqueda e inspección. Para cinco, comparar la
Ruta 2 con la Ruta 1: cambia el archivo musical, aunque la vista conceptual
coincide. No abrir los diagnósticos Jaccard en la introducción pública.

## Resultado de Serendipity preparado

Archivo existente: `serendipity_path_1773992550430.json`.
Ruta guardada: Aislamiento y Soledad → The Motorleague — Everyone Is Digital
→ Pérdida de Identidad → Bad Religion — I Love My Computer → Crítica a Internet
y la Era Digital. Abrir en
`/analysis/saved-paths?path=serendipity_path_1773992550430.json`.
Identificarlo como **resultado guardado de Serendipity**, no como una ejecución
nueva ni como un resultado de Pathfinder. Los títulos bastan; evitar proyectar
letras. Verificar su disponibilidad justo antes de la demo.

## Ejemplos de reserva

- **Astrónomo ciego ↔ Guerra:** cinco registros, cuatro secuencias. Sirve para
  explicar divergencias tras un tronco común, sin añadir filtros de diversidad.
- **Libre albedrío y responsabilidad ↔ Laberinto sin Salida:** caso técnico de
  dominios distintos. Requiere más contexto y contiene temas sensibles.

Un recorrido inesperado es una pista. Una explicación LLM es una interpretación
asistida, no evidencia ni sustituto de la fuente. Las referencias a
Hofstadter/Sander y Danesi motivan la pregunta computacional; no validan la
arquitectura. [Trabajo futuro](../research/FUTURE_WORK.md) queda fuera de la demo.
