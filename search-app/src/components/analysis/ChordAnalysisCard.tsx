import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { ResponsiveChord } from '@nivo/chord';
import { RefreshCw, Component, Loader2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface AnalysisResponse {
    tool: string;
    status: string;
    message: string;
    mock_data: {
        matrix: number[][]; // NxN matrix
        keys: string[]; // Labels
    };
}

export default function ChordAnalysisCard() {
    const [matrix, setMatrix] = useState<number[][]>([]);
    const [keys, setKeys] = useState<string[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const navigate = useNavigate();

    const fetchData = async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await axios.post<AnalysisResponse>('http://localhost:8000/analysis/chord');
            if (res.data.status === 'error') throw new Error(res.data.message);
            setMatrix(res.data.mock_data.matrix);
            setKeys(res.data.mock_data.keys);
        } catch (err: any) {
            console.error(err);
            setError(err.message || 'Error fetching chord data');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
    }, []);

    const theme = {
        background: 'transparent',
        textColor: '#e2e8f0', // Light text for dark mode compatibility mainly, or conditional
        fontSize: 12,
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
            <p>Calculando flujos entre categorías...</p>
        </div>
    );

    return (
        <div style={{ padding: 24, paddingBottom: 60, maxWidth: 1000, margin: '0 auto' }}>
            <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-4">
                    <button onClick={() => navigate('/analysis')} className="btn-secondary">Back</button>
                    <div>
                        <h2 className="text-2xl font-bold flex items-center gap-2">
                            <Component className="text-teal-500" />
                            Diagrama de Cuerdas
                        </h2>
                        <p className="text-gray-500">Flujo de información entre categorías del conocimiento.</p>
                    </div>
                </div>
                <button onClick={fetchData} className="btn-icon">
                    <RefreshCw size={18} />
                </button>
            </div>

            {error ? (
                <div className="p-8 text-red-500 border border-red-200 rounded">{error}</div>
            ) : (
                <div className="bg-white dark:bg-slate-950 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800 p-4 h-[700px] w-full relative ">
                    {matrix.length === 0 ? (
                        <div className="absolute inset-0 flex items-center justify-center text-slate-400">
                            No data available
                        </div>
                    ) : (
                        <ResponsiveChord
                            data={matrix}
                            keys={keys}
                            margin={{ top: 60, right: 60, bottom: 90, left: 60 }}
                            valueFormat=".2f"
                            padAngle={0.02}
                            innerRadiusRatio={0.96}
                            innerRadiusOffset={0.02}
                            inactiveArcOpacity={0.25}
                            arcOpacity={1}
                            activeArcOpacity={1}
                            inactiveRibbonOpacity={0.25}
                            ribbonOpacity={0.5}
                            activeRibbonOpacity={0.75}
                            labelRotation={-90}
                            labelOffset={12}
                            labelTextColor={{
                                from: 'color',
                                modifiers: [
                                    [
                                        'darker',
                                        1
                                    ]
                                ]
                            }}
                            colors={{ scheme: 'nivo' }}
                            motionConfig="stiff"
                            theme={theme}
                            arcTooltip={({ arc }) => (
                                <div className="bg-slate-800 text-white p-2 rounded text-xs shadow-xl">
                                    <strong>{arc.label}</strong>: {arc.value} conexiones
                                </div>
                            )}
                            ribbonTooltip={({ ribbon }) => (
                                <div className="bg-slate-800 text-white p-2 rounded text-xs shadow-xl">
                                    {ribbon.source.label} ↔ {ribbon.target.label}: {ribbon.source.value}
                                </div>
                            )}
                        />
                    )}
                </div>
            )}

            <div className="mt-8 text-center bg-teal-50 dark:bg-teal-900/10 p-4 rounded-lg text-teal-800 dark:text-teal-200 text-sm border border-teal-100 dark:border-teal-800/30">
                "Este diagrama visualiza cómo los 'Conceptos' actúan como el pegamento central entre 'Personas' y 'Lugares', revelando la estructura de tu grafo."
            </div>
        </div>
    );
}
