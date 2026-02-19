import { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { ResponsiveCirclePacking } from '@nivo/circle-packing';
import { Dna, Loader2, RefreshCw, Info } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface PackingNode {
    name: string;
    loc?: number;
    children?: PackingNode[];
    color?: string;
}

interface AnalysisResponse {
    tool: string;
    status: string;
    message: string;
    mock_data: {
        packing_data: PackingNode;
    };
}

const COMMUNITY_COLORS = [
    '#8b5cf6', '#f97316', '#22c55e', '#3b82f6',
    '#ec4899', '#eab308', '#14b8a6', '#ef4444',
    '#6366f1', '#84cc16', '#f59e0b', '#06b6d4',
];

export default function CommunityAnalysisCard() {
    const [data, setData] = useState<PackingNode | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [message, setMessage] = useState('');
    const navigate = useNavigate();

    const fetch = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await axios.post<AnalysisResponse>('http://localhost:8000/analysis/communities');
            if (res.data.status === 'error') throw new Error(res.data.message);
            setData(res.data.mock_data.packing_data || null);
            setMessage(res.data.message);
        } catch (err: any) {
            setError(err.message || 'Error detecting communities');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { fetch(); }, [fetch]);

    const communityCount = data?.children?.length || 0;

    return (
        <div style={{ padding: 24, paddingBottom: 60, maxWidth: 1200, margin: '0 auto' }}>
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-4">
                    <button onClick={() => navigate('/analysis')} className="btn-secondary">Back</button>
                    <div>
                        <h2 className="text-2xl font-bold flex items-center gap-2 text-slate-100">
                            <Dna size={28} className="text-purple-500" />
                            Comunidades Temáticas (Louvain)
                        </h2>
                        <p className="text-sm text-slate-500">
                            Clústeres de conceptos detectados por co-ocurrencia en archivos
                        </p>
                    </div>
                </div>
                <button onClick={fetch} className="btn-icon" disabled={loading}>
                    <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
                </button>
            </div>

            {error && (
                <div className="p-4 mb-6 text-red-500 border border-red-200 rounded-xl">{error}</div>
            )}

            <div style={{ display: 'flex', gap: 20 }}>
                {/* Main Circle Packing Panel */}
                <div
                    className="bg-white dark:bg-slate-950 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800"
                    style={{ flex: 1, padding: 0, minHeight: 560, overflow: 'hidden', position: 'relative' }}
                >
                    {loading && (
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: 560 }}>
                            <Loader2 className="animate-spin mb-4 text-purple-400" size={40} />
                            <span style={{ color: '#94a3b8', fontSize: '0.9rem' }}>Ejecutando Louvain Modularity...</span>
                            <span style={{ color: '#475569', fontSize: '0.7rem', marginTop: 6 }}>Proyectando grafo virtual en GDS</span>
                        </div>
                    )}

                    {!loading && data && data.children && data.children.length > 0 && (
                        <div style={{ height: 560, width: '100%' }}>
                            <ResponsiveCirclePacking
                                data={data}
                                id="name"
                                value="loc"
                                padding={4}
                                enableLabels={true}
                                labelsFilter={(label) => label.node.depth === 2}
                                labelsSkipRadius={15}
                                labelTextColor="#ffffff"
                                colors={(node) => {
                                    // Depth 1 = cluster, depth 2 = concept inside cluster
                                    if (node.depth === 1) {
                                        // Use index-based color from our palette
                                        const parentIndex = data.children?.findIndex(c => c.name === node.id) ?? 0;
                                        return COMMUNITY_COLORS[parentIndex % COMMUNITY_COLORS.length];
                                    }
                                    if (node.depth === 2 && node.parent) {
                                        const parentIndex = data.children?.findIndex(c => c.name === node.parent!.id) ?? 0;
                                        const baseColor = COMMUNITY_COLORS[parentIndex % COMMUNITY_COLORS.length];
                                        return baseColor + 'cc'; // Slightly transparent
                                    }
                                    return '#1e293b';
                                }}
                                borderWidth={2}
                                borderColor={{ from: 'color', modifiers: [['darker', 0.4]] }}
                                theme={{
                                    labels: {
                                        text: {
                                            fill: '#ffffff',
                                            fontWeight: 600,
                                            fontSize: 11,
                                        },
                                    },
                                    tooltip: {
                                        container: {
                                            background: '#0f172a',
                                            color: '#f8fafc',
                                            borderRadius: '8px',
                                            border: '1px solid #334155',
                                            fontSize: '13px',
                                            padding: '8px 12px',
                                        },
                                    },
                                }}
                                motionConfig="gentle"
                                animate={true}
                            />
                        </div>
                    )}

                    {!loading && (!data || !data.children || data.children.length === 0) && (
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: 560 }}>
                            <Dna size={48} color="#475569" />
                            <span style={{ color: '#475569', marginTop: 12 }}>
                                No se detectaron comunidades. Agrega más datos al grafo.
                            </span>
                        </div>
                    )}
                </div>

                {/* Explanation Panel */}
                <div
                    className="bg-white dark:bg-slate-950 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800"
                    style={{ width: 280, padding: 20, flexShrink: 0 }}
                >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
                        <Info size={18} className="text-purple-400" />
                        <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#f8fafc', margin: 0 }}>
                            ¿Qué es esto?
                        </h3>
                    </div>

                    <p style={{ fontSize: '0.78rem', color: '#94a3b8', lineHeight: 1.7, marginBottom: 16 }}>
                        El algoritmo de <strong style={{ color: '#a78bfa' }}>Louvain Modularity</strong> identifica
                        clústeres de conceptos que aparecen juntos frecuentemente en tus archivos.
                    </p>

                    <p style={{ fontSize: '0.78rem', color: '#94a3b8', lineHeight: 1.7, marginBottom: 16 }}>
                        Dos conceptos se consideran <em>vecinos</em> si al menos un <strong style={{ color: '#e2e8f0' }}>DigitalAsset</strong> los
                        menciona a ambos. El peso de la conexión es la cantidad de archivos compartidos.
                    </p>

                    {communityCount > 0 && (
                        <div style={{
                            background: '#1e293b', borderRadius: 8, padding: 12, marginBottom: 16,
                            border: '1px solid #334155'
                        }}>
                            <div style={{ fontSize: '0.7rem', color: '#64748b', fontWeight: 600, marginBottom: 6 }}>
                                RESULTADO
                            </div>
                            <p style={{ fontSize: '0.82rem', color: '#94a3b8', lineHeight: 1.6, margin: 0 }}>
                                El algoritmo ha agrupado tus datos en{' '}
                                <strong style={{ color: '#a78bfa' }}>{communityCount}</strong> grandes mundos.
                                Las burbujas agrupadas representan conceptos que el sistema considera
                                <em> indivisibles</em> debido a la alta frecuencia con la que aparecen juntos.
                            </p>
                        </div>
                    )}

                    {/* Community legend */}
                    {data?.children && data.children.length > 0 && (
                        <div style={{
                            background: '#1e293b', borderRadius: 8, padding: 12, marginBottom: 16,
                            border: '1px solid #334155'
                        }}>
                            <div style={{ fontSize: '0.7rem', color: '#64748b', fontWeight: 600, marginBottom: 8 }}>
                                COMUNIDADES
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 220, overflowY: 'auto' }}>
                                {data.children.map((community, i) => (
                                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                        <div style={{
                                            width: 10, height: 10, borderRadius: '50%',
                                            background: COMMUNITY_COLORS[i % COMMUNITY_COLORS.length],
                                            flexShrink: 0,
                                        }} />
                                        <span style={{ fontSize: '0.72rem', color: '#94a3b8', lineHeight: 1.3 }}>
                                            {community.name}
                                            <span style={{ color: '#475569', marginLeft: 4 }}>
                                                ({community.children?.length || 0})
                                            </span>
                                        </span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {message && (
                        <div style={{
                            fontSize: '0.7rem', color: '#4ade80',
                            padding: '8px 12px', background: '#22c55e10', borderRadius: 6,
                            border: '1px solid #22c55e30'
                        }}>
                            ✅ {message}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
