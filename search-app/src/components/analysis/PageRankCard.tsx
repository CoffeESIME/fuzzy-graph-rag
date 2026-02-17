import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { ResponsiveBar } from '@nivo/bar';
import { RefreshCw, Crown, Loader2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface RankItem {
    id: string; // Name
    value: number; // Score
    category: string;
}

interface AnalysisResponse {
    tool: string;
    status: string;
    message: string;
    mock_data: {
        ranking: RankItem[];
    };
}

export default function PageRankCard() {
    const [data, setData] = useState<RankItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const navigate = useNavigate();

    const fetchData = async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await axios.post<AnalysisResponse>('http://localhost:8000/analysis/pagerank');
            if (res.data.status === 'error') throw new Error(res.data.message);
            // Reverse data for horizontal bar chart (top items at top)
            // Nivo bottom-to-top by default on horizontal? 
            // Actually usually index 0 is at bottom.
            // Let's reverse them so highest score is at top.
            setData([...res.data.mock_data.ranking].reverse());
        } catch (err: any) {
            console.error(err);
            setError(err.message || 'Error fetching PageRank data');
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
            <p>Calculando influencia central (PageRank)...</p>
        </div>
    );

    return (
        <div style={{ padding: 24, paddingBottom: 60, maxWidth: 1000, margin: '0 auto' }}>
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
                            No significant ranking data found.
                        </div>
                    ) : (
                        <ResponsiveBar
                            data={data}
                            keys={['value']}
                            indexBy="id"
                            layout="horizontal"
                            margin={{ top: 10, right: 30, bottom: 50, left: 150 }} // Left margin for labels
                            padding={0.3}
                            valueScale={{ type: 'linear' }}
                            indexScale={{ type: 'band', round: true }}
                            colors={{ scheme: 'purple_orange' }} // Gradient-ish
                            colorBy="indexValue" // Different color per bar
                            borderColor={{ from: 'color', modifiers: [['darker', 1.6]] }}
                            axisTop={null}
                            axisRight={null}
                            axisBottom={{
                                tickSize: 5,
                                tickPadding: 5,
                                tickRotation: 0,
                                legend: 'PageRank Score',
                                legendPosition: 'middle',
                                legendOffset: 32
                            }}
                            axisLeft={{
                                tickSize: 5,
                                tickPadding: 5,
                                tickRotation: 0,
                                legend: '',
                                legendOffset: -40
                            }}
                            labelSkipWidth={12}
                            labelSkipHeight={12}
                            labelTextColor={{ from: 'color', modifiers: [['darker', 1.6]] }}
                            theme={theme}
                            role="application"
                            ariaLabel="Nivo bar chart demo"
                            tooltip={({ id, value, color, indexValue, data }) => (
                                <div style={{ padding: 12, color, background: '#222', borderRadius: '4px' }}>
                                    <strong>{indexValue}</strong> ({(data as any).category})
                                    <br />
                                    Score: {value}
                                </div>
                            )}
                        />
                    )}
                </div>
            )}

            <div className="mt-6 text-center text-sm text-slate-500">
                "Estos son los 'Influencers' de tu base de conocimiento. El algoritmo PageRank determina la centralidad de cada concepto."
            </div>
        </div>
    );
}
