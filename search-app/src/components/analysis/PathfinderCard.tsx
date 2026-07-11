import { useState, useCallback, useEffect, useRef } from 'react';
import ReactFlow, {
    Controls,
    Background,
    Handle,
    useNodesState,
    useEdgesState,
    MarkerType,
    Position,
    type Node,
    type Edge,
} from 'reactflow';
import 'reactflow/dist/style.css';
import dagre from 'dagre';
import {
    Search, Route, Zap, Loader2, X, ChevronRight,
    FileText, File, Lightbulb, User, Building2, MapPin, Move, Download, ChevronUp, ChevronDown, ArrowUp, ArrowDown, Eye, EyeOff
} from 'lucide-react';

import {
    searchGraphFuzzy,
    callPathfinder,
    getAssetPreview,
    explainAnalyticalPath,
    getEntities,
    getConcepts,
    type PathfinderNodeData,
    type PathfinderResponse,
    type AssetPreviewResponse,
} from '../../lib/api';
import type { GraphFuzzyRequest } from '../../types/search';
import MediaPreview from '../search/MediaPreview';

// =================== Types ===================
interface PinnedNode {
    id: string;   // Neo4j elementId
    label: string;
    type: string;
}

// =================== Helpers ===================
// Node accent colors — fixed brand palette, do not change with theme
const NODE_COLORS: Record<string, string> = {
    Concept: '#6d28d9',
    DigitalAsset: '#1e40af',
    Person: '#be123c',
    Location: '#b45309',
    Organization: '#0369a1',
    Event: '#7c3aed',
    Project: '#065f46',
};

// Node backgrounds adapt to theme via CSS variables where possible;
// for React Flow nodes we keep light backgrounds (they render on a light canvas).
const NODE_BG: Record<string, string> = {
    Concept: '#ede9fe',
    DigitalAsset: '#dbeafe',
    Person: '#ffe4e6',
    Location: '#fef3c7',
    Organization: '#e0f2fe',
    Event: '#ede9fe',
    Project: '#d1fae5',
};

const NODE_ICONS: Record<string, React.ReactNode> = {
    DigitalAsset: <FileText size={12} />,
    Concept: <Lightbulb size={12} />,
    Person: <User size={12} />,
    Location: <MapPin size={12} />,
    Organization: <Building2 size={12} />,
};

// CRITICAL FIX: Neo4j elementIds have the format "4:uuid:number" – the colons
// are separator tokens in dagre.graphlib and cause node/edge lookups to fail silently.
// We sanitize IDs for React Flow and dagre, preserving originals in data.raw for API calls.
const sanitizeId = (id: string): string => id.replace(/:/g, '_');

function layoutPathHorizontal(rfNodes: Node[], rfEdges: Edge[]): { nodes: Node[]; edges: Edge[] } {
    const g = new dagre.graphlib.Graph();
    g.setDefaultEdgeLabel(() => ({}));
    g.setGraph({ rankdir: 'LR', nodesep: 70, ranksep: 140 });

    rfNodes.forEach(n => g.setNode(n.id, { width: 180, height: 60 }));
    rfEdges.forEach(e => g.setEdge(e.source, e.target));

    dagre.layout(g);

    return {
        nodes: rfNodes.map(n => {
            const pos = g.node(n.id);
            return {
                ...n,
                position: { x: pos.x - 90, y: pos.y - 30 },
                targetPosition: Position.Left,
                sourcePosition: Position.Right,
            };
        }),
        edges: rfEdges,
    };
}

function buildReactFlowData(response: PathfinderResponse): { nodes: Node[]; edges: Edge[] } {
    const rfNodes: Node[] = response.nodes.map(n => ({
        id: sanitizeId(n.id),
        position: { x: 0, y: 0 },
        data: { label: n.label, nodeType: n.node_type, raw: n },
        type: 'pathNode',
    }));

    const rfEdges: Edge[] = response.edges.map((e, idx) => {
        const src = sanitizeId(e.source);
        const tgt = sanitizeId(e.target);
        return {
            id: `e-${src}-${tgt}-${e.rel_type}-${idx}`,
            source: src,
            target: tgt,
            type: 'smoothstep',
            animated: true,
            label: e.weight != null ? `${e.rel_type}\n${e.weight}` : e.rel_type,
            labelStyle: { fill: '#1e293b', fontSize: 10, fontWeight: 600 },
            labelBgStyle: { fill: '#ffffff', fillOpacity: 0.95 },
            labelBgPadding: [4, 2] as [number, number],
            labelBgBorderRadius: 4,
            style: {
                stroke: e.weight != null && e.weight < 0.5 ? '#d97706' : '#4f46e5',
                strokeWidth: 2.5,
            },
            markerEnd: { type: MarkerType.ArrowClosed, color: '#4f46e5' },
        };
    });

    return layoutPathHorizontal(rfNodes, rfEdges);
}


// =================== Custom React Flow Node ===================
// React Flow renders on a light canvas, so node BG stays readable against white.
function PathNode({ data }: { data: { label: string; nodeType: string; raw: PathfinderNodeData } }) {
    const color = NODE_COLORS[data.nodeType] || '#475569';
    const bg = NODE_BG[data.nodeType] || '#f8fafc';
    return (
        <div style={{
            background: bg,
            border: `2.5px solid ${color}`,
            borderRadius: 10,
            padding: '8px 14px',
            maxWidth: 170,
            minWidth: 110,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 4,
            cursor: 'pointer',
            boxShadow: `0 2px 8px ${color}40`,
        }}>
            {/* CRITICAL: Handles are required for edges to connect */}
            <Handle type="target" position={Position.Left} style={{ background: color, width: 8, height: 8, border: '2px solid white' }} />
            <Handle type="source" position={Position.Right} style={{ background: color, width: 8, height: 8, border: '2px solid white' }} />
            <div style={{ display: 'flex', alignItems: 'center', gap: 5, color }}>
                {NODE_ICONS[data.nodeType] || <Move size={12} />}
                <span style={{ fontSize: '0.62rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.5 }}>
                    {data.nodeType}
                </span>
            </div>
            <div style={{ fontSize: '0.75rem', color: '#1e293b', textAlign: 'center', fontWeight: 600, lineHeight: 1.3 }}>
                {data.label.length > 28 ? data.label.slice(0, 28) + '…' : data.label}
            </div>
        </div>
    );
}

const NODE_TYPES = { pathNode: PathNode };

// =================== Search Panel ===================

const ENTITY_TYPES_PF = [
    { label: 'Concepto', value: 'Concept' },
    { label: 'Archivo', value: 'DigitalAsset' },
    { label: 'Persona', value: 'Person' },
    { label: 'Proyecto', value: 'Project' },
    { label: 'Lugar', value: 'Location' },
    { label: 'Organización', value: 'Organization' },
    { label: 'Evento', value: 'Event' },
    { label: 'Dispositivo', value: 'Device' },
    { label: 'Método', value: 'Method' },
];

function NodeSearchPanel({
    label,
    color,
    pinned,
    onPin,
}: {
    label: string;
    color: string;
    pinned: PinnedNode | null;
    onPin: (node: PinnedNode | null) => void;
}) {
    const [mode, setMode] = useState<'fuzzy' | 'entity'>('fuzzy');

    const [query, setQuery] = useState('');
    const [results, setResults] = useState<Array<{ id: string; label: string; type: string }>>([]);
    const [loading, setLoading] = useState(false);
    const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    const [entityType, setEntityType] = useState('Concept');
    const [entitySearch, setEntitySearch] = useState('');
    const [entityList, setEntityList] = useState<Array<{ id: string; name: string; connections: number }>>([]);
    const [entityLoading, setEntityLoading] = useState(false);

    const handleFuzzySearch = useCallback((q: string) => {
        setQuery(q);
        if (debounceRef.current) clearTimeout(debounceRef.current);
        if (!q.trim()) { setResults([]); return; }
        debounceRef.current = setTimeout(async () => {
            setLoading(true);
            try {
                const req: GraphFuzzyRequest = { query: q, alpha_cut: 0.3, limit: 8, seed_alpha: 0.7, seed_limit: 8 };
                const res = await searchGraphFuzzy(req);
                const seen = new Set<string>();
                const candidates: Array<{ id: string; label: string; type: string }> = [];
                for (const n of res.graph_topology?.nodes || []) {
                    if (!seen.has(n.id)) { seen.add(n.id); candidates.push({ id: n.id, label: n.label, type: n.type }); }
                }
                setResults(candidates.slice(0, 10));
            } catch { setResults([]); }
            finally { setLoading(false); }
        }, 400);
    }, []);

    const loadEntities = useCallback(async (type: string) => {
        setEntityLoading(true);
        setEntityList([]);
        try {
            if (type === 'Concept') {
                const res = await getConcepts();
                setEntityList(res.concepts.map(c => ({ id: c.id, name: c.name, connections: 0 })));
            } else {
                const res = await getEntities(type, '', 300);
                setEntityList(res.entities.map(e => ({ id: e.id, name: e.name, connections: e.connections })));
            }
        } catch { setEntityList([]); }
        finally { setEntityLoading(false); }
    }, []);

    const handleEntityTypeChange = (type: string) => {
        setEntityType(type);
        setEntitySearch('');
        loadEntities(type);
    };

    const switchToEntity = () => {
        setMode('entity');
        setResults([]);
        setQuery('');
        if (entityList.length === 0) loadEntities(entityType);
    };

    const filteredEntities = entityList.filter(e =>
        e.name.toLowerCase().includes(entitySearch.toLowerCase())
    );

    // ── Pinned display ──
    if (pinned) {
        return (
            <div style={{ background: `${color}15`, border: `2px solid ${color}`, borderRadius: 12, padding: '12px 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flex: 1 }}>
                <div>
                    <div style={{ fontSize: '0.65rem', color, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 4 }}>{label}</div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-body)' }}>{pinned.label}</span>
                        <span style={{ fontSize: '0.65rem', background: `${color}30`, color, padding: '1px 6px', borderRadius: 4 }}>{pinned.type}</span>
                    </div>
                </div>
                <button onClick={() => onPin(null)} style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-muted-alt)', padding: 4 }}>
                    <X size={16} />
                </button>
            </div>
        );
    }

    return (
        <div style={{ flex: 1 }}>
            <div style={{ fontSize: '0.65rem', color, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 6 }}>{label}</div>

            {/* Mode toggle */}
            <div style={{ display: 'flex', background: 'var(--bg-deep)', borderRadius: 8, padding: 3, marginBottom: 10, width: 'max-content' }}>
                {(['fuzzy', 'entity'] as const).map(m => (
                    <button key={m} onClick={() => m === 'entity' ? switchToEntity() : setMode('fuzzy')}
                        style={{ padding: '5px 14px', borderRadius: 6, border: 'none', cursor: 'pointer', fontSize: '0.75rem', fontWeight: 600, background: mode === m ? color : 'transparent', color: mode === m ? '#fff' : 'var(--text-muted-alt)', transition: 'all 0.15s' }}>
                        {m === 'fuzzy' ? '🔍 Búsqueda' : '📋 Por Tipo'}
                    </button>
                ))}
            </div>

            {/* ── FUZZY MODE ── */}
            {mode === 'fuzzy' && (
                <div style={{ position: 'relative' }}>
                    <div style={{ position: 'relative' }}>
                        <Search size={14} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted-alt)' }} />
                        <input value={query} onChange={e => handleFuzzySearch(e.target.value)} placeholder="Busca cualquier nodo"
                            style={{ width: '100%', boxSizing: 'border-box', background: 'var(--bg-surface)', border: '1px solid var(--border-surface)', borderRadius: 8, padding: '10px 12px 10px 34px', fontSize: '0.85rem', color: 'var(--text-body)', outline: 'none' }} />
                        {loading && <Loader2 size={14} style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted-alt)' }} className="animate-spin" />}
                    </div>
                    {results.length > 0 && (
                        <div style={{ position: 'absolute', top: '100%', left: 0, right: 0, background: 'var(--bg-surface)', border: '1px solid var(--border-surface)', borderRadius: 8, zIndex: 100, maxHeight: 260, overflowY: 'auto', marginTop: 4, boxShadow: 'var(--shadow-panel)' }}>
                            {results.map(r => (
                                <div key={r.id} onClick={() => { onPin({ id: r.id, label: r.label, type: r.type }); setResults([]); setQuery(''); }}
                                    style={{ padding: '10px 14px', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--border-panel)', transition: 'background 0.15s' }}
                                    onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-panel)')}
                                    onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}>
                                    <span style={{ fontSize: '0.85rem', color: 'var(--text-primary)' }}>{r.label}</span>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                        <span style={{ fontSize: '0.65rem', color: NODE_COLORS[r.type] || 'var(--text-muted-alt)', background: `${NODE_COLORS[r.type] || '#475569'}20`, padding: '1px 6px', borderRadius: 4 }}>{r.type}</span>
                                        <ChevronRight size={14} color="var(--text-dim)" />
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* ENTITY MODE */}
            {mode === 'entity' && (
                <div style={{ background: 'var(--bg-panel)', border: '1px solid var(--border-panel)', borderRadius: 12, overflow: 'hidden' }}>
                    <div style={{ display: 'flex', gap: 4, padding: '8px 10px', flexWrap: 'wrap', borderBottom: '1px solid var(--border-panel)' }}>
                        {ENTITY_TYPES_PF.map(({ label: lbl, value }) => (
                            <button key={value} onClick={() => handleEntityTypeChange(value)}
                                style={{ padding: '3px 10px', borderRadius: 20, border: 'none', cursor: 'pointer', fontSize: '0.7rem', fontWeight: 600, background: entityType === value ? color : 'var(--bg-surface)', color: entityType === value ? '#fff' : 'var(--text-muted-alt)', transition: 'all 0.15s' }}>
                                {lbl}
                            </button>
                        ))}
                    </div>
                    <div style={{ padding: '8px 10px', borderBottom: '1px solid var(--border-panel)', position: 'relative' }}>
                        <Search size={13} style={{ position: 'absolute', left: 20, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-dim)' }} />
                        <input value={entitySearch} onChange={e => setEntitySearch(e.target.value)} placeholder={`Filtrar ${entityType}...`}
                            style={{ width: '100%', boxSizing: 'border-box', background: 'var(--bg-surface)', border: '1px solid var(--border-surface)', borderRadius: 6, padding: '6px 10px 6px 28px', fontSize: '0.8rem', color: 'var(--text-body)', outline: 'none' }} />
                    </div>
                    <div style={{ maxHeight: 220, overflowY: 'auto' }}>
                        {entityLoading ? (
                            <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-dim)', display: 'flex', justifyContent: 'center', gap: 8 }}>
                                <Loader2 size={16} className="animate-spin" /> Cargando...
                            </div>
                        ) : filteredEntities.length === 0 ? (
                            <div style={{ padding: 16, textAlign: 'center', color: 'var(--text-dim)', fontSize: '0.8rem' }}>Sin resultados.</div>
                        ) : (
                            filteredEntities.map(e => (
                                <div key={e.id} onClick={() => onPin({ id: e.id, label: e.name, type: entityType })}
                                    style={{ padding: '8px 14px', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--border-panel)', transition: 'background 0.12s' }}
                                    onMouseEnter={ev => (ev.currentTarget.style.background = 'var(--bg-surface)')}
                                    onMouseLeave={ev => (ev.currentTarget.style.background = 'transparent')}>
                                    <span style={{ fontSize: '0.82rem', color: 'var(--text-subtle)', fontWeight: 500 }}>{e.name}</span>
                                    {e.connections > 0 && <span style={{ fontSize: '0.65rem', color: 'var(--text-dim)' }}>{e.connections} conex.</span>}
                                </div>
                            ))
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}

// =================== Asset Detail Panel ===================
function AssetDetailPanel({ node, onClose }: { node: PathfinderNodeData; onClose: () => void }) {
    const [preview, setPreview] = useState<AssetPreviewResponse | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        setLoading(true);
        getAssetPreview(node.id)
            .then(setPreview)
            .catch(() => setPreview(null))
            .finally(() => setLoading(false));
    }, [node.id]);

    return (
        <div style={{
            background: 'var(--bg-panel)',
            border: '1px solid var(--border-surface)',
            borderRadius: 16,
            overflow: 'hidden',
            marginTop: 16,
        }}>
            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 20px', background: 'var(--bg-surface)', borderBottom: '1px solid var(--border-surface)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    {NODE_ICONS[node.node_type] || <File size={16} />}
                    <span style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-body)' }}>{node.label}</span>
                    <span style={{ fontSize: '0.65rem', padding: '2px 8px', borderRadius: 10, background: 'var(--bg-surface-hover)', color: 'var(--text-subtle)' }}>{node.node_type}</span>
                </div>
                <button onClick={onClose} style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-muted-alt)' }}>
                    <X size={18} />
                </button>
            </div>

            {/* Body */}
            <div style={{ padding: 20 }}>
                {loading ? (
                    <div style={{ display: 'flex', justifyContent: 'center', padding: 32 }}>
                        <Loader2 className="animate-spin text-amber-500" size={28} />
                    </div>
                ) : preview ? (
                    <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
                        {/* Meta column */}
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, minWidth: 200, flex: '0 0 220px' }}>
                            {preview.tags?.length > 0 && (
                                <div>
                                    <div style={{ fontSize: '0.6rem', color: 'var(--text-muted-alt)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 6 }}>ETIQUETAS</div>
                                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                                        {preview.tags.map((t, i) => (
                                            <span key={i} style={{ fontSize: '0.65rem', background: '#92400e30', color: '#fbbf24', border: '1px solid #92400e50', padding: '1px 8px', borderRadius: 12 }}>
                                                #{t}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}
                            {preview.mime_type && (
                                <div>
                                    <div style={{ fontSize: '0.6rem', color: 'var(--text-muted-alt)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 4 }}>TIPO</div>
                                    <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', fontFamily: 'monospace' }}>{preview.mime_type}</div>
                                </div>
                            )}
                        </div>

                        {/* Content column */}
                        <div style={{ flex: 1, minWidth: 240, display: 'flex', flexDirection: 'column', gap: 12 }}>
                            {(preview.download_url || preview.minio_path) && (
                                <div>
                                    <div style={{ fontSize: '0.6rem', color: 'var(--text-muted-alt)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 8 }}>VISTA PREVIA</div>
                                    <MediaPreview url={preview.download_url || undefined} path={preview.minio_path || undefined} />
                                </div>
                            )}
                            {preview.content && preview.content !== 'No textual content available' && (
                                <div>
                                    <div style={{ fontSize: '0.6rem', color: 'var(--text-muted-alt)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 8 }}>CONTENIDO EXTRAÍDO</div>
                                    <div style={{ background: 'var(--bg-deep)', border: '1px solid var(--border-surface)', borderRadius: 8, padding: 14, fontSize: '0.78rem', color: 'var(--text-code)', whiteSpace: 'pre-wrap', fontFamily: 'monospace', lineHeight: 1.6, maxHeight: 280, overflowY: 'auto' }} className="custom-scrollbar">
                                        {preview.content}
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                ) : (
                    <div style={{ color: 'var(--text-dim)', textAlign: 'center', padding: 24 }}>No se pudo cargar la vista previa.</div>
                )}
            </div>
        </div>
    );
}

// =================== Main Component ===================
export default function PathfinderCard() {
    const [sourceNode, setSourceNode] = useState<PinnedNode | null>(null);
    const [targetNode, setTargetNode] = useState<PinnedNode | null>(null);
    const [mode, setMode] = useState<'direct' | 'lateral' | 'topological'>('direct');
    const [threshold, setThreshold] = useState<number>(0.85);
    const [topoThreshold, setTopoThreshold] = useState<number>(0.0);
    const [kPaths, setKPaths] = useState<number>(3);
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState<PathfinderResponse | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [selectedNode, setSelectedNode] = useState<PathfinderNodeData | null>(null);

    // LLM Explanation State
    const [explanation, setExplanation] = useState<string | null>(null);
    const [explaining, setExplaining] = useState(false);
    const [privacyMode, setPrivacyMode] = useState(false);
    const [showExplanation, setShowExplanation] = useState(true);

    // React Flow
    const [rfNodes, setRfNodes, onNodesChange] = useNodesState([]);
    const [rfEdges, setRfEdges, onEdgesChange] = useEdgesState([]);

    const handleTrace = useCallback(async () => {
        if (!sourceNode || !targetNode) return;
        setLoading(true);
        setError(null);
        setResult(null);
        setSelectedNode(null);
        setExplanation(null);
        setRfNodes([]);
        setRfEdges([]);
        try {
            const res = await callPathfinder({
                source_element_id: sourceNode.id,
                target_element_id: targetNode.id,
                mode,
                threshold: mode === 'lateral' ? threshold : undefined,
                topo_threshold: mode === 'topological' ? topoThreshold : undefined,
                k_paths: kPaths,
            });
            setResult(res);
            if (res.status === 'success' && res.nodes.length > 0) {
                const { nodes: n, edges: e } = buildReactFlowData(res);
                setRfNodes(n);
                setRfEdges(e);
            } else {
                setError(res.message);
            }
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'Error desconocido');
        } finally {
            setLoading(false);
        }
    }, [sourceNode, targetNode, mode, threshold, topoThreshold, kPaths, setRfNodes, setRfEdges]);

    const onNodeClick = useCallback((_: React.MouseEvent, rfNode: Node) => {
        const raw: PathfinderNodeData | undefined = rfNode.data?.raw;
        if (raw) setSelectedNode(raw);
    }, []);

    const handleExplain = async () => {
        if (!result || !result.nodes.length) return;
        setExplaining(true);
        setExplanation(null);
        try {
            const res = await explainAnalyticalPath({
                tool_name: 'pathfinder',
                nodes: result.nodes,
                edges: result.edges,
                privacy_mode: privacyMode,
            });
            if (res.status === 'success') {
                setExplanation(res.explanation);
            } else {
                setExplanation(`⚠️ ${res.explanation}`);
            }
        } catch (err: unknown) {
            setExplanation('⚠️ Error al generar la explicación: ' + (err instanceof Error ? err.message : String(err)));
        } finally {
            setExplaining(false);
        }
    };

    const handleExportJson = () => {
        if (!result) return;
        const exportData = {
            exported_at: new Date().toISOString(),
            mode: result.mode,
            source: sourceNode ? { id: sourceNode.id, label: sourceNode.label, type: sourceNode.type } : null,
            target: targetNode ? { id: targetNode.id, label: targetNode.label, type: targetNode.type } : null,
            path_length: result.path_length,
            message: result.message,
            llm_explanation: explanation || null,
            options: {
                privacy_mode: privacyMode,
                threshold: result.mode === 'lateral' ? threshold : undefined
            },
            nodes: result.nodes.map(n => ({
                id: n.id,
                label: n.label,
                node_type: n.node_type,
                weight_to_next: n.weight_to_next ?? null,
                file_hash: n.file_hash ?? null,
                mime_type: n.mime_type ?? null,
            })),
            edges: result.edges.map(e => ({
                source: e.source,
                target: e.target,
                rel_type: e.rel_type,
                weight: e.weight ?? null,
            })),
        };
        const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        const srcLabel = (sourceNode?.label ?? 'origin').replace(/[^a-z0-9]/gi, '_').toLowerCase();
        const tgtLabel = (targetNode?.label ?? 'target').replace(/[^a-z0-9]/gi, '_').toLowerCase();
        a.href = url;
        a.download = `pathfinder_${srcLabel}_to_${tgtLabel}_${Date.now()}.json`;
        a.click();
        URL.revokeObjectURL(url);
    };

    const canTrace = !!sourceNode && !!targetNode && !loading;

    return (
        <div style={{ padding: '24px 32px', display: 'flex', flexDirection: 'column', gap: 20 }}>
            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 4 }}>
                <div style={{ width: 44, height: 44, borderRadius: 10, background: '#0e749020', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <Route size={22} color="#06b6d4" />
                </div>
                <div>
                    <h1 style={{ margin: 0, fontSize: '1.6rem', fontWeight: 800, background: 'linear-gradient(to right, #06b6d4, #6366f1)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                        Navegador Latente
                    </h1>
                    <p style={{ margin: 0, color: 'var(--text-muted-alt)', fontSize: '0.9rem' }}>
                        Traza el camino semántico entre dos ideas de tu grafo.
                    </p>
                </div>
            </div>

            {/* Control Panel */}
            <div style={{ background: 'var(--bg-panel)', border: '1px solid var(--border-panel)', borderRadius: 16, padding: 20, display: 'flex', flexDirection: 'column', gap: 16 }}>
                {/* Node selectors */}
                <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>
                    <NodeSearchPanel label="Nodo Origen" color="#06b6d4" pinned={sourceNode} onPin={setSourceNode} />
                    <div style={{ display: 'flex', alignItems: 'center', paddingTop: 28, color: 'var(--text-dim)', flexShrink: 0 }}>
                        <ChevronRight size={20} />
                    </div>
                    <NodeSearchPanel label="Nodo Destino" color="#a855f7" pinned={targetNode} onPin={setTargetNode} />
                </div>

                {/* Mode + Action row */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                    <div style={{ display: 'flex', background: 'var(--bg-surface)', borderRadius: 8, padding: 3 }}>
                        {(['direct', 'lateral', 'topological'] as const).map(m => (
                            <button
                                key={m}
                                onClick={() => setMode(m)}
                                style={{
                                    padding: '6px 16px',
                                    borderRadius: 6,
                                    border: 'none',
                                    cursor: 'pointer',
                                    fontSize: '0.8rem',
                                    fontWeight: 600,
                                    background: mode === m ? (m === 'direct' ? '#0e7490' : m === 'lateral' ? '#92400e' : '#4d7c0f') : 'transparent',
                                    color: mode === m ? '#fff' : 'var(--text-muted-alt)',
                                    transition: 'all 0.2s',
                                }}
                            >
                                {m === 'direct' ? '⚡ Directo' : m === 'lateral' ? '🌀 Lateral' : '🕸️ Topológico'}
                            </button>
                        ))}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', flex: 1 }}>
                        {mode === 'direct' ? 'Camino más corto sin restricciones.' : mode === 'lateral' ? `Evita conexiones muy fuertes (>${threshold}), forzando rutas creativas.` : topoThreshold > 0 ? `Solo saltos con peso ≥ ${topoThreshold.toFixed(2)} — conexiones débiles eliminadas del grafo.` : 'Menor cantidad de saltos, ignorando la fuerza de la conexión.'}
                    </div>
                    {/* Paths Count Select */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'var(--bg-surface)', padding: '6px 12px', borderRadius: 8, border: '1px solid var(--border-surface)' }}>
                        <span style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', fontWeight: 600, textTransform: 'uppercase' }}>Caminos:</span>
                        <select
                            value={kPaths}
                            onChange={e => setKPaths(Number(e.target.value))}
                            style={{
                                background: 'transparent',
                                border: 'none',
                                color: 'var(--text-primary)',
                                fontWeight: 700,
                                fontSize: '0.8rem',
                                outline: 'none',
                                cursor: 'pointer'
                            }}
                        >
                            <option value={1}>1</option>
                            <option value={3}>3</option>
                            <option value={5}>5</option>
                            <option value={10}>10</option>
                        </select>
                    </div>
                    {mode === 'lateral' && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'var(--bg-surface)', padding: '6px 12px', borderRadius: 8, border: '1px solid var(--border-surface)' }}>
                            <span style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', fontWeight: 600, textTransform: 'uppercase' }}>Umbral:</span>
                            <select
                                value={threshold}
                                onChange={e => setThreshold(Number(e.target.value))}
                                style={{
                                    background: 'transparent',
                                    border: 'none',
                                    color: 'var(--text-primary)',
                                    fontWeight: 700,
                                    fontSize: '0.8rem',
                                    outline: 'none',
                                    cursor: 'pointer'
                                }}
                            >
                                <option value={0.6}>0.6 (Muy Creativo)</option>
                                <option value={0.85}>0.85 (Equilibrado)</option>
                                <option value={0.9}>0.9 (Suave)</option>
                                <option value={0.95}>0.95 (Casi Directo)</option>
                            </select>
                        </div>
                    )}
                    {mode === 'topological' && (
                        <div style={{
                            display: 'flex', alignItems: 'center', gap: 10,
                            background: 'var(--bg-surface)', padding: '8px 14px',
                            borderRadius: 8, border: `1px solid ${topoThreshold > 0 ? '#4d7c0f' : 'var(--border-surface)'}`,
                            transition: 'border-color 0.2s', minWidth: 260,
                        }}>
                            <span style={{ fontSize: '0.7rem', color: '#84cc16', fontWeight: 700, textTransform: 'uppercase', whiteSpace: 'nowrap', flexShrink: 0 }}>
                                🔗 Umbral de Conexión:
                            </span>
                            <input
                                id="topo-threshold-slider"
                                type="range"
                                min={0}
                                max={1}
                                step={0.05}
                                value={topoThreshold}
                                onChange={e => setTopoThreshold(Number(e.target.value))}
                                style={{ flex: 1, accentColor: '#84cc16', cursor: 'pointer' }}
                            />
                            <span style={{
                                fontSize: '0.85rem', fontWeight: 700,
                                color: topoThreshold > 0 ? '#84cc16' : 'var(--text-dim)',
                                minWidth: 34, textAlign: 'right',
                                fontVariantNumeric: 'tabular-nums',
                            }}>
                                {topoThreshold > 0 ? topoThreshold.toFixed(2) : 'Off'}
                            </span>
                        </div>
                    )}
                    <button
                        onClick={handleTrace}
                        disabled={!canTrace}
                        style={{
                            padding: '10px 24px',
                            borderRadius: 10,
                            border: 'none',
                            cursor: canTrace ? 'pointer' : 'not-allowed',
                            background: canTrace ? 'linear-gradient(135deg, #06b6d4, #6366f1)' : 'var(--bg-surface)',
                            color: canTrace ? '#fff' : 'var(--text-dim)',
                            fontWeight: 700,
                            fontSize: '0.9rem',
                            display: 'flex',
                            alignItems: 'center',
                            gap: 8,
                            transition: 'all 0.2s',
                        }}
                    >
                        {loading ? <Loader2 size={16} className="animate-spin" /> : <Zap size={16} />}
                        Trazar Camino
                    </button>
                </div>
            </div>

            {/* Error */}
            {error && (
                <div style={{ background: '#7f1d1d30', border: '1px solid #7f1d1d', borderRadius: 12, padding: '12px 16px', color: '#fca5a5', fontSize: '0.85rem' }}>
                    ⚠️ {error}
                </div>
            )}

            {/* React Flow Canvas */}
            {rfNodes.length > 0 && (
                <div style={{ background: '#f8fafc', border: '1px solid var(--border-subtle)', borderRadius: 16, overflow: 'hidden' }}>
                    {/* Status bar */}
                    {result && (
                        <div style={{ padding: '10px 20px', background: 'var(--bg-surface)', borderBottom: '1px solid var(--border-surface)', display: 'flex', alignItems: 'center', gap: 12 }}>
                            <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#22c55e', display: 'inline-block' }} />
                            <span style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)' }}>{result.message}</span>
                            <span style={{ marginLeft: 'auto', fontSize: '0.75rem', color: 'var(--text-dim)' }}>{result.path_length} salto(s) • Modo {result.mode}</span>
                        </div>
                    )}
                    {/* React Flow always renders on a light canvas */}
                    <div style={{ height: 380 }}>
                        <ReactFlow
                            nodes={rfNodes}
                            edges={rfEdges}
                            onNodesChange={onNodesChange}
                            onEdgesChange={onEdgesChange}
                            onNodeClick={onNodeClick}
                            nodeTypes={NODE_TYPES}
                            fitView
                            fitViewOptions={{ padding: 0.3 }}
                            attributionPosition="bottom-right"
                            proOptions={{ hideAttribution: true }}
                        >
                            <Controls />
                            <Background color="#e2e8f0" gap={20} />
                        </ReactFlow>
                    </div>
                    <div style={{ padding: '10px 20px', background: 'var(--bg-surface)', borderTop: '1px solid var(--border-surface)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>
                            💡 Haz clic en cualquier nodo para ver sus detalles abajo.
                        </span>

                        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                            {/* Privacy Toggle */}
                            <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }} title="Proteger datos: El modelo LLM no entrenará con esta consulta ni su contexto">
                                <div style={{
                                    width: 32, height: 18, borderRadius: 16,
                                    background: privacyMode ? '#f59e0b' : 'var(--bg-surface-hover)',
                                    position: 'relative',
                                    transition: 'background 0.2s',
                                }}>
                                    <div style={{
                                        position: 'absolute', top: 2, left: privacyMode ? 16 : 2,
                                        width: 14, height: 14, borderRadius: '50%',
                                        background: '#fff', transition: 'left 0.2s'
                                    }} />
                                </div>
                                <span style={{ fontSize: '0.75rem', color: privacyMode ? '#f59e0b' : 'var(--text-muted-alt)', fontWeight: 600 }}>
                                    Privacidad
                                </span>
                                <input
                                    type="checkbox"
                                    checked={privacyMode}
                                    onChange={(e) => setPrivacyMode(e.target.checked)}
                                    style={{ display: 'none' }}
                                />
                            </label>

                            <button
                                onClick={handleExportJson}
                                title="Exportar camino a JSON"
                                style={{
                                    display: 'flex', alignItems: 'center', gap: 6,
                                    padding: '6px 14px',
                                    background: 'var(--bg-surface)',
                                    color: 'var(--text-tertiary)',
                                    border: '1px solid var(--border-surface)',
                                    borderRadius: 8,
                                    fontSize: '0.8rem',
                                    fontWeight: 600,
                                    cursor: 'pointer',
                                    transition: 'all 0.2s'
                                }}
                                onMouseEnter={e => { e.currentTarget.style.color = 'var(--text-body)'; e.currentTarget.style.borderColor = 'var(--text-dim)'; }}
                                onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-tertiary)'; e.currentTarget.style.borderColor = 'var(--border-surface)'; }}
                            >
                                <Download size={14} /> Exportar JSON
                            </button>

                            <button
                                onClick={handleExplain}
                                disabled={explaining}
                                style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: 6,
                                    padding: '6px 14px',
                                    background: 'linear-gradient(to right, #4c1d95, #7e22ce)',
                                    color: '#fff',
                                    border: 'none',
                                    borderRadius: 8,
                                    fontSize: '0.8rem',
                                    fontWeight: 600,
                                    cursor: explaining ? 'not-allowed' : 'pointer',
                                    opacity: explaining ? 0.7 : 1,
                                    transition: 'all 0.2s'
                                }}
                            >
                                {explaining ? <Loader2 size={14} className="animate-spin" /> : <span>🪄</span>}
                                Explicar Camino con IA
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Explanation Panel */}
            {explanation && (
                <div style={{
                    background: 'var(--bg-panel)',
                    borderRadius: 16,
                    border: '1px solid var(--border-panel)',
                    padding: '20px 24px',
                    position: 'relative',
                    overflow: 'hidden',
                    transition: 'all 0.3s'
                }}>
                    <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 4, background: 'linear-gradient(to right, #a855f7, #3b82f6)' }} />
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: showExplanation ? 16 : 0 }}>
                        <h3 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-body)', fontSize: '1.1rem' }}>
                            <span>🪄</span> Explicación del Camino
                        </h3>
                        <button
                            onClick={() => setShowExplanation(!showExplanation)}
                            style={{
                                background: 'transparent', border: '1px solid var(--border-surface)', borderRadius: 8,
                                display: 'flex', alignItems: 'center', gap: 6, padding: '4px 10px',
                                color: 'var(--text-tertiary)', cursor: 'pointer', transition: 'all 0.2s', fontSize: '0.75rem', fontWeight: 600
                            }}
                            onMouseEnter={e => { e.currentTarget.style.color = 'var(--text-body)'; e.currentTarget.style.background = 'var(--bg-surface)'; }}
                            onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-tertiary)'; e.currentTarget.style.background = 'transparent'; }}
                        >
                            {showExplanation ? <EyeOff size={14} /> : <Eye size={14} />}
                            {showExplanation ? 'Ocultar' : 'Mostrar'}
                        </button>
                    </div>
                    {showExplanation && (
                        <div style={{
                            color: 'var(--text-code)',
                            lineHeight: 1.6,
                            fontSize: '0.95rem',
                            whiteSpace: 'pre-wrap',
                            background: 'var(--bg-deep)',
                            padding: 16,
                            borderRadius: 12,
                            border: '1px solid var(--border-panel)'
                        }}>
                            {explanation}
                        </div>
                    )}
                </div>
            )}

            {/* Asset Detail Panel */}
            {selectedNode && (
                <AssetDetailPanel node={selectedNode} onClose={() => setSelectedNode(null)} />
            )}

            {/* Floating Navigation Controls */}
            <div style={{
                position: 'fixed',
                bottom: 32,
                right: 32,
                display: 'flex',
                flexDirection: 'column',
                gap: 12,
                zIndex: 1000
            }}>
                <button
                    onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
                    title="Ir arriba"
                    style={{
                        width: 44, height: 44, borderRadius: '50%',
                        background: 'var(--bg-surface)', border: '1px solid var(--border-surface)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        color: 'var(--text-body)', cursor: 'pointer',
                        boxShadow: 'var(--shadow-panel)',
                        transition: 'all 0.2s'
                    }}
                    onMouseEnter={e => { e.currentTarget.style.background = 'var(--bg-surface-hover)'; e.currentTarget.style.transform = 'translateY(-2px)'; }}
                    onMouseLeave={e => { e.currentTarget.style.background = 'var(--bg-surface)'; e.currentTarget.style.transform = 'translateY(0)'; }}
                >
                    <ArrowUp size={20} />
                </button>
                <button
                    onClick={() => window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' })}
                    title="Ir abajo"
                    style={{
                        width: 44, height: 44, borderRadius: '50%',
                        background: 'var(--bg-surface)', border: '1px solid var(--border-surface)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        color: 'var(--text-body)', cursor: 'pointer',
                        boxShadow: 'var(--shadow-panel)',
                        transition: 'all 0.2s'
                    }}
                    onMouseEnter={e => { e.currentTarget.style.background = 'var(--bg-surface-hover)'; e.currentTarget.style.transform = 'translateY(2px)'; }}
                    onMouseLeave={e => { e.currentTarget.style.background = 'var(--bg-surface)'; e.currentTarget.style.transform = 'translateY(0)'; }}
                >
                    <ArrowDown size={20} />
                </button>
            </div>
        </div>
    );
}
