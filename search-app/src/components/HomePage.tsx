import { useNavigate } from 'react-router-dom';
import { Search, Activity, Database, Upload, Sparkles } from 'lucide-react';

export default function HomePage() {
    const navigate = useNavigate();

    return (
        <div style={{
            minHeight: '100vh',
            background: 'var(--bg-primary)',
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center',
            padding: 24
        }}>
            <div style={{ textAlign: 'center', marginBottom: 60 }}>
                <div style={{
                    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                    width: 80, height: 80, borderRadius: '50%', background: 'var(--gradient-primary)',
                    marginBottom: 24, boxShadow: '0 0 40px rgba(99, 102, 241, 0.3)'
                }}>
                    <Database size={40} color="white" />
                </div>
                <h1 style={{
                    fontSize: '3rem', fontWeight: 800, marginBottom: 16,
                    background: 'var(--gradient-primary)',
                    WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent'
                }}>
                    Multimodal Graph RAG
                </h1>
                <p style={{ fontSize: '1.2rem', color: 'var(--text-secondary)', maxWidth: 600, margin: '0 auto' }}>
                    Plataforma de recuperación y análisis de conocimiento aumentada por grafos y búsqueda vectorial multimodal.
                </p>
            </div>

            <div style={{
                display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
                gap: 32, width: '100%', maxWidth: 1100
            }}>
                {/* Search Card */}
                <div
                    onClick={() => navigate('/search')}
                    className="home-card"
                    style={{
                        background: 'var(--bg-secondary)', borderRadius: 24, padding: 40,
                        border: '1px solid var(--border-subtle)', cursor: 'pointer',
                        display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center',
                        transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                    }}
                >
                    <div style={{
                        width: 64, height: 64, borderRadius: 16, background: 'rgba(59, 130, 246, 0.1)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 24
                    }}>
                        <Search size={32} className="text-blue-500" />
                    </div>
                    <h2 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: 12 }}>Search & Retrieval</h2>
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem', lineHeight: 1.5 }}>
                        Búsqueda semántica, visual y exploración de grafos. Encuentra información específica y atraviesa conexiones.
                    </p>
                </div>

                {/* Analysis Card */}
                <div
                    onClick={() => navigate('/analysis')}
                    className="home-card"
                    style={{
                        background: 'var(--bg-secondary)', borderRadius: 24, padding: 40,
                        border: '1px solid var(--border-subtle)', cursor: 'pointer',
                        display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center',
                        transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                    }}
                >
                    <div style={{
                        width: 64, height: 64, borderRadius: 16, background: 'rgba(168, 85, 247, 0.1)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 24
                    }}>
                        <Activity size={32} className="text-purple-500" />
                    </div>
                    <h2 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: 12 }}>System Analysis</h2>
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem', lineHeight: 1.5 }}>
                        Detección de comunidades, métricas de centralidad y visualizaciones avanzadas de la estructura del conocimiento.
                    </p>
                </div>

                {/* Ingest & Control Card */}
                <div
                    onClick={() => navigate('/ingest')}
                    className="home-card"
                    style={{
                        background: 'var(--bg-secondary)', borderRadius: 24, padding: 40,
                        border: '1px solid var(--border-subtle)', cursor: 'pointer',
                        display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center',
                        transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                    }}
                >
                    <div style={{
                        width: 64, height: 64, borderRadius: 16, background: 'rgba(234, 179, 8, 0.1)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 24
                    }}>
                        <Upload size={32} className="text-yellow-500" />
                    </div>
                    <h2 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: 12 }}>Ingest & Control</h2>
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem', lineHeight: 1.5 }}>
                        Ingesta de archivos, control de tareas de procesamiento, cola de revisión y generación de nodos.
                    </p>
                </div>

                {/* Enrichment Card */}
                <div
                    onClick={() => navigate('/enrichment')}
                    className="home-card"
                    style={{
                        background: 'var(--bg-secondary)', borderRadius: 24, padding: 40,
                        border: '1px solid var(--border-subtle)', cursor: 'pointer',
                        display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center',
                        transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                    }}
                >
                    <div style={{
                        width: 64, height: 64, borderRadius: 16, background: 'rgba(236, 72, 153, 0.1)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 24
                    }}>
                        <Sparkles size={32} className="text-pink-500" />
                    </div>
                    <h2 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: 12 }}>Graph Enrichment</h2>
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem', lineHeight: 1.5 }}>
                        Descubrimiento automático, deducción de relaciones ocultas y expansión semántica del conocimiento.
                    </p>
                </div>
            </div>

            <div style={{ marginTop: 60, display: 'flex', gap: 24, color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#22c55e' }}></div>
                    Graph: Online
                </span>
                <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#22c55e' }}></div>
                    Vector DB: Online
                </span>
            </div>

            <style>{`
                .home-card:hover {
                    transform: translateY(-8px);
                    box-shadow: 0 20px 40px -10px rgba(0,0,0,0.5);
                    border-color: var(--accent-indigo);
                }
                .text-blue-500 { color: #3b82f6; }
                .text-purple-500 { color: #a855f7; }
                .text-yellow-500 { color: #eab308; }
                .text-pink-500 { color: #ec4899; }
            `}</style>
        </div>
    );
}
