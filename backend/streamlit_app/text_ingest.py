"""
GraphRAG Text Ingest - Streamlit Frontend
==========================================
Simple interface to ingest raw text into the GraphRAG system.
"""

import streamlit as st
import requests
from datetime import datetime

# ==========================================
# CONFIGURATION
# ==========================================
API_BASE_URL = "http://localhost:8000"

# Vector type options
VECTOR_TYPE_OPTIONS = {
    "text_chunk": "📝 Fragmento de Texto - Búsqueda semántica",
    "user_memory": "🧠 Memoria de Usuario - Notas personales"
}

# Privacy level options
PRIVACY_OPTIONS = {
    "strict_local": "🔒 Local Estricto - Solo procesamiento local (Ollama)",
    "public_cloud": "☁️ Nube Pública - Permite APIs externas (Gemini)"
}


# ==========================================
# PAGE CONFIG
# ==========================================
st.set_page_config(
    page_title="GraphRAG - Ingesta de Texto",
    page_icon="📝",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .stTextArea textarea {
        font-family: 'SF Mono', 'Monaco', 'Inconsolata', monospace;
        font-size: 14px;
    }
    .success-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        margin: 1rem 0;
    }
    .info-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #e7f3ff;
        border: 1px solid #b6d4fe;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)


# ==========================================
# HEADER
# ==========================================
st.title("📝 Ingesta de Texto")
st.markdown("""
Ingresa texto directamente al sistema GraphRAG. El texto se guardará en MinIO,
se creará un sidecar con metadatos, y las tareas de vectorización quedarán en **ON_HOLD**.
""")

st.divider()


# ==========================================
# MAIN FORM
# ==========================================
col1, col2 = st.columns([2, 1])

with col1:
    # Title input
    title = st.text_input(
        "📌 Título (opcional)",
        placeholder="Ej: Notas de la reunión, Ideas del proyecto...",
        help="Se usará para generar el nombre del archivo"
    )
    
    # Main text area
    content = st.text_area(
        "📄 Contenido del texto",
        height=300,
        placeholder="Escribe o pega aquí el texto que deseas guardar y analizar...",
        help="El texto se guardará en master_records/texts/"
    )
    
    # User notes
    user_notes = st.text_area(
        "💬 Notas adicionales (opcional)",
        height=100,
        placeholder="Contexto adicional, recordatorios, por qué es importante...",
        help="Estas notas se guardarán en el sidecar para referencia futura"
    )

with col2:
    st.markdown("### ⚙️ Configuración")
    
    # Vector types selection
    st.markdown("**Tipos de vectorización:**")
    selected_vectors = []
    for key, label in VECTOR_TYPE_OPTIONS.items():
        if st.checkbox(label, value=(key == "text_chunk"), key=f"vec_{key}"):
            selected_vectors.append(key)
    
    st.markdown("---")
    
    # Privacy level
    st.markdown("**Nivel de privacidad:**")
    privacy_level = st.radio(
        "Selecciona el nivel",
        options=list(PRIVACY_OPTIONS.keys()),
        format_func=lambda x: PRIVACY_OPTIONS[x],
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    
    # Character count
    if content:
        char_count = len(content)
        word_count = len(content.split())
        st.metric("Caracteres", f"{char_count:,}")
        st.metric("Palabras", f"{word_count:,}")


# ==========================================
# SUBMIT BUTTON
# ==========================================
st.divider()

col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])

with col_btn1:
    submit = st.button(
        "🚀 Guardar Texto",
        type="primary",
        use_container_width=True,
        disabled=not content or not selected_vectors
    )

with col_btn2:
    if st.button("🗑️ Limpiar", use_container_width=True):
        st.rerun()


# ==========================================
# PROCESS SUBMISSION
# ==========================================
if submit and content and selected_vectors:
    with st.spinner("Guardando texto en el sistema..."):
        try:
            # Prepare request
            payload = {
                "content": content,
                "vector_types": selected_vectors,
                "privacy_level": privacy_level
            }
            
            if title:
                payload["title"] = title
            if user_notes:
                payload["user_notes"] = user_notes
            
            # Send request
            response = requests.post(
                f"{API_BASE_URL}/ingest/text",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                
                st.success("✅ Texto guardado exitosamente!")
                
                # Show details
                st.markdown("### 📋 Detalles del Asset Creado")
                
                asset = result["asset"]
                col_a, col_b = st.columns(2)
                
                with col_a:
                    st.markdown(f"**ID:** `{asset['id']}`")
                    st.markdown(f"**Archivo:** `{asset['filename']}`")
                    st.markdown(f"**Ruta MinIO:** `{asset['minio_path']}`")
                
                with col_b:
                    st.markdown(f"**Sidecar:** `{asset['sidecar_path']}`")
                    st.markdown(f"**Tareas creadas:** {asset['vector_tasks_created']}")
                    st.markdown(f"**Estado:** 🟡 ON_HOLD")
                
                st.info("""
                💡 **Siguiente paso:** Las tareas de vectorización están en ON_HOLD. 
                Ve al panel de control de tareas para iniciar el procesamiento.
                """)
                
            else:
                error_detail = response.json().get("detail", response.text)
                st.error(f"❌ Error del servidor: {error_detail}")
                
        except requests.exceptions.ConnectionError:
            st.error("❌ No se puede conectar al servidor. ¿Está corriendo el backend en localhost:8000?")
        except requests.exceptions.Timeout:
            st.error("❌ Timeout - El servidor tardó demasiado en responder")
        except Exception as e:
            st.error(f"❌ Error inesperado: {str(e)}")


# ==========================================
# SIDEBAR INFO
# ==========================================
with st.sidebar:
    st.markdown("## 📚 Ayuda")
    
    st.markdown("""
    ### ¿Qué hace esta página?
    
    1. **Guarda** tu texto en MinIO (`master_records/texts/`)
    2. **Crea** un sidecar JSON con metadatos
    3. **Registra** el asset en PostgreSQL
    4. **Genera** tareas de vectorización en estado ON_HOLD
    
    ### Tipos de vectorización
    
    - **Fragmento de Texto**: Divide el texto en chunks para búsqueda semántica
    - **Memoria de Usuario**: Para notas personales y contexto
    - **Resumen**: Genera un resumen del contenido
    
    ### Niveles de privacidad
    
    - **Local Estricto**: Solo usa modelos locales (Ollama)
    - **Nube Pública**: Puede usar APIs externas (Gemini, OpenAI)
    """)
    
    st.divider()
    
    # API Status
    st.markdown("### 🔌 Estado del API")
    try:
        health = requests.get(f"{API_BASE_URL}/ingest/health", timeout=2)
        if health.status_code == 200:
            st.success("✅ Backend conectado")
        else:
            st.warning("⚠️ Backend responde con errores")
    except:
        st.error("❌ Backend no disponible")
