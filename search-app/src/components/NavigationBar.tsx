import { useNavigate, useLocation } from 'react-router-dom';
import { Home, Search, Upload, Activity, Share2, Sun, Moon } from 'lucide-react';
import type { Theme } from '../hooks/useTheme';

interface NavigationBarProps {
    theme: Theme;
    onToggleTheme: () => void;
}

export default function NavigationBar({ theme, onToggleTheme }: NavigationBarProps) {
    const navigate = useNavigate();
    const location = useLocation();

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
            gap: '8px',
            padding: '12px 24px',
            background: 'var(--bg-secondary)',
            borderBottom: '1px solid var(--border-subtle)',
            position: 'sticky',
            top: 0,
            zIndex: 1000,
            boxShadow: 'var(--shadow-panel)',
        }}>
            {/* Nav items */}
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
                            background: isActive ? 'var(--bg-surface)' : 'transparent',
                            color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
                            fontSize: '0.9rem',
                            fontWeight: isActive ? 600 : 500,
                            cursor: 'pointer',
                            transition: 'all 0.2s',
                        }}
                        onMouseEnter={(e) => {
                            if (!isActive) {
                                e.currentTarget.style.background = 'var(--bg-surface)';
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

            {/* Spacer */}
            <div style={{ flex: 1 }} />

            {/* Theme toggle */}
            <button
                onClick={onToggleTheme}
                className="theme-toggle"
                title={theme === 'dark' ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro'}
                aria-label={theme === 'dark' ? 'Activar modo claro' : 'Activar modo oscuro'}
            >
                {theme === 'dark'
                    ? <Sun size={17} />
                    : <Moon size={17} />
                }
            </button>
        </nav>
    );
}
