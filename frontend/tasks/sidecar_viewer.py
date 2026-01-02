"""
Sidecar Metadata Viewer
========================

Component for displaying detailed sidecar JSON metadata in a sidebar.
"""

import streamlit as st
import json
from typing import Dict, Any


def render_privacy_config(privacy_config: Dict[str, Any]):
    """Renderiza la configuración de privacidad."""
    st.markdown("#### 🔐 Privacy Configuration")
    
    level = privacy_config.get("level", "strict_local")
    locked = privacy_config.get("locked", False)
    locked_reason = privacy_config.get("locked_reason")
    
    # Privacy level con icono
    level_icon = "🔒" if level == "strict_local" else "☁️"
    level_text = "Strict Local" if level == "strict_local" else "Public Cloud"
    st.markdown(f"**Level:** {level_icon} {level_text}")
    
    # Lock status
    if locked:
        st.markdown(f"**🔓 Locked:** ✅ Yes")
        if locked_reason:
            st.markdown(f"**Reason:** {locked_reason}")
    else:
        st.markdown(f"**🔓 Locked:** ❌ No")


def render_workflow_state(workflow_state: Dict[str, Any]):
    """Renderiza el estado del workflow."""
    st.markdown("#### ⚙️ Workflow State")
    
    current_status = workflow_state.get("current_status", "unknown")
    steps_completed = workflow_state.get("steps_completed", [])
    last_updated = workflow_state.get("last_updated", "N/A")
    error_log = workflow_state.get("error_log", [])
    
    # Status badge
    status_emoji = {
        "on_hold": "⏸️",
        "pending": "⏳",
        "processing": "⚙️",
        "review_required": "👁️",
        "completed": "✅",
        "failed": "❌",
        "rejected": "🚫"
    }
    emoji = status_emoji.get(current_status, "❓")
    st.markdown(f"**Current Status:** {emoji} `{current_status}`")
    
    # Steps completed
    if steps_completed:
        st.markdown(f"**Steps Completed:** {', '.join([f'`{s}`' for s in steps_completed])}")
    else:
        st.markdown("**Steps Completed:** None")
    
    st.markdown(f"**Last Updated:** {last_updated}")
    
    # Error log
    if error_log:
        st.markdown(f"**⚠️ Errors:** {len(error_log)} error(s) logged")
        with st.expander("View Error Log"):
            st.json(error_log)


def render_data_layers(data_layers: Dict[str, Any]):
    """Renderiza las capas de datos."""
    st.markdown("#### 📊 Data Layers")
    
    raw_ai_drafts = data_layers.get("raw_ai_drafts", {})
    human_curated = data_layers.get("human_curated", {})
    vectors_generated = data_layers.get("vectors_generated", [])
    
    # AI Drafts
    with st.expander("🤖 Raw AI Drafts", expanded=False):
        if raw_ai_drafts:
            st.json(raw_ai_drafts)
        else:
            st.info("No AI drafts available")
    
    # Human Curated
    with st.expander("✍️ Human Curated", expanded=False):
        if human_curated:
            st.json(human_curated)
        else:
            st.info("No human curation yet")
    
    # Vectors Generated
    st.markdown("**Vectors Generated:**")
    if vectors_generated:
        for vector_type in vectors_generated:
            st.markdown(f"  - ✅ `{vector_type}`")
    else:
        st.info("No vectors generated yet")


def render_upload_metadata(sidecar_data: Dict[str, Any]):
    """Renderiza metadata de upload."""
    st.markdown("#### 📤 Upload Metadata")
    
    cols = st.columns(2)
    
    with cols[0]:
        st.markdown(f"**Operation:** `{sidecar_data.get('operation', 'N/A')}`")
        st.markdown(f"**MIME Type:** `{sidecar_data.get('mime_type', 'N/A')}`")
        size_mb = sidecar_data.get('size_bytes', 0) / (1024 * 1024)
        st.markdown(f"**Size:** {size_mb:.2f} MB")
    
    with cols[1]:
        st.markdown(f"**Uploaded:** {sidecar_data.get('upload_timestamp', 'N/A')}")
        st.markdown(f"**Discard Original:** {'✅ Yes' if sidecar_data.get('discard_original') else '❌ No'}")
        st.markdown(f"**Is Merged:** {'✅ Yes' if sidecar_data.get('is_merged') else '❌ No'}")
    
    # User notes
    if sidecar_data.get('user_notes'):
        st.markdown(f"**📝 User Notes:** {sidecar_data['user_notes']}")
    
    # Vector types requested
    vector_types = sidecar_data.get('vector_types', [])
    if vector_types:
        st.markdown(f"**Vector Types Requested:** {', '.join([f'`{vt}`' for vt in vector_types])}")


def render_sidecar_sidebar(sidecar_data: Dict[str, Any], asset_filename: str) -> None:
    """
    Renderiza un sidebar con metadata sidecar formateada.
    
    Args:
        sidecar_data: Dict con estructura de SidecarMetadata
        asset_filename: Nombre del archivo para el título
    """
    st.sidebar.markdown(f"## 📄 {asset_filename}")
    st.sidebar.markdown("---")
    
    # Metadata de upload
    render_upload_metadata(sidecar_data)
    st.sidebar.markdown("---")
    
    # Privacy config
    if "privacy_config" in sidecar_data:
        render_privacy_config(sidecar_data["privacy_config"])
        st.sidebar.markdown("---")
    
    # Workflow state
    if "workflow_state" in sidecar_data:
        render_workflow_state(sidecar_data["workflow_state"])
        st.sidebar.markdown("---")
    
    # Data layers
    if "data_layers" in sidecar_data:
        render_data_layers(sidecar_data["data_layers"])
        st.sidebar.markdown("---")
    
    # Raw JSON viewer
    with st.sidebar.expander("🔍 View Raw JSON", expanded=False):
        st.json(sidecar_data)
    
    # Close button
    if st.sidebar.button("❌ Close Sidebar", use_container_width=True):
        st.session_state.viewing_sidecar = None
        st.rerun()
