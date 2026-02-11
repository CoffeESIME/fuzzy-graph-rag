"""
Graph Node Generator & Inbox Curator View
==========================================

Component for:
1. Reviewing and curating AI-extracted entities (HITL)
2. Approving entities for ingestion into Neo4j knowledge graph
3. Manual node creation and visualization

Integrates with:
- GET  /inbox/pending  -> List pending inbox items
- POST /inbox/{file_hash}/approve -> Approve and ingest
- GET  /inbox/stats -> Statistics
"""

import streamlit as st
import requests
import pandas as pd
import json
from typing import List, Dict, Any, Optional


# ==========================================
# API FUNCTIONS
# ==========================================

def fetch_pending_inbox(api_base_url: str) -> List[Dict[str, Any]]:
    """Fetch all pending inbox items from API."""
    url = f"{api_base_url}/inbox/pending"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        st.error("❌ No se puede conectar al backend. ¿Está corriendo en localhost:8000?")
        with st.expander("🔍 Debug: fetch_pending_inbox"):
            st.code(f"GET {url}", language="text")
        return []
    except requests.exceptions.Timeout:
        st.error("❌ Timeout al conectar con el backend.")
        return []
    except requests.exceptions.HTTPError as e:
        st.error(f"❌ Error al obtener inbox: HTTP {e.response.status_code}")
        with st.expander("🔍 Debug: fetch_pending_inbox"):
            st.code(f"GET {url}\nStatus: {e.response.status_code}\nResponse: {e.response.text}", language="text")
        return []
    except Exception as e:
        st.error(f"❌ Error al obtener datos: {str(e)}")
        return []


def fetch_inbox_stats(api_base_url: str) -> Dict[str, int]:
    """Fetch inbox statistics."""
    try:
        response = requests.get(f"{api_base_url}/inbox/stats", timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception:
        return {"pending": 0, "approved": 0, "rejected": 0, "total": 0}


def approve_inbox_item(api_base_url: str, file_hash: str, entities: Dict, 
                       concepts: List, tags: List) -> Dict[str, Any]:
    """Send approval request to API."""
    url = f"{api_base_url}/inbox/{file_hash}/approve"
    payload = {
        "entities": entities,
        "concepts": concepts,
        "tags": tags
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        return {"success": True, "data": response.json()}
    except requests.exceptions.HTTPError as e:
        error_msg = f"HTTP Error: {e.response.status_code} - {e.response.text}"
        st.error(f"❌ Error al aprobar: HTTP {e.response.status_code}")
        with st.expander("🔍 Debug: approve_inbox_item"):
            st.code(f"POST {url}\nPayload:\n{json.dumps(payload, indent=2, ensure_ascii=False)}\n\nStatus: {e.response.status_code}\nResponse: {e.response.text}", language="text")
        return {"success": False, "error": error_msg}
    except Exception as e:
        st.error(f"❌ Error al aprobar: {str(e)}")
        with st.expander("🔍 Debug: approve_inbox_item"):
            st.code(f"POST {url}\nPayload:\n{json.dumps(payload, indent=2, ensure_ascii=False)}\n\nError: {str(e)}", language="text")
        return {"success": False, "error": str(e)}


def get_node_types(api_base_url: str) -> Optional[List[Dict[str, Any]]]:
    """Fetch available node types from backend."""
    url = f"{api_base_url}/graph/node-types"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json()
        st.warning(f"⚠️ get_node_types: HTTP {response.status_code}")
        with st.expander("🔍 Debug: get_node_types"):
            st.code(f"GET {url}\nStatus: {response.status_code}\nResponse: {response.text}", language="text")
        return None
    except requests.exceptions.ConnectionError:
        # Return mock data for development
        return [
            {"id": "person", "name": "Person", "label": "Person", "description": "A person entity", "properties": ["name", "description"]},
            {"id": "place", "name": "Place", "label": "Place", "description": "A location", "properties": ["name", "description"]},
            {"id": "concept", "name": "Concept", "label": "Concept", "description": "An abstract concept", "properties": ["name", "description"]},
        ]
    except Exception as e:
        st.error(f"❌ Error get_node_types: {str(e)}")
        return None


def get_connection_types(api_base_url: str) -> Optional[List[Dict[str, Any]]]:
    """Fetch available connection types from backend."""
    url = f"{api_base_url}/graph/connection-types"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json()
        st.warning(f"⚠️ get_connection_types: HTTP {response.status_code}")
        with st.expander("🔍 Debug: get_connection_types"):
            st.code(f"GET {url}\nStatus: {response.status_code}\nResponse: {response.text}", language="text")
        return None
    except requests.exceptions.ConnectionError:
        return [
            {"id": "mentions_person", "name": "MENTIONS_PERSON", "label": "Mentions Person", "description": "Asset mentions person"},
            {"id": "mentions_location", "name": "MENTIONS_LOCATION", "label": "Mentions Location", "description": "Asset mentions location"},
            {"id": "evokes_concept", "name": "EVOKES_CONCEPT", "label": "Evokes Concept", "description": "Asset evokes concept"},
        ]
    except Exception as e:
        st.error(f"❌ Error get_connection_types: {str(e)}")
        return None


def create_node(api_base_url: str, node_type: str, properties: Dict[str, Any], 
                source_asset_id: Optional[str] = None) -> Optional[Dict]:
    """Create a node in the graph."""
    url = f"{api_base_url}/graph/nodes"
    payload = {
        "node_type": node_type,
        "properties": properties,
        "source_asset_id": source_asset_id
    }
    try:
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"❌ Error creando nodo: HTTP {response.status_code}")
            with st.expander("🔍 Debug: create_node"):
                st.code(f"POST {url}\nPayload:\n{json.dumps(payload, indent=2, ensure_ascii=False)}\n\nStatus: {response.status_code}\nResponse: {response.text}", language="text")
            return None
    except Exception as e:
        st.error(f"❌ Error creando nodo: {str(e)}")
        with st.expander("🔍 Debug: create_node"):
            st.code(f"POST {url}\nPayload:\n{json.dumps(payload, indent=2, ensure_ascii=False)}\n\nError: {str(e)}", language="text")
        return None


# ==========================================
# DATA TRANSFORMATION HELPERS
# ==========================================

def entities_to_dataframe(entities: List[Dict], entity_type: str) -> pd.DataFrame:
    """Convert entity list to DataFrame for editing."""
    if not entities:
        if entity_type == "persons":
            return pd.DataFrame(columns=["name", "description", "role", "confidence"])
        elif entity_type == "locations":
            return pd.DataFrame(columns=["name", "description", "type", "confidence"])
        elif entity_type == "organizations":
            return pd.DataFrame(columns=["name", "description", "type", "confidence"])
        else:
            return pd.DataFrame(columns=["name", "description", "confidence"])
    
    df = pd.DataFrame(entities)
    
    # Ensure required columns exist
    for col in ["name", "description"]:
        if col not in df.columns:
            df[col] = ""
    if "confidence" not in df.columns:
        df["confidence"] = 1.0
    
    df["confidence"] = pd.to_numeric(df["confidence"], errors="coerce").fillna(1.0)
    
    return df


def concepts_to_dataframe(concepts: List[Dict]) -> pd.DataFrame:
    """Convert concepts list to DataFrame for editing."""
    if not concepts:
        return pd.DataFrame(columns=["name", "definition", "domain", "confidence", "reasoning"])
    
    df = pd.DataFrame(concepts)
    
    for col in ["name", "definition", "domain", "reasoning"]:
        if col not in df.columns:
            df[col] = ""
    if "confidence" not in df.columns:
        df["confidence"] = 1.0
    
    df["confidence"] = pd.to_numeric(df["confidence"], errors="coerce").fillna(1.0)
    
    return df


def dataframe_to_entities(df: pd.DataFrame) -> List[Dict]:
    """Convert edited DataFrame back to entity list."""
    if df is None or df.empty:
        return []
    
    df_clean = df[df["name"].astype(str).str.strip().astype(bool)].copy()
    return df_clean.to_dict(orient="records")


# ==========================================
# SESSION STATE MANAGEMENT
# ==========================================

def init_graph_generator_state():
    """Initialize session state for graph generator."""
    if "graph_pending_data" not in st.session_state:
        st.session_state.graph_pending_data = None
    if "graph_created_nodes" not in st.session_state:
        st.session_state.graph_created_nodes = []
    if "inbox_items" not in st.session_state:
        st.session_state.inbox_items = None


def set_pending_graph_data(data: Dict[str, Any]):
    """Set data to be used for graph generation."""
    st.session_state.graph_pending_data = data


def clear_pending_graph_data():
    """Clear pending graph data after processing."""
    st.session_state.graph_pending_data = None


def has_pending_graph_data() -> bool:
    """Check if there's pending data for graph generation."""
    return st.session_state.get("graph_pending_data") is not None


# ==========================================
# INBOX CURATOR UI COMPONENTS
# ==========================================

def render_inbox_stats(api_base_url: str):
    """Render inbox statistics as metrics."""
    stats = fetch_inbox_stats(api_base_url)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📥 Pendientes", stats.get("pending", 0))
    with col2:
        st.metric("✅ Aprobados", stats.get("approved", 0))
    with col3:
        st.metric("❌ Rechazados", stats.get("rejected", 0))
    with col4:
        st.metric("📊 Total", stats.get("total", 0))


def render_entity_editor(item: Dict, item_key: str):
    """Render the entity/concept editor tabs."""
    entities = item.get("suggested_entities", {})
    concepts = item.get("suggested_concepts", [])
    tags = item.get("tags", [])
    
    tab_persons, tab_locations, tab_orgs, tab_concepts, tab_tags = st.tabs([
        f"👤 Personas ({len(entities.get('persons', []))})",
        f"📍 Lugares ({len(entities.get('locations', []))})",
        f"🏢 Organizaciones ({len(entities.get('organizations', []))})",
        f"💡 Conceptos ({len(concepts)})",
        f"🏷️ Tags ({len(tags)})"
    ])
    
    # PERSONS TAB
    with tab_persons:
        persons_df = entities_to_dataframe(entities.get("persons", []), "persons")
        edited_persons = st.data_editor(
            persons_df,
            key=f"persons_{item_key}",
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "name": st.column_config.TextColumn("Nombre", required=True),
                "description": st.column_config.TextColumn("Descripción"),
                "role": st.column_config.TextColumn("Rol"),
                "confidence": st.column_config.ProgressColumn("Confianza", min_value=0, max_value=1, format="%.2f")
            },
            hide_index=True
        )
        st.session_state[f"edited_persons_{item_key}"] = edited_persons
    
    # LOCATIONS TAB
    with tab_locations:
        locations_df = entities_to_dataframe(entities.get("locations", []), "locations")
        edited_locations = st.data_editor(
            locations_df,
            key=f"locations_{item_key}",
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "name": st.column_config.TextColumn("Nombre", required=True),
                "description": st.column_config.TextColumn("Descripción"),
                "type": st.column_config.SelectboxColumn("Tipo", options=["city", "country", "region", "building", "landmark", "other"], default="other"),
                "confidence": st.column_config.ProgressColumn("Confianza", min_value=0, max_value=1, format="%.2f")
            },
            hide_index=True
        )
        st.session_state[f"edited_locations_{item_key}"] = edited_locations
    
    # ORGANIZATIONS TAB
    with tab_orgs:
        orgs_df = entities_to_dataframe(entities.get("organizations", []), "organizations")
        edited_orgs = st.data_editor(
            orgs_df,
            key=f"orgs_{item_key}",
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "name": st.column_config.TextColumn("Nombre", required=True),
                "description": st.column_config.TextColumn("Descripción"),
                "type": st.column_config.SelectboxColumn("Tipo", options=["company", "government", "ngo", "educational", "media", "other"], default="other"),
                "confidence": st.column_config.ProgressColumn("Confianza", min_value=0, max_value=1, format="%.2f")
            },
            hide_index=True
        )
        st.session_state[f"edited_orgs_{item_key}"] = edited_orgs
    
    # CONCEPTS TAB
    with tab_concepts:
        concepts_df = concepts_to_dataframe(concepts)
        edited_concepts = st.data_editor(
            concepts_df,
            key=f"concepts_{item_key}",
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "name": st.column_config.TextColumn("Nombre", required=True),
                "definition": st.column_config.TextColumn("Definición"),
                "domain": st.column_config.SelectboxColumn("Dominio", options=["general", "technology", "science", "art", "philosophy", "business", "other"], default="general"),
                "reasoning": st.column_config.TextColumn("Razonamiento"),
                "confidence": st.column_config.ProgressColumn("Confianza", min_value=0, max_value=1, format="%.2f")
            },
            hide_index=True
        )
        st.session_state[f"edited_concepts_{item_key}"] = edited_concepts
    
    # TAGS TAB
    with tab_tags:
        st.caption("Tags separados por comas. Los duplicados con nombres de entidades se filtrarán automáticamente.")
        tags_str = ", ".join(tags) if tags else ""
        edited_tags_str = st.text_area(
            "Tags",
            value=tags_str,
            key=f"tags_{item_key}",
            height=80,
            label_visibility="collapsed"
        )
        edited_tags = [t.strip() for t in edited_tags_str.split(",") if t.strip()]
        st.session_state[f"edited_tags_{item_key}"] = edited_tags
        
        if edited_tags:
            st.write("Vista previa:", edited_tags)


def render_inbox_item(api_base_url: str, item: Dict, index: int):
    """Render a single inbox item as an expander."""
    file_hash = item.get("file_hash", "")
    filename = item.get("filename", "Sin nombre")
    status = item.get("processing_status", "UNKNOWN")
    summary = item.get("ai_summary", "")
    
    entities = item.get("suggested_entities", {})
    total_entities = (
        len(entities.get("persons", [])) +
        len(entities.get("locations", [])) +
        len(entities.get("organizations", []))
    )
    total_concepts = len(item.get("suggested_concepts", []))
    
    item_key = file_hash[:8]
    status_emoji = "🔶" if status == "REVIEW_REQUIRED" else "✅" if status == "APPROVED" else "❓"
    
    with st.expander(f"{status_emoji} **{filename}** — {total_entities} entidades, {total_concepts} conceptos", expanded=(index == 0)):
        # Summary
        st.subheader("📝 Resumen AI")
        st.text_area(
            "Resumen",
            value=summary,
            height=80,
            key=f"summary_{item_key}",
            label_visibility="collapsed",
            disabled=True
        )
        
        st.divider()
        
        # Entity editor
        st.subheader("✏️ Editar Entidades y Conceptos")
        render_entity_editor(item, item_key)
        
        st.divider()
        
        # Action buttons
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            if st.button(
                "✅ Aprobar e Ingestar al Grafo",
                key=f"approve_{item_key}",
                type="primary",
                use_container_width=True
            ):
                # Collect edited data
                edited_entities = {
                    "persons": dataframe_to_entities(st.session_state.get(f"edited_persons_{item_key}", pd.DataFrame())),
                    "locations": dataframe_to_entities(st.session_state.get(f"edited_locations_{item_key}", pd.DataFrame())),
                    "organizations": dataframe_to_entities(st.session_state.get(f"edited_orgs_{item_key}", pd.DataFrame()))
                }
                edited_concepts = dataframe_to_entities(st.session_state.get(f"edited_concepts_{item_key}", pd.DataFrame()))
                edited_tags = st.session_state.get(f"edited_tags_{item_key}", [])
                
                with st.spinner("Enviando aprobación..."):
                    result = approve_inbox_item(api_base_url, file_hash, edited_entities, edited_concepts, edited_tags)
                
                if result["success"]:
                    data = result["data"]
                    st.success(f"""
                    ✅ **Aprobado exitosamente!**
                    - Nodos creados: {data.get('nodes_created', 0)}
                    - Relaciones: {data.get('relationships_created', 0)}
                    """)
                    st.session_state.inbox_items = None
                    st.rerun()
                else:
                    st.error(f"❌ Error: {result['error']}")
        
        with col2:
            if st.button("🗑️ Rechazar", key=f"reject_{item_key}", use_container_width=True):
                st.warning("⚠️ Función de rechazo no implementada.")
        
        with col3:
            st.caption(f"`{file_hash[:12]}...`")


def render_inbox_curator(api_base_url: str):
    """Render the inbox curator section."""
    st.subheader("📥 Curaduría de Entidades (Human-in-the-Loop)")
    st.markdown("Revisa y aprueba las entidades extraídas por IA antes de ingestarlas al grafo.")
    
    # Refresh button
    col1, col2 = st.columns([4, 1])
    with col2:
        if st.button("🔄 Refrescar", key="refresh_inbox", use_container_width=True):
            st.session_state.inbox_items = None
            st.rerun()
    
    # Stats
    render_inbox_stats(api_base_url)
    st.divider()
    
    # Fetch items
    if st.session_state.inbox_items is None:
        with st.spinner("Cargando items pendientes..."):
            st.session_state.inbox_items = fetch_pending_inbox(api_base_url)
    
    pending_items = st.session_state.inbox_items
    
    if not pending_items:
        st.markdown("""
        <div style="text-align: center; padding: 2rem; background-color: #f0f2f6; border-radius: 8px;">
            <h3>🎉 ¡Todo al día!</h3>
            <p style="color: #666;">No hay items pendientes de revisión.</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info(f"📥 **{len(pending_items)}** items pendientes de revisión")
        
        for i, item in enumerate(pending_items):
            render_inbox_item(api_base_url, item, i)


# ==========================================
# MANUAL NODE CREATOR
# ==========================================

def render_manual_node_creator(api_base_url: str):
    """Render manual node creation form."""
    st.subheader("✏️ Crear Nodo Manualmente")
    
    node_types = get_node_types(api_base_url)
    
    if node_types:
        selected_type = st.selectbox(
            "Tipo de Nodo",
            options=[nt["id"] for nt in node_types],
            format_func=lambda x: next((nt["name"] for nt in node_types if nt["id"] == x), x)
        )
        
        selected_node = next((nt for nt in node_types if nt["id"] == selected_type), None)
        
        if selected_node:
            st.markdown(f"**Propiedades para {selected_node['name']}:**")
            
            properties = {}
            for prop in selected_node["properties"]:
                if prop in ["content", "description", "summary"]:
                    properties[prop] = st.text_area(prop.capitalize(), key=f"manual_node_{prop}")
                else:
                    properties[prop] = st.text_input(prop.capitalize(), key=f"manual_node_{prop}")
            
            if st.button("🚀 Crear Nodo", type="primary"):
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


def render_schema_viewer(api_base_url: str):
    """Render schema viewer section."""
    st.subheader("📦 Schema del Grafo")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("##### Tipos de Nodos")
        node_types = get_node_types(api_base_url)
        if node_types:
            for nt in node_types:
                with st.expander(f"🔷 {nt['name']}"):
                    st.markdown(f"**Label:** `{nt['label']}`")
                    st.markdown(f"**Descripción:** {nt['description']}")
                    st.markdown(f"**Propiedades:** {', '.join(nt['properties'])}")
    
    with col2:
        st.markdown("##### Tipos de Relaciones")
        connection_types = get_connection_types(api_base_url)
        if connection_types:
            for ct in connection_types:
                with st.expander(f"↔️ {ct['name']}"):
                    st.markdown(f"**Label:** `{ct['label']}`")
                    st.markdown(f"**Descripción:** {ct['description']}")


# ==========================================
# MAIN COMPONENT
# ==========================================

def render_graph_generator(api_base_url: str = "http://localhost:8000") -> None:
    """
    Render the graph generator & curator view.
    
    Includes:
    1. Inbox Curator (HITL) - Review and approve AI-extracted entities
    2. Manual Node Creator - Create nodes manually
    3. Schema Viewer - View available node/relationship types
    """
    init_graph_generator_state()
    
    st.header("🔗 Generador de Nodos & Curador")
    st.markdown("Gestiona la creación de nodos en el grafo de conocimiento.")
    st.markdown("---")
    
    # Subtabs for different functions
    curator_tab, manual_tab, schema_tab = st.tabs([
        "📥 Curaduría HITL",
        "✏️ Crear Manual",
        "📦 Schema"
    ])
    
    with curator_tab:
        render_inbox_curator(api_base_url)
    
    with manual_tab:
        render_manual_node_creator(api_base_url)
        
        # Show created nodes
        if st.session_state.graph_created_nodes:
            st.markdown("---")
            st.markdown("### 📋 Nodos Creados en Esta Sesión")
            for i, node in enumerate(st.session_state.graph_created_nodes):
                st.markdown(f"**{i+1}.** `{node['type']}` - ID: `{node['node_id']}`")
    
    with schema_tab:
        render_schema_viewer(api_base_url)


# ==========================================
# HELPER FOR REVIEW QUEUE INTEGRATION
# ==========================================

def send_to_graph_generator(task_data: Dict[str, Any]) -> None:
    """Helper function called from review_queue to send data to graph generator."""
    set_pending_graph_data(task_data)
    st.success("📤 Datos enviados al Generador de Nodos. Ve al tab correspondiente.")


# ==========================================
# TESTING
# ==========================================

if __name__ == "__main__":
    st.set_page_config(page_title="Graph Generator Test", layout="wide")
    render_graph_generator()
