import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Dna, // Communities
    Network, // Bridges (using Network as proxy) -> or ArrowLeftRight
    Combine, // Serendipity? Or Shuffle
    CloudFog, // Fog of War
    Grid3X3, // Heatmap
    CircleDot, // Chord Diagram
    Target, // Radial Tree
    Trophy, // PageRank
    Shapes, // Abstract Concepts
    Unplug, // Orphans
    BarChart3, // Weight Distribution
    Route, // Pathfinder
    ArrowRight,
    Search,
    BrainCircuit,
    FolderOpen
} from 'lucide-react';

const ANALYSIS_TOOLS = [
    { id: 'communities', title: 'Detección de Comunidades', description: 'Clusters semánticos (Louvain)', icon: Dna, color: '#8b5cf6' },
    { id: 'bridges', title: 'Puentes Semánticos', description: 'Nodos conectores y centralidad', icon: Network, color: '#3b82f6' },
    { id: 'serendipity', title: 'Camino de Serendipia', description: 'Rutas extrañas entre nodos', icon: BrainCircuit, color: '#ec4899' },
    { id: 'pathfinder', title: 'Navegador Latente', description: 'Traza el camino entre dos ideas', icon: Route, color: '#06b6d4' },
    { id: 'fog-of-war', title: 'Niebla de Guerra', description: 'Filtrado progresivo por confianza', icon: CloudFog, color: 'var(--text-muted)' },
    { id: 'heatmap', title: 'Matriz de Calor', description: 'Adyacencia de conceptos', icon: Grid3X3, color: '#ef4444' },
    { id: 'chord', title: 'Diagrama de Cuerdas', description: 'Relaciones entre categorías', icon: CircleDot, color: '#f59e0b' },
    { id: 'radial-tree', title: 'Árbol Radial', description: 'Jerarquías desde nodo central', icon: Target, color: '#10b981' },
    { id: 'pagerank', title: 'PageRank', description: 'Influencers del grafo', icon: Trophy, color: '#eab308' },
    { id: 'abstract-concepts', title: 'Conceptos Abstractos', description: 'Alta conectividad, bajo peso', icon: Shapes, color: '#a855f7' },
    { id: 'orphans', title: 'Nodos Huérfanos', description: 'Auditoría de salud del grafo', icon: Unplug, color: '#71717a' },
    { id: 'weight-distribution', title: 'Distribución de Pesos', description: 'Histograma de fuerzas', icon: BarChart3, color: '#06b6d4' },
    { id: 'saved-paths', title: 'Caminos Guardados', description: 'Galería de descubrimientos', icon: FolderOpen, color: '#4f46e5' },
];

export default function AnalysisDashboard() {
    const navigate = useNavigate();

    return (
        <div style={{ padding: '24px 48px', maxWidth: 1400, width: '100%', margin: '0 auto' }}>
            <div style={{ marginBottom: 40, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                    <h1 style={{ fontSize: '2rem', fontWeight: 800, marginBottom: 8, background: 'var(--gradient-primary)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                        System Analysis
                    </h1>
                    <p style={{ color: 'var(--text-secondary)', fontSize: '1.1rem' }}>
                        Métricas avanzadas y visualizaciones del Grafo de Conocimiento Multimodal.
                    </p>
                </div>
                {/* Navigation to Search */}
                <button
                    onClick={() => navigate('/search')}
                    className="btn-secondary"
                    style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 20px', borderRadius: 8 }}
                >
                    <Search size={18} />
                    Ir a Búsqueda
                </button>
            </div>

            <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
                gap: 24
            }}>
                {ANALYSIS_TOOLS.map((tool) => (
                    <div
                        key={tool.id}
                        onClick={() => navigate(`/analysis/${tool.id}`)}
                        className="analysis-card"
                        style={{
                            background: 'var(--bg-secondary)',
                            borderRadius: 12,
                            padding: 24,
                            border: '1px solid var(--border-subtle)',
                            cursor: 'pointer',
                            display: 'flex', flexDirection: 'column', gap: 16,
                            transition: 'all 0.2s ease',
                            position: 'relative', overflow: 'hidden'
                        }}
                    >
                        <div style={{
                            width: 48, height: 48, borderRadius: 10,
                            background: `${tool.color}15`,
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            color: tool.color
                        }}>
                            <tool.icon size={24} />
                        </div>

                        <div>
                            <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: 6 }}>
                                {tool.title}
                            </h3>
                            <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                                {tool.description}
                            </p>
                        </div>

                        <div style={{
                            marginTop: 'auto', paddingTop: 16,
                            display: 'flex', alignItems: 'center', gap: 6,
                            color: tool.color, fontSize: '0.85rem', fontWeight: 600
                        }}>
                            Analizar <ArrowRight size={14} />
                        </div>
                    </div>
                ))}
            </div>

            <style>{`
                .analysis-card:hover {
                    border-color: var(--accent-indigo);
                    transform: translateY(-2px);
                    box-shadow: 0 10px 30px -10px rgba(0,0,0,0.3);
                }
            `}</style>
        </div>
    );
}
