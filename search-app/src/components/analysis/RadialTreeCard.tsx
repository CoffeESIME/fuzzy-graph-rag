import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import ReactFlow, {
    Controls,
    Background,
    useNodesState,
    useEdgesState,
} from 'reactflow';
import type { Node, Edge } from 'reactflow';
import 'reactflow/dist/style.css';
import { RefreshCw, Loader2, Network, Info } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface GraphNode {
    id: string;
    level: number;
    type?: string;
    parent?: string | null;
}

interface GraphEdge {
    source: string;
    target: string;
}

interface AnalysisResponse {
    tool: string;
    status: string;
    message: string;
    mock_data: {
        root: string;
        nodes: GraphNode[];
        edges: GraphEdge[];
        method?: string;
    };
}

type RadialMode = 'standard' | 'fuzzy';

const NARRATIVES: Record<RadialMode, { title: string; icon: string; desc: string }> = {
    standard: {
        title: 'Órbita Literal',
        icon: '🌐',
        desc: 'Muestra los conceptos que coexisten más frecuentemente en tus archivos, sin importar el contexto profundo.',
    },
    fuzzy: {
        title: 'Órbita Semántica',
        icon: '🧠',
        desc: 'Muestra los conceptos que resuenan con mayor fuerza y certeza. Los temas secundarios desaparecen, acercando las ideas verdaderamente afines al centro.',
    },
};

// Color palette by node type
const TYPE_COLORS: Record<string, { bg: string; border: string; text: string }> = {
    Concept: { bg: '#7c3aed', border: '#a78bfa', text: '#fff' },
    Person: { bg: '#2563eb', border: '#60a5fa', text: '#fff' },
    Location: { bg: '#dc2626', border: '#f87171', text: '#fff' },
    Event: { bg: '#d97706', border: '#fbbf24', text: '#fff' },
    Organization: { bg: '#059669', border: '#34d399', text: '#fff' },
};

const TYPE_ICONS: Record<string, string> = {
    Concept: '💡', Person: '👤', Location: '📍', Event: '📅', Organization: '🏢',
};

function getNodeStyle(level: number, type: string) {
    const palette = TYPE_COLORS[type] || TYPE_COLORS.Concept;
    const sizes = [{ w: 90, h: 90, fs: 14 }, { w: 75, h: 75, fs: 12 }, { w: 60, h: 60, fs: 11 }];
    const s = sizes[level] || sizes[2];
    return {
        backgroundColor: level === 0 ? palette.bg : `${palette.bg}cc`,
        color: palette.text,
        border: `2px solid ${palette.border}`,
        width: s.w,
        height: s.h,
        borderRadius: '50%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: s.fs,
        fontWeight: level === 0 ? 700 : 500,
        cursor: 'pointer',
        boxShadow: level === 0 ? `0 0 20px ${palette.bg}88` : 'none',
        transition: 'box-shadow 0.2s',
    };
}

export default function RadialTreeCard() {
    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);
    const [loading, setLoading] = useState(true);
    const [rootNode, setRootNode] = useState<string | null>(null);
    const [message, setMessage] = useState('');
    const [error, setError] = useState<string | null>(null);
    const [method, setMethod] = useState<RadialMode>('standard');
    const [minWeight, setMinWeight] = useState<number>(0.0);
    const [debouncedWeight, setDebouncedWeight] = useState<number>(0.0);
    const navigate = useNavigate();

    useEffect(() => {
        const handler = setTimeout(() => {
            setDebouncedWeight(minWeight);
        }, 300);
        return () => clearTimeout(handler);
    }, [minWeight]);

    const fetchTree = useCallback(async (rootName: string | null | undefined, m: RadialMode, w: number) => {
        setLoading(true);
        setError(null);
        try {
            const payload = rootName ? { root_node_name: rootName } : {};
            const res = await axios.post<AnalysisResponse>(
                `http://localhost:8000/analysis/radial-tree?method=${m}&min_weight=${w}`,
                payload
            );
            if (res.data.status === 'error') throw new Error(res.data.message);

            const rawNodes = res.data.mock_data.nodes;
            const rawEdges = res.data.mock_data.edges;
            const root = res.data.mock_data.root;
            setRootNode(root);
            setMessage(res.data.message);

            // === Radial Layout Calculation ===
            const l0 = rawNodes.filter(n => n.level === 0);
            const l1 = rawNodes.filter(n => n.level === 1);
            const l2 = rawNodes.filter(n => n.level === 2);

            const computedNodes: Node[] = [];

            // Level 0: Center
            if (l0.length > 0) {
                computedNodes.push({
                    id: l0[0].id,
                    data: { label: `${TYPE_ICONS[l0[0].type || 'Concept'] || '💡'} ${l0[0].id}` },
                    position: { x: 0, y: 0 },
                    style: getNodeStyle(0, l0[0].type || 'Concept'),
                });
            }

            // Level 1: Ring at radius 300
            const R1 = 300;
            const l1AngleMap: Record<string, number> = {};
            l1.forEach((node, i) => {
                const angle = (2 * Math.PI * i) / l1.length;
                l1AngleMap[node.id] = angle;
                computedNodes.push({
                    id: node.id,
                    data: { label: `${TYPE_ICONS[node.type || 'Concept'] || '💡'} ${node.id}` },
                    position: { x: R1 * Math.cos(angle), y: R1 * Math.sin(angle) },
                    style: getNodeStyle(1, node.type || 'Concept'),
                });
            });

            // Level 2: Ring at radius 600, grouped near parent
            const R2 = 600;
            const l2ByParent: Record<string, GraphNode[]> = {};
            l2.forEach(n => {
                const p = n.parent || '';
                if (!l2ByParent[p]) l2ByParent[p] = [];
                l2ByParent[p].push(n);
            });

            const ARC_SPREAD = 0.35;
            Object.entries(l2ByParent).forEach(([parentId, children]) => {
                const parentAngle = l1AngleMap[parentId] ?? 0;
                const totalSpread = Math.min(ARC_SPREAD * children.length, Math.PI * 0.4);
                const startAngle = parentAngle - totalSpread / 2;
                children.forEach((node, i) => {
                    const angle = children.length === 1
                        ? parentAngle
                        : startAngle + (totalSpread * i) / (children.length - 1);
                    computedNodes.push({
                        id: node.id,
                        data: { label: `${TYPE_ICONS[node.type || 'Concept'] || '💡'} ${node.id}` },
                        position: { x: R2 * Math.cos(angle), y: R2 * Math.sin(angle) },
                        style: getNodeStyle(2, node.type || 'Concept'),
                    });
                });
            });

            setNodes(computedNodes);

            const computedEdges: Edge[] = rawEdges.map((e, i) => ({
                id: `e-${i}`,
                source: e.source,
                target: e.target,
                type: 'straight',
                style: { stroke: '#475569', strokeWidth: 1.5 },
                animated: false,
            }));
            setEdges(computedEdges);
        } catch (err: any) {
            console.error(err);
            setError(err.message || 'Error fetching tree');
        } finally {
            setLoading(false);
        }
    }, [setNodes, setEdges]);

    useEffect(() => {
        fetchTree(rootNode, method, debouncedWeight);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [method, debouncedWeight]);

    // Initial fetch on mount
    useEffect(() => {
        fetchTree(null, method, debouncedWeight);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const handleNodeClick = (_event: React.MouseEvent, node: Node) => {
        fetchTree(node.id, method, debouncedWeight);
    };

    const narrative = NARRATIVES[method];

    return (
        <div style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
            {/* Header */}
            <div className="p-4 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between z-10">
                <div className="flex items-center gap-4">
                    <button onClick={() => navigate('/analysis')} className="btn-secondary">Back</button>
                    <div>
                        <h2 className="text-xl font-bold flex items-center gap-2 text-slate-800 dark:text-white">
                            <Network className="text-cyan-500" />
                            Árbol Radial: {rootNode || '...'}
                        </h2>
                        <p className="text-xs text-slate-500">
                            Exploración concéntrica por co-ocurrencia (Root → Vecinos → Vecinos²)
                        </p>
                    </div>
                </div>
                <div className="flex gap-2">
                    <button onClick={() => fetchTree(null, method, debouncedWeight)} className="btn-secondary text-xs">Reset Root</button>
                    <button onClick={() => fetchTree(rootNode, method, debouncedWeight)} className="btn-icon" disabled={loading}>
                        <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
                    </button>
                </div>
            </div>

            <div style={{ flex: 1, display: 'flex', position: 'relative' }}>
                {/* React Flow canvas */}
                <div className="flex-1 relative bg-slate-50 dark:bg-slate-950">
                    {loading && (
                        <div className="absolute inset-0 flex items-center justify-center z-50 bg-white/50 dark:bg-black/50 backdrop-blur-sm">
                            <div className="flex flex-col items-center">
                                <Loader2 className="animate-spin text-indigo-600 mb-2" size={40} />
                                <span className="font-medium text-indigo-300">
                                    Expandiendo {method === 'fuzzy' ? 'órbita semántica' : 'grafo'}...
                                </span>
                            </div>
                        </div>
                    )}

                    {error && (
                        <div className="absolute top-10 left-1/2 -translate-x-1/2 bg-red-100 text-red-800 px-6 py-3 rounded-full shadow-lg z-50 border border-red-200">
                            Error: {error}
                        </div>
                    )}

                    <ReactFlow
                        nodes={nodes}
                        edges={edges}
                        onNodesChange={onNodesChange}
                        onEdgesChange={onEdgesChange}
                        onNodeClick={handleNodeClick}
                        fitView
                        minZoom={0.1}
                        nodesDraggable={false}
                    >
                        <Background color="#334155" gap={30} />
                        <Controls />
                    </ReactFlow>
                </div>

                {/* Explanation Side Panel */}
                <div
                    className="bg-white dark:bg-slate-950 border-l border-slate-200 dark:border-slate-800"
                    style={{ width: 260, padding: 20, flexShrink: 0, overflowY: 'auto' }}
                >
                    {/* Mode Toggle */}
                    <div style={{
                        display: 'flex', borderRadius: 8, overflow: 'hidden',
                        border: '1px solid #334155', marginBottom: 16,
                    }}>
                        {(['standard', 'fuzzy'] as RadialMode[]).map(m => (
                            <button
                                key={m}
                                onClick={() => setMethod(m)}
                                style={{
                                    flex: 1, padding: '8px 4px', fontSize: '0.72rem', fontWeight: 600,
                                    border: 'none', cursor: 'pointer',
                                    transition: 'all 0.25s ease',
                                    background: method === m
                                        ? (m === 'fuzzy' ? '#7c3aed' : '#0891b2')
                                        : '#0f172a',
                                    color: method === m ? '#ffffff' : '#64748b',
                                }}
                            >
                                {m === 'standard' ? '🌐 Standard' : '🧠 Fuzzy'}
                            </button>
                        ))}
                    </div>

                    {/* Threshold Slider */}
                    <div style={{
                        background: '#1e293b', borderRadius: 8, padding: 12, marginBottom: 16,
                        border: '1px solid #334155',
                    }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                            <div style={{ fontSize: '0.7rem', color: '#64748b', fontWeight: 600 }}>
                                UMBRAL DE CONFIANZA
                            </div>
                            <div style={{ fontSize: '0.9rem', color: '#f8fafc', fontWeight: 700 }}>
                                {minWeight.toFixed(2)}
                            </div>
                        </div>
                        <input
                            type="range"
                            min="0" max="0.9" step="0.05"
                            value={minWeight}
                            onChange={(e) => setMinWeight(parseFloat(e.target.value))}
                            style={{
                                width: '100%', cursor: 'pointer',
                                accentColor: method === 'fuzzy' ? '#7c3aed' : '#0ea5e9'
                            }}
                        />
                        <p style={{ fontSize: '0.65rem', color: '#64748b', margin: '8px 0 0 0', lineHeight: 1.4 }}>
                            Ignora conexiones menores al umbral para reducir el ruido.
                        </p>
                    </div>

                    {/* Dynamic Narrative */}
                    <div style={{
                        background: '#1e293b', borderRadius: 8, padding: 12, marginBottom: 16,
                        border: '1px solid #334155',
                    }}>
                        <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#f8fafc', marginBottom: 6 }}>
                            {narrative.icon} {narrative.title}
                        </div>
                        <p style={{ fontSize: '0.75rem', color: '#94a3b8', lineHeight: 1.6, margin: 0 }}>
                            {narrative.desc}
                        </p>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
                        <Info size={18} className="text-cyan-400" />
                        <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#f8fafc', margin: 0 }}>
                            ¿Qué veo aquí?
                        </h3>
                    </div>

                    <p style={{ fontSize: '0.78rem', color: '#94a3b8', lineHeight: 1.6, marginBottom: 16 }}>
                        El <strong style={{ color: '#e2e8f0' }}>centro</strong> es el concepto raíz.
                        Los <strong style={{ color: '#a5b4fc' }}>nodos del anillo interior</strong> son sus
                        {method === 'fuzzy' ? ' 8 vecinos de mayor peso difuso.' : ' 8 vecinos más frecuentes (comparten archivos).'}
                        {' '}El <strong style={{ color: '#e0e7ff' }}>anillo exterior</strong> muestra los
                        vecinos de los vecinos.
                    </p>

                    <p style={{ fontSize: '0.78rem', color: '#94a3b8', lineHeight: 1.6, marginBottom: 20 }}>
                        ¿Quieres explorar más? <strong style={{ color: '#e2e8f0' }}>Haz click en cualquier nodo</strong> para
                        convertirlo en la nueva raíz.
                    </p>

                    {/* Type legend */}
                    <div style={{
                        background: '#1e293b', borderRadius: 8, padding: 12, marginBottom: 16,
                        border: '1px solid #334155'
                    }}>
                        <div style={{ fontSize: '0.7rem', color: '#64748b', fontWeight: 600, marginBottom: 10 }}>
                            TIPOS DE ENTIDAD
                        </div>
                        {Object.entries(TYPE_COLORS).map(([name, c]) => (
                            <div key={name} style={{
                                display: 'flex', alignItems: 'center', gap: 8, marginBottom: 5,
                                fontSize: '0.75rem'
                            }}>
                                <div style={{
                                    width: 10, height: 10, borderRadius: '50%',
                                    background: c.bg, border: `1px solid ${c.border}`,
                                    flexShrink: 0
                                }} />
                                <span style={{ color: '#94a3b8' }}>
                                    {TYPE_ICONS[name]} {name}
                                </span>
                            </div>
                        ))}
                    </div>

                    <div style={{
                        background: '#1e293b', borderRadius: 8, padding: 12,
                        border: '1px solid #334155'
                    }}>
                        <div style={{ fontSize: '0.7rem', color: '#64748b', fontWeight: 600, marginBottom: 6 }}>
                            NIVELES
                        </div>
                        <p style={{ fontSize: '0.72rem', color: '#94a3b8', lineHeight: 1.5, margin: 0 }}>
                            <strong style={{ color: '#e2e8f0' }}>Nivel 0</strong> — Raíz (centro)<br />
                            <strong style={{ color: '#e2e8f0' }}>Nivel 1</strong> — 8 vecinos directos<br />
                            <strong style={{ color: '#e2e8f0' }}>Nivel 2</strong> — 3 vecinos por L1
                        </p>
                    </div>

                    {message && (
                        <div style={{
                            marginTop: 16, fontSize: '0.7rem', color: '#4ade80',
                            padding: '8px 12px', background: '#22c55e10', borderRadius: 6,
                            border: '1px solid #22c55e30'
                        }}>
                            ✅ {message}
                        </div>
                    )}
                </div>
            </div>

            {/* Bottom hint bar */}
            <div className="absolute bottom-6 left-1/2 -translate-x-1/2 bg-white/80 dark:bg-slate-900/80 backdrop-blur px-4 py-2 rounded-full text-xs text-slate-400 border border-slate-700 shadow-sm pointer-events-none z-20">
                🎯 Click en cualquier nodo para convertirlo en el nuevo centro
            </div>
        </div>
    );
}
