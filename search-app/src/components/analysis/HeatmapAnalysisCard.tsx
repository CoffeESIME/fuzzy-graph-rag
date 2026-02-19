import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { ResponsiveHeatMap } from '@nivo/heatmap';
import { RefreshCw, Grid, Loader2, Info } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface HeatmapCell {
    x: string;
    y: number;
}

interface HeatmapRow {
    id: string;
    data: HeatmapCell[];
}

interface AnalysisResponse {
    tool: string;
    status: string;
    message: string;
    mock_data: {
        matrix: HeatmapRow[];
        keys: string[];
    };
}

export default function HeatmapAnalysisCard() {
    const [data, setData] = useState<HeatmapRow[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [message, setMessage] = useState('');
    const navigate = useNavigate();

    const fetchData = async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await axios.post<AnalysisResponse>('http://localhost:8000/analysis/heatmap');
            if (res.data.status === 'error') throw new Error(res.data.message);
            setData(res.data.mock_data.matrix);
            setMessage(res.data.message);
        } catch (err: any) {
            console.error(err);
            setError(err.message || 'Error fetching heatmap data');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
    }, []);

    const theme = {
        background: 'transparent',
        textColor: '#94a3b8',
        fontSize: 10,
        axis: {
            domain: {
                line: { stroke: '#334155', strokeWidth: 1 }
            },
            ticks: {
                line: { stroke: '#334155', strokeWidth: 1 },
                text: { fill: '#94a3b8', fontSize: 10 }
            },
            legend: {
                text: { fill: '#64748b', fontSize: 11 }
            }
        },
        labels: {
            text: { fontSize: 9 }
        },
        tooltip: {
            container: {
                background: '#0f172a',
                color: '#f8fafc',
                fontSize: 12,
                borderRadius: 8,
                boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
                padding: '10px 14px',
                border: '1px solid #334155'
            }
        }
    };

    if (loading) return (
        <div className="flex flex-col items-center justify-center p-12 text-gray-500 min-h-[400px]">
            <Loader2 className="animate-spin mb-4" size={32} />
            <p>Calculando co-ocurrencia Jaccard entre conceptos...</p>
        </div>
    );

    return (
        <div style={{ padding: 24, paddingBottom: 60, maxWidth: 1200, margin: '0 auto' }}>
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-4">
                    <button onClick={() => navigate('/analysis')} className="btn-secondary">Back</button>
                    <div>
                        <h2 className="text-2xl font-bold flex items-center gap-2">
                            <Grid className="text-red-500" />
                            Matriz de Co-Ocurrencia
                        </h2>
                        <p className="text-gray-500">
                            Similitud Jaccard entre los conceptos más conectados del grafo.
                        </p>
                    </div>
                </div>
                <button onClick={fetchData} className="btn-icon">
                    <RefreshCw size={18} />
                </button>
            </div>

            {error ? (
                <div className="p-8 text-red-500 border border-red-200 rounded">{error}</div>
            ) : (
                <div style={{ display: 'flex', gap: 20 }}>
                    {/* Main Heatmap */}
                    <div
                        className="bg-white dark:bg-slate-950 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800"
                        style={{ flex: '1 1 0', height: 700, padding: 16, position: 'relative', minWidth: 0 }}
                    >
                        {data.length === 0 ? (
                            <div className="absolute inset-0 flex items-center justify-center text-slate-400">
                                No hay suficientes conceptos conectados a archivos.
                            </div>
                        ) : (
                            <ResponsiveHeatMap
                                data={data}
                                margin={{ top: 120, right: 20, bottom: 20, left: 120 }}
                                valueFormat=">-.2f"
                                axisTop={{
                                    tickSize: 5,
                                    tickPadding: 5,
                                    tickRotation: -55,
                                    legend: '',
                                    legendOffset: 46
                                }}
                                axisLeft={{
                                    tickSize: 5,
                                    tickPadding: 5,
                                    tickRotation: 0,
                                    legend: '',
                                    legendPosition: 'middle',
                                    legendOffset: -72
                                }}
                                axisRight={null}
                                colors={{
                                    type: 'sequential',
                                    scheme: 'reds',
                                    minValue: 0,
                                    maxValue: 1
                                }}
                                emptyColor="#0f172a"
                                borderWidth={1}
                                borderColor="#1e293b"
                                labelTextColor={({ value }) =>
                                    (value ?? 0) > 0.5 ? '#fef2f2' : '#64748b'
                                }
                                theme={theme}
                                hoverTarget="cell"
                                cellOpacity={1}
                                cellHoverOpacity={0.85}
                                cellHoverOthersOpacity={0.2}
                                tooltip={({ cell }) => (
                                    <div style={{
                                        background: '#0f172a',
                                        border: '1px solid #334155',
                                        borderRadius: 8,
                                        padding: '10px 14px',
                                        color: '#f8fafc',
                                        fontSize: 12,
                                        boxShadow: '0 8px 24px rgba(0,0,0,0.4)'
                                    }}>
                                        <div style={{ fontWeight: 700, marginBottom: 4 }}>
                                            {cell.serieId} ↔ {cell.data.x}
                                        </div>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                            <div style={{
                                                width: 12, height: 12, borderRadius: 3,
                                                background: cell.color
                                            }} />
                                            <span>Jaccard: <strong>{cell.formattedValue}</strong></span>
                                        </div>
                                    </div>
                                )}
                            />
                        )}
                    </div>

                    {/* Explanation Side Panel */}
                    <div
                        className="bg-white dark:bg-slate-950 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800"
                        style={{ width: 280, padding: 20, flexShrink: 0 }}
                    >
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
                            <Info size={18} className="text-red-400" />
                            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#f8fafc', margin: 0 }}>
                                ¿Qué veo aquí?
                            </h3>
                        </div>

                        <p style={{ fontSize: '0.78rem', color: '#94a3b8', lineHeight: 1.6, marginBottom: 16 }}>
                            Esta gráfica muestra qué conceptos <strong style={{ color: '#e2e8f0' }}>aparecen juntos</strong> en
                            tus archivos. A diferencia de una conexión directa, esto revela <em>temáticas</em>.
                        </p>

                        <p style={{ fontSize: '0.78rem', color: '#94a3b8', lineHeight: 1.6, marginBottom: 16 }}>
                            Si <strong style={{ color: '#fca5a5' }}>"Amor"</strong> y <strong style={{ color: '#fca5a5' }}>"Dolor"</strong> tienen
                            un cuadro brillante en su intersección, significa que tus archivos suelen tratar ambos
                            temas <em>simultáneamente</em>.
                        </p>

                        <div style={{
                            background: '#1e293b', borderRadius: 8, padding: 12, marginBottom: 16,
                            border: '1px solid #334155'
                        }}>
                            <div style={{ fontSize: '0.7rem', color: '#64748b', fontWeight: 600, marginBottom: 8 }}>
                                ESCALA DE SIMILITUD
                            </div>
                            <div style={{
                                height: 12, borderRadius: 6,
                                background: 'linear-gradient(90deg, #0f172a, #7f1d1d, #dc2626, #ef4444, #fca5a5)',
                                marginBottom: 6
                            }} />
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.65rem', color: '#64748b' }}>
                                <span>0.0 — Sin relación</span>
                                <span>1.0 — Idénticos</span>
                            </div>
                        </div>

                        <div style={{
                            background: '#1e293b', borderRadius: 8, padding: 12,
                            border: '1px solid #334155'
                        }}>
                            <div style={{ fontSize: '0.7rem', color: '#64748b', fontWeight: 600, marginBottom: 6 }}>
                                MÉTODO
                            </div>
                            <p style={{ fontSize: '0.72rem', color: '#94a3b8', lineHeight: 1.5, margin: 0 }}>
                                <strong style={{ color: '#e2e8f0' }}>Jaccard</strong> =
                                Archivos compartidos / Archivos totales.
                                J = |A ∩ B| / |A ∪ B|
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
            )}
        </div>
    );
}
