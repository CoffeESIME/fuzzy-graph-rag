from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import logging
import json

from shared.clients import get_neo4j_driver, get_minio_client
from config.settings import get_settings

router = APIRouter(
    prefix="/enrichment/health",
    tags=["enrichment", "health"]
)

logger = logging.getLogger(__name__)
settings = get_settings()

class HealthStatsResponse(BaseModel):
    total_artists: int
    total_projects: int
    orphaned_audio_no_artist: int
    orphaned_audio_no_project: int

class RepairResponse(BaseModel):
    success: bool
    message: str
    items_updated: int

@router.get("/stats", response_model=HealthStatsResponse)
def get_health_stats():
    """Returns statistics about music and arts nodes in the graph."""
    driver = get_neo4j_driver()
    
    query = """
    MATCH (p:Person)
    WITH count(p) as total_artists
    
    MATCH (pr:Project)
    WITH total_artists, count(pr) as total_projects
    
    OPTIONAL MATCH (d1:DigitalAsset)
    WHERE (d1.mime_type CONTAINS 'audio' OR d1.filename ENDS WITH '.mp3' OR d1.filename ENDS WITH '.flac' OR d1.filename ENDS WITH '.wav')
      AND NOT (d1)-[:CREATED_BY]->(:Person)
    WITH total_artists, total_projects, count(d1) as orphaned_audio_no_artist
    
    OPTIONAL MATCH (d2:DigitalAsset)
    WHERE (d2.mime_type CONTAINS 'audio' OR d2.filename ENDS WITH '.mp3' OR d2.filename ENDS WITH '.flac' OR d2.filename ENDS WITH '.wav')
      AND NOT (d2)-[:MENTIONS_PROJECT]->(:Project)
    WITH total_artists, total_projects, orphaned_audio_no_artist, count(d2) as orphaned_audio_no_project
    
    RETURN total_artists, total_projects, orphaned_audio_no_artist, orphaned_audio_no_project
    """
    
    try:
        with driver.session() as session:
            result = session.run(query).single()
            if not result:
                return HealthStatsResponse(
                    total_artists=0, total_projects=0,
                    orphaned_audio_no_artist=0, orphaned_audio_no_project=0
                )
            
            return HealthStatsResponse(
                total_artists=result["total_artists"],
                total_projects=result["total_projects"],
                orphaned_audio_no_artist=result["orphaned_audio_no_artist"],
                orphaned_audio_no_project=result["orphaned_audio_no_project"]
            )
    except Exception as e:
        logger.error(f"Error fetching health stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/repair-artists", response_model=RepairResponse)
def repair_artists():
    """Repairs audio-to-artist links by parsing filename 'Artist - Song.mp3'."""
    driver = get_neo4j_driver()
    
    fetch_query = """
    MATCH (d:DigitalAsset)
    WHERE (d.mime_type CONTAINS 'audio' OR d.filename ENDS WITH '.mp3' OR d.filename ENDS WITH '.flac' OR d.filename ENDS WITH '.wav')
      AND NOT (d)-[:CREATED_BY]->(:Person)
    RETURN elementId(d) as id, d.filename as filename
    """
    
    updates = 0
    
    try:
        with driver.session() as session:
            results = session.run(fetch_query)
            
            for record in results:
                asset_id = record["id"]
                filename = record["filename"]
                
                if not filename or " - " not in filename:
                    continue
                    
                parts = filename.split(" - ")
                artist_name = parts[0].strip()
                
                if artist_name.isdigit() or len(artist_name) < 2: 
                    continue
                    
                update_q = """
                MATCH (d:DigitalAsset) WHERE elementId(d) = $asset_id
                MERGE (p:Person {name: $artist_name})
                ON CREATE SET p.created_via = 'heuristic_repair'
                MERGE (d)-[r:CREATED_BY]->(p)
                SET r.weight = 1.0
                """
                session.run(update_q, asset_id=asset_id, artist_name=artist_name)
                updates += 1
                
        return RepairResponse(
            success=True,
            message=f"Se auto-vincularon {updates} archivos de audio a Artistas.",
            items_updated=updates
        )
    except Exception as e:
        logger.error(f"Error repairing artists: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def _get_analysis_from_sidecar(minio_client, file_hash: str) -> dict:
    bucket = settings.MINIO_BUCKET if hasattr(settings, 'MINIO_BUCKET') else "rag-dataset"
    sidecar_path = f"master_records/sidecars/{file_hash}.json"
    try:
        response = minio_client.get_object(Bucket=bucket, Key=sidecar_path)
        sidecar_data = json.loads(response['Body'].read().decode('utf-8'))
        
        data_layers = sidecar_data.get('data_layers', {})
        return (
            data_layers.get('analysis_json') or
            data_layers.get('raw_debug_data', {}).get('visual_semantic_json') or
            data_layers.get('raw_debug_data', {}).get('memory_analysis_json') or
            data_layers.get('text_summary_analysis') or
            data_layers.get('raw_debug_data', {}).get('text_analysis_json') or 
            {}
        )
    except Exception:
        return {}

@router.post("/backfill-projects", response_model=RepairResponse)
def backfill_projects():
    """Recovers Projects and Events mapped by the LLM from MinIO sidecars."""
    driver = get_neo4j_driver()
    minio_client = get_minio_client()
    
    fetch_query = """
    MATCH (a:DigitalAsset)-[:HAS_INBOX_ITEM]->(i:InboxItem)
    WHERE i.processing_status = 'APPROVED'
      AND NOT (a)-[:MENTIONS_PROJECT]->(:Project)
    RETURN a.file_hash AS file_hash
    """
    
    events_created = 0
    projects_created = 0
    assets_touched = 0
    
    try:
        with driver.session() as session:
            items = list(session.run(fetch_query))
            
            for record in items:
                file_hash = record["file_hash"]
                analysis_json = _get_analysis_from_sidecar(minio_client, file_hash)
                
                if not analysis_json:
                    continue
                    
                graph_core = analysis_json.get("graph_core", {})
                entities = graph_core.get("entities", {})
                
                events = entities.get("events", [])
                projects = entities.get("projects", [])
                
                if not events and not projects:
                    continue
                    
                assets_touched += 1
                
                # --- EVENTS ---
                for event in events:
                    event_name = event.get("name", "").strip()
                    if not event_name: continue
                        
                    q = """
                    MATCH (a:DigitalAsset {file_hash: $file_hash})
                    MERGE (e:Event {name: $name})
                    ON CREATE SET 
                        e.created_at = datetime(),
                        e.event_type = $event_type,
                        e.date = $date,
                        e.source = 'ai_extraction',
                        e.backfilled = true
                    ON MATCH SET e.last_referenced = datetime()
                    MERGE (a)-[r:MENTIONS_EVENT]->(e)
                    ON CREATE SET 
                        r.created_at = datetime(),
                        r.weight = $weight,
                        r.mention_count = 1,
                        r.backfilled = true
                    ON MATCH SET
                        r.last_seen = datetime(),
                        r.mention_count = coalesce(r.mention_count, 0) + 1
                    """
                    session.run(q, file_hash=file_hash, name=event_name,
                               event_type=event.get("type", event.get("event_type", "unknown")),
                               date=event.get("date", None),
                               weight=event.get("confidence", event.get("weight", 1.0)))
                    events_created += 1

                # --- PROJECTS ---
                for project in projects:
                    project_title = project.get("title", project.get("name", "")).strip()
                    if not project_title: continue

                    q = """
                    MATCH (a:DigitalAsset {file_hash: $file_hash})
                    MERGE (pr:Project {title: $title})
                    ON CREATE SET 
                        pr.created_at = datetime(),
                        pr.project_type = $project_type,
                        pr.year = $year,
                        pr.source = 'ai_extraction',
                        pr.backfilled = true
                    ON MATCH SET pr.last_referenced = datetime()
                    MERGE (a)-[r:MENTIONS_PROJECT]->(pr)
                    ON CREATE SET 
                        r.created_at = datetime(),
                        r.weight = $weight,
                        r.mention_count = 1,
                        r.backfilled = true
                    ON MATCH SET
                        r.last_seen = datetime(),
                        r.mention_count = coalesce(r.mention_count, 0) + 1
                    """
                    session.run(q, file_hash=file_hash, title=project_title,
                               project_type=project.get("type", project.get("project_type", "unknown")),
                               year=project.get("year", None),
                               weight=project.get("confidence", project.get("weight", 1.0)))
                    projects_created += 1

        return RepairResponse(
            success=True,
            message=f"Backfill completado: {assets_touched} archivos procesados. {projects_created} Proyectos y {events_created} Eventos creados.",
            items_updated=projects_created + events_created
        )
    except Exception as e:
        logger.error(f"Error backfilling projects/events: {e}")
        raise HTTPException(status_code=500, detail=str(e))
