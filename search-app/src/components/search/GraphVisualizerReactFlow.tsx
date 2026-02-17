import { useCallback, useEffect } from 'react';
import ReactFlow, {
    Controls,
    Background,
    useNodesState,
    useEdgesState,
    MarkerType,
    Position,
    type Node,
    type Edge,
} from 'reactflow';
import 'reactflow/dist/style.css';
import dagre from 'dagre';
import type { GraphNode, GraphEdge } from '../../types/search';

interface GraphVisualizerReactFlowProps {
    graphData: { nodes: GraphNode[]; links: GraphEdge[] };
    dimensions: { width: number; height: number };
    onNodeClick: (node: GraphNode) => void;
}

const nodeWidth = 172;
const nodeHeight = 36;

const getLayoutedElements = (nodes: Node[], edges: Edge[], direction = 'LR') => {
    const dagreGraph = new dagre.graphlib.Graph();
    dagreGraph.setDefaultEdgeLabel(() => ({}));

    dagreGraph.setGraph({ rankdir: direction });

    nodes.forEach((node) => {
        dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight });
    });

    edges.forEach((edge) => {
        dagreGraph.setEdge(edge.source, edge.target);
    });

    dagre.layout(dagreGraph);

    nodes.forEach((node) => {
        const nodeWithPosition = dagreGraph.node(node.id);
        node.targetPosition = direction === 'LR' ? Position.Left : Position.Top;
        node.sourcePosition = direction === 'LR' ? Position.Right : Position.Bottom;

        // We are shifting the dagre node position (anchor=center center) to the top left
        // so it matches the React Flow node anchor point (top left).
        node.position = {
            x: nodeWithPosition.x - nodeWidth / 2,
            y: nodeWithPosition.y - nodeHeight / 2,
        };

        return node;
    });

    return { nodes, edges };
};

export default function GraphVisualizerReactFlow({
    graphData,
    onNodeClick
}: GraphVisualizerReactFlowProps) {
    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);

    useEffect(() => {
        if (!graphData.nodes.length) return;

        // Transform GraphNode to ReactFlow Node
        const initialNodes: Node[] = graphData.nodes.map(node => ({
            id: node.id,
            data: { label: node.label, originalNode: node },
            position: { x: 0, y: 0 }, // Laid out by dagre
            type: 'default', // or custom
            style: {
                background: node.type === 'Concept' ? '#8b5cf6' :
                    node.type === 'Person' ? '#f43f5e' :
                        node.type === 'Location' ? '#f59e0b' :
                            node.type === 'Organization' ? '#3b82f6' :
                                node.type === 'Event' ? '#ec4899' :
                                    node.type === 'Project' ? '#14b8a6' :
                                        node.type === 'DigitalAsset' ? '#10b981' : '#64748b',
                color: '#fff',
                border: '1px solid #334155',
                width: 150,
                fontSize: 12
            }
        }));

        const initialEdges: Edge[] = graphData.links.map((link, idx) => ({
            id: `e-${idx}`,
            source: typeof link.source === 'object' ? (link.source as any).id : link.source,
            target: typeof link.target === 'object' ? (link.target as any).id : link.target,
            type: 'smoothstep',
            label: `${link.type} (${link.weight})`, // Show relationship type and weight
            labelStyle: { fill: '#94a3b8', fontSize: 11, fontWeight: 500 },
            labelBgStyle: { fill: '#0f172a', fillOpacity: 0.8, rx: 4, ry: 4 },
            labelBgPadding: [4, 2],
            labelBgBorderRadius: 4,
            animated: true,
            style: { stroke: '#94a3b8' },
            markerEnd: {
                type: MarkerType.ArrowClosed,
                color: '#94a3b8',
            },
        }));

        const layouted = getLayoutedElements(initialNodes, initialEdges);
        setNodes(layouted.nodes);
        setEdges(layouted.edges);

    }, [graphData, setNodes, setEdges]); // Only run when graphData changes deeply

    const onNodeClickCallback = useCallback((_event: React.MouseEvent, node: Node) => {
        if (node.data && node.data.originalNode) {
            onNodeClick(node.data.originalNode);
        }
    }, [onNodeClick]);

    return (
        <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={onNodeClickCallback}
            fitView
            attributionPosition="bottom-right"
        >
            <Controls style={{ fill: '#fff' }} />
            <Background color="#334155" gap={16} />
        </ReactFlow>
    );
}
