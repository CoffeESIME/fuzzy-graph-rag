"""
GraphRAG Prompt Generator
=========================
Generates specialized system prompts for LLM extraction tasks (Vision, Audio, Text).
Features:
- Modular JSON Schemas per media type.
- Fuzzy Logic (Confidence Scores).
- Nuance-Aware Context Injection (Interprets user uncertainty).
- Bilingual Structure (English Keys / Spanish Values).
"""

import json
from typing import Optional, Dict, Any, List


def build_specialized_prompt(
    task_type: str,  # "vision", "audio", "text"
    external_context: Optional[Dict[str, Any]] = None,
    existing_taxonomies: Optional[Dict[str, List[str]]] = None
) -> str:
    """
    Builds the system prompt for the LLM Gateway.
    
    Args:
        task_type: One of "vision", "audio", "text"
        external_context: User-provided context (notes, descriptions)
        existing_taxonomies: Existing concept types/domains from the graph
        
    Returns:
        Complete system prompt for the LLM
    """

    # ==========================================
    # 1. TAXONOMY HINTS (Reuse existing types)
    # ==========================================
    taxonomy_hint = ""
    if existing_taxonomies:
        types = ", ".join(f"'{t}'" for t in existing_taxonomies.get('concept_types', []))
        domains = ", ".join(f"'{d}'" for d in existing_taxonomies.get('domains', []))
        taxonomy_hint = f"SUGGESTED TAXONOMY (Prioritize these if applicable): Types=[{types}], Domains=[{domains}]"

    # ==========================================
    # 2. SCHEMA DEFINITIONS (Target JSONs)
    # ==========================================
    
    # Base structure for Fuzzy Concepts
    concept_structure = {
        "name": "Nombre del Concepto (Español)",
        "type": "Micro-Category (English preferred, e.g., 'Genre', 'Emotion')",
        "domain": "Macro-Area (English preferred, e.g., 'Arts', 'Math')",
        "definition": "Breve contexto para desambiguar",
        "confidence": "<float 0.0-1.0>"
        "reasoning": "Breve explicación de por qué se eligió este concepto y esta confianza (Español)"
    }

    # Core Graph Data (Neo4j Nodes)
    graph_core = {
        "summary": "Dense description (Spanish)",
        "entities": {
            "persons": [{"name": "Name", "role": "Role", "confidence": "<float 0.0-1.0>"}],
            "locations": [{"name": "Name", "type": "Type", "confidence": "<float 0.0-1.0>"}],
            "organizations": [{"name": "Org Name", "confidence": "<float 0.0-1.0>"}],
            "concepts": [concept_structure]
        },
        "tags": ["keyword1", "keyword2"]
    }

    # Specific Metadata per Type
    schemas = {
        "vision": {
            "graph_core": graph_core,
            "visual_specifics": {
                "image_type": "photography | meme | art | screenshot | diagram",
                "composition": "Rule of thirds, Close-up...",
                "lighting": "Hard light, Neon, Golden hour...",
                "dominant_colors": ["Hex Code OR Name (Ordered by dominance)"],
                "art_style": "Visual style (e.g. Cyberpunk, Baroque)",
                "ocr_text": "Literal text found in image (or null)",
                "visual_mood": "Perceived atmosphere"
            }
        },
        "audio": {
            "graph_core": graph_core,
            "audio_specifics": {
                "audio_type": "song | speech | sound_effect | instrumental",
                "genre": "Género musical o tipo de charla",
                "tempo": "BPM estimado o descripción (Lento/Rápido)",
                "instruments": ["Lista de instrumentos (Ordenada por prominencia)"],
                "lyrics_summary": "Tema de la letra o null",
                "emotional_tone": "Sentimiento percibido"
            }
        },
        "text": {
            "graph_core": graph_core,
            "text_specifics": {
                "document_type": "article | quote | personal_note | code | receipt",
                "rhetorical_tone": "Académico, Sarcástico, Informal...",
                "key_arguments": ["Puntos principales"],
                "language": "ISO Code (es, en, fr...)",
                "requires_action": True  # bool
            }
        }
    }

    target_schema = schemas.get(task_type, schemas["text"])

    # ==========================================
    # 3. FEW-SHOT EXAMPLES SELECTION
    # ==========================================
    if task_type == "vision":
        examples_str = _get_vision_examples()
    elif task_type == "audio":
        examples_str = _get_audio_examples()
    else:
        examples_str = _get_text_examples()

    # ==========================================
    # 4. NUANCE-AWARE CONTEXT INSTRUCTION
    # ==========================================
    context_instruction = ""
    if external_context:
        context_instruction = f"""
CRITICAL: USER CONTEXT ANALYSIS (NUANCE-AWARE):
The user has provided descriptions/metadata: {json.dumps(external_context, indent=2, ensure_ascii=False)}

RULES FOR INTERPRETING USER CONTEXT:
1. **Detect Qualifiers & Confidence:** Do NOT blindly assign confidence 1.0. Analyze tone:
   - "Definitely", "Always", "I love" -> Confidence 0.95 - 1.0
   - "Very marked", "Strong influence" -> Confidence 0.8 - 0.9
   - "A bit like", "Reminds me of", "Maybe", "Sounds like" -> Confidence 0.4 - 0.6

2. **Mixed Concepts:** If the user describes a mix (e.g., "Mexican Folk with Heavy Metal"), extract BOTH concepts separately with their respective confidence levels inferred from the description.

3. **Arrays as Distributions:** For fields like 'dominant_colors', 'genres', or 'instruments':
   - ORDER MATTERS. Place the most dominant/prominent elements FIRST.
   - Example: "Mucho amarillo, menos café" -> ["Yellow", "Brown"].
"""

    # ==========================================
    # 5. FINAL PROMPT ASSEMBLY
    # ==========================================
    prompt = f"""You are a GraphRAG Data Extractor.
Analyze the {task_type.upper()} input and output a valid JSON.

LANGUAGE & FORMAT RULES (STRICT):
1. **JSON KEYS:** Must be strictly **ENGLISH**.
2. **STRUCTURAL VALUES (Types/Domains):** Must be **ENGLISH** (Standardized Taxonomy).
   - BAD: "type": "Sentimiento", "domain": "Psicología"
   - GOOD: "type": "Sentiment", "domain": "Psychology"
3. **CONTENT VALUES (Names, Descriptions, Summaries):** Must be **SPANISH** (or original language).
   - This allows you to capture the nuance of the user's native language.
OUTPUT SCHEMA (Follow this structure exactly):
{json.dumps(target_schema, indent=2)}

{taxonomy_hint}

{context_instruction}

FEW-SHOT EXAMPLES (Reference for logic, not content):
{examples_str}

Analyze the input and return ONLY the JSON object, no additional text."""

    return prompt


# ==========================================
# HELPER: FEW-SHOT EXAMPLES (2-Shots per Type)
# ==========================================

def _get_vision_examples() -> str:
    """Get few-shot examples for vision analysis."""
    # Case 1: Complex/Rich Image
    ex1 = {
        "graph_core": {
            "summary": "Retrato cinemático de un anciano fumando en una calle oscura.",
            "entities": {
                "persons": [],
                "concepts": [
                    {"name": "Soledad", "type": "Emotion", "domain": "Psychology", "definition": "Aislamiento visual", "confidence": 0.9},
                    {"name": "Film Noir", "type": "Style", "domain": "Arts", "definition": "Estilo visual oscuro y contrastado", "confidence": 0.95}
                ]
            },
            "tags": ["bw", "smoke", "portrait", "night"]
        },
        "visual_specifics": {
            "image_type": "photography",
            "composition": "Primer plano, Regla de tercios",
            "lighting": "Contraluz (Rim light)",
            "dominant_colors": ["#000000", "#808080"],
            "art_style": "Film Noir",
            "visual_mood": "Misterioso y Melancólico",
            "ocr_text": None
        }
    }
    # Case 2: Meme / Screenshot (Edge Case)
    ex2 = {
        "graph_core": {
            "summary": "Meme de Bob Esponja cansado y jadeando.",
            "entities": {
                "persons": [{"name": "Bob Esponja", "role": "Personaje", "confidence": 0.99}],
                "concepts": [
                    {"name": "Agotamiento", "type": "State", "domain": "Health", "definition": "Estado físico del personaje", "confidence": 0.9},
                    {"name": "Burnout", "type": "Concept", "domain": "Work", "definition": "Contexto laboral sugerido por el texto", "confidence": 0.8}
                ]
            },
            "tags": ["meme", "tired", "funny", "work"]
        },
        "visual_specifics": {
            "image_type": "meme",
            "composition": "Dibujo 2D",
            "dominant_colors": ["#FFFF00 (Yellow)", "#FFFFFF"],
            "visual_mood": "Cómico / Exagerado",
            "ocr_text": "Cuando son las 4:59pm y llega un ticket urgente"
        }
    }
    return f"Input: (Cinematic Photo)\nOutput: {json.dumps(ex1, ensure_ascii=False)}\n\nInput: (Meme with Text)\nOutput: {json.dumps(ex2, ensure_ascii=False)}"


def _get_audio_examples() -> str:
    """Get few-shot examples for audio analysis."""
    # Case 1: Mixed Genres + User Nuance
    ex1 = {
        "graph_core": {
            "summary": "Pieza ecléctica que fusiona ritmos folclóricos con instrumentación pesada.",
            "entities": {
                "persons": [{"name": "Diablo Swing Orchestra", "role": "Banda", "confidence": 1.0}],
                "concepts": [
                    {"name": "Música Tradicional Mexicana", "type": "Genre Influence", "domain": "Music", "definition": "Aire rítmico percibido", "confidence": 0.5},
                    {"name": "Heavy Metal", "type": "Genre", "domain": "Music", "definition": "Instrumentación dominante", "confidence": 0.9},
                    {"name": "Energía", "type": "Mood", "domain": "Psychology", "definition": "Ambiente general", "confidence": 0.95}
                ]
            },
            "tags": ["metal", "fusion", "violin"]
        },
        "audio_specifics": {
            "audio_type": "song",
            "genre": "Avant-Garde Metal",
            "tempo": "Rápido (150 BPM)",
            "instruments": ["Guitarra Eléctrica", "Violín", "Trompeta", "Batería"],
            "emotional_tone": "Teatral y Enérgico",
            "lyrics_summary": "Celebración irónica sobre el destino inevitable."
        }
    }
    # Case 2: Instrumental / Ambient
    ex2 = {
        "graph_core": {
            "summary": "Sonido ambiental de lluvia suave y truenos lejanos.",
            "entities": {
                "concepts": [
                    {"name": "Relajación", "type": "Utility", "domain": "Health", "definition": "Uso potencial del audio", "confidence": 0.8},
                    {"name": "Tormenta", "type": "Category", "domain": "Environment", "definition": "Fuente del sonido", "confidence": 1.0}
                ]
            },
            "tags": ["ambience", "rain", "sleep", "nature"]
        },
        "audio_specifics": {
            "audio_type": "sound_effect",
            "genre": "Field Recording",
            "tempo": "N/A",
            "instruments": [],
            "emotional_tone": "Calmado",
            "lyrics_summary": None
        }
    }
    return f"Input: (Fusion Song with User Context 'sounds a bit like...')\nOutput: {json.dumps(ex1, ensure_ascii=False)}\n\nInput: (Ambient Sound)\nOutput: {json.dumps(ex2, ensure_ascii=False)}"


def _get_text_examples() -> str:
    """Get few-shot examples for text analysis."""
    # Case 1: Simple Note
    ex1 = {
        "graph_core": {
            "summary": "Nota rápida sobre ideas para la cena.",
            "entities": {
                "concepts": [{"name": "Dieta Keto", "type": "Topic", "domain": "Health", "definition": "Plan alimenticio", "confidence": 1.0}]
            },
            "tags": ["food", "todo", "ideas"]
        },
        "text_specifics": {
            "document_type": "personal_note",
            "rhetorical_tone": "Informal",
            "key_arguments": ["Usar aguacate", "Evitar carbohidratos"],
            "language": "es",
            "requires_action": True
        }
    }
    # Case 2: Academic/Formal (Edge Case)
    ex2 = {
        "graph_core": {
            "summary": "Fragmento sobre la teoría de la relatividad.",
            "entities": {
                "persons": [{"name": "Albert Einstein", "role": "Mencionado", "confidence": 1.0}],
                "concepts": [{"name": "Espacio-Tiempo", "type": "Scientific Concept", "domain": "Physics", "definition": "Unión de dimensiones", "confidence": 1.0}]
            },
            "tags": ["physics", "science", "history"]
        },
        "text_specifics": {
            "document_type": "article",
            "rhetorical_tone": "Académico / Explicativo",
            "key_arguments": ["La gravedad es curvatura geométrica", "La luz se desvía por la masa"],
            "language": "es",
            "requires_action": False
        }
    }
    return f"Input: (Personal Note)\nOutput: {json.dumps(ex1, ensure_ascii=False)}\n\nInput: (Scientific Text)\nOutput: {json.dumps(ex2, ensure_ascii=False)}"
