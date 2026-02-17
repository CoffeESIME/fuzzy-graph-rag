import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { Dna, Loader2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface Community {
    id: number;
    members: string[];
    size: number;
}

interface AnalysisResponse {
    tool: string;
    status: string;
    message: string;
    mock_data: {
        clusters: number;
        nodes: Community[];
    };
}

export default function CommunityAnalysisCard() {
    const [data, setData] = useState<Community[] | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const navigate = useNavigate();

    useEffect(() => {
        const fetchData = async () => {
            try {
                // Using axios directly for simplicity, or use React Query
                const res = await axios.post<AnalysisResponse>('http://localhost:8000/analysis/communities');
                if (res.data.status === 'error') {
                    throw new Error(res.data.message);
                }
                setData(res.data.mock_data.nodes);
            } catch (err: any) {
                setError(err.message || 'Error fetching analysis data');
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, []);

    const COLORS = ['#8884d8', '#82ca9d', '#ffc658', '#ff8042', '#8dd1e1', '#a4de6c'];

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center p-12 text-gray-500">
                <Loader2 className="animate-spin mb-4" size={32} />
                <p>Ejecutando algoritmo Louvain...</p>
                <div className="text-xs text-gray-400 mt-2">Projection graph in GDS Memory</div>
            </div>
        );
    }

    if (error) {
        return <div className="p-8 text-red-500">Error: {error}</div>
    }

    return (
        <div style={{ padding: 24, paddingBottom: 60 }}>
            {/* Header */}
            <div style={{ marginBottom: 24, display: 'flex', alignItems: 'center', gap: 16 }}>
                <button onClick={() => navigate('/analysis')} className="btn-secondary">Back</button>
                <div>
                    <h2 style={{ fontSize: '1.5rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 10 }}>
                        <Dna size={28} className="text-purple-500" />
                        Detección de Comunidades
                    </h2>
                    <p style={{ color: 'var(--text-secondary)' }}>
                        Algoritmo de Louvain aplicado a la estructura del grafo.
                    </p>
                </div>
            </div>

            {/* Narrative */}
            <div className="bg-slate-50 dark:bg-slate-900/50 p-6 rounded-xl border border-slate-200 dark:border-slate-800 mb-8">
                <p className="text-lg text-slate-700 dark:text-slate-300">
                    El algoritmo de Louvain ha detectado <strong>{data?.length}</strong> comunidades principales en tu cerebro digital.
                    Esto indica que tu información se agrupa naturalmente en estos temas.
                </p>
            </div>

            {/* Chart */}
            <div style={{ height: 400, width: '100%', marginBottom: 40 }}>
                <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={data || []} margin={{ top: 20, right: 30, left: 20, bottom: 50 }}>
                        <XAxis
                            dataKey="id"
                            label={{ value: 'ID Comunidad', position: 'insideBottom', offset: -10 }}
                        />
                        <YAxis label={{ value: 'Nodos', angle: -90, position: 'insideLeft' }} />
                        <Tooltip
                            content={({ active, payload }) => {
                                if (active && payload && payload.length) {
                                    const d = payload[0].payload;
                                    return (
                                        <div className="bg-white dark:bg-slate-800 p-4 rounded shadow-lg border border-slate-200 dark:border-slate-700">
                                            <p className="font-bold mb-2">Comunidad {d.id}</p>
                                            <p className="text-sm">Tamaño: {d.size} nodos</p>
                                            <div className="mt-2 text-xs text-slate-500">
                                                <strong>Top Miembros:</strong><br />
                                                {d.members.join(', ')}
                                            </div>
                                        </div>
                                    );
                                }
                                return null;
                            }}
                        />
                        <Bar dataKey="size" radius={[4, 4, 0, 0]}>
                            {data?.map((entry, index) => (
                                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                            ))}
                        </Bar>
                    </BarChart>
                </ResponsiveContainer>
            </div>

            {/* Detail Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {data?.map((community, i) => (
                    <div key={community.id} className="p-4 border rounded-lg bg-white dark:bg-slate-950 dark:border-slate-800">
                        <div className="flex justify-between items-center mb-2">
                            <span className="font-mono text-xs text-slate-400">ID: {community.id}</span>
                            <span className="bg-purple-100 text-purple-700 text-xs px-2 py-1 rounded-full font-bold">{community.size} nodos</span>
                        </div>
                        <div className="text-sm font-medium text-slate-600 dark:text-slate-300">
                            {community.members.slice(0, 3).join(', ')}...
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
