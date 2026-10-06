import { useMemo, useRef, useState, useEffect } from 'react';
import ReactFlow, { Background, Handle, Position, type NodeProps, type ReactFlowProps, type ReactFlowInstance } from 'reactflow';
import dagre from 'dagre';
import { ZoomIn, ZoomOut, Scan, RotateCcw, Download, Search } from 'lucide-react';
import VisualizationFrame, { type FigurePreset } from './VisualizationFrame';
import GraphLegend, { TypeGlyph } from './GraphLegend';
import AssetInspector from './AssetInspector';
import { cssColor, edgeVisual, nodeColors, visualNode } from './visualSystem';
import { downloadFigure, graphSvg } from './figureExport';
import 'reactflow/dist/style.css';

function GraphNode({ data, selected, sourcePosition, targetPosition }: NodeProps) {
    return <div className={`knowledge-node ${selected ? 'is-selected' : ''}`} style={{ borderColor: nodeColors[data.visualType] ?? '#78818c' }} title={`${data.visualType}: ${data.visualLabel}`}>
        <Handle type="target" position={targetPosition ?? Position.Left} />
        <span className="entity-type"><TypeGlyph type={data.visualType} />{data.visualType}</span>
        {data.showLabel && <strong>{data.visualLabel}</strong>}
        {data.role && <small>{data.role}</small>}
        <Handle type="source" position={sourcePosition ?? Position.Right} />
    </div>;
}
const nodeTypes = { knowledge: GraphNode };
type Layout = 'original' | 'horizontal' | 'vertical' | 'radial' | 'auto';
export default function GraphCanvas({ title = 'Exploración de conocimiento', initialLayout = 'original', ...props }: ReactFlowProps & { title?: string; initialLayout?: Layout }) {
    const { nodes = [], edges = [] } = props;
    const [layout, setLayout] = useState<Layout>(initialLayout);
    const [preset, setPreset] = useState<FigurePreset>('screen');
    const [labels, setLabels] = useState(true), [weights, setWeights] = useState(true);
    const [selected, setSelected] = useState<string | null>(null);
    const [query, setQuery] = useState('');
    const [positions, setPositions] = useState<Record<string, { x: number; y: number }>>({});
    const [measurements, setMeasurements] = useState<Record<string, { width: number; height: number }>>({});
    const [exportError, setExportError] = useState('');
    const instance = useRef<ReactFlowInstance | null>(null), host = useRef<HTMLDivElement>(null);
    const duration = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 220;
    const graphNodes = useMemo(() => {
        const vertical = layout === 'vertical' || (layout === 'auto' && nodes.length > 10);
        const g = new dagre.graphlib.Graph(); g.setDefaultEdgeLabel(() => ({}));
        g.setGraph({ rankdir: vertical ? 'TB' : 'LR', nodesep: 60, ranksep: 120 });
        const ids = new Map(nodes.map((n, i) => [n.id, `node${i}`]));
        if (layout !== 'original' && layout !== 'radial') {
            nodes.forEach(n => g.setNode(ids.get(n.id)!, { width: 200, height: 90 }));
            edges.forEach(e => { if (ids.has(e.source) && ids.has(e.target)) g.setEdge(ids.get(e.source)!, ids.get(e.target)!); }); dagre.layout(g);
        }
        return nodes.map((node, i) => {
            const visual = visualNode(node);
            let position = node.position;
            if (layout === 'radial') { const radius = Math.max(220, nodes.length * 40), angle = i * 2 * Math.PI / nodes.length; position = { x: radius * Math.cos(angle), y: radius * Math.sin(angle) }; }
            else if (layout !== 'original') { const p = g.node(ids.get(node.id)!); position = { x: p.x - 100, y: p.y - 45 }; }
            return { ...node, ...measurements[node.id], type: 'knowledge', position: positions[node.id] ?? position, style: undefined, selected: node.id === selected,
                sourcePosition: vertical ? Position.Bottom : Position.Right, targetPosition: vertical ? Position.Top : Position.Left,
                data: { ...node.data, visualType: visual.type, visualLabel: visual.label, showLabel: labels, role: node.data.role },
            };
        });
    }, [nodes, edges, layout, labels, selected, positions, measurements]);
    const graphEdges = useMemo(() => edges.map(edge => {
        const v = edgeVisual(edge), highlighted = selected === edge.source || selected === edge.target;
        return { ...edge, animated: false, label: [edge.data?.routeLabel, labels ? v.relation : '', weights && v.weight !== undefined ? String(v.weight) : ''].filter(Boolean).join(' · '),
            style: { ...edge.style, stroke: highlighted ? 'var(--accent)' : 'var(--graph-edge)', strokeWidth: highlighted ? 3.5 : 1.5 + 2 * Math.max(0, Math.min(1, v.weight ?? .5)), strokeDasharray: v.dash, opacity: selected && !highlighted ? .35 : 1 },
            labelStyle: { fill: 'var(--text-primary)', fontSize: preset === 'presentation' ? 14 : 12, fontWeight: 500 }, labelBgStyle: { fill: 'var(--surface)', fillOpacity: .95 },
        };
    }), [edges, labels, weights, selected, preset]);
    const fit = () => instance.current?.fitView({ padding: .22, duration: duration() });
    useEffect(() => {
        if (!host.current) return;
        const observer = new ResizeObserver(() => requestAnimationFrame(() => instance.current?.fitView({ padding: .22 })));
        observer.observe(host.current); return () => observer.disconnect();
    }, []);
    useEffect(() => { const handle = requestAnimationFrame(() => instance.current?.fitView({ padding: .22 })); return () => cancelAnimationFrame(handle); }, [layout, nodes.length]);
    const active = nodes.find(n => n.id === selected), visual = active ? visualNode(active) : null;
    const context = active ? edges.filter(e => e.source === active.id || e.target === active.id).map(e => {
        const other = nodes.find(n => n.id === (e.source === active.id ? e.target : e.source)), v = edgeVisual(e);
        return `${e.source === active.id ? 'Hacia' : 'Desde'} ${other ? visualNode(other).label : e.source === active.id ? e.target : e.source}${v.relation ? ` · ${v.relation}` : ''}${v.weight !== undefined ? ` · Peso ${v.weight}` : ''}`;
    }) : [];
    const exportGraph = async (format: 'svg' | 'png', transparent = false) => {
        if (!host.current) return;
        try { setExportError(''); await downloadFigure(graphSvg(graphNodes, edges, { title, labels, weights, transparent, large: preset === 'presentation', background: cssColor(host.current, '--background'), surface: cssColor(host.current, '--surface'), text: cssColor(host.current, '--text-primary'), line: cssColor(host.current, '--graph-edge') }), format, 'knowledge-figure'); }
        catch (error) { setExportError(error instanceof Error ? error.message : 'No se pudo exportar'); }
    };
    return <VisualizationFrame title={title} preset={preset} onPresetChange={setPreset} legend={<GraphLegend types={nodes.map(n => visualNode(n).type)} kinds={edges.map(e => edgeVisual(e).kind)} weighted={weights && edges.some(e => edgeVisual(e).weight !== undefined)} />}
        toolbar={<><select aria-label="Layout visual" value={layout} onChange={e => { setPositions({}); setLayout(e.target.value as Layout); }}><option value="original">Original</option><option value="horizontal">Horizontal</option><option value="vertical">Vertical</option><option value="radial">Radial</option><option value="auto">Auto</option></select>
            <button aria-label="Acercar" title="Zoom +" onClick={() => instance.current?.zoomIn({ duration: duration() })}><ZoomIn size={16} /></button><button aria-label="Alejar" title="Zoom −" onClick={() => instance.current?.zoomOut({ duration: duration() })}><ZoomOut size={16} /></button>
            <button onClick={fit}><Scan size={16} /> Ajustar / centrar</button><button title="Restablecer layout" aria-label="Restablecer layout" onClick={() => { setPositions({}); setLayout(initialLayout); setSelected(null); requestAnimationFrame(fit); }}><RotateCcw size={16} /></button>
            <label><input type="checkbox" checked={labels} onChange={e => setLabels(e.target.checked)} /> Labels</label><label><input type="checkbox" checked={weights} onChange={e => setWeights(e.target.checked)} /> Pesos</label>
            <form onSubmit={e => { e.preventDefault(); const match = graphNodes.find(n => n.data.visualLabel.toLowerCase().includes(query.toLowerCase())); if (match) { setSelected(match.id); instance.current?.fitView({ nodes: [match], maxZoom: 1.3, duration: duration() }); } }}><input aria-label="Buscar nodo en figura" placeholder="Buscar nodo…" value={query} onChange={e => setQuery(e.target.value)} /><button aria-label="Enfocar nodo" title="Enfocar nodo"><Search size={15} /></button></form>
            <details className="export-menu"><summary><Download size={15} /> Exportar</summary><div><button onClick={() => exportGraph('svg')}>SVG vectorial</button><button onClick={() => exportGraph('png')}>PNG ×3 (máx. 8192 px)</button><button onClick={() => exportGraph('png', true)}>PNG transparente</button></div></details>{exportError && <span role="alert">{exportError}</span>}</>}>
        <div ref={host} className="graph-stage"><ReactFlow {...props} nodes={graphNodes} edges={graphEdges} nodeTypes={nodeTypes} fitView minZoom={.03}
            onInit={value => { instance.current = value; props.onInit?.(value); }}
            onNodesChange={changes => {
                const moved = changes.filter(change => change.type === 'position' && change.position);
                if (moved.length) setPositions(previous => { const next = { ...previous }; moved.forEach(change => { if (change.type === 'position' && change.position) next[change.id] = change.position; }); return next; });
                const resized = changes.filter(change => change.type === 'dimensions' && change.dimensions);
                if (resized.length) setMeasurements(previous => { let changed = false; const next = { ...previous }; resized.forEach(change => { if (change.type === 'dimensions' && change.dimensions && (previous[change.id]?.width !== change.dimensions.width || previous[change.id]?.height !== change.dimensions.height)) { next[change.id] = change.dimensions; changed = true; } }); return changed ? next : previous; });
            }}
            onNodeClick={(event, node) => { setSelected(node.id); const original = nodes.find(n => n.id === node.id); if (original) props.onNodeClick?.(event, original); }}
        ><Background color="var(--border)" gap={24} /></ReactFlow>
        {active && visual && <AssetInspector key={active.id} id={visual.raw.id ?? active.id} label={visual.label} type={visual.type} metadata={visual.raw} context={context} onClose={() => setSelected(null)} />}</div>
    </VisualizationFrame>;
}
