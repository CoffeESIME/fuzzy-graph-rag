import { useCallback } from 'react';
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

    // --- Callbacks estables para pintado ---

    const getNodeColor = useCallback((node: any) => {
        if (node.type === 'Concept') return '#8b5cf6'; // Violet
        if (node.type === 'DigitalAsset') return '#10b981'; // Emerald
        return '#64748b'; // Slate
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
        ctx.arc(node.x, node.y, r, 0, 2 * Math.PI, false);
        ctx.fillStyle = getNodeColor(node);
        ctx.fill();

        // Dibujar Etiqueta (Solo si el zoom es suficiente para evitar ruido visual)
        if (globalScale > 1.2) {
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillStyle = 'rgba(255, 255, 255, 0.9)';
            // Dibujar texto debajo del nodo
            ctx.fillText(label, node.x, node.y + r + fontSize);
        }
    }, [getNodeColor, getNodeVal]);

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
        // @ts-ignore - ForceGraph2D types workaround
        <ForceGraph2D
            width={dimensions.width}
            height={dimensions.height}
            graphData={graphData}

            // Funciones optimizadas
            nodeLabel="label"
            nodeColor={getNodeColor}
            nodeVal={getNodeVal}
            nodeCanvasObject={nodeCanvasObject}
            nodePointerAreaPaint={nodePointerAreaPaint}

            // Configuración de Enlaces
            linkColor={() => '#334155'}
            linkWidth={link => (link as any).weight * 2}

            // Configuración de Motor
            backgroundColor="#0f172a"
            cooldownTicks={100} // Detener simulación tras 100 ticks para estabilidad
            onEngineStop={onEngineStop}

            // Interacción
            onNodeClick={(node) => {
                console.log("GraphVisualizer2D Node clicked:", node);
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
                ctx.strokeStyle = '#334155';
                ctx.lineWidth = (link.weight || 0.5) * 2;
                ctx.stroke();

                // Mostrar tipo de relación al hacer zoom
                if (globalScale > 2.5) {
                    const textPos = {
                        x: start.x + (end.x - start.x) / 2,
                        y: start.y + (end.y - start.y) / 2
                    };
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
    );
}
