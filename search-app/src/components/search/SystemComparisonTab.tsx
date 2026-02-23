import { useState } from 'react';
import { Search, Box, FileText, Image as ImageIcon } from 'lucide-react';
import { searchSemanticText, searchGraphFuzzy, synthesizeComparison } from '../../lib/api';
import type { GraphCrispResponse, RAGConfig, SynthesizeResponse } from '../../types/search';
import MediaPreview from './MediaPreview';
import TextPreviewModal from './TextPreviewModal';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

// Interface for matched item in the comparison table
interface ComparisonItem {
    id: string;
    label: string;
    type: string;
    vectorScore?: number;
    crispWeight?: number;
    fuzzy07Weight?: number;
    fuzzy05Weight?: number;
    crispData?: any;
    fuzzy07Data?: any;
    fuzzy05Data?: any;
    properties: Record<string, any>;
}

export default function SystemComparisonTab() {
    const [query, setQuery] = useState('');
    const [limit, setLimit] = useState(20);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const [comparisonData, setComparisonData] = useState<ComparisonItem[]>([]);
    const [selectedItem, setSelectedItem] = useState<ComparisonItem | null>(null);
    const [textPreviewOpen, setTextPreviewOpen] = useState(false);

    // Configurable alphas for the fuzzy search
    const [fuzzyHighAlpha, setFuzzyHighAlpha] = useState(0.8);
    const [fuzzyLowAlpha, setFuzzyLowAlpha] = useState(0.6);

    // Configurable seed parameters for the graph semantic extraction
    const [seedAlpha, setSeedAlpha] = useState(0.9);
    const [seedLimit, setSeedLimit] = useState(7);

    // Context arrays for synthesis
    const [vectorData, setVectorData] = useState<any[]>([]);
    const [crispData, setCrispData] = useState<any[]>([]);
    const [normalData, setNormalData] = useState<any[]>([]);
    const [fuzzyData, setFuzzyData] = useState<any[]>([]);

    // RAG Synthesis State
    const [ragConfig, setRagConfig] = useState<RAGConfig>({
        model: 'cloud',
        privacy_mode: false,
        strategy: 'hibrido_total',
        top_n: 5
    });
    const [isSynthesizing, setIsSynthesizing] = useState(false);
    const [synthResponse, setSynthResponse] = useState<SynthesizeResponse | null>(null);

    const handleSearch = async () => {
        if (!query.trim()) return;

        setIsLoading(true);
        setError(null);
        setComparisonData([]);

        try {
            // Fire all 4 requests concurrently
            const [vectorRes, crispRes, fuzzy07Res, fuzzy05Res] = await Promise.all([
                searchSemanticText({ query: query.trim(), limit, alpha: 1.0, spaces: ['TextSpace'] }),
                searchGraphFuzzy({ query: query.trim(), limit, alpha_cut: 0.95, seed_alpha: seedAlpha, seed_limit: seedLimit }) as unknown as Promise<GraphCrispResponse>,
                searchGraphFuzzy({ query: query.trim(), limit, alpha_cut: fuzzyHighAlpha, seed_alpha: seedAlpha, seed_limit: seedLimit }) as unknown as Promise<GraphCrispResponse>,
                searchGraphFuzzy({ query: query.trim(), limit, alpha_cut: fuzzyLowAlpha, seed_alpha: seedAlpha, seed_limit: seedLimit }) as unknown as Promise<GraphCrispResponse>,
            ]);

            // Store raw results for complete RAG Context payload
            setVectorData(vectorRes?.results || []);
            setCrispData(crispRes?.results || []);
            setNormalData(fuzzy07Res?.results || []);
            setFuzzyData(fuzzy05Res?.results || []);

            // Map to aggregate by unique node/asset identifier
            const itemMap = new Map<string, ComparisonItem>();

            // Helper to get or create an item
            const getOrCreateItem = (id: string, label: string, type: string, props: any) => {
                if (!itemMap.has(id)) {
                    itemMap.set(id, {
                        id,
                        label,
                        type,
                        properties: { ...props }
                    });
                } else {
                    const existing = itemMap.get(id)!;
                    // Merge existing properties with new ones safely
                    existing.properties = { ...props, ...existing.properties };
                    // If the existing one is just a GraphNode but the new one is VectorAsset, it might have better text
                    if (!existing.properties.text && props.text) existing.properties.text = props.text;
                    if (!existing.properties.content && props.content) existing.properties.content = props.content;
                }
                return itemMap.get(id)!;
            };

            // 1. Process Vector Results
            if (vectorRes && vectorRes.results) {
                vectorRes.results.forEach((item: any) => {
                    // Prioritize file_hash from properties to match the Graph results identifier
                    const id = item.properties?.file_hash || item.properties?.neo4j_hash || item.properties?.hash || item.uuid || item.properties?.name || 'unknown-vector';
                    const label = item.properties?.name || item.properties?.title || item.filename || id;
                    const compItem = getOrCreateItem(id, label, 'VectorAsset', item.properties);
                    compItem.vectorScore = item.score || item.distance;
                });
            }

            // Helper for Graph Results to ensure we group by file/asset hash/UUID
            const processGraphResult = (res: any, weightKey: 'crispWeight' | 'fuzzy07Weight' | 'fuzzy05Weight', dataKey: 'crispData' | 'fuzzy07Data' | 'fuzzy05Data', fallbackWeight: number) => {
                if (res && res.results) {
                    res.results.forEach((item: any) => {
                        // Graph results generally override uuid = file_hash, but check properties to be completely safe
                        const id = item.properties?.file_hash || item.properties?.neo4j_hash || item.properties?.hash || item.uuid || item.properties?.name || 'unknown-graph';
                        const baseLabel = item.properties?.name || item.properties?.title || item.filename || id;

                        const compItem = getOrCreateItem(id, baseLabel, 'GraphNode', item.properties);
                        compItem[weightKey] = item.score ?? item.distance ?? fallbackWeight;
                        compItem[dataKey] = {
                            matched_concept: item.matched_concept,
                            relation_type: item.relation_type,
                            distance: item.distance
                        };

                        // Store matched concept in properties to show importance/context
                        if (item.matched_concept) {
                            if (!compItem.properties.matched_concepts) {
                                compItem.properties.matched_concepts = [];
                            }
                            if (!compItem.properties.matched_concepts.includes(item.matched_concept)) {
                                compItem.properties.matched_concepts.push(item.matched_concept);
                            }
                        }
                    });
                }
            };

            // 2. Process Crisp Results
            processGraphResult(crispRes, 'crispWeight', 'crispData', 1.0);

            // 3. Process Fuzzy High Alpha Results
            processGraphResult(fuzzy07Res, 'fuzzy07Weight', 'fuzzy07Data', fuzzyHighAlpha);

            // 4. Process Fuzzy Low Alpha Results
            processGraphResult(fuzzy05Res, 'fuzzy05Weight', 'fuzzy05Data', fuzzyLowAlpha);

            // Convert map to array and sort by number of occurrences (most found system first), then score
            const aggregated = Array.from(itemMap.values());
            aggregated.sort((a, b) => {
                const countA = (a.vectorScore !== undefined ? 1 : 0) + (a.crispWeight !== undefined ? 1 : 0) + (a.fuzzy07Weight !== undefined ? 1 : 0) + (a.fuzzy05Weight !== undefined ? 1 : 0);
                const countB = (b.vectorScore !== undefined ? 1 : 0) + (b.crispWeight !== undefined ? 1 : 0) + (b.fuzzy07Weight !== undefined ? 1 : 0) + (b.fuzzy05Weight !== undefined ? 1 : 0);
                if (countB !== countA) return countB - countA;
                return (b.vectorScore || 0) - (a.vectorScore || 0); // fallback sort
            });

            setComparisonData(aggregated);

            // Auto-select first item if available
            if (aggregated.length > 0) {
                setSelectedItem(aggregated[0]);
            } else {
                setSelectedItem(null);
            }

        } catch (err: any) {
            console.error("Comparison search error:", err);
            setError(err.message || 'Error executing comparison searches');
        } finally {
            setIsLoading(false);
        }
    };

    const handleSynthesize = async () => {
        if (!query.trim() || comparisonData.length === 0) return;
        setIsSynthesizing(true);
        setSynthResponse(null);
        setError(null);
        try {
            const res = await synthesizeComparison({
                query: query.trim(),
                config: ragConfig,
                vector_results: vectorData,
                crisp_results: crispData,
                normal_results: normalData,
                fuzzy_results: fuzzyData
            });
            setSynthResponse(res);
        } catch (err: any) {
            console.error("Synthesis failed:", err);
            setError(err.response?.data?.detail || err.message || "Failed to synthesize comparison");
        } finally {
            setIsSynthesizing(false);
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter') handleSearch();
    };

    return (
        <div style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 16, overflow: 'hidden' }}>
            {/* Controls */}
            <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end', flexWrap: 'wrap' }}>
                <div style={{ flex: 1, minWidth: 200 }}>
                    <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>
                        Búsqueda Comparativa Multinivel
                    </label>
                    <input
                        className="search-input"
                        type="text"
                        placeholder="Ej: 'Documentos sobre válvulas'..."
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        onKeyDown={handleKeyDown}
                    />
                </div>

                <div style={{ width: 80 }}>
                    <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>
                        Fuzzy Alpha Alto
                    </label>
                    <input
                        className="search-input"
                        type="number"
                        step="0.1"
                        min={0} max={1}
                        value={fuzzyHighAlpha}
                        onChange={(e) => setFuzzyHighAlpha(parseFloat(e.target.value))}
                        style={{ textAlign: 'center' }}
                    />
                </div>

                <div style={{ width: 80 }}>
                    <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>
                        Fuzzy Alpha Bajo
                    </label>
                    <input
                        className="search-input"
                        type="number"
                        step="0.1"
                        min={0} max={1}
                        value={fuzzyLowAlpha}
                        onChange={(e) => setFuzzyLowAlpha(parseFloat(e.target.value))}
                        style={{ textAlign: 'center' }}
                    />
                </div>

                <div style={{ width: 80 }}>
                    <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>
                        Límite/Req
                    </label>
                    <input
                        className="search-input"
                        type="number"
                        min={1} max={100}
                        value={limit}
                        onChange={(e) => setLimit(parseInt(e.target.value))}
                        style={{ textAlign: 'center' }}
                    />
                </div>

                {/* Seed Config Controls */}
                <div style={{ paddingLeft: '8px', borderLeft: '1px solid var(--border-subtle)', display: 'flex', gap: 12 }}>
                    <div style={{ width: 80 }}>
                        <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'block', marginBottom: 4 }} title="¿Cuántos documentos tomar de Weaviate como punto de inicio?">
                            # Semillas
                        </label>
                        <input
                            className="search-input"
                            type="number"
                            min={1} max={50}
                            value={seedLimit}
                            onChange={(e) => setSeedLimit(parseInt(e.target.value))}
                            style={{ textAlign: 'center' }}
                        />
                    </div>

                    <div style={{ width: 85 }}>
                        <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'block', marginBottom: 4 }} title="Peso Vectorial vs Keywords para buscar las semillas">
                            Seed Alpha
                        </label>
                        <input
                            className="search-input"
                            type="number"
                            step="0.05"
                            min={0} max={1}
                            value={seedAlpha}
                            onChange={(e) => setSeedAlpha(parseFloat(e.target.value))}
                            style={{ textAlign: 'center' }}
                        />
                    </div>
                </div>

                <button
                    className="btn-primary"
                    onClick={handleSearch}
                    disabled={!query.trim() || isLoading}
                >
                    <Search size={16} />
                    Comparar
                </button>
            </div>

            {error && (
                <div style={{ padding: 12, background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', borderRadius: 6, border: '1px solid #ef4444' }}>
                    {error}
                </div>
            )}

            {/* Scrollable Layout for Content and RAG Panel */}
            <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 16, paddingRight: 4, paddingBottom: 16 }}>

                {/* Table Area (Scrollable internally but maintains a good height) */}
                <div style={{ flex: '1 0 350px', minHeight: 650, overflowY: 'auto', border: '1px solid var(--border-subtle)', borderRadius: 12, background: 'var(--bg-secondary)', padding: '0 12px 12px 12px' }}>
                    {isLoading ? (
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 16 }}>
                            <div className="loading-spinner" />
                            <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>Ejecutando consultas en paralelo...</p>
                        </div>
                    ) : comparisonData.length > 0 ? (
                        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                            <thead style={{ position: 'sticky', top: 0, background: 'var(--bg-secondary)', zIndex: 1, boxShadow: '0 1px 0 var(--border-subtle)' }}>
                                <tr>
                                    <th style={{ padding: '12px 16px', fontSize: '0.85rem', color: 'var(--text-muted)', fontWeight: 600 }}>Elemento Identificado</th>
                                    <th style={{ padding: '12px 16px', fontSize: '0.85rem', color: 'var(--text-muted)', fontWeight: 600, textAlign: 'center' }}>Vectorial Puro</th>
                                    <th style={{ padding: '12px 16px', fontSize: '0.85rem', color: 'var(--text-muted)', fontWeight: 600, textAlign: 'center' }}>Grafo Crisp (0.95)</th>
                                    <th style={{ padding: '12px 16px', fontSize: '0.85rem', color: 'var(--text-muted)', fontWeight: 600, textAlign: 'center' }}>Grafo Fuzzy ({fuzzyHighAlpha})</th>
                                    <th style={{ padding: '12px 16px', fontSize: '0.85rem', color: 'var(--text-muted)', fontWeight: 600, textAlign: 'center' }}>Grafo Fuzzy ({fuzzyLowAlpha})</th>
                                </tr>
                            </thead>
                            <tbody>
                                {comparisonData.map((item, i) => {
                                    const isSelected = selectedItem?.id === item.id;

                                    const renderGraphCell = (weight?: number, data?: any) => {
                                        if (weight === undefined) return <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>-</span>;

                                        let badgeColor = '#ef4444';
                                        let badgeBg = 'rgba(239, 68, 68, 0.1)';
                                        if (weight >= 0.8) {
                                            badgeColor = '#34d399';
                                            badgeBg = 'rgba(16, 185, 129, 0.1)';
                                        } else if (weight >= 0.5) {
                                            badgeColor = '#fbbf24';
                                            badgeBg = 'rgba(245, 158, 11, 0.1)';
                                        }

                                        return (
                                            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
                                                <span style={{ display: 'inline-flex', padding: '2px 6px', borderRadius: 4, background: badgeBg, color: badgeColor, fontSize: '0.75rem', fontWeight: 600 }}>
                                                    Score: {weight.toFixed(3)}
                                                </span>
                                                {data?.matched_concept && (
                                                    <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', lineHeight: 1.2, textAlign: 'center', maxWidth: 140 }}>
                                                        <span style={{ color: '#a78bfa', fontWeight: 600 }}>[{data.relation_type}]</span>
                                                        <br />{data.matched_concept}
                                                        {data.distance !== undefined && data.distance > 0 && <div style={{ marginTop: 2 }}>Dist: {data.distance.toFixed(3)}</div>}
                                                    </div>
                                                )}
                                            </div>
                                        );
                                    };

                                    return (
                                        <tr
                                            key={item.id}
                                            onClick={() => setSelectedItem(item)}
                                            style={{
                                                borderBottom: '1px solid var(--border-subtle)',
                                                background: isSelected ? 'rgba(99, 102, 241, 0.1)' : (i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.02)'),
                                                cursor: 'pointer',
                                                transition: 'background 0.2s',
                                            }}
                                            className="hover:bg-indigo-900/20"
                                        >
                                            <td style={{ padding: '12px 16px', borderLeft: isSelected ? '3px solid var(--accent-indigo)' : '3px solid transparent' }}>
                                                <div style={{ fontSize: '0.9rem', fontWeight: 500, color: 'var(--text-primary)', marginBottom: 4 }}>
                                                    {item.label}
                                                </div>
                                                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>ID: {item.id}</div>
                                                {item.properties?.matched_concepts && item.properties.matched_concepts.length > 0 && (
                                                    <div style={{ display: 'flex', gap: 4, marginTop: 6, flexWrap: 'wrap' }}>
                                                        {item.properties.matched_concepts.map((concept: string) => (
                                                            <span key={concept} style={{ fontSize: '0.65rem', padding: '2px 6px', borderRadius: 4, background: 'rgba(139, 92, 246, 0.15)', color: '#a78bfa', border: '1px solid rgba(139, 92, 246, 0.3)' }}>
                                                                {concept}
                                                            </span>
                                                        ))}
                                                    </div>
                                                )}
                                            </td>

                                            <td style={{ padding: '12px 16px', textAlign: 'center' }}>
                                                {item.vectorScore !== undefined ? (
                                                    <span style={{ display: 'inline-flex', padding: '4px 8px', borderRadius: 4, background: 'rgba(16, 185, 129, 0.1)', color: '#34d399', fontSize: '0.75rem', fontWeight: 600 }}>
                                                        {item.vectorScore.toFixed(3)}
                                                    </span>
                                                ) : (
                                                    <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>-</span>
                                                )}
                                            </td>

                                            <td style={{ padding: '12px 16px', textAlign: 'center' }}>
                                                {renderGraphCell(item.crispWeight, item.crispData)}
                                            </td>

                                            <td style={{ padding: '12px 16px', textAlign: 'center' }}>
                                                {renderGraphCell(item.fuzzy07Weight, item.fuzzy07Data)}
                                            </td>

                                            <td style={{ padding: '12px 16px', textAlign: 'center' }}>
                                                {renderGraphCell(item.fuzzy05Weight, item.fuzzy05Data)}
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)', opacity: 0.7 }}>
                            <Box size={48} style={{ marginBottom: 16 }} />
                            <p>Realiza una búsqueda para comparar los resultados de los 4 enfoques.</p>
                        </div>
                    )}
                </div>

                {/* Bottom Details Panel */}
                {selectedItem && (
                    <div style={{
                        width: '100%',
                        flexShrink: 0,
                        maxHeight: '90vh',
                        border: '1px solid var(--border-subtle)',
                        borderRadius: 12,
                        background: 'var(--bg-secondary)',
                        overflowY: 'auto',
                        overflowX: 'hidden',
                        display: 'flex', flexDirection: 'column'
                    }}>
                        <div style={{ padding: 16 }}>
                            <h4 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>
                                {selectedItem.label}
                            </h4>
                            <div style={{ display: 'flex', gap: 6, marginBottom: 12, flexWrap: 'wrap' }}>
                                <span style={{
                                    fontSize: '0.75rem',
                                    padding: '2px 8px',
                                    borderRadius: 12,
                                    background: 'rgba(99, 102, 241, 0.1)',
                                    color: 'var(--accent-indigo)',
                                    border: '1px solid var(--accent-indigo)',
                                    fontWeight: 600,
                                }}>
                                    {selectedItem.type || 'Element'}
                                </span>
                            </div>

                            <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: 8 }}>
                                {Object.entries(selectedItem.properties || {}).map(([key, val]) => {
                                    if (['download_url', 'minio_path', 'embedding', 'text', 'content', 'transcript', 'is_seed', 'is_discovery'].includes(key)) return null;
                                    return (
                                        <div key={key} style={{ width: '100%' }}>
                                            <strong style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>{key}:</strong>
                                            <div style={{ wordBreak: 'break-word', whiteSpace: 'pre-wrap', overflowWrap: 'break-word' }}>{String(val)}</div>
                                        </div>
                                    );
                                })}
                            </div>

                            {/* Media Preview */}
                            {(selectedItem.properties?.download_url || selectedItem.properties?.minio_path) && (
                                <div style={{ marginTop: 16 }}>
                                    <h5 style={{ fontSize: '0.8rem', fontWeight: 600, marginBottom: 8, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 6 }}>
                                        <ImageIcon size={14} /> Vista Previa Media
                                    </h5>
                                    <MediaPreview
                                        url={selectedItem.properties.download_url}
                                        path={selectedItem.properties.minio_path}
                                    />
                                </div>
                            )}

                            {/* Text Content Preview Button */}
                            {(() => {
                                const props = selectedItem.properties || {};
                                const hasTextData = !!(props.text || props.content || props.transcript || props.lyrics_summary || props.ocr_text);
                                const isTextFormat = props.mime_type?.includes('text') || props.mime_type?.includes('json') || props.mime_type?.includes('csv') || (props.minio_path && /\.(txt|md|csv|json|py|js|ts|html|css|xml|log)$/i.test(props.minio_path));
                                const hasUrl = !!props.download_url;

                                if (!hasTextData && !(isTextFormat && hasUrl)) return null;

                                return (
                                    <button
                                        onClick={() => setTextPreviewOpen(true)}
                                        style={{
                                            background: 'transparent',
                                            border: '1px solid var(--border-subtle)',
                                            borderRadius: 'var(--radius-sm)',
                                            padding: '8px 10px', fontSize: '0.8rem',
                                            color: 'var(--text-secondary)', cursor: 'pointer',
                                            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                                            width: '100%', marginTop: 12,
                                            transition: 'all 0.2s'
                                        }}
                                        onMouseEnter={(e: any) => {
                                            e.currentTarget.style.borderColor = 'var(--accent-primary)';
                                            e.currentTarget.style.color = 'var(--accent-primary)';
                                        }}
                                        onMouseLeave={(e: any) => {
                                            e.currentTarget.style.borderColor = 'var(--border-subtle)';
                                            e.currentTarget.style.color = 'var(--text-secondary)';
                                        }}
                                    >
                                        <FileText size={14} />
                                        Ver contenido completo
                                    </button>
                                );
                            })()}
                        </div>
                    </div>
                )}

                {/* RAG Generation Panel */}
                {comparisonData.length > 0 && (
                    <div style={{
                        border: '1px solid var(--border-subtle)',
                        borderRadius: 12,
                        background: 'var(--bg-secondary)',
                        padding: 16,
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 16,
                        flexShrink: 0
                    }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                            <h4 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)', margin: 0, display: 'flex', alignItems: 'center', gap: 6 }}>
                                🧠 Panel de Generación RAG (Control de Usuario)
                            </h4>
                            <button
                                className="btn-primary"
                                onClick={handleSynthesize}
                                disabled={isSynthesizing || comparisonData.length === 0}
                                style={{ padding: '8px 16px' }}
                            >
                                {isSynthesizing ? <div className="loading-spinner" style={{ width: 14, height: 14, borderWidth: 2 }} /> : <FileText size={16} />}
                                {isSynthesizing ? 'Sintetizando...' : 'Sintetizar Respuesta'}
                            </button>
                        </div>

                        <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', padding: '12px 0' }}>
                            {/* Selector de Modelo */}
                            <div style={{ flex: 1, minWidth: 200 }}>
                                <label style={{ fontSize: '0.85rem', fontWeight: 500, color: 'var(--text-primary)', display: 'block', marginBottom: 4 }}>
                                    Modelo de Inferencia
                                </label>
                                <select
                                    className="search-input"
                                    value={ragConfig.model}
                                    onChange={(e) => setRagConfig(prev => ({ ...prev, model: e.target.value as 'local' | 'cloud' }))}
                                    style={{ width: '100%', cursor: 'pointer' }}
                                >
                                    <option value="cloud">☁️ Cloud Advanced (Mejor razonamiento)</option>
                                    <option value="local">💻 Local Edge (Privacidad absoluta)</option>
                                </select>
                                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: 4 }}>
                                    Usa Cloud (ej. OpenAI/Gemini) para razonamiento complejo. Usa Local Edge para procesar todo en tu máquina.
                                </div>
                            </div>

                            {/* Estrategia de Contexto */}
                            <div style={{ flex: 1, minWidth: 220 }}>
                                <label style={{ fontSize: '0.85rem', fontWeight: 500, color: 'var(--text-primary)', display: 'block', marginBottom: 4 }}>
                                    Metodología de Recuperación (Ablation Mode)
                                </label>
                                <select
                                    className="search-input"
                                    value={ragConfig.strategy}
                                    onChange={(e) => setRagConfig(prev => ({ ...prev, strategy: e.target.value as RAGConfig['strategy'] }))}
                                    style={{ width: '100%', cursor: 'pointer', marginTop: 4 }}
                                >
                                    <option value="baseline_vectorial">Baseline Vectorial (Solo Weaviate)</option>
                                    <option value="hibrido_estandar">RAG Híbrido Estándar (Weaviate + Crisp Graph)</option>
                                    <option value="difuso_puro">RAG Difuso Puro (Crisp + Normal + Fuzzy)</option>
                                    <option value="hibrido_total">Híbrido Total (Blended)</option>
                                </select>
                                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: 8 }}>
                                    Permite comparar el rendimiento de diferentes paradigmas de recuperación de información.
                                </div>
                            </div>

                            {/* Top N y Privacidad */}
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 12, minWidth: 200 }}>
                                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
                                    <div>
                                        <label style={{ fontSize: '0.85rem', fontWeight: 500, color: 'var(--text-primary)', display: 'block', marginBottom: 4 }}>
                                            Límite de Docs (Top N)
                                        </label>
                                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', maxWidth: 160 }}>
                                            Nº de archivos a enviar al LLM. Más contexto = más tokens consumidos.
                                        </div>
                                    </div>
                                    <input
                                        className="search-input"
                                        type="number"
                                        min={1} max={30}
                                        value={ragConfig.top_n}
                                        onChange={(e) => setRagConfig(prev => ({ ...prev, top_n: parseInt(e.target.value) || 5 }))}
                                        style={{ width: 60, textAlign: 'center' }}
                                    />
                                </div>

                                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 8px', background: ragConfig.privacy_mode ? 'rgba(239, 68, 68, 0.1)' : 'transparent', border: `1px solid ${ragConfig.privacy_mode ? '#ef4444' : 'var(--border-subtle)'}`, borderRadius: 8, transition: 'all 0.2s', marginTop: 'auto' }}>
                                    <div style={{ fontSize: '0.8rem', color: ragConfig.privacy_mode ? '#ef4444' : 'var(--text-primary)', fontWeight: ragConfig.privacy_mode ? 600 : 400 }}>
                                        🕵️‍♂️ Modo Incógnito
                                    </div>
                                    <div className={`toggle-switch ${ragConfig.privacy_mode ? 'on' : 'off'}`} onClick={() => setRagConfig(prev => ({ ...prev, privacy_mode: !prev.privacy_mode }))} style={{ cursor: 'pointer' }}>
                                        <div className="toggle-slider" style={{
                                            width: 32, height: 18, background: ragConfig.privacy_mode ? '#ef4444' : 'var(--border-subtle)', borderRadius: 16, position: 'relative', transition: '0.2s'
                                        }}>
                                            <div style={{ width: 14, height: 14, background: 'var(--bg-primary)', borderRadius: '50%', position: 'absolute', top: 2, left: ragConfig.privacy_mode ? 16 : 2, transition: '0.2s' }} />
                                        </div>
                                    </div>
                                </div>
                                {ragConfig.privacy_mode && (
                                    <div style={{ fontSize: '0.65rem', color: '#ef4444', marginTop: -6 }}>
                                        *Petición no registrada en el historial.
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* Synthesized Response Area */}
                        {synthResponse && (
                            <div style={{
                                marginTop: 8,
                                paddingTop: 16,
                                borderTop: '1px solid var(--border-subtle)',
                                animation: 'fadeIn 0.5s ease-out'
                            }}>
                                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
                                    <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)' }}>Métricas RAG:</span>
                                    {synthResponse.is_private && <span style={{ fontSize: '0.7rem', padding: '2px 8px', borderRadius: 12, background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', border: '1px solid #ef4444' }}>Incógnito ✅</span>}
                                    <span style={{ fontSize: '0.7rem', padding: '2px 8px', borderRadius: 12, background: 'rgba(99, 102, 241, 0.1)', color: 'var(--accent-indigo)', border: '1px solid rgba(99, 102, 241, 0.3)' }}>{synthResponse.sources_used.length} Fuentes Citadas</span>
                                </div>

                                <div className="markdown-body" style={{ fontSize: '0.95rem', lineHeight: 1.6, color: 'var(--text-primary)' }}>
                                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                        {synthResponse.answer}
                                    </ReactMarkdown>
                                </div>
                            </div>
                        )}
                    </div>
                )}

                {/* Context legend or summary below */}
                {comparisonData.length > 0 && (
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'flex', gap: 16, flexWrap: 'wrap', flexShrink: 0 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#34d399' }} /> Puro (Solo Weaviate Text)
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#60a5fa' }} /> Crisp (Weaviate + Neo4j peso ≥ 0.9)
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#a78bfa' }} /> Fuzzy (Weaviate + Neo4j peso ≥ {fuzzyHighAlpha})
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#f472b6' }} /> Fuzzy (Weaviate + Neo4j peso ≥ {fuzzyLowAlpha})
                        </div>
                    </div>
                )}

                {/* Text Preview Modal */}
                {selectedItem && (() => {
                    const props = selectedItem.properties || {};
                    const hasTextData = !!(props.text || props.content || props.transcript);
                    const isTextFormat = props.mime_type?.includes('text') || props.mime_type?.includes('json') || props.mime_type?.includes('csv') || (props.minio_path && /\.(txt|md|csv|json|py|js|ts|html|css|xml|log)$/i.test(props.minio_path));
                    const urlToPass = (!hasTextData && isTextFormat && props.download_url) ? props.download_url : undefined;

                    return (
                        <TextPreviewModal
                            isOpen={textPreviewOpen}
                            onClose={() => setTextPreviewOpen(false)}
                            title={selectedItem.label || 'Contenido de detalle'}
                            content={
                                props.text ||
                                props.content ||
                                props.transcript ||
                                props.lyrics_summary ||
                                props.ocr_text ||
                                ''
                            }
                            url={urlToPass}
                        />
                    );
                })()}
            </div>
        </div>
    );
}
