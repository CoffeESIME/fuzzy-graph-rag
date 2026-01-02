# GraphRAG Multimodal - Previsualización Inteligente de Archivos

## 🎯 Funcionalidad

La sección **"Archivos Sin Asignar"** ahora incluye **previsualización inteligente** que detecta automáticamente el tipo de archivo y muestra un preview apropiado.

## 🖼️ Tipos de Preview Soportados

### 1. Imágenes (`image/*`)
- **Formatos:** JPG, PNG, GIF, WebP, SVG, etc.
- **Preview:** Renderiza la imagen completa usando `st.image()`
- **Características:**
  - Usa ancho completo del contenedor
  - Muestra caption "Preview"
  - Reset automático del file pointer con `seek(0)`

**Ejemplo:**
```
📎 vacation.jpg (2.45 MB) — image/jpeg
  └─ [Imagen mostrada en el expander]
```

### 2. Audio (`audio/*`)
- **Formatos:** MP3, WAV, OGG, M4A, etc.
- **Preview:** Reproduce con player nativo usando `st.audio()`
- **Características:**
  - Controles de reproducción integrados
  - Play/Pause/Volume
  - Reset automático del file pointer

**Ejemplo:**
```
📎 podcast_ep01.mp3 (45.67 MB) — audio/mpeg
  └─ [Reproductor de audio]
```

### 3. Video (`video/*`)
- **Formatos:** MP4, WebM, OGG, AVI, etc.
- **Preview:** Reproduce con player nativo usando `st.video()`
- **Características:**
  - Controles de reproducción completos
  - Fullscreen disponible
  - Reset automático del file pointer

**Ejemplo:**
```
📎 tutorial.mp4 (125.34 MB) — video/mp4
  └─ [Reproductor de video]
```

### 4. Texto (`text/*`)
- **Formatos:** TXT, MD, CSV, JSON, etc.
- **Preview:** Muestra primeros 1000 caracteres usando `st.code()`
- **Características:**
  - Trunca contenido largo
  - Mensaje de "contenido truncado" si aplica
  - Manejo de encoding UTF-8
  - Fallback para archivos no decodificables

**Ejemplo:**
```
📎 notes.txt (1.23 KB) — text/plain
  └─ [Código mostrado en caja de texto]
```

### 5. Otros Formatos
- **Formatos:** PDF, DOCX, ZIP, binarios, etc.
- **Preview:** Mensaje informativo
- **Características:**
  - Muestra tipo MIME detectado
  - Informa que preview no está disponible

**Ejemplo:**
```
📎 document.pdf (3.45 MB) — application/pdf
  └─ 📄 Preview no disponible para este formato (application/pdf)
```

## 🔧 Implementación Técnica

### Detección de Tipo MIME
```python
mime_type = getattr(file_obj, 'type', 'application/octet-stream')

if mime_type.startswith('image/'):
    # Lógica de imagen
elif mime_type.startswith('audio/'):
    # Lógica de audio
elif mime_type.startswith('video/'):
    # Lógica de video
elif mime_type.startswith('text/'):
    # Lógica de texto
else:
    # Otros formatos
```

### File Pointer Management
**Crítico:** Después de leer un archivo para preview, es **esencial** resetear el file pointer:

```python
st.image(file_obj, caption="Preview")
file_obj.seek(0)  # ¡IMPORTANTE! Reset para upload posterior
```

Sin `seek(0)`, el archivo estaría "vacío" al enviarlo al backend.

### Información del Archivo
Cada expander muestra:
- 📎 **Nombre del archivo**
- **(Tamaño)** - En KB o MB automáticamente
- **`tipo MIME`** - Para debugging/verificación

### Funciones Auxiliares

#### `get_file_size_mb(file_obj)`
Calcula tamaño del archivo:
- Si < 0.01 MB → muestra en KB
- Si >= 0.01 MB → muestra en MB
- Fallback: "Tamaño desconocido"

#### `render_file_preview(file_obj)`
Renderiza preview según tipo MIME:
- Detecta categoría de archivo
- Muestra preview apropiado
- Maneja errores gracefully
- **Siempre** hace `seek(0)` al final

#### `render_ungrouped_files()` (Mejorada)
- Itera sobre archivos sin asignar
- Crea expander por archivo
- Llama a `render_file_preview()`
- Muestra contador total

## 🎨 UX Mejoradas

### Antes
```
📋 Archivos Sin Asignar
Ver archivos sin asignar ▼
  • vacation.jpg
  • podcast.mp3
  • tutorial.mp4
```

### Después
```
📋 Archivos Sin Asignar
Total de archivos sin asignar: 3

📎 vacation.jpg (2.45 MB) — image/jpeg ▶
📎 podcast.mp3 (45.67 MB) — audio/mpeg ▶
📎 tutorial.mp4 (125.34 MB) — video/mp4 ▶
```

Al expandir cada archivo:
```
📎 vacation.jpg (2.45 MB) — image/jpeg ▼
  [Imagen de las vacaciones mostrada]

📎 podcast.mp3 (45.67 MB) — audio/mpeg ▼
  [▶️ Reproductor de audio con controles]

📎 tutorial.mp4 (125.34 MB) — video/mp4 ▼
  [▶️ Reproductor de video con controles]
```

## ✅ Ventajas

1. **Verificación Visual:** Los usuarios pueden confirmar el contenido antes de agrupar
2. **Prevención de Errores:** Evita agrupar archivos incorrectos
3. **Feedback Inmediato:** No necesita herramientas externas para ver archivos
4. **Detección de Problemas:** Identifica archivos corruptos antes del upload
5. **Mejor UX:** Interfaz más profesional e intuitiva

## 🐛 Manejo de Errores

### Errores de Carga
Si un archivo no puede ser previsualizados (corrupto, formato no soportado, etc.):

```python
try:
    st.image(file_obj, caption="Preview")
    file_obj.seek(0)
except Exception as e:
    st.warning(f"⚠️ No se pudo cargar la imagen: {str(e)}")
    file_obj.seek(0)  # Reset incluso en error
```

### Archivos de Texto No Decodificables
```python
try:
    text_content = content.decode('utf-8')
    # ...
except UnicodeDecodeError:
    st.info("📄 Archivo de texto detectado (no se puede previsualizar)")
```

## 📊 Casos de Uso

### Caso 1: Verificar Imágenes Antes de Merge OCR
**Escenario:** Usuario sube 5 screenshots para merge OCR.

**Beneficio:** Puede expandir cada imagen y verificar que todas son del mismo documento antes de crear el grupo.

### Caso 2: Confirmar Audio Correcto
**Escenario:** Usuario sube varios podcasts.

**Beneficio:** Puede reproducir los primeros segundos de cada episodio para confirmar que subió los archivos correctos.

### Caso 3: Verificar Video No Corrupto
**Escenario:** Usuario sube videos educativos.

**Beneficio:** Puede ver un preview del video para confirmar que no está corrupto o que es el video correcto.

### Caso 4: Revisar Contenido de Texto
**Escenario:** Usuario sube notas o documentos TXT.

**Beneficio:** Puede leer las primeras líneas para identificar el contenido sin abrir otro programa.

## 🔄 Flujo Completo

```
1. Usuario carga archivos
   ↓
2. Archivos aparecen en "Sin Asignar"
   ↓
3. Usuario expande un archivo
   ↓
4. Sistema detecta tipo MIME
   ↓
5. Renderiza preview apropiado
   ↓
6. Usuario verifica contenido
   ↓
7. Usuario decide si agrupar o no
   ↓
8. (Si agrupa) file.seek(0) asegura que el archivo esté completo para upload
```

## 🚀 Futuras Mejoras

### Posibles Extensiones
- [ ] **PDF Preview:** Usar PyMuPDF para renderizar PDFs
- [ ] **Thumbnails:** Generar miniaturas para videos largos
- [ ] **Metadata Display:** Mostrar EXIF para imágenes, duración para audio/video
- [ ] **Lazy Loading:** Cargar previews solo cuando se expande
- [ ] **Drag-and-Drop Sorting:** Reordenar archivos visualmente
- [ ] **Batch Preview:** Ver todos los archivos como galería

### Optimizaciones
- [ ] **Cache de Previews:** Evitar recargar mismo archivo múltiples veces
- [ ] **Límite de Tamaño:** No previsualizar archivos > 100MB
- [ ] **Compresión:** Comprimir imágenes grandes para preview
- [ ] **Background Loading:** Cargar previews asíncronamente

## 📝 Notas Importantes

### ⚠️ Warning: File Pointer
**Siempre** usar `file.seek(0)` después de leer un archivo. Sin esto, el backend recibirá un archivo "vacío".

### 💾 Memory Considerations
- Streamlit carga archivos en memoria
- Archivos muy grandes (>500MB) pueden causar problemas
- Considerar límite de `maxUploadSize` en `.streamlit/config.toml`

### 🔒 Security
- No se ejecuta código de archivos subidos
- Previews usan componentes nativos de Streamlit (seguros)
- No hay procesamiento del lado del servidor en esta etapa

## 🧪 Testing

### Pruebas Recomendadas
1. ✅ Subir imagen → Verificar preview correcto
2. ✅ Subir audio → Verificar reproductor funciona
3. ✅ Subir video → Verificar reproductor funciona
4. ✅ Subir texto → Verificar contenido mostrado
5. ✅ Subir PDF → Verificar mensaje "no disponible"
6. ✅ Agrupar y enviar → Verificar archivos llegan completos al backend
7. ✅ Archivo corrupto → Verificar manejo de error graceful

### Test de Integración
```bash
# 1. Iniciar app
streamlit run app.py

# 2. Subir archivos variados
# 3. Expandir cada uno y verificar preview
# 4. Crear grupo
# 5. Enviar al servidor
# 6. Verificar en backend que archivos llegaron completos
```

## 📚 Referencias

- [Streamlit File Uploader](https://docs.streamlit.io/library/api-reference/widgets/st.file_uploader)
- [Streamlit Image](https://docs.streamlit.io/library/api-reference/media/st.image)
- [Streamlit Audio](https://docs.streamlit.io/library/api-reference/media/st.audio)
- [Streamlit Video](https://docs.streamlit.io/library/api-reference/media/st.video)
- [Python MIME Types](https://docs.python.org/3/library/mimetypes.html)

---

**Implementado:** 2025-12-29  
**Versión:** 1.1.0  
**Estado:** ✅ Producción
