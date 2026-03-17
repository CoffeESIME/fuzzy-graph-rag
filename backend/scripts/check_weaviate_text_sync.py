import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import select
from app.models.vector_status import VectorStatus
from app.models.asset import Asset
from app.models.enums import VectorType, JobStatus
from shared.database import get_session
from shared.clients import get_weaviate_client

def check_text_sync():
    session = next(get_session())
    weaviate_client = get_weaviate_client()
    
    # 1. Check SQL
    print("--- SQL VectorStatus (TEXT_CHUNK para Archivos de Texto) ---")
    
    # NUEVO: Filtrar también por el tipo de Asset para excluir imágenes (OCR), audio, etc.
    completed_texts = session.exec(
        select(VectorStatus, Asset).join(Asset)
        .where(
            VectorStatus.vector_type == VectorType.TEXT_CHUNK,
            VectorStatus.status == JobStatus.COMPLETED,
            Asset.mime_type.startswith('text/')  # Este es el filtro correcto en SQLModel
        )
    ).all()
    
    print(f"Total TEXT_CHUNK (solo textos) completados en SQL: {len(completed_texts)}")
    
    uuids_in_sql = []
    vs_map = {}
    for vs, asset in completed_texts:
        if vs.weaviate_uuid:
            uuids_in_sql.append((vs.weaviate_uuid, asset.filename, vs.id))
            vs_map[vs.id] = vs
            
    print(f"Total UUIDs almacenados en SQL: {len(uuids_in_sql)}")
    
    # 2. Check Weaviate
    print("\n--- Weaviate TextSpace ---")
    if not weaviate_client.is_ready():
            print("ERROR: Weaviate no es alcanzable. Asegúrate de que el contenedor esté corriendo (docker compose up -d weaviate).")
            return
            
    try:
        collection = weaviate_client.collections.get("TextSpace")
        found_count = 0
        missing_count = 0
        missing_vs_ids = []
        
        for uuid, filename, vs_id in uuids_in_sql:
            exists = collection.data.exists(uuid)
            if exists:
                found_count += 1
            else:
                missing_count += 1
                missing_vs_ids.append(vs_id)
                print(f"✗ MISSING IN WEAVIATE: {filename} (UUID: {uuid}, ID: {vs_id})")
                
        print(f"\nResumen:")
        print(f"✓ Encontrados en Weaviate (TextSpace): {found_count}")
        print(f"✗ Faltantes en Weaviate (TextSpace): {missing_count}")
        
        if missing_count > 0:
            print("\n=============================================")
            print("🚨 ACCIONES para los documentos de texto faltantes:")
            print("1. [PENDING] Enviar a PENDING para re-procesar inmediatamente.")
            print("2. [ON_HOLD] Enviar a ON_HOLD para pausar e inspeccionar luego.")
            print("3. [SALIR] No hacer nada y salir de este asistente.")
            print("=============================================")
            
            choice = input("\nElige una acción (1/2/3): ").strip()
            
            if choice in ['1', '2']:
                new_status = JobStatus.PENDING if choice == '1' else JobStatus.ON_HOLD
                print(f"\nActualizando {missing_count} registros al estado {new_status}...\n")
                
                for vs_id in missing_vs_ids:
                    vs = vs_map[vs_id]
                    vs.status = new_status
                    vs.error_message = "Reset manual por script (Missing in Weaviate TextSpace sync check)"
                    session.add(vs)
                
                session.commit()
                print(f"✅ ¡Listos! Se modificó la base de datos SQL correctamente.")
                if new_status == JobStatus.PENDING:
                    print(f"Los workers de Celery deberían interceptarlos dentro de unos instantes y reprocesar la cola.")
            else:
                print("\n🚫 Saliendo sin modificar nada en la base de datos.")
        else:
            print("\n✅ Todos los documentos de texto puros están sincronizados en TextSpace. ¡Nada por hacer aquí!")
                
    except Exception as e:
        print(f"Error querying Weaviate: {e}")

if __name__ == "__main__":
    try:
        check_text_sync()
    except KeyboardInterrupt:
        print("\nSaliendo por comando del teclado...")
        sys.exit(0)
