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
        "CREATE CONSTRAINT person_name_unique IF NOT EXISTS FOR (n:Person) REQUIRE n.name IS UNIQUE",
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
    print("🧩 [Weaviate] Configurando Schemas...")
    client = get_weaviate_client()
    # No need to explictly connect() as the v4 client returned by our factory is ready to use
    
    common_props = [
        wc.Property(name="neo4j_hash", data_type=wc.DataType.TEXT),
        wc.Property(name="inbox_id", data_type=wc.DataType.TEXT),
    ]

    # TextSpace
    if not client.collections.exists("TextSpace"):
        client.collections.create(
            name="TextSpace",
            vector_config=wc.Configure.Vectorizer.none(),
            properties=common_props + [wc.Property(name="content", data_type=wc.DataType.TEXT)]
        )

    # VisualSpace (Corrección: description -> description_ai)
    if not client.collections.exists("VisualSpace"):
        client.collections.create(
            name="VisualSpace",
            vector_config=wc.Configure.Vectorizer.none(),
            properties=common_props + [wc.Property(name="description_ai", data_type=wc.DataType.TEXT)]
        )

    # AudioSpace (Corrección: Agregamos emotion si queremos buscar por emoción)
    if not client.collections.exists("AudioSpace"):
        client.collections.create(
            name="AudioSpace",
            vector_config=wc.Configure.Vectorizer.none(),
            properties=common_props + [
                wc.Property(name="transcript", data_type=wc.DataType.TEXT),
                wc.Property(name="emotion", data_type=wc.DataType.TEXT)
            ]
        )

    # MemorySpace
    if not client.collections.exists("MemorySpace"):
        client.collections.create(
            name="MemorySpace",
            vector_config=wc.Configure.Vectorizer.none(),
            properties=common_props + [wc.Property(name="text", data_type=wc.DataType.TEXT)]
        )
    
    print("   ✅ Weaviate: Colecciones listas.")
    # Do not close shared client here as it might be used elsewhere, 
    # but since this is a script, we will close it in main.

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