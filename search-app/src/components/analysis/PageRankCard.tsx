import { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { ResponsiveBar } from '@nivo/bar';
import { RefreshCw, Crown, Loader2, Info } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface RankItem {
    [key: string]: string | number;
    id: string;
    value: number;
}

interface AnalysisResponse {
    tool: string;
    status: string;
    message: string;
    mock_data: {
        ranking: RankItem[];
        method?: string;
    };
}

type PRMode = 'standard' | 'fuzzy';

const NARRATIVES: Record<PRMode, { title: string; icon: string; desc: string }> = {
    standard: {
        title: 'PageRank Discreto (Popularidad Estructural)',
        icon: '👑',
        desc: 'Mide la "popularidad" pura. Un concepto es influyente si aparece en muchos archivos junto a otros conceptos también populares. Revela la columna vertebral literal de tus datos.',
    },
    fuzzy: {
        title: 'PageRank Difuso (Autoridad Semántica)',
        icon: '🎯',
        desc: 'Mide la "autoridad" profunda. Toma en cuenta la certeza de la IA. Un concepto gana influencia solo si sus conexiones son fuertes e inequívocas (pesos cercanos a 1.0), filtrando el ruido genérico.',
    },
};

export default function PageRankCard() {
    const [data, setData] = useState<RankItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [message, setMessage] = useState('');
    const [method, setMethod] = useState<PRMode>('standard');
    const [minWeight, setMinWeight] = useState<number>(0.0);
    const [debouncedWeight, setDebouncedWeight] = useState<number>(0.0);
    const navigate = useNavigate();

    useEffect(() => {
        const handler = setTimeout(() => {
            setDebouncedWeight(minWeight);
        }, 300);
        return () => clearTimeout(handler);
    }, [minWeight]);

    const fetchData = useCallback(async (m: PRMode, w: number) => {
        setLoading(true);
        setError(null);
        try {
            const res = await axios.post<AnalysisResponse>(
                `http://localhost:8000/analysis/pagerank?method=${m}&min_weight=${w}`
            );
            if (res.data.status === 'error') throw new Error(res.data.message);
            // Reverse for Nivo horizontal bar (index 0 at bottom)
            setData([...res.data.mock_data.ranking].reverse());
            setMessage(res.data.message);
        } catch (err: any) {
            console.error(err);
            setError(err.message || 'Error fetching PageRank data');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { fetchData(method, debouncedWeight); }, [method, debouncedWeight, fetchData]);

    const narrative = NARRATIVES[method];
    const barColor = method === 'fuzzy' ? '#a78bfa' : '#f59e0b';

    const theme = {
        background: 'transparent',
        textColor: '#94a3b8',
        fontSize: 11,
        axis: {
            domain: { line: { stroke: '#475569', strokeWidth: 1 } },
            ticks: { line: { stroke: '#475569', strokeWidth: 1 }, text: { fill: '#94a3b8' } },
        },
        grid: { line: { stroke: '#334155', strokeWidth: 1 } },
        tooltip: {
            container: {
                background: '#0f172a', color: '#f8fafc', fontSize: 12,
                borderRadius: 8, boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
                padding: '10px 14px', border: '1px solid #334155',
            },
        },
    };

    return (
        <div style={{ padding: 24, paddingBottom: 60, maxWidth: 1200, width: '100%', margin: '0 auto' }}>
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-4">
                    <button onClick={() => navigate('/analysis')} className="btn-secondary">Back</button>
                    <div>
                        <h2 className="text-2xl font-bold flex items-center gap-2">
                            <Crown className="text-yellow-500" />
                            PageRank de Conceptos
                        </h2>
                        <p className="text-gray-500">Ranking de influencia topológica en el grafo de conocimiento.</p>
                    </div>
                </div>
                <button onClick={() => fetchData(method, debouncedWeight)} className="btn-icon" disabled={loading}>
                    <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
                </button>
            </div>

            {error ? (
                <div className="p-8 text-red-500 border border-red-200 rounded">{error}</div>
            ) : (
                <div style={{ display: 'flex', gap: 20 }}>
                    {/* Main Bar Chart */}
                    <div
                        className="bg-white dark:bg-slate-950 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800"
                        style={{ flex: '1 1 0', height: 660, padding: 16, position: 'relative', minWidth: 0 }}
                    >
                        {loading ? (
                            <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-400">
                                <Loader2 className="animate-spin mb-4" size={32} />
                                <p>Calculando {method === 'fuzzy' ? 'Fuzzy' : 'Standard'} PageRank...</p>
                            </div>
                        ) : data.length === 0 ? (
                            <div className="absolute inset-0 flex items-center justify-center text-slate-400">
                                No significant ranking data found.
                            </div>
                        ) : (
                            <ResponsiveBar
                                data={data}
                                keys={['value']}
                                indexBy="id"
                                layout="horizontal"
                                margin={{ top: 10, right: 30, bottom: 50, left: 150 }}
                                padding={0.3}
                                valueScale={{ type: 'linear' }}
                                indexScale={{ type: 'band', round: true }}
                                colors={() => barColor}
                                borderColor={{ from: 'color', modifiers: [['darker', 1.6]] }}
                                axisTop={null}
                                axisRight={null}
                                axisBottom={{
                                    tickSize: 5, tickPadding: 5, tickRotation: 0,
                                    legend: 'PageRank Score', legendPosition: 'middle', legendOffset: 36,
                                }}
                                axisLeft={{
                                    tickSize: 5, tickPadding: 5, tickRotation: 0,
                                    legend: '', legendOffset: -40,
                                }}
                                labelSkipWidth={12}
                                labelSkipHeight={12}
                                labelTextColor={{ from: 'color', modifiers: [['darker', 2]] }}
                                label={d => (d.value as number).toFixed(4)}
                                theme={theme}
                                animate={true}
                                motionConfig="gentle"
                                tooltip={({ indexValue, value }) => (
                                    <div style={{
                                        background: '#0f172a', border: '1px solid #334155',
                                        borderRadius: 8, padding: '10px 14px', color: '#f8fafc',
                                        fontSize: 12, boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
                                    }}>
                                        <div style={{ fontWeight: 700, marginBottom: 4 }}>{indexValue}</div>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                            <div style={{
                                                width: 12, height: 12, borderRadius: 3,
                                                background: barColor,
                                            }} />
                                            <span>
                                                {method === 'fuzzy' ? 'Fuzzy' : ''} PageRank:{' '}
                                                <strong>{(value as number).toFixed(4)}</strong>
                                            </span>
                                        </div>
                                    </div>
                                )}
                            />
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
                            {(['standard', 'fuzzy'] as PRMode[]).map(m => (
                                <button
                                    key={m}
                                    onClick={() => setMethod(m)}
                                    style={{
                                        flex: 1, padding: '8px 4px', fontSize: '0.72rem', fontWeight: 600,
                                        border: 'none', cursor: 'pointer',
                                        transition: 'all 0.25s ease',
                                        background: method === m
                                            ? (m === 'fuzzy' ? '#7c3aed' : '#d97706')
                                            : '#0f172a',
                                        color: method === m ? '#ffffff' : '#64748b',
                                    }}
                                >
                                    {m === 'standard' ? '👑 Standard' : '🎯 Fuzzy'}
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
                                    {minWeight.toFixed(1)}
                                </div>
                            </div>
                            <input
                                type="range"
                                min="0" max="0.9" step="0.1"
                                value={minWeight}
                                onChange={(e) => setMinWeight(parseFloat(e.target.value))}
                                style={{ width: '100%', cursor: 'pointer', accentColor: barColor }}
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
                            <Info size={18} style={{ color: barColor }} />
                            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#f8fafc', margin: 0 }}>
                                ¿Qué es PageRank?
                            </h3>
                        </div>

                        <p style={{ fontSize: '0.78rem', color: '#94a3b8', lineHeight: 1.7, marginBottom: 16 }}>
                            Inventado por Google, <strong style={{ color: '#e2e8f0' }}>PageRank</strong> mide la
                            importancia de un nodo no solo por sus conexiones directas, sino por la importancia de
                            <em> quién lo conecta</em>.
                        </p>

                        <div style={{
                            background: '#1e293b', borderRadius: 8, padding: 12, marginBottom: 16,
                            border: '1px solid #334155',
                        }}>
                            <div style={{ fontSize: '0.7rem', color: '#64748b', fontWeight: 600, marginBottom: 6 }}>
                                FÓRMULA
                            </div>
                            <p style={{
                                fontSize: '0.72rem', color: '#94a3b8', lineHeight: 1.5, margin: 0,
                                fontFamily: 'monospace',
                            }}>
                                PR(A) = (1−d) + d × Σ PR(T<sub>i</sub>) / C(T<sub>i</sub>)
                            </p>
                            <p style={{ fontSize: '0.65rem', color: '#64748b', marginTop: 4, margin: 0 }}>
                                d = 0.85 (damping factor)
                            </p>
                        </div>

                        {message && (
                            <div style={{
                                fontSize: '0.7rem', color: '#4ade80',
                                padding: '8px 12px', background: '#22c55e10', borderRadius: 6,
                                border: '1px solid #22c55e30',
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
