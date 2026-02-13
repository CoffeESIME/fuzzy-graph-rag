# GraphRAG Multimodal - Guía de Uso Rápido

## 🎯 Casos de Uso Comunes

### Caso 1: Subir Imágenes Estándar

**Objetivo:** Subir 3 imágenes para procesamiento visual individual.

1. **Tab 1: Ingesta y Agrupación**
2. Cargar `foto1.jpg`, `foto2.jpg`, `foto3.jpg`
3. Para cada imagen:
   - Seleccionar archivo
   - Operación: `standard`
   - Vectores: `visual_siglip`, `visual_semantic`
   - Descartar Original: ❌ No
   - Click "✅ Crear Grupo"
4. Verificar 3 grupos creados
5. Click "🚀 Enviar al Servidor"

**Resultado:** 3 Assets creados, 6 VectorStatus (2 por imagen)

---

### Caso 2: Merge de Screenshots con OCR

**Objetivo:** Combinar múltiples screenshots de un tutorial en un documento único.

1. **Tab 1: Ingesta y Agrupación**
2. Cargar `tutorial_1.png`, `tutorial_2.png`, `tutorial_3.png`, `tutorial_4.png`
3. Seleccionar TODAS las imágenes en el multiselect
4. Configurar:
   - Operación: `merge_ocr`
   - Vectores: `text_chunk`
   - Descartar Original: ✅ Sí (para ahorrar espacio)
   - Notas: "Tutorial de instalación de Docker"
   - Click "✅ Crear Grupo"
5. Click "🚀 Enviar al Servidor"

**Resultado:** 
- 1 Asset creado (merged)
- Archivo binario: Texto extraído concatenado
- 1 VectorStatus para `text_chunk`
- Screenshots originales eliminados tras extracción exitosa

---

### Caso 3: Audio con Transcripción y Embedding

**Objetivo:** Procesar un podcast para búsqueda semántica y embeddings de audio.

1. **Tab 1: Ingesta y Agrupación**
2. Cargar `podcast_ep01.mp3`
3. Seleccionar archivo
4. Configurar:
   - Operación: `standard`
   - Vectores: `audio_clap`, `audio_transcript`
   - Descartar Original: ❌ No
   - Notas: "Episodio 1: Introducción a GraphRAG"
   - Click "✅ Crear Grupo"
5. Click "🚀 Enviar al Servidor"

**Resultado:**
- 1 Asset creado
- 2 VectorStatus:
  - `audio_clap` → Embedding acústico
  - `audio_transcript` → Transcripción + embedding semántico

---

### Caso 4: Procesamiento Mixto (Imágenes + Audio)

**Objetivo:** Subir diferentes tipos de media con configuraciones únicas.

1. **Tab 1: Ingesta y Agrupación**
2. Cargar `meme.jpg`, `voice_note.mp3`, `screenshot.png`

3. **Grupo 1: Meme (Visual + Semántico)**
   - Archivos: `meme.jpg`
   - Operación: `standard`
   - Vectores: `visual_siglip`, `visual_semantic`, `text_ocr`
   - Descartar Original: ❌

4. **Grupo 2: Nota de Voz (Solo Transcripción)**
   - Archivos: `voice_note.mp3`
   - Operación: `standard`
   - Vectores: `audio_transcript`
   - Descartar Original: ✅ (solo necesito texto)

5. **Grupo 3: Screenshot (Solo OCR)**
   - Archivos: `screenshot.png`
   - Operación: `standard`
   - Vectores: `text_ocr`
   - Descartar Original: ✅

6. Click "🚀 Enviar al Servidor"

**Resultado:** 3 Assets, 5 VectorStatus total

---

### Caso 5: Control de Tareas Selectivo

**Objetivo:** Revisar tareas en staging y procesar solo las prioritarias.

1. **Tab 2: Control de Tareas**
2. Click "🔄 Refrescar"
3. Ver tabla de ON_HOLD tasks
4. **Ejemplo de tabla:**

   | ID | Filename | Vector Type | Status | Created At |
   |---|---|---|---|---|
   | abc-123 | meme.jpg | visual_siglip | on_hold | 2025-12-28 17:00 |
   | abc-124 | meme.jpg | visual_semantic | on_hold | 2025-12-28 17:00 |
   | abc-125 | voice.mp3 | audio_transcript | on_hold | 2025-12-28 17:01 |
   | abc-126 | screenshot.png | text_ocr | on_hold | 2025-12-28 17:02 |

5. Decidir procesar solo tareas de `meme.jpg`:
   - Copiar IDs: `abc-123, abc-124`
6. Pegar en campo "IDs de tareas"
7. Click "▶️ Procesar Seleccionados"

**Resultado:** 
- 2 tasks cambian a `PENDING`
- Celery workers inician procesamiento
- Otras tasks permanecen en `ON_HOLD`

---

### Caso 6: Búsqueda Semántica (React App)

**Objetivo:** Buscar contenido visual y textual usando lenguaje natural.

1. **Abrir Search App:** `http://localhost:5173/search`
2. **Tab: Semántica**
3. **Query:** "Documentos sobre inteligencia artificial y memes de gatos"
4. **Espacios:** Seleccionar `TextSpace` y `VisualSpace`
5. **Configuración:** Limit = 20
6. **Click "Buscar"**

**Resultado:**
- Grid de resultados mixtos
- **Imágenes:** Thumbnails de gatos
- **Documentos:** Tarjetas con resumen de IA
- **Acción:** Click en "Ver Texto" para abrir modal de lectura
- **Acción:** Click en imagen para ver tamaño completo

---

## 🔧 Troubleshooting por Caso de Uso

### Error: "No files were uploaded"
**Causa:** Olvidaste cargar archivos antes de crear grupo.
**Solución:** Usa el file_uploader primero.

### Error: "Invalid upload_map structure"
**Causa:** Bug en el frontend (no debería ocurrir).
**Solución:** Reportar issue. Verificar console del navegador.

### Error: "Connection refused"
**Causa:** Backend no está ejecutándose.
**Solución:** 
```bash
cd backend
poetry run uvicorn app:app --reload
```

### Warning: "El endpoint /tasks/on-hold aún no está implementado"
**Causa:** Backend antiguo sin el router de tasks.
**Solución:** Asegúrate de tener `app/routers/tasks.py` y registrado en `app/__init__.py`.

### Tasks no aparecen en Tab 2
**Causa:** Enviaste archivos pero no se crearon VectorStatus.
**Solución:** 
1. Verifica que seleccionaste al menos un vector en cada grupo
2. Revisa logs del backend
3. Query directo a PostgreSQL:
   ```sql
   SELECT * FROM vector_statuses WHERE status = 'on_hold';
   ```

---

## 💡 Tips y Mejores Prácticas

### 1. Organización de Archivos
- **Nombra descriptivamente:** `twitter_thread_ai_2025.jpg` mejor que `IMG_1234.jpg`
- **Agrupa lógicamente:** Archivos relacionados en el mismo grupo
- **Usa notas:** Contextualiza para búsqueda futura

### 2. Selección de Vectores
- **Imágenes:**
  - `visual_siglip` → Forma, estética, objetos
  - `visual_semantic` → Concepto, significado (memes, arte)
  - `text_ocr` → Si tiene texto relevante
- **Audio:**
  - `audio_clap` → Búsqueda por sonido/música
  - `audio_transcript` → Búsqueda por contenido hablado
- **Texto:**
  - `text_chunk` → Documentos, artículos
  - `user_memory` → Notas personales, contexto

### 3. Descartar Original
✅ **Cuándo activar:**
- Merge OCR de screenshots (solo necesitas texto)
- Transcripción de audio (solo necesitas texto)
- Extracción de metadata (ej: propiedades de imagen)

❌ **Cuándo NO activar:**
- Procesamiento visual que necesita imagen original
- Archivos únicos/valiosos
- Múltiples vectores que requieren binario

### 4. Batch Processing
- **Grupo grande vs múltiples grupos:** 
  - Merge OCR → Un solo grupo
  - Procesamiento individual → Un grupo por archivo
- **Performance:** Tab 2 permite activar múltiples tasks simultáneamente

### 5. Flujo Recomendado
1. **Staging First:** Sube todo a ON_HOLD
2. **Revisar en Tab 2:** Verifica tasks creadas
3. **Procesar Selectivo:** Activa solo lo que necesitas ahora
4. **Monitorear:** (Futuro: polling automático de status)

---

## 🎨 Ejemplos de Configuración

### Configuración Minimalista
```
Archivo: documento.pdf
Operación: standard
Vectores: text_chunk
Descartar: No
Notas: (vacío)
```

### Configuración Completa (Imagen Compleja)
```
Archivo: infographic.png
Operación: standard
Vectores: visual_siglip, visual_semantic, text_ocr
Descartar: No
Notas: "Infografía sobre cambio climático - Fuente: ONU 2025"
```

### Configuración de Transmutación
```
Archivos: [page1.jpg, page2.jpg, page3.jpg]
Operación: merge_ocr
Vectores: text_chunk
Descartar: Sí
Notas: "Contrato de arrendamiento - Extraer texto legal"
```

---

## 📊 Métricas y KPIs

### Qué Monitorear
- **Assets creados vs Files subidos:** Ratio de merge
- **VectorStatus por Asset:** Complejidad de procesamiento
- **ON_HOLD vs PENDING vs COMPLETED:** Pipeline health
- **Tiempo de procesamiento:** Per vector_type

### Queries SQL Útiles
```sql
-- Total de assets
SELECT COUNT(*) FROM assets;

-- Tasks por estado
SELECT status, COUNT(*) FROM vector_statuses GROUP BY status;

-- Assets con más vector types
SELECT asset_id, COUNT(*) as vector_count 
FROM vector_statuses 
GROUP BY asset_id 
ORDER BY vector_count DESC;

-- Tasks fallidas
SELECT * FROM vector_statuses WHERE status = 'failed';
```

---

## 🚀 Próximos Pasos

1. **Integración con Celery:** Workers reales procesando tasks
2. **Polling UI:** Auto-refresh de status en Tab 2
3. **Búsqueda Semántica:** Interface para query vectorial
4. **Visualización de Graph:** Neo4j + D3.js
5. **Batch Upload desde S3/Drive:** Ingesta masiva

---

## 📞 Soporte

Si encuentras problemas:
1. Revisa logs del backend
2. Verifica configuración en `.streamlit/secrets.toml`
3. Consulta `ARCHITECTURE.md` para detalles técnicos
4. Reporta issues con:
   - Request/Response completos
   - Stack trace
   - Configuración de grupo que causó error
