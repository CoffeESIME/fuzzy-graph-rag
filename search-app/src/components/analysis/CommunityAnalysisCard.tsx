import { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { ResponsiveCirclePacking } from '@nivo/circle-packing';
import { Dna, Loader2, RefreshCw, Info, X } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface PackingNode {
    name: string;
    loc?: number;
    degree?: number;
    children?: PackingNode[];
    color?: string;
    total_size?: number;
}

interface AnalysisResponse {
    tool: string;
    status: string;
    message: string;
    mock_data: {
        packing_data: PackingNode;
        method?: string;
    };
}

type CommunityMode = 'standard' | 'fuzzy';

const COMMUNITY_COLORS = [
    '#8b5cf6', '#f97316', '#22c55e', '#3b82f6',
    '#ec4899', '#eab308', '#14b8a6', '#ef4444',
    '#6366f1', '#84cc16', '#f59e0b', '#06b6d4',
];

const NARRATIVES: Record<CommunityMode, { title: string; icon: string; desc: string }> = {
    standard: {
        title: 'Comunidades Físicas (Standard)',
        icon: '🌍',
        desc: 'Los grupos se forman por la cantidad de veces que los conceptos comparten el mismo archivo. Las burbujas reflejan el volumen bruto de conexiones. Muestra áreas de interés amplias y literales.',
    },
    fuzzy: {
        title: 'Comunidades Semánticas (Fuzzy)',
        icon: '🧠',
        desc: 'El algoritmo es estricto. Usa la "certeza" de la IA, agrupando conceptos solo si evocan un significado profundo y simultáneo. Las burbujas reflejan el peso semántico. Revela clústeres más refinados y puros.',
    },
};

export default function CommunityAnalysisCard() {
    const [data, setData] = useState<PackingNode | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [message, setMessage] = useState('');
    const [method, setMethod] = useState<CommunityMode>('standard');
    const [selectedCommunity, setSelectedCommunity] = useState<PackingNode | null>(null);
    const navigate = useNavigate();

    const fetchData = useCallback(async (m: CommunityMode) => {
        setLoading(true);
        setError(null);
        setSelectedCommunity(null);
        try {
            const res = await axios.post<AnalysisResponse>(
                `http://localhost:8000/analysis/communities?method=${m}`
            );
            if (res.data.status === 'error') throw new Error(res.data.message);
            setData(res.data.mock_data.packing_data || null);
            setMessage(res.data.message);
        } catch (err: any) {
            setError(err.message || 'Error detecting communities');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { fetchData(method); }, [method, fetchData]);

    const communityCount = data?.children?.length || 0;
    const narrative = NARRATIVES[method];

    const findCommunityByName = (name: string): PackingNode | null => {
        return data?.children?.find(c => c.name === name) || null;
    };

    const selectedColor = selectedCommunity
        ? COMMUNITY_COLORS[(data?.children?.findIndex(c => c.name === selectedCommunity.name) ?? 0) % COMMUNITY_COLORS.length]
        : '#8b5cf6';

    const formatDegree = (val: number | undefined) => {
        if (val === undefined) return '?';
        return Number.isInteger(val) ? String(val) : val.toFixed(2);
    };

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
                <button onClick={() => fetchData(method)} className="btn-icon" disabled={loading}>
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
                            <span style={{ color: '#94a3b8', fontSize: '0.9rem' }}>
                                Ejecutando {method === 'fuzzy' ? 'Fuzzy' : 'Standard'} Louvain...
                            </span>
                            <span style={{ color: '#475569', fontSize: '0.7rem', marginTop: 6 }}>Proyectando grafo virtual en GDS</span>
                        </div>
                    )}

                    {!loading && data && data.children && data.children.length > 0 && (
                        <div style={{ height: 560, width: '100%', cursor: 'pointer' }}>
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
                                    if (node.depth === 1) {
                                        const parentIndex = data.children?.findIndex(c => c.name === node.id) ?? 0;
                                        return COMMUNITY_COLORS[parentIndex % COMMUNITY_COLORS.length];
                                    }
                                    if (node.depth === 2 && node.parent) {
                                        const parentIndex = data.children?.findIndex(c => c.name === node.parent!.id) ?? 0;
                                        const baseColor = COMMUNITY_COLORS[parentIndex % COMMUNITY_COLORS.length];
                                        return baseColor + 'cc';
                                    }
                                    return '#1e293b';
                                }}
                                borderWidth={2}
                                borderColor={{ from: 'color', modifiers: [['darker', 0.4]] }}
                                onClick={(node) => {
                                    if (node.depth === 1) {
                                        setSelectedCommunity(findCommunityByName(node.id as string));
                                    } else if (node.depth === 2 && node.parent) {
                                        setSelectedCommunity(findCommunityByName(node.parent.id as string));
                                    }
                                }}
                                theme={{
                                    labels: {
                                        text: { fill: '#ffffff', fontWeight: 600, fontSize: 11 },
                                    },
                                    tooltip: {
                                        container: {
                                            background: '#0f172a', color: '#f8fafc',
                                            borderRadius: '8px', border: '1px solid #334155',
                                            fontSize: '13px', padding: '8px 12px',
                                        },
                                    },
                                }}
                                tooltip={({ id, value, depth }) => (
                                    <div style={{
                                        background: '#0f172a', border: '1px solid #334155',
                                        borderRadius: 8, padding: '8px 12px', color: '#f8fafc', fontSize: 12,
                                    }}>
                                        <strong>{id}</strong>
                                        {depth === 2 && (
                                            <span style={{ color: '#94a3b8', marginLeft: 8 }}>
                                                {method === 'fuzzy'
                                                    ? `peso: ${typeof value === 'number' ? value.toFixed(2) : value}`
                                                    : `${value} archivo${value !== 1 ? 's' : ''}`
                                                }
                                            </span>
                                        )}
                                        {depth === 1 && (
                                            <span style={{ color: '#a78bfa', marginLeft: 8 }}>
                                                Click para ver detalles
                                            </span>
                                        )}
                                    </div>
                                )}
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

                {/* Side Panel */}
                <div
                    className="bg-white dark:bg-slate-950 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800"
                    style={{ width: 280, padding: 20, flexShrink: 0 }}
                >
                    {/* Mode Toggle */}
                    <div style={{
                        display: 'flex', borderRadius: 8, overflow: 'hidden',
                        border: '1px solid #334155', marginBottom: 20,
                    }}>
                        {(['standard', 'fuzzy'] as CommunityMode[]).map(m => (
                            <button
                                key={m}
                                onClick={() => setMethod(m)}
                                style={{
                                    flex: 1, padding: '8px 4px', fontSize: '0.72rem', fontWeight: 600,
                                    border: 'none', cursor: 'pointer',
                                    transition: 'all 0.25s ease',
                                    background: method === m
                                        ? (m === 'fuzzy' ? '#7c3aed' : '#8b5cf6')
                                        : '#0f172a',
                                    color: method === m ? '#ffffff' : '#64748b',
                                }}
                            >
                                {m === 'standard' ? '🌍 Standard' : '🧠 Fuzzy'}
                            </button>
                        ))}
                    </div>

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
                        El <strong style={{ color: '#e2e8f0' }}>tamaño de cada burbuja</strong> refleja{' '}
                        {method === 'fuzzy'
                            ? 'la suma de los pesos semánticos de las relaciones de ese concepto.'
                            : 'cuántos archivos mencionan ese concepto. Las más grandes son los más referenciados.'
                        }
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
                                Haz <strong style={{ color: '#e2e8f0' }}>click en una burbuja</strong> para
                                ver los detalles de esa comunidad.
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
                                    <div
                                        key={i}
                                        onClick={() => setSelectedCommunity(community)}
                                        style={{
                                            display: 'flex', alignItems: 'center', gap: 8,
                                            cursor: 'pointer', padding: '2px 4px', borderRadius: 4,
                                            transition: 'background 0.2s',
                                            background: selectedCommunity?.name === community.name ? '#334155' : 'transparent',
                                        }}
                                    >
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

            {/* ─── Detail Panel (appears below on community click) ─── */}
            {selectedCommunity && selectedCommunity.children && (
                <div style={{
                    marginTop: 20, padding: 20, borderRadius: 16,
                    background: '#0f172a', border: '1px solid #334155',
                }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                            <div style={{
                                width: 14, height: 14, borderRadius: '50%',
                                background: selectedColor,
                            }} />
                            <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: '#f8fafc', margin: 0 }}>
                                {selectedCommunity.name}
                            </h3>
                            <span style={{
                                fontSize: '0.68rem', fontFamily: 'monospace',
                                background: '#312e81', color: '#a5b4fc', padding: '3px 8px', borderRadius: 4,
                            }}>
                                {selectedCommunity.children.length} Conceptos Top
                            </span>
                            <span style={{
                                fontSize: '0.65rem', fontFamily: 'monospace',
                                background: method === 'fuzzy' ? '#4c1d95' : '#1e1b4b',
                                color: method === 'fuzzy' ? '#c4b5fd' : '#a5b4fc',
                                padding: '3px 8px', borderRadius: 4,
                            }}>
                                {method === 'fuzzy' ? '🧠 Peso Semántico' : '🌍 Conteo de Archivos'}
                            </span>
                        </div>
                        <button
                            onClick={() => setSelectedCommunity(null)}
                            style={{
                                background: '#1e293b', border: '1px solid #334155', borderRadius: 6,
                                color: '#94a3b8', cursor: 'pointer', padding: 4,
                            }}
                        >
                            <X size={14} />
                        </button>
                    </div>

                    <div style={{
                        display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
                        gap: 10, maxHeight: 260, overflowY: 'auto', paddingRight: 4,
                    }}>
                        {selectedCommunity.children.map((child, idx) => (
                            <div key={idx} style={{
                                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                                background: '#1e293b', padding: '8px 12px', borderRadius: 8,
                                border: '1px solid #334155',
                            }}>
                                <span style={{
                                    fontSize: '0.82rem', color: '#e2e8f0',
                                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                                    marginRight: 8, flex: 1,
                                }} title={child.name}>
                                    {child.name}
                                </span>
                                <span style={{
                                    fontSize: '0.7rem', fontFamily: 'monospace',
                                    color: selectedColor, flexShrink: 0,
                                    background: selectedColor + '18', padding: '2px 6px', borderRadius: 4,
                                }}>
                                    {formatDegree(child.degree ?? child.loc)} {method === 'fuzzy' ? 'w' : 'refs'}
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
