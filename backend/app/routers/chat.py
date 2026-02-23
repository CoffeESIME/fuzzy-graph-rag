from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import logging
import json

from shared.database import get_session
from sqlmodel import Session
from app.routers.search import SearchResultItem
from shared.clients import get_weaviate_client
from config.settings import get_settings
import requests

settings = get_settings()
LLM_GATEWAY_URL = settings.LLM_GATEWAY_URL

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/chat",
    tags=["chat"]
)

# --- Request Models ---

class RAGConfig(BaseModel):
    model: str = Field("local", description="Model choice: 'local' (Edge) or 'cloud' (Advanced)")
    privacy_mode: bool = Field(False, description="If True, do not log or store this query")
    strategy: str = Field("hibrido_total", description="Context strategy: baseline_vectorial, hibrido_estandar, difuso_puro, hibrido_total")
    top_n: int = Field(5, description="Number of documents to use (total for global, per column for blended)")

class SynthesizeRequest(BaseModel):
    query: str = Field(..., description="User's original query")
    config: RAGConfig
    # Arrays of results from the comparison tab
    vector_results: List[Dict[str, Any]] = []
    crisp_results: List[Dict[str, Any]] = []
    normal_results: List[Dict[str, Any]] = []
    fuzzy_results: List[Dict[str, Any]] = []

class SynthesizeResponse(BaseModel):
    answer: str
    sources_used: List[str]
    is_private: bool

# --- Helpers ---

def deduplicate_results(req: SynthesizeRequest) -> List[Dict[str, Any]]:
    """
    Deduplicates results based on the chosen strategy.
    Returns a list of result dictionaries with unique file_hashes.
    """
    seen_hashes = set()
    final_list = []
    
    def add_unique(item_list, limit=None):
        added = 0
        for item in item_list:
            if limit is not None and added >= limit:
                break
            
            # Extract hash fallback (graph uses properties.file_hash usually, vector uses properties or uuid)
            props = item.get("properties", {})
            file_hash = props.get("file_hash") or props.get("neo4j_hash") or props.get("hash") or item.get("uuid") or item.get("id")
            
            if not file_hash or file_hash in seen_hashes:
                continue
                
            seen_hashes.add(file_hash)
            final_list.append(item)
            added += 1

    if req.config.strategy == "baseline_vectorial":
        add_unique(req.vector_results, req.config.top_n)
        
    elif req.config.strategy == "hibrido_estandar":
        # Combines Weaviate and Crisp Neo4j
        add_unique(req.vector_results, req.config.top_n)
        add_unique(req.crisp_results, req.config.top_n)
        
    elif req.config.strategy == "difuso_puro":
        # Purely Graph-based retrieval
        add_unique(req.crisp_results, req.config.top_n)
        add_unique(req.normal_results, req.config.top_n)
        add_unique(req.fuzzy_results, req.config.top_n)
        
    else: # "hibrido_total" or anything else
        # Blended: Take Top N from each column (Fair Representation)
        limit = req.config.top_n
        add_unique(req.crisp_results, limit)
        add_unique(req.normal_results, limit)
        add_unique(req.vector_results, limit)
        add_unique(req.fuzzy_results, limit)
        
    return final_list

def extract_sidecar_context(item: Dict[str, Any]) -> str:
    """
    Extracts the most relevant context text based on the item's space and search origin.
    Handles both Weaviate (Vector) and Neo4j (Graph) structures.
    """
    props = item.get("properties", {})
    space = item.get("space", props.get("space", "UnknownSpace"))
    filename = props.get("filename") or item.get("filename") or item.get("id", "Unknown File")
    
    # Check multiple possible locations for text content (Vector vs Graph schemas)
    content = (
        props.get("text") or 
        props.get("content") or 
        item.get("text") or
        item.get("content") or
        props.get("ai_summary") or 
        props.get("description") or 
        props.get("description_ai") or
        props.get("ocr_text") or
        props.get("transcript") or
        props.get("lyrics_summary") or 
        ""
    )
    
    # Fallback: If content is still empty (common for Graph-only results), fetch directly from MinIO sidecar
    if not content:
        file_hash = props.get("hash") or props.get("file_hash") or item.get("uuid") or item.get("id")
        # Neo4j Graph Topology ids are typically the hash if we used file_hash as elementId/id.
        if file_hash:
            try:
                from shared.clients import get_minio_client
                minio_client = get_minio_client()
                bucket = settings.MINIO_BUCKET if hasattr(settings, 'MINIO_BUCKET') else "rag-dataset"
                
                # Check if file_hash looks like a hex string hash to avoid querying native Neo4j elementIds if they leaked
                sidecar_path = f"master_records/sidecars/{file_hash}.json"
                response = minio_client.get_object(Bucket=bucket, Key=sidecar_path)
                sidecar_data = json.loads(response['Body'].read().decode('utf-8'))
                
                data_layers = sidecar_data.get('data_layers', {})
                analysis_json = (
                    data_layers.get('analysis_json') or 
                    data_layers.get('raw_debug_data', {}).get('visual_semantic_json') or 
                    data_layers.get('raw_debug_data', {}).get('memory_analysis_json') or 
                    data_layers.get('text_summary_analysis') or 
                    data_layers.get('raw_debug_data', {}).get('text_analysis_json') or 
                    {}
                )
                
                # Try to extract audio transcript / lyrics
                audio_spec = analysis_json.get("audio_specifics", {})
                transcript = data_layers.get('intermediate_results', {}).get('audio_transcript', '')
                lyrics = audio_spec.get('lyrics_summary', '')
                
                # Try to extract image OCR
                ocr = analysis_json.get('visual_specifics', {}).get('ocr_text', '')
                
                content = (
                    sidecar_data.get("text") or 
                    transcript or 
                    lyrics or 
                    ocr or 
                    analysis_json.get('graph_core', {}).get('summary') or
                    str(analysis_json)
                )
            except Exception as e:
                logger.debug(f"Could not fetch sidecar fallback for {file_hash}: {e}")
                
    # If the search result has a specific matched concept from the Knowledge Graph, inject it into the context
    kg_context = ""
    matched_concept = item.get("matched_concept")
    relation_type = item.get("relation_type")
    
    if matched_concept and relation_type:
        kg_context = f"\n[Graph Relation: Este archivo tiene una relación de tipo '{relation_type}' con el concepto '{matched_concept}']\n"
        
    # Truncate if insanely long (just in case)
    if len(content) > 3000:
        content = content[:3000] + "..."
        
    return f"📄 [Archivo: {filename} | Tipo: {space}]{kg_context}\n{content}"

# --- Endpoints ---

@router.post("/synthesize", response_model=SynthesizeResponse)
async def synthesize_comparison(
    req: SynthesizeRequest,
    session: Session = Depends(get_session)
):
    """
    RAG Synthesis Endpoint with full User Control.
    Takes search results, extracts context, and generates an LLM response.
    """
    if not req.config.privacy_mode:
        logger.info(f"Synthesizing RAG response for query: '{req.query}'")
        logger.info(f"Config: {req.config.model_dump()}")
    else:
        logger.info("[Incognito Mode] Processing private RAG synthesis request.")
        
    try:
        # 1. Deduplicate and trim results based on strategy
        selected_results = deduplicate_results(req)
        
        # 2. Extract context from sidecards
        contexts = []
        sources = []
        for item in selected_results:
            context_string = extract_sidecar_context(item)
            if context_string.strip():
                contexts.append(context_string)
                props = item.get("properties", {})
                filename = props.get("filename") or item.get("filename") or item.get("id", "Unknown")
                sources.append(filename)
                
        # 3. Build Prompt
        joined_context = "\n\n---\n\n".join(contexts)
        
        system_prompt = f"""Eres un Second Brain AI y asistente de investigación.
Usa estrictamente la información provista en la sección de <CONTEXTO> para responder a la <PREGUNTA> del usuario.
Si la respuesta no está en el contexto, dilo claramente.
Cita siempre tus fuentes referenciando el '[Archivo: ...]' del cual provino la información.

<CONTEXTO>
{joined_context}
</CONTEXTO>
"""
        
        user_prompt = f"<PREGUNTA>\n{req.query}\n</PREGUNTA>"
        
        # 4. Route to Model
        provider = "local" if req.config.model == "local" else "openai"  # or whatever your cloud logic dictactes
        model_name = "llama3:8b" if provider == "local" else "gpt-4o-mini"
        
        # Note: If privacy_mode is true, we ONLY call the LLM and return.
        # We explicitly avoid saving this to Inbox, ChatHistory, or Neo4j.
        
        logger.info(f"Calling LLM Gateway ({provider} / {model_name}) with {len(sources)} sources.")
        
        url = f"{LLM_GATEWAY_URL}/v1/chat/completions"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        data = {
            "task": "chat",
            "privacy_mode": "strict" if req.config.privacy_mode else "flexible",
            "messages": json.dumps(messages),
            "temperature": 0.5,
            "provider": provider,
            "max_tokens": 1500
        }
        
        response = requests.post(url, data=data, timeout=120)
        
        if response.status_code == 200:
            result = response.json()
            answer = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            if not answer:
                answer = "Error: El modelo de lenguaje devolvió una respuesta vacía."
        else:
            answer = f"Error del LLM Gateway: HTTP {response.status_code} - {response.text}"
            
        return SynthesizeResponse(
            answer=answer,
            sources_used=sources,
            is_private=req.config.privacy_mode
        )
        
    except Exception as e:
        logger.error(f"Error in synthesize: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
