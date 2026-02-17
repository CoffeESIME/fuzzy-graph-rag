import { useNavigate } from 'react-router-dom';
import { Search, Home, Activity } from 'lucide-react';
import SearchTabs from './SearchTabs';

export default function SearchPage() {
    const navigate = useNavigate();

    return (
        <div style={{
            maxWidth: 1200, // Increased max width
            margin: '0 auto',
            padding: '24px 24px',
        }}>
            {/* Header + Nav */}
            <div style={{ marginBottom: 32, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <div style={{
                        width: 44, height: 44,
                        borderRadius: 'var(--radius-md)',
                        background: 'var(--gradient-primary)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        boxShadow: '0 4px 16px rgba(99,102,241,0.3)',
                    }}>
                        <Search size={22} color="white" />
                    </div>
                    <div>
                        <h1 style={{
                            fontSize: '1.75rem', fontWeight: 700, letterSpacing: '-0.02em',
                        }}>
                            <span className="text-gradient">Búsqueda</span>
                        </h1>
                        <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginTop: 2 }}>
                            Explora tu grafo de conocimiento
                        </p>
                    </div>
                </div>

                <div style={{ display: 'flex', gap: 12 }}>
                    <button
                        onClick={() => navigate('/')}
                        className="btn-secondary"
                        style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 16px', fontSize: '0.9rem' }}
                        title="Ir al Inicio"
                    >
                        <Home size={16} />
                        <span className="hide-mobile">Inicio</span>
                    </button>
                    <button
                        onClick={() => navigate('/analysis')}
                        className="btn-secondary"
                        style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 16px', fontSize: '0.9rem' }}
                        title="Ir a Análisis"
                    >
                        <Activity size={16} />
                        <span className="hide-mobile">Análisis</span>
                    </button>
                </div>
            </div>

            {/* Tabs card */}
            <div className="search-card">
                <SearchTabs />
            </div>
        </div>
    );
}
