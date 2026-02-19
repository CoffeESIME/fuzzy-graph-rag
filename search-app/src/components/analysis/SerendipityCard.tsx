import { useState, useCallback } from 'react';
import axios from 'axios';
import { Loader2, RefreshCw, Dice5, Info, FileText, X, Image, Music, Video, File } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import MediaPreview from '../search/MediaPreview';

interface PathStep {
    id: string;
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
                        : '#1e293b',
                    color: '#fff',
                    border: isSelected
                        ? '3px solid #fbbf24'
                        : isConcept
                            ? '3px solid #c4b5fd'
                            : '2px solid #475569',
                    boxShadow: isSelected
                        ? '0 0 20px #fbbf2466'
                        : isConcept
                            ? '0 0 16px #7c3aed55'
                            : '0 2px 8px #00000033',
                    transition: 'all 0.2s',
                }}
            >
                {isConcept ? '💡' : getMimeIcon(step.mime_type)}
            </div>
            <span
                style={{
                    fontSize: '0.75rem',
                    color: isSelected ? '#fbbf24' : isConcept ? '#c4b5fd' : '#94a3b8',
                    fontWeight: isConcept || isSelected ? 600 : 400,
                    textAlign: 'center',
                    maxWidth: 120,
                    wordBreak: 'break-word',
                }}
            >
                {step.id}
            </span>
            <span
                style={{
                    fontSize: '0.6rem',
                    color: '#475569',
                    textTransform: 'uppercase',
                    letterSpacing: 1,
                }}
            >
                {step.type}
                {isAsset && <span style={{ color: '#64748b', marginLeft: 4 }}>👆</span>}
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
            <span style={{ fontSize: '0.55rem', color: '#475569' }}>
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
    const navigate = useNavigate();

    const generate = useCallback(async () => {
        setLoading(true);
        setError(null);
        setSelectedAsset(null);
        try {
            const res = await axios.post<AnalysisResponse>('http://localhost:8000/analysis/serendipity');
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

    const firstConcept = path.length > 0 ? path[0] : null;
    const lastConcept = path.length > 0 ? path[path.length - 1] : null;

    return (
        <div style={{ padding: 24, paddingBottom: 60, maxWidth: 1200, margin: '0 auto' }}>
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
                    className="bg-white dark:bg-slate-950 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800"
                    style={{ flex: 1, padding: 24, minHeight: 400 }}
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
                            <p style={{ marginTop: 16, color: '#475569', fontSize: '0.82rem', textAlign: 'center', maxWidth: 400 }}>
                                Descubre asociaciones ocultas saltando entre conceptos y archivos
                                a través de conexiones que normalmente pasarían desapercibidas.
                            </p>
                        </div>
                    )}

                    {loading && (
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: 360 }}>
                            <Loader2 className="animate-spin mb-4 text-amber-400" size={40} />
                            <span style={{ color: '#94a3b8' }}>Buscando camino difuso...</span>
                        </div>
                    )}

                    {generated && !loading && path.length === 0 && (
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: 360 }}>
                            <p style={{ color: '#475569', fontSize: '0.9rem', textAlign: 'center' }}>
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

                            {/* Regenerate */}
                            <div style={{ textAlign: 'center', marginTop: 16 }}>
                                <button
                                    onClick={generate}
                                    style={{
                                        padding: '10px 28px', fontSize: '0.85rem', fontWeight: 600,
                                        borderRadius: 12, border: 'none', cursor: 'pointer',
                                        background: 'linear-gradient(135deg, #f97316, #fbbf24)',
                                        color: '#fff', boxShadow: '0 2px 12px #f9731644',
                                        display: 'inline-flex', alignItems: 'center', gap: 8,
                                    }}
                                >
                                    <Dice5 size={16} /> Otro Camino
                                </button>
                            </div>

                            {/* ── Asset Detail Panel (bottom) ── */}
                            {selectedAsset && (
                                <div
                                    style={{
                                        marginTop: 24,
                                        background: '#0f172a',
                                        border: '1px solid #334155',
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
                                            background: '#1e293b',
                                            borderBottom: '1px solid #334155',
                                        }}
                                    >
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                                            <FileText size={16} className="text-amber-400" />
                                            <span style={{ fontSize: '0.9rem', fontWeight: 600, color: '#f8fafc' }}>
                                                {selectedAsset.id}
                                            </span>
                                            <span
                                                style={{
                                                    fontSize: '0.68rem', padding: '2px 8px', borderRadius: 10,
                                                    background: '#475569', color: '#e2e8f0',
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
                                                color: '#64748b', padding: 4,
                                            }}
                                        >
                                            <X size={18} />
                                        </button>
                                    </div>

                                    {/* Body */}
                                    <div style={{ padding: 20 }}>
                                        <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
                                            {/* Properties column */}
                                            <div style={{ display: 'flex', flexDirection: 'column', gap: 12, minWidth: 200, flex: '0 0 240px' }}>
                                                <div>
                                                    <div style={{ fontSize: '0.65rem', color: '#64748b', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 4 }}>
                                                        FILENAME
                                                    </div>
                                                    <div style={{ fontSize: '0.85rem', color: '#e2e8f0', wordBreak: 'break-word' }}>
                                                        {selectedAsset.id}
                                                    </div>
                                                </div>
                                                <div>
                                                    <div style={{ fontSize: '0.65rem', color: '#64748b', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 4 }}>
                                                        TIPO
                                                    </div>
                                                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#e2e8f0', fontSize: '0.85rem' }}>
                                                        {getMimeIcon(selectedAsset.mime_type)}
                                                        <span>{getMimeLabel(selectedAsset.mime_type)}</span>
                                                    </div>
                                                    {selectedAsset.mime_type && (
                                                        <div style={{ fontSize: '0.7rem', color: '#475569', marginTop: 2, fontFamily: 'monospace' }}>
                                                            {selectedAsset.mime_type}
                                                        </div>
                                                    )}
                                                </div>
                                                {selectedAsset.file_hash && (
                                                    <div>
                                                        <div style={{ fontSize: '0.65rem', color: '#64748b', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 4 }}>
                                                            HASH
                                                        </div>
                                                        <div style={{ fontSize: '0.72rem', color: '#64748b', fontFamily: 'monospace', wordBreak: 'break-all' }}>
                                                            {selectedAsset.file_hash}
                                                        </div>
                                                    </div>
                                                )}
                                                {/* Connection context */}
                                                <div style={{
                                                    background: '#1e293b', borderRadius: 8, padding: 10,
                                                    border: '1px solid #334155', fontSize: '0.78rem', color: '#94a3b8', lineHeight: 1.6
                                                }}>
                                                    Peso: <WeightBadge weight={selectedAsset.weight} />{' '}
                                                    {selectedAsset.weight !== null && selectedAsset.weight < 0.8
                                                        ? '— conexión difusa, fuente de serendipia'
                                                        : '— conexión sólida'}
                                                </div>
                                            </div>

                                            {/* Media Preview column */}
                                            <div style={{ flex: 1, minWidth: 240 }}>
                                                {(selectedAsset.download_url || selectedAsset.minio_path) ? (
                                                    <>
                                                        <div style={{ fontSize: '0.65rem', color: '#64748b', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 8 }}>
                                                            VISTA PREVIA
                                                        </div>
                                                        <MediaPreview
                                                            url={selectedAsset.download_url || undefined}
                                                            path={selectedAsset.minio_path || undefined}
                                                        />
                                                    </>
                                                ) : (
                                                    <div style={{
                                                        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                                                        height: 120, background: '#1e293b', borderRadius: 12, border: '1px dashed #334155',
                                                    }}>
                                                        <File size={28} color="#475569" />
                                                        <span style={{ fontSize: '0.75rem', color: '#475569', marginTop: 8 }}>
                                                            Vista previa no disponible
                                                        </span>
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                    )}
                </div>

                {/* Explanation Panel */}
                <div
                    className="bg-white dark:bg-slate-950 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800"
                    style={{ width: 260, padding: 20, flexShrink: 0 }}
                >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
                        <Info size={18} className="text-amber-400" />
                        <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#f8fafc', margin: 0 }}>
                            ¿Qué es esto?
                        </h3>
                    </div>

                    <p style={{ fontSize: '0.78rem', color: '#94a3b8', lineHeight: 1.7, marginBottom: 16 }}>
                        La <strong style={{ color: '#fbbf24' }}>Serendipia</strong> simula un "pensamiento lateral".
                        Encuentra rutas entre conceptos priorizando conexiones <em>difusas</em> — asociaciones
                        que normalmente pasarían desapercibidas.
                    </p>

                    <p style={{ fontSize: '0.78rem', color: '#94a3b8', lineHeight: 1.7, marginBottom: 16 }}>
                        <strong style={{ color: '#e2e8f0' }}>Haz clic</strong> en cualquier <strong style={{ color: '#e2e8f0' }}>📄 Asset</strong> del recorrido
                        para ver sus datos y vista previa en el panel inferior.
                    </p>

                    {generated && path.length > 0 && firstConcept && lastConcept && (
                        <div style={{
                            background: '#1e293b', borderRadius: 8, padding: 12, marginBottom: 16,
                            border: '1px solid #334155'
                        }}>
                            <div style={{ fontSize: '0.7rem', color: '#64748b', fontWeight: 600, marginBottom: 6 }}>
                                VIAJE ACTUAL
                            </div>
                            <p style={{ fontSize: '0.78rem', color: '#94a3b8', lineHeight: 1.6, margin: 0 }}>
                                Hemos conectado{' '}
                                <strong style={{ color: '#c4b5fd' }}>{firstConcept.id}</strong> con{' '}
                                <strong style={{ color: '#c4b5fd' }}>{lastConcept.id}</strong>.
                                Este camino fue posible gracias a asociaciones sutiles en tus archivos
                                que normalmente pasarían desapercibidas.
                            </p>
                        </div>
                    )}

                    <div style={{
                        background: '#1e293b', borderRadius: 8, padding: 12, marginBottom: 16,
                        border: '1px solid #334155'
                    }}>
                        <div style={{ fontSize: '0.7rem', color: '#64748b', fontWeight: 600, marginBottom: 8 }}>
                            LEYENDA
                        </div>
                        <div style={{ fontSize: '0.75rem', color: '#94a3b8', lineHeight: 1.8 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#7c3aed' }} />
                                <span>💡 Concepto</span>
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                <div style={{ width: 8, height: 8, borderRadius: 3, background: '#475569' }} />
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
