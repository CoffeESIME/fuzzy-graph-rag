import axios from 'axios';
import type {
    SemanticTextRequest,
    VisualSigLIPRequest,
    HybridVisualRequest,
    GraphCrispRequest,
    GraphFuzzyRequest,
    SearchResponse,
    MultimodalFusionResponse,
    GraphCrispResponse,
    SynthesizeRequest,
    SynthesizeResponse,
} from '../types/search';

const api = axios.create({
    baseURL: '/api/search',
    headers: { 'Content-Type': 'application/json' },
    timeout: 30000,
});

// --- Tab 1: Semantic Hybrid (real /vectors endpoint) ---
export async function searchSemanticText(
    data: SemanticTextRequest
): Promise<SearchResponse> {
    const res = await api.post<SearchResponse>('/vectors', data);
    return res.data;
}

// --- Tab 2: Visual SigLIP (real endpoint) ---
export async function searchVisualSiglip(
    data: VisualSigLIPRequest
): Promise<SearchResponse> {
    const res = await api.post<SearchResponse>('/visual-siglip', data);
    return res.data;
}

// --- Tab 3: Hybrid Visual (real endpoint) ---
export async function searchHybridVisual(
    data: HybridVisualRequest
): Promise<MultimodalFusionResponse> {
    const res = await api.post<MultimodalFusionResponse>('/hybrid-visual', data);
    return res.data;
}

// --- Tab 4 & 5: Graph (Coming Soon stubs) ---
export async function searchGraphCrisp(
    data: GraphCrispRequest
): Promise<GraphCrispResponse> {
    const res = await api.post<GraphCrispResponse>('/graph-crisp', data);
    return res.data;
}

export async function searchGraphFuzzy(
    data: GraphFuzzyRequest
): Promise<GraphCrispResponse> {
    const res = await api.post<GraphCrispResponse>('/graph-fuzzy', data);
    return res.data;
}

// --- Tab 6: Chat Synthesis ---
const chatApi = axios.create({
    baseURL: '/api/chat',
    headers: { 'Content-Type': 'application/json' },
    timeout: 120000, // Synthesis can take a while
});

export async function synthesizeComparison(
    data: SynthesizeRequest
): Promise<SynthesizeResponse> {
    const res = await chatApi.post<SynthesizeResponse>('/synthesize', data);
    return res.data;
}

// --- Enrichment API ---
const enrichmentApi = axios.create({
    baseURL: '/api/api/enrichment',
    headers: { 'Content-Type': 'application/json' },
    timeout: 30000,
});

export interface EnrichRequest {
    node_ids: string[];
}

export interface WeightPreviewResult {
    file_hash: string;
    filename: string;
    space: string;
    relation_type: string | null;
    current_weight: number;
    vector_similarity: number | null;
    proposed_weight: number | null;
}

export interface WeightPreviewResponse {
    results: WeightPreviewResult[];
}
export interface CandidateNode {
    id: string;
    name: string;
    type: string;
    connections: number;
    status: string | null;
    error: string | null;
    fuzzy_applied: boolean | null;
}

export interface CandidateResponse {
    candidates: CandidateNode[];
    total: number;
}

export async function getEnrichmentCandidates(nodeType: string, limit: number = 50, statusFilter: string = 'PENDING'): Promise<CandidateResponse> {
    const res = await enrichmentApi.get<CandidateResponse>('/candidates', {
        params: { node_type: nodeType, limit, status_filter: statusFilter }
    });
    return res.data;
}

export async function requestEnrichment(nodeIds: string[]): Promise<{ status: string, message: string, queued_count: number }> {
    const res = await enrichmentApi.post('/enrich', { node_ids: nodeIds });
    return res.data;
}

export async function getPreviewWeights(nodeId: string, semanticWeight: number = 0.3): Promise<WeightPreviewResponse> {
    const res = await enrichmentApi.get<WeightPreviewResponse>(`/${nodeId}/preview-weights`, {
        params: { semantic_weight: semanticWeight }
    });
    return res.data;
}

export interface WeightUpdateItem {
    file_hash: string;
    new_weight: number;
}


export async function applyPreviewWeights(nodeId: string, updates: WeightUpdateItem[]): Promise<{ status: string, message: string, updated_count: number }> {
    const res = await enrichmentApi.post(`/${nodeId}/apply-weights`, { updates });
    return res.data;
}

// --- Entity Dedup API ---
export interface EntityNode {
    id: string;
    name: string;
    type: string;
    connections: number;
}

export interface EntityListResponse {
    entities: EntityNode[];
    total: number;
}

export interface MergeEntitiesRequest {
    node_type: string;
    target_name: string;
    source_ids: string[];
    keep_id: string;
}

export async function getEntities(
    nodeType: string,
    search: string = '',
    limit: number = 200
): Promise<EntityListResponse> {
    const res = await enrichmentApi.get<EntityListResponse>('/entities', {
        params: { node_type: nodeType, search, limit }
    });
    return res.data;
}

export async function mergeEntityNodes(
    data: MergeEntitiesRequest
): Promise<{ status: string; message: string; merged_count: number }> {
    const res = await enrichmentApi.post('/entities/merge', data);
    return res.data;
}

export interface DemoteEntitiesRequest {
    node_type: string;
    source_ids: string[];
}

export async function demoteEntityNodes(
    data: DemoteEntitiesRequest
): Promise<{ status: string; message: string; demoted_count: number }> {
    const res = await enrichmentApi.post('/entities/demote', data);
    return res.data;
}

export interface RetypeEntityRequest {
    node_id: string;
    from_type: string;
    to_type: string;
}

export async function retypeEntityNode(
    data: RetypeEntityRequest
): Promise<{ status: string; message: string; name: string }> {
    const res = await enrichmentApi.post('/entities/retype', data);
    return res.data;
}

export async function getGraphRelationTypes(): Promise<{ relation_types: string[]; count: number }> {
    const res = await enrichmentApi.get('/entities/relation-types');
    return res.data;
}

// --- Enrichment Health API ---
const healthApi = axios.create({
    baseURL: '/api/enrichment/health',
    headers: { 'Content-Type': 'application/json' },
    timeout: 60000,
});

export interface HealthStats {
    total_artists: number;
    total_projects: number;
    orphaned_audio_no_artist: number;
    orphaned_audio_no_project: number;
}

export interface RepairResponse {
    success: boolean;
    message: string;
    items_updated: number;
}

export async function getHealthStats(): Promise<HealthStats> {
    const res = await healthApi.get<HealthStats>('/stats');
    return res.data;
}

export async function repairArtists(): Promise<RepairResponse> {
    const res = await healthApi.post<RepairResponse>('/repair-artists');
    return res.data;
}

export async function backfillProjects(): Promise<RepairResponse> {
    const res = await healthApi.post<RepairResponse>('/backfill-projects');
    return res.data;
}

// --- Explore API ---
const exploreApi = axios.create({
    baseURL: '/api/api/explore',
    headers: { 'Content-Type': 'application/json' },
    timeout: 60000,
});

export interface SeedNode {
    id: string;
    name: string;
    type: string;
    connections: number;
}

export interface SeedResponse {
    seeds: SeedNode[];
    total: number;
}

export interface LatentConnectionSuggestion {
    asset_id: string;
    asset_name: string;
    target_concept_id: string;
    target_concept_name: string;
    relation_type: string;
    current_weight: number;
    cosine_similarity: number;
    proposed_weight: number;
    direction: string;
    reasoning: string;
}

export interface LatentConnectionResponse {
    seed_id: string;
    seed_name: string;
    suggestions: LatentConnectionSuggestion[];
}

export interface ApproveConnectionRequest {
    asset_id: string;
    target_concept_id: string;
    relation_type: string;
    proposed_weight: number;
    reasoning: string;
}

export async function getExplorableSeeds(nodeType: string, limit: number = 50, sortBy: string = 'top_connected', search: string = ''): Promise<SeedResponse> {
    const res = await exploreApi.get<SeedResponse>('/seeds', { params: { node_type: nodeType, limit, sort_by: sortBy, search } });
    return res.data;
}

export async function getLatentConnections(nodeId: string, topK: number = 5, alpha: number = 0.3): Promise<LatentConnectionResponse> {
    const res = await exploreApi.get<LatentConnectionResponse>(`/latent-connections/${nodeId}`, { params: { top_k: topK, alpha } });
    return res.data;
}

export async function approveLatentConnection(data: ApproveConnectionRequest): Promise<{ status: string, message: string }> {
    const res = await exploreApi.post('/approve-connection', data);
    return res.data;
}

export interface ValidateConnectionItem {
    key: string;
    asset_name: string;
    target_concept_name: string;
    relation_type: string;
    direction: string;
    reasoning: string;
}

export interface ValidateConnectionsRequest {
    asset_name: string;
    asset_content: string;
    asset_mime_type?: string;
    suggestions: ValidateConnectionItem[];
}

export interface ValidateConnectionsResponse {
    valid_keys: string[];
    removed_count: number;
    llm_explanation: string;
}

export async function validateLatentConnections(data: ValidateConnectionsRequest): Promise<ValidateConnectionsResponse> {
    const res = await exploreApi.post<ValidateConnectionsResponse>('/validate-connections', data);
    return res.data;
}

export interface AssetPreviewResponse {
    id: string;
    name: string;
    type: string;
    tags: string[];
    content: string;
    mime_type?: string;
    minio_path?: string;
    download_url?: string;
}

export async function getAssetPreview(assetId: string): Promise<AssetPreviewResponse> {
    const res = await exploreApi.get<AssetPreviewResponse>(`/asset-preview/${assetId}`);
    return res.data;
}

// --- Pathfinder (Navegador Latente) ---
// Timeout is generous: pathfinding on large graphs (variable-length Cypher) can be slow.
const analysisApi = axios.create({
    baseURL: '/api/analysis',
    headers: { 'Content-Type': 'application/json' },
    timeout: 300000, // 5 minutes – pathfinder can be slow on large graphs
});

export interface PathfinderRequest {
    source_element_id: string;
    target_element_id: string;
    mode: 'direct' | 'lateral' | 'topological';
    threshold?: number;
    topo_threshold?: number;
    k_paths?: number;
}

export interface PathfinderNodeData {
    id: string;
    label: string;
    node_type: string;
    weight_to_next?: number | null;
    file_hash?: string | null;
    mime_type?: string | null;
    download_url?: string | null;
    minio_path?: string | null;
}

export interface PathfinderEdgeData {
    source: string;
    target: string;
    weight: number | null;
    rel_type: string;
}

export interface PathfinderResponse {
    status: string;
    message: string;
    nodes: PathfinderNodeData[];
    edges: PathfinderEdgeData[];
    path_length: number;
    mode: string;
}

export async function callPathfinder(data: PathfinderRequest): Promise<PathfinderResponse> {
    const res = await analysisApi.post<PathfinderResponse>('/pathfinder', data);
    return res.data;
}

export interface PathExplanationRequest {
    tool_name: string;
    nodes: Record<string, any>[];
    edges: Record<string, any>[];
    privacy_mode?: boolean;
}

export interface PathExplanationResponse {
    explanation: string;
    status: string;
}

export async function explainAnalyticalPath(data: PathExplanationRequest): Promise<PathExplanationResponse> {
    const res = await analysisApi.post<PathExplanationResponse>('/explain-path', data);
    return res.data;
}

// --- Ontological Cleanup ---

export interface ConceptNode {
    id: string;
    name: string;
    domain?: string;
}

export interface ConceptListResponse {
    concepts: ConceptNode[];
    total: number;
}

export interface MergeRecommendation {
    cluster_id: number;
    concepts: ConceptNode[];
    similarity_score: number;
    recommended_hub_name?: string;
    recommended_hub_domain?: string;
}

export interface RecommendMergesResponse {
    recommendations: MergeRecommendation[];
    total_clusters: number;
    demote_recommendations: ConceptNode[];
}

export interface MergeConceptsRequest {
    target_name: string;
    target_domain: string;
    source_names: string[];
}

export interface MergeConceptsResponse {
    status: string;
    message: string;
    merged_count: number;
}

export async function getConcepts(): Promise<ConceptListResponse> {
    const res = await enrichmentApi.get<ConceptListResponse>('/concepts', { timeout: 300000 });
    return res.data;
}

export async function recommendConceptMerges(strategy: string = 'middle'): Promise<RecommendMergesResponse> {
    const res = await enrichmentApi.post<RecommendMergesResponse>('/concepts/recommend-merges', undefined, { params: { strategy }, timeout: 300000 });
    return res.data;
}

export async function mergeConcepts(data: MergeConceptsRequest): Promise<MergeConceptsResponse> {
    const res = await enrichmentApi.post<MergeConceptsResponse>('/concepts/merge', data, { timeout: 300000 });
    return res.data;
}

export interface DemoteConceptsRequest {
    source_names: string[];
}

export interface DemoteConceptsResponse {
    status: string;
    message: string;
    demoted_count: number;
}

export async function demoteConcepts(data: DemoteConceptsRequest): Promise<DemoteConceptsResponse> {
    const res = await enrichmentApi.post<DemoteConceptsResponse>('/concepts/demote', data, { timeout: 300000 });
    return res.data;
}

// --- Graph Schema ---

export async function getRelationTypes(): Promise<{ relation_types: string[] }> {
    const res = await analysisApi.get<{ relation_types: string[] }>('/relation-types');
    return res.data;
}

export interface GraphEntity {
    id: string;
    name: string;
    entity_type: string;
    already_connected?: boolean;
}

export async function searchGraphEntities(q: string, limit: number = 20, assetId?: string): Promise<{ entities: GraphEntity[] }> {
    const params: Record<string, any> = { q, limit };
    if (assetId) params.asset_id = assetId;
    const res = await analysisApi.get<{ entities: GraphEntity[] }>('/graph-entities', { params });
    return res.data;
}
