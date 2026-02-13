import { Search } from 'lucide-react';
import SearchTabs from './SearchTabs';

export default function SearchPage() {
    return (
        <div style={{
            maxWidth: 960,
            margin: '0 auto',
            padding: '40px 24px',
        }}>
            {/* Header */}
            <div style={{ marginBottom: 32 }}>
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
                            Explora tu grafo de conocimiento con múltiples estrategias de búsqueda
                        </p>
                    </div>
                </div>
            </div>

            {/* Tabs card */}
            <div className="search-card">
                <SearchTabs />
            </div>
        </div>
    );
}
