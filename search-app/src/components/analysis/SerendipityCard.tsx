import { useState, useCallback, useEffect } from 'react';
import axios from 'axios';
import { Loader2, RefreshCw, Dice5, Info, FileText, X, Sparkles, Image, Music, Video, File, Download } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import MediaPreview from '../search/MediaPreview';
import { getAssetPreview, explainAnalyticalPath, type AssetPreviewResponse } from '../../lib/api';

interface PathStep {
    id: string;
    name?: string;
    type: 'Concept' | 'Asset';
    weight: number | null;
    file_hash?: string | null;
    mime_type?: string | null;
    download_url?: string | null;
    minio_path?: string | null;
}

interface AnalysisResponse {
    tool: string;
    status: string;
    message: string;
    mock_data: {
        path: PathStep[];
    };
}

function WeightBadge({ weight }: { weight: number | null }) {
    if (weight === null || weight === undefined) return null;
    const isFuzzy = weight < 0.8;
    return (
        <div
            style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                padding: '2px 8px',
                borderRadius: 12,
                fontSize: '0.68rem',
                fontWeight: 600,
                fontFamily: 'monospace',
                background: isFuzzy ? '#f97316' : '#22c55e',
                color: '#fff',
                boxShadow: isFuzzy ? '0 0 8px #f9731666' : '0 0 8px #22c55e44',
            }}
        >
            {isFuzzy ? '✨' : '✅'} {weight.toFixed(2)}
        </div>
    );
}

function getMimeIcon(mime: string | null | undefined) {
    if (!mime) return <File size={16} />;
    if (mime.startsWith('image')) return <Image size={16} />;
    if (mime.startsWith('audio')) return <Music size={16} />;
    if (mime.startsWith('video')) return <Video size={16} />;
    if (mime.includes('pdf')) return <FileText size={16} />;
    return <File size={16} />;
}

function getMimeLabel(mime: string | null | undefined) {
    if (!mime) return 'Archivo';
    if (mime.startsWith('image')) return '🖼️ Imagen';
    if (mime.startsWith('audio')) return '🎵 Audio';
    if (mime.startsWith('video')) return '🎬 Video';
    if (mime.includes('pdf')) return '📄 PDF';
    if (mime.startsWith('text')) return '📝 Texto';
    return '📎 Archivo';
}

function StepNode({
    step,
    isSelected,
    onClick,
}: {
    step: PathStep;
    isSelected: boolean;
    onClick: () => void;
}) {
    const isConcept = step.type === 'Concept';
    const isAsset = step.type === 'Asset';
    return (
        <div
            onClick={isAsset ? onClick : undefined}
            style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 6,
                minWidth: 100,
                cursor: isAsset ? 'pointer' : 'default',
            }}
        >
            <div
                style={{
                    width: isConcept ? 64 : 56,
                    height: isConcept ? 64 : 56,
                    borderRadius: isConcept ? '50%' : 12,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: isConcept ? 22 : 18,
                    background: isConcept
                        ? 'linear-gradient(135deg, #7c3aed, #a78bfa)'
                        : 'var(--bg-surface)',
                    color: '#fff',
                    border: isSelected
                        ? '3px solid #fbbf24'
                        : isConcept
                            ? '3px solid var(--node-concept-border)'
                            : '2px solid var(--node-asset-border)',
                    boxShadow: isSelected
                        ? '0 0 20px #fbbf2466'
                        : isConcept
                            ? '0 0 16px var(--node-concept-shadow)'
                            : '0 2px 8px rgba(0,0,0,0.2)',
                    transition: 'all 0.2s',
                }}
            >
                {isConcept ? '💡' : getMimeIcon(step.mime_type)}
            </div>
            <span
                style={{
                    fontSize: '0.75rem',
                    color: isSelected ? '#fbbf24' : isConcept ? 'var(--node-concept-text)' : 'var(--text-tertiary)',
                    fontWeight: isConcept || isSelected ? 600 : 400,
                    textAlign: 'center',
                    maxWidth: 120,
                    wordBreak: 'break-word',
                }}
            >
                {step.name || step.id}
            </span>
            <span
                style={{
                    fontSize: '0.6rem',
                    color: 'var(--text-dim)',
                    textTransform: 'uppercase',
                    letterSpacing: 1,
                }}
            >
                {step.type}
                {isAsset && <span style={{ color: 'var(--text-muted-alt)', marginLeft: 4 }}>👆</span>}
            </span>
        </div>
    );
}

function Connector({ weight }: { weight: number | null }) {
    const isFuzzy = weight !== null && weight < 0.8;
    return (
        <div
            style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 4,
                minWidth: 60,
            }}
        >
            <WeightBadge weight={weight} />
            <div
                style={{
                    height: 3,
                    width: 60,
                    borderRadius: 2,
                    background: isFuzzy
                        ? 'linear-gradient(90deg, #f97316, #fbbf24)'
                        : 'linear-gradient(90deg, #22c55e, #86efac)',
                    opacity: 0.7,
                }}
            />
            <span style={{ fontSize: '0.55rem', color: 'var(--text-dim)' }}>
                {isFuzzy ? 'difusa' : 'segura'}
            </span>
        </div>
    );
}

export default function SerendipityCard() {
    const [path, setPath] = useState<PathStep[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [message, setMessage] = useState('');
    const [generated, setGenerated] = useState(false);
    const [selectedAsset, setSelectedAsset] = useState<PathStep | null>(null);
    const [previewAsset, setPreviewAsset] = useState<AssetPreviewResponse | null>(null);
    const [isLoadingPreview, setIsLoadingPreview] = useState(false);

    // LLM Explanation State
    const [explanation, setExplanation] = useState<string | null>(null);
    const [explaining, setExplaining] = useState(false);
    const [privacyMode, setPrivacyMode] = useState(false);

    const navigate = useNavigate();

    useEffect(() => {
        if (!selectedAsset || selectedAsset.type !== 'Asset') {
            setPreviewAsset(null);
            return;
        }
        let isMounted = true;

        const fetchPreview = async () => {
            setIsLoadingPreview(true);
            try {
                const res = await getAssetPreview(selectedAsset.id);
                if (isMounted) setPreviewAsset(res);
            } catch (err: any) {
                console.error("Failed to fetch asset preview:", err);
            } finally {
                if (isMounted) setIsLoadingPreview(false);
            }
        };
        fetchPreview();
        return () => { isMounted = false; };
    }, [selectedAsset]);

    const generate = useCallback(async () => {
        setLoading(true);
        setError(null);
        setSelectedAsset(null);
        setExplanation(null);
        try {
            const res = await axios.post<AnalysisResponse>('http://localhost:8000/analysis/serendipity', undefined, { timeout: 120000 });
            if (res.data.status === 'error') throw new Error(res.data.message);
            setPath(res.data.mock_data.path || []);
            setMessage(res.data.message);
            setGenerated(true);
        } catch (err: any) {
            console.error(err);
            setError(err.message || 'Error generating serendipity path');
        } finally {
            setLoading(false);
        }
    }, []);

    const handleExplain = async () => {
        if (!path.length) return;
        setExplaining(true);
        setExplanation(null);

        const nodes = path.map(p => ({
            id: p.id,
            name: p.name,
            node_type: p.type,
            file_hash: p.file_hash
        }));

        const edges = [];
        for (let i = 0; i < path.length - 1; i++) {
            edges.push({
                source: path[i].id,
                target: path[i + 1].id,
                weight: path[i + 1].weight,
                rel_type: 'CONECTADO_A'
            });
        }

        try {
            const res = await explainAnalyticalPath({
                tool_name: 'serendipity',
                nodes,
                edges,
                privacy_mode: privacyMode,
            });
            if (res.status === 'success') {
                setExplanation(res.explanation);
            } else {
                setExplanation(`⚠️ ${res.explanation}`);
            }
        } catch (err: unknown) {
            setExplanation('⚠️ Error al generar la explicación: ' + (err instanceof Error ? err.message : String(err)));
        } finally {
            setExplaining(false);
        }
    };

    const handleExportJSON = () => {
        if (!path.length) return;
        const exportData = {
            generated_at: new Date().toISOString(),
            tool: 'serendipity_path',
            path: path.map(p => ({
                id: p.id,
                name: p.name,
                type: p.type,
                weight: p.weight,
                file_hash: p.file_hash,
                mime_type: p.mime_type
            })),
            llm_explanation: explanation || null,
            message: message,
            options: { privacy_mode: privacyMode }
        };
        const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `serendipity_path_${Date.now()}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    };

    const firstConcept = path.length > 0 ? path[0] : null;
    const lastConcept = path.length > 0 ? path[path.length - 1] : null;

    return (
        <div style={{ padding: 24, paddingBottom: 60, width: '100%' }}>
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-4">
                    <button onClick={() => navigate('/analysis')} className="btn-secondary">Back</button>
                    <div>
                        <h2 className="text-2xl font-bold flex items-center gap-2 text-slate-100">
                            <Dice5 className="text-amber-500" />
                            Camino de Serendipia
                        </h2>
                        <p className="text-sm text-slate-500">
                            Asociaciones inesperadas a través de conexiones difusas
                        </p>
                    </div>
                </div>
                <button onClick={generate} className="btn-icon" disabled={loading}>
                    <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
                </button>
            </div>

            {error && (
                <div className="p-4 mb-6 text-red-500 border border-red-200 rounded-xl">{error}</div>
            )}

            <div style={{ display: 'flex', gap: 20 }}>
                {/* Main panel */}
                <div
                    style={{
                        flex: 1,
                        padding: 24,
                        minHeight: 400,
                        background: 'var(--bg-panel)',
                        border: '1px solid var(--border-panel)',
                        borderRadius: 16,
                    }}
                >
                    {!generated && !loading && (
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: 360 }}>
                            <button
                                onClick={generate}
                                style={{
                                    padding: '16px 40px',
                                    fontSize: '1.1rem',
                                    fontWeight: 700,
                                    borderRadius: 16,
                                    border: 'none',
                                    cursor: 'pointer',
                                    background: 'linear-gradient(135deg, #f97316, #fbbf24)',
                                    color: '#fff',
                                    boxShadow: '0 4px 20px #f9731655',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: 12,
                                    transition: 'transform 0.15s',
                                }}
                                onMouseOver={(e) => (e.currentTarget.style.transform = 'scale(1.05)')}
                                onMouseOut={(e) => (e.currentTarget.style.transform = 'scale(1)')}
                            >
                                <Dice5 size={24} /> 🎲 Generar Camino de Serendipia
                            </button>
                            <p style={{ marginTop: 16, color: 'var(--text-dim)', fontSize: '0.82rem', textAlign: 'center', maxWidth: 400 }}>
                                Descubre asociaciones ocultas saltando entre conceptos y archivos
                                a través de conexiones que normalmente pasarían desapercibidas.
                            </p>
                        </div>
                    )}

                    {loading && (
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: 360 }}>
                            <Loader2 className="animate-spin mb-4 text-amber-400" size={40} />
                            <span style={{ color: 'var(--text-tertiary)' }}>Buscando camino difuso...</span>
                        </div>
                    )}

                    {generated && !loading && path.length === 0 && (
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: 360 }}>
                            <p style={{ color: 'var(--text-dim)', fontSize: '0.9rem', textAlign: 'center' }}>
                                No se encontró un camino difuso esta vez. Intenta de nuevo 🎲
                            </p>
                            <button
                                onClick={generate}
                                style={{
                                    marginTop: 16, padding: '10px 24px', borderRadius: 12,
                                    border: 'none', cursor: 'pointer', background: '#f97316',
                                    color: '#fff', fontWeight: 600,
                                }}
                            >
                                Reintentar
                            </button>
                        </div>
                    )}

                    {generated && !loading && path.length > 0 && (
                        <div>
                            {/* Metro line */}
                            <div
                                style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    gap: 12,
                                    padding: '30px 0',
                                    overflowX: 'auto',
                                }}
                            >
                                {path.map((step, i) => (
                                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                                        <StepNode
                                            step={step}
                                            isSelected={selectedAsset?.id === step.id && step.type === 'Asset'}
                                            onClick={() => step.type === 'Asset' && setSelectedAsset(step)}
                                        />
                                        {i < path.length - 1 && (
                                            <Connector weight={path[i + 1].weight} />
                                        )}
                                    </div>
                                ))}
                            </div>

                            {/* Actions row */}
                            <div style={{ display: 'flex', gap: 16, justifyContent: 'center', marginTop: 16, alignItems: 'center' }}>
                                <button
                                    onClick={generate}
                                    style={{
                                        padding: '10px 28px', fontSize: '0.85rem', fontWeight: 600,
                                        borderRadius: 12, border: 'none', cursor: 'pointer',
                                        background: 'transparent',
                                        borderBottom: '2px solid #f97316',
                                        color: '#f97316',
                                        display: 'inline-flex', alignItems: 'center', gap: 8,
                                    }}
                                >
                                    <Dice5 size={16} /> Otro Camino
                                </button>

                                {/* Privacy toggle */}
                                <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }} title="Proteger datos: El modelo LLM no entrenará con esta consulta ni su contexto">
                                    <div style={{
                                        width: 32, height: 18, borderRadius: 16,
                                        background: privacyMode ? '#f59e0b' : 'var(--bg-surface-hover)',
                                        position: 'relative',
                                        transition: 'background 0.2s',
                                    }}>
                                        <div style={{
                                            position: 'absolute', top: 2, left: privacyMode ? 16 : 2,
                                            width: 14, height: 14, borderRadius: '50%',
                                            background: '#fff', transition: 'left 0.2s'
                                        }} />
                                    </div>
                                    <span style={{ fontSize: '0.75rem', color: privacyMode ? '#f59e0b' : 'var(--text-muted-alt)', fontWeight: 600 }}>
                                        Privacidad
                                    </span>
                                    <input
                                        type="checkbox"
                                        checked={privacyMode}
                                        onChange={(e) => setPrivacyMode(e.target.checked)}
                                        style={{ display: 'none' }}
                                    />
                                </label>

                                <button
                                    onClick={handleExplain}
                                    disabled={explaining}
                                    style={{
                                        padding: '10px 28px', fontSize: '0.85rem', fontWeight: 600,
                                        borderRadius: 12, border: 'none', cursor: explaining ? 'not-allowed' : 'pointer',
                                        background: 'linear-gradient(135deg, #ec4899, #8b5cf6)',
                                        color: '#fff', boxShadow: '0 2px 12px #ec489944',
                                        display: 'inline-flex', alignItems: 'center', gap: 8,
                                        opacity: explaining ? 0.7 : 1,
                                    }}
                                >
                                    {explaining ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
                                    Explicar Camino con IA
                                </button>

                                <button
                                    onClick={handleExportJSON}
                                    style={{
                                        padding: '10px 16px', fontSize: '0.85rem', fontWeight: 600,
                                        borderRadius: 12, border: '1px solid var(--border-surface)', cursor: 'pointer',
                                        background: 'var(--bg-surface)',
                                        color: 'var(--text-code)',
                                        display: 'inline-flex', alignItems: 'center', gap: 8,
                                        transition: 'all 0.2s',
                                    }}
                                    onMouseOver={(e) => { e.currentTarget.style.background = 'var(--bg-surface-hover)'; e.currentTarget.style.color = 'var(--text-body)'; }}
                                    onMouseOut={(e) => { e.currentTarget.style.background = 'var(--bg-surface)'; e.currentTarget.style.color = 'var(--text-code)'; }}
                                    title="Exportar a JSON"
                                >
                                    <Download size={16} /> JSON
                                </button>
                            </div>

                            {/* Explanation Panel */}
                            {explanation && (
                                <div style={{
                                    background: 'var(--bg-panel)',
                                    borderRadius: 16,
                                    border: '1px solid var(--border-panel)',
                                    padding: '24px',
                                    marginTop: '24px',
                                    position: 'relative',
                                    overflow: 'hidden'
                                }}>
                                    <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 4, background: 'linear-gradient(to right, #ec4899, #8b5cf6)' }} />
                                    <h3 style={{ margin: '0 0 16px', display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-body)', fontSize: '1.1rem' }}>
                                        <Sparkles size={20} className="text-pink-400" /> Explicación del Camino
                                    </h3>
                                    <div style={{
                                        color: 'var(--text-code)',
                                        lineHeight: 1.6,
                                        fontSize: '0.95rem',
                                        whiteSpace: 'pre-wrap',
                                        background: 'var(--bg-deep)',
                                        padding: 16,
                                        borderRadius: 12,
                                        border: '1px solid var(--border-panel)',
                                    }}>
                                        {explanation}
                                    </div>
                                </div>
                            )}

                            {/* Asset Detail Panel */}
                            {selectedAsset && (
                                <div
                                    style={{
                                        marginTop: 24,
                                        background: 'var(--bg-panel)',
                                        border: '1px solid var(--border-surface)',
                                        borderRadius: 16,
                                        overflow: 'hidden',
                                    }}
                                >
                                    {/* Header */}
                                    <div
                                        style={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            justifyContent: 'space-between',
                                            padding: '12px 20px',
                                            background: 'var(--bg-surface)',
                                            borderBottom: '1px solid var(--border-surface)',
                                        }}
                                    >
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                                            <FileText size={16} className="text-amber-400" />
                                            <span style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-body)' }}>
                                                {selectedAsset.name || selectedAsset.id}
                                            </span>
                                            <span
                                                style={{
                                                    fontSize: '0.68rem', padding: '2px 8px', borderRadius: 10,
                                                    background: 'var(--bg-surface-hover)', color: 'var(--text-subtle)',
                                                }}
                                            >
                                                DigitalAsset
                                            </span>
                                            {selectedAsset.weight !== null && (
                                                <WeightBadge weight={selectedAsset.weight} />
                                            )}
                                        </div>
                                        <button
                                            onClick={() => setSelectedAsset(null)}
                                            style={{
                                                background: 'transparent', border: 'none', cursor: 'pointer',
                                                color: 'var(--text-muted-alt)', padding: 4,
                                            }}
                                        >
                                            <X size={18} />
                                        </button>
                                    </div>

                                    {/* Body */}
                                    <div style={{ padding: 20 }}>
                                        {isLoadingPreview ? (
                                            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 120 }}>
                                                <Loader2 className="animate-spin text-amber-500" size={32} />
                                            </div>
                                        ) : previewAsset ? (
                                            <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
                                                {/* Properties column */}
                                                <div style={{ display: 'flex', flexDirection: 'column', gap: 12, minWidth: 200, flex: '0 0 240px' }}>
                                                    <div>
                                                        <div style={{ fontSize: '0.65rem', color: 'var(--text-muted-alt)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 4 }}>
                                                            FILENAME
                                                        </div>
                                                        <div style={{ fontSize: '0.85rem', color: 'var(--text-subtle)', wordBreak: 'break-word' }}>
                                                            {previewAsset.name || selectedAsset.id}
                                                        </div>
                                                    </div>
                                                    <div>
                                                        <div style={{ fontSize: '0.65rem', color: 'var(--text-muted-alt)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 4 }}>
                                                            TIPO
                                                        </div>
                                                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--text-subtle)', fontSize: '0.85rem' }}>
                                                            {getMimeIcon(previewAsset.mime_type || selectedAsset.mime_type)}
                                                            <span>{getMimeLabel(previewAsset.mime_type || selectedAsset.mime_type)}</span>
                                                        </div>
                                                        {(previewAsset.mime_type || selectedAsset.mime_type) && (
                                                            <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)', marginTop: 2, fontFamily: 'monospace' }}>
                                                                {previewAsset.mime_type || selectedAsset.mime_type}
                                                            </div>
                                                        )}
                                                    </div>
                                                    {previewAsset.tags && previewAsset.tags.length > 0 && (
                                                        <div>
                                                            <div style={{ fontSize: '0.65rem', color: 'var(--text-muted-alt)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 4 }}>
                                                                ETIQUETAS
                                                            </div>
                                                            <div className="flex flex-wrap gap-2">
                                                                {previewAsset.tags.map((tag, idx) => (
                                                                    <span key={idx} className="bg-amber-900/30 text-amber-300 border border-amber-500/30 px-2 py-0.5 rounded-full text-[0.65rem]">#{tag}</span>
                                                                ))}
                                                            </div>
                                                        </div>
                                                    )}
                                                    {(selectedAsset.file_hash) && (
                                                        <div>
                                                            <div style={{ fontSize: '0.65rem', color: 'var(--text-muted-alt)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 4 }}>
                                                                HASH
                                                            </div>
                                                            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted-alt)', fontFamily: 'monospace', wordBreak: 'break-all' }}>
                                                                {selectedAsset.file_hash}
                                                            </div>
                                                        </div>
                                                    )}
                                                    {/* Connection context */}
                                                    <div style={{
                                                        background: 'var(--bg-surface)', borderRadius: 8, padding: 10,
                                                        border: '1px solid var(--border-surface)', fontSize: '0.78rem', color: 'var(--text-tertiary)', lineHeight: 1.6
                                                    }}>
                                                        Peso: <WeightBadge weight={selectedAsset.weight} />{' '}
                                                        {selectedAsset.weight !== null && selectedAsset.weight < 0.8
                                                            ? '— conexión difusa, fuente de serendipia'
                                                            : '— conexión sólida'}
                                                    </div>
                                                </div>

                                                {/* Media column */}
                                                <div style={{ flex: 1, minWidth: 240, display: 'flex', flexDirection: 'column', gap: 16 }}>
                                                    {(previewAsset.download_url || previewAsset.minio_path) ? (
                                                        <div>
                                                            <div style={{ fontSize: '0.65rem', color: 'var(--text-muted-alt)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 8 }}>
                                                                VISTA PREVIA
                                                            </div>
                                                            <MediaPreview
                                                                url={previewAsset.download_url || undefined}
                                                                path={previewAsset.minio_path || undefined}
                                                            />
                                                        </div>
                                                    ) : <></>}

                                                    {previewAsset.content && (
                                                        <div>
                                                            <div style={{ fontSize: '0.65rem', color: 'var(--text-muted-alt)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 8 }}>
                                                                CONTENIDO EXTRAÍDO
                                                            </div>
                                                            <div style={{
                                                                background: 'var(--bg-deep)', border: '1px solid var(--border-surface)', borderRadius: 8, padding: 16,
                                                                fontSize: '0.8rem', color: 'var(--text-code)', whiteSpace: 'pre-wrap', fontFamily: 'monospace',
                                                                lineHeight: 1.6, maxHeight: 300, overflowY: 'auto'
                                                            }} className="custom-scrollbar">
                                                                {previewAsset.content}
                                                            </div>
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        ) : (
                                            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: 120, color: 'var(--text-dim)' }}>
                                                <File size={32} className="mb-2 opacity-50" />
                                                <span style={{ fontSize: '0.85rem' }}>No se pudo cargar la vista previa</span>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            )}
                        </div>
                    )}
                </div>

                {/* Info Sidebar */}
                <div
                    style={{
                        width: 260,
                        padding: 20,
                        flexShrink: 0,
                        background: 'var(--bg-panel)',
                        border: '1px solid var(--border-panel)',
                        borderRadius: 16,
                    }}
                >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
                        <Info size={18} className="text-amber-400" />
                        <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text-body)', margin: 0 }}>
                            ¿Qué es esto?
                        </h3>
                    </div>

                    <p style={{ fontSize: '0.78rem', color: 'var(--text-tertiary)', lineHeight: 1.7, marginBottom: 16 }}>
                        La <strong style={{ color: '#fbbf24' }}>Serendipia</strong> simula un "pensamiento lateral".
                        Encuentra rutas entre conceptos priorizando conexiones <em>difusas</em> — asociaciones
                        que normalmente pasarían desapercibidas.
                    </p>

                    <p style={{ fontSize: '0.78rem', color: 'var(--text-tertiary)', lineHeight: 1.7, marginBottom: 16 }}>
                        <strong style={{ color: 'var(--text-subtle)' }}>Haz clic</strong> en cualquier <strong style={{ color: 'var(--text-subtle)' }}>📄 Asset</strong> del recorrido
                        para ver sus datos y vista previa en el panel inferior.
                    </p>

                    {generated && path.length > 0 && firstConcept && lastConcept && (
                        <div style={{
                            background: 'var(--bg-surface)', borderRadius: 8, padding: 12, marginBottom: 16,
                            border: '1px solid var(--border-surface)'
                        }}>
                            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted-alt)', fontWeight: 600, marginBottom: 6 }}>
                                VIAJE ACTUAL
                            </div>
                            <p style={{ fontSize: '0.78rem', color: 'var(--text-tertiary)', lineHeight: 1.6, margin: 0 }}>
                                Hemos conectado{' '}
                                <strong style={{ color: 'var(--node-concept-text)' }}>{firstConcept.name || firstConcept.id}</strong> con{' '}
                                <strong style={{ color: 'var(--node-concept-text)' }}>{lastConcept.name || lastConcept.id}</strong>.
                                Este camino fue posible gracias a asociaciones sutiles en tus archivos
                                que normalmente pasarían desapercibidas.
                            </p>
                        </div>
                    )}

                    <div style={{
                        background: 'var(--bg-surface)', borderRadius: 8, padding: 12, marginBottom: 16,
                        border: '1px solid var(--border-surface)'
                    }}>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted-alt)', fontWeight: 600, marginBottom: 8 }}>
                            LEYENDA
                        </div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', lineHeight: 1.8 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#7c3aed' }} />
                                <span>💡 Concepto</span>
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                <div style={{ width: 8, height: 8, borderRadius: 3, background: 'var(--node-asset-border)' }} />
                                <span>📄 DigitalAsset (clic para ver)</span>
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 6 }}>
                                <span style={{ background: '#f97316', borderRadius: 8, padding: '1px 6px', fontSize: '0.6rem', color: '#fff' }}>✨ 0.7</span>
                                <span>Difusa ({"< 0.8"})</span>
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                <span style={{ background: '#22c55e', borderRadius: 8, padding: '1px 6px', fontSize: '0.6rem', color: '#fff' }}>✅ 0.9</span>
                                <span>Segura (≥ 0.8)</span>
                            </div>
                        </div>
                    </div>

                    {message && (
                        <div style={{
                            fontSize: '0.7rem', color: '#4ade80',
                            padding: '8px 12px', background: '#22c55e10', borderRadius: 6,
                            border: '1px solid #22c55e30'
                        }}>
                            ✅ {message}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
