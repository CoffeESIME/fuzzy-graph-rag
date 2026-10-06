import { useState } from 'react';
import GraphCanvas from '../graph/GraphCanvas';
import { edgeKey, routeGroups, routeSignature, routeView } from '../../lib/pathfinderRoutes';
import type { PathfinderEdgeData, PathfinderPath, PathfinderResponse } from '../../types/pathfinder';
import './PathfinderRoutes.css';

const modes: Record<string, string> = { direct: 'Coste ponderado', lateral: 'Lateral', topological: 'Topológica' };
const number = (n: number | null | undefined) => n == null ? 'No disponible' : String(n);

function EdgeDetails({ edge }: { edge: PathfinderEdgeData }) {
    return <div className="route-edge-details"><p><strong>{edge.rel_type}</strong> · peso {number(edge.weight)}</p>
        <p>{edge.reasoning || 'Sin justificación registrada.'}</p>
        <dl><dt>ID de relación</dt><dd>{edge.id || 'No conservado'}</dd><dt>Dirección almacenada</dt><dd>{edge.source} → {edge.target}</dd>
            {edge.traversal_source && <><dt>Dirección recorrida</dt><dd>{edge.traversal_source} → {edge.traversal_target}</dd></>}
            <dt>Peso original</dt><dd>{JSON.stringify(edge.raw_weight === undefined ? edge.weight : edge.raw_weight)}</dd><dt>Procedencia disponible</dt><dd><pre>{JSON.stringify(edge.provenance ?? {}, null, 2)}</pre></dd></dl>
    </div>;
}

export default function PathfinderRoutes({ result, onSelectionChange }: { result: PathfinderResponse; onSelectionChange?: (path: PathfinderPath | null) => void }) {
    const [selectedId, setSelectedId] = useState<string | null>(null);
    const [selectedEdge, setSelectedEdge] = useState<PathfinderEdgeData | null>(null);
    const groups = routeGroups(result.paths ?? []);
    const selected = result.paths?.find(p => p.id === selectedId) ?? null;
    const selectedGroup = selected ? groups.find(g => routeSignature(g.path) === routeSignature(selected)) : null;
    const graph = routeView(result, selectedId);
    const choose = (path: PathfinderPath | null) => { setSelectedId(path?.id ?? null); setSelectedEdge(null); onSelectionChange?.(path); };
    const sharedEdges = (path: PathfinderPath) => new Set(path.edges.filter(e => groups.some(g => g.path.id !== path.id && g.path.edges.some(other => edgeKey(other) === edgeKey(e)))).map(edgeKey)).size;
    return <section className="pathfinder-routes" aria-label="Rutas de Pathfinder">
        {groups.length ? <>
            <header><p>{result.paths!.length} resultados originales · {groups.length} secuencias distintas</p><p>Los rangos corresponden al algoritmo. Costes de modos diferentes no comparten escala.</p></header>
            <div className="route-selector" role="group" aria-label="Seleccionar recorrido">
                <button aria-pressed={!selected} onClick={() => choose(null)}>Todas</button>
                {groups.map((g, i) => <button key={g.path.id} aria-pressed={selectedGroup === g} onClick={() => choose(g.path)}><strong>Ruta {i + 1}</strong><span>{g.path.hop_count} saltos · {modes[g.path.mode] ?? g.path.mode}</span>{g.variants.length > 1 && <small>{g.variants.length} variantes de aristas</small>}</button>)}
            </div>
            {groups.length > 1 && <div className="route-comparison"><table><caption>Comparación de recorridos — el peso mínimo es diagnóstico, no probabilidad de verdad.</caption><thead><tr><th>Ruta</th><th>Saltos</th><th>Modo</th><th>Mín. peso</th><th>Coste nativo</th><th>Nodos únicos</th><th>Aristas compartidas</th></tr></thead><tbody>{groups.map((g, i) => <tr key={g.path.id}><th>Ruta {i + 1}</th><td>{g.path.hop_count}</td><td>{modes[g.path.mode] ?? g.path.mode}</td><td>{number(g.path.metrics.min_weight)}{g.path.metrics.missing_weight_count > 0 ? ' (parcial)' : ''}</td><td>{number(g.path.metrics.cost)}</td><td>{new Set(g.path.nodes.map(n => n.id)).size}</td><td>{sharedEdges(g.path)}</td></tr>)}</tbody></table></div>}
            {selected && <div className="route-sequence">
                {selectedGroup && selectedGroup.variants.length > 1 && <label>Variante original <select aria-label="Variante de aristas" value={selected.id} onChange={e => choose(selectedGroup.variants.find(p => p.id === e.target.value)!)}>{selectedGroup.variants.map(p => <option key={p.id} value={p.id}>Registro {p.rank} · coste {number(p.metrics.cost)}</option>)}</select></label>}
                <p>Registro {selected.rank} · {selected.hop_count} saltos · coste nativo {number(selected.metrics.cost)} · mínimo {number(selected.metrics.min_weight)}</p>
                {new Set(selected.nodes.map(n => n.id)).size < selected.nodes.length && <p>Contiene nodos repetidos. Cada aparición se conserva como un paso del recorrido.</p>}
                <ol aria-label="Secuencia ordenada">{selected.nodes.map((n, i) => <li key={i}>{n.label}</li>)}</ol>
                <details><summary>Parámetros y relaciones de esta ruta</summary><pre>{JSON.stringify(selected.parameters, null, 2)}</pre>{selected.edges.map((edge, i) => <details key={i}><summary>Paso {i + 1}: {selected.nodes[i].label} → {selected.nodes[i + 1].label}</summary><EdgeDetails edge={edge} /></details>)}</details>
            </div>}
            {!selected && <p className="route-help">R1, R2… indican pertenencia. Varias etiquetas sobre una arista indican una relación compartida. Se muestra una variante por secuencia; las variantes originales se conservan al exportar y al seleccionar cada ruta.</p>}
        </> : <p className="route-legacy">Grafo legado: este resultado no conserva rutas individuales ni sus parámetros completos. No se ha inferido su orden.</p>}
        <div className="route-canvas"><GraphCanvas key={selectedId ?? 'all'} nodes={graph.nodes} edges={graph.edges} title={selected ? `Pathfinder · Ruta ${groups.indexOf(selectedGroup!) + 1}` : 'Pathfinder · Todas las rutas'} initialLayout={selected ? 'original' : 'horizontal'} onEdgeClick={(_, edge) => setSelectedEdge(edge.data?.raw ?? null)} /></div>
        {selectedEdge && <aside aria-label="Detalle de relación" className="route-inspection"><button onClick={() => setSelectedEdge(null)}>Cerrar relación</button><EdgeDetails edge={selectedEdge} /></aside>}
    </section>;
}
