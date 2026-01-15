"""
Graph Node Generator View
==========================

Component for creating nodes in the knowledge graph from reviewed task data.
Allows users to send data from review queue to graph generation.

PLACEHOLDER - Actual Neo4j integration pending.
"""

import streamlit as st
import requests
from typing import List, Dict, Any, Optional


# ==========================================
# API FUNCTIONS (PLACEHOLDERS)
# ==========================================

def get_node_types(api_base_url: str) -> Optional[List[Dict[str, Any]]]:
    """[PLACEHOLDER] Fetch available node types from backend."""
    try:
        response = requests.get(
            f"{api_base_url}/graph/node-types",
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Error fetching node types: {response.status_code}")
            return None
    except requests.exceptions.ConnectionError:
        st.warning("⚠️ Backend no disponible. Usando datos mock.")
        # Return mock data for development
        return [
            {"id": "person", "name": "Person", "label": "Person", "description": "A person entity", "properties": ["name", "description"]},
            {"id": "place", "name": "Place", "label": "Place", "description": "A location", "properties": ["name", "description"]},
            {"id": "event", "name": "Event", "label": "Event", "description": "An event", "properties": ["name", "description", "date"]},
            {"id": "concept", "name": "Concept", "label": "Concept", "description": "An abstract concept", "properties": ["name", "description"]},
            {"id": "memory", "name": "Memory", "label": "Memory", "description": "A personal memory", "properties": ["content", "summary"]},
        ]
    except Exception as e:
        st.error(f"Error: {e}")
        return None


def get_connection_types(api_base_url: str) -> Optional[List[Dict[str, Any]]]:
    """[PLACEHOLDER] Fetch available connection types from backend."""
    try:
        response = requests.get(
            f"{api_base_url}/graph/connection-types",
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Error fetching connection types: {response.status_code}")
            return None
    except requests.exceptions.ConnectionError:
        st.warning("⚠️ Backend no disponible. Usando datos mock.")
        return [
            {"id": "knows", "name": "KNOWS", "label": "Knows", "description": "Person knows person"},
            {"id": "located_in", "name": "LOCATED_IN", "label": "Located In", "description": "Located in place"},
            {"id": "related_to", "name": "RELATED_TO", "label": "Related To", "description": "General relation"},
            {"id": "mentions", "name": "MENTIONS", "label": "Mentions", "description": "Mentions entity"},
        ]
    except Exception as e:
        st.error(f"Error: {e}")
        return None


def create_node(api_base_url: str, node_type: str, properties: Dict[str, Any], 
                source_asset_id: Optional[str] = None) -> Optional[Dict]:
    """[PLACEHOLDER] Create a node in the graph."""
    try:
        response = requests.post(
            f"{api_base_url}/graph/nodes",
            json={
                "node_type": node_type,
                "properties": properties,
                "source_asset_id": source_asset_id
            },
            timeout=30
        )
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Error creating node: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        st.error(f"Error: {e}")
        return None


def create_connection(api_base_url: str, connection_type: str, 
                      from_node_id: str, to_node_id: str) -> Optional[Dict]:
    """[PLACEHOLDER] Create a connection between nodes."""
    try:
        response = requests.post(
            f"{api_base_url}/graph/connections",
            json={
                "connection_type": connection_type,
                "from_node_id": from_node_id,
                "to_node_id": to_node_id
            },
            timeout=30
        )
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Error creating connection: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"Error: {e}")
        return None


# ==========================================
# SESSION STATE MANAGEMENT
# ==========================================

def init_graph_generator_state():
    """Initialize session state for graph generator."""
    if "graph_pending_data" not in st.session_state:
        st.session_state.graph_pending_data = None
    if "graph_created_nodes" not in st.session_state:
        st.session_state.graph_created_nodes = []


def set_pending_graph_data(data: Dict[str, Any]):
    """Set data to be used for graph generation (called from review queue)."""
    st.session_state.graph_pending_data = data


def clear_pending_graph_data():
    """Clear pending graph data after processing."""
    st.session_state.graph_pending_data = None


def has_pending_graph_data() -> bool:
    """Check if there's pending data for graph generation."""
    return st.session_state.get("graph_pending_data") is not None


# ==========================================
# MAIN COMPONENT
# ==========================================

def render_graph_generator(api_base_url: str = "http://localhost:8000") -> None:
    """
    [PLACEHOLDER] Render the graph node generator view.
    
    This component allows users to:
    1. View pending data from reviewed tasks
    2. Select node type for the data
    3. Map data fields to node properties
    4. Create nodes in the knowledge graph
    5. Create connections between nodes
    """
    init_graph_generator_state()
    
    st.subheader("🔗 Generador de Nodos")
    st.markdown("Crea nodos en el grafo de conocimiento a partir de datos revisados.")
    st.markdown("---")
    
    # Check for pending data
    if has_pending_graph_data():
        st.success("📥 Hay datos pendientes para procesar")
        _render_pending_data_section()
        st.markdown("---")
    else:
        st.info("💡 Selecciona datos desde la **Cola de Revisión** para enviarlos aquí.")
    
    # Load node types and connection types
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📦 Tipos de Nodos Disponibles")
        node_types = get_node_types(api_base_url)
        if node_types:
            for nt in node_types:
                with st.expander(f"🔷 {nt['name']}"):
                    st.markdown(f"**Label:** `{nt['label']}`")
                    st.markdown(f"**Descripción:** {nt['description']}")
                    st.markdown(f"**Propiedades:** {', '.join(nt['properties'])}")
    
    with col2:
        st.markdown("### 🔗 Tipos de Conexiones Disponibles")
        connection_types = get_connection_types(api_base_url)
        if connection_types:
            for ct in connection_types:
                with st.expander(f"↔️ {ct['name']}"):
                    st.markdown(f"**Label:** `{ct['label']}`")
                    st.markdown(f"**Descripción:** {ct['description']}")
    
    st.markdown("---")
    
    # Manual node creation form
    st.markdown("### ✏️ Crear Nodo Manualmente")
    
    if node_types:
        selected_type = st.selectbox(
            "Tipo de Nodo",
            options=[nt["id"] for nt in node_types],
            format_func=lambda x: next((nt["name"] for nt in node_types if nt["id"] == x), x)
        )
        
        # Get properties for selected type
        selected_node = next((nt for nt in node_types if nt["id"] == selected_type), None)
        
        if selected_node:
            st.markdown(f"**Propiedades para {selected_node['name']}:**")
            
            properties = {}
            for prop in selected_node["properties"]:
                if prop in ["content", "description", "summary"]:
                    properties[prop] = st.text_area(
                        prop.capitalize(),
                        key=f"node_prop_{prop}"
                    )
                else:
                    properties[prop] = st.text_input(
                        prop.capitalize(),
                        key=f"node_prop_{prop}"
                    )
            
            if st.button("🚀 Crear Nodo", type="primary"):
                # Filter out empty properties
                filtered_props = {k: v for k, v in properties.items() if v}
                
                if not filtered_props:
                    st.warning("⚠️ Debes llenar al menos una propiedad")
                else:
                    result = create_node(api_base_url, selected_type, filtered_props)
                    if result and result.get("success"):
                        st.success(f"✅ {result.get('message')}")
                        st.session_state.graph_created_nodes.append({
                            "node_id": result.get("neo4j_node_id"),
                            "type": selected_type,
                            "properties": filtered_props
                        })
    
    # Show created nodes
    if st.session_state.graph_created_nodes:
        st.markdown("---")
        st.markdown("### 📋 Nodos Creados en Esta Sesión")
        
        for i, node in enumerate(st.session_state.graph_created_nodes):
            st.markdown(f"**{i+1}.** `{node['type']}` - ID: `{node['node_id']}`")
            st.json(node["properties"])


def _render_pending_data_section():
    """Render section showing pending data from review queue."""
    data = st.session_state.graph_pending_data
    
    st.markdown("### 📥 Datos Pendientes")
    
    with st.expander("Ver datos recibidos", expanded=True):
        st.json(data)
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("✅ Usar estos datos"):
            st.info("🚧 [PLACEHOLDER] Procesamiento de datos pendiente de implementar")
    
    with col2:
        if st.button("❌ Descartar"):
            clear_pending_graph_data()
            st.rerun()


# ==========================================
# HELPER FOR REVIEW QUEUE INTEGRATION
# ==========================================

def send_to_graph_generator(task_data: Dict[str, Any]) -> None:
    """
    Helper function called from review_queue to send data to graph generator.
    
    Args:
        task_data: Dict containing sidecar_data, filename, etc.
    """
    set_pending_graph_data(task_data)
    st.success("📤 Datos enviados al Generador de Nodos. Ve al tab correspondiente.")


# ==========================================
# TESTING
# ==========================================

if __name__ == "__main__":
    st.set_page_config(page_title="Graph Generator Test", layout="wide")
    render_graph_generator()
