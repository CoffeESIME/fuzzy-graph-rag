export type PathfinderMode = 'direct' | 'lateral' | 'topological';
export interface PathfinderExplanation {
    path_id: string | null;
    path_ids: string[];
    explanation: string;
    generated_at: string | null;
    privacy_mode: boolean | null;
}
export interface PathfinderRequest {
    source_element_id: string; target_element_id: string; mode: PathfinderMode;
    threshold?: number; topo_threshold?: number; k_paths?: number;
}
export interface PathfinderNodeData {
    id: string; label: string; node_type: string;
    weight_to_next?: number | null; file_hash?: string | null; mime_type?: string | null;
    download_url?: string | null; minio_path?: string | null;
}
export interface PathfinderEdgeData {
    id?: string | null; source: string; target: string; rel_type: string; weight: number | null;
    raw_weight?: unknown; traversal_source?: string | null; traversal_target?: string | null;
    reasoning?: string | null; provenance?: Record<string, unknown>;
}
export interface PathfinderParameters {
    k_paths: number; requested_k_paths: number; max_hops: number;
    lateral_threshold: number | null; topological_threshold: number | null;
}
export interface PathfinderPath {
    id: string; rank: number; mode: string; signature: string; duplicate_of?: string | null;
    nodes: PathfinderNodeData[]; edges: PathfinderEdgeData[]; hop_count: number;
    metrics: { cost: number | null; min_weight: number | null; missing_weight_count: number };
    parameters: PathfinderParameters;
}
export interface PathfinderResponse {
    status: string; message: string; nodes: PathfinderNodeData[]; edges: PathfinderEdgeData[];
    path_length: number; mode: string; paths?: PathfinderPath[];
    raw_result_count?: number; unique_route_count?: number; generated_at?: string | null;
    algorithm_version?: string; parameters?: PathfinderParameters | null;
    source?: PathfinderNodeData | null; target?: PathfinderNodeData | null;
}
