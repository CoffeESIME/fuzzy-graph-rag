import { FileText, BarChart3 } from 'lucide-react';
import type { SearchResponse } from '../../types/search';

interface Props {
    data: SearchResponse | null;
    loading: boolean;
    error: string | null;
}

export default function SearchResults({ data, loading, error }: Props) {
    if (loading) {
        return (
            <div style={{ marginTop: 24 }}>
                <div className="loading-glow" style={{
                    padding: 16,
                    borderRadius: 'var(--radius-md)',
                    background: 'var(--bg-card)',
                    border: '1px solid var(--border-subtle)',
                    display: 'flex', alignItems: 'center', gap: 12,
                }}>
                    <div className="skeleton" style={{ width: 40, height: 40 }} />
                    <div style={{ flex: 1 }}>
                        <div className="skeleton" style={{ height: 14, width: '60%', marginBottom: 8 }} />
                        <div className="skeleton" style={{ height: 10, width: '40%' }} />
                    </div>
                </div>
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

    if (data.results.length === 0) {
        return (
            <div style={{
                marginTop: 24, padding: 20, textAlign: 'center',
                color: 'var(--text-muted)', fontStyle: 'italic',
            }}>
                No se encontraron resultados.
            </div>
        );
    }

    return (
        <div style={{ marginTop: 24 }}>
            <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                marginBottom: 16,
            }}>
                <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                    <BarChart3 size={14} style={{ display: 'inline', marginRight: 4 }} />
                    <strong>{data.total_results}</strong> resultados — <em>{data.search_type}</em>
                </span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {data.results.map((item, idx) => {
                    const scoreClass =
                        item.score >= 0.7 ? 'score-high' : item.score >= 0.4 ? 'score-medium' : 'score-low';

                    return (
                        <div key={idx} className="result-item">
                            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
                                <div style={{
                                    width: 36, height: 36,
                                    borderRadius: 'var(--radius-sm)',
                                    background: 'var(--bg-input)',
                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                    flexShrink: 0,
                                }}>
                                    <FileText size={18} color="var(--accent-indigo)" />
                                </div>

                                <div style={{ flex: 1, minWidth: 0 }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                                        <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>
                                            {item.filename}
                                        </span>
                                        <span className={`score-badge ${scoreClass}`}>
                                            {(item.score * 100).toFixed(1)}%
                                        </span>
                                        <span style={{
                                            fontSize: '0.7rem', padding: '2px 8px',
                                            background: 'var(--bg-input)', borderRadius: 12,
                                            color: 'var(--text-muted)',
                                        }}>
                                            {item.space}
                                        </span>
                                    </div>

                                    <p style={{
                                        marginTop: 6, fontSize: '0.82rem',
                                        color: 'var(--text-secondary)', lineHeight: 1.5,
                                    }}>
                                        {item.reasoning}
                                    </p>

                                    <code style={{
                                        display: 'block', marginTop: 8, fontSize: '0.7rem',
                                        color: 'var(--text-muted)', fontFamily: 'monospace',
                                    }}>
                                        UUID: {item.uuid}
                                    </code>
                                </div>
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
