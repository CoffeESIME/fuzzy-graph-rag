import React, { useEffect, useState, useMemo } from 'react';
import axios from 'axios';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, CartesianGrid } from 'recharts';
import { CloudFog, Loader2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import * as Slider from '@radix-ui/react-slider';

interface DistributionBin {
    range: string;
    count: number;
    label: string;
}

interface AnalysisResponse {
    tool: string;
    status: string;
    message: string;
    mock_data: {
        distribution: DistributionBin[];
        total_edges: number;
    };
}

export default function FogOfWarCard() {
    const [data, setData] = useState<DistributionBin[]>([]);
    const [totalEdges, setTotalEdges] = useState(0);
    const [loading, setLoading] = useState(true);
    const [alpha, setAlpha] = useState(0.5);
    const [error, setError] = useState<string | null>(null);
    const navigate = useNavigate();

    const fetchData = async () => {
        setLoading(true);
        setError(null);
        try {
            console.log('Fetching fog distribution...');
            const res = await axios.post<AnalysisResponse>('http://localhost:8000/analysis/fog-distribution');
            console.log('Fog response:', res.data);
            if (res.data.status === 'error') throw new Error(res.data.message);

            if (res.data.mock_data.distribution.length === 0) {
                setError('No data found in graph (No edges with "weight" property?).');
            } else {
                setData(res.data.mock_data.distribution);
                setTotalEdges(res.data.mock_data.total_edges);
            }
        } catch (err: any) {
            console.error(err);
            setError(err.message || 'Error fetching distribution data');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
    }, []);

    const visiblePercentage = useMemo(() => {
        if (!data.length || totalEdges === 0) return 0;
        let visibleCount = 0;
        data.forEach((bin, i) => {
            const binLower = i / 10.0;
            // If bin lower bound is >= alpha, it is visible (assuming alpha cuts out weak links < alpha)
            // Typically alpha_cut means "keep links >= alpha".
            if (binLower >= alpha) {
                visibleCount += bin.count;
            }
            // Handling fractional overlap is complex for bins, simple logic: entire bin inclusion based on threshold
        });
        return Math.round((visibleCount / totalEdges) * 100);
    }, [data, totalEdges, alpha]);

    if (loading) return (
        <div className="flex flex-col items-center justify-center p-12 text-gray-500">
            <Loader2 className="animate-spin mb-4" size={32} />
            <p>Calculando distribución de la Niebla...</p>
        </div>
    );

    return (
        <div style={{ padding: 24, paddingBottom: 60, maxWidth: 1000, width: '100%', margin: '0 auto' }}>
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-4">
                    <button onClick={() => navigate('/analysis')} className="btn-secondary">Back</button>
                    <div>
                        <h2 className="text-2xl font-bold flex items-center gap-2">
                            <CloudFog className="text-slate-500" />
                            Niebla de Guerra
                        </h2>
                        <p className="text-gray-500">Visualiza cómo el umbral Alpha afecta la percepción de tu conocimiento.</p>
                    </div>
                </div>
                <button onClick={fetchData} className="px-4 py-2 bg-blue-50 text-blue-600 rounded hover:bg-blue-100 transition-colors">
                    Recargar
                </button>
            </div>

            {error && (
                <div className="p-4 mb-8 bg-red-50 text-red-600 border border-red-200 rounded flex items-center justify-between">
                    <span>{error}</span>
                    <button onClick={fetchData} className="underline text-sm">Reintentar</button>
                </div>
            )}

            {data.length > 0 && (
                <div className="bg-white dark:bg-slate-950 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800 p-8">

                    {/* KPI */}
                    <div className="mb-8 text-center">
                        <h3 className="text-4xl font-black text-slate-800 dark:text-white mb-2">
                            {visiblePercentage}% <span className="text-lg font-normal text-slate-500">de realidad visible</span>
                        </h3>
                        <p className="text-slate-500">
                            Con Alpha <strong>{alpha.toFixed(2)}</strong>, ignoras el {100 - visiblePercentage}% de las conexiones (ruido/latentes).
                        </p>
                    </div>

                    {/* Chart */}
                    <div className="h-[300px] w-full mb-8">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 50 }}>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                                <XAxis
                                    dataKey="range"
                                    label={{ value: 'Rango de Peso (Fuerza)', position: 'insideBottom', offset: -20 }}
                                    tick={{ fontSize: 10 }}
                                    interval={0}
                                />
                                <YAxis />
                                <Tooltip
                                    cursor={{ fill: 'transparent' }}
                                    content={({ active, payload }) => {
                                        if (active && payload && payload.length) {
                                            const d = payload[0].payload as DistributionBin;
                                            return (
                                                <div className="bg-slate-800 text-white p-2 rounded text-xs shadow-xl">
                                                    <p className="font-bold">{d.label}</p>
                                                    <p>Rango: {d.range}</p>
                                                    <p>Conexiones: {d.count}</p>
                                                </div>
                                            );
                                        }
                                        return null;
                                    }}
                                />
                                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                                    {data.map((entry, index) => {
                                        // Determine if bar is "active" based on alpha
                                        // Bin index 0 is 0.0-0.1. If alpha is 0.5, bins 0,1,2,3,4 are "fogged" (hidden/gray)
                                        // We are keeping edges >= alpha. So edges < alpha are fogged.
                                        // The bin starts at index / 10.
                                        const binStart = index / 10;
                                        const isActive = binStart >= alpha;
                                        return (
                                            <Cell
                                                key={`cell-${index}`}
                                                fill={isActive ? '#6366f1' : '#e2e8f0'}
                                                className="transition-all duration-300"
                                            />
                                        );
                                    })}
                                </Bar>
                            </BarChart>
                        </ResponsiveContainer>
                    </div>

                    {/* Slider Control */}
                    <div className="px-12">
                        <div className="flex justify-between text-xs text-slate-400 mb-2 font-mono uppercase tracking-widest">
                            <span>Caos (0.0)</span>
                            <span>Equilibrio</span>
                            <span>Certeza (1.0)</span>
                        </div>
                        <Slider.Root
                            className="relative flex items-center select-none touch-none w-full h-5"
                            value={[alpha]}
                            max={0.9}
                            min={0.0}
                            step={0.1}
                            onValueChange={(val) => setAlpha(val[0])}
                        >
                            <Slider.Track className="bg-slate-200 dark:bg-slate-800 relative grow rounded-full h-[3px]">
                                <Slider.Range className="absolute bg-indigo-500 rounded-full h-full" />
                            </Slider.Track>
                            <Slider.Thumb
                                className="block w-5 h-5 bg-white border-2 border-indigo-500 shadow-md rounded-full hover:bg-violet-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-opacity-50 transition-transform hover:scale-110"
                                aria-label="Alpha Cut"
                            />
                        </Slider.Root>

                        <div className="mt-8 text-center bg-blue-50 dark:bg-blue-900/10 p-4 rounded-lg text-blue-800 dark:text-blue-200 text-sm">
                            "La 'Niebla de Guerra' te muestra cuánta información pierdes al ser estricto. Un Alpha bajo te da contexto, un Alpha alto te da certeza."
                        </div>
                    </div>

                </div>
            )}
        </div>
    );
}
