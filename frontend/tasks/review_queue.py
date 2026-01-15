"""
Review Queue View
==================

Component for displaying and managing tasks that need review or have failed.
Allows users to view error details and reset tasks back to ON_HOLD for retry.
"""

import streamlit as st
import requests
from typing import List, Dict, Any, Optional


# ==========================================
# CONSTANTS
# ==========================================

STATUS_ICONS = {
    "REVIEW_REQUIRED": "👁️",
    "FAILED": "❌",
}

STATUS_COLORS = {
    "REVIEW_REQUIRED": "🟣",
    "FAILED": "🔴",
}


# ==========================================
# API FUNCTIONS
# ==========================================

def get_review_queue(api_base_url: str) -> Optional[List[Dict[str, Any]]]:
    """Fetch tasks that need review or have failed."""
    try:
        response = requests.get(
            f"{api_base_url}/tasks/review-queue",
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Error fetching review queue: {response.status_code}")
            return None
    except requests.exceptions.ConnectionError:
        st.error("❌ No se pudo conectar al backend.")
        return None
    except Exception as e:
        st.error(f"Error: {e}")
        return None


def reset_tasks_to_hold(api_base_url: str, vector_status_ids: List[str]) -> bool:
    """Reset selected tasks back to ON_HOLD status."""
    try:
        response = requests.post(
            f"{api_base_url}/tasks/reset-to-hold",
            json={"vector_status_ids": vector_status_ids},
            timeout=30
        )
        if response.status_code == 200:
            result = response.json()
            st.success(f"✅ {result.get('tasks_reset', 0)} tarea(s) reseteadas a ON_HOLD")
            return True
        else:
            st.error(f"Error: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        st.error(f"Error resetting tasks: {e}")
        return False


# ==========================================
# MAIN COMPONENT
# ==========================================

def render_review_queue(api_base_url: str = "http://localhost:8000") -> None:
    """
    Render the review queue view showing REVIEW_REQUIRED and FAILED tasks.
    
    Features:
    - View tasks by status (REVIEW_REQUIRED / FAILED)
    - See error messages for failed tasks
    - Reset selected tasks back to ON_HOLD
    - View sidecar data for debugging
    """
    st.subheader("👁️ Cola de Revisión")
    st.markdown("Tareas que requieren revisión humana o que fallaron.")
    
    # Refresh button
    col1, col2 = st.columns([8, 2])
    with col2:
        if st.button("🔄 Refresh", key="refresh_review_queue", use_container_width=True):
            st.rerun()
    
    st.markdown("---")
    
    # Fetch review queue
    with st.spinner("Cargando cola de revisión..."):
        assets = get_review_queue(api_base_url)
    
    if assets is None:
        st.error("❌ No se pudo obtener la cola de revisión.")
        return
    
    if not assets:
        st.info("✨ No hay tareas pendientes de revisión.")
        return
    
    # Count tasks by status
    review_count = 0
    failed_count = 0
    all_tasks = []
    
    for asset in assets:
        for vs in asset.get("vector_statuses", []):
            all_tasks.append({
                "vector_status_id": vs["id"],
                "vector_type": vs["vector_type"],
                "status": vs["status"],
                "error_message": vs.get("error_message"),
                "asset_id": asset["id"],
                "filename": asset["filename"],
                "sidecar_data": asset.get("sidecar_data", {})
            })
            if vs["status"] == "REVIEW_REQUIRED":
                review_count += 1
            elif vs["status"] == "FAILED":
                failed_count += 1
    
    # Summary metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("👁️ Review Required", review_count)
    with col2:
        st.metric("❌ Failed", failed_count)
    with col3:
        st.metric("📊 Total", len(all_tasks))
    
    st.markdown("---")
    
    # Initialize selection state
    if "selected_review_tasks" not in st.session_state:
        st.session_state.selected_review_tasks = set()
    
    # Filter tabs
    tab_all, tab_review, tab_failed = st.tabs(["📊 Todas", "👁️ Review Required", "❌ Fallidas"])
    
    with tab_all:
        _render_task_list(all_tasks, "all")
    
    with tab_review:
        review_tasks = [t for t in all_tasks if t["status"] == "REVIEW_REQUIRED"]
        if review_tasks:
            _render_task_list(review_tasks, "review")
        else:
            st.info("No hay tareas que requieran revisión.")
    
    with tab_failed:
        failed_tasks = [t for t in all_tasks if t["status"] == "FAILED"]
        if failed_tasks:
            _render_task_list(failed_tasks, "failed")
        else:
            st.info("No hay tareas fallidas.")
    
    # Action buttons
    st.markdown("---")
    st.markdown("### 🔧 Acciones")
    
    selected_count = len(st.session_state.selected_review_tasks)
    
    col1, col2, col3 = st.columns([2, 2, 4])
    
    with col1:
        st.markdown(f"**Seleccionadas:** {selected_count}")
    
    with col2:
        if st.button(
            "🔄 Reset a ON_HOLD",
            disabled=selected_count == 0,
            use_container_width=True,
            type="primary"
        ):
            if reset_tasks_to_hold(api_base_url, list(st.session_state.selected_review_tasks)):
                st.session_state.selected_review_tasks = set()
                st.rerun()
    
    with col3:
        if st.button("Seleccionar Todas", key="select_all_review"):
            st.session_state.selected_review_tasks = {t["vector_status_id"] for t in all_tasks}
            st.rerun()


def _render_task_list(tasks: List[Dict], key_prefix: str) -> None:
    """Render a list of tasks with selection and details."""
    
    for i, task in enumerate(tasks):
        vs_id = task["vector_status_id"]
        status = task["status"]
        status_icon = STATUS_ICONS.get(status, "❓")
        
        col_check, col_info = st.columns([1, 11])
        
        with col_check:
            is_selected = st.checkbox(
                "",
                value=vs_id in st.session_state.selected_review_tasks,
                key=f"{key_prefix}_select_{vs_id}",
                label_visibility="collapsed"
            )
            
            if is_selected:
                st.session_state.selected_review_tasks.add(vs_id)
            else:
                st.session_state.selected_review_tasks.discard(vs_id)
        
        with col_info:
            expander_title = f"{status_icon} `{task['vector_type']}` - {task['filename']}"
            
            with st.expander(expander_title, expanded=False):
                st.markdown(f"**Estado:** {status}")
                st.markdown(f"**Archivo:** `{task['filename']}`")
                st.markdown(f"**Vector Type:** `{task['vector_type']}`")
                st.markdown(f"**ID:** `{vs_id[:8]}...`")
                
                # Show error message if present
                if task.get("error_message"):
                    st.markdown("---")
                    st.markdown("**⚠️ Mensaje de Error:**")
                    st.code(task["error_message"], language="text")
                    
                    # Hint for common errors
                    error_lower = task["error_message"].lower()
                    if "connection" in error_lower or "refused" in error_lower:
                        st.info("💡 Error de conexión. Verifica que los servicios estén corriendo.")
                    elif "minio" in error_lower:
                        st.info("💡 Error de MinIO. Verifica el bucket y las credenciales.")
                    elif "timeout" in error_lower:
                        st.info("💡 Timeout. El archivo puede ser demasiado grande o el servidor lento.")
                
                # Show sidecar data for debugging
                sidecar = task.get("sidecar_data", {})
                if sidecar:
                    with st.expander("🔍 Ver Sidecar (Debug)", expanded=False):
                        # Show raw_debug_data if available
                        debug_data = sidecar.get("data_layers", {}).get("raw_debug_data", {})
                        if debug_data:
                            st.json(debug_data)
                        else:
                            st.json(sidecar)


# ==========================================
# TESTING
# ==========================================

if __name__ == "__main__":
    st.set_page_config(page_title="Review Queue Test", layout="wide")
    render_review_queue()
