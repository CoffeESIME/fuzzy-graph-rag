/* ==========================================
   TypeScript Types for Multimodal Search
   ========================================== */

// --- Shared Result Type ---
export interface SearchResult {
    filename: string;
    score: number;
    space: string;
    uuid: string;
    reasoning: string;
    properties: Record<string, unknown>;
}

export interface SearchResponse {
    query: string;
    search_type: string;
    total_results: number;
    results: SearchResult[];
}

// --- Tab 1: Semantic Text ---
export interface SemanticTextRequest {
    query: string;
    limit: number;
}

// --- Tab 2: Visual SigLIP ---
export interface VisualSigLIPRequest {
    image: string; // base64 or URL
    limit: number;
}

// --- Tab 3: Hybrid Visual ---
export interface HybridVisualRequest {
    image: string;
    text_context: string;
    alpha: number;
    limit: number;
}

// --- Tab 4: Graph Crisp ---
export interface GraphCrispRequest {
    query: string;
    entity_types?: string[];
}

// --- Tab 5: Graph Fuzzy ---
export interface GraphFuzzyRequest {
    query: string;
    min_confidence: number;
}

// --- Tab Enum ---
export type SearchTab =
    | 'semantic-text'
    | 'visual-siglip'
    | 'hybrid-visual'
    | 'graph-crisp'
    | 'graph-fuzzy';

export const SEARCH_TABS: {
    id: SearchTab;
    label: string;
    icon: string;
    description: string;
}[] = [
        {
            id: 'semantic-text',
            label: 'Semántica',
            icon: 'type',
            description: 'Búsqueda vectorial estándar (BAAI/bge-m3)',
        },
        {
            id: 'visual-siglip',
            label: 'Visual (SigLIP)',
            icon: 'image',
            description: 'Búsqueda puramente visual (vectores de imagen)',
        },
        {
            id: 'hybrid-visual',
            label: 'Híbrida',
            icon: 'layers',
            description: 'Fusión de vectores SigLIP y BAAI/bge-m3',
        },
        {
            id: 'graph-crisp',
            label: 'Grafo',
            icon: 'git-branch',
            description: 'Búsqueda de relaciones estrictas en Neo4j',
        },
        {
            id: 'graph-fuzzy',
            label: 'Grafo Difuso',
            icon: 'radar',
            description: 'Expansión difusa con pesos calibrados',
        },
    ];
