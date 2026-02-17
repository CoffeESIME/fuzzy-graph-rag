"""
backfill_events_projects.py - Backfill Event and Project nodes for already-approved InboxItems.

The OLD pipeline filtered out events/projects before saving to InboxItem.suggested_entities.
This script reads the ORIGINAL LLM analysis from MinIO sidecars to recover the lost data.

Usage:
    cd backend
    poetry run python -m scripts.backfill_events_projects
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared.clients import get_neo4j_driver, get_minio_client
from config.settings import get_settings

settings = get_settings()
MINIO_BUCKET = settings.MINIO_BUCKET


def get_analysis_from_sidecar(minio_client, file_hash: str) -> dict:
    """Read the original LLM analysis JSON from the MinIO sidecar."""
    sidecar_path = f"master_records/sidecars/{file_hash}.json"
    try:
        response = minio_client.get_object(Bucket=MINIO_BUCKET, Key=sidecar_path)
        sidecar_data = json.loads(response['Body'].read().decode('utf-8'))
        
        data_layers = sidecar_data.get('data_layers', {})
        analysis_json = (
            data_layers.get('analysis_json') or
            data_layers.get('raw_debug_data', {}).get('visual_semantic_json') or
            data_layers.get('raw_debug_data', {}).get('memory_analysis_json') or
            data_layers.get('text_summary_analysis') or
            data_layers.get('raw_debug_data', {}).get('text_analysis_json')
        )
        return analysis_json or {}
    except Exception as e:
        return {}


def backfill():
    print("\n🔧 BACKFILL: Conectando a Neo4j y MinIO...")
    
    try:
        driver = get_neo4j_driver()
        # Quick connection test
        with driver.session() as s:
            s.run("RETURN 1").single()
        print("   ✅ Neo4j connected")
    except Exception as e:
        print(f"   ❌ Neo4j connection failed: {e}")
        print("   💡 ¿Está corriendo Neo4j? (docker-compose up neo4j)")
        return
    
    try:
        minio_client = get_minio_client()
        minio_client.head_bucket(Bucket=MINIO_BUCKET)
        print(f"   ✅ MinIO connected (bucket: {MINIO_BUCKET})")
    except Exception as e:
        print(f"   ❌ MinIO connection failed: {e}")
        print("   💡 ¿Está corriendo MinIO? (docker-compose up minio)")
        return

    # 1. Find all approved InboxItems with their parent asset hash
    fetch_query = """
    MATCH (a:DigitalAsset)-[:HAS_INBOX_ITEM]->(i:InboxItem)
    WHERE i.processing_status = 'APPROVED'
    RETURN 
        a.file_hash AS file_hash,
        a.filename AS filename
    """

    events_created = 0
    projects_created = 0
    assets_touched = 0
    sidecars_read = 0

    print("\n🔧 BACKFILL: Buscando InboxItems aprobados...")
    print("   📋 Leyendo análisis original desde MinIO sidecars (lo que el pipeline viejo descartó)\n")

    with driver.session() as session:
        items = list(session.run(fetch_query))

        if not items:
            print("   ✅ No hay InboxItems aprobados para revisar.")
            return

        print(f"   📋 Encontrados {len(items)} InboxItems aprobados. Escaneando sidecars...\n")

        for record in items:
            file_hash = record["file_hash"]
            filename = record["filename"] or "unknown"

            # Read the ORIGINAL LLM analysis from MinIO sidecar
            analysis_json = get_analysis_from_sidecar(minio_client, file_hash)
            if not analysis_json:
                continue
            
            sidecars_read += 1
            graph_core = analysis_json.get("graph_core", {})
            entities = graph_core.get("entities", {})

            events = entities.get("events", [])
            projects = entities.get("projects", [])

            if not events and not projects:
                continue

            assets_touched += 1
            print(f"   📂 {filename} ({file_hash[:8]}...)")

            # --- EVENTS ---
            for event in events:
                event_name = event.get("name", "").strip()
                if not event_name:
                    continue

                q = """
                MATCH (a:DigitalAsset {file_hash: $file_hash})
                MERGE (e:Event {name: $name})
                ON CREATE SET 
                    e.created_at = datetime(),
                    e.event_type = $event_type,
                    e.date = $date,
                    e.source = 'ai_extraction',
                    e.backfilled = true
                ON MATCH SET
                    e.last_referenced = datetime()
                MERGE (a)-[r:MENTIONS_EVENT]->(e)
                ON CREATE SET 
                    r.created_at = datetime(),
                    r.weight = $weight,
                    r.mention_count = 1,
                    r.backfilled = true
                ON MATCH SET
                    r.last_seen = datetime(),
                    r.mention_count = coalesce(r.mention_count, 0) + 1
                RETURN e.name as created
                """
                result = session.run(
                    q,
                    file_hash=file_hash,
                    name=event_name,
                    event_type=event.get("type", event.get("event_type", "unknown")),
                    date=event.get("date", None),
                    weight=event.get("confidence", event.get("weight", 1.0))
                )
                if result.single():
                    events_created += 1
                    print(f"      📅 Event: '{event_name}'")

            # --- PROJECTS ---
            for project in projects:
                project_title = project.get("title", project.get("name", "")).strip()
                if not project_title:
                    continue

                q = """
                MATCH (a:DigitalAsset {file_hash: $file_hash})
                MERGE (pr:Project {title: $title})
                ON CREATE SET 
                    pr.created_at = datetime(),
                    pr.project_type = $project_type,
                    pr.year = $year,
                    pr.source = 'ai_extraction',
                    pr.backfilled = true
                ON MATCH SET
                    pr.last_referenced = datetime()
                MERGE (a)-[r:MENTIONS_PROJECT]->(pr)
                ON CREATE SET 
                    r.created_at = datetime(),
                    r.weight = $weight,
                    r.mention_count = 1,
                    r.backfilled = true
                ON MATCH SET
                    r.last_seen = datetime(),
                    r.mention_count = coalesce(r.mention_count, 0) + 1
                RETURN pr.title as created
                """
                result = session.run(
                    q,
                    file_hash=file_hash,
                    title=project_title,
                    project_type=project.get("type", project.get("project_type", "unknown")),
                    year=project.get("year", None),
                    weight=project.get("confidence", project.get("weight", 1.0))
                )
                if result.single():
                    projects_created += 1
                    print(f"      🏗️ Project: '{project_title}'")

    print(f"\n{'='*50}")
    print(f"✅ BACKFILL COMPLETADO")
    print(f"   Sidecars leídos: {sidecars_read}")
    print(f"   Assets con events/projects: {assets_touched}")
    print(f"   Events creados/actualizados: {events_created}")
    print(f"   Projects creados/actualizados: {projects_created}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    try:
        backfill()
    except Exception as e:
        print(f"❌ Error en backfill: {e}")
        import traceback
        traceback.print_exc()
