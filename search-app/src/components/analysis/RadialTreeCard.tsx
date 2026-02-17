
import React, { useEffect, useState, useCallback, useMemo } from 'react';
import axios from 'axios';
import ReactFlow, {
    Controls,
    Background,
    useNodesState,
    useEdgesState,
    MarkerType
} from 'reactflow';
import type { Node, Edge } from 'reactflow';
import 'reactflow/dist/style.css';
import { RefreshCw, GitCommit, Loader2, Network } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface GraphNode {
    id: string;
    level: number;
}

interface GraphEdge {
    source: string;
    target: string;
}

interface AnalysisResponse {
    tool: string;
    status: string;
    message: string;
    mock_data: {
        root: string;
        nodes: GraphNode[];
        edges: GraphEdge[];
    };
}

export default function RadialTreeCard() {
    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);
    const [loading, setLoading] = useState(true);
    const [rootNode, setRootNode] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const navigate = useNavigate();

    const fetchTree = useCallback(async (rootName?: string | null) => {
        setLoading(true);
        setError(null);
        try {
            const payload = rootName ? { root_node_name: rootName } : {};
            const res = await axios.post<AnalysisResponse>('http://localhost:8000/analysis/radial-tree', payload);

            if (res.data.status === 'error') throw new Error(res.data.message);

            const rawNodes = res.data.mock_data.nodes;
            const rawEdges = res.data.mock_data.edges;
            const root = res.data.mock_data.root;
            setRootNode(root);

            // Compute Radial Layout
            // Level 0: (0,0)
            // Level 1: radius 250
            // Level 2: radius 500

            const levelNodes = {
                0: rawNodes.filter(n => n.level === 0),
                1: rawNodes.filter(n => n.level === 1),
                2: rawNodes.filter(n => n.level === 2),
            };

            const computedNodes: Node[] = [];

            // Place Root
            if (levelNodes[0].length > 0) {
                computedNodes.push({
                    id: levelNodes[0][0].id,
                    data: { label: levelNodes[0][0].id },
                    position: { x: 0, y: 0 },
                    type: 'input', // ReactFlow type
                    style: { backgroundColor: '#6366f1', color: 'white', border: 'none', width: 60, height: 60, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: '50%', fontWeight: 'bold' }
                });
            }

            // Place Layer 1
            const layer1 = levelNodes[1];
            const radius1 = 250;
            layer1.forEach((node, i) => {
                const angle = (2 * Math.PI * i) / layer1.length;
                computedNodes.push({
                    id: node.id,
                    data: { label: node.id },
                    position: {
                        x: radius1 * Math.cos(angle),
                        y: radius1 * Math.sin(angle)
                    },
                    style: { backgroundColor: '#a5b4fc', width: 50, height: 50, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px' }
                });
            });

            // Place Layer 2
            const layer2 = levelNodes[2];
            const radius2 = 500;
            layer2.forEach((node, i) => {
                const angle = (2 * Math.PI * i) / layer2.length;
                // Add some offset so it doesn't align perfectly if counts match
                const offsetAngle = angle + (Math.PI / 8);
                computedNodes.push({
                    id: node.id,
                    data: { label: node.id },
                    position: {
                        x: radius2 * Math.cos(offsetAngle),
                        y: radius2 * Math.sin(offsetAngle)
                    },
                    style: { backgroundColor: '#e0e7ff', width: 40, height: 40, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '9px', opacity: 0.8 }
                });
            });

            setNodes(computedNodes);

            const computedEdges: Edge[] = rawEdges.map((e, i) => ({
                id: `e - ${i} `,
                source: e.source,
                target: e.target,
                type: 'straight',
                style: { stroke: '#cbd5e1', strokeWidth: 1 }
            }));
            setEdges(computedEdges);

        } catch (err: any) {
            console.error(err);
            setError(err.message || 'Error fetching tree data');
        } finally {
            setLoading(false);
        }
    }, [setNodes, setEdges]);

    useEffect(() => {
        fetchTree(null); // Initial load
    }, [fetchTree]);

    const handleNodeClick = (event: React.MouseEvent, node: Node) => {
        // Drill down: make clicked node the new root
        fetchTree(node.id);
    };

    return (
        <div style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
            <div className="p-4 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between z-10">
                <div className="flex items-center gap-4">
                    <button onClick={() => navigate('/analysis')} className="btn-secondary">Back</button>
                    <div>
                        <h2 className="text-xl font-bold flex items-center gap-2 text-slate-800 dark:text-white">
                            <Network className="text-cyan-500" />
                            Árbol Radial: {rootNode || '...'}
                        </h2>
                        <p className="text-xs text-slate-500">Exploración concéntrica (Root → Vecinos → Vecinos 2)</p>
                    </div>
                </div>
                <div className="flex gap-2">
                    <button onClick={() => fetchTree(null)} className="btn-secondary text-xs">Reset Root</button>
                    <button onClick={() => fetchTree(rootNode)} className="btn-icon">
                        <RefreshCw size={18} />
                    </button>
                </div>
            </div>

            <div className="flex-1 relative bg-slate-50 dark:bg-slate-950">
                {loading && (
                    <div className="absolute inset-0 flex items-center justify-center z-50 bg-white/50 dark:bg-black/50 backdrop-blur-sm">
                        <div className="flex flex-col items-center">
                            <Loader2 className="animate-spin text-indigo-600 mb-2" size={40} />
                            <span className="font-medium text-indigo-800">Expandiendo grafo...</span>
                        </div>
                    </div>
                )}

                {error && (
                    <div className="absolute top-10 left-1/2 -translate-x-1/2 bg-red-100 text-red-800 px-6 py-3 rounded-full shadow-lg z-50 border border-red-200">
                        Error: {error}
                    </div>
                )}

                <ReactFlow
                    nodes={nodes}
                    edges={edges}
                    onNodesChange={onNodesChange}
                    onEdgesChange={onEdgesChange}
                    onNodeClick={handleNodeClick}
                    fitView
                    minZoom={0.1} // Allow zooming out far for large trees
                    nodesDraggable={false} // Keep layout rigid
                >
                    <Background color="#94a3b8" gap={20} />
                    <Controls />
                </ReactFlow>
            </div>

            <div className="absolute bottom-6 left-1/2 -translate-x-1/2 bg-white/80 dark:bg-slate-900/80 backdrop-blur px-4 py-2 rounded-full text-xs text-slate-600 border border-slate-200 shadow-sm pointer-events-none">
                "El centro es {rootNode}. Haz click en un nodo periférico para convertirlo en el nuevo centro."
            </div>
        </div>
    );
}
