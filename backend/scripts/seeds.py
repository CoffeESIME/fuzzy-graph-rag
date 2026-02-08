import os
import json
import logging
import sys

# Ensure we can import from the root directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.clients import get_minio_client, get_weaviate_client, get_neo4j_driver
import weaviate.classes.config as wc
from botocore.exceptions import ClientError

# ==========================================
# 1. NEO4J: ONTOLOGÍA FLEXIBLE
# ==========================================
def seed_neo4j():
    print("🧠 [Neo4j] Sembrando Ontología (Versión Flexible)...")
    driver = get_neo4j_driver()

    node_types = [
        # --- NIVEL 1: CORE (ESTRICTO) ---
        # Estos campos SÍ son requeridos porque sin ellos el sistema pierde el archivo
        {
            "id": "digital_asset",
            "name": "Digital Asset",
            "description": "Hub central del archivo.",
            "fields": json.dumps([
                {"fieldName": "file_hash", "required": True, "readonly": True},
                {"fieldName": "file_path", "required": True},
                {"fieldName": "mime_type", "required": True},
                {"fieldName": "original_name", "required": True},
                {"fieldName": "size_bytes", "type": "number"},
                # Opcionales
                {"fieldName": "creation_date", "placeholder": "ISO Date"},
                {"fieldName": "duration_seconds", "type": "number"}, 
                {"fieldName": "resolution"}
            ])
        },
        
        # --- NIVEL 2: INBOX (FLEXIBLE) ---
        {
            "id": "inbox_item",
            "name": "Inbox Item",
            "fields": json.dumps([
                {"fieldName": "processing_status", "required": True}, # pending/done
                {"fieldName": "ai_summary", "widget": "textarea"},
                {"fieldName": "suggested_entities", "widget": "json_editor"},
                {"fieldName": "suggested_concepts", "widget": "json_editor"},
                {"fieldName": "suggested_metadata", "widget": "json_editor"},
                {"fieldName": "user_curation_notes", "widget": "textarea"}
            ])
        },

        # --- NIVEL 3: SATÉLITES (GRANULARIDAD) ---
        # Nota: Quitamos 'required' de los textos para evitar fallos en contenido vacío
        
        {
            "id": "text_chunk", "name": "Fragmento Texto",
            "fields": json.dumps([
                {"fieldName": "text_preview", "widget": "textarea"}, 
                {"fieldName": "page_number", "type": "number"},
                {"fieldName": "weaviate_id", "readonly": True} 
            ])
        },
        {
            "id": "visual_frame", "name": "Frame Visual",
            "fields": json.dumps([
                {"fieldName": "timestamp", "type": "number", "required": True}, # 0.0 para imágenes fijas
                {"fieldName": "weaviate_id", "readonly": True},
                {"fieldName": "description_ai", "widget": "textarea"}, # Opcional (puede fallar el VLM)
                {"fieldName": "ocr_text", "widget": "textarea"}       # Opcional (puede no tener texto)
            ])
        },
        {
            "id": "audio_chunk", "name": "Fragmento Audio",
            "fields": json.dumps([
                {"fieldName": "start_time", "type": "number", "required": True},
                {"fieldName": "end_time", "type": "number", "required": True},
                {"fieldName": "transcript_segment", "widget": "textarea"}, # Opcional (Música instrumental)
                {"fieldName": "emotion_detected"}, # Opcional
                {"fieldName": "weaviate_id", "readonly": True}
            ])
        },
        {
            "id": "user_memory", "name": "Contexto Usuario",
            "fields": json.dumps([
                {"fieldName": "text", "widget": "textarea", "required": True}, # Aquí sí, una memoria vacía no sirve
                {"fieldName": "sentiment", "type": "number"},
                {"fieldName": "weaviate_id", "readonly": True}
            ])
        },

        # --- NIVEL 4: ENTIDADES (CONOCIMIENTO) ---
        
        {
            "id": "person", "name": "Persona",
            "fields": json.dumps([
                {"fieldName": "name", "required": True}, # El nombre es el ID semántico
                {"fieldName": "roles"},
                {"fieldName": "bio", "widget": "textarea"},
                {"fieldName": "birthdate"},
                {"fieldName": "deathdate"}
            ])
        },
        {
            "id": "location", "name": "Ubicación",
            "fields": json.dumps([
                {"fieldName": "name", "required": True},
                {"fieldName": "type"},
                {"fieldName": "coords"},
                {"fieldName": "iso_code"}
            ])
        },
        {
            "id": "organization", "name": "Organización",
            "fields": json.dumps([
                {"fieldName": "name", "required": True},
                {"fieldName": "industry"},
                {"fieldName": "website"}
            ])
        },
        {
            "id": "event", "name": "Evento",
            "fields": json.dumps([
                {"fieldName": "name", "required": True},
                {"fieldName": "date"},
                {"fieldName": "type"}
            ])
        },
        {
            "id": "project", "name": "Proyecto / Obra",
            "fields": json.dumps([
                {"fieldName": "title", "required": True},
                {"fieldName": "type"},
                {"fieldName": "year", "type": "number"}
            ])
        },
        {
            "id": "concept", "name": "Concepto",
            "fields": json.dumps([
                {"fieldName": "name", "required": True},
                {"fieldName": "type"},
                {"fieldName": "definition", "widget": "textarea"},
                {"fieldName": "domain"}
            ])
        },
        {
            "id": "quote", "name": "Cita",
            "fields": json.dumps([
                {"fieldName": "text", "required": True, "widget": "textarea"},
                {"fieldName": "form"},
                {"fieldName": "author_ref_name"},
                {"fieldName": "context"},
                {"fieldName": "sentiment_score", "type": "number"}
            ])
        },
        {
            "id": "post", "name": "Post Social",
            "fields": json.dumps([
                {"fieldName": "platform"},
                {"fieldName": "url", "required": True},
                {"fieldName": "metrics_json", "widget": "json_editor"},
                {"fieldName": "content_snapshot", "widget": "textarea"}
            ])
        },
        {
            "id": "tag", "name": "Etiqueta",
            "fields": json.dumps([{"fieldName": "name", "required": True}])
        }
    ]

    # Constraints (Integridad de Datos)
    constraints = [
        "CREATE CONSTRAINT asset_hash_unique IF NOT EXISTS FOR (n:DigitalAsset) REQUIRE n.file_hash IS UNIQUE",
        "CREATE CONSTRAINT location_name_unique IF NOT EXISTS FOR (n:Location) REQUIRE n.name IS UNIQUE",
        "CREATE CONSTRAINT tag_name_unique IF NOT EXISTS FOR (n:Tag) REQUIRE n.name IS UNIQUE",
        "CREATE CONSTRAINT concept_name_unique IF NOT EXISTS FOR (n:Concept) REQUIRE n.name IS UNIQUE",
        "CREATE CONSTRAINT chunk_uuid_unique IF NOT EXISTS FOR (n:TextChunk) REQUIRE n.weaviate_id IS UNIQUE",
    ]

    with driver.session() as session:
        for q in constraints:
            try:
                session.run(q)
            except Exception:
                pass # Ignorar si ya existen
        
        for node in node_types:
            session.run("""
            MERGE (nt:NodeType {id: $id})
            SET nt.name = $name, nt.fields = $fields, nt.description = $description
            """, id=node["id"], name=node["name"], fields=node["fields"], description=node.get("description", ""))
    
    # We do not close the driver here because it's a shared instance
    print("   ✅ Neo4j: Ontología lista.")

# ==========================================
# 2. WEAVIATE: CONSISTENCIA DE NOMBRES
# ==========================================
def seed_weaviate():
    print("🧩 [Weaviate] Configurando Schemas Ricos (Hybrid Search Ready)...")
    client = get_weaviate_client()
    
    # Propiedades base para trazabilidad
    common_props = [
        wc.Property(name="neo4j_hash", data_type=wc.DataType.TEXT), # ID Universal
        wc.Property(name="inbox_id", data_type=wc.DataType.TEXT),   # ID de Proceso
        wc.Property(name="tags", data_type=wc.DataType.TEXT_ARRAY)  # Tags para todos
    ]

    # =========================================================
    # 1. TEXT SPACE (Documentos)
    # =========================================================
    if not client.collections.exists("TextSpace"):
        client.collections.create(
            name="TextSpace",
            properties=common_props + [
                wc.Property(name="content", data_type=wc.DataType.TEXT), # Texto Crudo
                wc.Property(name="ai_summary", data_type=wc.DataType.TEXT),
                wc.Property(name="document_type", data_type=wc.DataType.TEXT), # Filter: 'article', 'note'
                wc.Property(name="rhetorical_tone", data_type=wc.DataType.TEXT), # Filter: 'sarcastic'
            ],
            vector_config=[wc.Configure.Vectors.self_provided(name="default")]
        )

    # =========================================================
    # 2. VISUAL SPACE (Imágenes/Memes)
    # =========================================================
    if not client.collections.exists("VisualSpace"):
        client.collections.create(
            name="VisualSpace",
            properties=common_props + [
                # Contenido Textual derivado
                wc.Property(name="description_ai", data_type=wc.DataType.TEXT), # Summary
                wc.Property(name="ocr_text", data_type=wc.DataType.TEXT),       # Searchable Text inside image
                
                # Metadatos Visuales (Filtros)
                wc.Property(name="image_type", data_type=wc.DataType.TEXT),    # Filter: 'meme', 'photo'
                wc.Property(name="art_style", data_type=wc.DataType.TEXT),     # Filter: 'pixel_art', 'noir'
                wc.Property(name="visual_mood", data_type=wc.DataType.TEXT),   # Filter: 'gloomy', 'vibrant'
                wc.Property(name="dominant_colors", data_type=wc.DataType.TEXT_ARRAY) # Filter: ['#000', '#F00']
            ],
            vector_config=[
                wc.Configure.Vectors.self_provided(name="visual"),   # SigLIP
                wc.Configure.Vectors.self_provided(name="semantic")  # BGE-M3 (Super String)
            ]
        )

    # =========================================================
    # 3. AUDIO SPACE (Música/Voz)
    # =========================================================
    if not client.collections.exists("AudioSpace"):
        client.collections.create(
            name="AudioSpace",
            properties=common_props + [
                # Contenido Textual derivado
                wc.Property(name="transcript", data_type=wc.DataType.TEXT),     # Whisper output
                wc.Property(name="lyrics_summary", data_type=wc.DataType.TEXT), # Topic analysis
                
                # Metadatos Sonoros (Filtros)
                wc.Property(name="audio_type", data_type=wc.DataType.TEXT),     # Filter: 'song', 'speech'
                wc.Property(name="genre", data_type=wc.DataType.TEXT),          # Filter: 'jazz', 'rock'
                wc.Property(name="emotion", data_type=wc.DataType.TEXT),        # Filter: 'sad', 'energetic'
                wc.Property(name="instruments", data_type=wc.DataType.TEXT_ARRAY), # Filter: ['guitar', 'piano']
                wc.Property(name="tempo", data_type=wc.DataType.TEXT)           # Filter: 'fast', '120bpm'
            ],
            vector_config=[
                wc.Configure.Vectors.self_provided(name="audio_clap"),         # CLAP
                wc.Configure.Vectors.self_provided(name="transcript_semantic") # BGE-M3 (Super String)
            ]
        )

    # =========================================================
    # 4. MEMORY SPACE (Contexto de Usuario)
    # =========================================================
    if not client.collections.exists("MemorySpace"):
        client.collections.create(
            name="MemorySpace",
            properties=common_props + [
                wc.Property(name="text", data_type=wc.DataType.TEXT),           # Enriched Narrative
                
                # Metadatos Emocionales/Relacionales (Filtros)
                wc.Property(name="sentiment", data_type=wc.DataType.TEXT),      # Filter: 'nostalgic'
                wc.Property(name="emotional_intensity", data_type=wc.DataType.NUMBER), # Filter: > 0.8
                wc.Property(name="connection_type", data_type=wc.DataType.TEXT),# Filter: 'soundtrack_of'
                
                # Referencias para Merge futuro
                wc.Property(name="related_file_uuids", data_type=wc.DataType.TEXT_ARRAY) 
            ],
            vector_config=[wc.Configure.Vectors.self_provided(name="default")]
        )
    
    print("   ✅ Weaviate: Colecciones enriquecidas listas.")

# ==========================================
# 3. MINIO: ESTRUCTURA MAESTRA
# ==========================================
def seed_minio():
    print(f"🌊 [MinIO] Configurando estructura...")
    # get_minio_client ensures bucket exists
    s3 = get_minio_client()
    
    folders = [
        "raw/videos/", "raw/images/", "raw/documents/", "raw/audio/", 
        "master_records/texts/", "master_records/sidecars/",
        "processed/frames/", "processed/audio/", "processed/text_chunks/", "processed/temp/"
    ]
    
    bucket_name = "rag-dataset"
    for f in folders:
        try:
            s3.put_object(Bucket=bucket_name, Key=f)
        except Exception:
            pass
    print("   ✅ MinIO: Estructura lista.")

def cleanup():
    """Explicitly close shared connections to avoid ResourceWarnings"""
    print("\n🧹 Cleaning up connections...")
    try:
        get_weaviate_client().close()
        print("   ✅ Weaviate client closed.")
    except Exception as e:
        print(f"   ⚠️ Error closing Weaviate client: {e}")
        
    try:
        get_neo4j_driver().close()
        print("   ✅ Neo4j driver closed.")
    except Exception as e:
        print(f"   ⚠️ Error closing Neo4j driver: {e}")

if __name__ == "__main__":
    try:
        seed_minio()
        seed_neo4j()
        seed_weaviate()
        print("\n🚀 SEED COMPLETADO: Infraestructura validada y flexible.")
    finally:
        cleanup()