import { useState } from 'react';
import { Search, SlidersHorizontal } from 'lucide-react';
import { useSemanticTextSearch } from '../../hooks/useSearch';
import { useSearchStore } from '../../store/searchStore';
import SearchResults from './SearchResults';

const SPACES = [
    { id: 'TextSpace', label: 'Texto', icon: '' },
    { id: 'VisualSpace', label: 'Visual', icon: '' },
    { id: 'AudioSpace', label: 'Audio', icon: '' },
    { id: 'MemorySpace', label: 'Memoria', icon: '' },
];

const ALPHA_PRESETS = [
    { value: 0.0, label: 'Keyword', desc: 'Solo BM25' },
    { value: 0.25, label: 'Keyword+', desc: 'Más keywords' },
    { value: 0.5, label: 'Balanceado', desc: 'BM25 + Vector' },
    { value: 0.75, label: 'Semántico+', desc: 'Más vector' },
    { value: 1.0, label: 'Semántico', desc: 'Solo vector' },
];

export default function SemanticTextTab() {
    const [query, setQuery] = useState('');
    const [limit, setLimit] = useState(10);
    const [selectedSpaces, setSelectedSpaces] = useState<string[]>(SPACES.map(s => s.id));
    const [alpha, setAlpha] = useState(0.5);
    const [tagInput, setTagInput] = useState('');
    const [tags, setTags] = useState<string[]>([]);
    const [showAdvanced, setShowAdvanced] = useState(false);

    const mutation = useSemanticTextSearch();
    const { results, loading, error } = useSearchStore();

    const handleSearch = () => {
        if (!query.trim()) return;
        mutation.mutate({
            query: query.trim(),
            limit,
            spaces: selectedSpaces.length > 0 ? selectedSpaces : undefined,
            filters: tags.length > 0 ? tags : undefined,
            alpha,
        });
    };

    const toggleSpace = (id: string) => {
        setSelectedSpaces(prev =>
            prev.includes(id)
                ? prev.filter(s => s !== id)
                : [...prev, id]
        );
    };

    const addTag = () => {
        const newTag = tagInput.trim();
        if (newTag && !tags.includes(newTag)) {
            setTags(prev => [...prev, newTag]);
        }
        setTagInput('');
    };

    const removeTag = (tag: string) => {
        setTags(prev => prev.filter(t => t !== tag));
    };

    const handleTagKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            addTag();
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter') handleSearch();
    };

    const getAlphaLabel = () => {
        const preset = ALPHA_PRESETS.find(p => Math.abs(p.value - alpha) < 0.05);
        return preset ? preset.desc : `α=${alpha.toFixed(2)}`;
    };

    return (
        <div>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: 20 }}>
                Búsqueda <strong>Híbrida</strong>: combina coincidencia de palabras clave (BM25) con similitud vectorial (BGE-M3).
                Usa el slider de <em>alpha</em> para ajustar el balance.
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

            {/* Query + Limit + Search Button */}
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

            {/* Advanced Toggle */}
            <button
                onClick={() => setShowAdvanced(!showAdvanced)}
                style={{
                    display: 'flex', alignItems: 'center', gap: 6,
                    marginTop: 12, padding: '4px 0',
                    background: 'none', border: 'none',
                    color: 'var(--accent-indigo)',
                    fontSize: '0.8rem', cursor: 'pointer',
                    fontWeight: 500,
                }}
            >
                <SlidersHorizontal size={14} />
                {showAdvanced ? 'Ocultar opciones avanzadas' : 'Opciones avanzadas'}
            </button>

            {/* Advanced Options Panel */}
            {showAdvanced && (
                <div style={{
                    marginTop: 12, padding: 16,
                    background: 'var(--bg-card)',
                    borderRadius: 12,
                    border: '1px solid var(--border-subtle)',
                }}>
                    {/* Alpha Slider */}
                    <div style={{ marginBottom: 16 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                            <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                                Alpha (Keyword ↔ Semántico)
                            </label>
                            <span style={{
                                fontSize: '0.75rem', fontWeight: 600,
                                color: 'var(--accent-indigo)',
                                background: 'rgba(99, 102, 241, 0.1)',
                                padding: '2px 8px', borderRadius: 8,
                            }}>
                                {getAlphaLabel()}
                            </span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>BM25</span>
                            <input
                                type="range"
                                min={0}
                                max={1}
                                step={0.05}
                                value={alpha}
                                onChange={(e) => setAlpha(parseFloat(e.target.value))}
                                style={{ flex: 1, accentColor: 'var(--accent-indigo)' }}
                            />
                            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>Vector</span>
                        </div>
                        {/* Preset Buttons */}
                        <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
                            {ALPHA_PRESETS.map(p => (
                                <button
                                    key={p.value}
                                    onClick={() => setAlpha(p.value)}
                                    style={{
                                        padding: '3px 8px', borderRadius: 6,
                                        fontSize: '0.7rem', cursor: 'pointer',
                                        border: '1px solid',
                                        borderColor: Math.abs(alpha - p.value) < 0.05 ? 'var(--accent-indigo)' : 'var(--border-subtle)',
                                        background: Math.abs(alpha - p.value) < 0.05 ? 'rgba(99, 102, 241, 0.15)' : 'transparent',
                                        color: Math.abs(alpha - p.value) < 0.05 ? 'var(--accent-indigo)' : 'var(--text-muted)',
                                        transition: 'all 0.15s ease',
                                    }}
                                >
                                    {p.label}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Tag Filters */}
                    <div>
                        <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: 8, display: 'block' }}>
                            Filtrar por Tags
                        </label>
                        <div style={{ display: 'flex', gap: 8 }}>
                            <input
                                className="search-input"
                                type="text"
                                placeholder="Ej: meme, reflexivo, paisaje..."
                                value={tagInput}
                                onChange={(e) => setTagInput(e.target.value)}
                                onKeyDown={handleTagKeyDown}
                                style={{ flex: 1 }}
                            />
                            <button
                                onClick={addTag}
                                disabled={!tagInput.trim()}
                                style={{
                                    padding: '6px 14px', borderRadius: 8,
                                    fontSize: '0.8rem', cursor: 'pointer',
                                    border: '1px solid var(--border-subtle)',
                                    background: 'var(--bg-input)',
                                    color: 'var(--text-secondary)',
                                }}
                            >
                                + Agregar
                            </button>
                        </div>

                        {/* Tag Pills */}
                        {tags.length > 0 && (
                            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 8 }}>
                                {tags.map(tag => (
                                    <span
                                        key={tag}
                                        style={{
                                            display: 'inline-flex', alignItems: 'center', gap: 4,
                                            padding: '3px 10px', borderRadius: 12,
                                            fontSize: '0.75rem', fontWeight: 500,
                                            background: 'rgba(16, 185, 129, 0.15)',
                                            color: 'var(--accent-emerald, #10b981)',
                                            border: '1px solid rgba(16, 185, 129, 0.3)',
                                        }}
                                    >
                                         {tag}
                                        <button
                                            onClick={() => removeTag(tag)}
                                            style={{
                                                background: 'none', border: 'none',
                                                color: 'inherit', cursor: 'pointer',
                                                padding: '0 2px', fontSize: '0.85rem',
                                                lineHeight: 1,
                                            }}
                                        >
                                            ×
                                        </button>
                                    </span>
                                ))}
                                <button
                                    onClick={() => setTags([])}
                                    style={{
                                        background: 'none', border: 'none',
                                        color: 'var(--text-muted)', cursor: 'pointer',
                                        fontSize: '0.7rem', textDecoration: 'underline',
                                    }}
                                >
                                    Limpiar todos
                                </button>
                            </div>
                        )}
                    </div>
                </div>
            )}

            <SearchResults
                data={results['semantic-text'] ?? null}
                loading={loading['semantic-text'] ?? false}
                error={error['semantic-text'] ?? null}
            />
        </div>
    );
}
