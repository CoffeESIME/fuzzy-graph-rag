/* ==========================================
   TypeScript Types for Multimodal Search
   ========================================== */

// --- Shared Result Type (Matching Real Backend) ---
export interface SearchResult {
    space: string;
    space_icon: string;
    uuid: string;
    distance: number;
    score: number;
    properties: Record<string, any>;
}

export interface SearchResponse {
    query: string;
    embedding_dimensions?: number;
    spaces_searched?: string[];
    total_results: number;
    results: SearchResult[];
}

// --- Coming Soon Response ---
export interface ComingSoonResponse {
    message: string;
    results: any[];
}

// --- Multimodal Fusion Response (Split View) ---
export interface MultimodalFusionResponse {
    query: string;
    alpha: number;
    text_results: SearchResult[];
    visual_results: SearchResult[];
    fused_results: SearchResult[];
    total_results: number;
    spaces_searched: string[];
}

// --- Tab 1: Semantic Text (Hybrid BM25 + Vector) ---
export interface SemanticTextRequest {
    query: string;
    limit: number;
    spaces?: string[];
    filters?: string[];   // Tag filters
    alpha?: number;       // 0=keyword, 1=vector, 0.5=balanced
}

// --- Tab 2: Visual SigLIP ---
export interface VisualSigLIPRequest {
    image: string; // base64
    limit: number;
}

// --- Tab 3: Hybrid Visual (Image + Text Fusion) ---
export interface HybridVisualRequest {
    image: string;        // base64
    text_context: string;
    alpha: number;        // image vs text weight
    limit: number;
}

// --- Tab 4: Graph Crisp ---
export interface GraphCrispRequest {
    query: string;
    alpha_cut?: number;
    limit?: number;
}

export interface GraphNode {
    id: string;
    label: string;
    type: string;
    properties: Record<string, any>;
}

export interface GraphEdge {
    source: string;
    target: string;
    type: string;
    weight: number;
    reasoning?: string;
}

export interface GraphTopology {
    nodes: GraphNode[];
    edges: GraphEdge[];
}

export interface GraphCrispResultItem extends SearchResult {
    matched_concept: string;
    relation_type: string;
}

export interface GraphCrispResponse {
    query: string;
    concepts_matched: string[];
    alpha_cut: number;
    total_results: number;
    results: GraphCrispResultItem[];
    graph_topology: GraphTopology;
}

// --- Tab 5: Graph Fuzzy (Vector-First) ---
export interface GraphFuzzyRequest {
    query: string;
    alpha_cut: number;
    limit: number;
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
    comingSoon?: boolean;
}[] = [
        {
            id: 'semantic-text',
            label: 'Semántica',
            icon: 'type',
            description: 'Híbrida: BM25 + Vector (BAAI/bge-m3) con filtros por tags',
        },
        {
            id: 'visual-siglip',
            label: 'Visual (SigLIP)',
            icon: 'image',
            description: 'Búsqueda puramente visual (vectores de imagen SigLIP)',
        },
        {
            id: 'hybrid-visual',
            label: 'Multimodal',
            icon: 'layers',
            description: 'Fusión de imagen (SigLIP) + texto (BGE-M3) con RRF',
        },
        {
            id: 'graph-crisp',
            label: 'Grafo',
            icon: 'git-branch',
            description: 'Búsqueda de relaciones en Neo4j',
            comingSoon: true,
        },
        {
            id: 'graph-fuzzy',
            label: 'Grafo Difuso',
            icon: 'radar',
            description: 'Expansión difusa con pesos calibrados',
            comingSoon: true,
        },
    ];
