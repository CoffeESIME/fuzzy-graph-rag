import { useState, useRef, useEffect } from 'react';
import { Search, GitBranch } from 'lucide-react';
import ForceGraph2D from 'react-force-graph-2d';
import { useGraphCrispSearch } from '../../hooks/useSearch';
import { useSearchStore } from '../../store/searchStore';
import type { GraphNode, GraphCrispResponse } from '../../types/search';

export default function GraphCrispTab() {
    const [query, setQuery] = useState('');
    const [alphaCut, setAlphaCut] = useState(0.9);
    const [limit, setLimit] = useState(20);
    const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const [dimensions, setDimensions] = useState({ width: 800, height: 600 });

    const mutation = useGraphCrispSearch();
    const { results, loading } = useSearchStore();
    const resultData = results['graph-crisp'] as GraphCrispResponse | undefined;

    // Resize observer for the graph container
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

    // Graph data preparation
    const topology = resultData?.graph_topology;
    const graphData = topology
        ? { nodes: [...topology.nodes], links: [...topology.edges] }
        : { nodes: [], links: [] };

    // Node coloring
    const getNodeColor = (node: GraphNode) => {
        if (node.type === 'Concept') return '#8b5cf6'; // Violet
        if (node.type === 'DigitalAsset') return '#10b981'; // Emerald
        return '#64748b'; // Slate
    };

    const getNodeVal = (node: GraphNode) => {
        if (node.type === 'Concept') return 5;
        return 3;
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
            </div>

            {/* Main Content Area */}
            <div style={{ display: 'flex', gap: 16, flex: 1, minHeight: 0 }}>
                {/* Graph Visualization */}
                <div
                    ref={containerRef}
                    style={{
                        flex: 1,
                        background: '#0f172a',
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

                    {/* @ts-ignore - ForceGraph2D types might be finicky */}
                    <ForceGraph2D
                        width={dimensions.width}
                        height={dimensions.height}
                        graphData={graphData}
                        nodeLabel="label"
                        nodeColor={getNodeColor}
                        nodeVal={getNodeVal}
                        linkColor={() => '#334155'}
                        linkWidth={link => (link as any).weight * 2}
                        onNodeClick={(node) => setSelectedNode(node as GraphNode)}
                        backgroundColor="#0f172a"
                        nodeCanvasObject={(node: any, ctx, globalScale) => {
                            const label = node.label;
                            const fontSize = 12 / globalScale;
                            ctx.font = `${fontSize}px Sans-Serif`;

                            // Draw Circle
                            const r = Math.sqrt(getNodeVal(node)) * 4;
                            ctx.beginPath();
                            ctx.arc(node.x, node.y, r, 0, 2 * Math.PI, false);
                            ctx.fillStyle = getNodeColor(node);
                            ctx.fill();

                            // Draw Label
                            if (globalScale > 1.5) { // Only show labels when zoomed in a bit
                                ctx.textAlign = 'center';
                                ctx.textBaseline = 'middle';
                                ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
                                ctx.fillText(label, node.x, node.y + r + fontSize);
                            }
                        }}
                        linkCanvasObject={(link: any, ctx, globalScale) => {
                            const start = link.source;
                            const end = link.target;

                            // Draw line
                            ctx.beginPath();
                            ctx.moveTo(start.x, start.y);
                            ctx.lineTo(end.x, end.y);
                            ctx.strokeStyle = '#334155';
                            ctx.lineWidth = link.weight * 2;
                            ctx.stroke();

                            // Draw Label (Relationship Type)
                            if (globalScale > 2) { // Only show edge labels when zoomed in
                                const textPos = Object.assign({}, start, { x: start.x + (end.x - start.x) / 2, y: start.y + (end.y - start.y) / 2 });
                                const relType = link.type;
                                const fontSize = 10 / globalScale;
                                ctx.font = `${fontSize}px Sans-Serif`;
                                ctx.fillStyle = '#94a3b8';
                                ctx.textAlign = 'center';
                                ctx.textBaseline = 'middle';
                                ctx.fillText(relType, textPos.x, textPos.y);
                            }
                        }}
                    />

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
                {selectedNode && (
                    <div style={{
                        width: 300,
                        background: 'var(--bg-card)',
                        border: '1px solid var(--border-subtle)',
                        borderRadius: 12,
                        padding: 16,
                        overflowY: 'auto'
                    }}>
                        <h4 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>
                            {selectedNode.label}
                        </h4>
                        <span style={{
                            fontSize: '0.75rem',
                            padding: '2px 8px',
                            borderRadius: 12,
                            background: getNodeColor(selectedNode) + '20', // 20% opacity
                            color: getNodeColor(selectedNode),
                            fontWeight: 600,
                            marginBottom: 12,
                            display: 'inline-block'
                        }}>
                            {selectedNode.type}
                        </span>

                        <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: 8 }}>
                            {Object.entries(selectedNode.properties).map(([key, val]) => {
                                if (key === 'download_url' || key === 'minio_path' || key === 'embedding') return null;
                                return (
                                    <div key={key}>
                                        <strong style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>{key}:</strong>
                                        <div style={{ wordBreak: 'break-word' }}>{String(val)}</div>
                                    </div>
                                );
                            })}
                        </div>

                        {selectedNode.properties.download_url && (
                            <a
                                href={selectedNode.properties.download_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                style={{
                                    marginTop: 16,
                                    display: 'block',
                                    textAlign: 'center',
                                    padding: '8px',
                                    background: 'var(--accent-indigo)',
                                    color: 'white',
                                    borderRadius: 6,
                                    textDecoration: 'none',
                                    fontSize: '0.85rem'
                                }}
                            >
                                Abrir Recurso
                            </a>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}
