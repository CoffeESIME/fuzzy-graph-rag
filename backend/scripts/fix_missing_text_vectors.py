import os
import sys

# Ensure backend root is in PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import select, Session
from config.settings import get_settings
from sqlalchemy import create_engine
from app.models.vector_status import VectorStatus
from app.models.enums import VectorType, JobStatus
from app.core.celery_app import app as celery_app

engine = create_engine(get_settings().DATABASE_URL)

def queue_missing_text_chunks():
    print("🔍 Buscando assets con 'visual_siglip' y 'text_summary' completados pero sin 'text_chunk'...")
    with Session(engine) as session:
        # 1. Obtenemos ids de assets que tienen siglip completado
        siglip_query = select(VectorStatus.asset_id).where(
            VectorStatus.vector_type == VectorType.VISUAL_SIGLIP,
            VectorStatus.status == JobStatus.COMPLETED
        )
        siglip_ids = session.exec(siglip_query).all()
        
        # 2. Iteramos para revisar text_chunk
        queued_count = 0
        for idx in set(siglip_ids):
            # Revisar si se insertaron al grafo (tienen text_summary COMPLETED)
            has_summary = session.exec(
                select(VectorStatus).where(
                    VectorStatus.asset_id == idx,
                    VectorStatus.vector_type == VectorType.TEXT_SUMMARY,
                    VectorStatus.status == JobStatus.COMPLETED
                )
            ).first()
            
            if not has_summary:
                continue
                
            # Revisar si NO tienen text_chunk
            has_chunk = session.exec(
                select(VectorStatus).where(
                    VectorStatus.asset_id == idx,
                    VectorStatus.vector_type == VectorType.TEXT_CHUNK
                )
            ).first()
            
            queue_it = False
            
            if not has_chunk:
                # Need to create it
                has_chunk = VectorStatus(
                    asset_id=idx,
                    vector_type=VectorType.TEXT_CHUNK,
                    status=JobStatus.ON_HOLD
                )
                session.add(has_chunk)
                session.commit()
                # Need to refresh to get the id
                session.refresh(has_chunk)
                queue_it = True
            elif has_chunk.status != JobStatus.COMPLETED and has_chunk.status != JobStatus.PROCESSING:
                if has_chunk.status != JobStatus.ON_HOLD:
                    has_chunk.status = JobStatus.ON_HOLD
                    session.add(has_chunk)
                    session.commit()
                queue_it = True
                
            if queue_it:
                print(f"✅ text_chunk configurado a ON_HOLD para asset_id: {idx} (VS ID: {has_chunk.id})")
                queued_count += 1
                
        print(f"\n🎉 Terminado. Se pusieron en ON_HOLD {queued_count} tareas de text_chunk.")

if __name__ == "__main__":
    queue_missing_text_chunks()
