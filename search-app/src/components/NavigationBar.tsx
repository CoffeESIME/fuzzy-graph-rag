import { useNavigate, useLocation } from 'react-router-dom';
import { Home, Search, Upload, Activity, Share2 } from 'lucide-react';

export default function NavigationBar() {
    const navigate = useNavigate();
    const location = useLocation();

    // Do not show navigation bar on the home page itself to keep it clean, 
    // or maybe show it but highlight Home. Let's show it everywhere for consistency.
    const isHome = location.pathname === '/';

    const navItems = [
        { path: '/', label: 'Inicio', icon: <Home size={18} /> },
        { path: '/search', label: 'Búsqueda', icon: <Search size={18} /> },
        { path: '/ingest', label: 'Ingesta', icon: <Upload size={18} /> },
        { path: '/analysis', label: 'Análisis', icon: <Activity size={18} /> },
        { path: '/enrichment', label: 'Enriquecimiento', icon: <Share2 size={18} /> },
    ];

    return (
        <nav style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '8px',
            padding: '12px 24px',
            background: 'var(--bg-secondary)',
            borderBottom: '1px solid var(--border-subtle)',
            position: 'sticky',
            top: 0,
            zIndex: 1000,
            boxShadow: '0 4px 12px rgba(0, 0, 0, 0.1)'
        }}>
            {navItems.map((item) => {
                const isActive = location.pathname === item.path ||
                    (item.path !== '/' && location.pathname.startsWith(item.path));

                return (
                    <button
                        key={item.path}
                        onClick={() => navigate(item.path)}
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '8px',
                            padding: '8px 16px',
                            borderRadius: '8px',
                            border: 'none',
                            background: isActive ? 'var(--bg-tertiary)' : 'transparent',
                            color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
                            fontSize: '0.9rem',
                            fontWeight: isActive ? 600 : 500,
                            cursor: 'pointer',
                            transition: 'all 0.2s',
                        }}
                        onMouseEnter={(e) => {
                            if (!isActive) {
                                e.currentTarget.style.background = 'var(--bg-tertiary)';
                                e.currentTarget.style.color = 'var(--text-primary)';
                            }
                        }}
                        onMouseLeave={(e) => {
                            if (!isActive) {
                                e.currentTarget.style.background = 'transparent';
                                e.currentTarget.style.color = 'var(--text-secondary)';
                            }
                        }}
                    >
                        {item.icon}
                        {item.label}
                    </button>
                );
            })}
        </nav>
    );
}
