# Explicaciones asociativas v2

Versión del prompt: `v2-associative-evidence`.

## Alcance y comportamiento

El pipeline ahora solicita evaluación de cada salto antes de interpretar el
recorrido. Separa relación y fuerza de asociación del grafo, reasoning registrado,
evidencia recuperada, interpretación y límites. Las categorías de asociación son
abiertas; la causalidad requiere evidencia específica de un mecanismo.

El prompt admite contrastes, divergencias, analogías, contrapuntos y resultados
insuficientes o triviales. Distingue dirección de lectura de dirección causal.
No asigna calidad por umbrales de peso ni centralidad global por posición en una
ruta. Incluye calibración con los ejemplos Khayyam/Ramanujan, Khayyam/Sade y
Thoreau/Sabaton. También exige que hallazgo, justificación y conclusión respeten
los límites identificados por salto, sin introducir causalidad seguida de un
descargo contradictorio.

Los bloques recuperados llevan `source_id` y etiquetas que distinguen resumen
previo de texto literal; el resumen de una letra ya no se presenta como la letra.
Se preservan los metadatos de relaciones que ya venían en la petición antigua
sin `paths`. No se reconstruyen rutas a partir de un grafo combinado.

## Compatibilidad

`PathExplanationResponse` mantiene exactamente `status: string` y
`explanation: string`. En éxito, el string contiene JSON validado:

```json
{"analisis_serendipia": {"ruta_id": "una-ruta", "...": "campos del análisis"}}
```

Para varias rutas:

```json
{"analisis_serendipia": [{"ruta_id": "ruta-1", "...": "análisis independiente"}, {"ruta_id": "ruta-2", "...": "análisis independiente"}]}
```

Estos ejemplos abrevian los campos. El esquema completo está en
`backend/shared/path_explanation.py`. En la entrada sin rutas explícitas se usa
`recorrido-sin-rutas-explicitas` como ID del conjunto, declarando la limitación;
no representa una ruta descubierta o inferida.

El componente existente `components/graph/Explanation.tsx` ya parsea strings JSON
y presenta sus objetos/listas recursivamente. Pathfinder, Serendipity y Saved
Paths mantienen y exportan la explicación como string. No fue necesario cambiar
el frontend ni migrar los archivos existentes. Las explicaciones históricas no
se revalidan ni se reescriben.

La respuesta nueva se valida con Pydantic: campos, tipos, categorías de soporte,
IDs y orden de rutas, número y extremos de saltos, relación/peso/reasoning
registrados e IDs de fuentes pertenecientes a la ruta. Esa validación es
estructural: no demuestra la verdad de una interpretación ni verifica por sí
sola que una cita sea fiel al archivo.

Texto libre, JSON incompleto, contenido vacío, salida truncada o rutas mezcladas
devuelven `status: error`, conservando el contrato de errores de la interfaz.
No se fabrican análisis para completar respuestas inválidas ni se reintenta
automáticamente la generación. La validación aplica tanto en modo local como nube.

## Parámetros y diagnóstico

- Temperatura de esta operación: constante `PATH_EXPLANATION_TEMPERATURE = 0.35`.
  No había una configuración central de temperaturas que reutilizar.
- Versión del prompt, modelo efectivo y `finish_reason`: logger INFO.
- `usage`, cuando existe: logger DEBUG.
- Se retiró `provider="openai"`, que el gateway no interpretaba. La selección
  continúa dependiendo de `task=chat` y privacidad; no se modificó el gateway.
- Modelo configurado durante las pruebas: Gemini 3 Flash Preview vía OpenRouter
  en modo flexible; gpt-oss:20b vía Ollama en modo estricto.

## Archivos de esta implementación

| Archivo | Motivo |
| --- | --- |
| `backend/app/routers/analysis.py` | Integra prompt/temperatura, conserva datos recibidos, etiqueta fuentes, valida salida y registra diagnóstico. Sólo cambia el handler de explicación en esta tarea. |
| `backend/shared/path_explanation.py` | Prompt versionado, estructura JSON, formato esperado de rutas y validación. |
| `backend/tests/test_path_explanations.py` | Pruebas de contrato, contexto, compatibilidad, privacidad y rechazo de respuestas inválidas. |
| `backend/tests/fixtures/path_explanation_cases.json` | Cuatro escenarios sintéticos, expresamente identificados como pruebas y no citas históricas. |
| `backend/tests/evaluate_path_explanations.py` | Evaluación opt-in con gateway real y contenido sintético, sin acceder al corpus ni escribir el grafo. |
| `docs/research/path-llm-audit/v2-controlled-*.json` | Salidas locales generadas, excluidas de Git. Los casos, evaluador y resultados resumidos se conservan. |
| Este documento | Decisiones, alcance y resultados. |

Los otros cambios que ya existían en el working tree pertenecen a tareas previas.

## Verificación automatizada

```powershell
python -m unittest discover -s backend/tests -v
cd search-app
node --test tests/pathfinder.test.mjs tests/pathfinder-diagnostics.test.mjs
```

Resultado: 16 pruebas backend aprobadas y 3 de integración Neo4j omitidas por ser
opt-in y quedar fuera de esta tarea; 17 pruebas frontend aprobadas. Se comprobó
también el esquema del servidor activo: `explanation` sigue siendo string.
Compilación Python y `git diff --check` sin errores.

## Evaluación con modelos reales

```powershell
python backend/tests/evaluate_path_explanations.py --live
python backend/tests/evaluate_path_explanations.py --live --private --case insuficiente
```

El evaluador usa el handler real y sustituye únicamente almacenamiento por
sidecars sintéticos; el gateway y los modelos sí son reales. Las pruebas unitarias
no se presentan como demostración de calidad semántica.

Se revisaron los cuatro casos individuales, dos rutas simultáneas en nube y el
caso sin evidencia en local. Las salidas brutas históricas se eliminaron durante la limpieza del repositorio; el siguiente registro conserva el resumen de los intentos, incluidos los fallidos. Los nombres identifican aquellas ejecuciones, no archivos incluidos en Git. Volver a ejecutar el evaluador requiere el gateway y puede producir respuestas distintas:

- `v2-controlled-cloud-initial.json`: detectó una lista en la raíz en el caso
  múltiple; fue rechazada. Se hizo explícito el esquema para cada cardinalidad.
- `v2-controlled-local-initial.json`: detectó extremos invertidos y objetos en una
  lista de strings; fue rechazada. Se añadieron los extremos esperados y tipos
  explícitos de esas listas.
- `v2-controlled-cloud.json`: A/B/C/D y múltiples rutas aceptadas estructuralmente.
  A identifica analogía estructural, B tensión/divergencia ética. La revisión
  semántica posterior encontró inferencias globales excesivas en C y metáforas
  sobre la ausencia de contenido en D, y motivó otra calibración.
- `v2-controlled-cloud-insuficiente.json`: D marca ambos saltos y la evaluación
  como insuficientes pese a pesos 1.0, no inventa contenido y deja vacías las
  lecturas alternativas.
- `v2-controlled-local-insuficiente.json`: el modelo local conserva los extremos,
  devuelve JSON válido y marca ambos saltos como insuficientes.
- `v2-controlled-cloud-contrapunto-initial.json` y
  `v2-controlled-cloud-contrapunto-calibration.json`: conservan las respuestas de
  C que todavía introducían causalidad en el hallazgo. Su aceptación estructural
  no se considera aprobación semántica.
- `v2-controlled-cloud-contrapunto.json`: resultado de la calibración final del
  caso C: clasifica contrapunto normativo-histórico y declara que no hay evidencia
  de un mecanismo causal entre la teoría de Thoreau y los eventos representados.
  No presenta la canción como validación empírica ni el Holocausto como efecto
  monocausal de identidad nacional. Las lecturas alternativas se expresan como
  interpretaciones, no como hechos del archivo.

| Criterio semántico | Resultado observado |
| --- | --- |
| A: analogía sin teoría causal de genialidad | Analogía estructural; no atribuye a Khayyam una teoría histórica sobre Ramanujan. |
| B: respuestas diferentes ante finitud | Contraste/tensión ética entre cuidado e indiferencia; no materialismo como causa necesaria de cinismo. |
| C: contraste normativo/representación artística | Contrapunto, con límite causal explícito en la respuesta final. |
| D: contenido no recuperado | Ambos saltos insuficientes; la respuesta final en nube deja vacías las lecturas alternativas y no inventa contenido. |
| Varias rutas | Dos objetos independientes con IDs, cuatro saltos y fuentes de su respectiva ruta. |
| Modo local | JSON aceptado, mismos extremos del recorrido, ambos saltos de D insuficientes. |

Estas son pruebas controladas de los casos solicitados, no una garantía de que
cualquier respuesta futura del modelo mantenga todos los matices.

## Trabajo futuro preservado fuera de alcance

No se cambian descubrimiento/selección de caminos, pesos, Jaccard, penalizaciones,
topología ni datos de Neo4j. Tampoco se cambia recuperación de archivos, los cortes
de 1,000/3,000 caracteres, definiciones ausentes de conceptos, contenido curado
omitido, presentación visual ni formato de archivos antiguos.

La pérdida de metadatos al regenerar desde Saved Paths antiguo/Serendipity sigue
necesitando una tarea separada: el nuevo pipeline sólo puede evaluar lo que recibe.
Una evaluación más amplia sobre corpus real y modelos locales también queda
separada de estos ejemplos controlados.
