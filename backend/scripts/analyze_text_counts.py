import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.database import get_session
from app.models.asset import Asset
from app.models.vector_status import VectorStatus

def analyze_text_assets():
    print("Connecting to database...")
    session = next(get_session())
    
    print("Fetching text assets...")
    text_assets = session.query(Asset).filter(Asset.asset_type == 'text').all()
    print(f"Total Text Assets found: {len(text_assets)}")
    
    summary_count = 0
    chunk_count = 0
    only_summary_count = 0
    
    for a in text_assets:
        statuses = session.query(VectorStatus).filter(VectorStatus.asset_id == a.id).all()
        types = [s.vector_type.value for s in statuses]
        
        has_summary = 'text_summary' in types
        has_chunk = 'text_chunk' in types
        
        if has_summary: summary_count += 1
        if has_chunk: chunk_count += 1
        if has_summary and not has_chunk:
            only_summary_count += 1
            print(f"Asset missing TEXT_CHUNK: {a.filename} (ID: {a.id})")
            
    print("\n--- RESULTS ---")
    print(f"Assets with TEXT_SUMMARY: {summary_count}")
    print(f"Assets with TEXT_CHUNK: {chunk_count}")
    print(f"Assets with ONLY TEXT_SUMMARY (Missing Chunk): {only_summary_count}")

if __name__ == "__main__":
    analyze_text_assets()
