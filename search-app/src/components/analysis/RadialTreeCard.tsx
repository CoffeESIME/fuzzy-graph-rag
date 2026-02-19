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
    };
}

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
    const sizes = [{ w: 70, h: 70, fs: 11 }, { w: 54, h: 54, fs: 10 }, { w: 42, h: 42, fs: 9 }];
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
    const navigate = useNavigate();

    const fetchTree = useCallback(async (rootName?: string | null) => {
        setLoading(true);
        setError(null);
        try {
            const payload = rootName ? { root_node_name: rootName } : {};
            const res = await axios.post<AnalysisResponse>('http://localhost:8000/analysis/radial-tree', payload);
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

            // Level 1: Ring at radius 250
            const R1 = 250;
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

            // Level 2: Ring at radius 500, grouped near parent
            const R2 = 500;
            // Group L2 by parent
            const l2ByParent: Record<string, GraphNode[]> = {};
            l2.forEach(n => {
                const p = n.parent || '';
                if (!l2ByParent[p]) l2ByParent[p] = [];
                l2ByParent[p].push(n);
            });

            // Spread L2 children in a small arc around their parent's angle
            const ARC_SPREAD = 0.35; // radians per child group
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
        fetchTree(null);
    }, [fetchTree]);

    const handleNodeClick = (_event: React.MouseEvent, node: Node) => {
        fetchTree(node.id);
    };

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
                    <button onClick={() => fetchTree(null)} className="btn-secondary text-xs">Reset Root</button>
                    <button onClick={() => fetchTree(rootNode)} className="btn-icon">
                        <RefreshCw size={18} />
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
                                <span className="font-medium text-indigo-300">Expandiendo grafo...</span>
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
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
                        <Info size={18} className="text-cyan-400" />
                        <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#f8fafc', margin: 0 }}>
                            ¿Qué veo aquí?
                        </h3>
                    </div>

                    <p style={{ fontSize: '0.78rem', color: '#94a3b8', lineHeight: 1.6, marginBottom: 16 }}>
                        El <strong style={{ color: '#e2e8f0' }}>centro</strong> es el concepto raíz.
                        Los <strong style={{ color: '#a5b4fc' }}>nodos del anillo interior</strong> son sus
                        10 vecinos más frecuentes (comparten archivos).
                        El <strong style={{ color: '#e0e7ff' }}>anillo exterior</strong> muestra los
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
                            <strong style={{ color: '#e2e8f0' }}>Nivel 1</strong> — 10 vecinos directos<br />
                            <strong style={{ color: '#e2e8f0' }}>Nivel 2</strong> — 5 vecinos por L1
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
