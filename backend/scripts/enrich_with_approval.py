"""
enrich_with_approval.py - Human-in-the-Loop Enrichment Pipeline
================================================================

Combines External Truth (Wikipedia) with Internal Relevance (Graph Context)
to generate rich semantic profiles for graph nodes.

Flow:
1. CANDIDATE DISCOVERY  → Find un-enriched nodes with connections
2. LOCAL CONTEXT         → Extract file types, tags, co-occurring entities from Neo4j
3. EXTERNAL GROUNDING    → Wikipedia summary (graceful fallback)
4. LLM ONTOLOGICAL ANALYSIS → Fuse both sources into a semantic profile
5. HUMAN APPROVAL        → Interactive y/n per candidate
6. PERSISTENCE           → Neo4j nodes + MinIO sidecar JSON + pending vectorization

Usage:
    cd backend
    poetry run python -m scripts.enrich_with_approval [--limit 10] [--auto]
"""

import sys
import os
import json
import uuid
import re
import hashlib
import argparse
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

import requests

# Setup path for local imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared.clients import get_neo4j_driver, get_minio_client
from config.settings import get_settings

# Wikipedia (optional dependency)
try:
    import wikipedia
    wikipedia.set_lang("es")
    wikipedia.API_URL = "https://es.wikipedia.org/w/api.php"
    HAS_WIKIPEDIA = True
except ImportError:
    HAS_WIKIPEDIA = False

# ==========================================
# CONFIGURATION
# ==========================================
settings = get_settings()
LLM_GATEWAY_BASE_URL = f"{settings.LLM_GATEWAY_URL}/v1"
MINIO_BUCKET = settings.MINIO_BUCKET

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Whitelist for graph relation types (shared with inbox.py)
ALLOWED_ENRICHMENT_RELATIONS = {
    "EMBODIES", "EXPLORES", "EVOKES",
    "CREATED_BY", "PARTICIPATED_IN", "DEPICTS",
    "PART_OF_PROJECT", "ABOUT_PROJECT",
    "ABOUT_EVENT", "CAPTURED_DURING",
    "INFLUENCED_BY", "CONTEMPORARY_OF",
    "MENTIONS", "DEFINES",
}

# ==========================================
# SYSTEM PROMPT FOR LLM
# ==========================================
ENRICHMENT_SYSTEM_PROMPT = """
Eres un Arquitecto de Ontologías y Curador de Conocimiento para un sistema RAG avanzado.
Tu objetivo es **sintetizar** un "Perfil Semántico" para una entidad, fusionando hechos externos con el contexto interno del usuario.

### TUS FUENTES DE INFORMACIÓN:
1. **WIKI_TRUTH (Grounding):** Datos factuales extraídos de Wikipedia. Úsalos para definiciones precisas y biografías.
2. **GRAPH_CONTEXT (Relevancia):** Los archivos locales donde aparece la entidad. Esto dicta el "Ángulo" del perfil.
   - *Ejemplo:* Si "Einstein" aparece en archivos de "Música Electrónica", tu perfil debe enfocarlo como "Referencia Pop/Cultural", no solo como Físico.

### TUS OBJETIVOS DE SALIDA (JSON):
1. **`text_for_embedding`:** Un párrafo narrativo DENSO (150-200 palabras). Debe explicar quién es la entidad Y por qué es relevante en el contexto de los archivos. Este texto será vectorizado.
2. **`fuzzy_relations`:** Relaciones ontológicas estrictas con pesos de confianza (0.0 - 1.0).

### RÚBRICA DE RELACIONES (ONTOLOGÍA STRICTA):
Usa SOLO estos verbos. No inventes otros.

* **EMBODIES (Peso 1.0):** La entidad ES la encarnación misma del concepto.
    * *Uso:* Sísifo -> Absurdo; Romeo -> Amor Romántico.
* **EXPLORES (Peso 0.8 - 0.9):** La entidad investiga, critica o trata este tema profundamente.
    * *Uso:* Orwell -> Vigilancia; Pink Floyd -> Locura.
* **EVOKES (Peso 0.5 - 0.7):** Conexión estética, atmosférica o sutil.
    * *Uso:* Música Gótica -> Melancolía; Lluvia -> Tristeza.
* **CREATED_BY / PARTICIPATED_IN (Peso 1.0):** Autoría factual.

### FEW-SHOT EXAMPLES (APRENDE DE ESTOS PATRONES):

--- EJEMPLO 1: PERSONAJE CONTEXTUALIZADO (Sísifo) ---
**Input:**
* **Entity:** "Sísifo"
* **Wiki_Truth:** "En la mitología griega, rey de Éfira condenado a empujar una roca cuesta arriba por la eternidad."
* **Graph_Context:** "Conectado a: 'Ensayo sobre el Absurdo.pdf', 'Camus_El_Mito.epub', 'Canción: Weight of the World.mp3'"

**Output JSON:**
{
  "canonical_name": "Sísifo",
  "entity_type": "Mythological Figure",
  "domain": "Philosophy / Mythology",
  "text_for_embedding": "Sísifo es una figura de la mitología griega conocida por su castigo eterno de empujar una roca, que se ha convertido en el arquetipo del esfuerzo inútil y la resiliencia absurda. En el contexto de este grafo, Sísifo no es solo un mito, sino el símbolo central del existencialismo de Albert Camus. Representa la condición humana: encontrar propósito en una tarea repetitiva y sin sentido aparente. Su presencia conecta la mitología clásica con la filosofía moderna del Absurdo.",
  "sidecar_data": {
    "short_bio": "Arquetipo mitológico del esfuerzo eterno y símbolo central del absurdo existencialista.",
    "emotional_atmosphere": ["Agobiante", "Resiliente", "Cíclico"],
    "fuzzy_concepts": [
      {"name": "El Absurdo", "weight": 1.0, "relation_type": "EMBODIES", "reasoning": "Personificación central del concepto en la obra de Camus."},
      {"name": "Resiliencia", "weight": 0.7, "relation_type": "EVOKES", "reasoning": "La aceptación de su castigo sugiere una fuerza interna."},
      {"name": "Eterno Retorno", "weight": 0.8, "relation_type": "EXPLORES", "reasoning": "La naturaleza cíclica de su castigo."}
    ]
  },
  "requires_embedding": true
}

--- EJEMPLO 2: ARTISTA MUSICAL (Nach) ---
**Input:**
* **Entity:** "Nach"
* **Wiki_Truth:** "Ignacio Fornés Olmo, rapero, poeta y sociólogo español. Conocido por 'Poesía Difusa'."
* **Graph_Context:** "Conectado a: 'Disparos de Silencio.mp3', 'Efectos Vocales.mp3'. Tags: Protesta, Rap."

**Output JSON:**
{
  "canonical_name": "Nach",
  "entity_type": "Artist",
  "domain": "Music / Hip-Hop",
  "text_for_embedding": "Nach (Ignacio Fornés) es un referente fundamental del Rap en español, distinguido por su lírica densa y su enfoque en la crítica social. A diferencia del rap gangsta, su obra 'Disparos de Silencio' y otros temas presentes en el grafo exploran la desigualdad, la corrupción política y la introspección existencial. Combina la agresividad rítmica del Hip-Hop con estructuras de poesía hablada (Spoken Word), utilizando el lenguaje como herramienta de protesta.",
  "sidecar_data": {
    "short_bio": "Rapero y poeta español conocido por su lírica intelectual y compromiso social.",
    "emotional_atmosphere": ["Crítico", "Cerebral", "Urbano"],
    "fuzzy_concepts": [
      {"name": "Protesta Social", "weight": 0.95, "relation_type": "EXPLORES", "reasoning": "Tema recurrente y explícito en sus letras."},
      {"name": "Poesía Urbana", "weight": 1.0, "relation_type": "EMBODIES", "reasoning": "Su estilo define este subgénero."},
      {"name": "Sociología", "weight": 0.6, "relation_type": "EVOKES", "reasoning": "Su formación académica permea su análisis lírico."}
    ]
  },
  "requires_embedding": true
}

--- EJEMPLO 3: CONCEPTO FILOSÓFICO (Existencialismo) ---
**Input:**
* **Entity:** "Existencialismo"
* **Wiki_Truth:** "Corriente filosófica que sostiene que la existencia precede a la esencia. Sartre, Kierkegaard."
* **Graph_Context:** "Conectado a: 'La Nausea.pdf', 'Radiohead - Creep.mp3', 'Blade Runner.mkv'"

**Output JSON:**
{
  "canonical_name": "Existencialismo",
  "entity_type": "Concept",
  "domain": "Philosophy",
  "text_for_embedding": "El Existencialismo es una corriente filosófica centrada en la libertad individual, la responsabilidad y la angustia ante un universo sin sentido intrínseco. En este grafo, el concepto actúa como un puente semántico que conecta textos académicos (Sartre) con manifestaciones culturales de alienación moderna (como Radiohead o Blade Runner). Se define por la premisa 'la existencia precede a la esencia', enfatizando la creación del propio destino.",
  "sidecar_data": {
    "short_bio": "Filosofía de la libertad radical y la búsqueda de sentido en un mundo absurdo.",
    "emotional_atmosphere": ["Angustioso", "Libre", "Reflexivo"],
    "fuzzy_concepts": [
      {"name": "Libertad Radical", "weight": 1.0, "relation_type": "DEFINES", "reasoning": "Núcleo teórico del concepto."},
      {"name": "Alienación Urbana", "weight": 0.7, "relation_type": "EVOKES", "reasoning": "Conexión temática con los archivos multimedia del grafo."}
    ]
  },
  "requires_embedding": true
}
"""

# ==========================================
# 1. CANDIDATE DISCOVERY
# ==========================================
def find_candidates(driver, limit: int = 15) -> List[Dict[str, Any]]:
    """
    Find un-enriched nodes with connections.
    Returns list of candidates with basic info.
    """
    query = """
    MATCH (n)
    WHERE (n:Person OR n:Concept OR n:Location OR n:Organization OR n:Event OR n:Project)
      AND n.enriched IS NULL
      AND NOT n.name IN ['Usuario', 'Admin', 'Me']
    
    // Must have at least one connection
    MATCH (n)<-[r]-(asset:DigitalAsset)
    
    WITH n, labels(n) as node_labels, count(distinct asset) as connections
    WHERE connections >= 1
    
    RETURN 
        elementId(n) as node_id,
        n.name as name,
        coalesce(n.title, n.name) as display_name,
        node_labels[0] as label,
        connections
    ORDER BY connections DESC
    LIMIT $limit
    """
    
    candidates = []
    with driver.session() as session:
        results = session.run(query, limit=limit)
        for record in results:
            candidates.append({
                "node_id": record["node_id"],
                "name": record["name"] or record["display_name"],
                "display_name": record["display_name"],
                "label": record["label"],
                "connections": record["connections"]
            })
    
    return candidates


# ==========================================
# 2. LOCAL CONTEXT EXTRACTION
# ==========================================
def extract_local_context(driver, node_id: str) -> Dict[str, Any]:
    """
    Extract rich context from the graph for a given node.
    Returns file types, tags, co-occurring entities, and filenames.
    """
    query = """
    MATCH (n) WHERE elementId(n) = $node_id
    
    // Connected assets + relationship types
    MATCH (n)<-[r]-(asset:DigitalAsset)
    
    WITH n, 
         collect(distinct {type: type(r), reasoning: r.reasoning, weight: r.weight}) as relations_detailed,
         collect(distinct asset.mime_type)[..5] as file_types,
         collect(distinct asset.file_hash)[..8] as file_hashes,
         count(distinct asset) as total_connections
    
    // Co-occurring entities (entities that share assets with this node)
    OPTIONAL MATCH (n)<-[]-(shared_asset:DigitalAsset)-[]->(sibling)
    WHERE sibling <> n 
      AND (sibling:Person OR sibling:Concept OR sibling:Organization OR sibling:Event OR sibling:Project)
    
    WITH n, relations_detailed, file_types, file_hashes, total_connections,
         collect(distinct {name: sibling.name, label: labels(sibling)[0]})[..10] as co_entities
    
    // Tags from connected assets
    OPTIONAL MATCH (n)<-[]-(tagged_asset:DigitalAsset)
    WHERE tagged_asset.tags IS NOT NULL
    
    RETURN
        n.name as name,
        total_connections,
        relations_detailed,
        file_types,
        file_hashes,
        co_entities,
        collect(distinct tagged_asset.tags)[..3] as tag_groups
    """
    
    with driver.session() as session:
        result = session.run(query, node_id=node_id)
        record = result.single()
        
        if not record:
            return {"error": "Node not found"}
        
        # Flatten tag groups
        all_tags = set()
        for tag_group in record["tag_groups"]:
            if tag_group:
                all_tags.update(tag_group)
        
        # Categorize file types
        ftypes = [t for t in record["file_types"] if t]
        media_categories = set()
        for ft in ftypes:
            if "audio" in ft: media_categories.add("Audio")
            elif "image" in ft: media_categories.add("Image")
            elif "text" in ft or "pdf" in ft: media_categories.add("Text")
            elif "video" in ft: media_categories.add("Video")
            else: media_categories.add(ft)
        
        return {
            "name": record["name"],
            "total_connections": record["total_connections"],
            "relations_detailed": record["relations_detailed"],
            "media_categories": list(media_categories),
            "file_types": ftypes,
            "file_hashes": [h for h in record["file_hashes"] if h],
            "co_entities": [e for e in record["co_entities"] if e.get("name")],
            "tags": list(all_tags)
        }


# ==========================================
# 3. EXTERNAL GROUNDING (WIKIPEDIA)
# ==========================================
def fetch_wikipedia_summary(name: str) -> Optional[str]:
    """
    Fetch Wikipedia summary for a term.
    Returns summary text or None.
    """
    if not HAS_WIKIPEDIA:
        logger.warning("   ⚠️  wikipedia lib not installed. Run: pip install wikipedia")
        return None
    
    try:
        # Try exact match first
        page = wikipedia.page(name, auto_suggest=True)
        summary = page.summary[:1500]  # Cap at 1500 chars
        logger.info(f"   📚 Wikipedia: Found '{page.title}' ({len(summary)} chars)")
        return summary
    except wikipedia.exceptions.DisambiguationError as e:
        # Try first option
        try:
            first_option = e.options[0]
            page = wikipedia.page(first_option)
            summary = page.summary[:1500]
            logger.info(f"   📚 Wikipedia (disambig -> '{first_option}'): {len(summary)} chars")
            return summary
        except Exception:
            logger.warning(f"   ⚠️  Wikipedia disambiguation failed for '{name}'")
            return None
    except wikipedia.exceptions.PageError:
        logger.warning(f"   ⚠️  Wikipedia: No page for '{name}'")
        return None
    except Exception as e:
        logger.warning(f"   ⚠️  Wikipedia error: {e}")
        return None


# ==========================================
# 4. LLM ONTOLOGICAL ANALYSIS
# ==========================================
def call_enrichment_llm(
    entity_name: str,
    entity_label: str,
    local_context: Dict[str, Any],
    wiki_summary: Optional[str]
) -> Optional[Dict[str, Any]]:
    """
    Call LLM to generate a fused semantic profile.
    """
    # Build the user message with both sources
    user_content = f"""ENTIDAD A ENRIQUECER: "{entity_name}" (Tipo actual: {entity_label})

=== Grounding_Source (Wikipedia) ===
{wiki_summary if wiki_summary else "No se encontró en Wikipedia. Usa solo el contexto local."}

=== Relevance_Source (Grafo Local) ===
- Conexiones totales: {local_context.get('total_connections', 0)}
- Categorías de archivos conectados: {local_context.get('media_categories', [])}
- Relaciones detalladas en el grafo (con reasoning y peso): {json.dumps(local_context.get('relations_detailed', []), ensure_ascii=False)}
- Tags co-ocurrentes: {local_context.get('tags', [])[:10]}
- Entidades que co-ocurren: {json.dumps([e.get('name', '') for e in local_context.get('co_entities', [])[:8]], ensure_ascii=False)}

Genera el Perfil Sidecar JSON fusionando ambas fuentes. SOLO JSON, sin texto adicional."""

    messages = [
        {"role": "system", "content": ENRICHMENT_SYSTEM_PROMPT},
        {"role": "user", "content": user_content}
    ]
    
    url = f"{LLM_GATEWAY_BASE_URL}/chat/completions"
    data = {
        "task": "chat",
        "privacy_mode": "flexible",
        "messages": json.dumps(messages),
        "temperature": 0.5,
        "response_format": json.dumps({"type": "json_object"})
    }
    
    try:
        logger.info(f"   🤖 Calling LLM Gateway ({url})...")
        response = requests.post(url, data=data, timeout=120)
        
        if response.status_code != 200:
            logger.error(f"   ❌ LLM returned {response.status_code}: {response.text[:200]}")
            return None
        
        result = response.json()
        llm_text = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        # Extract JSON from response (handle markdown wrapping)
        llm_text = llm_text.strip()
        if llm_text.startswith("```"):
            # Remove markdown code blocks
            llm_text = re.sub(r'^```(?:json)?\s*', '', llm_text)
            llm_text = re.sub(r'\s*```$', '', llm_text)
        
        parsed = json.loads(llm_text)
        logger.info(f"   ✅ LLM returned profile with {len(parsed.get('graph_relations', []))} relations")
        return parsed
        
    except json.JSONDecodeError as e:
        logger.error(f"   ❌ Failed to parse LLM JSON: {e}")
        logger.debug(f"   Raw: {llm_text[:300]}")
        return None
    except requests.exceptions.ConnectionError:
        logger.error(f"   ❌ Cannot connect to LLM Gateway. Is it running?")
        return None
    except Exception as e:
        logger.error(f"   ❌ LLM call failed: {e}")
        return None


# ==========================================
# 5. PERSISTENCE
# ==========================================
def slugify(text: str) -> str:
    """Create a filesystem-safe slug from text."""
    text = text.lower().strip()
    text = re.sub(r'[áàäâ]', 'a', text)
    text = re.sub(r'[éèëê]', 'e', text)
    text = re.sub(r'[íìïî]', 'i', text)
    text = re.sub(r'[óòöô]', 'o', text)
    text = re.sub(r'[úùüû]', 'u', text)
    text = re.sub(r'[ñ]', 'n', text)
    text = re.sub(r'[^a-z0-9]+', '_', text)
    text = text.strip('_')
    return text[:80]


def persist_enrichment(
    driver,
    minio_client,
    node_id: str,
    entity_name: str,
    entity_label: str,
    profile: Dict[str, Any],
    local_context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Persist enrichment results to:
    A. Neo4j (graph knowledge)
    B. MinIO sidecar JSON (vectorization)
    C. SQL (Asset + VectorStatus for TEXT_CHUNK embedding worker)
    """
    results = {"graph_updates": 0, "sidecar_path": None, "relations_created": 0, "asset_id": None}
    canonical = profile.get("canonical_name", entity_name)
    
    # Lazy imports - bypass shared.database and app.__init__ to avoid circular import:
    #   shared.database -> app.models -> app.__init__ -> shared.database
    from sqlmodel import Session, select, create_engine
    from app.models.asset import Asset
    from app.models.vector_status import VectorStatus
    from app.models.enums import JobStatus, VectorType
    _engine = create_engine(settings.DATABASE_URL, echo=False)
    
    # --------------------------------------------------------
    # A. NEO4J: Update node properties + create relations
    # --------------------------------------------------------
    with driver.session() as session:
        # Update the node itself
        update_query = """
        MATCH (n) WHERE elementId(n) = $node_id
        SET n.enriched = true,
            n.enriched_at = datetime(),
            n.canonical_name = $canonical_name,
            n.short_bio = $short_bio,
            n.text_for_embedding = $text_for_embedding,
            n.mood = $mood,
            n.entity_type_refined = $entity_type
        RETURN n.name as name
        """
        
        # Support both prompt schemas: metadata.* or sidecar_data.*
        metadata = profile.get("metadata", profile.get("sidecar_data", {}))
        session.run(update_query,
            node_id=node_id,
            canonical_name=canonical,
            short_bio=metadata.get("short_bio", ""),
            text_for_embedding=profile.get("text_for_embedding", ""),
            mood=metadata.get("mood", metadata.get("emotional_atmosphere", [])),
            entity_type=profile.get("entity_type", entity_label)
        )
        results["graph_updates"] += 1
        
        # Create fuzzy relations from LLM
        # Support both schemas: graph_relations[] or sidecar_data.fuzzy_concepts[]
        fuzzy_rels = profile.get("graph_relations", [])
        if not fuzzy_rels:
            sidecar_data = profile.get("sidecar_data", {})
            fuzzy_rels = sidecar_data.get("fuzzy_concepts", [])
        
        for rel in fuzzy_rels:
            target_name = rel.get("target_name", rel.get("name", "")).strip()
            if not target_name:
                continue
            
            rel_type = rel.get("relation", rel.get("relation_type", "EVOKES")).upper().replace(" ", "_")
            if rel_type not in ALLOWED_ENRICHMENT_RELATIONS:
                logger.warning(f"      ⚠️ Skipping unknown relation '{rel_type}'")
                continue
            
            target_type = rel.get("target_type", "Concept")
            weight = min(max(float(rel.get("weight", 0.5)), 0.0), 1.0)
            reasoning = rel.get("reasoning", "")
            
            # MERGE target node (could be new or existing)
            rel_query = f"""
            MATCH (source) WHERE elementId(source) = $node_id
            MERGE (target:{target_type} {{name: $target_name}})
            ON CREATE SET target.created_at = datetime(), target.source = 'enrichment'
            MERGE (source)-[r:{rel_type}]->(target)
            ON CREATE SET 
                r.weight = $weight,
                r.reasoning = $reasoning,
                r.created_at = datetime(),
                r.source = 'enrichment_llm'
            ON MATCH SET
                r.weight = CASE WHEN $weight > r.weight THEN $weight ELSE r.weight END
            """
            
            try:
                session.run(rel_query,
                    node_id=node_id,
                    target_name=target_name,
                    weight=weight,
                    reasoning=reasoning
                )
                results["relations_created"] += 1
                logger.info(f"      🔗 {canonical} -[{rel_type} {weight:.1f}]-> {target_name}")
            except Exception as e:
                logger.warning(f"      ⚠️ Failed to create relation: {e}")
    
    # --------------------------------------------------------
    # B. MINIO: Save text content + sidecar JSON
    # --------------------------------------------------------
    text_for_embedding = profile.get("text_for_embedding", "")
    text_bytes = text_for_embedding.encode("utf-8")
    content_hash = hashlib.sha256(text_bytes).hexdigest()
    slug = slugify(canonical)
    
    # B.1 Save the raw text (what TEXT_CHUNK worker will read)
    text_key = f"master_records/texts/{content_hash}.txt"
    try:
        minio_client.put_object(
            Bucket=MINIO_BUCKET,
            Key=text_key,
            Body=text_bytes,
            ContentType="text/plain; charset=utf-8"
        )
        logger.info(f"   📝 Text saved: {text_key} ({len(text_bytes)} bytes)")
    except Exception as e:
        logger.error(f"   ❌ Failed to save text to MinIO: {e}")
        return results
    
    # B.2 Save the sidecar JSON
    sidecar_key = f"master_records/sidecars/{content_hash}.json"
    
    sidecar_doc = {
        "file_hash": content_hash,
        "original_filename": f"enrichment_{slug}.txt",
        "mime_type": "text/plain",
        "size_bytes": len(text_bytes),
        "upload_timestamp": datetime.utcnow().isoformat(),
        "operation": "enrichment_ingest",
        "sidecar_type": "enrichment_profile",
        "source_node_id": node_id,
        "entity_name": canonical,
        "entity_type": profile.get("entity_type", entity_label),
        "text_for_embedding": text_for_embedding,
        "graph_relations": fuzzy_rels,
        "metadata": metadata,
        "local_context_snapshot": {
            "media_categories": local_context.get("media_categories", []),
            "total_connections": local_context.get("total_connections", 0),
            "co_entities": [e.get("name") for e in local_context.get("co_entities", [])],
            "tags": local_context.get("tags", [])
        },
        "vector_types": [VectorType.TEXT_SUMMARY.value, VectorType.TEXT_CHUNK.value],
        "privacy_config": {"level": "strict_local", "locked": False},
        "workflow_state": {
            "steps_completed": ["enrichment_approved", "text_summary_completed"],
            "current_status": JobStatus.ON_HOLD.value
        },
        "data_layers": {
            "text_summary_analysis": profile,  # The enrichment IS the text summary
            "analysis_json": profile,
            "intermediate_results": {}
        }
    }
    
    try:
        sidecar_bytes = json.dumps(sidecar_doc, ensure_ascii=False, indent=2).encode("utf-8")
        minio_client.put_object(
            Bucket=MINIO_BUCKET,
            Key=sidecar_key,
            Body=sidecar_bytes,
            ContentType="application/json"
        )
        results["sidecar_path"] = sidecar_key
        logger.info(f"   💾 Sidecar saved: {sidecar_key}")
    except Exception as e:
        logger.error(f"   ❌ Failed to save sidecar to MinIO: {e}")
        return results
    
    # --------------------------------------------------------
    # C. SQL: Register Asset + VectorStatuses
    #    - TEXT_SUMMARY → COMPLETED (the enrichment LLM analysis IS the summary)
    #    - TEXT_CHUNK   → ON_HOLD   (ready for embedding worker dispatch)
    #
    # NOTE: The dispatcher blocks TEXT_CHUNK unless TEXT_SUMMARY is COMPLETED.
    #        Since the enrichment analysis already produced the summary, we mark
    #        TEXT_SUMMARY as pre-completed to satisfy this prerequisite.
    # --------------------------------------------------------
    try:
        with Session(_engine) as sql_session:
            # Check for duplicate (idempotent)
            existing = sql_session.exec(
                select(Asset).where(Asset.file_hash == content_hash)
            ).first()
            
            if existing:
                logger.info(f"   ℹ️  Asset already exists (hash: {content_hash[:12]}...), skipping SQL")
                results["asset_id"] = str(existing.id)
            else:
                # Create Asset record
                asset = Asset(
                    filename=f"enrichment_{slug}.txt",
                    minio_path=text_key,
                    mime_type="text/plain",
                    size_bytes=len(text_bytes),
                    file_hash=content_hash,
                    is_merged=False,
                    original_deleted=False,
                    privacy_level="strict_local",
                    sidecar_path=sidecar_key
                )
                sql_session.add(asset)
                sql_session.commit()
                sql_session.refresh(asset)
                
                # 1. TEXT_SUMMARY → COMPLETED (enrichment LLM = text summary)
                vs_summary = VectorStatus(
                    asset_id=asset.id,
                    vector_type=VectorType.TEXT_SUMMARY,
                    status=JobStatus.COMPLETED
                )
                sql_session.add(vs_summary)
                
                # 2. TEXT_CHUNK → ON_HOLD (ready for dispatch)
                vs_chunk = VectorStatus(
                    asset_id=asset.id,
                    vector_type=VectorType.TEXT_CHUNK,
                    status=JobStatus.ON_HOLD
                )
                sql_session.add(vs_chunk)
                sql_session.commit()
                
                results["asset_id"] = str(asset.id)
                logger.info(f"   🗄️  SQL registered: Asset {asset.id}")
                logger.info(f"       → TEXT_SUMMARY: COMPLETED (enrichment analysis)")
                logger.info(f"       → TEXT_CHUNK:   ON_HOLD   (ready for dispatch)")
    except Exception as e:
        logger.error(f"   ❌ SQL registration failed: {e}")
    
    return results


# ==========================================
# 6. DISPLAY HELPERS
# ==========================================
def display_candidate(idx: int, candidate: Dict, context: Dict, wiki: Optional[str]):
    """Pretty-print candidate info for human review."""
    print(f"\n{'='*70}")
    print(f"  [{idx}] {candidate['display_name']}  ({candidate['label']}, {candidate['connections']} conexiones)")
    print(f"{'='*70}")
    
    if context.get("media_categories"):
        print(f"  📂 Media: {', '.join(context['media_categories'])}")
    
    if context.get("filenames"):
        print(f"  📄 Archivos: {', '.join(context['filenames'][:4])}")
    
    if context.get("tags"):
        print(f"  🏷️  Tags: {', '.join(list(context['tags'])[:8])}")
    
    if context.get("co_entities"):
        co_names = [e.get("name", "") for e in context["co_entities"][:6]]
        print(f"  🔗 Co-occurs: {', '.join(co_names)}")
    
    if wiki:
        print(f"  📚 Wikipedia: {wiki[:200]}...")
    else:
        print(f"  📚 Wikipedia: (no encontrado)")


def display_profile(profile: Dict):
    """Pretty-print LLM-generated profile for approval."""
    print(f"\n  --- PERFIL GENERADO ---")
    print(f"  Nombre canónico: {profile.get('canonical_name', '?')}")
    print(f"  Tipo: {profile.get('entity_type', '?')}")
    
    bio = profile.get("metadata", {}).get("short_bio", "")
    if bio:
        print(f"  Bio: {bio[:150]}")
    
    mood = profile.get("metadata", {}).get("mood", [])
    if mood:
        print(f"  Mood: {', '.join(mood)}")
    
    embedding_text = profile.get("text_for_embedding", "")
    if embedding_text:
        print(f"  Embedding text ({len(embedding_text.split())} words): {embedding_text[:200]}...")
    
    relations = profile.get("graph_relations", [])
    if relations:
        print(f"  Relaciones ({len(relations)}):")
        for r in relations[:6]:
            print(f"    → {r.get('relation', '?')} [{r.get('weight', 0):.1f}] -> {r.get('target_name', '?')} ({r.get('target_type', '?')})")
            if r.get("reasoning"):
                print(f"      Razón: {r['reasoning'][:80]}")


# ==========================================
# MAIN FLOW
# ==========================================
def main():
    parser = argparse.ArgumentParser(description="Enrichment pipeline with Human-in-the-Loop approval")
    parser.add_argument("--limit", type=int, default=10, help="Max candidates to process")
    parser.add_argument("--auto", action="store_true", help="Auto-approve all (skip human review)")
    args = parser.parse_args()
    
    print("\n🧠 ENRICHMENT PIPELINE v2.0 - Human-in-the-Loop")
    print("=" * 50)
    
    # --- Connection checks ---
    try:
        driver = get_neo4j_driver()
        with driver.session() as s:
            s.run("RETURN 1").single()
        print("✅ Neo4j connected")
    except Exception as e:
        print(f"❌ Neo4j connection failed: {e}")
        return
    
    try:
        minio_client = get_minio_client()
        minio_client.head_bucket(Bucket=MINIO_BUCKET)
        print(f"✅ MinIO connected (bucket: {MINIO_BUCKET})")
    except Exception as e:
        print(f"❌ MinIO connection failed: {e}")
        return
    
    if not HAS_WIKIPEDIA:
        print("⚠️  wikipedia lib not installed — external grounding disabled")
        print("   Install with: poetry add wikipedia")
    
    # --- 1. Find candidates ---
    print(f"\n🔍 Buscando candidatos (límite: {args.limit})...")
    candidates = find_candidates(driver, limit=args.limit)
    
    if not candidates:
        print("✅ No hay candidatos pendientes de enriquecimiento.")
        return
    
    print(f"📋 Encontrados {len(candidates)} candidatos:\n")
    for i, c in enumerate(candidates, 1):
        print(f"   {i}. {c['display_name']} ({c['label']}, {c['connections']} conex.)")
    
    # --- Process each candidate ---
    stats = {"processed": 0, "approved": 0, "skipped": 0, "errors": 0}
    
    for i, candidate in enumerate(candidates, 1):
        name = candidate["name"]
        node_id = candidate["node_id"]
        
        # 2. Local context
        print(f"\n{'─'*50}")
        print(f"[{i}/{len(candidates)}] Procesando: {name}")
        context = extract_local_context(driver, node_id)
        
        if context.get("error"):
            logger.error(f"   ❌ {context['error']}")
            stats["errors"] += 1
            continue
        
        # 3. External grounding
        wiki_summary = fetch_wikipedia_summary(name)
        
        # Display for human
        display_candidate(i, candidate, context, wiki_summary)
        
        # 4. LLM analysis
        profile = call_enrichment_llm(name, candidate["label"], context, wiki_summary)
        
        if not profile:
            print("   ❌ LLM no generó perfil. Saltando...")
            stats["errors"] += 1
            continue
        
        # Display profile for review
        display_profile(profile)
        
        # 5. Human approval
        if args.auto:
            approved = True
            print("   ✅ Auto-aprobado (--auto)")
        else:
            try:
                choice = input("\n  ¿Aprobar? [y/n/q(uit)] > ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\n\n⚠️ Interrumpido por el usuario.")
                break
            
            if choice == 'q':
                print("\n⚠️ Terminado por el usuario.")
                break
            approved = choice in ('y', 'yes', 's', 'si', 'sí')
        
        if not approved:
            print("   ⏭️  Saltado")
            stats["skipped"] += 1
            continue
        
        # 6. Persist
        try:
            result = persist_enrichment(
                driver, minio_client,
                node_id, name, candidate["label"],
                profile, context
            )
            stats["approved"] += 1
            stats["processed"] += 1
            print(f"   ✅ Guardado: {result['graph_updates']} props, {result['relations_created']} rels, sidecar: {result.get('sidecar_path', 'N/A')}")
        except Exception as e:
            logger.error(f"   ❌ Persistence failed: {e}")
            stats["errors"] += 1
    
    # --- Summary ---
    print(f"\n{'='*50}")
    print(f"✅ ENRICHMENT COMPLETADO")
    print(f"   Procesados: {stats['processed']}")
    print(f"   Aprobados:  {stats['approved']}")
    print(f"   Saltados:   {stats['skipped']}")
    print(f"   Errores:    {stats['errors']}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
