# Corrección de pesos de relaciones (2026-10-07 UTC)

## Causa

La aprobación de Inbox aceptaba diccionarios sin validar `confidence` y enviaba
sus valores directamente a Neo4j. Las respuestas del LLM o los datos curados
podían contener cadenas numéricas. Los ejemplos del prompt también mostraban
placeholders entre comillas. El frontend convertía las ediciones manuales, pero
conservaba el tipo original de los valores no editados.

Las sumas de pesos durante la promoción de conceptos y la fusión de ontología
podían concatenar cadenas. Se encontraron 44 pesos de texto: 39 numéricos y cinco
concatenados (`1.01.0`, `0.90.9`, `1.01.01.01.0`). La multiplicación de niebla de
guerra y el promedio de conceptos fallaban; otros filtros y agregaciones tenían
la misma exposición. El histograma de niebla también descartaba el peso exacto
1.0 al producir un índice 10 fuera de sus diez intervalos.

## Corrección

- Validación previa a la escritura de todo el payload de aprobación: conversión
  a float, rango [0, 1], finitud y rechazo de booleanos, null explícito y texto
  malformado. Los campos ausentes mantienen sus defaults existentes.
- La promoción directa valida todo el lote antes de abrir la sesión. Las rutas
  de recuperación de eventos/proyectos también validan los pesos.
- Las operaciones sobre pesos existentes convierten los textos numéricos antes
  de sumar, comparar o promediar. La niebla incluye 1.0 en el último intervalo.
  El scatter conserva el grado total y promedia solo los pesos válidos; omite
  conceptos sin ninguna certeza válida en lugar de inventar un promedio.
- El prompt pide explícitamente números JSON para las confidencias.

## Reparación aplicada

`backend/scripts/repair_relationship_weights.py` audita sin modificar por defecto.
Con `--apply --backup FILE` crea un respaldo exclusivo antes de escribir, verifica
que cada relación conserve el valor auditado y aplica los cambios en una
transacción. Las cadenas numéricas se convierten sin cambiar su valor. Solo se
reconstruyen concatenaciones de un mismo decimal repetido en los tipos de
relación de conceptos que usan suma limitada a 1.0. Los demás casos quedan sin
resolver para revisión; no se adivinan separaciones arbitrarias.

Se corrigieron las 44 relaciones, incluidas las cinco sumas concatenadas cuyo
resultado numérico limitado era 1.0. No quedaron casos sin resolver.

Respaldo local (excluido de Git por `data_dev/`):
`data_dev/weight-repairs/2026-10-07-original-weights.json`.
Contiene identificador de relación, valor original, reemplazo y razón.

Auditoría posterior: 4,327 pesos float, 1,184 enteros y 456 relaciones sin peso;
cero pesos de texto. Las 5,511 relaciones ponderadas tienen valores entre 0 y 1.
Los pesos exactos 1.0 son 1,845.

## Verificación

```powershell
$env:GRAPH_WEIGHT_INTEGRATION='1'
python -m unittest discover -s backend/tests -v
```

Pasaron 14 pruebas, incluidas tres de integración con Neo4j cuyos fixtures se
revierten siempre. Cubren normalización, rechazo previo a cualquier escritura,
sumas sobre valores heredados, límite 1.0, distribución, promedio y reparación
condicionada al valor auditado.

En el servidor activo se verificó HTTP 200 y `status: success` en niebla,
conceptos, histograma, heatmap fuzzy, chord fuzzy, bridges fuzzy, PageRank fuzzy
y comunidades fuzzy. Una aprobación con `confidence: "1.01.0"` devuelve HTTP 422.
