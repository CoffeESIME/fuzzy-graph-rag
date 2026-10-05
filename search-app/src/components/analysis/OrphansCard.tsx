import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { RefreshCw, Unplug, Loader2, FileWarning, AlertTriangle } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface OrphanNode {
    filename: string;
    uuid: string;
}

interface AnalysisResponse {
    tool: string;
    status: string;
    message: string;
    mock_data: {
        count: number;
        nodes: OrphanNode[];
    };
}

export default function OrphansCard() {
    const [nodes, setNodes] = useState<OrphanNode[]>([]);
    const [count, setCount] = useState(0);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const navigate = useNavigate();

    const fetchData = async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await axios.post<AnalysisResponse>('http://localhost:8000/analysis/orphans');
            if (res.data.status === 'error') throw new Error(res.data.message);
            setNodes(res.data.mock_data.nodes);
            setCount(res.data.mock_data.count);
        } catch (err: any) {
            console.error(err);
            setError(err.message || 'Error auditing orphans');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
    }, []);

    if (loading) return (
        <div className="flex flex-col items-center justify-center p-12 text-gray-500 min-h-[400px]">
            <Loader2 className="animate-spin mb-4" size={32} />
            <p>Auditando archivos desconectados...</p>
        </div>
    );

    return (
        <div style={{ padding: 24, paddingBottom: 60, maxWidth: 1000, width: '100%', margin: '0 auto' }}>
            <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-4">
                    <button onClick={() => navigate('/analysis')} className="btn-secondary">Back</button>
                    <div>
                        <h2 className="text-2xl font-bold flex items-center gap-2">
                            <Unplug className="text-gray-500" />
                            Nodos Huérfanos ({count})
                        </h2>
                        <p className="text-gray-500">Archivos (DigitalAssets) que no generaron ninguna conexión en el grafo.</p>
                    </div>
                </div>
                <button onClick={fetchData} className="btn-icon">
                    <RefreshCw size={18} />
                </button>
            </div>

            {error ? (
                <div className="p-8 text-red-500 border border-red-200 rounded">{error}</div>
            ) : (
                <div className="min-h-[400px]">
                    {nodes.length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-64 bg-green-50 dark:bg-green-900/10 rounded-xl border border-green-100 dark:border-green-900/30 text-green-700 dark:text-green-300">
                            <span className="text-4xl mb-4"></span>
                            <p className="font-semibold">¡Todo limpio!</p>
                            <p className="text-sm opacity-80">No hay nodos huérfanos. Todos los archivos están conectados.</p>
                        </div>
                    ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                            {nodes.map((node) => (
                                <div key={node.uuid} className="bg-red-50 dark:bg-red-900/10 border border-red-200 dark:border-red-900/30 p-4 rounded-lg flex items-start gap-3 shadow-sm hover:shadow-md transition-shadow">
                                    <div className="bg-red-100 dark:bg-red-800/30 p-2 rounded text-red-600 dark:text-red-400">
                                        <FileWarning size={20} />
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <h4 className="font-medium text-red-900 dark:text-red-200 truncate" title={node.filename}>
                                            {node.filename}
                                        </h4>
                                        <p className="text-xs text-red-700 dark:text-red-300/70 truncate mb-2">
                                            ID: {node.uuid.substring(0, 8)}...
                                        </p>
                                        <button className="text-xs bg-white dark:bg-slate-800 border border-red-200 dark:border-red-800 text-red-600 dark:text-red-300 px-3 py-1 rounded hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors w-full">
                                            Re-indexar (Mock)
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            <div className="mt-8 flex items-start gap-3 bg-amber-50 dark:bg-amber-900/10 p-4 rounded-lg text-amber-800 dark:text-amber-200 text-sm border border-amber-100 dark:border-amber-800/30">
                <AlertTriangle className="shrink-0 mt-0.5" size={16} />
                <p>
                    "Estos archivos están aislados. La IA no encontró nada relevante en ellos o falló el proceso de extracción. Revisa si el contenido es legible."
                </p>
            </div>
        </div>
    );
}
