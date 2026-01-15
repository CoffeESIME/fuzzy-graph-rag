"""
Task Metadata Editor
====================

Component for editing metadata on individual tasks before dispatch.
Shows task-specific forms (user_context for all, audio_processing_options for AUDIO_TRANSCRIPT).
"""

import streamlit as st
from typing import List, Dict, Any, Callable, Optional


# ==========================================
# CONSTANTS
# ==========================================

AUDIO_TRANSCRIPT_TYPES = ["audio_transcript"]

STATUS_ICONS = {
    "ON_HOLD": "⏸️",
    "PENDING": "⏳",
    "PROCESSING": "⚙️",
    "REVIEW_REQUIRED": "👁️",
    "COMPLETED": "✅",
    "FAILED": "❌",
}


# ==========================================
# HELPER FUNCTIONS
# ==========================================

def get_tasks_for_editing(assets: List[Dict[str, Any]], only_on_hold: bool = True) -> List[Dict[str, Any]]:
    """
    Extract all tasks (vector statuses) that can be edited.
    
    Args:
        assets: List of assets with vector_statuses
        only_on_hold: If True, only return ON_HOLD tasks
    
    Returns:
        List of task dicts with asset info included
    """
    tasks = []
    for asset in assets:
        for vs in asset.get("vector_statuses", []):
            if only_on_hold and vs["status"] != "ON_HOLD":
                continue
            tasks.append({
                "vector_status_id": vs["id"],
                "vector_type": vs["vector_type"],
                "status": vs["status"],
                "asset_id": asset["id"],
                "filename": asset["filename"],
                "mime_type": asset["mime_type"],
            })
    return tasks


def init_metadata_state():
    """Initialize session state for metadata editing."""
    if "task_metadata_state" not in st.session_state:
        st.session_state.task_metadata_state = {}
    if "selected_tasks_for_dispatch" not in st.session_state:
        st.session_state.selected_tasks_for_dispatch = set()


# ==========================================
# MAIN COMPONENT
# ==========================================

def render_task_metadata_editor(
    assets: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """
    Render editors for each ON_HOLD task with metadata forms.
    
    Args:
        assets: List of assets with vector_statuses
    
    Returns:
        Dict mapping vector_status_id -> metadata dict
    """
    init_metadata_state()
    
    # Get editable tasks
    tasks = get_tasks_for_editing(assets, only_on_hold=True)
    
    if not tasks:
        st.info("✨ No hay tareas ON_HOLD disponibles para editar.")
        return {}
    
    st.markdown("### 📝 Configuración de Tareas")
    st.markdown(f"Selecciona las tareas a procesar y opcionalmente agrega metadatos.")
    st.markdown("---")
    
    # Select all / deselect all
    col1, col2, col3 = st.columns([2, 2, 4])
    with col1:
        if st.button("✅ Seleccionar Todas", key="select_all_tasks"):
            st.session_state.selected_tasks_for_dispatch = {t["vector_status_id"] for t in tasks}
            st.rerun()
    with col2:
        if st.button("❌ Deseleccionar Todas", key="deselect_all_tasks"):
            st.session_state.selected_tasks_for_dispatch = set()
            st.rerun()
    with col3:
        selected_count = len(st.session_state.selected_tasks_for_dispatch)
        st.markdown(f"**Seleccionadas:** {selected_count} de {len(tasks)}")
    
    st.markdown("---")
    
    # Group tasks by asset for better UX
    tasks_by_asset = {}
    for task in tasks:
        asset_id = task["asset_id"]
        if asset_id not in tasks_by_asset:
            tasks_by_asset[asset_id] = {
                "filename": task["filename"],
                "mime_type": task["mime_type"],
                "tasks": []
            }
        tasks_by_asset[asset_id]["tasks"].append(task)
    
    # Render each asset's tasks
    for asset_id, asset_data in tasks_by_asset.items():
        mime_icon = "🖼️" if asset_data["mime_type"].startswith("image/") else \
                    "🎵" if asset_data["mime_type"].startswith("audio/") else \
                    "🎬" if asset_data["mime_type"].startswith("video/") else \
                    "📝" if asset_data["mime_type"].startswith("text/") else "📎"
        
        with st.expander(f"{mime_icon} **{asset_data['filename']}** ({len(asset_data['tasks'])} tareas)", expanded=True):
            for task in asset_data["tasks"]:
                _render_single_task_editor(task)
    
    # Build final metadata dict from state
    result_metadata = {}
    for vs_id in st.session_state.selected_tasks_for_dispatch:
        meta = st.session_state.task_metadata_state.get(vs_id, {})
        if meta:  # Only include if there's actual metadata
            result_metadata[vs_id] = meta
    
    return result_metadata


def _render_single_task_editor(task: Dict[str, Any]) -> None:
    """
    Render a single task editor with checkbox and metadata forms.
    
    Args:
        task: Task dict with vector_status_id, vector_type, etc.
    """
    vs_id = task["vector_status_id"]
    vector_type = task["vector_type"]
    is_audio_transcript = vector_type in AUDIO_TRANSCRIPT_TYPES
    
    # Initialize state for this task
    if vs_id not in st.session_state.task_metadata_state:
        st.session_state.task_metadata_state[vs_id] = {}
    
    # Checkbox for selection
    col_check, col_info = st.columns([1, 11])
    
    with col_check:
        is_selected = st.checkbox(
            "",
            value=vs_id in st.session_state.selected_tasks_for_dispatch,
            key=f"select_{vs_id}",
            label_visibility="collapsed"
        )
        
        if is_selected:
            st.session_state.selected_tasks_for_dispatch.add(vs_id)
        else:
            st.session_state.selected_tasks_for_dispatch.discard(vs_id)
    
    with col_info:
        # Task type badge
        type_emoji = "🎵" if "audio" in vector_type else \
                     "🖼️" if "visual" in vector_type else \
                     "📝" if "text" in vector_type else "🔷"
        
        with st.expander(f"{type_emoji} `{vector_type}`", expanded=is_selected):
            st.markdown(f"**ID:** `{vs_id[:8]}...`")
            
            # ==========================================
            # USER CONTEXT (applies to all types)
            # ==========================================
            st.markdown("##### 💬 Contexto del Usuario (Opcional)")
            
            user_context_content = st.text_area(
                "Notas o contexto adicional",
                value=st.session_state.task_metadata_state[vs_id].get("user_context", {}).get("content", ""),
                key=f"user_context_{vs_id}",
                placeholder="Ej: Esta imagen es de mi viaje a París en 2020...",
                height=80
            )
            
            convert_to_memory = st.checkbox(
                "🧠 Convertir a memoria personal",
                value=st.session_state.task_metadata_state[vs_id].get("user_context", {}).get("convert_to_memory", False),
                key=f"convert_memory_{vs_id}",
                help="Si se activa, el contexto se guardará como memoria personal accesible en búsquedas"
            )
            
            # Update state for user_context
            if user_context_content or convert_to_memory:
                st.session_state.task_metadata_state[vs_id]["user_context"] = {
                    "content": user_context_content if user_context_content else None,
                    "convert_to_memory": convert_to_memory
                }
            elif "user_context" in st.session_state.task_metadata_state[vs_id]:
                del st.session_state.task_metadata_state[vs_id]["user_context"]
            
            # ==========================================
            # AUDIO PROCESSING OPTIONS (only for AUDIO_TRANSCRIPT)
            # ==========================================
            if is_audio_transcript:
                st.markdown("---")
                st.markdown("##### 🎵 Opciones de Procesamiento de Audio")
                
                audio_opts = st.session_state.task_metadata_state[vs_id].get("audio_processing_options", {})
                
                col_a, col_b = st.columns(2)
                
                with col_a:
                    is_voice_note = st.checkbox(
                        "🎤 Es nota de voz",
                        value=audio_opts.get("is_voice_note", False),
                        key=f"is_voice_{vs_id}",
                        help="Marcar si es una grabación de voz hablada"
                    )
                
                with col_b:
                    is_song = st.checkbox(
                        "🎶 Es canción",
                        value=audio_opts.get("is_song", False),
                        key=f"is_song_{vs_id}",
                        help="Marcar si el audio contiene música/canción"
                    )
                
                has_provided_lyrics = st.checkbox(
                    "📜 Tengo la letra/transcripción",
                    value=audio_opts.get("has_provided_lyrics", False),
                    key=f"has_lyrics_{vs_id}",
                    help="Si tienes la letra o transcripción del audio, puedes proporcionarla"
                )
                
                provided_lyrics_text = None
                if has_provided_lyrics:
                    provided_lyrics_text = st.text_area(
                        "Letra / Transcripción",
                        value=audio_opts.get("provided_lyrics_text", ""),
                        key=f"lyrics_text_{vs_id}",
                        placeholder="Pega aquí la letra o transcripción del audio...",
                        height=120
                    )
                
                st.markdown("---")
                use_whisper = st.checkbox(
                    "🎙️ Usar Whisper para transcripción automática",
                    value=audio_opts.get("use_whisper", False),
                    key=f"use_whisper_{vs_id}",
                    help="Si se activa, se usará el modelo Whisper para transcribir automáticamente el audio"
                )
                
                # Update state for audio_processing_options
                if is_voice_note or is_song or has_provided_lyrics or use_whisper:
                    st.session_state.task_metadata_state[vs_id]["audio_processing_options"] = {
                        "is_voice_note": is_voice_note,
                        "is_song": is_song,
                        "has_provided_lyrics": has_provided_lyrics,
                        "provided_lyrics_text": provided_lyrics_text if has_provided_lyrics else None,
                        "use_whisper": use_whisper
                    }
                elif "audio_processing_options" in st.session_state.task_metadata_state[vs_id]:
                    del st.session_state.task_metadata_state[vs_id]["audio_processing_options"]


def get_selected_tasks_with_metadata() -> List[Dict[str, Any]]:
    """
    Get the final list of selected tasks with their metadata.
    
    Returns:
        List of dicts with vector_status_id and optional metadata
    """
    init_metadata_state()
    
    result = []
    for vs_id in st.session_state.selected_tasks_for_dispatch:
        task_data = {"vector_status_id": vs_id}
        
        meta = st.session_state.task_metadata_state.get(vs_id, {})
        
        if "user_context" in meta:
            task_data["user_context"] = meta["user_context"]
        
        if "audio_processing_options" in meta:
            task_data["audio_processing_options"] = meta["audio_processing_options"]
        
        result.append(task_data)
    
    return result


def clear_metadata_state():
    """Clear all metadata and selection state after successful dispatch."""
    st.session_state.task_metadata_state = {}
    st.session_state.selected_tasks_for_dispatch = set()
