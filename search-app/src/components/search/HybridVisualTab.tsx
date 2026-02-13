import { useState, useRef, useCallback } from 'react';
import { Search, Upload, X } from 'lucide-react';
import * as SliderPrimitive from '@radix-ui/react-slider';
import { useHybridVisualSearch } from '../../hooks/useSearch';
import { useSearchStore } from '../../store/searchStore';
import SearchResults from './SearchResults';

export default function HybridVisualTab() {
    const [imageData, setImageData] = useState<string | null>(null);
    const [imageName, setImageName] = useState('');
    const [textContext, setTextContext] = useState('');
    const [alpha, setAlpha] = useState(0.5);
    const [limit, setLimit] = useState(10);
    const [isDragOver, setIsDragOver] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);
    const mutation = useHybridVisualSearch();
    const { results, loading, error } = useSearchStore();

    const handleFile = useCallback((file: File) => {
        if (!file.type.startsWith('image/')) return;
        setImageName(file.name);
        const reader = new FileReader();
        reader.onload = (e) => setImageData(e.target?.result as string);
        reader.readAsDataURL(file);
    }, []);

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setIsDragOver(false);
        const file = e.dataTransfer.files[0];
        if (file) handleFile(file);
    }, [handleFile]);

    const handleSearch = () => {
        if (!imageData) return;
        mutation.mutate({ image: imageData, text_context: textContext.trim(), alpha, limit });
    };

    return (
        <div>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: 20 }}>
                Fusión de vectores <strong>SigLIP</strong> (visual) y <strong>BAAI/bge-m3</strong> (texto).
                Usa el slider <em>alpha</em> para controlar el peso entre imagen y texto.
            </p>

            {/* Image area */}
            {!imageData ? (
                <div
                    className={`drop-zone ${isDragOver ? 'drag-over' : ''}`}
                    onClick={() => fileInputRef.current?.click()}
                    onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
                    onDragLeave={() => setIsDragOver(false)}
                    onDrop={handleDrop}
                >
                    <Upload size={32} color="var(--text-muted)" style={{ marginBottom: 8 }} />
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                        Arrastra una imagen o <span style={{ color: 'var(--accent-indigo)' }}>selecciona</span>
                    </p>
                    <input
                        ref={fileInputRef} type="file" accept="image/*" hidden
                        onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
                    />
                </div>
            ) : (
                <div style={{
                    display: 'flex', gap: 16, alignItems: 'center',
                    padding: 12, background: 'var(--bg-input)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-md)',
                }}>
                    <div style={{ position: 'relative' }}>
                        <img src={imageData} alt="Preview" style={{ width: 100, height: 100, borderRadius: 8, objectFit: 'cover' }} />
                        <button onClick={() => { setImageData(null); setImageName(''); }} style={{
                            position: 'absolute', top: -6, right: -6,
                            width: 20, height: 20, borderRadius: '50%',
                            background: 'var(--accent-rose)', border: 'none',
                            color: 'white', cursor: 'pointer', fontSize: 10,
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                        }}>
                            <X size={12} />
                        </button>
                    </div>
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{imageName}</span>
                </div>
            )}

            {/* Text context */}
            <div style={{ marginTop: 16 }}>
                <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: 4, display: 'block' }}>
                    Contexto de texto (opcional)
                </label>
                <input
                    className="search-input"
                    type="text"
                    placeholder="Ej: paisaje nocturno con estrellas..."
                    value={textContext}
                    onChange={(e) => setTextContext(e.target.value)}
                />
            </div>

            {/* Alpha slider + limit + button */}
            <div style={{ display: 'flex', gap: 20, alignItems: 'flex-end', marginTop: 16 }}>
                <div style={{ flex: 1 }}>
                    <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: 8, display: 'flex', justifyContent: 'space-between' }}>
                        <span>Alpha (imagen ↔ texto)</span>
                        <span style={{ color: 'var(--accent-indigo)', fontWeight: 600 }}>{alpha.toFixed(2)}</span>
                    </label>
                    <SliderPrimitive.Root
                        className="slider-root"
                        value={[alpha]}
                        onValueChange={([v]) => setAlpha(v)}
                        min={0} max={1} step={0.05}
                    >
                        <SliderPrimitive.Track className="slider-track">
                            <SliderPrimitive.Range className="slider-range" />
                        </SliderPrimitive.Track>
                        <SliderPrimitive.Thumb className="slider-thumb" />
                    </SliderPrimitive.Root>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.65rem', color: 'var(--text-muted)', marginTop: 4 }}>
                        <span>0.0 — Solo imagen</span>
                        <span>1.0 — Solo texto</span>
                    </div>
                </div>

                <div style={{ width: 80 }}>
                    <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: 4, display: 'block' }}>Límite</label>
                    <input
                        className="search-input"
                        type="number" min={1} max={50}
                        value={limit}
                        onChange={(e) => setLimit(Number(e.target.value))}
                        style={{ textAlign: 'center' }}
                    />
                </div>

                <button className="btn-primary" onClick={handleSearch} disabled={!imageData || loading['hybrid-visual']}>
                    <Search size={16} /> Buscar
                </button>
            </div>

            <SearchResults
                data={results['hybrid-visual'] ?? null}
                loading={loading['hybrid-visual'] ?? false}
                error={error['hybrid-visual'] ?? null}
            />
        </div>
    );
}
