import { useState } from 'react';
import { Search } from 'lucide-react';
import { useSemanticTextSearch } from '../../hooks/useSearch';
import { useSearchStore } from '../../store/searchStore';
import SearchResults from './SearchResults';

export default function SemanticTextTab() {
    const [query, setQuery] = useState('');
    const [limit, setLimit] = useState(10);
    const mutation = useSemanticTextSearch();
    const { results, loading, error } = useSearchStore();

    const handleSearch = () => {
        if (!query.trim()) return;
        mutation.mutate({ query: query.trim(), limit });
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
