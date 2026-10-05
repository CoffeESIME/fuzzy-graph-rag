import VisualizationFrame, { type FigurePreset } from '../graph/VisualizationFrame';
import GraphLegend from '../graph/GraphLegend';
import AssetInspector from '../graph/AssetInspector';
import { nodeColors, canonicalType, shapeFor } from '../graph/visualSystem';
import { useCanvasTheme } from '../../hooks/useCanvasTheme';
import { downloadBlob } from '../graph/figureExport';
import { useCallback, useRef, useState, useEffect } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import type { GraphNode, GraphEdge } from '../../types/search';

interface GraphVisualizer2DProps {
    graphData: { nodes: GraphNode[]; links: GraphEdge[] };
    dimensions: { width: number; height: number };
    onNodeClick: (node: GraphNode) => void;
    onEngineStop?: () => void;
}

export default function GraphVisualizer2D({
    graphData,
    dimensions,
    onNodeClick,
    onEngineStop
}: GraphVisualizer2DProps) {

    const host = useRef<HTMLDivElement>(null);
    const graph = useRef<any>(null);
    const colors = useCanvasTheme(host);
    const [preset, setPreset] = useState<FigurePreset>('screen');
    const [labels, setLabels] = useState(true);
    const [selected, setSelected] = useState<GraphNode | null>(null);
    const [size, setSize] = useState(dimensions);
    useEffect(() => { if (!host.current) return; const observer = new ResizeObserver(entries => { const r = entries[0].contentRect; if (r.width && r.height) setSize({width:r.width,height:r.height}); }); observer.observe(host.current); return () => observer.disconnect(); }, []);
    // --- Callbacks estables para pintado ---

    const getNodeColor = useCallback((node: any) => {
        return nodeColors[canonicalType(node.type)] ?? '#78818c';
    }, []);

    const getNodeVal = useCallback((_node: any) => {
        // Valor constante para simplificar cálculos, el tamaño visual lo controlamos en el canvas
        return 5;
    }, []);

    // Función optimizada para dibujar el nodo
    const nodeCanvasObject = useCallback((node: any, ctx: any, globalScale: number) => {
        const label = node.label;
        const fontSize = 12 / globalScale;
        ctx.font = `${fontSize}px Sans-Serif`;

        // Dibujar Círculo
        const r = Math.sqrt(getNodeVal(node)) * 4;
        ctx.beginPath();
        const shape = shapeFor(canonicalType(node.type));
        if (shape === 'square') ctx.rect(node.x-r, node.y-r, r*2, r*2);
        else if (shape === 'diamond') { ctx.moveTo(node.x,node.y-r*1.4); ctx.lineTo(node.x+r*1.4,node.y); ctx.lineTo(node.x,node.y+r*1.4); ctx.lineTo(node.x-r*1.4,node.y); ctx.closePath(); }
        else ctx.arc(node.x, node.y, r, 0, 2 * Math.PI, false);
        ctx.fillStyle = getNodeColor(node);
        ctx.fill();

        // Dibujar Etiqueta (Solo si el zoom es suficiente para evitar ruido visual)
        if (labels && (globalScale > 1.2 || preset !== 'screen')) {
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillStyle = colors.text;
            // Dibujar texto debajo del nodo
            ctx.fillText(label, node.x, node.y + r + fontSize);
        }
    }, [getNodeColor, getNodeVal, colors.text, labels, preset]);

    // Función crítica para la interacción (Click/Hover)
    const nodePointerAreaPaint = useCallback((node: any, color: string, ctx: any) => {
        const r = Math.sqrt(getNodeVal(node)) * 4;
        ctx.fillStyle = color; // IMPORTANTE: Usar el color de hit-detection provisto
        ctx.beginPath();
        // Área de clic aumentada (+8px) para facilitar la selección
        ctx.arc(node.x, node.y, r + 8, 0, 2 * Math.PI, false);
        ctx.fill();
    }, [getNodeVal]);

    return (
        <VisualizationFrame title="Grafo de búsqueda · Canvas" preset={preset} onPresetChange={setPreset}
            toolbar={<><button onClick={() => graph.current?.zoom(graph.current.zoom()*1.25, 0)}>Zoom +</button><button onClick={() => graph.current?.zoom(graph.current.zoom()/1.25, 0)}>Zoom −</button><button onClick={() => graph.current?.zoomToFit(0, 30)}>Ajustar / centrar</button><label><input type="checkbox" checked={labels} onChange={e => setLabels(e.target.checked)} /> Labels</label><button onClick={() => host.current?.querySelector('canvas')?.toBlob(blob => { if (blob) downloadBlob(blob,'knowledge-canvas.png'); })}>PNG · resolución del canvas</button><span>SVG disponible en vista React Flow</span></>}
            legend={<GraphLegend types={graphData.nodes.map(n => n.type)} kinds={['normal']} weighted />}>
        <div ref={host} className="graph-stage">
        <ForceGraph2D ref={graph}
            width={size.width}
            height={size.height}
            graphData={graphData}

            // Funciones optimizadas
            nodeLabel="label"
            nodeColor={getNodeColor}
            nodeVal={getNodeVal}
            nodeCanvasObject={nodeCanvasObject}
            nodePointerAreaPaint={nodePointerAreaPaint}

            // Configuración de Enlaces
            linkColor={() => colors.edge}
            linkWidth={link => (link as any).weight * 2}

            // Configuración de Motor
            backgroundColor={colors.background}
            cooldownTicks={100} // Detener simulación tras 100 ticks para estabilidad
            onEngineStop={onEngineStop}

            // Interacción
            onNodeClick={(node) => {
                console.log("GraphVisualizer2D Node clicked:", node);
                setSelected(node as GraphNode);
                onNodeClick(node as GraphNode);
            }}
            onNodeHover={(node: any) => {
                const container = document.querySelector('canvas')?.parentElement; // Hacky but works for ForceGraph2D container
                if (container) {
                    container.style.cursor = node ? 'pointer' : 'default';
                }
            }}

            // Dibujado de enlaces personalizado
            linkCanvasObject={(link: any, ctx, globalScale) => {
                const start = link.source;
                const end = link.target;

                if (typeof start !== 'object' || typeof end !== 'object') return;

                ctx.beginPath();
                ctx.moveTo(start.x, start.y);
                ctx.lineTo(end.x, end.y);
                ctx.strokeStyle = colors.edge;
                ctx.lineWidth = (link.weight || 0.5) * 2;
                ctx.stroke();

                // Mostrar tipo de relación al hacer zoom
                if (labels && globalScale > 2.5) {
                    const textPos = {
                        x: start.x + (end.x - start.x) / 2,
                        y: start.y + (end.y - start.y) / 2
                    };
                    const relType = link.type;
                    const fontSize = 10 / globalScale;
                    ctx.font = `${fontSize}px Sans-Serif`;
                    ctx.fillStyle = colors.text;
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'middle';
                    ctx.fillText(relType, textPos.x, textPos.y);
                }
            }}
        />
        {selected && <AssetInspector key={selected.id} id={selected.id} label={selected.label} type={canonicalType(selected.type)} metadata={selected} context={graphData.links.filter(e => (typeof e.source === 'object' ? (e.source as any).id : e.source) === selected.id || (typeof e.target === 'object' ? (e.target as any).id : e.target) === selected.id).map(e => `${e.type} · Peso ${e.weight}`)} onClose={() => setSelected(null)} />}
        </div></VisualizationFrame>
    );
}
