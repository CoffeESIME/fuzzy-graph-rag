import { Link } from 'react-router-dom';
import { ArrowRight, Search, Network, Upload, Sparkles, CircleHelp, Route, FolderOpen, ChevronDown } from 'lucide-react';
import './HomePage.css';
import FeaturedDiscovery from './home/FeaturedDiscovery';

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
                        <p className="home-description">Explora tus archivos a través de asociaciones, analogías y conexiones inesperadas.</p>
                        <p className="home-technical-description">Un experimento de Fuzzy Graph RAG para recorrer el conocimiento más allá de la similitud directa.</p>
                    </div>
                    <div className="home-intro-note"><span>DEL ARCHIVO AL HALLAZGO</span><p>Un espacio para buscar con intención<br />y dejar lugar a lo inesperado.</p></div>
                </div>
                <details className="home-about">
                    <summary><CircleHelp size={18} aria-hidden="true" /><span>Sobre la herramienta</span><ChevronDown size={15} className="home-about-chevron" aria-hidden="true" /></summary>
                    <div className="home-about-content">
                        <section className="home-about-motivation"><h2>¿Por qué una máquina de serendipia?</h2><p>Este proyecto parte de una pregunta: ¿puede un sistema de conocimiento ayudarnos a encontrar relaciones que no sabíamos que estábamos buscando?</p><p>The Associative Engine explora esta pregunta mediante grafos difusos, búsqueda lateral y recorridos explicables entre conceptos, en un corpus de documentos, imágenes, audio y video.</p><blockquote>El sistema no intenta determinar que una analogía sea verdadera; intenta hacerla visible para que una persona pueda evaluarla.</blockquote></section>
                        <section><h2>¿Por dónde empiezo?</h2><p>Si todavía no tienes material, empieza por <Link to="/ingest">incorporar archivos</Link>. Si ya tienes un corpus, busca un tema, conecta dos entidades con Pathfinder o explora un recorrido de Serendipity.</p></section>
                        <section><h2>¿Cómo interpreto un hallazgo?</h2><p>Una conexión es una pista para investigar. Inspecciona el recorrido, vuelve a los archivos de origen y contrasta su contenido. Un peso entre 0 y 1 expresa la fuerza de una relación según el método utilizado; no es una probabilidad de verdad.</p></section>
                        <section className="home-about-ideas"><h2>Ideas detrás del sistema</h2><dl><div><dt>ANALOGÍA</dt><dd>Douglas Hofstadter &amp; Emmanuel Sander<cite>Surfaces and Essences</cite></dd></div><div><dt>PENSAMIENTO POÉTICO</dt><dd>Marcel Danesi<cite>Poetic Logic and the Origins of the Mathematical Imagination</cite></dd></div><div><dt>RELACIONES DIFUSAS</dt><dd>Fuzzy sets / fuzzy graphs<span>Relaciones con distintos grados de fuerza.</span></dd></div></dl></section>
                    </div>
                </details>
            </header>

            <section className="home-exploration" aria-labelledby="home-explore-title">
                <div className="home-section-heading"><h2 id="home-explore-title">Sigue una conexión</h2><span>Recorridos por tu conocimiento</span></div>
                <div className="home-discovery-layout">
                    <FeaturedDiscovery />
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
