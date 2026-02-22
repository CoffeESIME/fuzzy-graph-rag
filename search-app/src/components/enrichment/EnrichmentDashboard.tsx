import { Sparkles, ArrowLeft } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export default function EnrichmentDashboard() {
    const navigate = useNavigate();

    return (
        <div style={{
            minHeight: '100vh',
            background: 'var(--bg-primary)',
            color: 'var(--text-primary)',
            padding: 24
        }}>
            <div style={{ maxWidth: 1200, margin: '0 auto' }}>
                <header style={{ marginBottom: 32, display: 'flex', alignItems: 'center', gap: 16 }}>
                    <button
                        onClick={() => navigate('/')}
                        style={{
                            background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)',
                            borderRadius: 'var(--radius-md)', padding: 8, cursor: 'pointer',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            color: 'var(--text-secondary)'
                        }}
                    >
                        <ArrowLeft size={20} />
                    </button>
                    <div>
                        <h1 style={{ fontSize: '2rem', fontWeight: 800, display: 'flex', alignItems: 'center', gap: 12 }}>
                            <Sparkles size={28} className="text-pink-500" />
                            Enriquecimiento de Grafo
                        </h1>
                        <p style={{ color: 'var(--text-secondary)', marginTop: 4 }}>
                            Centro de control para procesos de descubrimiento y expansión semántica automatizada.
                        </p>
                    </div>
                </header>

                <div style={{
                    background: 'var(--bg-secondary)',
                    border: '1px dashed var(--border-subtle)',
                    borderRadius: 16,
                    padding: 60,
                    textAlign: 'center',
                    color: 'var(--text-muted)'
                }}>
                    <Sparkles size={48} style={{ margin: '0 auto 16px', opacity: 0.5 }} />
                    <h2 style={{ fontSize: '1.5rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>Sección en Construcción</h2>
                    <p style={{ maxWidth: 500, margin: '0 auto' }}>
                        Aquí se integrarán las herramientas para lanzar jobs de enriquecimiento, deducción de relaciones ocultas y clustering inteligente sobre el grafo existente.
                    </p>
                </div>
            </div>
            <style>{`
                .text-pink-500 { color: #ec4899; }
            `}</style>
        </div>
    );
}
