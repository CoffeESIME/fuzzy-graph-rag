# GraphRAG — Diagramas de Documentación

---

## 1. Arquitectura del Sistema

```mermaid
graph TB
    subgraph Frontend["Frontend (Vite + React)"]
        UI_Search["🔍 Búsqueda"]
        UI_Ingest["📥 Ingesta"]
        UI_Enrich["🧠 Enriquecimiento"]
        UI_Analysis["📊 Análisis"]
    end

    subgraph Backend["Backend (FastAPI + Uvicorn)"]
        R_Search["/search"]
        R_Ingest["/ingest"]
        R_Enrich["/api/enrichment"]
        R_Explore["/api/explore"]
        R_Analysis["/analysis"]
        R_Inbox["/inbox"]
        Celery["Celery Worker\n(tareas asíncronas)"]
    end

    subgraph Storage["Almacenamiento"]
        Neo4j[("Neo4j\nGrafo principal")]
        Weaviate[("Weaviate\nVectores multimodal")]
        MinIO[("MinIO\nArchivos binarios")]
        Redis[("Redis\nCola Celery")]
    end

    subgraph AI["Servicios IA"]
        LLM["LLM Local\n(Ollama)"]
        Embedder["BGE-M3 / CLIP\nEmbedding"]
    end

    UI_Search --> R_Search
    UI_Ingest --> R_Ingest
    UI_Ingest --> R_Inbox
    UI_Enrich --> R_Enrich
    UI_Enrich --> R_Explore
    UI_Analysis --> R_Analysis

    R_Enrich --> Celery
    R_Ingest --> Celery
    Celery --> Redis
    Celery --> LLM
    Celery --> Embedder

    R_Search --> Neo4j
    R_Search --> Weaviate
    R_Enrich --> Neo4j
    R_Enrich --> Weaviate
    R_Explore --> Neo4j
    R_Explore --> Weaviate
    R_Analysis --> Neo4j
    R_Inbox --> Neo4j
    R_Ingest --> MinIO

    Embedder --> Weaviate
```

---

## 2. Modelo de Datos — Neo4j

```mermaid
erDiagram
    DigitalAsset {
        string elementId PK
        string filename
        string file_hash
        string mime_type
        string minio_path
        string[] tags
        bool fuzzy_applied
    }
    Concept {
        string elementId PK
        string name
        string domain
        string description
        string[] aliases
        bool fuzzy_applied
        string enrichment_status
    }
    Person {
        string elementId PK
        string name
    }
    Project {
        string elementId PK
        string name
        string description
    }
    Location {
        string elementId PK
        string name
    }
    Organization {
        string elementId PK
        string name
    }
    Event {
        string elementId PK
        string name
    }

    DigitalAsset ||--o{ Concept : "EVOKES_CONCEPT\n(weight: 0-1)"
    DigitalAsset ||--o{ Person : "CREATED_BY\n(weight: 1.0)"
    DigitalAsset ||--o{ Project : "BELONGS_TO\n(weight: 1.0)"
    DigitalAsset ||--o{ Location : "LOCATED_AT\n(weight: 1.0)"
    DigitalAsset ||--o{ Organization : "AFFILIATED_WITH"
    DigitalAsset ||--o{ Event : "PART_OF"
```

---

## 3. Pipeline de Enriquecimiento Semántico

```mermaid
sequenceDiagram
    participant User as Usuario
    participant FE as Frontend
    participant API as /api/enrichment
    participant Celery
    participant LLM as LLM Local
    participant W as Weaviate
    participant Neo as Neo4j

    User->>FE: Selecciona nodo hub (Concept/Person)
    FE->>API: GET /candidates?node_type=Concept&status=UNAPPLIED
    API->>Neo: MATCH (n:Concept) WHERE n.fuzzy_applied IS NULL
    Neo-->>API: Lista de nodos
    API-->>FE: Candidatos

    User->>FE: Encola enriquecimiento
    FE->>API: POST /enrich {node_ids:[...]}
    API->>Celery: enqueue task
    Celery->>LLM: Genera n.description vía prompt
    LLM-->>Celery: Descripción en lenguaje natural
    Celery->>Neo: SET n.description = "..."

    User->>FE: Vista previa de pesos (slider α)
    FE->>API: GET /{node_id}/preview-weights?semantic_weight=0.3
    API->>W: near_text(description, top_k=50)
    W-->>API: [{file_hash, cosine_sim}, ...]
    API->>Neo: MATCH assets conectados al nodo
    Note over API: blended = current*(1-α) + sim_norm*α
    Note over API: Protege weight≥1.0 y tipos fijos
    API-->>FE: [{file_hash, current_weight, proposed_weight}]

    User->>FE: Aplica pesos
    FE->>API: POST /{node_id}/apply-weights {updates:[...]}
    API->>Neo: UNWIND updates SET r.weight = new_weight
    API->>Neo: SET n.fuzzy_applied = true
    Neo-->>API: OK
    API-->>FE: ✅ Pesos aplicados
```

---

## 4. Búsqueda Latente (Latent Explorer)

```mermaid
flowchart TD
    A["Usuario selecciona\nDigitalAsset seed"] --> B["GET /explore/seeds\nsort: top/random/least"]
    B --> C["Selecciona seed\nde la lista"]
    C --> D["GET /latent-connections/{id}\n?alpha=0.3&top_k=5"]
    D --> E["Fetch vector seed\ndesde Weaviate\n4 espacios vectoriales"]
    E --> F["near_vector búsqueda\nen TextSpace / VisualSpace\n/ AudioSpace / MemorySpace"]
    F --> G["Merge global de vecinos\nK más cercanos"]
    G --> H{"¿Relación\nya existe en Neo4j?"}
    H -- Sí --> I["Omitir sugerencia"]
    H -- No --> J["Proponer nueva conexión\ncon weight calculado"]
    J --> K["Mostrar sugerencias\nagrupadas por DigitalAsset"]
    K --> L{"Usuario decide"}
    L -- "Validar con LLM" --> M["POST /validate-connections\nLLM filtra inválidas"]
    M --> K
    L -- "Aprobar" --> N["POST /approve-connection"]
    N --> O["MERGE relación en Neo4j\nsource='interactive_latent_explorer'"]
    L -- "Descartar" --> P["Eliminar de lista local"]
    L -- "Exportar JSON" --> Q["Descarga archivo\ncon seed + config + sugerencias"]
```

---

## 5. Operaciones de Dedup de Entidades

```mermaid
flowchart LR
    subgraph Input["Selección"]
        S1["Entidades del\nmismo tipo\nmulti-select"]
        S2["Entidad origen\n+ Entidad destino\ntipo diferente"]
        S3["Una o más\nentidades a\neliminar"]
        S4["Una entidad +\nnuevo tipo\nobjetivo"]
    end

    subgraph Ops["Operación"]
        O1["Fusionar\nDuplicados"]
        O2["Fusión\nCruzada"]
        O3["Degradar\na Tag"]
        O4["Cambiar\nTipo"]
    end

    subgraph Backend["Backend Cypher"]
        B1["MATCH relaciones src\nMERGE en hub\nDETACH DELETE src"]
        B2["Merge + opcional\nRETYPE del resultado"]
        B3["SET a.tags += name\nDETACH DELETE nodo"]
        B4["REMOVE n:TipoA\nSET n:TipoB"]
    end

    S1 --> O1 --> B1
    S2 --> O2 --> B2
    S3 --> O3 --> B3
    S4 --> O4 --> B4
```

---

## 6. Navegación Frontend

```mermaid
graph LR
    Root["/ App Root"] --> Search["🔍 /search\nBúsqueda Híbrida"]
    Root --> Ingest["📥 /ingest\nIngesta de Archivos"]
    Root --> Enrich["🧠 /enrichment\nEnriquecimiento"]
    Root --> Analysis["📊 /analysis\nAnálisis de Grafo"]

    Search --> S1["Búsqueda Fuzzy\n(Grafo)"]
    Search --> S2["Búsqueda Semántica\n(Texto)"]
    Search --> S3["Visual SigLIP"]
    Search --> S4["Comparativa"]
    Search --> S5["Vista Híbrida"]

    Ingest --> I1["Cola de Revisión"]
    Ingest --> I2["Generación de Grafo"]
    Ingest --> I3["Control de Tareas"]
    Ingest --> I4["Agrupación"]

    Enrich --> E1["Pesos Difusos\n(Semantic Weights)"]
    Enrich --> E2["Navegador Latente\n(Latent Explorer)"]
    Enrich --> E3["Limpieza Ontológica"]
    E3 --> E3a["Dedup Conceptos"]
    E3 --> E3b["Demote Manual"]
    E3 --> E3c["Dedup Entidades\n(4 tabs)"]

    Analysis --> A1["/pathfinder\nNavegador Latente"]
    Analysis --> A2["/serendipity\nCamino Serendipia"]
    Analysis --> A3["/comparison\nBúsqueda Comparativa"]
    Analysis --> A4["Community / PageRank\nChord / Heatmap / etc."]
```
