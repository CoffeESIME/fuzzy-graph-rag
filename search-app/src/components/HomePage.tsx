import { Link } from 'react-router-dom';
import { ArrowRight, Search, Network, Upload, Sparkles, CircleHelp, Route, FolderOpen, ChevronDown } from 'lucide-react';
import './HomePage.css';

const workspace = [
    { to: '/search', icon: Search, title: 'Buscar en el corpus', description: 'Encuentra archivos por su contenido, significado o conexiones.', index: '01' },
    { to: '/analysis', icon: Network, title: 'Observar el grafo', description: 'Explora comunidades, relaciones y la estructura del conocimiento.', index: '02' },
    { to: '/ingest', icon: Upload, title: 'Incorporar archivos', description: 'Añade material al corpus y revisa su procesamiento.', index: '03' },
    { to: '/enrichment', icon: Sparkles, title: 'Enriquecer conexiones', description: 'Revisa las herramientas de expansión y organización del grafo.', index: '04' },
];

export default function HomePage() {
    return (
        <main className="observatory-home">
            <header className="home-intro">
                <div className="home-kicker"><span /> OBSERVATORIO DE CONOCIMIENTO <span className="home-kicker-product">/ Multimodal Graph RAG</span></div>
                <div className="home-intro-layout">
                    <div>
                        <h1>La máquina de <em>serendipia.</em></h1>
                        <p className="home-description">Explora tus archivos, sigue sus conexiones y descubre ideas que no estabas buscando.</p>
                    </div>
                    <div className="home-intro-note"><span>DEL ARCHIVO AL HALLAZGO</span><p>Un espacio para buscar con intención<br />y dejar lugar a lo inesperado.</p></div>
                </div>
                <details className="home-about">
                    <summary><CircleHelp size={18} aria-hidden="true" /><span>Sobre la herramienta</span><ChevronDown size={15} className="home-about-chevron" aria-hidden="true" /></summary>
                    <div className="home-about-content">
                        <section><h2>¿Qué es?</h2><p>Un entorno de exploración de conocimiento que combina búsqueda multimodal y grafos. Permite recorrer las relaciones entre archivos, conceptos y entidades de tu corpus.</p></section>
                        <section><h2>¿Por dónde empiezo?</h2><p>Si todavía no tienes material, empieza por <Link to="/ingest">incorporar archivos</Link>. Si ya tienes un corpus, busca un tema, conecta dos entidades con Pathfinder o explora un recorrido de Serendipity.</p></section>
                        <section><h2>¿Cómo interpreto un hallazgo?</h2><p>Una conexión es una pista para investigar. Inspecciona las relaciones y sus pesos, abre los archivos de origen y contrasta su contenido. Los detalles del método explican los criterios disponibles en cada vista.</p></section>
                    </div>
                </details>
            </header>

            <section className="home-exploration" aria-labelledby="home-explore-title">
                <div className="home-section-heading"><h2 id="home-explore-title">Sigue una conexión</h2><span>Recorridos por tu conocimiento</span></div>
                <div className="home-discovery-layout">
                    <Link to="/analysis/serendipity" className="home-discovery" aria-label="Descubrir un recorrido de Serendipity">
                        <div className="home-discovery-copy"><span className="home-eyebrow"><Sparkles size={15} aria-hidden="true" /> SERENDIPITY</span><h3>Encuentra lo<br />inesperado.</h3><p>Deja que las relaciones del corpus te lleven de una idea a otra.</p><span className="home-action">Descubrir un recorrido <ArrowRight size={18} aria-hidden="true" /></span></div>
                        <svg className="home-connection-map" viewBox="0 0 360 220" aria-hidden="true" focusable="false">
                            <g fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M54 136 158 70 291 110" /><path d="M158 70 210 180 291 110" strokeDasharray="3 6" /><path d="M54 136 210 180" opacity=".35" /></g>
                            <g className="home-map-node"><rect x="42" y="124" width="24" height="24" rx="3" /><circle cx="158" cy="70" r="12" /><path d="m291 95 15 15-15 15-15-15Z" /><circle cx="210" cy="180" r="9" /></g>
                            <g className="home-map-label"><text x="54" y="170" textAnchor="middle">Archivo</text><text x="158" y="42" textAnchor="middle">Concepto</text><text x="291" y="147" textAnchor="middle">Conexión</text></g>
                        </svg>
                    </Link>
                    <div className="home-path-menu">
                        <Link to="/analysis/pathfinder" className="home-path-link"><Route size={21} aria-hidden="true" /><div><h3>Conecta dos ideas</h3><p>Elige un origen y un destino. Explora los caminos que los unen.</p><span>Pathfinder <ArrowRight size={15} aria-hidden="true" /></span></div></Link>
                        <Link to="/analysis/saved-paths" className="home-path-link"><FolderOpen size={21} aria-hidden="true" /><div><h3>Retoma un hallazgo</h3><p>Vuelve a tus caminos guardados y examina sus conexiones.</p><span>Caminos guardados <ArrowRight size={15} aria-hidden="true" /></span></div></Link>
                    </div>
                </div>
            </section>

            <section className="home-workspace" aria-labelledby="home-workspace-title">
                <div className="home-section-heading"><h2 id="home-workspace-title">Tu espacio de trabajo</h2><span>Buscar · observar · ampliar</span></div>
                <div className="home-workspace-menu">{workspace.map(({ to, icon: Icon, title, description, index }) => (
                    <Link to={to} className="home-workspace-link" key={to}><span className="home-menu-index">{index}</span><Icon size={20} aria-hidden="true" /><div><h3>{title}</h3><p>{description}</p></div><ArrowRight size={18} className="home-menu-arrow" aria-hidden="true" /></Link>
                ))}</div>
            </section>
            <footer className="home-footer"><span>Archivos, conceptos y relaciones en un mismo lugar.</span><span>Multimodal Graph RAG</span></footer>
        </main>
    );
}
