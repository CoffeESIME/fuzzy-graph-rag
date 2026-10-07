# Pathfinder: contrato de rutas

## Contrato anterior (inspeccionado antes del cambio)

`POST /analysis/pathfinder` recibe `source_element_id`, `target_element_id`,
`mode` (direct/lateral/topological), `threshold` (0.85), `topo_threshold` (0),
y `k_paths` (3, limitado por el backend a 1–10).

La respuesta contiene `status`, `message`, `nodes`, `edges`, `path_length`,
`mode`. `nodes` y `edges` son una unión deduplicada; `path_length` es el máximo
de saltos. Los registros Cypher ordenados y `totalCost` se pierden al formar
la unión. Las aristas conservan orientación de almacenamiento, tipo y peso
redondeado, pero no ID ni procedencia. El export añade extremos, timestamp,
explicación y privacidad/umbral lateral; no guarda k ni corte topológico.

`PathfinderCard` dibuja esa unión usando `GraphCanvas`, que mantiene acceso
a archivos mediante `AssetInspector`. `SavedPathsViewer` acepta JSON
Pathfinder con nodes/edges y Serendipity con una secuencia path.

## Contrato nuevo

La representación canónica es `paths`: registros ordenados independientes.
Se mantienen los campos antiguos como grafo combinado para consumidores
existentes. Cada ruta conserva ID, rango nativo, firma de secuencia de nodos,
`duplicate_of`, modo, nodos/aristas ordenados, saltos, coste nativo, mínimo
diagnóstico de pesos y parámetros efectivos. Cada arista conserva ID,
orientación de almacenamiento, orientación de recorrido (`traversal_source`,
`traversal_target`), peso numérico sin redondear, `raw_weight`, reasoning y
propiedades de procedencia disponibles. No se reconstruyen datos ausentes.

`raw_result_count` cuenta registros; `unique_route_count` cuenta secuencias
ordenadas de nodos. Los duplicados permanecen en `paths` y en el export;
el selector agrupa sus representaciones. Un ciclo no se elimina: se indica
y se muestra por ocurrencias al seleccionar su ruta.

Saved Paths v2 añade `schema_version: 2`, `tool: pathfinder`, timestamps,
extremos, parámetros, versión del contrato del algoritmo y todos los paths.
Los exports antiguos siguen siendo grafos legados: no se inventa su división
en rutas ni se migran archivos automáticamente. Serendipity no cambia.

Los costes son propios del modo; no son comparables entre algoritmos.
El peso mínimo no es probabilidad ni medida de verdad. La versión
`pathfinder-cypher-v1` identifica las consultas actuales, que no se modifican.
Las fuentes preservadas son hashes, nombres, MIME y rutas disponibles;
no se incluyen URLs firmadas temporales como evidencia duradera.

## Compatibilidad y límites

La unión superior sigue disponible. Sus aristas ahora distinguen IDs paralelos
y conservan precisión numérica: un consumidor que asumía una sola relación por
par origen/destino/tipo o pesos siempre redondeados deberá adaptarse. Un peso
ausente o no numérico se representa como `weight: null`, conservando
`raw_weight`; no se sustituye por una probabilidad ni por el valor empleado
internamente por la consulta para calcular costes.

En «Todas» se dibuja un representante por secuencia; se pueden inspeccionar
las variantes originales con el selector de variante de cada ruta. El export
siempre conserva todos los registros y la unión completa. Las etiquetas R1,
R2… identifican pertenencia; varias etiquetas indican relaciones compartidas.

Los archivos antiguos no permiten recuperar pertenencia, orden, costes,
parámetros ni procedencia que ya se habían descartado. Los nuevos conservan
solo propiedades disponibles en el grafo; no reparan procedencia histórica.
Los IDs de Neo4j no garantizan identidad tras reconstruir la base de datos.
El JSON permite revisar el resultado guardado; repetir la consulta sobre un
grafo diferente no garantiza obtenerlo de nuevo. Los archivos originales
deben seguir disponibles para abrirlos desde sus referencias.

## Verificación

Desde la raíz:

```powershell
python -m unittest discover -s backend/tests -p test_pathfinder_contract.py -v
```

Desde `search-app`:

```powershell
node --test tests/pathfinder.test.mjs
npm run build
```

La página de desarrollo `/tests/pathfinder-fixture.html` utiliza el componente
real con `tests/fixtures/canonical-pathfinder-v2.json`. No se importa desde la
aplicación ni se incluye en el build de producción. Combina una ruta topológica
y dos laterales de las dos consultas auditadas; no afirma que una sola petición
devuelva modos diferentes. Permite comprobar selección y round-trip v2.

Verificado: 4 pruebas backend, 8 pruebas frontend, TypeScript, lint de los
módulos nuevos y build. Las pruebas leen los 24 Pathfinder legados existentes.
En navegador se comprobaron las tres secuencias, selección, round-trip, tema
claro/oscuro, inspector del archivo y procedencia de relaciones. En API local,
la consulta topológica conservó un recorrido de cuatro saltos; la lateral con
k=3 conservó tres registros de seis saltos y dos secuencias distintas. k es un
límite de registros, no una garantía de obtener k secuencias distintas.
Se comprobó que las consultas Cypher y los hashes de los 50 archivos guardados
coinciden con sus versiones anteriores.

## Explicaciones por recorrido

Al explicar una ruta se envían únicamente sus nodos, relaciones y secuencia.
«Todas» envía la unión y todos los registros ordenados en `paths`, con sus IDs
y límites explícitos. Solicita una explicación conjunta que distinga rutas;
no dispara N llamadas ni genera automáticamente N explicaciones independientes.

El export incluye `explanations`, un historial de respuestas exitosas con
`path_id` (null para Todas), `path_ids`, texto, fecha de recepción y modo de
privacidad solicitado. Cambiar de ruta no borra respuestas, incluso si una
petición sigue pendiente. Regenerar añade otra versión; la interfaz muestra
la última de la selección actual. Un resultado nuevo inicia otro historial.
Los errores no se archivan como explicaciones. `llm_explanation` y
`explanation_path_id` reflejan la selección actual para lectores antiguos.
Saved Paths lee este historial y permite descargar una copia con nuevas
explicaciones, sin sobrescribir archivos del servidor. Antes de descargar,
el historial existe solo en memoria; recargar la página lo pierde.

El timeout privado de lectura al gateway pasa de 60 a 900 segundos; conexión
10 segundos. Frontend y proxies permiten 960 segundos para dar margen al
backend. El modo no privado mantiene 60 segundos al gateway y cinco minutos
en el cliente. Vite requiere recargar su configuración y Nginx reconstruir o
recargar el despliegue. Un gateway externo o proveedor puede tener límites
propios. Se verifican ambos modos con un gateway simulado; no se hizo una
inferencia real de 15 minutos. Pruebas ampliadas: 6 backend y 11 frontend.
