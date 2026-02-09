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
    existing_taxonomies: Optional[Dict[str, List[str]]] = None,
    is_user_memory: bool = False  # NEW: Flag for memory-specific processing
) -> str:
    """
    Builds the system prompt for the LLM Gateway.
    
    Args:
        task_type: One of "vision", "audio", "text"
        external_context: User-provided context (notes, descriptions)
        existing_taxonomies: Existing concept types/domains from the graph
        is_user_memory: If True, use memory_analysis schema instead of text_specifics
        
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
        "confidence": "<float 0.0-1.0>",
        "reasoning": "Breve explicación de por qué se eligió este concepto y esta confianza (Español)"
    }

    # ==========================================
    # USER CONTEXT STRUCTURE (Firewall for external memories)
    # ==========================================
    user_context_structure = {
        "summary": "Resumen de la anécdota o memoria del usuario (Español)",
        "context_entities": {
            "events": [{"name": "Nombre del evento", "type": "Type", "confidence": "<float 0.0-1.0>"}],
            "locations": [{"name": "Lugar del contexto", "confidence": "<float 0.0-1.0>"}],
            "persons": [{"name": "Personas acompañantes", "confidence": "<float 0.0-1.0>"}]
        },
        "mood_influence": "Cómo este contexto afecta la percepción (e.g. Nostálgico, Celebratorio)"
    }

    # Core Graph Data (Neo4j Nodes)
    graph_core = {
        "summary": "Dense description (Spanish)",
        "entities": {
            "persons": [{"name": "Name", "role": "Role", "confidence": "<float 0.0-1.0>"}],
            "locations": [{"name": "Name", "type": "Type", "confidence": "<float 0.0-1.0>"}],
            "organizations": [{"name": "Org Name", "confidence": "<float 0.0-1.0>"}],
            "events": [{"name": "Event Name", "type": "Concert/Conference/etc", "date": "YYYY-MM-DD (opt)", "confidence": "<float 0.0-1.0>"}],
            "projects": [{"title": "Project Title", "type": "Type of project", "year": "YYYY (opt)", "confidence": "<float 0.0-1.0>"}],
            "concepts": [concept_structure]
        },
        "tags": ["keyword1", "keyword2"]
    }

    # ==========================================
    # CONDITIONAL CONTEXT FLAG
    # ==========================================
    # Detect if user provided context (and it's not a pure memory ingestion)
    has_context = bool(external_context) and not is_user_memory

    # Specific Metadata per Type
    schemas = {
        "vision": {
            "graph_core": graph_core,
            "user_context_analysis": user_context_structure if external_context else None,
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
            "user_context_analysis": user_context_structure if external_context else None,
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
            "user_context_analysis": user_context_structure if external_context else None,
            "text_specifics": {
                "document_type": "article | quote | personal_note | code | receipt",
                "rhetorical_tone": "Académico, Sarcástico, Informal...",
                "key_arguments": ["Puntos principales"],
                "language": "ISO Code (es, en, fr...)",
                "requires_action": True  # bool
            }
        }
    }

    # --- SCHEMA SELECTION ---
    target_schema = schemas.get(task_type, schemas["text"]).copy()
    
    # Override for User Memory: use memory_analysis instead of text_specifics
    if task_type == "text" and is_user_memory:
        target_schema = {
            "graph_core": graph_core,
            "memory_analysis": {
                "enriched_text": "Narrativa detallada que expande y contextualiza el input del usuario (Spanish)",
                "sentiment": "Nostalgic | Happy | Anxious | Surreal | Reflective | etc.",
                "emotional_intensity": "<float 0.0-1.0>",
                "file_connection": {
                    "relation_type": "SOUNDTRACK_OF | REMINDS_OF | CAPTURED_DURING | INSPIRED_BY | etc.",
                    "reasoning": "Explicación de por qué el archivo está conectado a esta memoria (Spanish)",
                    "confidence": "<float 0.0-1.0>"
                }
            }
        }
    
    # Note: user_context_analysis is already conditionally included in schemas above

    # ==========================================
    # 3. FEW-SHOT EXAMPLES SELECTION
    # ==========================================
    if task_type == "vision":
        examples_str = _get_vision_examples(include_context=has_context)
    elif task_type == "audio":
        examples_str = _get_audio_examples(include_context=has_context)
    elif task_type == "text":
        # Memory-specific examples vs normal text examples
        if is_user_memory:
            examples_str = _get_memory_examples()
        else:
            examples_str = _get_text_examples(include_context=has_context)
    else:
        examples_str = _get_text_examples(include_context=has_context)

    # ==========================================
    # 4. NUANCE-AWARE CONTEXT INSTRUCTION
    # ==========================================
    ocr_instruction = ""
    if task_type == "vision":
        ocr_instruction = """
VISION TASK SPECIFIC RULES:
1. **MEMES & SCREENSHOTS:** If the image contains text (e.g., subtitles, code, chat logs), you MUST transcribe it VERBATIM into the 'ocr_text' field.
2. **CONTEXTUALIZATION:** Use the 'ocr_text' to inform the 'visual_mood' and 'summary'. (e.g., If the text is a joke, the mood is 'Humorous').
"""
    # ==========================================
    # CONTEXT INSTRUCTION WITH FIREWALL RULES
    # ==========================================
    context_instruction = ""
    if has_context:
        context_instruction = f"""
CRITICAL: USER CONTEXT PROVIDED:
{json.dumps(external_context, indent=2, ensure_ascii=False)}

================================================================================
FIREWALL RULES - SEPARATE CONTENT VS CONTEXT (MANDATORY)
================================================================================

1. **graph_core.entities:** ONLY facts found INSIDE the file content itself (pixels/audio/text).
   - Example: If a photo shows a beach, extract Location: "Beach" here.
   - Do NOT include places the user mentions in their notes unless visible in the actual file.

2. **user_context_analysis.context_entities:** Entities mentioned ONLY by the user in their notes.
   - Example: User says "I took this in London" -> Put "London" here, NOT in graph_core.
   - This is the user's ANECDOTE, not the file content.

3. **user_context_analysis.mood_influence:** How the user's story CHANGES the file's perceived vibe.
   - Example: A neutral photo + "My wedding day" -> mood_influence: "Celebratory, Romantic"

================================================================================
NUANCE DETECTION RULES
================================================================================

4. **Detect Qualifiers & Confidence:** Do NOT blindly assign confidence 1.0. Analyze tone:
   - "Definitely", "Always", "I love" -> Confidence 0.95 - 1.0
   - "Very marked", "Strong influence" -> Confidence 0.8 - 0.9
   - "A bit like", "Reminds me of", "Maybe", "Sounds like" -> Confidence 0.4 - 0.6

5. **Mixed Concepts:** If the user describes a mix (e.g., "Mexican Folk with Heavy Metal"), extract BOTH concepts separately with their respective confidence levels.
   - Example: "Mexican Folk with Heavy Metal" -> ["Mexican Folk", "Heavy Metal"]

6. **Arrays as Distributions:** ORDER MATTERS. Place the most dominant elements FIRST.
   - Example: "Mucho amarillo, menos café" -> ["Yellow", "Brown"]
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
   {ocr_instruction}
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

def _get_vision_examples(include_context: bool = False) -> str:
    """Get few-shot examples for vision analysis."""
    # Case 1: Complex/Rich Image (No context)
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
    
    # Case 2: With User Context (Firewall example)
    if include_context:
        ex2 = {
            "graph_core": {
                "summary": "Foto de un atardecer dorado sobre el mar.",
                "entities": {
                    "persons": [],
                    "locations": [{"name": "Playa", "type": "Landscape", "confidence": 1.0}],
                    "concepts": [
                        {"name": "Atardecer", "type": "Time", "domain": "Nature", "definition": "Hora del día visible", "confidence": 1.0}
                    ]
                },
                "tags": ["sunset", "beach", "golden_hour"]
            },
            "visual_specifics": {
                "image_type": "photography",
                "composition": "Horizonte centrado",
                "lighting": "Golden hour",
                "dominant_colors": ["#FFD700", "#FF6347", "#4169E1"],
                "art_style": "Naturalista",
                "visual_mood": "Romántico y Sereno",
                "ocr_text": None
            },
            "user_context_analysis": {
                "summary": "El usuario tomó esta foto durante su luna de miel en Londres.",
                "context_entities": {
                    "events": [{"name": "Luna de miel", "type": "Personal Event", "confidence": 1.0}],
                    "locations": [{"name": "Londres", "confidence": 1.0}],
                    "persons": [{"name": "Esposa", "confidence": 0.9}]
                },
                "mood_influence": "Celebratorio, Romántico, Nostálgico"
            }
        }
        return f"Input: (Cinematic Photo without context)\nOutput: {json.dumps(ex1, ensure_ascii=False)}\n\nInput: (Sunset Photo + User says 'Luna de miel en Londres')\nOutput: {json.dumps(ex2, ensure_ascii=False)}"
    else:
        # Case 2: Meme / Screenshot (No context)
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


def _get_audio_examples(include_context: bool = False) -> str:
    """Get few-shot examples for audio analysis."""
    # Case 1: Mixed Genres + User Nuance (No context)
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
    
    if include_context:
        # Case 2: With User Context (Pink Floyd + London example)
        ex2 = {
            "graph_core": {
                "summary": "Pieza de rock progresivo con sintetizadores atmosféricos y guitarra melodíosa.",
                "entities": {
                    "persons": [{"name": "Pink Floyd", "role": "Banda", "confidence": 0.95}],
                    "concepts": [
                        {"name": "Rock Progresivo", "type": "Genre", "domain": "Music", "definition": "Género detectado en la composición", "confidence": 0.9},
                        {"name": "Melancolía", "type": "Mood", "domain": "Psychology", "definition": "Tono emocional de la música", "confidence": 0.85}
                    ]
                },
                "tags": ["prog_rock", "atmospheric", "70s"]
            },
            "audio_specifics": {
                "audio_type": "song",
                "genre": "Progressive Rock",
                "tempo": "Lento (70 BPM)",
                "instruments": ["Sintetizador", "Guitarra Eléctrica", "Bajo", "Batería"],
                "emotional_tone": "Introspectivo y Nostálgico",
                "lyrics_summary": "Reflexión sobre el paso del tiempo."
            },
            "user_context_analysis": {
                "summary": "El usuario escuchó esta canción por primera vez en un concierto en Londres.",
                "context_entities": {
                    "events": [{"name": "Concierto de Pink Floyd", "type": "Concert", "confidence": 0.9}],
                    "locations": [{"name": "Londres", "confidence": 1.0}],
                    "persons": []
                },
                "mood_influence": "Nostálgico, Emocional, Significativo"
            }
        }
        return f"Input: (Fusion Song)\nOutput: {json.dumps(ex1, ensure_ascii=False)}\n\nInput: (Song + User says 'Lo escuché en un concierto en Londres')\nOutput: {json.dumps(ex2, ensure_ascii=False)}"
    else:
        # Case 2: Instrumental / Ambient (No context)
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


def _get_text_examples(include_context: bool = False) -> str:
    """Get few-shot examples for text analysis."""
    # Case 1: Simple Note (No context)
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
    
    if include_context:
        # Case 2: Document with User Context
        ex2 = {
            "graph_core": {
                "summary": "Contrato de arrendamiento de departamento.",
                "entities": {
                    "persons": [{"name": "Juan Pérez", "role": "Arrendatario", "confidence": 1.0}],
                    "organizations": [{"name": "Inmobiliaria ABC", "confidence": 1.0}],
                    "concepts": [{"name": "Contrato Legal", "type": "Document Type", "domain": "Law", "definition": "Tipo de documento", "confidence": 1.0}]
                },
                "tags": ["legal", "rent", "contract"]
            },
            "text_specifics": {
                "document_type": "contract",
                "rhetorical_tone": "Formal / Legal",
                "key_arguments": ["Duración 12 meses", "Depósito de 2 meses"],
                "language": "es",
                "requires_action": True
            },
            "user_context_analysis": {
                "summary": "El usuario firmó este contrato cuando se mudó a Monterrey por trabajo.",
                "context_entities": {
                    "events": [{"name": "Mudanza por trabajo", "type": "Life Event", "confidence": 0.95}],
                    "locations": [{"name": "Monterrey", "confidence": 1.0}],
                    "persons": []
                },
                "mood_influence": "Transición, Nuevo comienzo, Profesional"
            }
        }
        return f"Input: (Personal Note)\nOutput: {json.dumps(ex1, ensure_ascii=False)}\n\nInput: (Contract + User says 'Lo firmé cuando me mudé a Monterrey')\nOutput: {json.dumps(ex2, ensure_ascii=False)}"
    else:
        # Case 2: Academic/Formal (No context)
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


def _get_memory_examples() -> str:
    """Get few-shot examples specifically for User Memory analysis."""
    
    # Case 1: Strong Memory connected to a file (Synchrony)
    ex1 = {
        "graph_core": {
            "summary": "Recuerdo sobre un sismo coincidiendo con una canción.",
            "entities": {
                "persons": [],
                "locations": [{"name": "Ciudad de México", "type": "City", "confidence": 1.0}],
                "organizations": [],
                "concepts": [
                    {"name": "Sincronía", "type": "Phenomenon", "domain": "Philosophy", "definition": "Coincidencia significativa percibida", "confidence": 0.9, "reasoning": "El timing exacto creó una experiencia surreal"}
                ]
            },
            "tags": ["sismo", "coincidencia", "miedo", "musica"]
        },
        "memory_analysis": {
            "enriched_text": "El usuario relata una experiencia surrealista donde el sismo de 2017 comenzó exactamente cuando la canción llegó a su clímax, creando una asociación permanente entre el caos y la música.",
            "sentiment": "Surreal / Awe",
            "emotional_intensity": 0.95,
            "file_connection": {
                "relation_type": "SOUNDTRACK_OF",
                "reasoning": "La canción sonaba durante el evento traumático, creando una conexión emocional permanente.",
                "confidence": 1.0
            }
        }
    }

    # Case 2: Vague Memory / Reflection (Weak connection)
    ex2 = {
        "graph_core": {
            "summary": "Reflexión vaga sobre la infancia al ver una imagen.",
            "entities": {
                "persons": [{"name": "Abuela", "role": "Family", "confidence": 1.0}],
                "locations": [],
                "organizations": [],
                "concepts": [
                    {"name": "Nostalgia", "type": "Emotion", "domain": "Psychology", "definition": "Añoranza del pasado", "confidence": 1.0, "reasoning": "Sentimiento central de la memoria"}
                ]
            },
            "tags": ["infancia", "abuela", "cocina"]
        },
        "memory_analysis": {
            "enriched_text": "Una breve nota nostálgica evocada por el color amarillo de la imagen, que le recuerda vagamente a la cocina de su abuela.",
            "sentiment": "Nostalgic",
            "emotional_intensity": 0.4,
            "file_connection": {
                "relation_type": "REMINDS_OF",
                "reasoning": "Asociación visual tenue por el color amarillo.",
                "confidence": 0.3
            }
        }
    }

    return f"Input: (Story about earthquake + song)\nOutput: {json.dumps(ex1, ensure_ascii=False)}\n\nInput: (Vague childhood memory)\nOutput: {json.dumps(ex2, ensure_ascii=False)}"
