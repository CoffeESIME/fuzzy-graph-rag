import os
import sys

# Ensure backend root is in PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import select, Session
from sqlalchemy import create_engine
import weaviate
from config.settings import get_settings
from app.models.vector_status import VectorStatus
from app.models.asset import Asset
from app.models.enums import VectorType, JobStatus
from worker.utils import generate_collection_uuid
from shared.clients import get_weaviate_client

settings = get_settings()
engine = create_engine(settings.DATABASE_URL)

def check_orphan_vectors():
    print("🔍 Iniciando diagnóstico de vectores huérfanos...")
    client = get_weaviate_client()
    
    with Session(engine) as session:
        # 1. Obtener todos los Assets que son imágenes (o al menos tienen VISUAL_SIGLIP exitoso)
        siglip_query = select(VectorStatus.asset_id).where(
            VectorStatus.vector_type == VectorType.VISUAL_SIGLIP,
            VectorStatus.status == JobStatus.COMPLETED
        )
        siglip_ids = list(set(session.exec(siglip_query).all()))
        print(f"📸 Encontrados {len(siglip_ids)} assets con vector visual completado.")
        
        orphans_found = 0
        missing_everywhere = 0
        
        for idx in siglip_ids:
            # Traer el asset para tener el hash
            asset = session.get(Asset, idx)
            if not asset:
                continue
                
            # Verificar si existe el VectorStatus de TEXT_CHUNK
            has_chunk = session.exec(
                select(VectorStatus).where(
                    VectorStatus.asset_id == idx,
                    VectorStatus.vector_type == VectorType.TEXT_CHUNK,
                    VectorStatus.status == JobStatus.COMPLETED
                )
            ).first()
            
            if has_chunk:
                # Todo está bien, DB dice que el vector de texto existe
                continue
                
            # Si NO existe en DB, revisamos Weaviate
            # En esta app, los UUIDs en Weaviate son determinísticos: uuid(file_hash, collection_name)
            # Y la colección para textos es "TextSpace"
            expected_uuid = generate_collection_uuid(asset.file_hash, "TextSpace")
            
            try:
                # Buscar directamente el UUID en Weaviate iterando o buscando por ID
                # Usamos GET /objects/{id} de Weaviate para checkear si existe
                exists_in_weaviate = client.data_object.exists(
                    uuid=expected_uuid,
                    class_name="TextSpace"
                )
            except Exception as e:
                # Fallback genérico por si falla el chequeo de clase
                exists_in_weaviate = False
                print(f"⚠️ Error verificando UUID en Weaviate: {e}")

            if exists_in_weaviate:
                orphans_found += 1
                print(f"🚨 HUÉRFANO DETECTADO: El asset {idx} (Hash {asset.file_hash[:8]}) tiene vector de texto en Weaviate, pero su base de datos Postgres NO LO SABE.")
            else:
                missing_everywhere += 1
                print(f"❌ AUSENTE TOTALMENTe: El asset {idx} (Hash {asset.file_hash[:8]}) no tiene vector de texto ni en DB ni en Weaviate.")
                
        print("\n" + "="*50)
        print("📊 RESUMEN:")
        print(f"Total de imágenes sin status de text_chunk en DB: {orphans_found + missing_everywhere}")
        print(f"✅ Vectores huérfanos (Aparecen en Weaviate pero no en DB): {orphans_found}")
        print(f"❌ Archivos genuinamente sin vector de texto: {missing_everywhere}")
        print("="*50)

if __name__ == "__main__":
    check_orphan_vectors()
