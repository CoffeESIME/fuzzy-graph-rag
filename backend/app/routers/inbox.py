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


def promote_inbox_to_graph(driver, file_hash: str, entities: dict, concepts: list, tags: list) -> Dict[str, int]:
    """
    Promote approved entities and concepts to actual graph nodes.
    
    Schema-on-Write Rules (STRICT):
    ┌─────────────────────┬──────────────┬────────────────────┬─────────────────────────┐
    │ JSON Key            │ Node Type    │ Relationship       │ Rel Properties          │
    ├─────────────────────┼──────────────┼────────────────────┼─────────────────────────┤
    │ entities.persons    │ Person       │ MENTIONS_PERSON    │ weight, role            │
    │ entities.locations  │ Location     │ MENTIONS_LOCATION  │ weight, type            │
    │ entities.organizations │ Organization │ MENTIONS_ORG    │ weight                  │
    │ concepts (list)     │ Concept      │ EVOKES_CONCEPT     │ weight, reasoning       │
    └─────────────────────┴──────────────┴────────────────────┴─────────────────────────┘
    
    Tag Filtering:
    - Tags that match entity/concept names (fuzzy > 90%) are discarded
    - Prevents redundancy in the graph
    
    Returns:
        Dict with counts: {nodes_created, relationships_created, tags_saved}
    """
    nodes_created = 0
    relationships_created = 0
    
    # Collect all entity/concept names for tag filtering
    all_entity_names = []
    
    with driver.session() as session:
        # ==========================================
        # 1. PERSONS - MENTIONS_PERSON relationship
        # ==========================================
        for person in entities.get("persons", []):
            person_name = person.get("name", "").strip()
            if not person_name:
                continue
                
            all_entity_names.append(person_name)
            
            query = """
            MATCH (a:DigitalAsset {file_hash: $file_hash})
            MERGE (c:Concept {name: $name})
            ON CREATE SET 
                c.created_at = datetime(),
                c.definition = $definition,
                c.domain = $domain,
                c.concept_type = $concept_type,
                c.source = 'ai_extraction'
            
            MERGE (a)-[r:EVOKES_CONCEPT]->(c)
            ON CREATE SET 
                r.created_at = datetime(),
                r.weight = $weight,         // Peso inicial
                r.reasoning = $reasoning,
                r.evocation_count = 1
            ON MATCH SET
                r.last_seen = datetime(),
                r.evocation_count = r.evocation_count + 1,
                // LÓGICA DIFUSA INTELIGENTE:
                // Si la nueva confianza es mayor, actualízala. Si no, mantén la histórica.
                r.weight = CASE WHEN $weight > r.weight THEN $weight ELSE r.weight END,
                // Si actualizamos el peso, actualizamos el razonamiento también
                r.reasoning = CASE WHEN $weight > r.weight THEN $reasoning ELSE r.reasoning END
            RETURN c.name as created, type(r) as rel_type
            """
            result = session.run(
                query,
                file_hash=file_hash,
                name=person_name,
                description=person.get("description", ""),
                aliases=person.get("aliases", []),
                weight=person.get("confidence", person.get("weight", 1.0)),
                role=person.get("role", "mentioned")
            )
            record = result.single()
            if record:
                nodes_created += 1
                relationships_created += 1
                logger.debug(f"   👤 Created Person '{person_name}' with MENTIONS_PERSON")
        
        # ==========================================
        # 2. LOCATIONS - MENTIONS_LOCATION relationship
        # ==========================================
        for location in entities.get("locations", []):
            location_name = location.get("name", "").strip()
            if not location_name:
                continue
                
            all_entity_names.append(location_name)
            
            query = """
            MATCH (a:DigitalAsset {file_hash: $file_hash})
            MERGE (l:Location {name: $name})
            ON CREATE SET 
                l.created_at = datetime(),
                l.description = $description,
                l.coordinates = $coordinates,
                l.source = 'ai_extraction'
            ON MATCH SET
                l.last_referenced = datetime()
            MERGE (a)-[r:MENTIONS_LOCATION]->(l)
            ON CREATE SET 
                r.created_at = datetime(),
                r.weight = $weight,
                r.location_type = $location_type
            ON MATCH SET
                r.last_seen = datetime(),
                r.mention_count = coalesce(r.mention_count, 0) + 1
            RETURN l.name as created, type(r) as rel_type
            """
            result = session.run(
                query,
                file_hash=file_hash,
                name=location_name,
                description=location.get("description", ""),
                coordinates=location.get("coordinates", None),
                weight=location.get("confidence", location.get("weight", 1.0)),
                location_type=location.get("type", location.get("location_type", "unknown"))
            )
            record = result.single()
            if record:
                nodes_created += 1
                relationships_created += 1
                logger.debug(f"   📍 Created Location '{location_name}' with MENTIONS_LOCATION")
        
        # ==========================================
        # 3. ORGANIZATIONS - MENTIONS_ORG relationship
        # ==========================================
        for org in entities.get("organizations", []):
            org_name = org.get("name", "").strip()
            if not org_name:
                continue
                
            all_entity_names.append(org_name)
            
            query = """
            MATCH (a:DigitalAsset {file_hash: $file_hash})
            MERGE (o:Organization {name: $name})
            ON CREATE SET 
                o.created_at = datetime(),
                o.description = $description,
                o.org_type = $org_type,
                o.source = 'ai_extraction'
            ON MATCH SET
                o.last_referenced = datetime()
            MERGE (a)-[r:MENTIONS_ORG]->(o)
            ON CREATE SET 
                r.created_at = datetime(),
                r.weight = $weight
            ON MATCH SET
                r.last_seen = datetime(),
                r.mention_count = coalesce(r.mention_count, 0) + 1
            RETURN o.name as created, type(r) as rel_type
            """
            result = session.run(
                query,
                file_hash=file_hash,
                name=org_name,
                description=org.get("description", ""),
                org_type=org.get("type", org.get("org_type", "unknown")),
                weight=org.get("confidence", org.get("weight", 1.0))
            )
            record = result.single()
            if record:
                nodes_created += 1
                relationships_created += 1
                logger.debug(f"   🏢 Created Organization '{org_name}' with MENTIONS_ORG")
        
        # ==========================================
        # 4. CONCEPTS - EVOKES_CONCEPT relationship
        # ==========================================
        for concept in concepts:
            concept_name = concept.get("name", "").strip()
            if not concept_name:
                continue
                
            all_entity_names.append(concept_name)
            
            query = """
            MATCH (a:DigitalAsset {file_hash: $file_hash})
            MERGE (c:Concept {name: $name})
            ON CREATE SET 
                c.created_at = datetime(),
                c.definition = $definition,
                c.domain = $domain,
                c.concept_type = $concept_type,
                c.source = 'ai_extraction'
            ON MATCH SET
                c.last_referenced = datetime()
            MERGE (a)-[r:EVOKES_CONCEPT]->(c)
            ON CREATE SET 
                r.created_at = datetime(),
                r.weight = $weight,
                r.reasoning = $reasoning
            ON MATCH SET
                r.last_seen = datetime(),
                r.evocation_count = coalesce(r.evocation_count, 0) + 1
            RETURN c.name as created, type(r) as rel_type
            """
            result = session.run(
                query,
                file_hash=file_hash,
                name=concept_name,
                definition=concept.get("definition", concept.get("description", "")),
                domain=concept.get("domain", "general"),
                concept_type=concept.get("type", concept.get("concept_type", "abstract")),
                weight=concept.get("confidence", concept.get("weight", 1.0)),
                reasoning=concept.get("reasoning", concept.get("why", ""))
            )
            record = result.single()
            if record:
                nodes_created += 1
                relationships_created += 1
                logger.debug(f"   💡 Created Concept '{concept_name}' with EVOKES_CONCEPT")
        
        # ==========================================
        # 5. TAGS - Filter redundant + Save to DigitalAsset
        # ==========================================
        filtered_tags = filter_redundant_tags(tags, all_entity_names)
        
        if filtered_tags:
            query = """
            MATCH (a:DigitalAsset {file_hash: $file_hash})
            SET a.tags = $tags,
                a.tags_updated_at = datetime()
            RETURN a.file_hash as updated
            """
            session.run(query, file_hash=file_hash, tags=filtered_tags)
            logger.info(f"   🏷️ Saved {len(filtered_tags)} tags to DigitalAsset")
    
    return {
        "nodes_created": nodes_created,
        "relationships_created": relationships_created,
        "tags_saved": len(filtered_tags) if tags else 0
    }


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
