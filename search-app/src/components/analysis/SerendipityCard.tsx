import React, { useState } from 'react';
import axios from 'axios';
import { Route, Shuffle, Sparkles, ArrowRight } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface PathStep {
    node: string;
    edge: string;
    next: string;
    weight: number;
}

interface AnalysisResponse {
    tool: string;
    status: string;
    message: string;
    mock_data: {
        path: PathStep[];
        total_serendipity_score: number;
        source: string;
        target: string;
    };
}

export default function SerendipityCard() {
    const [pathData, setPathData] = useState<AnalysisResponse['mock_data'] | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const navigate = useNavigate();

    const fetchSerendipity = async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await axios.post<AnalysisResponse>('http://localhost:8000/analysis/serendipity');
            if (res.data.status === 'error') throw new Error(res.data.message);
            setPathData(res.data.mock_data);
        } catch (err: any) {
            setError(err.message || 'Error fetching serendipity path');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div style={{ padding: 24, paddingBottom: 60, maxWidth: 900, margin: '0 auto' }}>
            {/* Header */}
            <div className="flex items-center gap-4 mb-6">
                <button onClick={() => navigate('/analysis')} className="btn-secondary">Back</button>
                <div>
                    <h2 className="text-2xl font-bold flex items-center gap-2">
                        <Sparkles className="text-yellow-500" />
                        Camino de Serendipia
                    </h2>
                    <p className="text-gray-500">Descubre conexiones inesperadas a través de enlaces débiles.</p>
                </div>
            </div>

            {/* Main Action */}
            <div className="flex justify-center my-8">
                <button
                    onClick={fetchSerendipity}
                    disabled={loading}
                    className="flex items-center gap-3 bg-gradient-to-r from-violet-600 to-indigo-600 text-white px-8 py-4 rounded-full text-lg font-bold shadow-lg hover:shadow-xl hover:scale-105 transition-all disabled:opacity-50"
                >
                    {loading ? <Shuffle className="animate-spin" /> : <Route />}
                    {loading ? 'Explorando...' : '🎲 Tirar los Dados'}
                </button>
            </div>

            {error && <div className="text-red-500 text-center mb-4">{error}</div>}

            {/* Path Visualization */}
            {pathData && (
                <div className="animate-in fade-in slide-in-from-bottom-4 duration-700">
                    <div className="bg-slate-50 dark:bg-slate-900/50 p-6 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm relative overflow-hidden">
                        <div className="absolute top-0 right-0 p-4 opacity-10">
                            <Sparkles size={120} />
                        </div>

                        <div className="text-center mb-8">
                            <h3 className="text-xl text-slate-700 dark:text-slate-300">
                                Conectando <strong className="text-indigo-600">{pathData.source}</strong> con <strong className="text-pink-600">{pathData.target}</strong>
                            </h3>
                            <p className="text-sm text-slate-500 mt-2">
                                Puntuación de Serendipia: {pathData.total_serendipity_score.toFixed(3)} (menor es más sorprendente)
                            </p>
                        </div>

                        {/* Subway Line Viz */}
                        <div className="relative flex flex-col md:flex-row items-center justify-center gap-2 md:gap-0 max-w-4xl mx-auto">
                            {/* Start Node */}
                            <div className="flex flex-col items-center z-10">
                                <div className="w-12 h-12 rounded-full bg-indigo-100 text-indigo-700 flex items-center justify-center font-bold border-4 border-white shadow-md">
                                    A
                                </div>
                                <span className="mt-2 font-medium text-sm">{pathData.source}</span>
                            </div>

                            {/* Steps */}
                            {pathData.path.map((step, i) => (
                                <React.Fragment key={i}>
                                    {/* Connection Line & Label */}
                                    <div className="flex-1 flex flex-col items-center px-2 min-w-[100px] relative group">
                                        <div className="h-1 w-full bg-slate-200 rounded-full my-6 overflow-hidden">
                                            <div
                                                className="h-full bg-slate-400/50"
                                                style={{ width: '100%' }}
                                            />
                                        </div>
                                        <span className="absolute top-0 text-[10px] text-slate-400 bg-white px-2 py-0.5 rounded-full border border-slate-100 shadow-sm -mt-3">
                                            {step.edge}
                                        </span>
                                        <ArrowRight className="absolute text-slate-300 top-[22px]" size={16} />
                                    </div>

                                    {/* Intermediate Node */}
                                    <div className="flex flex-col items-center z-10 animation-delay-200">
                                        <div className="w-8 h-8 rounded-full bg-white border-2 border-slate-300 flex items-center justify-center text-[10px] text-slate-500 shadow-sm">
                                            {i + 1}
                                        </div>
                                        <span className="mt-2 text-xs font-medium text-slate-600 max-w-[80px] text-center truncate" title={step.next}>
                                            {step.next}
                                        </span>
                                    </div>
                                </React.Fragment>
                            ))}
                        </div>

                        <div className="mt-8 p-4 bg-yellow-50 dark:bg-yellow-900/10 text-yellow-800 dark:text-yellow-200 text-sm rounded-lg text-center border border-yellow-100 dark:border-yellow-800/30">
                            "Este camino conecta conceptos a través de asociaciones sutiles que normalmente ignorarías."
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
