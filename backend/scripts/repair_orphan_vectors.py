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

def repair_orphan_vectors():
    print("🛠️ Iniciando reparación de vectores huérfanos...")
    client = get_weaviate_client()
    
    with Session(engine) as session:
        siglip_query = select(VectorStatus.asset_id).where(
            VectorStatus.vector_type == VectorType.VISUAL_SIGLIP,
            VectorStatus.status == JobStatus.COMPLETED
        )
        siglip_ids = list(set(session.exec(siglip_query).all()))
        
        repaired_count = 0
        
        for idx in siglip_ids:
            asset = session.get(Asset, idx)
            if not asset:
                continue
                
            has_chunk = session.exec(
                select(VectorStatus).where(
                    VectorStatus.asset_id == idx,
                    VectorStatus.vector_type == VectorType.TEXT_CHUNK
                )
            ).first()
            
            expected_uuid = generate_collection_uuid(asset.file_hash, "TextSpace")
            
            exists = False
            try:
                exists = client.data_object.exists(
                    uuid=expected_uuid,
                    class_name="TextSpace"
                )
            except Exception:
                pass

            if exists:
                if not has_chunk:
                    print(f"✅ Reparando: Creando VectorStatus para {asset.file_hash[:8]}")
                    new_status = VectorStatus(
                        asset_id=idx,
                        vector_type=VectorType.TEXT_CHUNK,
                        status=JobStatus.COMPLETED,
                        weaviate_uuid=expected_uuid
                    )
                    session.add(new_status)
                    repaired_count += 1
                elif has_chunk.status != JobStatus.COMPLETED:
                    print(f"✅ Reparando: Actualizando status a COMPLETED para {asset.file_hash[:8]}")
                    has_chunk.status = JobStatus.COMPLETED
                    has_chunk.weaviate_uuid = expected_uuid
                    session.add(has_chunk)
                    repaired_count += 1
                
        session.commit()
        print(f"\n🎉 Terminó la reparación. {repaired_count} assets arreglados en la DB Postgres.")

if __name__ == "__main__":
    repair_orphan_vectors()
