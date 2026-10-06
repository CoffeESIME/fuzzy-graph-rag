import type { PathfinderEdgeData, PathfinderNodeData, PathfinderPath, PathfinderResponse, PathfinderExplanation } from '../types/pathfinder';

export function explanationFor(entries: PathfinderExplanation[], pathId: string | null) {
    return entries.filter(e => e.path_id === pathId).at(-1)?.explanation ?? null;
}
export function readPathfinderExplanations(value: unknown): PathfinderExplanation[] {
    if (!record(value)) return [];
    if (Array.isArray(value.explanations)) return value.explanations.filter((e): e is PathfinderExplanation => record(e) && (e.path_id === null || typeof e.path_id === 'string') && Array.isArray(e.path_ids) && e.path_ids.every(id => typeof id === 'string') && typeof e.explanation === 'string' && (e.generated_at === null || typeof e.generated_at === 'string') && (e.privacy_mode === null || typeof e.privacy_mode === 'boolean'));
    return typeof value.llm_explanation === 'string' && value.llm_explanation ? [{ path_id: typeof value.explanation_path_id === 'string' ? value.explanation_path_id : null, path_ids: [], explanation: value.llm_explanation, generated_at: null, privacy_mode: null }] : [];
}
export function explanationInput(result: PathfinderResponse, selected: PathfinderPath | null) {
    return { nodes: selected?.nodes ?? result.nodes, edges: selected?.edges ?? result.edges, paths: selected ? [selected] : result.paths ?? [] };
}

// Sequence identity is independent of parallel relationship IDs and weights.
export const routeSignature = (path: PathfinderPath) => JSON.stringify(path.nodes.map(n => n.id));
export function routeGroups(paths: PathfinderPath[]) {
    const groups = new Map<string, { path: PathfinderPath; variants: PathfinderPath[] }>();
    for (const path of paths) {
        const signature = routeSignature(path);
        const group = groups.get(signature);
        if (group) group.variants.push(path);
        else groups.set(signature, { path, variants: [path] });
    }
    return [...groups.values()];
}
export const edgeKey = (e: PathfinderEdgeData) => e.id ?? JSON.stringify([e.source, e.target, e.rel_type, e.raw_weight ?? e.weight]);
export function combinedGraph(paths: PathfinderPath[]) {
    const nodes = new Map<string, PathfinderNodeData>();
    const edges = new Map<string, PathfinderEdgeData>();
    paths.forEach(p => { p.nodes.forEach(n => nodes.set(n.id, n)); p.edges.forEach(e => edges.set(edgeKey(e), e)); });
    return { nodes: [...nodes.values()], edges: [...edges.values()] };
}

/** Canvas occurrences preserve cycles in a selected route; all-view merges identities. */
export function routeView(result: PathfinderResponse, selectedId: string | null) {
    const groups = routeGroups(result.paths ?? []);
    const selected = result.paths?.find(p => p.id === selectedId);
    if (selected) {
        return {
            nodes: selected.nodes.map((raw, i) => ({ id: `step-${i}`, position: { x: i * 260, y: 0 }, data: { label: raw.label, nodeType: raw.node_type, raw, role: `${i === 0 ? 'Origen · ' : i === selected.nodes.length - 1 ? 'Destino · ' : ''}Paso ${i + 1}` } })),
            edges: selected.edges.map((raw, i) => ({ id: `step-edge-${i}`, source: `step-${i}`, target: `step-${i + 1}`, data: { relation: raw.rel_type, weight: raw.weight, raw, routeLabel: `R${groups.findIndex(g => routeSignature(g.path) === routeSignature(selected)) + 1}` } })),
        };
    }
    const graph = groups.length ? combinedGraph(groups.map(g => g.path)) : result;
    const ids = new Map(graph.nodes.map((n, i) => [n.id, `node-${i}`]));
    return {
        nodes: graph.nodes.map((raw, i) => ({ id: ids.get(raw.id)!, position: { x: i * 240, y: 0 }, data: { label: raw.label, nodeType: raw.node_type, raw, role: groups.map((g, j) => g.path.nodes.some(n => n.id === raw.id) ? `R${j + 1}` : null).filter(Boolean).join(' · ') } })),
        edges: graph.edges.map((raw, i) => ({ id: `edge-${i}`, source: ids.get(raw.source)!, target: ids.get(raw.target)!, data: { relation: raw.rel_type, weight: raw.weight, raw, routeLabel: groups.map((g, j) => g.path.edges.some(e => edgeKey(e) === edgeKey(raw)) ? `R${j + 1}` : null).filter(Boolean).join(' · ') } })),
    };
}

const durableNode = (source: PathfinderNodeData) => {
    const node = { ...source };
    delete node.download_url;
    return node;
};
export function exportPathfinder(result: PathfinderResponse, explanation: string | null = null, explanationPathId: string | null = null, explanations?: PathfinderExplanation[]) {
    return {
        ...result, schema_version: result.paths?.length ? 2 : 1, tool: 'pathfinder',
        generated_at: result.generated_at ?? null, exported_at: new Date().toISOString(),
        source: result.source ? durableNode(result.source) : null,
        target: result.target ? durableNode(result.target) : null,
        nodes: result.nodes.map(durableNode),
        paths: result.paths?.map(p => ({ ...p, nodes: p.nodes.map(durableNode) })),
        llm_explanation: explanation, explanation_path_id: explanationPathId,
        explanations: explanations ?? readPathfinderExplanations({ llm_explanation: explanation, explanation_path_id: explanationPathId }),
    };
}

function record(value: unknown): value is Record<string, unknown> { return !!value && typeof value === 'object'; }
function node(value: unknown): value is PathfinderNodeData {
    return record(value) && typeof value.id === 'string' && typeof value.label === 'string' && typeof value.node_type === 'string';
}
function edge(value: unknown): value is PathfinderEdgeData {
    return record(value) && typeof value.source === 'string' && typeof value.target === 'string' && typeof value.rel_type === 'string' && (value.weight === null || (typeof value.weight === 'number' && Number.isFinite(value.weight)));
}
/** Legacy unions remain unions: route order is never inferred from their node array. */
export function readSavedPathfinder(value: unknown): PathfinderResponse | null {
    if (!record(value) || !Array.isArray(value.nodes) || !value.nodes.every(node) || !Array.isArray(value.edges) || !value.edges.every(edge)) return null;
    if (value.schema_version !== undefined && value.schema_version !== 1 && value.schema_version !== 2) return null;
    const ids = new Set(value.nodes.map(n => n.id));
    if (!value.edges.every(e => ids.has(e.source) && ids.has(e.target))) return null;
    if (value.schema_version === 2) {
        if (!Array.isArray(value.paths) || !value.paths.length) return null;
        const pathIds = new Set<string>();
        for (const p of value.paths) {
            if (!record(p) || typeof p.id !== 'string' || pathIds.has(p.id) || !Number.isInteger(p.rank) || typeof p.mode !== 'string' || !Array.isArray(p.nodes) || !p.nodes.every(node) || !Array.isArray(p.edges) || !p.edges.every(edge) || p.nodes.length !== p.edges.length + 1 || p.hop_count !== p.edges.length || !record(p.metrics) || !record(p.parameters)) return null;
            const orderedNodes = p.nodes;
            if (!p.edges.every((e, i) => (e.source === orderedNodes[i].id && e.target === orderedNodes[i + 1].id) || (e.target === orderedNodes[i].id && e.source === orderedNodes[i + 1].id))) return null;
            pathIds.add(p.id);
        }
    }
    const paths = value.schema_version === 2 ? value.paths as PathfinderPath[] : [];
    return { ...value, status: 'success', message: typeof value.message === 'string' ? value.message : 'Archivo guardado', mode: typeof value.mode === 'string' ? value.mode : 'legacy', path_length: typeof value.path_length === 'number' ? value.path_length : 0, nodes: value.nodes, edges: value.edges, paths } as PathfinderResponse;
}
