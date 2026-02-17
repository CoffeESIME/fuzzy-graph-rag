import React, { useEffect, useState } from 'react';
import axios from 'axios';
import ReactFlow, { Background, Controls } from 'reactflow';
import type { Node, Edge } from 'reactflow';
import 'reactflow/dist/style.css';
import { Network, Loader2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface BridgeNode {
    name: string;
    type: string;
    score: number;
}

interface AnalysisResponse {
    tool: string;
    status: string;
    message: string;
    mock_data: {
        bridges: BridgeNode[];
        impact_score: number;
    };
}

export default function BridgeAnalysisCard() {
    const [bridges, setBridges] = useState<BridgeNode[]>([]);
    const [loading, setLoading] = useState(true);
    const [nodes, setNodes] = useState<Node[]>([]);
    const [edges, setEdges] = useState<Edge[]>([]);
    const navigate = useNavigate();

    useEffect(() => {
        const fetchData = async () => {
            try {
                const res = await axios.post<AnalysisResponse>('http://localhost:8000/analysis/bridges');
                if (res.data.status === 'error') {
                    throw new Error(res.data.message);
                }
                const data = res.data.mock_data.bridges;
                setBridges(data);

                // Create visualization for top bridge
                if (data.length > 0) {
                    const center = data[0];
                    const initialNodes: Node[] = [
                        {
                            id: 'center',
                            position: { x: 250, y: 150 },
                            data: { label: center.name },
                            style: { background: '#ef4444', color: 'white', borderRadius: '50%', width: 60, height: 60, display: 'flex', alignItems: 'center', justifyContent: 'center', border: 'none' }
                        }
                    ];
                    const initialEdges: Edge[] = [];

                    // Create satellite nodes to symbolize connections
                    [1, 2, 3, 4, 5].forEach((i) => {
                        const angle = (i * 72) * (Math.PI / 180);
                        const x = 250 + 120 * Math.cos(angle);
                        const y = 150 + 120 * Math.sin(angle);
                        initialNodes.push({
                            id: `sat-${i}`,
                            position: { x, y },
                            data: { label: 'Cluster ' + i },
                            style: { background: '#e2e8f0', color: '#64748b', fontSize: 10, borderRadius: 4, width: 60, textAlign: 'center' }
                        });
                        initialEdges.push({
                            id: `e-${i}`,
                            source: 'center',
                            target: `sat-${i}`,
                            style: { stroke: '#94a3b8', strokeDasharray: '5,5' }
                        });
                    });

                    setNodes(initialNodes);
                    setEdges(initialEdges);
                }

            } catch (err) {
                console.error(err);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, []);

    if (loading) return (
        <div className="flex flex-col items-center justify-center p-12 text-gray-500">
            <Loader2 className="animate-spin mb-4" size={32} />
            <p>Calculando Centralidad de Intermediación...</p>
        </div>
    );

    const topBridge = bridges[0];

    return (
        <div style={{ padding: 24, paddingBottom: 60 }}>
            {/* Header */}
            <div style={{ marginBottom: 24, display: 'flex', alignItems: 'center', gap: 16 }}>
                <button onClick={() => navigate('/analysis')} className="btn-secondary">Back</button>
                <div>
                    <h2 style={{ fontSize: '1.5rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 10 }}>
                        <Network size={28} className="text-red-500" />
                        Puentes Semánticos
                    </h2>
                    <p style={{ color: 'var(--text-secondary)' }}>
                        Nodos con mayor Betweenness Centrality.
                    </p>
                </div>
            </div>

            <div className="flex gap-8 flex-col lg:flex-row">
                {/* Ranking List */}
                <div className="flex-1">
                    <div className="bg-slate-50 dark:bg-slate-900/50 p-6 rounded-xl border border-slate-200 dark:border-slate-800 mb-6">
                        <p className="text-lg text-slate-700 dark:text-slate-300">
                            Estos conceptos actúan como carreteras principales.
                            Si eliminas <strong>{topBridge?.name}</strong>, tu grafo podría fragmentarse.
                        </p>
                    </div>

                    <h3 className="font-bold mb-4 text-gray-600 uppercase text-xs tracking-wider">Top Conceptos Puente</h3>
                    <div className="space-y-3">
                        {bridges.map((b, i) => (
                            <div key={i} className="flex items-center justify-between p-3 bg-white dark:bg-slate-950 border rounded-lg hover:border-red-300 transition-colors">
                                <div className="flex items-center gap-3">
                                    <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${i === 0 ? 'bg-red-100 text-red-600' : 'bg-gray-100 text-gray-500'}`}>
                                        {i + 1}
                                    </div>
                                    <span className="font-medium">{b.name}</span>
                                </div>
                                <div className="text-right">
                                    <div className="text-sm font-mono font-bold text-slate-700">{b.score.toFixed(2)}</div>
                                    <div className="text-[10px] text-slate-400">{b.type}</div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Visual Graph */}
                <div className="flex-1 h-[500px] border rounded-xl overflow-hidden bg-slate-50 relative">
                    <div className="absolute top-4 left-4 z-10 bg-white/90 p-2 rounded text-xs font-mono shadow-sm">
                        Visualization: Bridge Node Impact
                    </div>
                    <ReactFlow
                        nodes={nodes}
                        edges={edges}
                        fitView
                    >
                        <Background />
                        <Controls />
                    </ReactFlow>
                </div>
            </div>
        </div>
    );
}
