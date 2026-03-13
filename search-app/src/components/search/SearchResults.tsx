import { useState } from 'react';
import { FileText, BarChart3 } from 'lucide-react';
import type { SearchResponse, MultimodalFusionResponse, GraphCrispResponse, SearchResult } from '../../types/search';
import { useSearchStore } from '../../store/searchStore';
import {
    detectStrategy,
    normalizeScores,
    getMatchTypeBadge,
    getAlphaDominance,
    type NormalizedScore,
} from '../../utils/scoreNormalizer';
import MediaPreview from './MediaPreview';

type AnySearchResponse = SearchResponse | MultimodalFusionResponse | GraphCrispResponse;

/** Returns true only for responses that carry a flat `results` array */
function isSearchResponse(data: AnySearchResponse): data is SearchResponse | GraphCrispResponse {
    return 'results' in data;
}

interface Props {
    data: AnySearchResponse | null;
    loading: boolean;
    error: string | null;
}

export default function SearchResults({ data, loading, error }: Props) {
    const [selectedTextItem, setSelectedTextItem] = useState<SearchResult | null>(null);
    const [hoveredScoreIdx, setHoveredScoreIdx] = useState<number | null>(null);
    const { activeTab } = useSearchStore();

    if (loading) {
        return (
            <div style={{ marginTop: 24 }}>
                {[0, 1, 2].map(i => (
                    <div key={i} className="loading-glow" style={{
                        padding: 16, marginBottom: 10,
                        borderRadius: 'var(--radius-md)',
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
                ))}
            </div>
        );
    }

    if (error) {
        return (
            <div style={{
                marginTop: 24, padding: 16,
                background: 'rgba(244,63,94,0.08)', border: '1px solid rgba(244,63,94,0.3)',
                borderRadius: 'var(--radius-md)', color: 'var(--accent-rose)',
            }}>
                ❌ {error}
            </div>
        );
    }

    if (!data) return null;

    // MultimodalFusionResponse has fused_results, not results[]
    const resultsArray: SearchResult[] = isSearchResponse(data) ? data.results : [];

    if (resultsArray.length === 0) {
        return (
            <div style={{
                marginTop: 24, padding: 20, textAlign: 'center',
                color: 'var(--text-muted)', fontStyle: 'italic',
            }}>
                No se encontraron resultados.
            </div>
        );
    }

    // Normalize scores for the entire batch
    const strategy = detectStrategy(activeTab);
    const rawScores = resultsArray.map(r => r.score);
    const normalized: NormalizedScore[] = normalizeScores(rawScores, strategy);
    const matchBadge = getMatchTypeBadge(activeTab);

    // Alpha dominance indicator (for multimodal)
    // Extract alpha from query label if present (format: "[image] + text")
    const alphaDominance = activeTab === 'hybrid-visual'
        ? getAlphaDominance(0.5) // We don't track alpha in the response, use neutral default
        : null;

    return (
        <div style={{ marginTop: 24 }}>
            {/* Results Header */}
            <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                marginBottom: 16, flexWrap: 'wrap', gap: 8,
            }}>
                <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: 6 }}>
                    <BarChart3 size={14} />
                    <strong>{data.total_results}</strong> resultados
                    {(data as any).spaces_searched?.length > 0 && (
                        <span style={{ color: 'var(--text-muted)' }}>
                            · {((data as any).spaces_searched as string[]).join(', ')}
                        </span>
                    )}
                </span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{
                        display: 'inline-flex', alignItems: 'center', gap: 4,
                        padding: '3px 10px', borderRadius: 12,
                        fontSize: '0.7rem', fontWeight: 600,
                        background: matchBadge.bg,
                        color: matchBadge.color,
                    }}>
                        {matchBadge.icon} {matchBadge.label}
                    </span>
                    {alphaDominance && (
                        <span style={{
                            display: 'inline-flex', alignItems: 'center', gap: 4,
                            padding: '3px 10px', borderRadius: 12,
                            fontSize: '0.65rem', fontWeight: 500,
                            background: 'rgba(245,158,11,0.1)',
                            color: '#f59e0b',
                        }}>
                            {alphaDominance.icon} {alphaDominance.label}
                        </span>
                    )}
                </div>
            </div>

            {/* Result Cards */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {resultsArray.map((item, idx) => {
                    const norm = normalized[idx];

                    const title = String(
                        item.properties.filename ||
                        item.properties.name ||
                        item.properties.title ||
                        item.label ||
                        item.properties.label ||
                        item.properties.id ||
                        item.uuid ||
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
                        'Sin descripción disponible.'
                    ).slice(0, 200);

                    // Tags from properties
                    const tags: string[] = Array.isArray(item.properties.tags) ? item.properties.tags : [];

                    return (
                        <div key={idx} className="result-item">
                            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
                                {/* Space Icon */}
                                <div style={{
                                    width: 36, height: 36,
                                    borderRadius: 'var(--radius-sm)',
                                    background: 'var(--bg-input)',
                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                    flexShrink: 0, fontSize: '1.2rem',
                                }}>
                                    {item.space_icon || <FileText size={18} color="var(--accent-indigo)" />}
                                </div>

                                <div style={{ flex: 1, minWidth: 0 }}>
                                    {/* Title Row */}
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                                        <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>{title}</span>
                                        <span style={{
                                            fontSize: '0.7rem', padding: '2px 8px',
                                            background: 'var(--bg-input)', borderRadius: 12,
                                            color: 'var(--text-muted)',
                                        }}>
                                            {item.space}
                                        </span>
                                        {idx < 3 && strategy !== 'vector' && (
                                            <span style={{
                                                fontSize: '0.6rem', fontWeight: 700,
                                                padding: '1px 6px', borderRadius: 4,
                                                background: 'rgba(16,185,129,0.12)',
                                                color: '#10b981',
                                            }}>
                                                TOP {idx + 1}
                                            </span>
                                        )}
                                    </div>

                                    {/* Relevance Bar + Score */}
                                    <div
                                        style={{ marginTop: 8, position: 'relative' }}
                                        onMouseEnter={() => setHoveredScoreIdx(idx)}
                                        onMouseLeave={() => setHoveredScoreIdx(null)}
                                    >
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                                            {/* Progress Bar */}
                                            <div style={{
                                                flex: 1, height: 6, borderRadius: 3,
                                                background: 'var(--bg-input)',
                                                overflow: 'hidden',
                                            }}>
                                                <div style={{
                                                    width: `${norm.displayPercent}%`,
                                                    height: '100%', borderRadius: 3,
                                                    background: norm.barColor,
                                                    transition: 'width 0.5s ease-out',
                                                }} />
                                            </div>
                                            {/* Percentage Label */}
                                            <span style={{
                                                fontSize: '0.75rem', fontWeight: 600,
                                                color: norm.barColor,
                                                minWidth: 42, textAlign: 'right',
                                                fontVariantNumeric: 'tabular-nums',
                                            }}>
                                                {norm.label}
                                            </span>
                                        </div>

                                        {/* Tooltip */}
                                        {hoveredScoreIdx === idx && (
                                            <div style={{
                                                position: 'absolute', top: -36, left: 0,
                                                padding: '5px 10px', borderRadius: 8,
                                                fontSize: '0.7rem', color: '#e2e8f0',
                                                background: 'rgba(15, 23, 42, 0.95)',
                                                border: '1px solid rgba(100,116,139,0.3)',
                                                whiteSpace: 'nowrap',
                                                pointerEvents: 'none',
                                                zIndex: 10,
                                                boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
                                            }}>
                                                {norm.tooltip}
                                            </div>
                                        )}
                                    </div>

                                    {/* Description */}
                                    <p style={{
                                        marginTop: 6, fontSize: '0.82rem',
                                        color: 'var(--text-secondary)', lineHeight: 1.5,
                                    }}>
                                        {description}{description.length >= 200 ? '...' : ''}
                                    </p>

                                    {/* Tags */}
                                    {tags.length > 0 && (
                                        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginTop: 6 }}>
                                            {tags.slice(0, 5).map((tag, i) => (
                                                <span key={i} style={{
                                                    fontSize: '0.65rem', padding: '1px 6px',
                                                    borderRadius: 6, fontWeight: 500,
                                                    background: 'rgba(99,102,241,0.1)',
                                                    color: 'var(--accent-indigo)',
                                                    border: '1px solid rgba(99,102,241,0.2)',
                                                }}>
                                                    {tag}
                                                </span>
                                            ))}
                                            {tags.length > 5 && (
                                                <span style={{
                                                    fontSize: '0.65rem', padding: '1px 6px',
                                                    color: 'var(--text-muted)',
                                                }}>
                                                    +{tags.length - 5}
                                                </span>
                                            )}
                                        </div>
                                    )}

                                    {/* Audio Specific Metadata */}
                                    {item.space === 'AudioSpace' && (
                                        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 8 }}>
                                            {item.properties.genre && <span className="badge-meta">🎵 {item.properties.genre}</span>}
                                            {item.properties.tempo && <span className="badge-meta">⏱️ {item.properties.tempo}</span>}
                                            {item.properties.audio_type && <span className="badge-meta">💿 {item.properties.audio_type}</span>}
                                            {item.properties.emotion && <span className="badge-meta">😊 {item.properties.emotion}</span>}
                                            {Array.isArray(item.properties.instruments) && item.properties.instruments.length > 0 && (
                                                <span className="badge-meta">🎸 {item.properties.instruments.slice(0, 3).join(', ')}</span>
                                            )}
                                        </div>
                                    )}

                                    {/* Visual Specific Metadata */}
                                    {item.space === 'VisualSpace' && (
                                        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 8 }}>
                                            {item.properties.image_type && <span className="badge-meta">🖼️ {item.properties.image_type}</span>}
                                            {item.properties.art_style && <span className="badge-meta">🎨 {item.properties.art_style}</span>}
                                            {item.properties.visual_mood && <span className="badge-meta">✨ {item.properties.visual_mood}</span>}
                                            {Array.isArray(item.properties.dominant_colors) && item.properties.dominant_colors.map((color: string, i: number) => (
                                                <span key={i} className="badge-meta" style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                                                    <span style={{ width: 10, height: 10, borderRadius: '50%', backgroundColor: color, border: '1px solid var(--border-subtle)' }}></span>
                                                    {color}
                                                </span>
                                            ))}
                                        </div>
                                    )}

                                    {/* Text Specific Metadata & Action */}
                                    {item.space === 'TextSpace' && (
                                        <div style={{ marginTop: 8 }}>
                                            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
                                                {item.properties.document_type && <span className="badge-meta">📄 {item.properties.document_type}</span>}
                                                {item.properties.rhetorical_tone && <span className="badge-meta">🗣️ {item.properties.rhetorical_tone}</span>}
                                            </div>
                                            <button
                                                onClick={() => setSelectedTextItem(item)}
                                                style={{
                                                    background: 'transparent',
                                                    border: '1px solid var(--border-subtle)',
                                                    borderRadius: 'var(--radius-sm)',
                                                    padding: '4px 10px', fontSize: '0.75rem',
                                                    color: 'var(--text-secondary)', cursor: 'pointer',
                                                    display: 'flex', alignItems: 'center', gap: 6,
                                                    transition: 'all 0.2s'
                                                }}
                                                onMouseEnter={e => {
                                                    e.currentTarget.style.borderColor = 'var(--accent-primary)';
                                                    e.currentTarget.style.color = 'var(--accent-primary)';
                                                }}
                                                onMouseLeave={e => {
                                                    e.currentTarget.style.borderColor = 'var(--border-subtle)';
                                                    e.currentTarget.style.color = 'var(--text-secondary)';
                                                }}
                                            >
                                                <FileText size={12} />
                                                Ver contenido completo
                                            </button>
                                        </div>
                                    )}

                                    {/* Memory Specific Metadata & Action */}
                                    {item.space === 'MemorySpace' && (
                                        <div style={{ marginTop: 8 }}>
                                            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
                                                {item.properties.sentiment && <span className="badge-meta">❤️ {item.properties.sentiment}</span>}
                                                {item.properties.emotional_intensity !== undefined && (
                                                    <span className="badge-meta">🔥 Intensidad: {item.properties.emotional_intensity}</span>
                                                )}
                                                {item.properties.connection_type && <span className="badge-meta">🔗 {item.properties.connection_type}</span>}
                                            </div>
                                            <button
                                                onClick={() => setSelectedTextItem(item)}
                                                style={{
                                                    background: 'transparent',
                                                    border: '1px solid var(--border-subtle)',
                                                    borderRadius: 'var(--radius-sm)',
                                                    padding: '4px 10px', fontSize: '0.75rem',
                                                    color: 'var(--text-secondary)', cursor: 'pointer',
                                                    display: 'flex', alignItems: 'center', gap: 6,
                                                    transition: 'all 0.2s'
                                                }}
                                                onMouseEnter={e => {
                                                    e.currentTarget.style.borderColor = 'var(--accent-primary)';
                                                    e.currentTarget.style.color = 'var(--accent-primary)';
                                                }}
                                                onMouseLeave={e => {
                                                    e.currentTarget.style.borderColor = 'var(--border-subtle)';
                                                    e.currentTarget.style.color = 'var(--text-secondary)';
                                                }}
                                            >
                                                <FileText size={12} />
                                                Ver memoria completa
                                            </button>
                                        </div>
                                    )}

                                    <code style={{
                                        display: 'block', marginTop: 8, fontSize: '0.7rem',
                                        color: 'var(--text-muted)', fontFamily: 'monospace',
                                    }}>
                                        UUID: {item.uuid.slice(0, 8)}... | Dist: {item.distance?.toFixed(4) ?? 'N/A'} | Raw: {norm.rawScore.toFixed(6)}
                                    </code>

                                    {/* Media Preview */}
                                    {(item.properties.minio_path || item.properties.download_url) && (
                                        <div style={{ width: '100%', marginTop: 8 }}>
                                            <MediaPreview
                                                path={item.properties.minio_path}
                                                url={item.properties.download_url}
                                            />
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    );
                })}
            </div>

            {/* Text Preview Modal (Inlined for stability) */}
            {selectedTextItem && (
                <div style={{
                    position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
                    backgroundColor: 'rgba(0, 0, 0, 0.7)',
                    backdropFilter: 'blur(4px)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    zIndex: 9999, padding: 20
                }} onClick={() => setSelectedTextItem(null)}>
                    <div style={{
                        backgroundColor: 'var(--bg-card)',
                        border: '1px solid var(--border-subtle)',
                        borderRadius: 'var(--radius-lg)',
                        width: '100%', maxWidth: '700px', maxHeight: '85vh',
                        display: 'flex', flexDirection: 'column',
                        boxShadow: '0 20px 50px rgba(0,0,0,0.5)',
                        animation: 'fadeIn 0.2s ease-out'
                    }} onClick={e => e.stopPropagation()}>

                        {/* Header */}
                        <div style={{
                            padding: '16px 20px', borderBottom: '1px solid var(--border-subtle)',
                            display: 'flex', alignItems: 'center', justifyContent: 'space-between'
                        }}>
                            <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                                {selectedTextItem.properties.filename || 'Detalle'}
                            </h3>
                            <button onClick={() => setSelectedTextItem(null)} style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '1.2rem' }}>
                                ✕
                            </button>
                        </div>

                        {/* Content */}
                        <div style={{
                            padding: '20px', overflowY: 'auto', flex: 1,
                            fontSize: '0.95rem', lineHeight: 1.6, color: 'var(--text-secondary)',
                            whiteSpace: 'pre-wrap', fontFamily: 'var(--font-sans)'
                        }}>
                            {String(
                                selectedTextItem.properties.content ||
                                selectedTextItem.properties.text ||
                                selectedTextItem.properties.transcript ||
                                'Sin contenido disponible.'
                            )}
                        </div>

                        {/* Footer */}
                        <div style={{
                            padding: '12px 20px', borderTop: '1px solid var(--border-subtle)',
                            display: 'flex', justifyContent: 'flex-end',
                        }}>
                            <button onClick={() => setSelectedTextItem(null)} style={{
                                padding: '8px 16px', backgroundColor: 'var(--accent-primary)',
                                color: 'white', border: 'none', borderRadius: 'var(--radius-sm)',
                                fontWeight: 500, cursor: 'pointer'
                            }}>
                                Cerrar
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
