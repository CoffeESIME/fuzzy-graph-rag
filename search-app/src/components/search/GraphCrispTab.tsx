import { useState, useRef, useEffect, useMemo } from 'react';
import { Search, GitBranch, FileText, Layers, Workflow } from 'lucide-react';
// ForceGraph2D removed as it is now in GraphVisualizer2D
import { useGraphCrispSearch } from '../../hooks/useSearch';
import { useSearchStore } from '../../store/searchStore';
import type { GraphNode, GraphCrispResponse } from '../../types/search';
import MediaPreview from './MediaPreview';
import TextPreviewModal from './TextPreviewModal';
import GraphVisualizer2D from './GraphVisualizer2D';
// import GraphVisualizerThree from './GraphVisualizerThree'; // Kept for reference but unused
import GraphVisualizerReactFlow from './GraphVisualizerReactFlow';

export default function GraphCrispTab() {
    const [query, setQuery] = useState('');
    const [alphaCut, setAlphaCut] = useState(0.9);
    const [limit, setLimit] = useState(20);
    const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
    const [textPreviewOpen, setTextPreviewOpen] = useState(false);
    const [visualizerMode, setVisualizerMode] = useState<'2d' | 'flow'>('2d');
    const containerRef = useRef<HTMLDivElement>(null);
    const [dimensions, setDimensions] = useState({ width: 800, height: 600 });

    const mutation = useGraphCrispSearch();
    const { results, loading } = useSearchStore();
    const resultData = results['graph-crisp'] as GraphCrispResponse | undefined;

    // Resize observer para el contenedor del grafo
    useEffect(() => {
        if (!containerRef.current) return;
        const ro = new ResizeObserver((entries) => {
            const entry = entries[0];
            setDimensions({
                width: entry.contentRect.width,
                height: entry.contentRect.height
            });
        });
        ro.observe(containerRef.current);
        return () => ro.disconnect();
    }, []);

    const handleSearch = () => {
        if (!query.trim()) return;
        setSelectedNode(null);
        mutation.mutate({
            query: query.trim(),
            alpha_cut: alphaCut,
            limit
        });
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter') handleSearch();
    };

    // --- OPTIMIZACIÓN 1: Memorizar graphData ---
    // Esto evita que el grafo se reinicie (física) cada vez que escribes en el input.
    const topology = resultData?.graph_topology;
    const graphData = useMemo(() => {
        return topology
            ? { nodes: [...topology.nodes], links: [...topology.edges] }
            : { nodes: [], links: [] };
    }, [topology]);

    // Helper for sidebar coloring
    const getNodeColor = (node: GraphNode) => {
        switch (node.type) {
            case 'Concept': return '#8b5cf6'; // Violet
            case 'Person': return '#f43f5e'; // Rose
            case 'Location': return '#f59e0b'; // Amber
            case 'Organization': return '#3b82f6'; // Blue
            case 'Event': return '#ec4899'; // Pink
            case 'Project': return '#14b8a6'; // Teal
            case 'DigitalAsset': return '#10b981'; // Emerald
            default: return '#64748b'; // Slate
        }
    };

    return (
        <div style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 16 }}>
            {/* Header / Controls */}
            <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end', flexWrap: 'wrap' }}>
                <div style={{ flex: 1, minWidth: 200 }}>
                    <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>
                        Consulta en Grafo
                    </label>
                    <input
                        className="search-input"
                        type="text"
                        placeholder="Ej: machine learning, renacimiento..."
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        onKeyDown={handleKeyDown}
                    />
                </div>

                <div style={{ width: 120 }}>
                    <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>
                        Alpha Cut ({alphaCut})
                    </label>
                    <input
                        type="range"
                        min="0" max="1" step="0.05"
                        value={alphaCut}
                        onChange={(e) => setAlphaCut(parseFloat(e.target.value))}
                        style={{ width: '100%', accentColor: 'var(--accent-indigo)' }}
                    />
                </div>

                <div style={{ width: 80 }}>
                    <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>
                        Límite
                    </label>
                    <input
                        className="search-input"
                        type="number"
                        min={1} max={100}
                        value={limit}
                        onChange={(e) => setLimit(parseInt(e.target.value))}
                        style={{ textAlign: 'center' }}
                    />
                </div>

                <button
                    className="btn-primary"
                    onClick={handleSearch}
                    disabled={!query.trim() || loading['graph-crisp']}
                >
                    <Search size={16} />
                    Explorar
                </button>

                {/* Visualizer Toggle */}
                <div style={{ marginLeft: 'auto', display: 'flex', background: 'var(--bg-input)', borderRadius: 6, padding: 2 }}>
                    <button
                        onClick={() => setVisualizerMode('2d')}
                        style={{
                            padding: '6px 10px', borderRadius: 4,
                            background: visualizerMode === '2d' ? 'var(--accent-indigo)' : 'transparent',
                            color: visualizerMode === '2d' ? 'white' : 'var(--text-secondary)',
                            display: 'flex', alignItems: 'center', gap: 6,
                            fontSize: '0.75rem', cursor: 'pointer', border: 'none'
                        }}
                        title="Vista Grafo de Fuerza (2D)"
                    >
                        <Layers size={14} /> Force
                    </button>
                    <button
                        onClick={() => setVisualizerMode('flow')}
                        style={{
                            padding: '6px 10px', borderRadius: 4,
                            background: visualizerMode === 'flow' ? 'var(--accent-indigo)' : 'transparent',
                            color: visualizerMode === 'flow' ? 'white' : 'var(--text-secondary)',
                            display: 'flex', alignItems: 'center', gap: 6,
                            fontSize: '0.75rem', cursor: 'pointer', border: 'none'
                        }}
                        title="Vista Diagrama (React Flow)"
                    >
                        <Workflow size={14} /> Flow
                    </button>
                </div>
            </div>

            {/* Main Content Area */}
            <div style={{ display: 'flex', gap: 16, flex: 1, minHeight: 0 }}>
                {/* Graph Visualization */}
                <div
                    ref={containerRef}
                    style={{
                        flex: 1,
                        background: 'var(--bg-card)',
                        borderRadius: 12,
                        border: '1px solid var(--border-subtle)',
                        overflow: 'hidden',
                        position: 'relative',
                        minHeight: 400
                    }}
                >
                    {!resultData && !loading['graph-crisp'] && (
                        <div style={{
                            position: 'absolute', inset: 0,
                            display: 'flex', flexDirection: 'column',
                            alignItems: 'center', justifyContent: 'center',
                            color: 'rgba(255,255,255,0.3)'
                        }}>
                            <GitBranch size={48} style={{ marginBottom: 16, opacity: 0.5 }} />
                            <p>Visualización de grafo</p>
                        </div>
                    )}

                    {loading['graph-crisp'] && (
                        <div style={{
                            position: 'absolute', inset: 0,
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            zIndex: 10, background: 'rgba(15, 23, 42, 0.7)'
                        }}>
                            <div className="loading-spinner" />
                        </div>
                    )}

                    {/* Visualizer Component */}
                    {visualizerMode === '2d' ? (
                        <GraphVisualizer2D
                            graphData={graphData}
                            dimensions={dimensions}
                            onNodeClick={setSelectedNode}
                            onEngineStop={() => console.log('Simulación 2D estabilizada')}
                        />
                    ) : (
                        <GraphVisualizerReactFlow
                            graphData={graphData}
                            dimensions={dimensions}
                            onNodeClick={setSelectedNode}
                        />
                    )}

                    {/* Legend Overlay */}
                    <div style={{
                        position: 'absolute', bottom: 12, left: 12,
                        background: 'rgba(15, 23, 42, 0.85)',
                        padding: '8px 12px', borderRadius: 8,
                        border: '1px solid var(--border-subtle)',
                        fontSize: '0.75rem', color: 'var(--text-secondary)',
                        backdropFilter: 'blur(4px)',
                        pointerEvents: 'none'
                    }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                            <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#8b5cf6' }}></span>
                            <span>Concepto</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                            <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#f43f5e' }}></span>
                            <span>Persona</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                            <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#f59e0b' }}></span>
                            <span>Lugar</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#10b981' }}></span>
                            <span>Asset Digital</span>
                        </div>
                        <div style={{ marginTop: 8, fontSize: '0.7rem', opacity: 0.7 }}>
                            * Haz zoom para ver etiquetas
                        </div>
                    </div>
                </div>

                {/* Side Panel / Details */}
                <div style={{
                    width: 350, borderLeft: '1px solid var(--border-color)',
                    background: 'var(--bg-secondary)', overflowY: 'auto',
                    display: 'flex', flexDirection: 'column'
                }}>
                    {/* Logic & Query Info Section */}
                    {resultData && (
                        <div style={{ padding: 16, borderBottom: '1px solid var(--border-color)' }}>
                            <h3 style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
                                <GitBranch size={14} className="text-purple-400" />
                                Lógica de Ejecución
                            </h3>

                            <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: 12 }}>
                                <div>
                                    <span style={{ display: 'block', fontWeight: 500, marginBottom: 4 }}>Conceptos Ancla Identificados:</span>
                                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                                        {resultData.concepts_matched.length > 0 ? resultData.concepts_matched.map(c => (
                                            <span key={c} style={{
                                                padding: '2px 6px', borderRadius: 4,
                                                background: 'rgba(139, 92, 246, 0.15)',
                                                color: '#a78bfa', fontSize: '0.7rem'
                                            }}>
                                                {c}
                                            </span>
                                        )) : <span style={{ fontStyle: 'italic', opacity: 0.5 }}>Ninguno</span>}
                                    </div>
                                </div>

                                <div>
                                    <span style={{ display: 'block', fontWeight: 500, marginBottom: 4 }}>Camino Lógico (Cypher):</span>
                                    <div style={{
                                        background: 'rgba(0,0,0,0.3)', padding: 8, borderRadius: 6,
                                        fontFamily: 'monospace', fontSize: '0.65rem', whiteSpace: 'pre-wrap',
                                        color: '#cbd5e1'
                                    }}>
                                        {`MATCH (n:Concept|Person|Location|...)
WHERE n.name CONTAINS "${query}"
<-[r:MENTIONS|EVOKES|...]-(d:Asset)
WHERE r.weight >= ${alphaCut}
RETURN n, r, d`}
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}

                    {selectedNode && (
                        <div style={{ padding: 16 }}>
                            <h4 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>
                                {selectedNode.label}
                            </h4>
                            <span style={{
                                fontSize: '0.75rem',
                                padding: '2px 8px',
                                borderRadius: 12,
                                background: getNodeColor(selectedNode) + '20',
                                color: getNodeColor(selectedNode),
                                fontWeight: 600,
                                marginBottom: 12,
                                display: 'inline-block'
                            }}>
                                {selectedNode.type}
                            </span>

                            <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: 8 }}>
                                {Object.entries(selectedNode.properties).map(([key, val]) => {
                                    // Filtrar propiedades grandes o técnicas
                                    if (['download_url', 'minio_path', 'embedding', 'text', 'content', 'transcript'].includes(key)) return null;
                                    return (
                                        <div key={key}>
                                            <strong style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>{key}:</strong>
                                            <div style={{ wordBreak: 'break-word' }}>{String(val)}</div>
                                        </div>
                                    );
                                })}
                            </div>

                            {/* Media Preview */}
                            {(selectedNode.properties.download_url || selectedNode.properties.minio_path) && (
                                <div style={{ marginTop: 16 }}>
                                    <h5 style={{ fontSize: '0.8rem', fontWeight: 600, marginBottom: 8, color: 'var(--text-muted)' }}>
                                        Vista Previa
                                    </h5>
                                    <MediaPreview
                                        url={selectedNode.properties.download_url}
                                        path={selectedNode.properties.minio_path}
                                    />
                                </div>
                            )}

                            {/* Text Content Preview Button */}
                            {(selectedNode.properties.text || selectedNode.properties.content || selectedNode.properties.transcript) && (
                                <button
                                    onClick={() => setTextPreviewOpen(true)}
                                    style={{
                                        marginTop: 12,
                                        width: '100%',
                                        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                                        padding: '8px',
                                        background: 'var(--bg-input)',
                                        border: '1px solid var(--border-subtle)',
                                        borderRadius: 6,
                                        color: 'var(--text-secondary)',
                                        fontSize: '0.8rem',
                                        cursor: 'pointer',
                                        transition: 'all 0.2s'
                                    }}
                                    onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--accent-indigo)'}
                                    onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--border-subtle)'}
                                >
                                    <FileText size={14} />
                                    Ver contenido de texto
                                </button>
                            )}
                        </div>
                    )}
                </div>
            </div>

            {/* Text Preview Modal */}
            {selectedNode && (
                <TextPreviewModal
                    isOpen={textPreviewOpen}
                    onClose={() => setTextPreviewOpen(false)}
                    title={selectedNode.label || 'Contenido de texto'}
                    content={
                        selectedNode.properties.text ||
                        selectedNode.properties.content ||
                        selectedNode.properties.transcript ||
                        ''
                    }
                />
            )}
        </div>
    );
}