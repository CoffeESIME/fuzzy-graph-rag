"""
Inbox Review API Router
=======================

Endpoints for the Human-in-the-Loop (HITL) graph review flow.
Allows users to review, edit, and approve AI-suggested entities
before they are promoted to the main Neo4j graph.

Endpoints:
- GET /inbox/pending: List all items awaiting human review
- POST /inbox/{file_hash}/approve: Approve edited entities and promote to graph
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import logging
import re
from shared.clients import get_neo4j_driver

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/inbox",
    tags=["inbox", "graph-review"]
)


# ==========================================
# PYDANTIC SCHEMAS
# ==========================================

class EntityDict(BaseModel):
    """A single entity suggestion from LLM."""
    name: str
    description: Optional[str] = None
    aliases: Optional[List[str]] = []
    
    class Config:
        extra = "allow"  # Allow additional fields


class InboxItemResponse(BaseModel):
    """
    Response model for a pending inbox item.
    
    Contains data from BOTH the parent DigitalAsset (for identification)
    and the child InboxItem (for editing).
    """
    # Parent DigitalAsset data - NEEDED for approval endpoint URL
    file_hash: str = Field(description="Parent asset file hash (used as identifier)")
    filename: str = Field(description="Parent asset original filename")
    
    # InboxItem data - FOR DISPLAY AND EDITING
    inbox_id: str = Field(description="InboxItem node ID")
    ai_summary: str = Field(description="AI-generated summary of the content")
    suggested_entities: Dict[str, List[Dict[str, Any]]] = Field(
        default_factory=dict,
        description="Entities grouped by type: {persons: [], locations: [], organizations: []}"
    )
    suggested_concepts: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Abstract concepts/themes extracted"
    )
    tags: List[str] = Field(default_factory=list, description="Suggested tags")
    processing_status: str = Field(description="Current status (REVIEW_REQUIRED, APPROVED, etc)")


class ApprovalPayload(BaseModel):
    """
    Payload for approving and promoting inbox items.
    
    Contains the user-edited/confirmed data that should be
    written to the graph.
    """
    entities: Dict[str, List[Dict[str, Any]]] = Field(
        description="Curated entities by type: {persons: [], locations: [], organizations: []}"
    )
    concepts: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Curated concepts to create as Concept nodes"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Final approved tags"
    )


class ApprovalResponse(BaseModel):
    """Response from the approval endpoint."""
    success: bool
    message: str
    file_hash: str
    nodes_created: int = 0
    relationships_created: int = 0


# ==========================================
# HELPER FUNCTIONS
# ==========================================

def safe_json_loads(json_str: Optional[str], default: Any = None) -> Any:
    """
    Safely parse JSON string, returning default on failure.
    
    Handles None, empty strings, and invalid JSON gracefully.
    """
    if not json_str:
        return default if default is not None else {}
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        logger.warning(f"Failed to parse JSON: {json_str[:100] if json_str else 'None'}...")
        return default if default is not None else {}


def filter_redundant_tags(tags: List[str], entity_names: List[str], fuzzy_threshold: float = 0.9) -> List[str]:
    """
    Filter out tags that are redundant with entity/concept names.
    
    Uses simple normalized matching (no external fuzzy lib dependency).
    A tag is considered redundant if:
    - Exact match (case-insensitive)
    - One is a substring of the other (normalized)
    - High character overlap (> 90%)
    
    Args:
        tags: List of tags to filter
        entity_names: List of entity/concept names to check against
        fuzzy_threshold: Similarity threshold (0.0 - 1.0)
        
    Returns:
        Filtered list of non-redundant tags
    """
    def normalize(s: str) -> str:
        """Normalize string for comparison."""
        return s.lower().strip().replace("-", " ").replace("_", " ")
    
    def similarity_ratio(a: str, b: str) -> float:
        """Calculate simple character overlap ratio."""
        a_norm, b_norm = normalize(a), normalize(b)
        
        # Exact match
        if a_norm == b_norm:
            return 1.0
        
        # Substring match  
        if a_norm in b_norm or b_norm in a_norm:
            return 0.95
        
        # Character overlap (Jaccard-like)
        set_a, set_b = set(a_norm), set(b_norm)
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union > 0 else 0.0
    
    normalized_entity_names = [normalize(name) for name in entity_names]
    filtered_tags = []
    
    for tag in tags:
        tag_norm = normalize(tag)
        is_redundant = False
        
        for entity_name in normalized_entity_names:
            if similarity_ratio(tag, entity_name) >= fuzzy_threshold:
                logger.debug(f"   🏷️ Filtering redundant tag '{tag}' (matches '{entity_name}')")
                is_redundant = True
                break
        
        if not is_redundant:
            filtered_tags.append(tag)
    
    if len(filtered_tags) < len(tags):
        logger.info(f"   🧹 Filtered {len(tags) - len(filtered_tags)} redundant tags (kept {len(filtered_tags)})")
    
    return filtered_tags


def sanitize_rel_type(rel_type: str, default: str) -> str:
    """Valida y limpia el tipo de relación."""
    if not rel_type:
        return default
    
    # Normalizar (Upper snake case)
    clean_rel = rel_type.strip().upper().replace(" ", "_")
    
    # Validar contra whitelist (Critical for Cypher injection prevention)
    if clean_rel in ALLOWED_RELATIONSHIPS:
        return clean_rel
    
    # Si el LLM inventó un verbo raro, volver al default seguro
    logger.warning(f"⚠️ Relación desconocida '{clean_rel}', usando default '{default}'")
    return default

def promote_inbox_to_graph(driver, file_hash: str, entities: dict, concepts: list, tags: list) -> Dict[str, int]:
    """
    Promote approved entities/concepts using DYNAMIC relationships.
    """
    nodes_created = 0
    relationships_created = 0
    
    all_entity_names = []
    
    with driver.session() as session:
        # ==========================================
        # 1. PERSONS (Dynamic: CREATED_BY vs MENTIONS)
        # ==========================================
        for person in entities.get("persons", []):
            person_name = person.get("name", "").strip()
            if not person_name: continue
            all_entity_names.append(person_name)
            
            # A. Obtener tipo de relación dinámica (Default: MENTIONS)
            raw_rel = person.get("relation_type", "MENTIONS")
            rel_type = sanitize_rel_type(raw_rel, "MENTIONS")
            
            # B. Inyectar relación en f-string (Seguro porque pasó por sanitize)
            query = f"""
            MATCH (a:DigitalAsset {{file_hash: $file_hash}})
            MERGE (p:Person {{name: $name}})
            ON CREATE SET 
                p.created_at = datetime(),
                p.description = $description,
                p.aliases = $aliases,
                p.source = 'ai_extraction'
            ON MATCH SET
                p.last_referenced = datetime()
            
            MERGE (a)-[r:{rel_type}]->(p)
            ON CREATE SET 
                r.created_at = datetime(),
                r.weight = $weight,
                r.role = $role,
                r.reasoning = $reasoning,
                r.count = 1
            ON MATCH SET
                r.last_seen = datetime(),
                r.count = coalesce(r.count, 0) + 1,
                r.weight = CASE WHEN $weight > r.weight THEN $weight ELSE r.weight END
            """
            
            session.run(query, 
                file_hash=file_hash, name=person_name,
                description=person.get("description", ""),
                aliases=person.get("aliases", []),
                weight=person.get("confidence", 1.0),
                role=person.get("role", "mentioned"),
                reasoning=person.get("reasoning", "") # Guardamos el porqué
            )
            nodes_created += 1; relationships_created += 1

        # ==========================================
        # 2. LOCATIONS
        # ==========================================
        for location in entities.get("locations", []):
            loc_name = location.get("name", "").strip()
            if not loc_name: continue
            all_entity_names.append(loc_name)
            
            raw_rel = location.get("relation_type", "MENTIONS")
            rel_type = sanitize_rel_type(raw_rel, "MENTIONS") # Podría ser LOCATED_AT

            query = f"""
            MATCH (a:DigitalAsset {{file_hash: $file_hash}})
            MERGE (l:Location {{name: $name}})
            ON CREATE SET l.created_at = datetime(), l.source = 'ai_extraction'
            MERGE (a)-[r:{rel_type}]->(l)
            ON CREATE SET r.weight = $weight, r.created_at = datetime()
            ON MATCH SET r.weight = CASE WHEN $weight > r.weight THEN $weight ELSE r.weight END
            """
            session.run(query, file_hash=file_hash, name=loc_name, 
                        weight=location.get("confidence", 1.0))
            nodes_created += 1; relationships_created += 1

        # ==========================================
        # 3. PROJECTS (Vital para Álbumes)
        # ==========================================
        for project in entities.get("projects", []):
            proj_title = project.get("title", project.get("name", "")).strip()
            if not proj_title: continue
            all_entity_names.append(proj_title)
            
            # Aquí es donde capturamos "PART_OF_PROJECT" (Canción -> Álbum)
            raw_rel = project.get("relation_type", "MENTIONS")
            rel_type = sanitize_rel_type(raw_rel, "MENTIONS")

            query = f"""
            MATCH (a:DigitalAsset {{file_hash: $file_hash}})
            MERGE (pr:Project {{title: $title}})
            ON CREATE SET 
                pr.created_at = datetime(),
                pr.project_type = $type,
                pr.source = 'ai_extraction'
            
            MERGE (a)-[r:{rel_type}]->(pr)
            ON CREATE SET r.weight = $weight, r.created_at = datetime()
            """
            session.run(query, file_hash=file_hash, title=proj_title, 
                        type=project.get("type", "unknown"),
                        weight=project.get("confidence", 1.0))
            nodes_created += 1; relationships_created += 1

        # ==========================================
        # 4. CONCEPTS (Fuzzy Logic Core)
        # ==========================================
        for concept in concepts:
            c_name = concept.get("name", "").strip()
            if not c_name: continue
            all_entity_names.append(c_name)
            
            # Dinámico: EVOKES vs EXPLORES vs DEFINES
            raw_rel = concept.get("relation_type", "EVOKES")
            rel_type = sanitize_rel_type(raw_rel, "EVOKES")

            query = f"""
            MATCH (a:DigitalAsset {{file_hash: $file_hash}})
            MERGE (c:Concept {{name: $name}})
            ON CREATE SET 
                c.created_at = datetime(),
                c.domain = $domain,
                c.definition = $definition,
                c.source = 'ai_extraction'
            
            MERGE (a)-[r:{rel_type}]->(c)
            ON CREATE SET 
                r.created_at = datetime(),
                r.weight = $weight,
                r.reasoning = $reasoning
            ON MATCH SET
                r.weight = CASE WHEN $weight > r.weight THEN $weight ELSE r.weight END,
                r.reasoning = CASE WHEN $weight > r.weight THEN $reasoning ELSE r.reasoning END
            """
            session.run(query, 
                file_hash=file_hash, name=c_name,
                domain=concept.get("domain", "General"),
                definition=concept.get("definition", ""),
                weight=concept.get("confidence", 0.5), # Fuzzy default
                reasoning=concept.get("reasoning", "")
            )
            nodes_created += 1; relationships_created += 1

        # 5. TAGS (Igual que antes)
        filtered_tags = filter_redundant_tags(tags, all_entity_names)
        if filtered_tags:
            session.run("""
            MATCH (a:DigitalAsset {file_hash: $file_hash})
            SET a.tags = $tags
            """, file_hash=file_hash, tags=filtered_tags)

    return {"nodes_created": nodes_created, "relationships_created": relationships_created}
# ==========================================
# ENDPOINTS
# ==========================================

@router.get("/pending", response_model=List[InboxItemResponse])
async def get_pending_inbox_items():
    """
    Get all inbox items awaiting human review.
    
    Returns items with processing_status = 'REVIEW_REQUIRED',
    joining data from both DigitalAsset (parent) and InboxItem (child).
    
    The file_hash from the parent is critical as it's used as
    the identifier for the approval endpoint.
    """
    logger.info("📥 Fetching pending inbox items for review")
    
    driver = get_neo4j_driver()
    
    query = """
    MATCH (a:DigitalAsset)-[:HAS_INBOX_ITEM]->(i:InboxItem)
    WHERE i.processing_status = 'REVIEW_REQUIRED'
    RETURN 
        a.file_hash as file_hash, 
        a.filename as filename, 
        i.id as inbox_id,
        i.ai_summary as summary,
        i.suggested_entities as entities_str,
        i.suggested_concepts as concepts_str,
        i.tags as tags_list,
        i.processing_status as status
    ORDER BY i.updated_at DESC
    """
    
    items = []
    
    try:
        with driver.session() as session:
            result = session.run(query)
            
            for record in result:
                # Deserialize JSON strings from Neo4j
                entities = safe_json_loads(record["entities_str"], {})
                concepts = safe_json_loads(record["concepts_str"], [])
                tags = record["tags_list"] if record["tags_list"] else []
                
                item = InboxItemResponse(
                    file_hash=record["file_hash"],
                    filename=record["filename"] or "unknown",
                    inbox_id=record["inbox_id"],
                    ai_summary=record["summary"] or "",
                    suggested_entities=entities,
                    suggested_concepts=concepts,
                    tags=tags,
                    processing_status=record["status"]
                )
                items.append(item)
        
        logger.info(f"   Found {len(items)} pending inbox items")
        return items
        
    except Exception as e:
        logger.error(f"❌ Failed to fetch pending inbox items: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.post("/{file_hash}/approve", response_model=ApprovalResponse)
async def approve_and_promote(file_hash: str, payload: ApprovalPayload):
    """
    Approve user-curated entities and promote them to the graph.
    
    Flow:
    1. Update InboxItem with curated data (persistence)
    2. Create actual Person/Location/Organization/Concept nodes
    3. Link nodes to the DigitalAsset
    4. Update InboxItem status to APPROVED
    
    Args:
        file_hash: The parent DigitalAsset's file hash
        payload: Curated entities, concepts, and tags
        
    Returns:
        ApprovalResponse with counts of created nodes
    """
    logger.info(f"✅ Approving inbox item for asset: {file_hash[:8]}...")
    logger.info(f"   Entities: {sum(len(v) for v in payload.entities.values())}")
    logger.info(f"   Concepts: {len(payload.concepts)}")
    logger.info(f"   Tags: {len(payload.tags)}")
    
    driver = get_neo4j_driver()
    
    try:
        # Step 1: Update InboxItem with curated data
        update_query = """
        MATCH (a:DigitalAsset {file_hash: $file_hash})-[:HAS_INBOX_ITEM]->(i:InboxItem)
        SET 
            i.suggested_entities = $entities_json,
            i.suggested_concepts = $concepts_json,
            i.tags = $tags_list,
            i.user_curation_date = datetime(),
            i.processing_status = 'APPROVED'
        RETURN i.id as inbox_id
        """
        
        with driver.session() as session:
            result = session.run(
                update_query,
                file_hash=file_hash,
                entities_json=json.dumps(payload.entities),
                concepts_json=json.dumps(payload.concepts),
                tags_list=payload.tags
            )
            record = result.single()
            
            if not record:
                raise HTTPException(
                    status_code=404, 
                    detail=f"No inbox item found for asset with hash: {file_hash}"
                )
        
        # Step 2: Promote to graph - create actual nodes
        counts = promote_inbox_to_graph(
            driver=driver,
            file_hash=file_hash,
            entities=payload.entities,
            concepts=payload.concepts,
            tags=payload.tags
        )
        
        logger.info(f"   ✅ Promoted: {counts['nodes_created']} nodes, {counts['relationships_created']} relationships")
        
        return ApprovalResponse(
            success=True,
            message=f"Successfully approved and promoted {counts['nodes_created']} entities to graph",
            file_hash=file_hash,
            nodes_created=counts["nodes_created"],
            relationships_created=counts["relationships_created"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Approval failed for {file_hash}: {e}")
        raise HTTPException(status_code=500, detail=f"Approval failed: {str(e)}")


@router.get("/stats")
async def get_inbox_stats():
    """
    Get statistics about inbox items.
    
    Returns counts by status for dashboard display.
    """
    logger.info("📊 Fetching inbox statistics")
    
    driver = get_neo4j_driver()
    
    query = """
    MATCH (i:InboxItem)
    RETURN 
        i.processing_status as status,
        count(i) as count
    """
    
    try:
        stats = {"REVIEW_REQUIRED": 0, "APPROVED": 0, "REJECTED": 0}
        
        with driver.session() as session:
            result = session.run(query)
            for record in result:
                status = record["status"] or "UNKNOWN"
                stats[status] = record["count"]
        
        return {
            "pending": stats.get("REVIEW_REQUIRED", 0),
            "approved": stats.get("APPROVED", 0),
            "rejected": stats.get("REJECTED", 0),
            "total": sum(stats.values())
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to fetch inbox stats: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
