import type { Node, Edge } from 'reactflow';

// Presentation metadata only. Unknown types retain their original name.
export const nodeColors: Record<string, string> = {
    Concept: '#8974b5', DigitalAsset: '#5289b5', Person: '#bc7b51', Author: '#bc7b51',
    Book: '#9c8051', Document: '#5289b5', Image: '#ad6e96', Audio: '#698f8d',
    Video: '#7c82ba', Tag: '#8b819f', Event: '#b18b45', Location: '#8c9460',
    Organization: '#668fa9', Project: '#8d869e', Device: '#778c9b', Method: '#967b9f',
};
export const communityColors = ['#6961a8', '#a76837', '#387d98', '#9b557c', '#677f42', '#957132', '#487f77', '#746b88', '#98635d', '#536d9c', '#837c42', '#8c608e'];
export function canonicalType(type: unknown): string { return type === 'Asset' ? 'DigitalAsset' : typeof type === 'string' ? type : 'Entity'; }
export function visualNode(node: Node) {
    const raw = node.data.raw ?? node.data.fullData ?? node.data.originalNode ?? node.data;
    return {
        type: canonicalType(node.data.nodeType ?? raw.node_type ?? raw.type),
        label: String(raw.label && typeof raw.label === 'string' ? raw.label : raw.name ?? (typeof node.data.label === 'string' ? node.data.label : node.id)),
        raw,
    };
}
export function edgeVisual(edge: Edge) {
    const relation = String(edge.data?.relation ?? edge.data?.raw?.rel_type ?? (typeof edge.label === 'string' ? edge.label.split('\n')[0] : '') ?? '');
    const weight = edge.data?.weight ?? edge.data?.raw?.weight;
    const kind = edge.data?.kind === 'serendipity' ? 'serendipity' : /fuzzy/i.test(relation) ? 'fuzzy' : 'normal';
    return { relation, weight: typeof weight === 'number' && Number.isFinite(weight) ? weight : undefined, kind, dash: kind === 'serendipity' ? '2 6' : kind === 'fuzzy' ? '7 4' : undefined };
}
export function shapeFor(type: string) { return ['Person', 'Author'].includes(type) ? 'diamond' : type === 'Concept' ? 'circle' : 'square'; }
export function cssColor(element: Element, token: string) { return getComputedStyle(element).getPropertyValue(token).trim(); }
