import ChartFrame from '../graph/ChartFrame';
import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { ResponsiveBar } from '@nivo/bar';
import { RefreshCw, BarChart3, Loader2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface HistogramBin {
    [key: string]: string | number;
    range: string; // "0.0-0.1"
    count: number;
    bucket: number;
}

interface AnalysisResponse {
    tool: string;
    status: string;
    message: string;
    mock_data: {
        histogram: HistogramBin[];
    };
}

export default function WeightDistributionCard() {
    const [data, setData] = useState<HistogramBin[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [step, setStep] = useState<number>(0.1);
    const navigate = useNavigate();

    const fetchData = useCallback(async (currentStep: number) => {
        setLoading(true);
        setError(null);
        try {
            const res = await axios.post<AnalysisResponse>(`http://localhost:8000/analysis/weight-distribution?step=${currentStep}`);
            if (res.data.status === 'error') throw new Error(res.data.message);
            setData(res.data.mock_data.histogram);
        } catch (err: any) {
            console.error(err);
            setError(err.message || 'Error fetching distributions');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchData(step);
    }, [step, fetchData]);

    const theme = {
        background: 'transparent',
        textColor: 'var(--text-secondary)',
        fontSize: 11,
        axis: {
            domain: { line: { stroke: 'var(--text-muted)', strokeWidth: 1 } },
            ticks: { line: { stroke: 'var(--text-muted)', strokeWidth: 1 }, text: { fill: 'var(--text-secondary)' } }
        },
        grid: { line: { stroke: 'var(--border)', strokeWidth: 1 } },
        tooltip: {
            container: {
                background: 'var(--surface)',
                color: 'var(--text-primary)',
                fontSize: 12,
                borderRadius: 4,
                boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
                padding: '8px 12px'
            }
        }
    };

    if (loading) return (
        <div className="flex flex-col items-center justify-center p-12 text-gray-500 min-h-[400px]">
            <Loader2 className="animate-spin mb-4" size={32} />
            <p>Analizando la distribución de confianza...</p>
        </div>
    );

    return (
        <div style={{ padding: 24, paddingBottom: 60, maxWidth: 1000, width: '100%', margin: '0 auto' }}>
            <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-4">
                    <button onClick={() => navigate('/analysis')} className="btn-secondary">Back</button>
                    <div>
                        <h2 className="text-2xl font-bold flex items-center gap-2">
                            <BarChart3 className="text-cyan-500" />
                            Distribución de Pesos
                        </h2>
                        <p className="text-gray-500">Histograma de la fuerza de las relaciones en el grafo.</p>
                    </div>
                </div>
                <div className="flex items-center gap-3">
                    <div style={{ display: 'flex', borderRadius: 6, overflow: 'hidden', border: '1px solid var(--border)' }}>
                        {[0.1, 0.05].map(s => (
                            <button
                                key={s}
                                onClick={() => setStep(s)}
                                style={{
                                    padding: '6px 12px', fontSize: '0.75rem', fontWeight: 600,
                                    border: 'none', cursor: 'pointer', transition: 'all 0.25s ease',
                                    background: step === s ? '#06b6d4' : 'var(--background-secondary)',
                                    color: step === s ? '#ffffff' : 'var(--text-secondary)',
                                }}
                            >
                                Paso {s}
                            </button>
                        ))}
                    </div>
                    <button onClick={() => fetchData(step)} className="btn-icon">
                        <RefreshCw size={18} className={loading && !data.length ? 'animate-spin' : ''} />
                    </button>
                </div>
            </div>

            {error ? (
                <div className="p-8 text-red-500 border border-red-200 rounded">{error}</div>
            ) : (
                <div className="bg-white dark:bg-slate-950 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800 p-4 h-[500px] w-full relative">
                    {data.length === 0 ? (
                        <div className="absolute inset-0 flex items-center justify-center text-slate-400">
                            No data available.
                        </div>
                    ) : (
                        <ChartFrame title="Distribución de pesos"><ResponsiveBar
                            data={data}
                            keys={['count']}
                            indexBy="range"
                            margin={{ top: 20, right: 30, bottom: 50, left: 60 }}
                            padding={0.3}
                            valueScale={{ type: 'linear' }}
                            indexScale={{ type: 'band', round: true }}
                            // Custom color per bar
                            colors={() => '#06b6d4'}
                            axisTop={null}
                            axisRight={null}
                            axisBottom={{
                                tickSize: 5,
                                tickPadding: 5,
                                tickRotation: 0,
                                legend: 'Rango de Peso (Confianza)',
                                legendPosition: 'middle',
                                legendOffset: 32
                            }}
                            axisLeft={{
                                tickSize: 5,
                                tickPadding: 5,
                                tickRotation: 0,
                                legend: 'Cantidad de Relaciones',
                                legendPosition: 'middle',
                                legendOffset: -40
                            }}
                            labelSkipWidth={12}
                            labelSkipHeight={12}
                            labelTextColor={{ from: 'color', modifiers: [['darker', 1.6]] }}
                            theme={theme}
                            role="application"
                            ariaLabel="Weight Distribution Histogram"
                        /></ChartFrame>
                    )}
                </div>
            )}

            <div className="mt-6 text-center text-sm text-slate-500 max-w-2xl mx-auto">
                "Esta es la huella digital de tu cerebro. <br />
                Izquierda (Bajo peso) = Difuso/Creativo. Derecha (Alto peso) = Literal/Estricto."
            </div>
        </div>
    );
}
