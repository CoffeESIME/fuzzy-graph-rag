import { useState } from 'react';
import { Search } from 'lucide-react';
import * as SliderPrimitive from '@radix-ui/react-slider';
import { useGraphFuzzySearch } from '../../hooks/useSearch';
import { useSearchStore } from '../../store/searchStore';
import SearchResults from './SearchResults';

export default function GraphFuzzyTab() {
    const [query, setQuery] = useState('');
    const [minConfidence, setMinConfidence] = useState(0.6);
    const mutation = useGraphFuzzySearch();
    const { results, loading, error } = useSearchStore();

    const handleSearch = () => {
        if (!query.trim()) return;
        mutation.mutate({ query: query.trim(), min_confidence: minConfidence });
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter') handleSearch();
    };

    return (
        <div>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: 20 }}>
                Algoritmo de expansión difusa con pesos calibrados.
                Encuentra relaciones aproximadas y conexiones semánticas en el grafo.
            </p>

            <div>
                <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: 4, display: 'block' }}>
                    Consulta
                </label>
                <input
                    className="search-input"
                    type="text"
                    placeholder="Ej: conceptos de física cuántica, impresionismo artístico..."
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyDown={handleKeyDown}
                />
            </div>

            <div style={{ marginTop: 20 }}>
                <label style={{
                    fontSize: '0.8rem', color: 'var(--text-muted)',
                    marginBottom: 8, display: 'flex', justifyContent: 'space-between',
                }}>
                    <span>Confianza mínima</span>
                    <span style={{ color: 'var(--accent-violet)', fontWeight: 600 }}>{minConfidence.toFixed(2)}</span>
                </label>
                <SliderPrimitive.Root
                    className="slider-root"
                    value={[minConfidence]}
                    onValueChange={([v]) => setMinConfidence(v)}
                    min={0} max={1} step={0.05}
                >
                    <SliderPrimitive.Track className="slider-track">
                        <SliderPrimitive.Range className="slider-range" />
                    </SliderPrimitive.Track>
                    <SliderPrimitive.Thumb className="slider-thumb" />
                </SliderPrimitive.Root>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.65rem', color: 'var(--text-muted)', marginTop: 4 }}>
                    <span>0.0 — Muy permisivo</span>
                    <span>1.0 — Muy estricto</span>
                </div>
            </div>

            <div style={{ marginTop: 16 }}>
                <button
                    className="btn-primary"
                    onClick={handleSearch}
                    disabled={!query.trim() || loading['graph-fuzzy']}
                >
                    <Search size={16} /> Buscar Difuso
                </button>
            </div>

            <SearchResults
                data={results['graph-fuzzy'] ?? null}
                loading={loading['graph-fuzzy'] ?? false}
                error={error['graph-fuzzy'] ?? null}
            />
        </div>
    );
}
