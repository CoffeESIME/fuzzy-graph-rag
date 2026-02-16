import { useState, useRef, useCallback, useMemo } from 'react';
import { Search, Upload, X, FileText, Eye, Zap } from 'lucide-react';
import * as SliderPrimitive from '@radix-ui/react-slider';
import { useHybridVisualSearch } from '../../hooks/useSearch';
import type { SearchResult } from '../../types/search';
import MediaPreview from './MediaPreview';

/* ─────────────── Helpers ─────────────── */

function getConfidence(score: number) {
    const pct = Math.min(100, Math.max(0, score * 100));
    if (pct >= 75) return { pct, color: '#10b981', label: 'Alta' };
    if (pct >= 45) return { pct, color: '#6366f1', label: 'Media' };
    return { pct, color: '#6b7280', label: 'Baja' };
}

/* ─────────────── Mini Result Card ─────────────── */

function MiniCard({
    item,
    rank,
    isPerfectMatch,
}: {
    item: SearchResult;
    rank: number;
    isPerfectMatch: boolean;
}) {
    const { pct, color } = getConfidence(item.score);

    const title = String(
        item.properties.filename ||
        item.properties.name ||
        item.properties.title ||
        item.properties.ai_summary ||
        'Sin título'
    );

    const description = String(
        item.properties.ai_summary ||
        item.properties.reasoning ||
        item.properties.description ||
        item.properties.text ||
        item.properties.content ||
        item.properties.ocr_text ||
        item.properties.transcript ||
        ''
    ).slice(0, 120);

    return (
        <div style={{
            padding: 12, borderRadius: 10,
            background: 'var(--bg-base)',
            border: isPerfectMatch
                ? '2px solid #f59e0b'
                : '1px solid var(--border-subtle)',
            boxShadow: isPerfectMatch
                ? '0 0 12px rgba(245,158,11,0.15)'
                : 'none',
            transition: 'all 0.2s ease',
            position: 'relative',
        }}>
            {/* Perfect Match badge */}
            {isPerfectMatch && (
                <span style={{
                    position: 'absolute', top: -8, right: 8,
                    display: 'inline-flex', alignItems: 'center', gap: 3,
                    padding: '2px 8px', borderRadius: 8,
                    fontSize: '0.6rem', fontWeight: 700,
                    background: 'rgba(245,158,11,0.15)',
                    color: '#f59e0b',
                    border: '1px solid rgba(245,158,11,0.3)',
                }}>
                    <Zap size={9} /> Perfect Match
                </span>
            )}

            {/* Rank + Title */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                <span style={{
                    width: 22, height: 22, borderRadius: 6,
                    background: rank < 3 ? 'rgba(16,185,129,0.12)' : 'var(--bg-input)',
                    color: rank < 3 ? '#10b981' : 'var(--text-muted)',
                    fontSize: '0.65rem', fontWeight: 700,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    flexShrink: 0,
                }}>
                    {rank + 1}
                </span>
                <span style={{
                    fontSize: '0.82rem', fontWeight: 600,
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    flex: 1,
                }}>
                    {title}
                </span>
                <span style={{
                    fontSize: '0.7rem', padding: '1px 6px',
                    borderRadius: 8, background: 'var(--bg-input)',
                    color: 'var(--text-muted)', flexShrink: 0,
                }}>
                    {item.space_icon || '📄'}
                </span>
            </div>

            {/* Relevance bar */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                <div style={{
                    flex: 1, height: 5, borderRadius: 3,
                    background: 'var(--bg-input)', overflow: 'hidden',
                }}>
                    <div style={{
                        width: `${pct}%`, height: '100%', borderRadius: 3,
                        background: color,
                        transition: 'width 0.4s ease-out',
                    }} />
                </div>
                <span style={{
                    fontSize: '0.7rem', fontWeight: 600,
                    color, minWidth: 38, textAlign: 'right',
                    fontVariantNumeric: 'tabular-nums',
                }}>
                    {pct.toFixed(1)}%
                </span>
            </div>

            {/* Description */}
            {description && (
                <p style={{
                    fontSize: '0.75rem', color: 'var(--text-muted)',
                    lineHeight: 1.4, margin: 0,
                }}>
                    {description}{description.length >= 120 ? '...' : ''}
                </p>
            )}

            {/* Tags */}
            {Array.isArray(item.properties.tags) && item.properties.tags.length > 0 && (
                <div style={{ display: 'flex', gap: 3, flexWrap: 'wrap', marginTop: 6 }}>
                    {item.properties.tags.slice(0, 3).map((tag: string, i: number) => (
                        <span key={i} style={{
                            fontSize: '0.6rem', padding: '1px 5px',
                            borderRadius: 4, background: 'rgba(99,102,241,0.08)',
                            color: 'var(--accent-indigo)',
                        }}>
                            {tag}
                        </span>
                    ))}
                </div>
            )}

            {/* Media Preview */}
            {(item.properties.minio_path || item.properties.download_url) && (
                <div style={{ marginTop: 8 }}>
                    <MediaPreview
                        path={item.properties.minio_path}
                        url={item.properties.download_url}
                    />
                </div>
            )}
        </div>
    );
}

/* ─────────────── Main Component ─────────────── */

export default function HybridVisualTab() {
    const [imageData, setImageData] = useState<string | null>(null);
    const [imageName, setImageName] = useState('');
    const [textContext, setTextContext] = useState('');
    const [alpha, setAlpha] = useState(0.5);
    const [limit, setLimit] = useState(10);
    const [isDragOver, setIsDragOver] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const { mutation, fusionData, fusionLoading, fusionError } = useHybridVisualSearch();

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

    // Cross-reference: UUIDs that appear in BOTH text and visual results
    const crossRefUuids = useMemo(() => {
        if (!fusionData) return new Set<string>();
        const textUuids = new Set(fusionData.text_results.map(r => r.uuid));
        const visualUuids = new Set(fusionData.visual_results.map(r => r.uuid));
        return new Set([...textUuids].filter(id => visualUuids.has(id)));
    }, [fusionData]);

    // Perfect match items: render once in a dedicated section, remove from columns
    const perfectMatchItems = useMemo(() => {
        if (!fusionData || crossRefUuids.size === 0) return [];
        return fusionData.visual_results.filter(r => crossRefUuids.has(r.uuid));
    }, [fusionData, crossRefUuids]);

    // Filtered column lists (without perfect matches)
    const filteredTextResults = useMemo(() => {
        if (!fusionData) return [];
        return fusionData.text_results.filter(r => !crossRefUuids.has(r.uuid));
    }, [fusionData, crossRefUuids]);

    const filteredVisualResults = useMemo(() => {
        if (!fusionData) return [];
        return fusionData.visual_results.filter(r => !crossRefUuids.has(r.uuid));
    }, [fusionData, crossRefUuids]);

    // Alpha-based column opacity
    const textColumnOpacity = alpha <= 0.15 ? 0.3 : 1;
    const visualColumnOpacity = alpha >= 0.85 ? 0.3 : 1;

    // Alpha dominance label
    const getDominanceLabel = () => {
        if (alpha < 0.2) return { icon: '👁️', text: 'Dominancia Visual' };
        if (alpha > 0.8) return { icon: '📝', text: 'Dominancia Textual' };
        return null;
    };
    const dominance = getDominanceLabel();

    return (
        <div>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: 20 }}>
                Fusión <strong>Multimodal</strong>: vectores <em>SigLIP</em> (visual) + <em>BGE-M3</em> (texto).
                Los resultados se muestran en columnas separadas. Los que aparecen en ambas columnas son <strong>🔥 Perfect Match</strong>.
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
                        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <span style={{ color: 'var(--accent-indigo)', fontWeight: 600 }}>{alpha.toFixed(2)}</span>
                            {dominance && (
                                <span style={{
                                    fontSize: '0.65rem', padding: '1px 6px', borderRadius: 6,
                                    background: 'rgba(245,158,11,0.1)', color: '#f59e0b',
                                    fontWeight: 600,
                                }}>
                                    {dominance.icon} {dominance.text}
                                </span>
                            )}
                        </span>
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

                <button className="btn-primary" onClick={handleSearch} disabled={!imageData || fusionLoading}>
                    <Search size={16} /> Buscar
                </button>
            </div>

            {/* Loading */}
            {fusionLoading && (
                <div style={{ marginTop: 24 }}>
                    <div className="loading-glow" style={{
                        padding: 16, borderRadius: 'var(--radius-md)',
                        background: 'var(--bg-card)',
                        border: '1px solid var(--border-subtle)',
                        display: 'flex', alignItems: 'center', gap: 12,
                    }}>
                        <div className="skeleton" style={{ width: 40, height: 40, borderRadius: 8 }} />
                        <div style={{ flex: 1 }}>
                            <div className="skeleton" style={{ height: 14, width: '60%', marginBottom: 8 }} />
                            <div className="skeleton" style={{ height: 10, width: '40%' }} />
                        </div>
                    </div>
                </div>
            )}

            {/* Error */}
            {fusionError && (
                <div style={{
                    marginTop: 24, padding: 16,
                    background: 'rgba(244,63,94,0.08)', border: '1px solid rgba(244,63,94,0.3)',
                    borderRadius: 'var(--radius-md)', color: 'var(--accent-rose)',
                }}>
                    ❌ {fusionError}
                </div>
            )}

            {/* ─── Split View Results ─── */}
            {fusionData && (
                <div style={{ marginTop: 24 }}>
                    {/* Stats bar */}
                    <div style={{
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                        marginBottom: 16, flexWrap: 'wrap', gap: 8,
                    }}>
                        <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                            <strong>{fusionData.total_results}</strong> resultados totales
                            {crossRefUuids.size > 0 && (
                                <span style={{ marginLeft: 8, color: '#f59e0b' }}>
                                    · 🔥 {crossRefUuids.size} coincidencia{crossRefUuids.size > 1 ? 's' : ''} cruzada{crossRefUuids.size > 1 ? 's' : ''}
                                </span>
                            )}
                        </span>
                        <span style={{
                            fontSize: '0.7rem', fontWeight: 600,
                            padding: '3px 10px', borderRadius: 12,
                            background: 'rgba(245,158,11,0.12)', color: '#f59e0b',
                        }}>
                            🔀 Multimodal · α={fusionData.alpha.toFixed(2)}
                        </span>
                    </div>

                    {/* ── Perfect Match Section ── */}
                    {perfectMatchItems.length > 0 && (
                        <div style={{
                            marginBottom: 20, padding: 16,
                            background: 'rgba(245,158,11,0.05)',
                            border: '1px solid rgba(245,158,11,0.25)',
                            borderRadius: 12,
                        }}>
                            <div style={{
                                display: 'flex', alignItems: 'center', gap: 8,
                                marginBottom: 12, paddingBottom: 8,
                                borderBottom: '1px solid rgba(245,158,11,0.2)',
                            }}>
                                <Zap size={16} color="#f59e0b" />
                                <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#f59e0b' }}>
                                    Perfect Match
                                </span>
                                <span style={{
                                    fontSize: '0.65rem', padding: '1px 6px', borderRadius: 6,
                                    background: 'rgba(245,158,11,0.12)', color: '#f59e0b',
                                }}>
                                    Encontrado por texto e imagen
                                </span>
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                                {perfectMatchItems.map((item, idx) => (
                                    <MiniCard
                                        key={item.uuid}
                                        item={item}
                                        rank={idx}
                                        isPerfectMatch={true}
                                    />
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Two-column grid */}
                    <div style={{
                        display: 'grid',
                        gridTemplateColumns: '1fr 1fr',
                        gap: 16,
                    }}>
                        {/* LEFT: Text Results (without perfect matches) */}
                        <div style={{
                            opacity: textColumnOpacity,
                            transition: 'opacity 0.3s ease',
                        }}>
                            <div style={{
                                display: 'flex', alignItems: 'center', gap: 8,
                                marginBottom: 12, paddingBottom: 8,
                                borderBottom: '2px solid rgba(99,102,241,0.3)',
                            }}>
                                <div style={{
                                    width: 28, height: 28, borderRadius: 8,
                                    background: 'rgba(99,102,241,0.12)',
                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                }}>
                                    <FileText size={14} color="#6366f1" />
                                </div>
                                <span style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                                    Contexto Semántico
                                </span>
                                <span style={{
                                    fontSize: '0.65rem', padding: '1px 6px', borderRadius: 6,
                                    background: 'rgba(99,102,241,0.1)', color: '#6366f1',
                                }}>
                                    BGE-M3
                                </span>
                            </div>

                            {filteredTextResults.length === 0 ? (
                                <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontStyle: 'italic', textAlign: 'center', padding: 20 }}>
                                    {textContext.trim() ? 'Sin resultados adicionales de texto.' : 'Escribe un contexto de texto para activar esta columna.'}
                                </p>
                            ) : (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                                    {filteredTextResults.map((item, idx) => (
                                        <MiniCard
                                            key={item.uuid}
                                            item={item}
                                            rank={idx}
                                            isPerfectMatch={false}
                                        />
                                    ))}
                                </div>
                            )}
                        </div>

                        {/* RIGHT: Visual Results (without perfect matches) */}
                        <div style={{
                            opacity: visualColumnOpacity,
                            transition: 'opacity 0.3s ease',
                        }}>
                            <div style={{
                                display: 'flex', alignItems: 'center', gap: 8,
                                marginBottom: 12, paddingBottom: 8,
                                borderBottom: '2px solid rgba(139,92,246,0.3)',
                            }}>
                                <div style={{
                                    width: 28, height: 28, borderRadius: 8,
                                    background: 'rgba(139,92,246,0.12)',
                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                }}>
                                    <Eye size={14} color="#8b5cf6" />
                                </div>
                                <span style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                                    Similitud Visual
                                </span>
                                <span style={{
                                    fontSize: '0.65rem', padding: '1px 6px', borderRadius: 6,
                                    background: 'rgba(139,92,246,0.1)', color: '#8b5cf6',
                                }}>
                                    SigLIP
                                </span>
                            </div>

                            {filteredVisualResults.length === 0 ? (
                                <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontStyle: 'italic', textAlign: 'center', padding: 20 }}>
                                    Sin resultados visuales adicionales.
                                </p>
                            ) : (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                                    {filteredVisualResults.map((item, idx) => (
                                        <MiniCard
                                            key={item.uuid}
                                            item={item}
                                            rank={idx}
                                            isPerfectMatch={false}
                                        />
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
