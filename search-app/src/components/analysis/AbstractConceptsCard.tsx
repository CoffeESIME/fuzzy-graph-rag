import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { ResponsiveScatterPlot } from '@nivo/scatterplot';
import { RefreshCw, Shapes, Loader2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface ScatterPoint {
    x: number;
    y: number;
}

interface ScatterSeries {
    id: string; // Concept name
    data: ScatterPoint[];
}

interface AnalysisResponse {
    tool: string;
    status: string;
    message: string;
    mock_data: {
        abstract_nodes: ScatterSeries[];
    };
}

export default function AbstractConceptsCard() {
    const [data, setData] = useState<ScatterSeries[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const navigate = useNavigate();

    const fetchData = async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await axios.post<AnalysisResponse>('http://localhost:8000/analysis/abstract-concepts');
            if (res.data.status === 'error') throw new Error(res.data.message);
            setData(res.data.mock_data.abstract_nodes);
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

    const theme = {
        background: 'transparent',
        textColor: '#94a3b8',
        fontSize: 11,
        axis: {
            domain: { line: { stroke: '#475569', strokeWidth: 1 } },
            ticks: { line: { stroke: '#475569', strokeWidth: 1 }, text: { fill: '#94a3b8' } }
        },
        grid: { line: { stroke: '#334155', strokeWidth: 1 } },
        tooltip: {
            container: {
                background: '#1e293b',
                color: '#f8fafc',
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
            <p>Buscando conceptos abstractos (pegamento difuso)...</p>
        </div>
    );

    return (
        <div style={{ padding: 24, paddingBottom: 60, maxWidth: 1000, margin: '0 auto' }}>
            <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-4">
                    <button onClick={() => navigate('/analysis')} className="btn-secondary">Back</button>
                    <div>
                        <h2 className="text-2xl font-bold flex items-center gap-2">
                            <Shapes className="text-purple-500" />
                            Conceptos Abstractos
                        </h2>
                        <p className="text-gray-500">Nodos con alta conectividad pero bajo peso promedio.</p>
                    </div>
                </div>
                <button onClick={fetchData} className="btn-icon">
                    <RefreshCw size={18} />
                </button>
            </div>

            {error ? (
                <div className="p-8 text-red-500 border border-red-200 rounded">{error}</div>
            ) : (
                <div className="bg-white dark:bg-slate-950 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800 p-4 h-[600px] w-full relative">
                    {data.length === 0 ? (
                        <div className="absolute inset-0 flex items-center justify-center text-slate-400">
                            No se encontraron conceptos abstractos con los criterios actuales.
                        </div>
                    ) : (
                        <ResponsiveScatterPlot
                            data={data}
                            margin={{ top: 60, right: 140, bottom: 70, left: 90 }}
                            xScale={{ type: 'linear', min: 'auto', max: 'auto' }}
                            yScale={{ type: 'linear', min: 0, max: 1 }}
                            blendMode="normal" // multiply for heavy overlap
                            colors={{ scheme: 'category10' }}
                            axisTop={null}
                            axisRight={null}
                            axisBottom={{
                                tickSize: 5,
                                tickPadding: 5,
                                tickRotation: 0,
                                legend: 'Grado (Cantidad de Conexiones)',
                                legendPosition: 'middle',
                                legendOffset: 46
                            }}
                            axisLeft={{
                                tickSize: 5,
                                tickPadding: 5,
                                tickRotation: 0,
                                legend: 'Peso Promedio',
                                legendPosition: 'middle',
                                legendOffset: -60
                            }}
                            theme={theme}
                            tooltip={({ node }) => (
                                <div style={{ padding: 12, background: '#222', color: '#fff', borderRadius: '4px' }}>
                                    <strong>{node.serieId}</strong>
                                    <br />
                                    Grado: {node.data.x}
                                    <br />
                                    Peso: {node.data.y}
                                </div>
                            )}
                        />
                    )}
                </div>
            )}

            <div className="mt-6 text-center text-sm text-slate-500">
                "Estos conceptos conectan muchas cosas, pero de forma sutil. Son la 'poesía' o el 'ruido' de tu sistema."
            </div>
        </div>
    );
}
