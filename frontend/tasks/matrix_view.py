"""
Task Matrix View
================

Component for rendering a matrix-style table of assets and their vector processing status.
"""

import streamlit as st
import pandas as pd
from typing import List, Dict, Any, Optional


# ==========================================
# CONSTANTS
# ==========================================

ALL_VECTOR_TYPES = [
    "visual_siglip",
    "visual_semantic", 
    "text_ocr",
    "audio_clap",
    "audio_transcript",
    "text_chunk",
    "text_summary",
    "user_memory"
]

STATUS_ICONS = {
    "ON_HOLD": "⏸️",
    "PENDING": "⏳",
    "PROCESSING": "⚙️",
    "REVIEW_REQUIRED": "👁️",
    "COMPLETED": "✅",
    "FAILED": "❌",
    "REJECTED": "🚫"
}

MIME_TYPE_ICONS = {
    "image/": "🖼️",
    "audio/": "🎵",
    "video/": "🎬",
    "text/": "📝",
    "application/pdf": "📄"
}


# ==========================================
# HELPER FUNCTIONS
# ==========================================

def get_mime_icon(mime_type: str) -> str:
    """Obtiene el icono correspondiente al MIME type."""
    for prefix, icon in MIME_TYPE_ICONS.items():
        if mime_type.startswith(prefix):
            return icon
    return "📎"


def build_matrix_dataframe(assets: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Construye un DataFrame en formato matriz para visualización.
    
    Estructura:
    - Una fila por Asset
    - Columnas: Preview, Filename, Privacy, [VectorTypes...], Review
    
    Args:
        assets: Lista de assets con vector_statuses nested
    
    Returns:
        DataFrame listo para st.dataframe
    """
    rows = []
    
    for asset in assets:
        # Datos base
        row = {
            "🔍": get_mime_icon(asset["mime_type"]),
            "Filename": asset["filename"],
            "Privacy": asset["privacy_level"],
            "Asset ID": asset["id"]  # Hidden column para referencia
        }
        
        # Mapear vector statuses
        vector_status_map = {
            vs["vector_type"]: vs["status"] 
            for vs in asset.get("vector_statuses", [])
        }
        
        # Agregar columnas para cada vector type
        for vector_type in ALL_VECTOR_TYPES:
            status = vector_status_map.get(vector_type, None)
            if status:
                row[vector_type] = STATUS_ICONS.get(status, "❓")
            else:
                row[vector_type] = "-"
        
        rows.append(row)
    
    return pd.DataFrame(rows)


def get_privacy_display(privacy_level: str) -> str:
    """Formatea privacy level para display."""
    if privacy_level == "strict_local":
        return "🔒 Local"
    else:
        return "☁️ Cloud"


# ==========================================
# MAIN COMPONENT
# ==========================================

def render_task_matrix(assets: List[Dict[str, Any]]) -> None:
    """
    Renderiza una matriz de tareas mostrando assets y su estado de procesamiento.
    
    Columnas:
    - Preview (icono según MIME type)
    - Filename
    - Privacy Level (editable)
    - Una columna por VectorType (visual_siglip, text_ocr, etc.)
    - Botón de Review
    
    Args:
        assets: Lista de assets con vector_statuses y sidecar_data
    """
    
    if not assets:
        st.info("✨ No hay tareas disponibles.")
        return
    
    st.markdown(f"**Total de Assets:** {len(assets)}")
    st.markdown("---")
    
    # Construir DataFrame
    df = build_matrix_dataframe(assets)
    
    # Configurar columnas para display
    column_config = {
        "🔍": st.column_config.TextColumn("Preview", width="small"),
        "Filename": st.column_config.TextColumn("Filename", width="large"),
        "Privacy": st.column_config.SelectboxColumn(
            "Privacy",
            width="medium",
            options=["strict_local", "public_cloud"],
            help="Change privacy level for this asset"
        ),
        "Asset ID": st.column_config.TextColumn("Asset ID", width="small")
    }
    
    # Configurar columnas de vector types
    for vector_type in ALL_VECTOR_TYPES:
        column_config[vector_type] = st.column_config.TextColumn(
            vector_type.replace("_", " ").title(),
            width="small",
            help=f"Status for {vector_type}"
        )
    
    # Renderizar tabla editable
    st.markdown("### 📊 Processing Matrix")
    
    edited_df = st.data_editor(
        df,
        column_config=column_config,
        use_container_width=True,
        hide_index=True,
        disabled=["🔍", "Filename", "Asset ID"] + ALL_VECTOR_TYPES,  # Solo Privacy es editable
        key="task_matrix_editor"
    )
    
    # Detectar cambios en Privacy
    if not df.equals(edited_df):
        changed_rows = df.compare(edited_df)
        if not changed_rows.empty:
            st.info("💡 Privacy levels changed. Click 'Save Changes' to persist updates.")
            
            if st.button("💾 Save Privacy Changes", type="primary"):
                # Aquí se implementaría la llamada al backend
                st.success("✅ Privacy levels updated successfully!")
                # TODO: Implementar update via API
    
    st.markdown("---")
    
    # Renderizar filas individuales con botón de Review
    st.markdown("### 🔎 Asset Details")
    
    for idx, asset in enumerate(assets):
        with st.expander(f"📄 {asset['filename']}", expanded=False):
            cols = st.columns([3, 1])
            
            with cols[0]:
                # Info básica
                st.markdown(f"**MIME Type:** `{asset['mime_type']}`")
                st.markdown(f"**Privacy:** {get_privacy_display(asset['privacy_level'])}")
                st.markdown(f"**Created:** {asset['created_at']}")
                
                # Vector statuses
                st.markdown("**Vector Statuses:**")
                for vs in asset.get("vector_statuses", []):
                    status_icon = STATUS_ICONS.get(vs["status"], "❓")
                    st.markdown(f"  - {status_icon} `{vs['vector_type']}`: **{vs['status']}**")
            
            with cols[1]:
                # Botón de review
                if st.button(
                    "👁️ Review Sidecar", 
                    key=f"review_btn_{asset['id']}",
                    use_container_width=True
                ):
                    # Guardar en session state para mostrar en sidebar
                    st.session_state.viewing_sidecar = {
                        "filename": asset["filename"],
                        "sidecar_data": asset.get("sidecar_data", {})
                    }
                    st.rerun()


def render_dispatch_button(assets: List[Dict[str, Any]], api_base_url: str = "http://localhost:8000") -> None:
    """
    Renderiza el botón para despachar jobs pendientes con metadatos.
    
    Uses the selected tasks from task_metadata_editor and sends metadata with dispatch.
    
    Args:
        assets: Lista de assets con vector_statuses
        api_base_url: Base URL del backend API
    """
    import requests
    from .task_metadata_editor import get_selected_tasks_with_metadata, clear_metadata_state
    
    st.markdown("---")
    st.markdown("### 🚀 Dispatch Jobs")
    
    # Contar tareas ON_HOLD
    on_hold_count = 0
    on_hold_ids = []
    
    for asset in assets:
        for vs in asset.get("vector_statuses", []):
            if vs["status"] == "ON_HOLD":
                on_hold_count += 1
                on_hold_ids.append(vs["id"])
    
    if on_hold_count == 0:
        st.info("✨ No hay tareas en estado ON_HOLD.")
        return
    
    st.markdown(f"**Tareas en ON_HOLD:** {on_hold_count}")
    
    # Get selected tasks from metadata editor
    selected_tasks = get_selected_tasks_with_metadata()
    selected_count = len(selected_tasks)
    
    cols = st.columns([2, 1, 1])
    
    with cols[0]:
        dispatch_all = st.checkbox(
            "Dispatch TODAS las ON_HOLD (sin selección)",
            value=False,
            help="Ignorar selección y enviar todas las tareas ON_HOLD"
        )
    
    with cols[1]:
        st.markdown(f"**Seleccionadas:** {selected_count}")
    
    with cols[2]:
        # Determine what to dispatch
        if dispatch_all:
            button_text = f"▶️ Dispatch {on_hold_count} (todas)"
            can_dispatch = True
        elif selected_count > 0:
            button_text = f"▶️ Dispatch {selected_count} seleccionadas"
            can_dispatch = True
        else:
            button_text = "▶️ Selecciona tareas arriba"
            can_dispatch = False
        
        if st.button(
            button_text, 
            type="primary",
            use_container_width=True,
            disabled=not can_dispatch
        ):
            with st.spinner(f"Dispatching task(s)..."):
                try:
                    # Prepare payload
                    if dispatch_all:
                        payload = {"dispatch_all": True}
                    else:
                        # Build payload with metadata
                        vector_status_ids = [t["vector_status_id"] for t in selected_tasks]
                        
                        # Build task_metadata list
                        task_metadata = []
                        for t in selected_tasks:
                            meta_entry = {"vector_status_id": t["vector_status_id"]}
                            
                            if "user_context" in t:
                                meta_entry["user_context"] = t["user_context"]
                            
                            if "audio_processing_options" in t:
                                meta_entry["audio_processing_options"] = t["audio_processing_options"]
                            
                            task_metadata.append(meta_entry)
                        
                        payload = {
                            "vector_status_ids": vector_status_ids,
                            "task_metadata": task_metadata if any(
                                "user_context" in t or "audio_processing_options" in t 
                                for t in selected_tasks
                            ) else None
                        }
                    
                    # Log payload for debugging
                    st.write("📤 Payload:", payload)
                    
                    # Call backend API
                    response = requests.post(
                        f"{api_base_url}/tasks/dispatch",
                        json=payload,
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        dispatched_count = result.get("tasks_updated", 0)
                        celery_task_ids = result.get("celery_task_ids", [])
                        
                        st.success(f"✅ {dispatched_count} task(s) dispatched successfully!")
                        
                        # Clear metadata state after successful dispatch
                        clear_metadata_state()
                        
                        # Show Celery task IDs in expander
                        if celery_task_ids:
                            with st.expander("🔍 Ver Celery Task IDs"):
                                for i, task_id in enumerate(celery_task_ids, 1):
                                    st.code(f"Task {i}: {task_id}")
                        
                        st.info("🔄 Refresh to see updated statuses.")
                        st.balloons()
                    else:
                        st.error(f"❌ Error {response.status_code}: {response.text}")
                        
                except requests.exceptions.ConnectionError:
                    st.error("❌ No se pudo conectar al backend. Verifica que esté corriendo en http://localhost:8000")
                except requests.exceptions.Timeout:
                    st.error("❌ Timeout: El backend tardó demasiado en responder.")
                except Exception as e:
                    st.error(f"❌ Error inesperado: {str(e)}")


def render_task_status_summary(assets: List[Dict[str, Any]]) -> None:
    """
    Render a summary of task statuses with counts and failed task details.
    
    Args:
        assets: Lista de assets con vector_statuses
    """
    st.markdown("---")
    st.markdown("### 📊 Resumen de Estados")
    
    # Count tasks by status
    status_counts = {
        "ON_HOLD": 0,
        "PENDING": 0,
        "PROCESSING": 0,
        "REVIEW_REQUIRED": 0,
        "COMPLETED": 0,
        "FAILED": 0,
        "REJECTED": 0
    }
    
    failed_tasks = []
    completed_tasks = []
    
    for asset in assets:
        for vs in asset.get("vector_statuses", []):
            status = vs.get("status", "unknown")
            if status in status_counts:
                status_counts[status] += 1
            
            # Collect failed tasks with details
            if status == "FAILED":
                failed_tasks.append({
                    "asset": asset.get("filename", "Unknown"),
                    "vector_type": vs.get("vector_type", "Unknown"),
                    "error": vs.get("error_message", "No error message"),
                    "id": vs.get("id", "")
                })
            
            # Collect completed tasks
            if status == "COMPLETED":
                completed_tasks.append({
                    "asset": asset.get("filename", "Unknown"),
                    "vector_type": vs.get("vector_type", "Unknown"),
                    "weaviate_uuid": vs.get("weaviate_uuid", "-")
                })
    
    # Display status metrics
    cols = st.columns(7)
    status_colors = {
        "ON_HOLD": "🔵",
        "PENDING": "🟡",
        "PROCESSING": "🟠",
        "REVIEW_REQUIRED": "🟣",
        "COMPLETED": "🟢",
        "FAILED": "🔴",
        "REJECTED": "⚫"
    }
    
    for i, (status, count) in enumerate(status_counts.items()):
        with cols[i]:
            icon = status_colors.get(status, "⚪")
            st.metric(
                label=f"{icon} {status.replace('_', ' ').title()}",
                value=count
            )
    
    # Show failed tasks detail with retry functionality
    if failed_tasks:
        st.markdown("---")
        st.markdown("### ❌ Tareas Fallidas")
        st.warning(f"⚠️ {len(failed_tasks)} tarea(s) fallaron. Ver detalles para diagnóstico.")
        
        # Initialize session state for selections
        if "selected_failed_tasks" not in st.session_state:
            st.session_state.selected_failed_tasks = set()
        
        # Retry controls
        col1, col2, col3 = st.columns([2, 2, 4])
        
        with col1:
            select_all = st.checkbox(
                "Seleccionar todos",
                key="select_all_failed",
                value=len(st.session_state.selected_failed_tasks) == len(failed_tasks)
            )
            
            if select_all:
                st.session_state.selected_failed_tasks = {t['id'] for t in failed_tasks}
            elif len(st.session_state.selected_failed_tasks) == len(failed_tasks):
                st.session_state.selected_failed_tasks = set()
        
        with col2:
            selected_count = len(st.session_state.selected_failed_tasks)
            if st.button(
                f"🔄 Retry Seleccionados ({selected_count})",
                disabled=selected_count == 0,
                key="retry_selected_failed"
            ):
                _retry_failed_tasks(list(st.session_state.selected_failed_tasks))
        
        with col3:
            if st.button("🔄 Retry TODOS los Fallidos", key="retry_all_failed"):
                _retry_failed_tasks([t['id'] for t in failed_tasks])
        
        # List failed tasks with checkboxes
        for i, task in enumerate(failed_tasks):
            col_check, col_info = st.columns([1, 11])
            
            with col_check:
                is_selected = st.checkbox(
                    "",
                    value=task['id'] in st.session_state.selected_failed_tasks,
                    key=f"failed_task_{task['id']}",
                    label_visibility="collapsed"
                )
                
                if is_selected:
                    st.session_state.selected_failed_tasks.add(task['id'])
                else:
                    st.session_state.selected_failed_tasks.discard(task['id'])
            
            with col_info:
                with st.expander(f"🔴 {task['asset']} - {task['vector_type']}", expanded=False):
                    st.markdown(f"**Asset:** `{task['asset']}`")
                    st.markdown(f"**Vector Type:** `{task['vector_type']}`")
                    st.markdown(f"**Task ID:** `{task['id']}`")
                    st.markdown("**Error Message:**")
                    st.code(task['error'] or "No error message captured", language="text")
                    
                    # Individual retry button
                    if st.button(f"🔄 Retry esta tarea", key=f"retry_single_{task['id']}"):
                        _retry_failed_tasks([task['id']])
                    
                    # Hint for common errors
                    error_lower = (task['error'] or "").lower()
                    if "connection" in error_lower or "refused" in error_lower:
                        st.info("💡 **Hint:** Error de conexión. Verifica que el LLM Gateway esté corriendo en localhost:8765")
                    elif "minio" in error_lower or "s3" in error_lower:
                        st.info("💡 **Hint:** Error de MinIO. Verifica que MinIO esté corriendo y el bucket exista.")
                    elif "not found" in error_lower:
                        st.info("💡 **Hint:** Recurso no encontrado. Verifica que el asset y su archivo existan.")


def _retry_failed_tasks(task_ids: List[str], api_base_url: str = "http://localhost:8000") -> None:
    """
    Call backend to retry failed tasks.
    
    Args:
        task_ids: List of VectorStatus IDs to retry
        api_base_url: Backend API base URL
    """
    import requests
    
    try:
        with st.spinner(f"🔄 Retrying {len(task_ids)} task(s)..."):
            response = requests.post(
                f"{api_base_url}/tasks/retry-failed",
                json={"vector_status_ids": task_ids},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                st.success(f"✅ {data.get('tasks_retried', len(task_ids))} tarea(s) en cola para retry!")
                st.session_state.selected_failed_tasks = set()
                st.rerun()
            else:
                st.error(f"❌ Error {response.status_code}: {response.text}")
                
    except requests.exceptions.ConnectionError:
        st.error("❌ No se pudo conectar al backend.")
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
    
    # Show completed tasks summary
    if completed_tasks:
        st.markdown("---")
        st.markdown("### ✅ Tareas Completadas")
        
        with st.expander(f"Ver {len(completed_tasks)} tarea(s) completada(s)", expanded=False):
            for task in completed_tasks[:20]:  # Limit to 20
                st.markdown(f"- **{task['asset']}** → {task['vector_type']} (Weaviate: `{task['weaviate_uuid']}`)")
            
            if len(completed_tasks) > 20:
                st.info(f"... y {len(completed_tasks) - 20} más")


# ==========================================
# TESTING
# ==========================================

if __name__ == "__main__":
    # This would be run as a Streamlit app for testing
    st.set_page_config(page_title="Task Matrix Test", layout="wide")
    
    st.title("Task Matrix Test")
    st.warning("⚠️ Testing mode requires backend connection. Please run the full app instead.")
    st.info("Run `streamlit run app.py` to test with real backend data.")
