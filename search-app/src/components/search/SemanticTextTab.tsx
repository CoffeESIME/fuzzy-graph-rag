import { useState } from 'react';
import { Search } from 'lucide-react';
import { useSemanticTextSearch } from '../../hooks/useSearch';
import { useSearchStore } from '../../store/searchStore';
import SearchResults from './SearchResults';

const SPACES = [
    { id: 'TextSpace', label: 'Texto', icon: '📄' },
    { id: 'VisualSpace', label: 'Visual', icon: '📸' },
    { id: 'AudioSpace', label: 'Audio', icon: '🎵' },
    { id: 'MemorySpace', label: 'Memoria', icon: '🧠' },
];

export default function SemanticTextTab() {
    const [query, setQuery] = useState('');
    const [limit, setLimit] = useState(10);
    const [selectedSpaces, setSelectedSpaces] = useState<string[]>(SPACES.map(s => s.id));
    const mutation = useSemanticTextSearch();
    const { results, loading, error } = useSearchStore();

    const handleSearch = () => {
        if (!query.trim()) return;
        mutation.mutate({
            query: query.trim(),
            limit,
            spaces: selectedSpaces.length > 0 ? selectedSpaces : undefined
        });
    };

    const toggleSpace = (id: string) => {
        setSelectedSpaces(prev =>
            prev.includes(id)
                ? prev.filter(s => s !== id)
                : [...prev, id]
        );
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter') handleSearch();
    };

    return (
        <div>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: 20 }}>
                Búsqueda vectorial estándar usando el modelo <strong>BAAI/bge-m3</strong>.
                Ingresa una consulta de texto para encontrar contenido semánticamente similar.
            </p>

            {/* Space Selection Pills */}
            <div style={{ marginBottom: 16 }}>
                <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: 8, display: 'block' }}>
                    Espacios de búsqueda
                </label>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    {SPACES.map(space => (
                        <button
                            key={space.id}
                            onClick={() => toggleSpace(space.id)}
                            style={{
                                display: 'flex', alignItems: 'center', gap: 6,
                                padding: '6px 12px',
                                borderRadius: 20,
                                fontSize: '0.8rem', fontWeight: 500,
                                cursor: 'pointer',
                                border: '1px solid',
                                borderColor: selectedSpaces.includes(space.id) ? 'var(--accent-indigo)' : 'var(--border-subtle)',
                                background: selectedSpaces.includes(space.id) ? 'rgba(99, 102, 241, 0.15)' : 'var(--bg-input)',
                                color: selectedSpaces.includes(space.id) ? 'var(--accent-indigo)' : 'var(--text-secondary)',
                                transition: 'all 0.2s ease'
                            }}
                        >
                            <span>{space.icon}</span>
                            {space.label}
                        </button>
                    ))}
                </div>
            </div>

            <div style={{ display: 'flex', gap: 10, alignItems: 'flex-end' }}>
                <div style={{ flex: 1 }}>
                    <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: 4, display: 'block' }}>
                        Consulta
                    </label>
                    <input
                        className="search-input"
                        type="text"
                        placeholder="Ej: fotografía nocturna urbana, machine learning, recuerdos..."
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        onKeyDown={handleKeyDown}
                    />
                </div>
                <div style={{ width: 80 }}>
                    <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: 4, display: 'block' }}>
                        Límite
                    </label>
                    <input
                        className="search-input"
                        type="number"
                        min={1}
                        max={50}
                        value={limit}
                        onChange={(e) => setLimit(Number(e.target.value))}
                        style={{ textAlign: 'center' }}
                    />
                </div>
                <button
                    className="btn-primary"
                    onClick={handleSearch}
                    disabled={!query.trim() || loading['semantic-text']}
                >
                    <Search size={16} />
                    Buscar
                </button>
            </div>

            <SearchResults
                data={results['semantic-text'] ?? null}
                loading={loading['semantic-text'] ?? false}
                error={error['semantic-text'] ?? null}
            />
        </div>
    );
}
