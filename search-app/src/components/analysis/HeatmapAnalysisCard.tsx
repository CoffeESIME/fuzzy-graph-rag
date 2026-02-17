import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { ResponsiveHeatMap } from '@nivo/heatmap';
import { RefreshCw, Grid, Loader2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface HeatmapCell {
    x: string;
    y: number;
}

interface HeatmapRow {
    id: string; // The row label (Concept name)
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
    const [keys, setKeys] = useState<string[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const navigate = useNavigate();

    const fetchData = async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await axios.post<AnalysisResponse>('http://localhost:8000/analysis/heatmap');
            if (res.data.status === 'error') throw new Error(res.data.message);
            setData(res.data.mock_data.matrix);
            setKeys(res.data.mock_data.keys);
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
                line: { stroke: '#475569', strokeWidth: 1 }
            },
            ticks: {
                line: { stroke: '#475569', strokeWidth: 1 },
                text: { fill: '#94a3b8' }
            }
        },
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
            <p>Calculando matriz de adyacencia de conceptos...</p>
        </div>
    );

    return (
        <div style={{ padding: 24, paddingBottom: 60, maxWidth: 1000, margin: '0 auto' }}>
            <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-4">
                    <button onClick={() => navigate('/analysis')} className="btn-secondary">Back</button>
                    <div>
                        <h2 className="text-2xl font-bold flex items-center gap-2">
                            <Grid className="text-orange-500" />
                            Matriz de Calor
                        </h2>
                        <p className="text-gray-500">Densidad de conexiones entre los principales conceptos.</p>
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
                            No data available
                        </div>
                    ) : (
                        <ResponsiveHeatMap
                            data={data}
                            margin={{ top: 120, right: 90, bottom: 60, left: 120 }}
                            valueFormat=">-.2f"
                            axisTop={{
                                tickSize: 5,
                                tickPadding: 5,
                                tickRotation: -90,
                                legend: '',
                                legendOffset: 46
                            }}
                            axisRight={{
                                tickSize: 5,
                                tickPadding: 5,
                                tickRotation: 0,
                                legend: 'Top Concepts',
                                legendPosition: 'middle',
                                legendOffset: 70
                            }}
                            axisLeft={{
                                tickSize: 5,
                                tickPadding: 5,
                                tickRotation: 0,
                                legend: 'Top Concepts',
                                legendPosition: 'middle',
                                legendOffset: -72
                            }}
                            colors={{
                                type: 'sequential',
                                scheme: 'orange_red'
                            }}
                            emptyColor="#1e293b"
                            borderColor={{ from: 'color', modifiers: [['darker', 0.8]] }}
                            labelTextColor={{ from: 'color', modifiers: [['darker', 2]] }}
                            theme={theme}
                            hoverTarget="cell"
                            cellOpacity={1}
                            cellHoverOpacity={0.8}
                            cellHoverOthersOpacity={0.25}
                        />
                    )}
                </div>
            )}

            <div className="mt-6 text-center text-sm text-slate-500">
                "Esta matriz muestra la densidad de las conexiones. Las celdas oscuras indican conceptos que casi siempre aparecen juntos."
            </div>
        </div>
    );
}
