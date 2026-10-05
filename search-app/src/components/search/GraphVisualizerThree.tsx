import { nodeColors, canonicalType } from '../graph/visualSystem';
import { useRef, useEffect, useCallback } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import * as d3 from 'd3-force';
import type { GraphNode, GraphEdge } from '../../types/search';

interface GraphVisualizerThreeProps {
    graphData: { nodes: GraphNode[]; links: GraphEdge[] };
    dimensions: { width: number; height: number };
    onNodeClick: (node: GraphNode) => void;
}

export default function GraphVisualizerThree({
    graphData,
    dimensions,
    onNodeClick
}: GraphVisualizerThreeProps) {
    const mountRef = useRef<HTMLDivElement>(null);
    const sceneRef = useRef<THREE.Scene | null>(null);
    const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
    const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
    const controlsRef = useRef<OrbitControls | null>(null);
    const simulationRef = useRef<d3.Simulation<any, any> | null>(null);
    const requestRef = useRef<number | null>(null);

    // Almacenes de objetos 3D para actualizar posiciones
    const nodeMeshesRef = useRef<Map<string, THREE.Mesh>>(new Map());
    const linkLinesRef = useRef<Map<string, THREE.Line>>(new Map());

    // Interacción
    const raycaster = useRef(new THREE.Raycaster());
    const mouse = useRef(new THREE.Vector2());

    // Inicialización de la escena
    useEffect(() => {
        if (!mountRef.current) return;

        // 1. Scene setup
        const scene = new THREE.Scene();
        scene.background = new THREE.Color(getComputedStyle(document.documentElement).getPropertyValue('--background').trim()); // Mismo fondo que el 2D
        sceneRef.current = scene;

        // 2. Camera setup
        const camera = new THREE.PerspectiveCamera(60, dimensions.width / dimensions.height, 0.1, 2000);
        camera.position.z = 300;
        cameraRef.current = camera;

        // 3. Renderer setup
        const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        renderer.setSize(dimensions.width, dimensions.height);
        renderer.setPixelRatio(window.devicePixelRatio);
        renderer.domElement.style.display = 'block'; // Prevent vertical alignment issues causing infinite resize
        mountRef.current.appendChild(renderer.domElement);
        rendererRef.current = renderer;

        // 4. Controls
        const controls = new OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.dampingFactor = 0.1;
        controlsRef.current = controls;

        // 5. Lights
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
        scene.add(ambientLight);

        const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
        directionalLight.position.set(100, 100, 100);
        scene.add(directionalLight);

        const updateTheme = () => {
            scene.background = new THREE.Color(getComputedStyle(document.documentElement).getPropertyValue('--background').trim());
            linkLinesRef.current.forEach(line => (line.material as THREE.LineBasicMaterial).color.set(getComputedStyle(document.documentElement).getPropertyValue('--graph-edge').trim()));
        };
        const themeObserver = new MutationObserver(updateTheme);
        themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
        // Cleanup
        return () => {
            themeObserver.disconnect();
            if (mountRef.current && renderer.domElement) {
                mountRef.current.removeChild(renderer.domElement);
            }
            if (requestRef.current) {
                cancelAnimationFrame(requestRef.current);
            }
            if (simulationRef.current) {
                simulationRef.current.stop();
            }
            renderer.dispose();
            // Dispose geometries/materials if needed logic expanded
        };
    }, []); // Run only once on mount logic, dimensions handled separately

    // Manejo de redimensionamiento
    useEffect(() => {
        if (cameraRef.current && rendererRef.current) {
            cameraRef.current.aspect = dimensions.width / dimensions.height;
            cameraRef.current.updateProjectionMatrix();
            rendererRef.current.setSize(dimensions.width, dimensions.height);
        }
    }, [dimensions]);

    // Actualización de datos y simulación
    useEffect(() => {
        if (!sceneRef.current) return;

        const scene = sceneRef.current;

        // Limpiar objetos anteriores
        nodeMeshesRef.current.forEach(mesh => scene.remove(mesh));
        linkLinesRef.current.forEach(line => scene.remove(line));
        nodeMeshesRef.current.clear();
        linkLinesRef.current.clear();

        // Crear geometría y material compartidos para optimizar
        const sphereGeo = new THREE.SphereGeometry(1, 16, 16); // Radio base 1, escalaremos
        const lineMaterial = new THREE.LineBasicMaterial({ color: getComputedStyle(document.documentElement).getPropertyValue('--graph-edge').trim(), transparent: true, opacity: 0.6 });

        // Nodos
        graphData.nodes.forEach((node: any) => {
            const color = nodeColors[canonicalType(node.type)] ?? '#78818c';
            const radius = ['Concept','DigitalAsset'].includes(node.type) ? 7 : 5;

            const material = new THREE.MeshLambertMaterial({ color });
            const mesh = new THREE.Mesh(sphereGeo, material);
            mesh.scale.set(radius, radius, radius);

            // Metadata for raycasting
            mesh.userData = { id: node.id, node };

            scene.add(mesh);
            nodeMeshesRef.current.set(node.id, mesh);

            // Inicializar posición random si es nan
            node.x = node.x || (Math.random() - 0.5) * 100;
            node.y = node.y || (Math.random() - 0.5) * 100;
            node.z = node.z || (Math.random() - 0.5) * 100;
        });

        // Enlaces (Edges)
        // D3 Force muta los links reemplazando ids con objetos nodo, necesitamos manejar eso
        // Ojo: Si graphData viene de react-force-graph-2d, ya puede estar mutado.
        // Haremos una copia de links para no romper referencias si se comparten
        const links = graphData.links.map((l: any) => ({ ...l }));

        // Pero d3 necesita referencias a los nodos del array de nodos
        // Map ids to nodes in current nodes array
        const nodeMap = new Map(graphData.nodes.map((n: any) => [n.id, n]));
        const validLinks = links.map((l: any) => {
            // Check if source/target are objects or ids
            const sourceId = typeof l.source === 'object' ? l.source.id : l.source;
            const targetId = typeof l.target === 'object' ? l.target.id : l.target;

            return {
                ...l,
                source: nodeMap.get(sourceId),
                target: nodeMap.get(targetId)
            };
        }).filter(l => l.source && l.target);

        validLinks.forEach((link: any, index) => {
            const geometry = new THREE.BufferGeometry();
            const positions = new Float32Array(6); // 2 puntos * 3 coords
            geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));

            const line = new THREE.Line(geometry, lineMaterial);
            scene.add(line);

            // Usamos un id compuesto o índice como clave
            linkLinesRef.current.set(`link-${index}`, line);

            // Attach line to link object to update easily
            link.__lineObj = line;
        });

        // Configurar simulación D3 en 3D
        if (simulationRef.current) simulationRef.current.stop();

        // Configurar simulación D3 (2D layout renderizado en 3D)
        const simulation = d3.forceSimulation(graphData.nodes as any)
            // .numDimensions(3) // d3-force standard is 2D
            .force('link', d3.forceLink(validLinks).id((d: any) => d.id).distance(50))
            .force('charge', d3.forceManyBody().strength(-100))
            .force('center', d3.forceCenter(0, 0)) // 2D center
            .velocityDecay(0.4); // Más fricción para estabilidad

        simulation.on('tick', () => {
            // Actualizar posiciones de nodos
            graphData.nodes.forEach((node: any) => {
                const mesh = nodeMeshesRef.current.get(node.id);
                if (mesh) {
                    mesh.position.set(node.x, node.y, node.z);
                }
            });

            // Actualizar posiciones de líneas
            validLinks.forEach((link: any) => {
                const line = link.__lineObj;
                if (line) {
                    const positions = line.geometry.attributes.position.array;

                    positions[0] = link.source.x;
                    positions[1] = link.source.y;
                    positions[2] = link.source.z;

                    positions[3] = link.target.x;
                    positions[4] = link.target.y;
                    positions[5] = link.target.z;

                    line.geometry.attributes.position.needsUpdate = true;
                }
            });
        });

        simulationRef.current = simulation;

        // Loop de renderizado
        const animate = () => {
            requestRef.current = requestAnimationFrame(animate);
            if (controlsRef.current) controlsRef.current.update();
            if (rendererRef.current && sceneRef.current && cameraRef.current) {
                rendererRef.current.render(sceneRef.current, cameraRef.current);
            }
        };
        animate();

    }, [graphData]); // Re-init simulation when data changes

    // Click Handler
    const handleClick = useCallback((event: React.MouseEvent) => {
        if (!mountRef.current || !cameraRef.current) return;

        // Calcular posición mouse normalizada (-1 a +1)
        const rect = mountRef.current.getBoundingClientRect();
        mouse.current.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
        mouse.current.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

        // Raycasting
        raycaster.current.setFromCamera(mouse.current, cameraRef.current);
        const intersects = raycaster.current.intersectObjects(Array.from(nodeMeshesRef.current.values()));

        if (intersects.length > 0) {
            // El primer objeto intersectado es el más cercano
            const nodeData = intersects[0].object.userData.node;
            onNodeClick(nodeData);
            console.log("ThreeJS Node Click:", nodeData);
        }
    }, [onNodeClick]);

    return (
        <div
            ref={mountRef}
            onClick={handleClick}
            style={{
                width: '100%',
                height: '100%',
                overflow: 'hidden',
                borderRadius: 12, // Match parent styling
                cursor: 'pointer' // Can refine to only show pointer on hover over nodes later
            }}
        />
    );
}
