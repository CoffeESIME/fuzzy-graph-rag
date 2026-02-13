import { useState, useRef, useCallback } from 'react';
import { Search, Upload, X } from 'lucide-react';
import { useVisualSigLIPSearch } from '../../hooks/useSearch';
import { useSearchStore } from '../../store/searchStore';
import SearchResults from './SearchResults';

export default function VisualSigLIPTab() {
    const [imageData, setImageData] = useState<string | null>(null);
    const [imageName, setImageName] = useState('');
    const [limit, setLimit] = useState(10);
    const [isDragOver, setIsDragOver] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);
    const mutation = useVisualSigLIPSearch();
    const { results, loading, error } = useSearchStore();

    const handleFile = useCallback((file: File) => {
        if (!file.type.startsWith('image/')) return;
        setImageName(file.name);
        const reader = new FileReader();
        reader.onload = (e) => {
            setImageData(e.target?.result as string);
        };
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
        mutation.mutate({ image: imageData, limit });
    };

    const clearImage = () => {
        setImageData(null);
        setImageName('');
    };

    return (
        <div>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: 20 }}>
                Búsqueda puramente visual usando <strong>SigLIP</strong>.
                Sube o arrastra una imagen para encontrar contenido visualmente similar.
            </p>

            {!imageData ? (
                <div
                    className={`drop-zone ${isDragOver ? 'drag-over' : ''}`}
                    onClick={() => fileInputRef.current?.click()}
                    onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
                    onDragLeave={() => setIsDragOver(false)}
                    onDrop={handleDrop}
                >
                    <Upload size={36} color="var(--text-muted)" style={{ marginBottom: 12 }} />
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
                        Arrastra una imagen aquí o <span style={{ color: 'var(--accent-indigo)', cursor: 'pointer' }}>haz clic para seleccionar</span>
                    </p>
                    <p style={{ color: 'var(--text-muted)', fontSize: '0.75rem', marginTop: 4 }}>
                        PNG, JPG, WebP — máx. 10MB
                    </p>
                    <input
                        ref={fileInputRef}
                        type="file"
                        accept="image/*"
                        hidden
                        onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
                    />
                </div>
            ) : (
                <div style={{
                    display: 'flex', gap: 20, alignItems: 'flex-start',
                    padding: 16, background: 'var(--bg-input)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-lg)',
                }}>
                    <div style={{ position: 'relative' }}>
                        <img
                            src={imageData}
                            alt="Preview"
                            style={{
                                maxWidth: 200, maxHeight: 200,
                                borderRadius: 'var(--radius-md)',
                                objectFit: 'contain',
                            }}
                        />
                        <button
                            onClick={clearImage}
                            style={{
                                position: 'absolute', top: -8, right: -8,
                                width: 24, height: 24, borderRadius: '50%',
                                background: 'var(--accent-rose)', border: 'none',
                                color: 'white', cursor: 'pointer',
                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                            }}
                        >
                            <X size={14} />
                        </button>
                    </div>
                    <div style={{ flex: 1 }}>
                        <p style={{ fontSize: '0.85rem', fontWeight: 600 }}>{imageName}</p>
                        <div style={{ display: 'flex', gap: 10, alignItems: 'flex-end', marginTop: 12 }}>
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
                            <button className="btn-primary" onClick={handleSearch} disabled={loading['visual-siglip']}>
                                <Search size={16} /> Buscar
                            </button>
                        </div>
                    </div>
                </div>
            )}

            <SearchResults
                data={results['visual-siglip'] ?? null}
                loading={loading['visual-siglip'] ?? false}
                error={error['visual-siglip'] ?? null}
            />
        </div>
    );
}
