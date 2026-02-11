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

# --- 1. DEFINICIÓN DE LA ESCALA MAESTRA (LA REGLA DE ORO) ---
CALIBRATION_RUBRIC = """
CONFIDENCE SCORING RUBRIC (STRICT ENFORCEMENT):
You must assign a 'confidence' score (0.0 - 1.0) to every entity and concept based on this scale:

* **1.0 (FACTUAL / HARD DATA):** - Direct visual evidence (e.g., "The car is red").
  - Explicit text definitions (e.g., "MQTT is a protocol").
  - Physical locations or dates mentioned explicitly.

* **0.7 - 0.9 (THEMATIC / STRONG CONTEXT):**
  - Strong logical inference.
  - Shared context (e.g., "Beach" implies "Vacation" even if not stated).
  - Clear emotions explicitly described.

* **0.4 - 0.6 (FUZZY / METAPHORICAL / VIBES):** <-- CRITICAL ZONE
  - Artistic interpretations (e.g., "Darkness" symbolizing "Sadness").
  - "Reminds of", "Looks like", or subtle emotional undertones.
  - Cross-domain connections (Engineering <-> Philosophy).

* **0.0 - 0.3 (NOISE):**
  - Tangential mentions or weak guesses. Do not include unless necessary.

RULE: Do NOT default to 0.9. If the connection is abstract, artistic, or distant, the score MUST be < 0.6.
""" 

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
        "reasoning": "WHY this score? (e.g. 'Direct visual evidence' or 'Metaphorical link')",
        "confidence": "<float 0.0-1.0 based on CALIBRATION_RUBRIC>"
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
        "tags": ["keyword1", "keyword2"],
        "extracted_concepts": ["List of extracted concept names for vector search"]
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

{CALIBRATION_RUBRIC}

OUTPUT SCHEMA (Follow this structure exactly):
{json.dumps(target_schema, indent=2)}

{taxonomy_hint}

{context_instruction}

FEW-SHOT EXAMPLES (Study these carefully - note how confidence scores match the rubric):
{examples_str}

Analyze the input and return ONLY the JSON object, no additional text."""

    return prompt


# ==========================================
# HELPER: FEW-SHOT EXAMPLES (2-Shots per Type)
# ==========================================

def _get_vision_examples(include_context: bool = False) -> str:
    """Get calibrated few-shot examples for vision analysis."""
    # Example 1: Clear Object (Factual - Score 1.0)
    ex1_input = "Input: (Photo of a red sports car on a track)"
    ex1_output = {
        "graph_core": {
            "summary": "Foto deportiva de un coche rojo en movimiento en una pista.",
            "entities": {
                "persons": [],
                "locations": [{"name": "Pista de carreras", "type": "Venue", "confidence": 1.0}],
                "concepts": [
                    {"name": "Coche Deportivo", "type": "Object", "domain": "Automotive", "definition": "Objeto central visible", "reasoning": "Direct visual evidence - clearly visible central object.", "confidence": 1.0},
                    {"name": "Velocidad", "type": "Action", "domain": "Physics", "definition": "Movimiento inferido", "reasoning": "Inferred from motion blur on background.", "confidence": 0.9}
                ]
            },
            "tags": ["car", "racing", "speed", "red"],
            "extracted_concepts": ["Coche Deportivo", "Velocidad"]
        },
        "visual_specifics": {
            "image_type": "photography",
            "composition": "Tracking shot, Regla de tercios",
            "lighting": "Luz natural directa",
            "dominant_colors": ["#CC0000", "#333333", "#87CEEB"],
            "art_style": "Deportivo / Dinámico",
            "visual_mood": "Adrenalina y Emoción",
            "ocr_text": None
        }
    }

    # Example 2: Abstract Art (Fuzzy - Score 0.4-0.5)
    ex2_input = "Input: (Abstract painting with chaotic dark swirls)"
    ex2_output = {
        "graph_core": {
            "summary": "Pintura abstracta oscura con trazos caóticos.",
            "entities": {
                "persons": [],
                "concepts": [
                    {"name": "Caos", "type": "Vibe", "domain": "Arts", "definition": "Interpretación subjetiva de los trazos", "reasoning": "Subjective interpretation of the swirls - no literal chaos depicted.", "confidence": 0.5},
                    {"name": "Miedo", "type": "Emotion", "domain": "Psychology", "definition": "Respuesta emocional posible", "reasoning": "Possible emotional response to dark colors, highly subjective.", "confidence": 0.4}
                ]
            },
            "tags": ["abstract", "dark", "art", "painting"],
            "extracted_concepts": ["Caos", "Miedo"]
        },
        "visual_specifics": {
            "image_type": "art",
            "composition": "Sin estructura definida",
            "lighting": "Oscuro, bajo contraste",
            "dominant_colors": ["#1A1A1A", "#2C2C54", "#474787"],
            "art_style": "Expresionismo Abstracto",
            "visual_mood": "Opresivo e Inquietante",
            "ocr_text": None
        }
    }

    if include_context:
        # Example 3: With User Context (Firewall demo)
        ex3_input = "Input: (Sunset Photo + User says 'Luna de miel en Londres')"
        ex3_output = {
            "graph_core": {
                "summary": "Foto de un atardecer dorado sobre el mar.",
                "entities": {
                    "persons": [],
                    "locations": [{"name": "Playa", "type": "Landscape", "confidence": 1.0}],
                    "concepts": [
                        {"name": "Atardecer", "type": "Time", "domain": "Nature", "definition": "Hora del día visible", "reasoning": "Direct visual evidence - golden hour clearly visible.", "confidence": 1.0}
                    ]
                },
                "tags": ["sunset", "beach", "golden_hour"],
                "extracted_concepts": ["Atardecer"]
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
        return f"{ex1_input}\nOutput: {json.dumps(ex1_output, ensure_ascii=False)}\n\n{ex2_input}\nOutput: {json.dumps(ex2_output, ensure_ascii=False)}\n\n{ex3_input}\nOutput: {json.dumps(ex3_output, ensure_ascii=False)}"
    else:
        return f"{ex1_input}\nOutput: {json.dumps(ex1_output, ensure_ascii=False)}\n\n{ex2_input}\nOutput: {json.dumps(ex2_output, ensure_ascii=False)}"


def _get_audio_examples(include_context: bool = False) -> str:
    """Get calibrated few-shot examples for audio analysis."""
    # Example 1: Clear Song with Identifiable Artist (Factual - Score 1.0/0.9)
    ex1_input = "Input: (Rock song with heavy guitar riffs and English lyrics about rebellion)"
    ex1_output = {
        "graph_core": {
            "summary": "Canción de rock pesado con riffs de guitarra y letras sobre rebeldía.",
            "entities": {
                "persons": [],
                "concepts": [
                    {"name": "Rock", "type": "Genre", "domain": "Music", "definition": "Género musical dominante", "reasoning": "Direct auditory evidence - guitar riffs, drum patterns.", "confidence": 1.0},
                    {"name": "Rebeldía", "type": "Theme", "domain": "Culture", "definition": "Tema central de la letra", "reasoning": "Explicit lyrical content about rebellion.", "confidence": 0.9}
                ]
            },
            "tags": ["rock", "guitar", "rebellion", "energy"],
            "extracted_concepts": ["Rock", "Rebeldía"]
        },
        "audio_specifics": {
            "audio_type": "song",
            "genre": "Hard Rock",
            "tempo": "Rápido (140 BPM)",
            "instruments": ["Guitarra Eléctrica", "Batería", "Bajo", "Voz"],
            "emotional_tone": "Agresivo y Enérgico",
            "lyrics_summary": "Letras sobre desafiar la autoridad y vivir sin reglas."
        }
    }

    # Example 2: Ambient / Abstract Sound (Fuzzy - Score 0.5)
    ex2_input = "Input: (Ambient electronic track with ethereal pads and no lyrics)"
    ex2_output = {
        "graph_core": {
            "summary": "Pieza electrónica ambiental con pads etéreos.",
            "entities": {
                "persons": [],
                "concepts": [
                    {"name": "Electrónica Ambiental", "type": "Genre", "domain": "Music", "definition": "Género detectado", "reasoning": "Direct auditory evidence - synthesizer pads, no beat.", "confidence": 0.9},
                    {"name": "Meditación", "type": "Utility", "domain": "Health", "definition": "Uso potencial interpretado", "reasoning": "Subjective utility - calming sounds could be for meditation but not explicitly stated.", "confidence": 0.5},
                    {"name": "Espacio", "type": "Vibe", "domain": "Arts", "definition": "Sensación sugerida", "reasoning": "Metaphorical association - ethereal pads evoke space, but it's artistic interpretation.", "confidence": 0.4}
                ]
            },
            "tags": ["ambient", "electronic", "ethereal", "calm"],
            "extracted_concepts": ["Electrónica Ambiental", "Meditación", "Espacio"]
        },
        "audio_specifics": {
            "audio_type": "instrumental",
            "genre": "Ambient Electronic",
            "tempo": "Muy lento (60 BPM)",
            "instruments": ["Sintetizador", "Pad", "Reverb Effects"],
            "emotional_tone": "Contemplativo y Flotante",
            "lyrics_summary": None
        }
    }

    if include_context:
        # Example 3: With User Context (Firewall demo)
        ex3_input = "Input: (Song + User says 'Lo escuché en un concierto en Londres')"
        ex3_output = {
            "graph_core": {
                "summary": "Pieza de rock progresivo con sintetizadores atmosféricos.",
                "entities": {
                    "persons": [],
                    "concepts": [
                        {"name": "Rock Progresivo", "type": "Genre", "domain": "Music", "definition": "Género detectado en la composición", "reasoning": "Direct auditory evidence from song structure and instruments.", "confidence": 0.9},
                        {"name": "Melancolía", "type": "Mood", "domain": "Psychology", "definition": "Tono emocional percibido", "reasoning": "Strong thematic context from slow tempo and minor key.", "confidence": 0.7}
                    ]
                },
                "tags": ["prog_rock", "atmospheric", "melancholy"],
                "extracted_concepts": ["Rock Progresivo", "Melancolía"]
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
                    "events": [{"name": "Concierto en vivo", "type": "Concert", "confidence": 0.9}],
                    "locations": [{"name": "Londres", "confidence": 1.0}],
                    "persons": []
                },
                "mood_influence": "Nostálgico, Emocional, Significativo"
            }
        }
        return f"{ex1_input}\nOutput: {json.dumps(ex1_output, ensure_ascii=False)}\n\n{ex2_input}\nOutput: {json.dumps(ex2_output, ensure_ascii=False)}\n\n{ex3_input}\nOutput: {json.dumps(ex3_output, ensure_ascii=False)}"
    else:
        return f"{ex1_input}\nOutput: {json.dumps(ex1_output, ensure_ascii=False)}\n\n{ex2_input}\nOutput: {json.dumps(ex2_output, ensure_ascii=False)}"


def _get_text_examples(include_context: bool = False) -> str:
    """Get calibrated few-shot examples for text analysis."""
    # Example 1: Technical/Factual (Score 1.0)
    ex1_input = "Input: (Technical Note: 'El protocolo MQTT usa un modelo publish/subscribe para IoT.')"
    ex1_output = {
        "graph_core": {
            "summary": "Definición técnica del protocolo MQTT y su modelo de comunicación.",
            "entities": {
                "persons": [],
                "concepts": [
                    {"name": "MQTT", "type": "Protocol", "domain": "Technology", "definition": "Protocolo de mensajería ligero", "reasoning": "Explicitly defined subject in the text.", "confidence": 1.0},
                    {"name": "IoT", "type": "Context", "domain": "Technology", "definition": "Internet de las Cosas", "reasoning": "Explicit usage context mentioned in the text.", "confidence": 0.9},
                    {"name": "Publish/Subscribe", "type": "Architecture Pattern", "domain": "Software Engineering", "definition": "Patrón de comunicación", "reasoning": "Directly stated architectural model.", "confidence": 1.0}
                ]
            },
            "tags": ["mqtt", "iot", "protocol", "pubsub"],
            "extracted_concepts": ["MQTT", "IoT", "Publish/Subscribe"]
        },
        "text_specifics": {
            "document_type": "article",
            "rhetorical_tone": "Técnico / Explicativo",
            "key_arguments": ["MQTT usa publish/subscribe", "Diseñado para IoT"],
            "language": "es",
            "requires_action": False
        }
    }

    # Example 2: Poetic/Fuzzy (Score 0.5)
    ex2_input = "Input: (Poem: 'Tu ausencia es como el invierno en mis manos.')"
    ex2_output = {
        "graph_core": {
            "summary": "Fragmento poético sobre la soledad y la ausencia.",
            "entities": {
                "persons": [],
                "concepts": [
                    {"name": "Ausencia", "type": "Theme", "domain": "Literature", "definition": "Tema central del texto", "reasoning": "Main topic textually present - explicit subject.", "confidence": 1.0},
                    {"name": "Invierno", "type": "Metaphor", "domain": "Literature", "definition": "Recurso literario", "reasoning": "Used metaphorically to describe coldness/sadness, not a literal season.", "confidence": 0.5},
                    {"name": "Soledad", "type": "Emotion", "domain": "Psychology", "definition": "Sentimiento inferido", "reasoning": "Implied feeling from context of absence - not explicitly written.", "confidence": 0.6}
                ]
            },
            "tags": ["poetry", "absence", "metaphor", "emotion"],
            "extracted_concepts": ["Ausencia", "Invierno", "Soledad"]
        },
        "text_specifics": {
            "document_type": "quote",
            "rhetorical_tone": "Poético / Melancólico",
            "key_arguments": ["La ausencia se compara con el frío invernal"],
            "language": "es",
            "requires_action": False
        }
    }

    if include_context:
        # Example 3: With User Context (Firewall demo)
        ex3_input = "Input: (Contract + User says 'Lo firmé cuando me mudé a Monterrey')"
        ex3_output = {
            "graph_core": {
                "summary": "Contrato de arrendamiento de departamento.",
                "entities": {
                    "persons": [{"name": "Juan Pérez", "role": "Arrendatario", "confidence": 1.0}],
                    "organizations": [{"name": "Inmobiliaria ABC", "confidence": 1.0}],
                    "concepts": [
                        {"name": "Contrato Legal", "type": "Document Type", "domain": "Law", "definition": "Tipo de documento", "reasoning": "Document explicitly identified as a legal contract.", "confidence": 1.0}
                    ]
                },
                "tags": ["legal", "rent", "contract"],
                "extracted_concepts": ["Contrato Legal"]
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
        return f"{ex1_input}\nOutput: {json.dumps(ex1_output, ensure_ascii=False)}\n\n{ex2_input}\nOutput: {json.dumps(ex2_output, ensure_ascii=False)}\n\n{ex3_input}\nOutput: {json.dumps(ex3_output, ensure_ascii=False)}"
    else:
        return f"{ex1_input}\nOutput: {json.dumps(ex1_output, ensure_ascii=False)}\n\n{ex2_input}\nOutput: {json.dumps(ex2_output, ensure_ascii=False)}"


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
            "tags": ["sismo", "coincidencia", "miedo", "musica"],
            "extracted_concepts": ["Sincronía"]
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
            "tags": ["infancia", "abuela", "cocina"],
            "extracted_concepts": ["Nostalgia"]
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
