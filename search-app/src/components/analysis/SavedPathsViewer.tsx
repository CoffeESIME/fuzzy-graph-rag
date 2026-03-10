import React, { useState, useEffect, useCallback, useMemo } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { FileDown, RefreshCw, X, FolderOpen, MousePointerClick, Image, Music, Video, File, ChevronRight, Activity, Cpu, BrainCircuit } from 'lucide-react';
import ReactFlow, {
    Background,
    Controls,
    MiniMap,
    MarkerType,
    Position,
    applyNodeChanges,
} from 'reactflow';
import type { Node, Edge, NodeChange } from 'reactflow';
import 'reactflow/dist/style.css';
import MediaPreview from '../search/MediaPreview';
import { getAssetPreview, explainAnalyticalPath } from '../../lib/api';
import type { AssetPreviewResponse } from '../../lib/api';

// --- Types ---
interface SavedPathInfo {
    filename: string;
    tool_type: string; // 'serendipity_path', 'pathfinder', etc.
    created_at: string;
    size_bytes: number;
}

// Support both Pathfinder mode and Serendipity path structures
interface PathNodeData {
    id: string;
    label?: string; // from pathfinder
    name?: string;  // from serendipity
    type?: string;  // 'Concept', 'Asset'
    node_type?: string; // from pathfinder
    weight?: number;
    file_hash?: string;
    mime_type?: string;
}

interface PathEdgeData {
    source: string;
    target: string;
    weight?: number;
    rel_type?: string;
}

export default function SavedPathsViewer() {
    const navigate = useNavigate();
    const [paths, setPaths] = useState<SavedPathInfo[]>([]);
    const [loadingList, setLoadingList] = useState(false);

    const [selectedPathInfo, setSelectedPathInfo] = useState<SavedPathInfo | null>(null);
    const [pathContent, setPathContent] = useState<any | null>(null);
    const [loadingContent, setLoadingContent] = useState(false);

    // ReactFlow states
    const [nodes, setNodes] = useState<Node[]>([]);
    const [edges, setEdges] = useState<Edge[]>([]);

    const onNodesChange = useCallback(
        (changes: NodeChange[]) => setNodes((nds) => applyNodeChanges(changes, nds)),
        [setNodes]
    );

    // Detail Panel
    const [selectedNodeData, setSelectedNodeData] = useState<PathNodeData | null>(null);
    const [previewData, setPreviewData] = useState<AssetPreviewResponse | null>(null);

    // LLM Explanation state
    const [liveExplanation, setLiveExplanation] = useState<string | null>(null);
    const [explaining, setExplaining] = useState(false);
    const [privacyMode, setPrivacyMode] = useState(true);

    const fetchPaths = useCallback(async () => {
        setLoadingList(true);
        try {
            const res = await axios.get<{ files: SavedPathInfo[] }>('http://localhost:8000/analysis/saved-paths');
            setPaths(res.data.files || []);
        } catch (error) {
            console.error("Error fetching paths:", error);
        } finally {
            setLoadingList(false);
        }
    }, []);

    useEffect(() => {
        fetchPaths();
    }, [fetchPaths]);

    const loadPathContent = async (info: SavedPathInfo) => {
        setSelectedPathInfo(info);
        setLoadingContent(true);
        setPathContent(null);
        setSelectedNodeData(null);
        setPreviewData(null);
        setLiveExplanation(null);

        try {
            const res = await axios.get(`http://localhost:8000/analysis/saved-paths/${info.filename}`);
            const data = res.data;
            setPathContent(data);

            // Build Graph
            buildGraph(data, info.tool_type);

        } catch (error) {
            console.error("Error loading path content:", error);
        } finally {
            setLoadingContent(false);
        }
    };

    const buildGraph = (data: any, toolType: string) => {
        let newNodes: Node[] = [];
        let newEdges: Edge[] = [];
        const spacingX = 220;

        if (toolType === 'serendipity_path' && data.path) {
            // Linear graph
            data.path.forEach((p: PathNodeData, idx: number) => {
                const isAsset = p.type === 'Asset';
                newNodes.push({
                    id: p.id,
                    type: 'default',
                    position: { x: idx * spacingX, y: 150 },
                    data: {
                        label: (
                            <div style={{ textAlign: 'center' }}>
                                <div style={{ fontWeight: 'bold', fontSize: 12, marginBottom: 4 }}>{p.name}</div>
                                <div style={{ fontSize: 10, color: '#64748b' }}>{p.type}</div>
                                {p.weight && <div style={{ fontSize: 10, color: '#0ea5e9', marginTop: 2 }}>w: {p.weight.toFixed(2)}</div>}
                            </div>
                        ),
                        fullData: p
                    },
                    style: {
                        background: isAsset ? '#1e293b' : '#312e81',
                        color: 'white',
                        border: `1px solid ${isAsset ? '#3b82f6' : '#6366f1'}`,
                        borderRadius: 8,
                        minWidth: 160,
                        padding: 10
                    },
                    sourcePosition: Position.Right,
                    targetPosition: Position.Left,
                });

                if (idx > 0) {
                    newEdges.push({
                        id: `e-${data.path[idx - 1].id}-${p.id}`,
                        source: data.path[idx - 1].id,
                        target: p.id,
                        animated: true,
                        style: { stroke: '#6366f1', strokeWidth: 2 }
                    });
                }
            });
        } else if (data.nodes && data.edges) {
            // Pathfinder Graph
            data.nodes.forEach((n: PathNodeData, idx: number) => {
                const isAsset = n.node_type === 'DigitalAsset' || n.type === 'Asset';
                // Very basic linear layout for Pathfinder nodes (you can improve layout if needed)
                newNodes.push({
                    id: n.id,
                    type: 'default',
                    position: { x: (idx % 3) * 280, y: Math.floor(idx / 3) * 150 + 50 },
                    data: {
                        label: (
                            <div style={{ textAlign: 'center' }}>
                                <div style={{ fontWeight: 'bold', fontSize: 12, marginBottom: 4 }}>{n.label || n.name}</div>
                                <div style={{ fontSize: 10, color: '#64748b' }}>{n.node_type || n.type}</div>
                            </div>
                        ),
                        fullData: n
                    },
                    style: {
                        background: isAsset ? '#1e293b' : '#312e81',
                        color: 'white',
                        border: `1px solid ${isAsset ? '#3b82f6' : '#6366f1'}`,
                        borderRadius: 8,
                        minWidth: 160,
                        padding: 10
                    },
                });
            });

            data.edges.forEach((e: PathEdgeData, idx: number) => {
                newEdges.push({
                    id: `e-${e.source}-${e.target}-${idx}`,
                    source: e.source,
                    target: e.target,
                    label: e.weight ? e.weight.toFixed(2) : '',
                    labelStyle: { fill: '#94a3b8', fontSize: 10, fontWeight: 700 },
                    labelBgStyle: { fill: '#1e293b', fillOpacity: 0.8 },
                    animated: true,
                    style: { stroke: '#4f46e5', strokeWidth: 1.5 },
                    markerEnd: { type: MarkerType.ArrowClosed, color: '#4f46e5' },
                });
            });
        }

        setNodes(newNodes);
        setEdges(newEdges);
    };

    const handleExplainPath = async () => {
        if (nodes.length === 0) return;
        setExplaining(true);
        try {
            const res = await explainAnalyticalPath({
                tool_name: selectedPathInfo?.tool_type || 'saved_path',
                nodes: nodes.map(n => n.data.fullData),
                edges: edges.map(e => ({ source: e.source, target: e.target })),
                privacy_mode: privacyMode
            });
            setLiveExplanation(res.explanation);
        } catch (err) {
            console.error("Error explaining path", err);
        } finally {
            setExplaining(false);
        }
    };

    const getIconForType = (mime?: string) => {
        if (!mime) return <File size={48} className="text-slate-500" />;
        if (mime.startsWith('image/')) return <Image size={48} className="text-blue-400" />;
        if (mime.startsWith('audio/')) return <Music size={48} className="text-purple-400" />;
        if (mime.startsWith('video/')) return <Video size={48} className="text-pink-400" />;
        return <File size={48} className="text-slate-400" />;
    };

    return (
        <div style={{ padding: '24px 32px', display: 'flex', flexDirection: 'column', height: 'calc(100vh - 84px)' }}>
            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20, flexShrink: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <div style={{ width: 44, height: 44, borderRadius: 10, background: '#4f46e5' + '20', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <FolderOpen size={24} color="#6366f1" />
                    </div>
                    <div>
                        <h1 style={{ fontSize: '1.5rem', fontWeight: 700, margin: 0, color: '#f8fafc' }}>
                            Visualizador de Caminos
                        </h1>
                        <p style={{ margin: 0, color: '#94a3b8', fontSize: '0.85rem', marginTop: 2 }}>
                            Galería de descubrimientos de Serendipia y Pathfinder.
                        </p>
                    </div>
                </div>
                <button onClick={() => navigate('/analysis')} className="btn-secondary">Volver</button>
            </div>

            <div style={{ display: 'flex', flex: 1, gap: 20, minHeight: 0 }}>
                {/* Sidebar List */}
                <div style={{
                    width: 320, background: '#0f172a', borderRadius: 16, border: '1px solid #1e293b',
                    display: 'flex', flexDirection: 'column', overflow: 'hidden', flexShrink: 0
                }}>
                    <div style={{ padding: '16px 20px', borderBottom: '1px solid #1e293b', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <h3 style={{ fontSize: '0.9rem', fontWeight: 600, color: '#f8fafc', margin: 0 }}>Archivos Guardados</h3>
                        <button onClick={fetchPaths} style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}>
                            <RefreshCw size={14} className={loadingList ? 'animate-spin' : ''} />
                        </button>
                    </div>

                    <div style={{ overflowY: 'auto', flex: 1, padding: 10 }}>
                        {paths.length === 0 && !loadingList && (
                            <div style={{ textAlign: 'center', color: '#64748b', marginTop: 40, fontSize: '0.85rem' }}>
                                No hay archivos guardados aún.
                            </div>
                        )}
                        {paths.map(p => {
                            const isSerendipity = p.tool_type === 'serendipity_path';
                            const isSelected = selectedPathInfo?.filename === p.filename;

                            return (
                                <div
                                    key={p.filename}
                                    onClick={() => loadPathContent(p)}
                                    style={{
                                        padding: '12px 16px', borderRadius: 8, cursor: 'pointer',
                                        background: isSelected ? '#1e293b' : 'transparent',
                                        border: `1px solid ${isSelected ? '#3b82f6' : 'transparent'}`,
                                        marginBottom: 4, transition: 'all 0.2s'
                                    }}
                                    onMouseOver={(e) => { if (!isSelected) e.currentTarget.style.background = '#162032'; }}
                                    onMouseOut={(e) => { if (!isSelected) e.currentTarget.style.background = 'transparent'; }}
                                >
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
                                        {isSerendipity ? <Activity size={16} color="#ec4899" /> : <Cpu size={16} color="#0ea5e9" />}
                                        <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#e2e8f0', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                            {p.filename}
                                        </span>
                                    </div>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingLeft: 26 }}>
                                        <span style={{ fontSize: '0.7rem', color: '#64748b' }}>
                                            {new Date(p.created_at).toLocaleString()}
                                        </span>
                                        <span style={{ fontSize: '0.7rem', color: '#64748b', background: '#1e293b', padding: '2px 6px', borderRadius: 4 }}>
                                            {(p.size_bytes / 1024).toFixed(1)} KB
                                        </span>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>

                {/* Main Content Area */}
                <div style={{
                    flex: 1, background: '#0f172a', borderRadius: 16, border: '1px solid #1e293b',
                    display: 'flex', flexDirection: 'column', overflow: 'hidden', position: 'relative'
                }}>
                    {!selectedPathInfo ? (
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#64748b' }}>
                            <FileDown size={48} style={{ marginBottom: 16, opacity: 0.5 }} />
                            <p>Selecciona un archivo del panel izquierdo para visualizarlo.</p>
                        </div>
                    ) : loadingContent ? (
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
                            <RefreshCw size={32} className="animate-spin text-indigo-500" />
                        </div>
                    ) : (
                        <>
                            {/* Top Info Bar */}
                            <div style={{ padding: '16px 20px', borderBottom: '1px solid #1e293b', background: '#0f172a', zIndex: 10, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <div>
                                    <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#818cf8', textTransform: 'uppercase', letterSpacing: 1 }}>
                                        {selectedPathInfo.tool_type.replace('_', ' ')}
                                    </span>
                                    <h2 style={{ fontSize: '1.1rem', margin: '4px 0 0 0', color: '#f8fafc' }}>{selectedPathInfo.filename}</h2>
                                </div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                                    {pathContent?.message && (
                                        <div style={{ fontSize: '0.8rem', color: '#a3e635', background: '#3f621240', padding: '6px 12px', borderRadius: 6, border: '1px solid #4d7c0f' }}>
                                            {pathContent.message}
                                        </div>
                                    )}
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                                        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.8rem', color: '#94a3b8', cursor: 'pointer' }}>
                                            <input type="checkbox" checked={privacyMode} onChange={e => setPrivacyMode(e.target.checked)} />
                                            Privacy Mode
                                        </label>
                                        <button onClick={handleExplainPath} disabled={explaining} style={{ background: '#3b82f6', color: '#f8fafc', border: 'none', padding: '6px 12px', borderRadius: 6, fontSize: '0.8rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6, cursor: explaining ? 'not-allowed' : 'pointer', opacity: explaining ? 0.7 : 1 }}>
                                            {explaining ? <RefreshCw size={14} className="animate-spin" /> : <BrainCircuit size={14} />}
                                            {explaining ? 'Generando...' : 'Explicar con IA'}
                                        </button>
                                    </div>
                                </div>
                            </div>

                            <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
                                {/* Graph Area */}
                                <div style={{ flex: 1, position: 'relative', height: '100%' }}>
                                    <ReactFlow
                                        nodes={nodes}
                                        edges={edges}
                                        onNodesChange={onNodesChange}
                                        fitView
                                        fitViewOptions={{ padding: 0.2 }}
                                        onNodeClick={async (_, node) => {
                                            const nData = node.data.fullData;
                                            setSelectedNodeData(nData);
                                            setPreviewData(null);

                                            // Fetch presigned URL if it's an asset
                                            if (nData.type === 'Asset' || nData.node_type === 'DigitalAsset') {
                                                try {
                                                    const res = await getAssetPreview(nData.id);
                                                    setPreviewData(res);
                                                } catch (err) {
                                                    console.error("Error fetching preview", err);
                                                }
                                            }
                                        }}
                                        proOptions={{ hideAttribution: true }}
                                    >
                                        <Background gap={20} size={1} color="#334155" />
                                        <Controls />
                                    </ReactFlow>

                                    {/* Selected Node Overlay (if clicking an Asset) */}
                                    {selectedNodeData && (
                                        <div style={{
                                            position: 'absolute', right: 20, top: 20, width: 340,
                                            background: '#0f172a', borderRadius: 12, border: '1px solid #334155',
                                            boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.5)', overflow: 'hidden',
                                            zIndex: 50, display: 'flex', flexDirection: 'column'
                                        }}>
                                            <div style={{ padding: '12px 16px', borderBottom: '1px solid #1e293b', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#1e293b' }}>
                                                <h3 style={{ fontSize: '0.9rem', margin: 0, color: '#f8fafc' }}>
                                                    {selectedNodeData.type === 'Asset' || selectedNodeData.node_type === 'DigitalAsset' ? 'Ver Archivo' : 'Concepto'}
                                                </h3>
                                                <button onClick={() => setSelectedNodeData(null)} style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}>
                                                    <X size={16} />
                                                </button>
                                            </div>

                                            <div style={{ padding: 16 }}>
                                                <div style={{ fontSize: '1.1rem', fontWeight: 600, color: '#f8fafc', marginBottom: 12, wordBreak: 'break-all' }}>
                                                    {selectedNodeData.name || selectedNodeData.label}
                                                </div>

                                                {(selectedNodeData.type === 'Asset' || selectedNodeData.node_type === 'DigitalAsset') ? (
                                                    selectedNodeData.file_hash ? (
                                                        <div style={{ marginTop: 10, background: '#000', borderRadius: 8, overflow: 'hidden' }}>
                                                            {previewData ? (
                                                                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                                                                    {(previewData.download_url || previewData.minio_path) && (
                                                                        <MediaPreview
                                                                            url={previewData.download_url}
                                                                            path={previewData.minio_path}
                                                                        />
                                                                    )}
                                                                    {previewData.content && previewData.content !== 'No textual content available' && (
                                                                        <div style={{ padding: 12 }}>
                                                                            <div style={{ fontSize: '0.65rem', color: '#64748b', fontWeight: 700, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 8 }}>CONTENIDO TEXTUAL</div>
                                                                            <div style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid #334155', borderRadius: 6, padding: 12, fontSize: '0.8rem', color: '#e2e8f0', whiteSpace: 'pre-wrap', maxHeight: 200, overflowY: 'auto' }}>
                                                                                {previewData.content}
                                                                            </div>
                                                                        </div>
                                                                    )}
                                                                </div>
                                                            ) : (
                                                                <div style={{ color: '#94a3b8', padding: 12, textAlign: 'center' }}>Cargando preview...</div>
                                                            )}
                                                        </div>
                                                    ) : (
                                                        <div style={{ color: '#ef4444', fontSize: '0.8rem', padding: 12, background: '#7f1d1d20', borderRadius: 6, border: '1px solid #7f1d1d' }}>
                                                            No se pudo recuperar el hash para visualizar el archivo.
                                                        </div>
                                                    )
                                                ) : (
                                                    <div style={{ color: '#94a3b8', fontSize: '0.85rem' }}>
                                                        Este es un nodo conceptual estructural semántico.
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    )}
                                </div>

                                {/* Right Info Area (LLM Explanation) */}
                                {(liveExplanation || pathContent?.llm_explanation) && (
                                    <div style={{
                                        width: 320, borderLeft: '1px solid #1e293b', background: '#020617',
                                        display: 'flex', flexDirection: 'column', height: '100%'
                                    }}>
                                        <div style={{ padding: '16px 20px', borderBottom: '1px solid #1e293b', flexShrink: 0 }}>
                                            <h3 style={{ fontSize: '0.9rem', margin: 0, color: '#a78bfa', display: 'flex', alignItems: 'center', gap: 6 }}>
                                                <Activity size={16} /> Explicación IA
                                            </h3>
                                        </div>
                                        <div style={{ padding: 20, overflowY: 'auto', flex: 1 }} className="custom-scrollbar">
                                            <div style={{
                                                fontSize: '0.85rem', color: '#cbd5e1', lineHeight: 1.6,
                                                background: '#1e293b', padding: 16, borderRadius: 12, border: '1px solid #334155'
                                            }}>
                                                {/* Prettier rendering if it is stringified JSON */}
                                                {(() => {
                                                    const contentToParse = liveExplanation || pathContent.llm_explanation;
                                                    try {
                                                        const parsed = typeof contentToParse === 'string'
                                                            ? JSON.parse(contentToParse)
                                                            : contentToParse;

                                                        if (parsed.explanation && Array.isArray(parsed.explanation)) {
                                                            return parsed.explanation.map((step: any, i: number) => (
                                                                <div key={i} style={{ marginBottom: 16 }}>
                                                                    <div style={{ fontWeight: 600, color: '#f8fafc', marginBottom: 4 }}>
                                                                        Paso {step.step}: {step.from} → {step.to}
                                                                    </div>
                                                                    <div style={{ color: '#94a3b8' }}>{step.reason}</div>
                                                                </div>
                                                            ));
                                                        }
                                                        return <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', color: '#94a3b8', fontSize: '0.8rem', margin: 0 }}>{JSON.stringify(parsed, null, 2)}</pre>;
                                                    } catch (e) {
                                                        return <div style={{ whiteSpace: 'pre-wrap' }}>{contentToParse}</div>;
                                                    }
                                                })()}
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </>
                    )}
                </div>
            </div>
        </div>
    );
}
