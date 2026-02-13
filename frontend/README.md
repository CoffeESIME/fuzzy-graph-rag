# GraphRAG Multimodal - Admin Frontend (Streamlit)

> **⚠️ ADMIN PANEL ONLY:** Esta aplicación es el **Panel de Administración** para Ingesta y Control de Tareas. 
> Para la interfaz de **Búsqueda (Usuario Final)**, por favor diríjase a `../search-app`.

Interfaz de usuario Streamlit para el sistema GraphRAG Multimodal.

## 🚀 Características

### Tab 1: Ingesta y Agrupación
- **Carga de Archivos**: Sube múltiples archivos simultáneamente
- **🎨 Previsualización Inteligente**: 
  - Vista previa automática de imágenes, audio, video y texto
  - Detecta tipo MIME y muestra preview apropiado
  - Verifica contenido antes de agrupar
  - Ver [FILE_PREVIEW_GUIDE.md](FILE_PREVIEW_GUIDE.md) para detalles
- **Constructor de Grupos**: 
  - Agrupa archivos según tipo de operación (Standard/Merge OCR)
  - Configura vectores deseados (VISUAL_SIGLIP, TEXT_OCR, AUDIO_CLAP, etc.)
  - Opciones avanzadas: Descartar originales, notas personalizadas
- **Visualización de Grupos**: Vista clara de grupos creados con opción de eliminar
- **Envío Inteligente**: Mapeo automático de índices para el backend

### Tab 2: Control de Tareas
- **Dashboard de Staging**: Visualiza todas las tareas en estado ON_HOLD
- **Activación Selectiva**: Selecciona y procesa tareas específicas
- **Auto-refresh**: Actualización manual del estado de tareas

## 📋 Requisitos Previos

- Python 3.10+
- Backend FastAPI ejecutándose (ver `/backend`)

## 🛠️ Instalación

1. **Crear entorno virtual** (recomendado):
```bash
cd frontend
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

2. **Instalar dependencias**:
```bash
pip install -r requirements.txt
```

3. **Configurar secrets**:
```bash
# Copiar template
cp .streamlit/secrets.toml.template .streamlit/secrets.toml

# Editar con tu configuración
# Actualizar API_BASE_URL si el backend no está en localhost:8000
```

## ▶️ Ejecución

```bash
streamlit run app.py
```

La aplicación se abrirá en `http://localhost:8501`

## 🧠 Uso

### Flujo Típico de Ingesta

1. **Cargar archivos**: Usa el uploader para seleccionar tus archivos
2. **🎨 Previsualizar**: Expande archivos en "Sin Asignar" para verificar contenido
   - Imágenes se muestran completas
   - Audio/video tienen reproductores integrados
   - Texto muestra primeros 1000 caracteres
3. **Crear grupos**: 
   - Selecciona archivos de la lista "Sin Asignar"
   - Elige operación (Standard para 1:1, Merge OCR para N:1)
   - Selecciona vectores deseados
   - Opcionalmente marca "Descartar Original" para transmutación
   - Agrega notas contextuales
4. **Revisar grupos**: Verifica tus grupos en la sección "Grupos Listos"
5. **Enviar**: Presiona "Enviar al Servidor" para iniciar la ingesta

### Flujo de Control de Tareas

1. **Ver tareas ON_HOLD**: Tab 2 muestra todas las tareas en staging
2. **Seleccionar tareas**: Copia los IDs de las tareas que deseas procesar
3. **Activar procesamiento**: Ingresa los IDs y presiona "Procesar Seleccionados"

## 🗂️ Estructura

```
frontend/
├── app.py                      # Aplicación principal
├── requirements.txt            # Dependencias Python
├── .streamlit/
│   ├── config.toml            # Configuración de tema y servidor
│   └── secrets.toml.template  # Template para configuración
└── README.md
```

## 🔧 Configuración Avanzada

### Tema
Edita `.streamlit/config.toml` para personalizar colores y fuentes.

### Límites de Upload
Por defecto, `maxUploadSize = 500` MB. Ajustar según necesidades.

### CORS
Si el backend está en otro dominio, actualizar `enableCORS = true` y configurar CORS en FastAPI.

## 🐛 Troubleshooting

### "Error al enviar archivos al servidor"
- Verifica que el backend esté ejecutándose
- Confirma que `API_BASE_URL` en secrets.toml sea correcto
- Revisa los logs del backend para más detalles

### "El endpoint /tasks/on-hold aún no está implementado"
- El Tab 2 requiere endpoints adicionales en el backend:
  - `GET /tasks/on-hold`: Lista tareas en staging
  - `POST /process/start`: Activa procesamiento

**Endpoints Pendientes en Backend**:

```python
# En app/routers/__init__.py o nuevo router

@router.get("/tasks/on-hold")
async def get_on_hold_tasks(session: Session = Depends(get_session)):
    """Obtiene todas las tareas en estado ON_HOLD."""
    from app.models.vector_status import VectorStatus
    from app.models.asset import Asset
    
    tasks = session.exec(
        select(VectorStatus, Asset.filename)
        .join(Asset)
        .where(VectorStatus.status == JobStatus.ON_HOLD)
    ).all()
    
    return [
        {
            "id": str(task[0].id),
            "filename": task[1],
            "vector_type": task[0].vector_type,
            "status": task[0].status,
            "created_at": task[0].created_at.isoformat()
        }
        for task in tasks
    ]

@router.post("/process/start")
async def start_processing(
    task_ids: List[str],
    session: Session = Depends(get_session)
):
    """Activa el procesamiento de tareas seleccionadas."""
    # Lógica para cambiar estado a PENDING y enviar a Celery
    pass
```

## 📚 Recursos

- [Documentación Streamlit](https://docs.streamlit.io)
- [FastAPI Docs](https://fastapi.tiangolo.com)
- [GraphRAG Backend](../backend/README.md)

## 📄 Licencia

Parte del proyecto Multimodal Graph RAG v2
