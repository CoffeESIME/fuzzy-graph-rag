# Roadmap de mejoras futuras

Este documento analiza propuestas; **no implementa las funcionalidades siguientes**. Prioridades: P1 alta, P2 media, P3 posterior. Dificultad relativa: baja/media/alta. Cualquier cambio en resultados, backend o contratos necesita un alcance nuevo explícito.

| Área | Problema observado | Propuesta | Beneficio | Dificultad | Backend | Cambia comportamiento | Prioridad |
|---|---|---|---|---|---|---|---|
| UI/UX | Estilos inline y controles históricos heterogéneos | Migrar progresivamente a Button, Tabs, Field y EmptyState con variantes tipadas | Consistencia completa y mantenimiento simple | Media | No | Solo presentación | P1 |
| UI/UX | Accesibilidad sin evaluación completa | Auditar teclado, lector de pantalla, contraste y touch targets en todos los estados | Acceso verificable, no solo visual | Media | No | Solo interacción UI | P1 |
| UI/UX | Paneles complejos con anchos fijos | Convertir a paneles colapsables y layouts por contenedor, con pruebas a 768/1024 px | Menos overflow y controles accesibles | Media | No | Solo UI | P1 |
| UI/UX | Bundle de producción grande | Separar rutas y cargar visualizadores bajo demanda | Menor carga inicial | Media | No | Solo carga del frontend | P2 |
| Visualización | SVG de caminos reconstruye conectores, no curvas exactas | Exportar geometría real de aristas y puertos conservando texto vectorial | Mayor equivalencia pantalla/figura | Alta | No | Solo exportación | P1 |
| Visualización | Colisiones en grafos grandes | Ajuste editorial de labels, rutas de aristas paralelas y paginación de leyendas | Figuras densas más legibles | Alta | No | Solo presentación | P1 |
| Visualización | Canvas exporta resolución disponible; 3D no exporta figuras | Añadir captura raster dedicada con resolución configurable y leyenda | Figuras de proyección reproducibles | Media | No | Solo UI/exportación | P2 |
| Visualización | Presentation no reconfigura todos los Nivo | Unificar theme Nivo, escalas de texto, ejes y captions por preset | Consistencia completa entre figuras | Media | No | Solo visual | P1 |
| Visualización | Layouts no se conservan entre visitas | Guardar preferencias locales de viewport/layout/preset por vista | Continuidad de exploración | Media | No | Persistencia de UI | P2 |
| Enriquecimiento | Fórmulas repartidas por operaciones | Documentar cada mezcla de pesos enlazando la rama exacta del código | Evitar explicaciones genéricas erróneas | Media | No para documentación | No | P1 |
| Enriquecimiento | Acciones complejas y feedback heterogéneo | Presentar alcance, estados y resultados en un flujo común | Menos ambigüedad operativa | Media | No si los estados existen | Solo UI | P2 |
| Búsqueda | Previews de listas/tablas y selección de grafo todavía independientes | Migrar todas las superficies a AssetInspector/AssetViewer con adaptadores explícitos | Mismo archivo, misma experiencia completa | Media | No con datos existentes | Solo UI | P1 |
| Búsqueda | Métricas de sistemas distintos pueden parecer comparables | Explicar procedencia y dominio de cada score, sin renormalizar resultados | Interpretación correcta de relevancia | Media | No si la fuente está disponible | No | P1 |
| Búsqueda | Rendimiento visual de resultados extensos | Virtualizar listas manteniendo orden y resultados | Navegación fluida | Media | No | Solo renderizado | P2 |
| Pathfinder | Varias rutas se devuelven como unión de nodos/aristas | Evaluar IDs explícitos de ruta y membresía antes de ofrecer selección por ruta | Explicar qué conexiones forman cada alternativa | Alta | Sí, probablemente contrato | Sí, contrato/presentación; no necesariamente algoritmo | P2 |
| Pathfinder | Densidad y rutas largas reducen labels | Añadir recorrido paso a paso y miniaturas de contexto sin eliminar nodos del resultado | Orientación al explorar caminos grandes | Media | No | Solo UI | P1 |
| Serendipity | Explicaciones pueden variar entre texto y estructuras | Definir esquema de narrativa estable y validar su presencia | Secciones narrativas consistentes | Media | Sí para garantizar esquema | Sí, contrato generado | P2 |
| Serendipity | Los pasos repetidos requieren distinguir identidad de occurrence | Añadir navegación entre ocurrencias de una misma entidad | Mejor lectura de recorridos cíclicos | Media | No | Solo UI | P2 |
| Graph analysis | Comunidades limitadas a 12 y top 25 miembros | Evaluar endpoint paginado de miembros y tamaño total | Inspección completa del cluster | Alta | Sí | Sí, recuperación de datos/contrato | P2 |
| Graph analysis | Focus/labels actuales por umbral de tamaño, no jerarquía continua | Implementar LOD según zoom y selección con pruebas de densidad | Menos ruido en comunidades grandes | Media | No sobre datos existentes | Solo visual | P1 |
| Graph analysis | Three.js existe pero no está activo en las vistas actuales | Decidir si se integra como modo soportado o se conserva como experimental | Alcance explícito y menor deuda de UI | Media | No | Cambia opciones de UI | P3 |
| Ingesta | Estados de tareas y colas usan presentaciones diferentes | Normalizar badges, tablas, empty/loading/error y disclosure técnico | Lectura operativa más clara | Media | No | Solo UI | P1 |
| Ingesta | Seguimiento fino depende de estados que envíe el servidor | Evaluar progreso por etapa verificable, sin porcentajes estimados inventados | Diagnóstico del procesamiento | Alta | Sí si falta la información | Sí, contrato de estado | P2 |

## Criterio de aceptación para trabajo posterior

Separar siempre preferencias de visualización de parámetros de consulta. Un filtro que oculta nodos localmente debe identificarse como visual y no convertirse en un cambio de alpha-cut, threshold o clustering. Antes de cambiar datos disponibles, documentar contrato, alcance y autorización. Mantener muestras verificables para Paper, escala de grises, tamaños de publicación y reduced-motion.
