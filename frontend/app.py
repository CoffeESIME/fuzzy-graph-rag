"""
GraphRAG Multimodal - Frontend de Gestión
==========================================

Aplicación Streamlit para la ingesta y control de tareas del sistema GraphRAG.

Funcionalidades:
- Tab 1: Ingesta y Agrupación de Archivos
- Tab 2: Control de Tareas en Staging (ON_HOLD)
"""

import streamlit as st
import requests
import pandas as pd
from typing import List, Dict, Any, Optional
import json
from datetime import datetime

# ==========================================
# CONFIGURACIÓN
# ==========================================

# URL del Backend (ajustar según configuración)
API_BASE_URL = st.secrets.get("API_BASE_URL", "http://localhost:8000")

# Enums del Backend
VECTOR_OPTS = [
    "visual_siglip",
    "visual_semantic", 
    "text_ocr",
    "audio_clap",
    "audio_transcript",
    "text_chunk",
    "text_summary",
    "user_memory"
]

OPERATION_OPTS = ["standard", "merge_ocr"]

PRIVACY_OPTS = [
    "strict_local",
    "public_cloud"
]

# ==========================================
# INICIALIZACIÓN DE ESTADO
# ==========================================

def init_session_state():
    """Inicializa st.session_state con valores por defecto."""
    if 'uploaded_files' not in st.session_state:
        st.session_state.uploaded_files = []
    
    if 'file_groups' not in st.session_state:
        st.session_state.file_groups = []
    
    if 'ungrouped_files' not in st.session_state:
        st.session_state.ungrouped_files = []
    
    if 'next_group_id' not in st.session_state:
        st.session_state.next_group_id = 1


# ==========================================
# FUNCIONES DE UTILIDAD
# ==========================================

def get_file_display_name(file_obj) -> str:
    """Obtiene el nombre del archivo para mostrar."""
    if hasattr(file_obj, 'name'):
        return file_obj.name
    return str(file_obj)


def create_upload_map(groups: List[Dict[str, Any]], all_files: List) -> tuple:
    """
    Crea el payload para el endpoint /ingest/upload.
    
    Returns:
        tuple: (files_to_send: List, upload_map: List[Dict])
    """
    files_to_send = []
    upload_map = []
    
    for group in groups:
        # Mapear archivos del grupo
        group_file_indices = []
        
        for file_name in group['files']:
            # Encontrar el archivo en ungrouped o uploaded
            for file_obj in all_files:
                if get_file_display_name(file_obj) == file_name:
                    files_to_send.append(file_obj)
                    group_file_indices.append(len(files_to_send) - 1)
                    break
        
        # Construir el upload_map entry
        upload_map.append({
            "file_indices": group_file_indices,
            "operation": group['operation'],
            "vector_types": group['vectors'],
            "privacy_level": group.get('privacy_level', 'strict_local'),
            "user_notes": group.get('notes', ''),
            "discard_original": group.get('discard_original', False)
        })
    
    return files_to_send, upload_map


# ==========================================
# API CALLS
# ==========================================

def send_files_to_server(files_to_send: List, upload_map: List[Dict]) -> Optional[Dict]:
    """
    Envía archivos al endpoint POST /ingest/upload.
    
    Returns:
        Dict con la respuesta del servidor o None si falla.
    """
    try:
        # Preparar files para multipart
        files_multipart = [
            ("files", (get_file_display_name(f), f, f.type if hasattr(f, 'type') else 'application/octet-stream'))
            for f in files_to_send
        ]
        
        # Preparar form data
        data = {
            "upload_map": json.dumps(upload_map)
        }
        
        # Enviar request
        response = requests.post(
            f"{API_BASE_URL}/ingest/upload",
            files=files_multipart,
            data=data,
            timeout=60
        )
        
        response.raise_for_status()
        return response.json()
        
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Error al enviar archivos al servidor: {str(e)}")
        return None


def get_on_hold_tasks() -> Optional[pd.DataFrame]:
    """
    Obtiene las tareas en estado ON_HOLD desde el backend.
    
    Returns:
        DataFrame con las tareas o None si falla.
    """
    try:
        # Nota: Necesitarás crear este endpoint en el backend
        # Por ahora, simulamos la respuesta
        response = requests.get(
            f"{API_BASE_URL}/tasks/on-hold",
            timeout=10
        )
        
        if response.status_code == 404:
            st.warning("⚠️ El endpoint /tasks/on-hold aún no está implementado en el backend.")
            return None
        
        response.raise_for_status()
        tasks = response.json()
        
        # Convertir a DataFrame
        if tasks:
            df = pd.DataFrame(tasks)
            return df
        else:
            return pd.DataFrame(columns=['id', 'filename', 'vector_type', 'status', 'created_at'])
        
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Error al obtener tareas: {str(e)}")
        return None


def trigger_processing(task_ids: List[str]) -> bool:
    """
    Envía tareas seleccionadas al endpoint POST /process/start.
    
    Returns:
        True si el envío fue exitoso, False en caso contrario.
    """
    try:
        response = requests.post(
            f"{API_BASE_URL}/process/start",
            json={"task_ids": task_ids},
            timeout=30
        )
        
        if response.status_code == 404:
            st.warning("⚠️ El endpoint /process/start aún no está implementado en el backend.")
            return False
        
        response.raise_for_status()
        return True
        
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Error al activar procesamiento: {str(e)}")
        return False


# ==========================================
# COMPONENTES UI
# ==========================================

def render_file_uploader():
    """Renderiza el cargador de archivos."""
    st.subheader("📁 Cargar Archivos")
    
    uploaded = st.file_uploader(
        "Selecciona archivos para cargar",
        accept_multiple_files=True,
        key="file_uploader"
    )
    
    if uploaded:
        # Actualizar el estado
        st.session_state.uploaded_files = uploaded
        
        # Sincronizar ungrouped_files (archivos que no están en grupos)
        grouped_file_names = set()
        for group in st.session_state.file_groups:
            grouped_file_names.update(group['files'])
        
        st.session_state.ungrouped_files = [
            f for f in uploaded 
            if get_file_display_name(f) not in grouped_file_names
        ]


def get_file_size_mb(file_obj) -> str:
    """Obtiene el tamaño del archivo en MB."""
    if hasattr(file_obj, 'size'):
        size_mb = file_obj.size / (1024 * 1024)
        if size_mb < 0.01:
            return f"{file_obj.size / 1024:.2f} KB"
        return f"{size_mb:.2f} MB"
    return "Tamaño desconocido"


def render_file_preview(file_obj):
    """
    Renderiza la previsualización inteligente del archivo según su tipo MIME.
    
    Args:
        file_obj: UploadFile object de Streamlit
    """
    mime_type = getattr(file_obj, 'type', 'application/octet-stream')
    
    # Detectar categoría de archivo
    if mime_type.startswith('image/'):
        # Previsualización de imágenes
        try:
            st.image(file_obj, caption="Preview", use_container_width=True)
            file_obj.seek(0)  # Reset file pointer para upload posterior
        except Exception as e:
            st.warning(f"⚠️ No se pudo cargar la imagen: {str(e)}")
            file_obj.seek(0)
    
    elif mime_type.startswith('audio/'):
        # Previsualización de audio
        try:
            st.audio(file_obj)
            file_obj.seek(0)  # Reset file pointer
        except Exception as e:
            st.warning(f"⚠️ No se pudo cargar el audio: {str(e)}")
            file_obj.seek(0)
    
    elif mime_type.startswith('video/'):
        # Previsualización de video
        try:
            st.video(file_obj)
            file_obj.seek(0)  # Reset file pointer
        except Exception as e:
            st.warning(f"⚠️ No se pudo cargar el video: {str(e)}")
            file_obj.seek(0)
    
    elif mime_type.startswith('text/'):
        # Previsualización de archivos de texto
        try:
            content = file_obj.read()
            file_obj.seek(0)  # Reset file pointer
            
            # Decodificar y mostrar (limitado a primeros 1000 caracteres)
            try:
                text_content = content.decode('utf-8')
                preview_text = text_content[:1000]
                if len(text_content) > 1000:
                    preview_text += "\n\n... (contenido truncado)"
                st.code(preview_text, language='text')
            except UnicodeDecodeError:
                st.info("📄 Archivo de texto detectado (no se puede previsualizar)")
        except Exception as e:
            st.warning(f"⚠️ No se pudo leer el archivo: {str(e)}")
            file_obj.seek(0)
    
    else:
        # Tipos no soportados
        st.info(f"📄 Preview no disponible para este formato (`{mime_type}`)")


def render_ungrouped_files():
    """Renderiza la lista de archivos sin asignar con previsualización inteligente."""
    st.subheader("📋 Archivos Sin Asignar")
    
    if not st.session_state.ungrouped_files:
        st.info("✨ Todos los archivos han sido asignados a grupos.")
        return
    
    st.markdown(f"**Total de archivos sin asignar:** {len(st.session_state.ungrouped_files)}")
    
    # Renderizar cada archivo con su preview
    for idx, file_obj in enumerate(st.session_state.ungrouped_files):
        filename = get_file_display_name(file_obj)
        file_size = get_file_size_mb(file_obj)
        mime_type = getattr(file_obj, 'type', 'unknown')
        
        # Crear expander para cada archivo
        with st.expander(
            f"📎 **{filename}** ({file_size}) — `{mime_type}`",
            expanded=False
        ):
            # Renderizar preview inteligente
            render_file_preview(file_obj)


def render_group_builder():
    """Renderiza el constructor de grupos."""
    st.subheader("🔧 Constructor de Grupos")
    
    if not st.session_state.ungrouped_files:
        st.warning("⚠️ No hay archivos disponibles para agrupar. Carga archivos primero.")
        return
    
    with st.form("group_builder_form"):
        st.markdown("##### Crear Nuevo Grupo")
        
        # Selector de archivos
        available_file_names = [get_file_display_name(f) for f in st.session_state.ungrouped_files]
        selected_files = st.multiselect(
            "Selecciona archivos para el grupo",
            options=available_file_names,
            help="Elige uno o más archivos para agrupar"
        )
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Tipo de operación
            operation = st.selectbox(
                "Tipo de Operación",
                options=OPERATION_OPTS,
                format_func=lambda x: "Estándar (1 archivo = 1 asset)" if x == "standard" else "Merge OCR (N archivos = 1 asset)",
                help="Define cómo se procesarán los archivos"
            )
        
        with col2:
            # Vectores deseados
            vectors = st.multiselect(
                "Vectores Deseados",
                options=VECTOR_OPTS,
                help="Selecciona los tipos de vectorización a aplicar"
            )
        
        # Privacy Level selector
        privacy_level = st.selectbox(
            "🔐 Nivel de Privacidad",
            options=PRIVACY_OPTS,
            index=0,  # Default: strict_local
            format_func=lambda x: "🔒 Estricto Local (no cloud AI)" if x == "strict_local" else "☁️ Nube Pública (OpenAI, etc.)",
            help="Controla dónde se puede procesar la data: local only o permite APIs externas"
        )
        
        # Opciones adicionales
        discard_original = st.checkbox(
            "Descartar Original",
            help="Eliminar archivos binarios después de la extracción (útil para transmutación)"
        )
        
        notes = st.text_area(
            "Notas del Usuario (Opcional)",
            placeholder="Ej: Twitter thread sobre IA, Screenshots de tutorial, etc.",
            help="Contexto adicional para este grupo"
        )
        
        # Botón para crear grupo
        submit_button = st.form_submit_button("✅ Crear Grupo", type="primary")
        
        if submit_button:
            # Validaciones
            if not selected_files:
                st.error("❌ Selecciona al menos un archivo.")
            elif not vectors:
                st.error("❌ Selecciona al menos un tipo de vector.")
            else:
                # Crear grupo
                new_group = {
                    'id': st.session_state.next_group_id,
                    'files': selected_files,
                    'operation': operation,
                    'vectors': vectors,
                    'privacy_level': privacy_level,
                    'discard_original': discard_original,
                    'notes': notes
                }
                
                st.session_state.file_groups.append(new_group)
                st.session_state.next_group_id += 1
                
                # Remover archivos de ungrouped
                st.session_state.ungrouped_files = [
                    f for f in st.session_state.ungrouped_files
                    if get_file_display_name(f) not in selected_files
                ]
                
                st.success(f"✅ Grupo {new_group['id']} creado exitosamente con {len(selected_files)} archivo(s).")
                st.rerun()


def render_ready_groups():
    """Renderiza los grupos listos para enviar."""
    st.subheader("📦 Grupos Listos")
    
    if not st.session_state.file_groups:
        st.info("📭 No hay grupos creados aún.")
        return
    
    for group in st.session_state.file_groups:
        with st.expander(f"**Grupo {group['id']}** — {len(group['files'])} archivo(s)", expanded=False):
            # Archivos
            st.markdown("**Archivos:**")
            for fname in group['files']:
                st.text(f"  • {fname}")
            
            # Detalles
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Operación:** `{group['operation']}`")
                st.markdown(f"**Descartar Original:** {'✅ Sí' if group['discard_original'] else '❌ No'}")
                privacy_icon = "🔒" if group.get('privacy_level', 'strict_local') == 'strict_local' else "☁️"
                privacy_text = "Estricto Local" if group.get('privacy_level', 'strict_local') == 'strict_local' else "Nube Pública"
                st.markdown(f"**Privacidad:** {privacy_icon} {privacy_text}")
            
            with col2:
                st.markdown(f"**Vectores:** {', '.join([f'`{v}`' for v in group['vectors']])}")
            
            if group.get('notes'):
                st.markdown(f"**Notas:** {group['notes']}")
            
            # Botón para eliminar
            if st.button(f"🗑️ Eliminar Grupo {group['id']}", key=f"delete_group_{group['id']}"):
                # Devolver archivos a ungrouped
                for fname in group['files']:
                    for file_obj in st.session_state.uploaded_files:
                        if get_file_display_name(file_obj) == fname:
                            st.session_state.ungrouped_files.append(file_obj)
                            break
                
                # Remover grupo
                st.session_state.file_groups = [g for g in st.session_state.file_groups if g['id'] != group['id']]
                st.success(f"Grupo {group['id']} eliminado.")
                st.rerun()


def render_send_button():
    """Renderiza el botón de envío al servidor."""
    st.markdown("---")
    
    if not st.session_state.file_groups:
        st.warning("⚠️ Crea al menos un grupo antes de enviar al servidor.")
        return
    
    if st.button("🚀 Enviar al Servidor", type="primary", use_container_width=True):
        with st.spinner("Enviando archivos al servidor..."):
            # Preparar payload
            files_to_send, upload_map = create_upload_map(
                st.session_state.file_groups,
                st.session_state.uploaded_files
            )
            
            # Enviar
            response = send_files_to_server(files_to_send, upload_map)
            
            if response and response.get('success'):
                st.success(f"✅ {response.get('message', 'Archivos enviados exitosamente!')}")
                
                # Mostrar detalles
                with st.expander("Ver detalles de la respuesta"):
                    st.json(response)
                
                # Limpiar estado
                st.session_state.file_groups = []
                st.session_state.ungrouped_files = []
                st.session_state.uploaded_files = []
                
                st.info("🔄 Estado limpiado. Puedes cargar nuevos archivos.")
            else:
                st.error("❌ Error al enviar archivos. Revisa los logs.")


def render_task_dashboard():
    """Renderiza el dashboard de tareas en staging."""
    st.subheader("📊 Dashboard de Tareas ON_HOLD")
    
    # Botón de refrescar
    if st.button("🔄 Refrescar", key="refresh_tasks"):
        st.rerun()
    
    # Obtener tareas
    with st.spinner("Cargando tareas..."):
        df = get_on_hold_tasks()
    
    if df is None:
        st.error("❌ No se pudieron cargar las tareas.")
        return
    
    if df.empty:
        st.info("✨ No hay tareas en estado ON_HOLD.")
        return
    
    # Mostrar tabla
    st.markdown(f"**Total de tareas:** {len(df)}")
    
    # Tabla interactiva con selección
    st.markdown("##### Selecciona tareas para procesar:")
    
    # Configurar editor
    edited_df = st.data_editor(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "id": st.column_config.TextColumn("ID", width="small"),
            "filename": st.column_config.TextColumn("Archivo", width="medium"),
            "vector_type": st.column_config.TextColumn("Vector Type", width="medium"),
            "status": st.column_config.TextColumn("Estado", width="small"),
            "created_at": st.column_config.TextColumn("Creado", width="medium")
        },
        disabled=True,  # No editable
        key="task_table"
    )
    
    # Selector manual (alternativa si data_editor no soporta selección múltiple)
    st.markdown("##### O ingresa IDs manualmente:")
    task_ids_input = st.text_input(
        "IDs de tareas (separados por comas)",
        placeholder="ej: 123e4567-e89b-12d3-a456-426614174000, 987fcdeb-51a2-...",
        help="Copia y pega los IDs de las tareas que deseas procesar"
    )
    
    if st.button("▶️ Procesar Seleccionados", type="primary"):
        # Parsear IDs
        if task_ids_input:
            task_ids = [tid.strip() for tid in task_ids_input.split(',') if tid.strip()]
        else:
            st.warning("⚠️ Ingresa al menos un ID de tarea.")
            return
        
        # Enviar al backend
        with st.spinner(f"Activando procesamiento de {len(task_ids)} tarea(s)..."):
            success = trigger_processing(task_ids)
        
        if success:
            st.success(f"✅ {len(task_ids)} tarea(s) enviadas a procesamiento.")
            st.rerun()


# ==========================================
# MAIN APP
# ==========================================

def main():
    st.set_page_config(
        page_title="GraphRAG Multimodal - Control Panel",
        page_icon="🧠",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    # Inicializar estado
    init_session_state()
    
    # Header
    st.title("🧠 GraphRAG Multimodal — Panel de Control")
    st.markdown("Sistema de gestión para ingesta y procesamiento de datos multimodales.")
    
    # Tabs principales
    tab1, tab2 = st.tabs(["📤 Ingesta y Agrupación", "⚙️ Control de Tareas"])
    
    # --- TAB 1: INGESTA ---
    with tab1:
        st.header("Ingesta y Agrupación de Archivos")
        
        # Cargador
        render_file_uploader()
        
        st.markdown("---")
        
        # Archivos sin asignar
        render_ungrouped_files()
        
        st.markdown("---")
        
        # Constructor de grupos
        render_group_builder()
        
        st.markdown("---")
        
        # Grupos listos
        render_ready_groups()
        
        # Botón de envío
        render_send_button()
    
    # --- TAB 2: CONTROL DE TAREAS ---
    with tab2:
        st.header("Control de Tareas en Staging")
        
        render_task_dashboard()
    
    # Footer
    st.markdown("---")
    st.caption("GraphRAG Multimodal v2 — Hybrid Worker-Server Architecture")


if __name__ == "__main__":
    main()
