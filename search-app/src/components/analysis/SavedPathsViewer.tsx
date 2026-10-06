import PathfinderRoutes from './PathfinderRoutes';
import { readSavedPathfinder, readPathfinderExplanations, explanationFor, explanationInput, exportPathfinder } from '../../lib/pathfinderRoutes';
import type { PathfinderPath, PathfinderExplanation } from '../../types/pathfinder';
import Explanation from '../graph/Explanation';
import { downloadBlob } from '../graph/figureExport';
import React, { useState, useRef, useEffect, useEffectEvent, useCallback, useMemo } from 'react';
import axios from 'axios';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { FileDown, RefreshCw, X, FolderOpen, MousePointerClick, Image, Music, Video, File, ChevronRight, Activity, Cpu, BrainCircuit } from 'lucide-react';
import ReactFlow from '../graph/GraphCanvas';
import {
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
    const [searchParams] = useSearchParams();
    const featuredFilename = searchParams.get('path');
    const [paths, setPaths] = useState<SavedPathInfo[]>([]);
    const [loadingList, setLoadingList] = useState(false);

    const [selectedPathInfo, setSelectedPathInfo] = useState<SavedPathInfo | null>(null);
    const [pathContent, setPathContent] = useState<any | null>(null);
    const [loadingContent, setLoadingContent] = useState(false);
    const [selectedRoute, setSelectedRoute] = useState<PathfinderPath | null>(null);
    const savedPathfinder = readSavedPathfinder(pathContent);
    const explanationRequest = useRef(0);
    const [explanations, setExplanations] = useState<PathfinderExplanation[]>([]);
    const [explanationError, setExplanationError] = useState<string | null>(null);
    const loadRequest = useRef(0);

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
        const requestId = ++loadRequest.current;
        explanationRequest.current += 1;
        setSelectedRoute(null);
        setSelectedPathInfo(info);
        setLoadingContent(true);
        setPathContent(null);
        setSelectedNodeData(null);
        setPreviewData(null);
        setLiveExplanation(null);
        setExplanations([]); setExplanationError(null);

        try {
            const res = await axios.get(`http://localhost:8000/analysis/saved-paths/${info.filename}`);
            if (requestId !== loadRequest.current) return;
            const data = res.data;
            setPathContent(data);
            setExplanations(readPathfinderExplanations(data));

            // Build Graph
            buildGraph(data, info.tool_type);

        } catch (error) {
            console.error("Error loading path content:", error);
        } finally {
            if (requestId === loadRequest.current) setLoadingContent(false);
        }
    };

    const openFeaturedPath = useEffectEvent((info: SavedPathInfo) => { void loadPathContent(info); });
    useEffect(() => {
        const info = paths.find(path => path.filename === featuredFilename);
        if (info) openFeaturedPath(info);
    }, [paths, featuredFilename]);

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
                                <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{p.type}</div>
                                {p.weight && <div style={{ fontSize: 10, color: '#0ea5e9', marginTop: 2 }}>w: {p.weight.toFixed(2)}</div>}
                            </div>
                        ),
                        fullData: p
                    },
                    style: {
                        background: isAsset ? 'var(--surface)' : '#312e81',
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
                        data: { relation: '', weight: p.weight, kind: 'serendipity' },
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
                                <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{n.node_type || n.type}</div>
                            </div>
                        ),
                        fullData: n
                    },
                    style: {
                        background: isAsset ? 'var(--surface)' : '#312e81',
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
                    data: { relation: e.rel_type, weight: e.weight },
                    label: e.weight ? e.weight.toFixed(2) : '',
                    labelStyle: { fill: 'var(--text-secondary)', fontSize: 10, fontWeight: 700 },
                    labelBgStyle: { fill: 'var(--surface)', fillOpacity: 0.8 },
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
        const requestId = ++explanationRequest.current;
        setExplaining(true);
        setExplanationError(null);
        try {
            const res = await explainAnalyticalPath({
                tool_name: selectedPathInfo?.tool_type || 'saved_path',
                ...(savedPathfinder ? explanationInput(savedPathfinder, selectedRoute) : { nodes: nodes.map(n => n.data.fullData), edges: edges.map(e => ({ source: e.source, target: e.target })) }),
                privacy_mode: privacyMode
            });
            if (requestId !== explanationRequest.current) return;
            if (res.status !== 'success') { setExplanationError(res.explanation); return; }
            if (savedPathfinder) setExplanations(previous => [...previous, { path_id: selectedRoute?.id ?? null, path_ids: (selectedRoute ? [selectedRoute] : savedPathfinder.paths ?? []).map(p => p.id), explanation: res.explanation, generated_at: new Date().toISOString(), privacy_mode: privacyMode }]);
            else setLiveExplanation(res.explanation);
        } catch (err) {
            if (requestId === explanationRequest.current) setExplanationError(err instanceof Error ? err.message : String(err));
        } finally {
            setExplaining(false);
        }
    };

    const displayedExplanation = savedPathfinder ? explanationFor(explanations, selectedRoute?.id ?? null) : liveExplanation || pathContent?.llm_explanation;

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
                        <h1 style={{ fontSize: '1.5rem', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
                            Visualizador de Caminos
                        </h1>
                        <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '0.85rem', marginTop: 2 }}>
                            Galería de descubrimientos de Serendipia y Pathfinder.
                        </p>
                    </div>
                </div>
                <button onClick={() => navigate('/analysis')} className="btn-secondary">Volver</button>
            </div>

            <div style={{ display: 'flex', flex: 1, gap: 20, minHeight: 0 }}>
                {/* Sidebar List */}
                <div style={{
                    width: 320, background: 'var(--background-secondary)', borderRadius: 16, border: '1px solid var(--surface)',
                    display: 'flex', flexDirection: 'column', overflow: 'hidden', flexShrink: 0
                }}>
                    <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--surface)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <h3 style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>Archivos Guardados</h3>
                        <button onClick={fetchPaths} style={{ background: 'transparent', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer' }}>
                            <RefreshCw size={14} className={loadingList ? 'animate-spin' : ''} />
                        </button>
                    </div>

                    <div style={{ overflowY: 'auto', flex: 1, padding: 10 }}>
                        {paths.length === 0 && !loadingList && (
                            <div style={{ textAlign: 'center', color: 'var(--text-muted)', marginTop: 40, fontSize: '0.85rem' }}>
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
                                        background: isSelected ? 'var(--surface)' : 'transparent',
                                        border: `1px solid ${isSelected ? '#3b82f6' : 'transparent'}`,
                                        marginBottom: 4, transition: 'all 0.2s'
                                    }}
                                    onMouseOver={(e) => { if (!isSelected) e.currentTarget.style.background = '#162032'; }}
                                    onMouseOut={(e) => { if (!isSelected) e.currentTarget.style.background = 'transparent'; }}
                                >
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
                                        {isSerendipity ? <Activity size={16} color="#ec4899" /> : <Cpu size={16} color="#0ea5e9" />}
                                        <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                            {p.filename}
                                        </span>
                                    </div>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingLeft: 26 }}>
                                        <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                                            {new Date(p.created_at).toLocaleString()}
                                        </span>
                                        <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', background: 'var(--surface)', padding: '2px 6px', borderRadius: 4 }}>
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
                    flex: 1, background: 'var(--background-secondary)', borderRadius: 16, border: '1px solid var(--surface)',
                    display: 'flex', flexDirection: 'column', overflow: 'hidden', position: 'relative'
                }}>
                    {!selectedPathInfo ? (
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)' }}>
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
                            <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--surface)', background: 'var(--background-secondary)', zIndex: 10, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <div>
                                    <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#818cf8', textTransform: 'uppercase', letterSpacing: 1 }}>
                                        {selectedPathInfo.tool_type.replace('_', ' ')}
                                    </span>
                                    <h2 style={{ fontSize: '1.1rem', margin: '4px 0 0 0', color: 'var(--text-primary)' }}>{selectedPathInfo.filename}</h2>
                                </div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                                    {pathContent?.message && (
                                        <div style={{ fontSize: '0.8rem', color: '#a3e635', background: '#3f621240', padding: '6px 12px', borderRadius: 6, border: '1px solid #4d7c0f' }}>
                                            {pathContent.message}
                                        </div>
                                    )}
                                    {savedPathfinder && <button onClick={() => downloadBlob(new Blob([JSON.stringify(exportPathfinder(savedPathfinder, displayedExplanation, selectedRoute?.id ?? null, explanations), null, 2)], { type: 'application/json' }), selectedPathInfo.filename)}>Exportar JSON con explicaciones</button>}
                                    {explanationError && <p role="alert">{explanationError}</p>}
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                                        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.8rem', color: 'var(--text-secondary)', cursor: 'pointer' }}>
                                            <input type="checkbox" checked={privacyMode} onChange={e => setPrivacyMode(e.target.checked)} />
                                            Privacy Mode
                                        </label>
                                        <button onClick={handleExplainPath} disabled={explaining} style={{ background: '#3b82f6', color: 'var(--text-primary)', border: 'none', padding: '6px 12px', borderRadius: 6, fontSize: '0.8rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6, cursor: explaining ? 'not-allowed' : 'pointer', opacity: explaining ? 0.7 : 1 }}>
                                            {explaining ? <RefreshCw size={14} className="animate-spin" /> : <BrainCircuit size={14} />}
                                            {explaining ? (privacyMode ? 'Generando localmente (hasta 15 min)…' : 'Generando…') : selectedRoute ? `Explicar registro ${selectedRoute.rank}` : 'Explicar con IA'}
                                        </button>
                                    </div>
                                </div>
                            </div>

                            <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
                                {/* Graph Area */}
                                <div style={{ flex: 1, minWidth: 0, position: 'relative', height: '100%', overflowY: 'auto' }}>
                                    {savedPathfinder ? <PathfinderRoutes key={selectedPathInfo.filename} result={savedPathfinder} onSelectionChange={path => { setSelectedRoute(path); setExplanationError(null); }} /> : pathContent?.schema_version === 2 ? <p role="alert">El archivo v2 no contiene rutas válidas. No se ha inferido su orden.</p> : (
                                    <ReactFlow
                                        nodes={nodes}
                                        edges={edges}
                                        onNodesChange={onNodesChange}
                                        fitView
                                        fitViewOptions={{ padding: 0.2 }}
                                        title="Caminos guardados" initialLayout="auto"
                                        proOptions={{ hideAttribution: true }}
                                    >
                                        <Background gap={20} size={1} color="var(--border)" />
                                        <Controls />
                                    </ReactFlow>
                                    )}

                                </div>

                                {/* Right Info Area (LLM Explanation) */}
                                {displayedExplanation && (
                                    <div style={{
                                        width: 320, borderLeft: '1px solid var(--surface)', background: 'var(--background)',
                                        display: 'flex', flexDirection: 'column', height: '100%'
                                    }}>
                                        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--surface)', flexShrink: 0 }}>
                                            <h3 style={{ fontSize: '0.9rem', margin: 0, color: '#a78bfa', display: 'flex', alignItems: 'center', gap: 6 }}>
                                                <Activity size={16} /> Explicación IA
                                            </h3>
                                        </div>
                                        <div style={{ padding: 20, overflowY: 'auto', flex: 1 }} className="custom-scrollbar">
                                            <div style={{
                                                fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.6,
                                                background: 'var(--surface)', padding: 16, borderRadius: 12, border: '1px solid var(--border)'
                                            }}>
                                                <Explanation content={displayedExplanation} />
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
