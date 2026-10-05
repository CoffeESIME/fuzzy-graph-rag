import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Construction } from 'lucide-react';

interface AnalysisPlaceholderProps {
    title?: string;
    description?: string;
}

const TOOL_DESCRIPTIONS: Record<string, { title: string; description: string }> = {
    'communities': { title: 'Detección de Comunidades', description: 'Identificación de clusters semánticos usando algoritmos como Louvain o Leiden.' },
    'bridges': { title: 'Puentes Semánticos', description: 'Análisis de nodos conectores y centralidad de intermediación (Betweenness).' },
    'serendipity': { title: 'Camino de Serendipia', description: 'Descubrimiento de rutas no obvias y conexiones débiles entre conceptos distantes.' },
    'fog-of-war': { title: 'Niebla de Guerra', description: 'Visualización progresiva del grafo basada en niveles de confianza (Alpha 0.1-1.0).' },
    'heatmap': { title: 'Matriz de Calor', description: 'Mapa de calor de adyacencia y co-ocurrencia de conceptos.' },
    'chord': { title: 'Diagrama de Cuerdas', description: 'Visualización circular de flujos y relaciones entre categorías principales.' },
    'radial': { title: 'Árbol Radial', description: 'Expansión jerárquica desde un nodo central seleccionado.' },
    'pagerank': { title: 'PageRank de Conceptos', description: 'Ranking de influencia y autoridad de nodos dentro del grafo.' },
    'abstract-concepts': { title: 'Conceptos Abstractos', description: 'Detección de nodos con alta conectividad pero bajo peso específico.' },
    'orphans': { title: 'Nodos Huérfanos', description: 'Auditoría de nodos desconectados o con baja densidad de relaciones.' },
    'weight-distribution': { title: 'Distribución de Pesos', description: 'Histograma de la fuerza de las relaciones en todo el grafo.' },
};

export default function AnalysisPlaceholder(props: AnalysisPlaceholderProps) {
    const { toolId } = useParams<{ toolId: string }>();
    const navigate = useNavigate();

    const info = toolId ? TOOL_DESCRIPTIONS[toolId] : {
        title: props.title || 'Herramienta de Análisis',
        description: props.description || 'Esta herramienta está en desarrollo.'
    };

    return (
        <div style={{ padding: 24, height: '100%', display: 'flex', flexDirection: 'column' }}>
            <button
                onClick={() => navigate('/analysis')}
                style={{
                    display: 'flex', alignItems: 'center', gap: 8,
                    background: 'none', border: 'none', color: 'var(--text-secondary)',
                    cursor: 'pointer', marginBottom: 24, width: 'fit-content'
                }}
            >
                <ArrowLeft size={16} /> Volver al Dashboard
            </button>

            <div style={{
                flex: 1,
                display: 'flex', flexDirection: 'column',
                alignItems: 'center', justifyContent: 'center',
                background: 'var(--bg-secondary)',
                borderRadius: 16, border: '1px solid var(--border-subtle)',
                padding: 40, textAlign: 'center'
            }}>
                <div style={{
                    width: 80, height: 80, borderRadius: '50%',
                    background: 'rgba(245, 158, 11, 0.1)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    marginBottom: 24
                }}>
                    <Construction size={40} color="#f59e0b" />
                </div>

                <h2 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: 12 }}>
                     {info.title}
                </h2>

                <p style={{ maxWidth: 500, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                    Work in Progress. {info.description}
                    <br /><br />
                    Pronto podrás visualizar métricas avanzadas y gráficos interactivos aquí.
                </p>

                <div style={{ marginTop: 32, padding: '12px 24px', background: 'var(--bg-input)', borderRadius: 8, fontFamily: 'monospace', fontSize: '0.8rem' }}>
                    Endpoint: POST /api/analysis/{toolId || 'tool'}
                </div>
            </div>
        </div>
    );
}
