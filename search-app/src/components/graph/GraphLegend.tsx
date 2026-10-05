import { canonicalType, nodeColors, shapeFor } from './visualSystem';

export function TypeGlyph({ type, size = 14 }: { type: string; size?: number }) {
    const shape = shapeFor(type);
    return <svg width={size} height={size} viewBox="0 0 20 20" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2">
        {shape === 'circle' ? <circle cx="10" cy="10" r="7" /> : shape === 'diamond' ? <path d="M10 1 19 10 10 19 1 10Z" /> : <rect x="3" y="3" width="14" height="14" rx="1" />}
    </svg>;
}
export default function GraphLegend({ types = [], kinds = [], weighted = false }: { types?: string[]; kinds?: string[]; weighted?: boolean }) {
    return <div className="graph-legend" aria-label="Leyenda">
        {[...new Set(types.map(canonicalType))].map(type => <span key={type}><i style={{ color: nodeColors[type] ?? '#888' }}><TypeGlyph type={type} /></i>{type}</span>)}
        {[...new Set(kinds)].map(kind => <span key={kind}><svg width="30" height="14" aria-hidden="true"><path d="M0 7H30" stroke="currentColor" strokeWidth="2" strokeDasharray={kind === 'fuzzy' ? '7 4' : kind === 'serendipity' ? '2 5' : undefined} /></svg>{kind === 'normal' ? 'Relación' : kind === 'fuzzy' ? 'Fuzzy' : 'Serendipity'}</span>)}
        {weighted && <span>Peso: valor numérico · grosor proporcional (0–1)</span>}
    </div>;
}
