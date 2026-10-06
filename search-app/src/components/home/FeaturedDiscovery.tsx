import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';

// Editorial selection from the existing corpus. Fetch the original rather than
// embedding a copy: other installations may not have this saved discovery.
const FEATURED_PATH = 'serendipity_path_1773992550430.json';

interface PathStep {
    id: string;
    name: string;
    type: string;
    weight: number | null;
}

function isSavedDiscovery(value: unknown): value is { tool: string; path: PathStep[] } {
    if (!value || typeof value !== 'object' || !('tool' in value) || value.tool !== 'serendipity_path' || !('path' in value) || !Array.isArray(value.path)) return false;
    return value.path.length >= 2 && value.path.length <= 8 && value.path.every((step: unknown, index: number) => {
        if (!step || typeof step !== 'object') return false;
        const node = step as Partial<PathStep>;
        return typeof node.id === 'string' && typeof node.name === 'string' && node.name.trim().length > 0 && typeof node.type === 'string'
            && (index === 0 || (typeof node.weight === 'number' && Number.isFinite(node.weight) && node.weight >= 0 && node.weight <= 1));
    });
}

const example: PathStep[] = [
    { id: 'city', name: 'CIUDAD', type: 'Concept', weight: null },
    { id: 'streets', name: 'calles', type: 'Concept', weight: null },
    { id: 'veins', name: 'venas', type: 'Concept', weight: null },
    { id: 'circulation', name: 'circulación', type: 'Concept', weight: null },
    { id: 'organism', name: 'ORGANISMO', type: 'Concept', weight: null },
];

function AssociativePath({ path, saved }: { path: PathStep[]; saved: boolean }) {
    const minimum = saved ? Math.min(...path.slice(1).map(step => step.weight!)) : null;
    return (
        <figure className="home-associative-path">
            <figcaption>{saved ? 'RECORRIDO GUARDADO' : 'EJEMPLO CONCEPTUAL · NO ES UN RESULTADO'}</figcaption>
            <ol>{path.map((step, index) => {
                const lateral = saved ? step.weight === minimum : index === 2;
                return <li key={`${index}-${step.id}`}>
                    {index > 0 && <div className="home-path-edge">
                        <svg width="20" height="26" viewBox="0 0 20 26" aria-hidden="true"><path d="M10 0V26" stroke="currentColor" strokeWidth="1.5" strokeDasharray={lateral ? '2 4' : undefined} /></svg>
                        <span>{saved ? `peso ${step.weight!.toFixed(2)}` : lateral ? 'asociación lateral' : ''}</span>
                    </div>}
                    <div className="home-path-step"><svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true" className="home-map-node">{step.type === 'Asset' ? <rect x="2" y="2" width="8" height="8" rx="1" /> : <circle cx="6" cy="6" r="4" />}</svg><span>{step.name}</span></div>
                </li>;
            })}</ol>
            <p className="home-path-key">{saved ? 'Línea punteada: menor peso en este recorrido. Los pesos indican fuerza de relación, no probabilidad de verdad.' : 'Línea continua: relación directa. Punteada: asociación lateral por explorar.'}</p>
        </figure>
    );
}

export default function FeaturedDiscovery() {
    const [path, setPath] = useState<PathStep[] | null>(null);
    useEffect(() => {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 5000);
        fetch(`/api/analysis/saved-paths/${FEATURED_PATH}`, { signal: controller.signal })
            .then(response => response.ok ? response.json() : null)
            .then((data: unknown) => { if (!controller.signal.aborted && isSavedDiscovery(data)) setPath(data.path); })
            .catch(() => { /* The labelled conceptual example also works offline. */ })
            .finally(() => clearTimeout(timeout));
        return () => { controller.abort(); clearTimeout(timeout); };
    }, []);

    return (
        <article className={`home-discovery${path ? ' home-discovery-featured' : ''}`}>
            <div className="home-discovery-copy">
                <span className="home-eyebrow">SERENDIPITY{path ? ' / HALLAZGO' : ''}</span>
                <h3>{path ? <>{path[0].name}<span className="home-discovery-between" aria-label="hacia">→</span>{path[path.length - 1].name}</> : <>Encuentra lo<br />inesperado.</>}</h3>
                {path && <p className="home-discovery-metadata">{path.length - 1} saltos · recorrido del corpus</p>}
                <p>{path ? 'Una asociación para investigar: inspecciona cada vínculo y vuelve a sus fuentes.' : 'Sigue asociaciones más allá de la similitud directa. Cada conexión es una pista para investigar.'}</p>
                <Link className="home-action" to={path ? `/analysis/saved-paths?path=${encodeURIComponent(FEATURED_PATH)}` : '/analysis/serendipity'}>{path ? 'Explorar recorrido' : 'Descubrir un recorrido'}<ArrowRight size={18} aria-hidden="true" /></Link>
                {path && <Link className="home-discovery-more" to="/analysis/serendipity">Buscar otro hallazgo →</Link>}
            </div>
            <AssociativePath path={path ?? example} saved={path !== null} />
        </article>
    );
}
