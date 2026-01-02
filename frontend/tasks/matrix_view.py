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
    "on_hold": "⏸️",
    "pending": "⏳",
    "processing": "⚙️",
    "review_required": "👁️",
    "completed": "✅",
    "failed": "❌",
    "rejected": "🚫"
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


def render_dispatch_button(assets: List[Dict[str, Any]]) -> None:
    """
    Renderiza el botón para despachar jobs pendientes.
    
    Args:
        assets: Lista de assets con vector_statuses
    """
    st.markdown("---")
    st.markdown("### 🚀 Dispatch Jobs")
    
    # Contar tareas ON_HOLD
    on_hold_count = 0
    on_hold_ids = []
    
    for asset in assets:
        for vs in asset.get("vector_statuses", []):
            if vs["status"] == "on_hold":
                on_hold_count += 1
                on_hold_ids.append(vs["id"])
    
    if on_hold_count == 0:
        st.info("✨ No hay tareas en estado ON_HOLD.")
        return
    
    st.markdown(f"**Tareas en ON_HOLD:** {on_hold_count}")
    
    cols = st.columns([2, 1])
    
    with cols[0]:
        dispatch_all = st.checkbox(
            "Dispatch all ON_HOLD tasks",
            value=False,
            help="Send all ON_HOLD vector statuses to processing queue"
        )
    
    with cols[1]:
        if st.button(
            f"▶️ Dispatch {on_hold_count if dispatch_all else 'Selected'}", 
            type="primary",
            use_container_width=True,
            disabled=not dispatch_all  # Por ahora solo soporta "all"
        ):
            with st.spinner(f"Dispatching {on_hold_count} task(s)..."):
                # TODO: Implementar llamada al backend /tasks/dispatch
                # For now, simulate success
                st.success(f"✅ {on_hold_count} task(s) dispatched successfully!")
                st.info("🔄 Refresh to see updated statuses.")


# ==========================================
# TESTING
# ==========================================

if __name__ == "__main__":
    # This would be run as a Streamlit app for testing
    st.set_page_config(page_title="Task Matrix Test", layout="wide")
    
    from mock_data import generate_mock_assets
    
    st.title("Task Matrix Test")
    
    # Generate mock data
    if 'mock_assets' not in st.session_state:
        st.session_state.mock_assets = generate_mock_assets(5)
    
    # Render matrix
    render_task_matrix(st.session_state.mock_assets)
    render_dispatch_button(st.session_state.mock_assets)
