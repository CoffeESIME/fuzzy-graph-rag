import { useEffect, useState } from 'react';
import axios from 'axios';
import { ResponsiveScatterPlot } from '@nivo/scatterplot';
import { RefreshCw, Shapes, Loader2, Info } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface ScatterPoint {
    x: number;
    y: number;
    name: string;
}

interface ScatterSeries {
    id: string;
    data: ScatterPoint[];
}

interface AnalysisResponse {
    tool: string;
    status: string;
    message: string;
    mock_data: {
        series: ScatterSeries[];
    };
}

export default function AbstractConceptsCard() {
    const [data, setData] = useState<ScatterSeries[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [message, setMessage] = useState('');
    const navigate = useNavigate();

    const fetchData = async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await axios.post<AnalysisResponse>('http://localhost:8000/analysis/abstract-concepts');
            if (res.data.status === 'error') throw new Error(res.data.message);
            setData(res.data.mock_data.series);
            setMessage(res.data.message);
        } catch (err: any) {
            console.error(err);
            setError(err.message || 'Error fetching abstract concepts');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
    }, []);

    const nivoTheme = {
        background: 'transparent',
        textColor: '#94a3b8',
        fontSize: 11,
        axis: {
            domain: { line: { stroke: '#475569', strokeWidth: 1 } },
            ticks: { line: { stroke: '#475569', strokeWidth: 1 }, text: { fill: '#94a3b8', fontSize: 11 } },
            legend: { text: { fill: '#cbd5e1', fontSize: 12, fontWeight: 600 } },
        },
        grid: { line: { stroke: '#1e293b', strokeWidth: 1 } },
        tooltip: {
            container: {
                background: '#0f172a',
                color: '#f8fafc',
                fontSize: 12,
                borderRadius: 8,
                boxShadow: '0 8px 24px rgb(0 0 0 / 0.4)',
                padding: '10px 14px',
                border: '1px solid #334155',
            },
        },
    };

    if (loading)
        return (
            <div className="flex flex-col items-center justify-center p-12 text-gray-500 min-h-[400px]">
                <Loader2 className="animate-spin mb-4" size={32} />
                <p>Analizando conceptos...</p>
            </div>
        );

    return (
        <div style={{ padding: 24, paddingBottom: 60, maxWidth: 1200, width: '100%', margin: '0 auto' }}>
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-4">
                    <button onClick={() => navigate('/analysis')} className="btn-secondary">Back</button>
                    <div>
                        <h2 className="text-2xl font-bold flex items-center gap-2 text-slate-100">
                            <Shapes className="text-purple-500" />
                            Distribución de Conceptos
                        </h2>
                        <p className="text-sm text-slate-500">
                            Grado vs. Certeza — cada punto es un concepto de tu grafo.
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
                    {/* Chart */}
                    <div
                        className="bg-white dark:bg-slate-950 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800"
                        style={{ flex: 1, height: 600, padding: 16, position: 'relative' }}
                    >
                        {data.length === 0 || data[0]?.data.length === 0 ? (
                            <div className="absolute inset-0 flex items-center justify-center text-slate-400">
                                No se encontraron conceptos con degree ≥ 2.
                            </div>
                        ) : (
                            <ResponsiveScatterPlot
                                data={data}
                                margin={{ top: 30, right: 30, bottom: 70, left: 80 }}
                                xScale={{ type: 'linear', min: 'auto', max: 'auto' }}
                                yScale={{ type: 'linear', min: 0, max: 1.1 }}
                                blendMode="normal"
                                colors={['#8b5cf6']}
                                nodeSize={14}
                                axisTop={null}
                                axisRight={null}
                                axisBottom={{
                                    tickSize: 5,
                                    tickPadding: 5,
                                    tickRotation: 0,
                                    legend: 'Cantidad de Conexiones (Grado)',
                                    legendPosition: 'middle',
                                    legendOffset: 50,
                                }}
                                axisLeft={{
                                    tickSize: 5,
                                    tickPadding: 5,
                                    tickRotation: 0,
                                    legend: 'Certeza (Peso Promedio)',
                                    legendPosition: 'middle',
                                    legendOffset: -55,
                                }}
                                theme={nivoTheme}
                                tooltip={({ node }) => {
                                    const pt = node.data as unknown as ScatterPoint;
                                    return (
                                        <div
                                            style={{
                                                background: '#0f172a',
                                                color: '#f8fafc',
                                                padding: '10px 14px',
                                                borderRadius: 8,
                                                border: '1px solid #334155',
                                                fontSize: 12,
                                                maxWidth: 220,
                                            }}
                                        >
                                            <div style={{ fontWeight: 700, marginBottom: 4, color: '#a78bfa' }}>
                                                💡 {pt.name || node.id}
                                            </div>
                                            <div style={{ color: '#94a3b8' }}>
                                                Conexiones: <strong style={{ color: '#e2e8f0' }}>{pt.x}</strong>
                                            </div>
                                            <div style={{ color: '#94a3b8' }}>
                                                Certeza: <strong style={{ color: '#e2e8f0' }}>{pt.y}</strong>
                                            </div>
                                        </div>
                                    );
                                }}
                            />
                        )}
                    </div>

                    {/* Explanation Side Panel */}
                    <div
                        className="bg-white dark:bg-slate-950 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800"
                        style={{ width: 260, padding: 20, flexShrink: 0 }}
                    >
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
                            <Info size={18} className="text-purple-400" />
                            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#f8fafc', margin: 0 }}>
                                ¿Qué veo aquí?
                            </h3>
                        </div>

                        <p style={{ fontSize: '0.78rem', color: '#94a3b8', lineHeight: 1.6, marginBottom: 16 }}>
                            Cada punto es un <strong style={{ color: '#e2e8f0' }}>Concepto</strong> de tu grafo
                            de conocimiento.
                        </p>

                        <div
                            style={{
                                background: '#1e293b',
                                borderRadius: 8,
                                padding: 12,
                                marginBottom: 16,
                                border: '1px solid #334155',
                            }}
                        >
                            <div style={{ fontSize: '0.7rem', color: '#64748b', fontWeight: 600, marginBottom: 8 }}>
                                EJES
                            </div>
                            <div style={{ fontSize: '0.75rem', color: '#94a3b8', lineHeight: 1.7 }}>
                                <strong style={{ color: '#e2e8f0' }}>X — Grado:</strong> Cuántos archivos lo
                                mencionan. Más a la derecha = más popular.
                                <br />
                                <strong style={{ color: '#e2e8f0' }}>Y — Certeza:</strong> Peso promedio de
                                sus relaciones. Más arriba = mayor confianza.
                            </div>
                        </div>

                        <div
                            style={{
                                background: '#1e293b',
                                borderRadius: 8,
                                padding: 12,
                                marginBottom: 16,
                                border: '1px solid #334155',
                            }}
                        >
                            <div style={{ fontSize: '0.7rem', color: '#64748b', fontWeight: 600, marginBottom: 8 }}>
                                INTERPRETACIÓN
                            </div>
                            <div style={{ fontSize: '0.75rem', color: '#94a3b8', lineHeight: 1.7 }}>
                                <strong style={{ color: '#34d399' }}>↗ Arriba-derecha:</strong> Conceptos concretos y
                                frecuentes (pilares).
                                <br />
                                <strong style={{ color: '#fbbf24' }}>↙ Abajo-izquierda:</strong> Conceptos vagos y
                                raros.
                                <br />
                                <strong style={{ color: '#f87171' }}>↘ Abajo-derecha:</strong> Aparecen mucho pero con
                                bajo peso — posibles conceptos «pegamento» abstracto.
                            </div>
                        </div>

                        {message && (
                            <div
                                style={{
                                    fontSize: '0.7rem',
                                    color: '#4ade80',
                                    padding: '8px 12px',
                                    background: '#22c55e10',
                                    borderRadius: 6,
                                    border: '1px solid #22c55e30',
                                }}
                            >
                                ✅ {message}
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
