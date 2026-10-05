import ChartFrame from '../graph/ChartFrame';
import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { ResponsiveHeatMap } from '@nivo/heatmap';
import { RefreshCw, Grid, Loader2, Info } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface HeatmapCell { x: string; y: number; }
interface HeatmapRow { id: string; data: HeatmapCell[]; }
interface AnalysisResponse {
    tool: string;
    status: string;
    message: string;
    mock_data: {
        matrix: HeatmapRow[];
        keys: string[];
        method: string;
    };
}

type JaccardMode = 'standard' | 'fuzzy';

const MODES: { key: JaccardMode; label: string; icon: string }[] = [
    { key: 'standard', label: 'Clásico', icon: '' },
    { key: 'fuzzy', label: 'Difuso', icon: '' },
];

const NARRATIVES: Record<JaccardMode, { title: string; desc: string; uso: string }> = {
    standard: {
        title: 'Jaccard Clásico (Conteo Binario)',
        desc: 'Esta vista es estricta. Cuenta físicamente cuántos archivos comparten ambos conceptos e ignora la "certeza" de la IA. Si "Filosofía" y "Muerte" aparecen en un mismo archivo, cuenta como 1 conexión completa.',
        uso: 'Ideal para ver la estructura dura y literal de tu información.',
    },
    fuzzy: {
        title: 'Jaccard Difuso (Pesos Semánticos)',
        desc: 'Esta vista considera los matices. Si un archivo menciona "Melancolía" fuertemente (0.9) pero "Amor" muy sutilmente (0.4), la intersección difusa toma el valor menor (0.4) para no exagerar la relación. Refleja fielmente la incertidumbre de la IA.',
        uso: 'Ideal para descubrir asociaciones sutiles y poéticas en tu red.',
    },
};

export default function HeatmapAnalysisCard() {
    const [data, setData] = useState<HeatmapRow[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [message, setMessage] = useState('');
    const [method, setMethod] = useState<JaccardMode>('standard');
    const [minWeight, setMinWeight] = useState<number>(0.0);
    const [debouncedWeight, setDebouncedWeight] = useState<number>(0.0);
    const navigate = useNavigate();

    useEffect(() => {
        const handler = setTimeout(() => {
            setDebouncedWeight(minWeight);
        }, 300);
        return () => clearTimeout(handler);
    }, [minWeight]);

    const fetchData = useCallback(async (m: JaccardMode, w: number) => {
        setLoading(true);
        setError(null);
        try {
            const res = await axios.post<AnalysisResponse>(
                `http://localhost:8000/analysis/heatmap?method=${m}&min_weight=${w}`
            );
            if (res.data.status === 'error') throw new Error(res.data.message);
            setData(res.data.mock_data.matrix);
            setMessage(res.data.message);
        } catch (err: any) {
            console.error(err);
            setError(err.message || 'Error fetching heatmap data');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { fetchData(method, debouncedWeight); }, [method, debouncedWeight, fetchData]);

    const narrative = NARRATIVES[method];

    const theme = {
        background: 'transparent',
        textColor: 'var(--text-secondary)',
        fontSize: 10,
        axis: {
            domain: { line: { stroke: 'var(--border)', strokeWidth: 1 } },
            ticks: { line: { stroke: 'var(--border)', strokeWidth: 1 }, text: { fill: 'var(--text-secondary)', fontSize: 10 } },
            legend: { text: { fill: 'var(--text-muted)', fontSize: 11 } },
        },
        labels: { text: { fontSize: 9 } },
        tooltip: {
            container: {
                background: 'var(--background-secondary)', color: 'var(--text-primary)', fontSize: 12,
                borderRadius: 8, boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
                padding: '10px 14px', border: '1px solid var(--border)',
            },
        },
    };

    const colorScheme = method === 'fuzzy' ? 'purples' : 'reds';
    const accentColor = method === 'fuzzy' ? '#a78bfa' : '#fca5a5';
    const accentGradient = method === 'fuzzy'
        ? 'var(--gradient-primary)'
        : 'var(--gradient-primary)';

    return (
        <div style={{ padding: 24, paddingBottom: 60, width: '100%' }}>
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
                <button onClick={() => fetchData(method, debouncedWeight)} className="btn-icon" disabled={loading}>
                    <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
                </button>
            </div>

            {error ? (
                <div className="p-8 text-red-500 border border-red-200 rounded">{error}</div>
            ) : (
                <div className="responsive-panels" style={{ display: 'flex', gap: 20 }}>
                    {/* Main Heatmap */}
                    <div
                        className="bg-white dark:bg-slate-950 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800"
                        style={{ flex: '1 1 0', minHeight: 700, padding: 16, position: 'relative', minWidth: 0 }}
                    >
                        {loading ? (
                            <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-400">
                                <Loader2 className="animate-spin mb-4" size={32} />
                                <p>Calculando co-ocurrencia {method === 'fuzzy' ? 'difusa' : 'clásica'}...</p>
                            </div>
                        ) : data.length === 0 ? (
                            <div className="absolute inset-0 flex items-center justify-center text-slate-400">
                                No hay suficientes conceptos conectados a archivos.
                            </div>
                        ) : (
                            <div style={{ height: 700 }}>
                                <ChartFrame title="Matriz de relaciones"><ResponsiveHeatMap
                                    data={data}
                                    margin={{ top: 120, right: 20, bottom: 20, left: 120 }}
                                    valueFormat=">-.2f"
                                    axisTop={{
                                        tickSize: 5, tickPadding: 5, tickRotation: -55,
                                        legend: '', legendOffset: 46,
                                    }}
                                    axisLeft={{
                                        tickSize: 5, tickPadding: 5, tickRotation: 0,
                                        legend: '', legendPosition: 'middle', legendOffset: -72,
                                    }}
                                    axisRight={null}
                                    colors={{
                                        type: 'sequential',
                                        scheme: colorScheme as any,
                                        minValue: 0,
                                        maxValue: 1,
                                    }}
                                    emptyColor="var(--background-secondary)"
                                    borderWidth={1}
                                    borderColor="var(--surface)"
                                    labelTextColor={({ value }) =>
                                        (value ?? 0) > 0.5 ? '#fef2f2' : 'var(--text-muted)'
                                    }
                                    theme={theme}
                                    hoverTarget="cell"
                                    animate={true}
                                    motionConfig="gentle"
                                    tooltip={({ cell }) => (
                                        <div style={{
                                            background: 'var(--background-secondary)', border: '1px solid var(--border)',
                                            borderRadius: 8, padding: '10px 14px', color: 'var(--text-primary)',
                                            fontSize: 12, boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
                                        }}>
                                            <div style={{ fontWeight: 700, marginBottom: 4 }}>
                                                {cell.serieId} ↔ {cell.data.x}
                                            </div>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                                <div style={{
                                                    width: 12, height: 12, borderRadius: 3,
                                                    background: cell.color,
                                                }} />
                                                <span>
                                                    {method === 'fuzzy' ? 'Fuzzy Jaccard' : 'Jaccard'}:{' '}
                                                    <strong>{cell.formattedValue}</strong>
                                                </span>
                                            </div>
                                        </div>
                                    )}
                                /></ChartFrame>
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
                            border: '1px solid var(--border)', marginBottom: 20,
                        }}>
                            {MODES.map(m => (
                                <button
                                    key={m.key}
                                    onClick={() => setMethod(m.key)}
                                    style={{
                                        flex: 1, padding: '8px 4px', fontSize: '0.72rem', fontWeight: 600,
                                        border: 'none', cursor: 'pointer',
                                        transition: 'all 0.25s ease',
                                        background: method === m.key
                                            ? (m.key === 'fuzzy' ? '#7c3aed' : '#dc2626')
                                            : 'var(--background-secondary)',
                                        color: method === m.key ? '#ffffff' : 'var(--text-muted)',
                                    }}
                                >
                                    {m.icon} {m.label}
                                </button>
                            ))}
                        </div>

                        {/* Threshold Slider */}
                        <div style={{
                            background: 'var(--surface)', borderRadius: 8, padding: 12, marginBottom: 16,
                            border: '1px solid var(--border)',
                        }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 600 }}>
                                    UMBRAL DE CONFIANZA
                                </div>
                                <div style={{ fontSize: '0.9rem', color: 'var(--text-primary)', fontWeight: 700 }}>
                                    {minWeight.toFixed(2)}
                                </div>
                            </div>
                            <input
                                type="range"
                                min="0" max="0.9" step="0.05"
                                value={minWeight}
                                onChange={(e) => setMinWeight(parseFloat(e.target.value))}
                                style={{ width: '100%', cursor: 'pointer', accentColor }}
                            />
                            <p style={{ fontSize: '0.65rem', color: 'var(--text-muted)', margin: '8px 0 0 0', lineHeight: 1.4 }}>
                                Ignora conexiones menores al umbral para reducir el ruido.
                            </p>
                        </div>

                        {/* Dynamic Title */}
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
                            <Info size={18} style={{ color: accentColor }} />
                            <h3 style={{ fontSize: '0.88rem', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
                                {narrative.title}
                            </h3>
                        </div>

                        {/* Description */}
                        <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: 1.7, marginBottom: 16 }}>
                            {narrative.desc}
                        </p>

                        {/* Uso */}
                        <div style={{
                            background: 'var(--surface)', borderRadius: 8, padding: 12, marginBottom: 16,
                            border: '1px solid var(--border)',
                        }}>
                            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 600, marginBottom: 6 }}>
                                USO
                            </div>
                            <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', lineHeight: 1.5, margin: 0 }}>
                                {narrative.uso}
                            </p>
                        </div>

                        {/* Color scale */}
                        <div style={{
                            background: 'var(--surface)', borderRadius: 8, padding: 12, marginBottom: 16,
                            border: '1px solid var(--border)',
                        }}>
                            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 600, marginBottom: 8 }}>
                                ESCALA DE SIMILITUD
                            </div>
                            <div style={{
                                height: 12, borderRadius: 6, marginBottom: 6,
                                background: accentGradient,
                            }} />
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.65rem', color: 'var(--text-muted)' }}>
                                <span>0.0 — Sin relación</span>
                                <span>1.0 — Idénticos</span>
                            </div>
                        </div>

                        {/* Formula */}
                        <div style={{
                            background: 'var(--surface)', borderRadius: 8, padding: 12, marginBottom: 16,
                            border: '1px solid var(--border)',
                        }}>
                            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 600, marginBottom: 6 }}>
                                FÓRMULA
                            </div>
                            <p style={{
                                fontSize: '0.72rem', color: 'var(--text-secondary)', lineHeight: 1.5, margin: 0,
                                fontFamily: 'monospace',
                            }}>
                                {method === 'fuzzy' ? (
                                    <>
                                        <strong style={{ color: '#c4b5fd' }}>J<sub>fuzzy</sub></strong> = Σ min(w₁, w₂) / Σ(w₁ + w₂ − min)
                                    </>
                                ) : (
                                    <>
                                        <strong style={{ color: 'var(--text-primary)' }}>J</strong> = |A ∩ B| / |A ∪ B|
                                    </>
                                )}
                            </p>
                        </div>

                        {message && (
                            <div style={{
                                fontSize: '0.7rem', color: '#4ade80',
                                padding: '8px 12px', background: '#22c55e10', borderRadius: 6,
                                border: '1px solid #22c55e30',
                            }}>
                                 {message}
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
