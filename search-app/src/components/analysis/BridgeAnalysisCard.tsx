import { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import ReactFlow, { Background, Controls } from 'reactflow';
import type { Node, Edge } from 'reactflow';
import 'reactflow/dist/style.css';
import { Network, Loader2, RefreshCw, Info } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface BridgeItem {
    id: string;
    score: number;
    context: string[];
}

interface AnalysisResponse {
    tool: string;
    status: string;
    message: string;
    mock_data: {
        bridges: BridgeItem[];
        method?: string;
    };
}

type BridgeMode = 'standard' | 'fuzzy';

const NARRATIVES: Record<BridgeMode, { title: string; icon: string; desc: string; scoreLabel: string }> = {
    standard: {
        title: 'Puentes Estructurales (Standard)',
        icon: '🌉',
        desc: 'Conceptos que unen la mayor cantidad de archivos de diferentes temáticas. Muestra los "cuellos de botella" físicos de tu información.',
        scoreLabel: 'diversidad × nodos conectados',
    },
    fuzzy: {
        title: 'Puentes Interdisciplinarios (Fuzzy)',
        icon: '✨',
        desc: 'Filtra el ruido usando los pesos de la IA. Solo muestra conceptos que conectan mundos dispares con ALTA certeza semántica. Ideal para descubrir tus verdaderas asociaciones interdisciplinarias.',
        scoreLabel: 'diversidad × peso difuso',
    },
};

// Build a Bowtie layout: left column → center → right column
function buildBowtieGraph(bridge: BridgeItem): { nodes: Node[]; edges: Edge[] } {
    const ctx = bridge.context || [];
    const mid = Math.ceil(ctx.length / 2);
    const leftItems = ctx.slice(0, mid);
    const rightItems = ctx.slice(mid);

    const nodes: Node[] = [];
    const edges: Edge[] = [];

    // Center bridge node
    const centerX = 300;
    const centerY = Math.max(leftItems.length, rightItems.length, 1) * 40;
    nodes.push({
        id: 'bridge',
        position: { x: centerX, y: centerY },
        data: { label: `🌉 ${bridge.id}` },
        style: {
            background: 'linear-gradient(135deg, #ef4444, #f97316)',
            color: '#fff',
            borderRadius: '50%',
            width: 80,
            height: 80,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 11,
            fontWeight: 700,
            border: '3px solid #fbbf24',
            boxShadow: '0 0 24px rgba(239,68,68,0.5)',
            textAlign: 'center' as const,
        },
    });

    // Left column
    leftItems.forEach((name, i) => {
        const y = i * 80 + 20;
        const nodeId = `left-${i}`;
        nodes.push({
            id: nodeId,
            position: { x: 30, y },
            data: { label: name },
            style: {
                background: '#1e293b',
                color: '#93c5fd',
                border: '1px solid #3b82f6',
                borderRadius: 8,
                fontSize: 10,
                padding: '6px 10px',
                minWidth: 100,
                textAlign: 'center' as const,
            },
        });
        edges.push({
            id: `e-l-${i}`,
            source: nodeId,
            target: 'bridge',
            animated: true,
            style: { stroke: '#3b82f6', strokeWidth: 2 },
        });
    });

    // Right column
    rightItems.forEach((name, i) => {
        const y = i * 80 + 20;
        const nodeId = `right-${i}`;
        nodes.push({
            id: nodeId,
            position: { x: 570, y },
            data: { label: name },
            style: {
                background: '#1e293b',
                color: '#86efac',
                border: '1px solid #22c55e',
                borderRadius: 8,
                fontSize: 10,
                padding: '6px 10px',
                minWidth: 100,
                textAlign: 'center' as const,
            },
        });
        edges.push({
            id: `e-r-${i}`,
            source: 'bridge',
            target: nodeId,
            animated: true,
            style: { stroke: '#22c55e', strokeWidth: 2 },
        });
    });

    return { nodes, edges };
}

export default function BridgeAnalysisCard() {
    const [bridges, setBridges] = useState<BridgeItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [activeBridge, setActiveBridge] = useState<BridgeItem | null>(null);
    const [flowNodes, setFlowNodes] = useState<Node[]>([]);
    const [flowEdges, setFlowEdges] = useState<Edge[]>([]);
    const [message, setMessage] = useState('');
    const [method, setMethod] = useState<BridgeMode>('standard');
    const navigate = useNavigate();

    const fetchData = useCallback(async (m: BridgeMode) => {
        setLoading(true);
        setError(null);
        setActiveBridge(null);
        setFlowNodes([]);
        setFlowEdges([]);
        try {
            const res = await axios.post<AnalysisResponse>(
                `http://localhost:8000/analysis/bridges?method=${m}`
            );
            if (res.data.status === 'error') throw new Error(res.data.message);
            const items = res.data.mock_data.bridges;
            setBridges(items);
            setMessage(res.data.message);
            if (items.length > 0) {
                selectBridge(items[0]);
            }
        } catch (err: any) {
            console.error(err);
            setError(err.message || 'Error fetching bridges');
        } finally {
            setLoading(false);
        }
    }, []);

    const selectBridge = (b: BridgeItem) => {
        setActiveBridge(b);
        const { nodes, edges } = buildBowtieGraph(b);
        setFlowNodes(nodes);
        setFlowEdges(edges);
    };

    useEffect(() => { fetchData(method); }, [method, fetchData]);

    const narrative = NARRATIVES[method];

    return (
        <div style={{ padding: 24, paddingBottom: 60, maxWidth: 1400, margin: '0 auto' }}>
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-4">
                    <button onClick={() => navigate('/analysis')} className="btn-secondary">Back</button>
                    <div>
                        <h2 className="text-2xl font-bold flex items-center gap-2 text-slate-100">
                            <Network size={28} className="text-red-500" />
                            Puentes Semánticos
                        </h2>
                        <p className="text-sm text-slate-500">
                            Conceptos que conectan diferentes "mundos" de tu grafo
                        </p>
                    </div>
                </div>
                <button onClick={() => fetchData(method)} className="btn-icon" disabled={loading}>
                    <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
                </button>
            </div>

            {error ? (
                <div className="p-8 text-red-500 border border-red-200 rounded">{error}</div>
            ) : (
                <div style={{ display: 'flex', gap: 20 }}>
                    {/* Left Panel — Toggle + Leaderboard */}
                    <div style={{ width: 280, flexShrink: 0 }}>
                        <div
                            className="bg-white dark:bg-slate-950 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800"
                            style={{ padding: 16 }}
                        >
                            {/* Mode Toggle */}
                            <div style={{
                                display: 'flex', borderRadius: 8, overflow: 'hidden',
                                border: '1px solid #334155', marginBottom: 16,
                            }}>
                                {(['standard', 'fuzzy'] as BridgeMode[]).map(m => (
                                    <button
                                        key={m}
                                        onClick={() => setMethod(m)}
                                        style={{
                                            flex: 1, padding: '8px 4px', fontSize: '0.72rem', fontWeight: 600,
                                            border: 'none', cursor: 'pointer',
                                            transition: 'all 0.25s ease',
                                            background: method === m
                                                ? (m === 'fuzzy' ? '#7c3aed' : '#dc2626')
                                                : '#0f172a',
                                            color: method === m ? '#ffffff' : '#64748b',
                                        }}
                                    >
                                        {m === 'standard' ? '🌉 Standard' : '✨ Fuzzy'}
                                    </button>
                                ))}
                            </div>

                            <div style={{ fontSize: '0.7rem', color: '#64748b', fontWeight: 600, marginBottom: 12, textTransform: 'uppercase', letterSpacing: 1 }}>
                                🏆 Ranking de Puentes
                            </div>

                            {loading ? (
                                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: 24 }}>
                                    <Loader2 className="animate-spin mb-2 text-red-400" size={24} />
                                    <span style={{ color: '#64748b', fontSize: '0.75rem' }}>
                                        Buscando {method === 'fuzzy' ? 'fuzzy' : 'standard'} bridges...
                                    </span>
                                </div>
                            ) : (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                                    {bridges.map((b, i) => {
                                        const isActive = activeBridge?.id === b.id;
                                        return (
                                            <button
                                                key={b.id}
                                                onClick={() => selectBridge(b)}
                                                style={{
                                                    display: 'flex',
                                                    alignItems: 'center',
                                                    justifyContent: 'space-between',
                                                    padding: '10px 12px',
                                                    borderRadius: 10,
                                                    border: isActive ? '1px solid #ef4444' : '1px solid #334155',
                                                    background: isActive ? '#ef444418' : '#0f172a',
                                                    cursor: 'pointer',
                                                    transition: 'all 0.15s',
                                                    textAlign: 'left',
                                                }}
                                            >
                                                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                                                    <div
                                                        style={{
                                                            width: 24,
                                                            height: 24,
                                                            borderRadius: '50%',
                                                            background: i === 0 ? '#ef4444' : i < 3 ? '#f9731630' : '#1e293b',
                                                            color: i === 0 ? '#fff' : '#94a3b8',
                                                            display: 'flex',
                                                            alignItems: 'center',
                                                            justifyContent: 'center',
                                                            fontSize: 11,
                                                            fontWeight: 700,
                                                            flexShrink: 0,
                                                        }}
                                                    >
                                                        {i + 1}
                                                    </div>
                                                    <span style={{ fontSize: '0.82rem', color: isActive ? '#fca5a5' : '#e2e8f0', fontWeight: isActive ? 600 : 400 }}>
                                                        {b.id}
                                                    </span>
                                                </div>
                                                <span style={{ fontSize: '0.7rem', color: '#64748b', fontFamily: 'monospace' }}>
                                                    {b.score}
                                                </span>
                                            </button>
                                        );
                                    })}
                                </div>
                            )}

                            {!loading && bridges.length === 0 && (
                                <div style={{ padding: 20, textAlign: 'center', color: '#475569', fontSize: '0.8rem' }}>
                                    No se encontraron puentes.
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Center Panel — Bowtie React Flow */}
                    <div
                        className="bg-white dark:bg-slate-950 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800"
                        style={{ flex: 1, height: 520, position: 'relative', overflow: 'hidden' }}
                    >
                        {!activeBridge ? (
                            <div className="absolute inset-0 flex items-center justify-center text-slate-400">
                                Selecciona un puente del ranking para visualizarlo.
                            </div>
                        ) : (
                            <>
                                <div
                                    style={{
                                        position: 'absolute',
                                        top: 12,
                                        left: 16,
                                        zIndex: 10,
                                        background: '#0f172acc',
                                        backdropFilter: 'blur(8px)',
                                        padding: '6px 14px',
                                        borderRadius: 20,
                                        fontSize: '0.72rem',
                                        color: '#94a3b8',
                                        border: '1px solid #334155',
                                    }}
                                >
                                    {method === 'fuzzy' ? '✨' : '🌉'} Bowtie: <strong style={{ color: '#fca5a5' }}>{activeBridge.id}</strong>
                                </div>
                                <ReactFlow
                                    nodes={flowNodes}
                                    edges={flowEdges}
                                    fitView
                                    minZoom={0.5}
                                    nodesDraggable={false}
                                >
                                    <Background color="#334155" gap={30} />
                                    <Controls />
                                </ReactFlow>
                            </>
                        )}
                    </div>

                    {/* Right Panel — Explanation */}
                    <div
                        className="bg-white dark:bg-slate-950 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800"
                        style={{ width: 250, padding: 20, flexShrink: 0 }}
                    >
                        {/* Dynamic narrative */}
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
                            <Info size={18} className="text-red-400" />
                            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#f8fafc', margin: 0 }}>
                                Puente Semántico
                            </h3>
                        </div>

                        {activeBridge ? (
                            <>
                                <p style={{ fontSize: '0.78rem', color: '#94a3b8', lineHeight: 1.7, marginBottom: 16 }}>
                                    El concepto <strong style={{ color: '#fca5a5' }}>{activeBridge.id}</strong> es
                                    un <strong style={{ color: '#e2e8f0' }}>puente crítico</strong>. Está
                                    conectando temas como{' '}
                                    <strong style={{ color: '#93c5fd' }}>
                                        {activeBridge.context[0] || '—'}
                                    </strong>{' '}
                                    con{' '}
                                    <strong style={{ color: '#86efac' }}>
                                        {activeBridge.context[activeBridge.context.length - 1] || '—'}
                                    </strong>
                                    .
                                </p>
                                <p style={{ fontSize: '0.78rem', color: '#94a3b8', lineHeight: 1.7, marginBottom: 16 }}>
                                    Sin este concepto, estos temas estarían <em>aislados</em> en el grafo.
                                </p>

                                <div style={{
                                    background: '#1e293b', borderRadius: 8, padding: 12, marginBottom: 16,
                                    border: '1px solid #334155'
                                }}>
                                    <div style={{ fontSize: '0.7rem', color: '#64748b', fontWeight: 600, marginBottom: 8 }}>
                                        CONECTA
                                    </div>
                                    {activeBridge.context.map((c, i) => (
                                        <div key={i} style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: 3 }}>
                                            • {c}
                                        </div>
                                    ))}
                                </div>

                                <div style={{
                                    background: '#1e293b', borderRadius: 8, padding: 12,
                                    border: '1px solid #334155'
                                }}>
                                    <div style={{ fontSize: '0.7rem', color: '#64748b', fontWeight: 600, marginBottom: 4 }}>
                                        SCORE
                                    </div>
                                    <div style={{ fontSize: '1.2rem', fontWeight: 700, color: '#ef4444', fontFamily: 'monospace' }}>
                                        {activeBridge.score}
                                    </div>
                                    <div style={{ fontSize: '0.65rem', color: '#475569', marginTop: 2 }}>
                                        {narrative.scoreLabel}
                                    </div>
                                </div>
                            </>
                        ) : (
                            <p style={{ fontSize: '0.78rem', color: '#475569', lineHeight: 1.6 }}>
                                Selecciona un concepto del ranking para ver su visualización Bowtie y
                                entender qué mundos conecta.
                            </p>
                        )}

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
            )}
        </div>
    );
}
