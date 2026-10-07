import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import { readSavedPathfinder, routeGroups } from '../../lib/pathfinderRoutes';
import type { PathfinderResponse } from '../../types/pathfinder';

// Curated presentation only: never changes Pathfinder selection or ranking.
// The source export stays in Saved Paths; installations without it show no invented result.
const FEATURED_PATH = 'pathfinder_astr_nomo_ciego_to_abandono_de_lo_superficial_1791347443292.json';
const FEATURED_ROUTES = ['route-1-c39324b8f0ea', 'route-3-bf6db450d548'];

function conceptualBranches(result: PathfinderResponse) {
    const branches = FEATURED_ROUTES.map(id => result.paths?.find(p => p.id === id)?.nodes.filter(n => n.node_type === 'Concept'));
    if (branches.some(p => !p || p.length !== 5)) return null;
    const [a, b] = branches as NonNullable<typeof branches[number]>[];
    if (a[0].id !== b[0].id || a[3].id !== b[3].id || a[4].id !== b[4].id) return null;
    return [a, b];
}

function ConceptualRoutes({ result }: { result: PathfinderResponse }) {
    const branches = conceptualBranches(result)!;
    const [a, b] = branches;
    return <figure className="home-conceptual-routes">
        <figcaption>Vista conceptual de recorridos reales</figcaption>
        <svg viewBox="0 0 380 324" role="img" aria-label={`Dos recorridos desde ${a[0].label}: uno por ${a[1].label} y ${a[2].label}; otro por ${b[1].label} y ${b[2].label}. Ambos pasan por ${a[3].label} hasta ${a[4].label}. Los archivos intermedios están omitidos.`}>
            <g className="home-conceptual-links" fill="none" stroke="currentColor" strokeWidth="1.2" strokeDasharray="3 5">
                <path d="M190 38 C190 64 95 58 95 84 M190 38 C190 64 285 58 285 84 M95 116 V152 M285 116 V152 M95 182 C95 214 190 194 190 222 M285 182 C285 214 190 194 190 222 M190 248 V282" />
            </g>
            <g textAnchor="middle" fill="currentColor">
                <text x="190" y="28" className="home-conceptual-endpoint">{a[0].label}</text>
                <text x="95" y="102">{a[1].label}</text>
                <text x="285" y="94"><tspan x="285">{b[1].label.split(' ').slice(0, -1).join(' ')}</tspan><tspan x="285" dy="18">{b[1].label.split(' ').at(-1)}</tspan></text>
                <text x="95" y="172">{a[2].label}</text>
                <text x="285" y="172">{b[2].label}</text>
                <text x="190" y="240">{a[3].label}</text>
                <text x="190" y="304" className="home-conceptual-endpoint">{a[4].label}</text>
            </g>
        </svg>
        <p>Registros 1 y 3. Cada tramo punteado resume un paso por un archivo; no representa una relación directa entre conceptos.</p>
    </figure>;
}

export default function FeaturedDiscovery() {
    const [result, setResult] = useState<PathfinderResponse | null>(null);
    useEffect(() => {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 5000);
        fetch(`/api/analysis/saved-paths/${FEATURED_PATH}`, { signal: controller.signal })
            .then(response => response.ok ? response.json() : null)
            .then((data: unknown) => {
                const parsed = readSavedPathfinder(data);
                if (!controller.signal.aborted && parsed && conceptualBranches(parsed)) setResult(parsed);
            })
            .catch(() => { /* No substitute corpus or synthetic paths. */ })
            .finally(() => clearTimeout(timeout));
        return () => { controller.abort(); clearTimeout(timeout); };
    }, []);
    return <article className="home-discovery home-discovery-featured home-discovery-canonical">
        <div className="home-discovery-copy">
            <span className="home-eyebrow">PATHFINDER / RECORRIDOS REALES</span>
            <h3>Un origen.<br />Un destino.</h3>
            <p>Distintas formas de atravesar el corpus.</p>
            {result ? <>
                <p className="home-discovery-metadata">{routeGroups(result.paths ?? []).length} recorridos distintos en el resultado guardado</p>
                <p>De la imagen de un astrónomo ciego al abandono de lo superficial. Dos recorridos para abrir, contrastar y volver a sus fuentes.</p>
                <Link className="home-action" to={`/analysis/saved-paths?path=${encodeURIComponent(FEATURED_PATH)}`}>Inspeccionar las rutas completas<ArrowRight size={18} aria-hidden="true" /></Link>
            </> : <>
                <p>El ejemplo curado no está disponible en esta instalación. Elige dos ideas de tu corpus para explorar sus conexiones.</p>
                <Link className="home-action" to="/analysis/pathfinder">Abrir Pathfinder<ArrowRight size={18} aria-hidden="true" /></Link>
            </>}
        </div>
        {result && <ConceptualRoutes result={result} />}
    </article>;
}
