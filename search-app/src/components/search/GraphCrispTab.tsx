import { useState } from 'react';
import { Search } from 'lucide-react';
import { useGraphCrispSearch } from '../../hooks/useSearch';
import { useSearchStore } from '../../store/searchStore';
import SearchResults from './SearchResults';

const ENTITY_OPTIONS = ['Person', 'Concept', 'Location', 'Organization', 'Event', 'DigitalAsset'];

export default function GraphCrispTab() {
    const [query, setQuery] = useState('');
    const [entityTypes, setEntityTypes] = useState<string[]>([]);
    const mutation = useGraphCrispSearch();
    const { results, loading, error } = useSearchStore();

    const toggleEntity = (e: string) => {
        setEntityTypes((prev) =>
            prev.includes(e) ? prev.filter((x) => x !== e) : [...prev, e]
        );
    };

    const handleSearch = () => {
        if (!query.trim()) return;
        mutation.mutate({
            query: query.trim(),
            entity_types: entityTypes.length > 0 ? entityTypes : undefined,
        });
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter') handleSearch();
    };

    return (
        <div>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: 20 }}>
                Búsqueda de relaciones estrictas en <strong>Neo4j</strong>.
                Encuentra entidades y conexiones exactas en el grafo de conocimiento.
            </p>

            <div>
                <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: 4, display: 'block' }}>
                    Consulta
                </label>
                <input
                    className="search-input"
                    type="text"
                    placeholder="Ej: Albert Einstein, Fotografía, React..."
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyDown={handleKeyDown}
                />
            </div>

            <div style={{ marginTop: 16 }}>
                <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: 8, display: 'block' }}>
                    Tipos de entidad (opcional)
                </label>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                    {ENTITY_OPTIONS.map((ent) => (
                        <button
                            key={ent}
                            onClick={() => toggleEntity(ent)}
                            style={{
                                padding: '6px 14px', fontSize: '0.78rem', fontWeight: 500,
                                borderRadius: 20, cursor: 'pointer',
                                border: `1px solid ${entityTypes.includes(ent) ? 'var(--accent-indigo)' : 'var(--border-subtle)'}`,
                                background: entityTypes.includes(ent) ? 'rgba(99,102,241,0.12)' : 'var(--bg-input)',
                                color: entityTypes.includes(ent) ? 'var(--accent-indigo)' : 'var(--text-secondary)',
                                transition: 'all 150ms ease',
                            }}
                        >
                            {ent}
                        </button>
                    ))}
                </div>
            </div>

            <div style={{ marginTop: 16 }}>
                <button
                    className="btn-primary"
                    onClick={handleSearch}
                    disabled={!query.trim() || loading['graph-crisp']}
                >
                    <Search size={16} /> Buscar en Grafo
                </button>
            </div>

            <SearchResults
                data={results['graph-crisp'] ?? null}
                loading={loading['graph-crisp'] ?? false}
                error={error['graph-crisp'] ?? null}
            />
        </div>
    );
}
