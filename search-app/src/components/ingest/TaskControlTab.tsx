import { useEffect, useState, useCallback, useMemo } from 'react';
import axios from 'axios';
import {
    RefreshCw, Loader2, AlertTriangle, CheckCircle2,
    Clock, Pause, Eye, XCircle, Ban, Zap,
    ChevronDown, ChevronRight, FileText, RotateCcw, Send, Filter, Table2
} from 'lucide-react';

// ==========================================
// TYPES
// ==========================================

interface VectorStatus {
    id: string;
    vector_type: string;
    status: string;
    error_message?: string;
    weaviate_uuid?: string;
}

interface Asset {
    id: string;
    filename: string;
    mime_type: string;
    privacy_level: string;
    created_at: string;
    vector_statuses: VectorStatus[];
    sidecar_data?: Record<string, any>;
}

// ==========================================
// CONSTANTS
// ==========================================

const ALL_VECTOR_TYPES = [
    'text_summary', 'visual_siglip', 'visual_semantic', 'text_ocr',
    'audio_clap', 'audio_transcript', 'text_chunk', 'user_memory', 'user_memory_required'
];

const STATUS_CONFIG: Record<string, { icon: typeof Clock; color: string; bg: string; label: string }> = {
    ON_HOLD: { icon: Pause, color: '#3b82f6', bg: '#3b82f620', label: 'On Hold' },
    PENDING: { icon: Clock, color: '#eab308', bg: '#eab30820', label: 'Pendiente' },
    PROCESSING: { icon: Loader2, color: '#f97316', bg: '#f9731620', label: 'Procesando' },
    REVIEW_REQUIRED: { icon: Eye, color: '#a855f7', bg: '#a855f720', label: 'Revisión' },
    COMPLETED: { icon: CheckCircle2, color: '#22c55e', bg: '#22c55e20', label: 'Completado' },
    FAILED: { icon: XCircle, color: '#ef4444', bg: '#ef444420', label: 'Fallido' },
    REJECTED: { icon: Ban, color: '#71717a', bg: '#71717a20', label: 'Rechazado' },
};

const MIME_ICONS: Record<string, string> = {
    'image/': '', 'audio/': '', 'video/': '', 'text/': '', 'application/pdf': ''
};

function getMimeIcon(mime: string): string {
    for (const [prefix, icon] of Object.entries(MIME_ICONS)) {
        if (mime.startsWith(prefix)) return icon;
    }
    return '';
}

// ==========================================
// STATUS BADGE COMPONENT
// ==========================================

function StatusBadge({ status }: { status: string }) {
    const config = STATUS_CONFIG[status] || { icon: Clock, color: 'var(--text-secondary)', bg: 'color-mix(in srgb, var(--text-secondary) 13%, transparent)', label: status };
    const Icon = config.icon;
    return (
        <span style={{
            display: 'inline-flex', alignItems: 'center', gap: 4,
            padding: '2px 8px', borderRadius: 6, fontSize: '0.7rem', fontWeight: 600,
            color: config.color, background: config.bg, whiteSpace: 'nowrap'
        }}>
            <Icon size={10} className={status === 'PROCESSING' ? 'animate-spin' : ''} />
            {config.label}
        </span>
    );
}

// ==========================================
// STATUS SUMMARY COMPONENT
// ==========================================

function StatusSummary({ assets }: { assets: Asset[] }) {
    const counts: Record<string, number> = {};
    for (const a of assets) {
        for (const vs of a.vector_statuses) {
            counts[vs.status] = (counts[vs.status] || 0) + 1;
        }
    }

    return (
        <div style={{
            display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(130px, 1fr))',
            gap: 12, marginBottom: 24
        }}>
            {Object.entries(STATUS_CONFIG).map(([key, cfg]) => {
                const Icon = cfg.icon;
                const count = counts[key] || 0;
                return (
                    <div key={key} style={{
                        background: cfg.bg, borderRadius: 12, padding: '16px 14px',
                        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
                        border: `1px solid ${cfg.color}30`
                    }}>
                        <Icon size={18} style={{ color: cfg.color }} />
                        <span style={{ fontSize: '1.5rem', fontWeight: 700, color: cfg.color }}>{count}</span>
                        <span style={{ fontSize: '0.7rem', color: cfg.color, opacity: 0.8, textAlign: 'center' }}>
                            {cfg.label}
                        </span>
                    </div>
                );
            })}
        </div>
    );
}

// ==========================================
// FAILED TASKS SECTION
// ==========================================

function FailedTasksSection({ assets, onRetry }: { assets: Asset[]; onRetry: () => void }) {
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
    const [retrying, setRetrying] = useState(false);
    const [expandedId, setExpandedId] = useState<string | null>(null);

    const failedTasks: { asset: string; vs: VectorStatus }[] = [];
    for (const a of assets) {
        for (const vs of a.vector_statuses) {
            if (vs.status === 'FAILED') {
                failedTasks.push({ asset: a.filename, vs });
            }
        }
    }

    if (failedTasks.length === 0) return null;

    const toggleSelect = (id: string) => {
        setSelectedIds(prev => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id); else next.add(id);
            return next;
        });
    };

    const selectAll = () => {
        if (selectedIds.size === failedTasks.length) {
            setSelectedIds(new Set());
        } else {
            setSelectedIds(new Set(failedTasks.map(f => f.vs.id)));
        }
    };

    const handleRetry = async (ids: string[]) => {
        setRetrying(true);
        try {
            await axios.post('http://localhost:8000/tasks/retry-failed', { vector_status_ids: ids });
            onRetry();
        } catch (err) {
            console.error('Retry failed', err);
        } finally {
            setRetrying(false);
        }
    };

    return (
        <div style={{
            background: '#ef444410', border: '1px solid #ef444430', borderRadius: 12,
            padding: 20, marginBottom: 24
        }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <AlertTriangle size={18} style={{ color: '#ef4444' }} />
                    <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#fca5a5' }}>
                        Tareas Fallidas ({failedTasks.length})
                    </h3>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                    <button onClick={selectAll}
                        style={{
                            padding: '6px 12px', borderRadius: 6, fontSize: '0.75rem',
                            background: '#ef444420', color: '#fca5a5', border: '1px solid #ef444430',
                            cursor: 'pointer'
                        }}>
                        {selectedIds.size === failedTasks.length ? 'Deseleccionar' : 'Seleccionar Todos'}
                    </button>
                    <button onClick={() => handleRetry(Array.from(selectedIds))} disabled={selectedIds.size === 0 || retrying}
                        style={{
                            padding: '6px 12px', borderRadius: 6, fontSize: '0.75rem',
                            background: selectedIds.size > 0 ? '#f97316' : 'var(--border)', color: '#fff',
                            border: 'none', cursor: selectedIds.size > 0 ? 'pointer' : 'not-allowed',
                            display: 'flex', alignItems: 'center', gap: 4, opacity: selectedIds.size > 0 ? 1 : 0.5
                        }}>
                        <RotateCcw size={12} /> Retry ({selectedIds.size})
                    </button>
                    <button onClick={() => handleRetry(failedTasks.map(f => f.vs.id))} disabled={retrying}
                        style={{
                            padding: '6px 12px', borderRadius: 6, fontSize: '0.75rem',
                            background: '#ef4444', color: '#fff', border: 'none', cursor: 'pointer',
                            display: 'flex', alignItems: 'center', gap: 4
                        }}>
                        <RotateCcw size={12} /> Retry TODOS
                    </button>
                </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {failedTasks.map(({ asset, vs }) => (
                    <div key={vs.id} style={{
                        background: 'var(--surface)', borderRadius: 8, border: '1px solid var(--border)', overflow: 'hidden'
                    }}>
                        <div style={{
                            display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px', cursor: 'pointer'
                        }} onClick={() => setExpandedId(expandedId === vs.id ? null : vs.id)}>
                            <input type="checkbox" checked={selectedIds.has(vs.id)}
                                onChange={() => toggleSelect(vs.id)} onClick={(e) => e.stopPropagation()}
                                style={{ accentColor: '#ef4444' }}
                            />
                            {expandedId === vs.id ? <ChevronDown size={14} style={{ color: 'var(--text-secondary)' }} />
                                : <ChevronRight size={14} style={{ color: 'var(--text-secondary)' }} />}
                            <XCircle size={14} style={{ color: '#ef4444' }} />
                            <span style={{ color: 'var(--text-primary)', fontSize: '0.85rem', fontWeight: 500 }}>{asset}</span>
                            <span style={{ color: 'var(--text-secondary)', fontSize: '0.75rem' }}>→ {vs.vector_type}</span>
                        </div>

                        {expandedId === vs.id && (
                            <div style={{ padding: '0 14px 14px 42px' }}>
                                <p style={{ color: 'var(--text-secondary)', fontSize: '0.75rem', marginBottom: 4 }}>
                                    <strong>Task ID:</strong> {vs.id}
                                </p>
                                <pre style={{
                                    background: 'var(--background-secondary)', padding: 12, borderRadius: 6, fontSize: '0.75rem',
                                    color: '#fca5a5', whiteSpace: 'pre-wrap', wordBreak: 'break-all', margin: '8px 0'
                                }}>
                                    {vs.error_message || 'No error message captured'}
                                </pre>
                                <button onClick={() => handleRetry([vs.id])} disabled={retrying}
                                    style={{
                                        padding: '4px 10px', borderRadius: 6, fontSize: '0.7rem',
                                        background: '#f97316', color: '#fff', border: 'none', cursor: 'pointer',
                                        display: 'flex', alignItems: 'center', gap: 4
                                    }}>
                                    <RotateCcw size={10} /> Retry esta tarea
                                </button>
                            </div>
                        )}
                    </div>
                ))}
            </div>
        </div>
    );
}

// ==========================================
// COLLAPSIBLE TASK MATRIX TABLE
// ==========================================

function TaskMatrix({ assets, onPrivacyChange }: { assets: Asset[], onPrivacyChange?: (assetId: string, level: string) => void }) {
    const [isOpen, setIsOpen] = useState(false);

    // Find which vector types are actually in use
    const usedVectorTypes = new Set<string>();
    for (const a of assets) {
        for (const vs of a.vector_statuses) {
            usedVectorTypes.add(vs.vector_type);
        }
    }
    const columns = ALL_VECTOR_TYPES.filter(vt => usedVectorTypes.has(vt));

    return (
        <div style={{
            marginBottom: 24, background: 'var(--surface)', borderRadius: 12,
            border: '1px solid var(--border)', overflow: 'hidden'
        }}>
            {/* Collapsible Header */}
            <div onClick={() => setIsOpen(!isOpen)}
                style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '14px 20px', cursor: 'pointer',
                    transition: 'background 0.15s'
                }}
                onMouseEnter={e => (e.currentTarget.style.background = 'var(--border)')}
                onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
            >
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    {isOpen ? <ChevronDown size={16} style={{ color: '#818cf8' }} />
                        : <ChevronRight size={16} style={{ color: '#818cf8' }} />}
                    <Table2 size={16} style={{ color: '#818cf8' }} />
                    <span style={{ color: 'var(--text-primary)', fontWeight: 600, fontSize: '0.95rem' }}>
                        Processing Matrix
                    </span>
                    <span style={{
                        padding: '2px 10px', borderRadius: 10, fontSize: '0.7rem', fontWeight: 600,
                        background: '#818cf820', color: '#818cf8'
                    }}>
                        {assets.length} assets
                    </span>
                </div>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                    {isOpen ? 'Clic para colapsar' : 'Clic para expandir'}
                </span>
            </div>

            {/* Table Content */}
            {isOpen && (
                <div style={{ overflowX: 'auto', borderTop: '1px solid var(--border)' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
                        <thead>
                            <tr style={{ background: 'var(--background-secondary)' }}>
                                <th style={thStyle}></th>
                                <th style={{ ...thStyle, textAlign: 'left', minWidth: 200 }}>Filename</th>
                                <th style={thStyle}>Privacy</th>
                                {columns.map(col => (
                                    <th key={col} style={{ ...thStyle, fontSize: '0.65rem' }}>
                                        {col.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {assets.map((asset) => {
                                const statusMap: Record<string, VectorStatus> = {};
                                for (const vs of asset.vector_statuses) {
                                    statusMap[vs.vector_type] = vs;
                                }

                                return (
                                    <tr key={asset.id}
                                        style={{
                                            borderBottom: '1px solid var(--surface)',
                                            transition: 'background 0.15s'
                                        }}
                                        onMouseEnter={e => (e.currentTarget.style.background = 'color-mix(in srgb, var(--surface) 38%, transparent)')}
                                        onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                                    >
                                        <td style={tdStyle}>{getMimeIcon(asset.mime_type)}</td>
                                        <td style={{ ...tdStyle, textAlign: 'left', fontWeight: 500, color: 'var(--text-primary)' }}>
                                            {asset.filename}
                                        </td>
                                        <td style={tdStyle}>
                                            <select
                                                value={asset.privacy_level}
                                                onChange={(e) => onPrivacyChange && onPrivacyChange(asset.id, e.target.value)}
                                                style={{
                                                    padding: '2px 8px', borderRadius: 4, fontSize: '0.7rem',
                                                    background: asset.privacy_level === 'strict_local' ? '#3b82f620' : '#eab30820',
                                                    color: asset.privacy_level === 'strict_local' ? '#60a5fa' : '#fbbf24',
                                                    border: '1px solid transparent', cursor: 'pointer', outline: 'none',
                                                    appearance: 'none', textAlign: 'center', fontWeight: 600
                                                }}
                                                title="Cambiar proveedor Local ↔ Cloud"
                                            >
                                                <option value="strict_local" style={{ background: 'var(--background-secondary)', color: '#60a5fa' }}> Local</option>
                                                <option value="public_cloud" style={{ background: 'var(--background-secondary)', color: '#fbbf24' }}> Cloud</option>
                                            </select>
                                        </td>
                                        {columns.map(col => {
                                            const vs = statusMap[col];
                                            return (
                                                <td key={col} style={{ ...tdStyle, textAlign: 'center' }}>
                                                    {vs ? <StatusBadge status={vs.status} /> : (
                                                        <span style={{ color: 'var(--border)' }}>—</span>
                                                    )}
                                                </td>
                                            );
                                        })}
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}

const thStyle: React.CSSProperties = {
    padding: '10px 12px', textAlign: 'center', fontWeight: 600, color: 'var(--text-secondary)',
    borderBottom: '1px solid var(--border)', whiteSpace: 'nowrap', fontSize: '0.75rem'
};

const tdStyle: React.CSSProperties = {
    padding: '10px 12px', textAlign: 'center', color: 'var(--text-secondary)'
};

// ==========================================
// ON_HOLD TASK LIST WITH FILTERS, SELECTORS & METADATA
// ==========================================

interface OnHoldTask {
    vsId: string;
    vectorType: string;
    assetId: string;
    filename: string;
    mimeType: string;
    privacyLevel: string;
}

interface UserContext {
    content: string;
    convert_to_memory: boolean;
}

interface AudioProcessingOptions {
    is_voice_note: boolean;
    is_song: boolean;
    has_provided_lyrics: boolean;
    provided_lyrics_text: string | null;
    use_whisper: boolean;
}

interface TaskMeta {
    user_context?: UserContext;
    audio_processing_options?: AudioProcessingOptions;
}

interface LrcResult {
    trackName: string;
    artistName: string;
    albumName: string;
    duration: number;
    instrumental: boolean;
    syncedLyrics?: string;
    plainLyrics?: string;
}

// ==========================================
// TASK METADATA PANEL (per-task)
// ==========================================

function TaskMetadataPanel({
    task,
    meta,
    onMetaChange
}: {
    task: OnHoldTask;
    meta: TaskMeta;
    onMetaChange: (vsId: string, meta: TaskMeta) => void;
}) {
    const [lrcTrack, setLrcTrack] = useState('');
    const [lrcArtist, setLrcArtist] = useState('');
    const [lrcAlbum, setLrcAlbum] = useState('');
    const [lrcResults, setLrcResults] = useState<LrcResult[]>([]);
    const [lrcSearching, setLrcSearching] = useState(false);
    const [lrcError, setLrcError] = useState<string | null>(null);

    const isTextSummary = task.vectorType === 'text_summary';
    const isAudioFile = task.mimeType.startsWith('audio/');
    const showAudioOptions = isTextSummary && isAudioFile;

    const userCtx = meta.user_context || { content: '', convert_to_memory: false };
    const audioOpts = meta.audio_processing_options || {
        is_voice_note: false, is_song: false,
        has_provided_lyrics: false, provided_lyrics_text: null, use_whisper: false
    };

    const updateUserContext = (partial: Partial<UserContext>) => {
        onMetaChange(task.vsId, {
            ...meta,
            user_context: { ...userCtx, ...partial }
        });
    };

    const updateAudioOpts = (partial: Partial<AudioProcessingOptions>) => {
        onMetaChange(task.vsId, {
            ...meta,
            audio_processing_options: { ...audioOpts, ...partial }
        });
    };

    const handleLrcSearch = async () => {
        if (!lrcTrack.trim()) { setLrcError('El nombre de la canción es obligatorio.'); return; }
        setLrcSearching(true);
        setLrcError(null);
        try {
            const params: Record<string, string> = { track_name: lrcTrack.trim() };
            if (lrcArtist.trim()) params.artist_name = lrcArtist.trim();
            if (lrcAlbum.trim()) params.album_name = lrcAlbum.trim();
            const res = await axios.get('http://localhost:8000/lyrics/search', { params, timeout: 20000 });
            setLrcResults(res.data || []);
            if ((res.data || []).length === 0) setLrcError('No se encontraron resultados.');
        } catch (err: any) {
            setLrcError(err.response?.data?.detail || err.message || 'Error de conexión');
        } finally {
            setLrcSearching(false);
        }
    };

    const useLyrics = (item: LrcResult) => {
        const lyrics = item.syncedLyrics || item.plainLyrics || '(instrumental)';
        const header = `Canción: ${item.trackName}\nArtista: ${item.artistName}\nÁlbum: ${item.albumName}\n${'='.repeat(40)}\n`;
        updateAudioOpts({
            has_provided_lyrics: true,
            provided_lyrics_text: header + lyrics,
            is_song: true
        });
        setLrcResults([]);
    };

    const inputStyle: React.CSSProperties = {
        width: '100%', padding: '8px 12px', borderRadius: 6, fontSize: '0.8rem',
        background: 'var(--background-secondary)', border: '1px solid var(--border)', color: 'var(--text-primary)',
        outline: 'none'
    };

    const checkboxLabelStyle: React.CSSProperties = {
        display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer',
        color: 'var(--text-secondary)', fontSize: '0.8rem', padding: '4px 0'
    };

    return (
        <div style={{
            padding: '12px 14px 12px 38px', borderTop: '1px solid var(--surface)',
            background: 'color-mix(in srgb, var(--background-secondary) 50%, transparent)'
        }}>
            {/* ─── User Context (for text_summary tasks) ─── */}
            {isTextSummary && (
                <div style={{ marginBottom: showAudioOptions ? 16 : 0 }}>
                    <div style={{
                        fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)',
                        marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6
                    }}>
                         Contexto del Usuario (Opcional)
                    </div>
                    <textarea
                        value={userCtx.content}
                        onChange={e => updateUserContext({ content: e.target.value })}
                        placeholder="Ej: Esta imagen es de mi viaje a París en 2020..."
                        style={{
                            ...inputStyle, minHeight: 60, resize: 'vertical',
                            fontFamily: 'inherit'
                        }}
                    />
                    <label style={{ ...checkboxLabelStyle, marginTop: 6 }}>
                        <input type="checkbox" checked={userCtx.convert_to_memory}
                            onChange={e => updateUserContext({ convert_to_memory: e.target.checked })}
                            style={{ accentColor: '#a855f7' }}
                        />
                         Convertir a memoria personal
                        <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>
                            (se guardará como memoria accesible en búsquedas)
                        </span>
                    </label>
                </div>
            )}

            {/* ─── Audio Processing Options ─── */}
            {showAudioOptions && (
                <div>
                    <div style={{
                        fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)',
                        marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6,
                        borderTop: '1px solid var(--surface)', paddingTop: 12
                    }}>
                         Opciones de Procesamiento de Audio
                    </div>

                    <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 8 }}>
                        <label style={checkboxLabelStyle}>
                            <input type="checkbox" checked={audioOpts.is_voice_note}
                                onChange={e => updateAudioOpts({ is_voice_note: e.target.checked })}
                                style={{ accentColor: '#3b82f6' }}
                            />
                             Es nota de voz
                        </label>
                        <label style={checkboxLabelStyle}>
                            <input type="checkbox" checked={audioOpts.is_song}
                                onChange={e => updateAudioOpts({ is_song: e.target.checked })}
                                style={{ accentColor: '#eab308' }}
                            />
                             Es canción
                        </label>
                        <label style={checkboxLabelStyle}>
                            <input type="checkbox" checked={audioOpts.use_whisper}
                                onChange={e => updateAudioOpts({ use_whisper: e.target.checked })}
                                style={{ accentColor: '#22c55e' }}
                            />
                             Usar Whisper (transcripción automática)
                        </label>
                    </div>

                    {/* ─── LRCLIB Lyrics Search (when is_song) ─── */}
                    {audioOpts.is_song && (
                        <div style={{
                            background: 'var(--surface)', borderRadius: 8, padding: 14,
                            border: '1px solid var(--border)', marginBottom: 10
                        }}>
                            <div style={{
                                fontSize: '0.75rem', fontWeight: 600, color: '#eab308',
                                marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6
                            }}>
                                 Buscar Letra en LRCLIB
                            </div>

                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginBottom: 10 }}>
                                <div>
                                    <label style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', display: 'block', marginBottom: 3 }}>
                                         Canción *
                                    </label>
                                    <input value={lrcTrack} onChange={e => setLrcTrack(e.target.value)}
                                        placeholder="Bohemian Rhapsody" style={inputStyle}
                                    />
                                </div>
                                <div>
                                    <label style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', display: 'block', marginBottom: 3 }}>
                                         Artista
                                    </label>
                                    <input value={lrcArtist} onChange={e => setLrcArtist(e.target.value)}
                                        placeholder="Queen" style={inputStyle}
                                    />
                                </div>
                                <div>
                                    <label style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', display: 'block', marginBottom: 3 }}>
                                         Álbum
                                    </label>
                                    <input value={lrcAlbum} onChange={e => setLrcAlbum(e.target.value)}
                                        placeholder="A Night at the Opera" style={inputStyle}
                                    />
                                </div>
                            </div>

                            <button onClick={handleLrcSearch} disabled={lrcSearching}
                                style={{
                                    padding: '6px 16px', borderRadius: 6, fontSize: '0.75rem', fontWeight: 600,
                                    background: 'var(--gradient-primary)',
                                    color: 'var(--background-secondary)', border: 'none', cursor: 'pointer',
                                    display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8
                                }}>
                                {lrcSearching
                                    ? <><Loader2 size={12} className="animate-spin" /> Buscando...</>
                                    : <> Buscar Letra</>
                                }
                            </button>

                            {lrcError && (
                                <div style={{
                                    padding: '6px 10px', borderRadius: 6, fontSize: '0.75rem',
                                    background: '#ef444415', color: '#fca5a5', border: '1px solid #ef444430',
                                    marginBottom: 8
                                }}>
                                     {lrcError}
                                </div>
                            )}

                            {/* Search Results */}
                            {lrcResults.length > 0 && (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                                    <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', fontWeight: 500 }}>
                                        Resultados ({lrcResults.length}):
                                    </span>
                                    {lrcResults.map((item, idx) => {
                                        const lyrics = item.syncedLyrics || item.plainLyrics || '';
                                        const mins = Math.floor(item.duration / 60);
                                        const secs = Math.floor(item.duration % 60);
                                        const syncBadge = item.syncedLyrics ? ' ⏱ Synced' : '';
                                        const tag = item.instrumental
                                            ? ' Instrumental'
                                            : `${lyrics.split('\n').length} líneas${syncBadge}`;

                                        return (
                                            <div key={idx} style={{
                                                background: 'var(--background-secondary)', borderRadius: 6,
                                                border: '1px solid var(--surface)', overflow: 'hidden'
                                            }}>
                                                <div style={{
                                                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                                                    padding: '8px 12px', gap: 8
                                                }}>
                                                    <div style={{ flex: 1 }}>
                                                        <span style={{ color: 'var(--text-primary)', fontSize: '0.8rem', fontWeight: 600 }}>
                                                            {item.trackName}
                                                        </span>
                                                        <span style={{ color: 'var(--text-secondary)', fontSize: '0.75rem' }}>
                                                            {' — '}{item.artistName} | {item.albumName} ({mins}:{secs.toString().padStart(2, '0')})
                                                        </span>
                                                        <span style={{
                                                            marginLeft: 6, fontSize: '0.65rem', color: 'var(--text-muted)'
                                                        }}>
                                                            {tag}
                                                        </span>
                                                    </div>
                                                    <button onClick={() => useLyrics(item)}
                                                        style={{
                                                            padding: '4px 10px', borderRadius: 4, fontSize: '0.7rem',
                                                            background: '#22c55e', color: 'var(--background-secondary)', fontWeight: 600,
                                                            border: 'none', cursor: 'pointer', whiteSpace: 'nowrap'
                                                        }}>
                                                         Usar esta
                                                    </button>
                                                </div>
                                                {lyrics && (
                                                    <pre style={{
                                                        padding: '6px 12px', fontSize: '0.65rem', color: 'var(--text-muted)',
                                                        maxHeight: 80, overflow: 'auto', margin: 0,
                                                        borderTop: '1px solid var(--surface)', whiteSpace: 'pre-wrap'
                                                    }}>
                                                        {lyrics.substring(0, 300)}{lyrics.length > 300 ? '\n...' : ''}
                                                    </pre>
                                                )}
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                        </div>
                    )}

                    {/* ─── Provided Lyrics Textarea ─── */}
                    <label style={checkboxLabelStyle}>
                        <input type="checkbox" checked={audioOpts.has_provided_lyrics}
                            onChange={e => updateAudioOpts({
                                has_provided_lyrics: e.target.checked,
                                provided_lyrics_text: e.target.checked ? audioOpts.provided_lyrics_text : null
                            })}
                            style={{ accentColor: '#a855f7' }}
                        />
                         Tengo la letra / transcripción
                    </label>

                    {audioOpts.has_provided_lyrics && (
                        <textarea
                            value={audioOpts.provided_lyrics_text || ''}
                            onChange={e => updateAudioOpts({ provided_lyrics_text: e.target.value })}
                            placeholder="Pega aquí la letra o transcripción del audio..."
                            style={{
                                ...inputStyle, minHeight: 80, resize: 'vertical',
                                fontFamily: 'monospace', fontSize: '0.75rem', marginTop: 4
                            }}
                        />
                    )}
                </div>
            )}
        </div>
    );
}

// ==========================================
// ON_HOLD TASK LIST MAIN COMPONENT
// ==========================================

function OnHoldTaskList({ assets, onDispatch, onPrivacyChange }: { assets: Asset[]; onDispatch: () => void; onPrivacyChange?: (assetId: string, level: string) => void }) {
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
    const [activeFilters, setActiveFilters] = useState<Set<string>>(new Set());
    const [dispatching, setDispatching] = useState(false);
    const [result, setResult] = useState<string | null>(null);
    const [taskMetadata, setTaskMetadata] = useState<Record<string, TaskMeta>>({});
    const [expandedTaskId, setExpandedTaskId] = useState<string | null>(null);

    // Collect all ON_HOLD tasks
    const allOnHoldTasks: OnHoldTask[] = useMemo(() => {
        const tasks: OnHoldTask[] = [];
        for (const a of assets) {
            for (const vs of a.vector_statuses) {
                if (vs.status === 'ON_HOLD') {
                    tasks.push({
                        vsId: vs.id,
                        vectorType: vs.vector_type,
                        assetId: a.id,
                        filename: a.filename,
                        mimeType: a.mime_type,
                        privacyLevel: a.privacy_level
                    });
                }
            }
        }
        return tasks;
    }, [assets]);

    // Get all unique vector types present in ON_HOLD tasks
    const availableVectorTypes = useMemo(() => {
        const types = new Set<string>();
        for (const t of allOnHoldTasks) types.add(t.vectorType);
        return Array.from(types).sort();
    }, [allOnHoldTasks]);

    // Filtered tasks: if no filters active → show all; otherwise show only matching vector types
    const filteredTasks = useMemo(() => {
        if (activeFilters.size === 0) return allOnHoldTasks;
        return allOnHoldTasks.filter(t => activeFilters.has(t.vectorType));
    }, [allOnHoldTasks, activeFilters]);

    // When filters change, clean up selection to only include visible tasks
    useEffect(() => {
        const visibleIds = new Set(filteredTasks.map(t => t.vsId));
        setSelectedIds(prev => {
            const next = new Set<string>();
            for (const id of prev) {
                if (visibleIds.has(id)) next.add(id);
            }
            return next;
        });
    }, [filteredTasks]);

    if (allOnHoldTasks.length === 0) {
        return (
            <div style={{
                padding: 20, borderRadius: 12, background: '#22c55e10',
                border: '1px solid #22c55e30', textAlign: 'center', color: '#86efac', marginBottom: 24
            }}>
                 No hay tareas en estado ON_HOLD.
            </div>
        );
    }

    const toggleFilter = (vt: string) => {
        setActiveFilters(prev => {
            const next = new Set(prev);
            if (next.has(vt)) next.delete(vt); else next.add(vt);
            return next;
        });
    };

    const toggleTask = (id: string) => {
        setSelectedIds(prev => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id); else next.add(id);
            return next;
        });
    };

    const selectAllVisible = () => {
        if (selectedIds.size === filteredTasks.length) {
            setSelectedIds(new Set());
        } else {
            setSelectedIds(new Set(filteredTasks.map(t => t.vsId)));
        }
    };

    const updateTaskMeta = (vsId: string, meta: TaskMeta) => {
        setTaskMetadata(prev => ({ ...prev, [vsId]: meta }));
    };

    // Build task_metadata payload for dispatch
    const buildTaskMetadataPayload = (ids: string[]) => {
        const metaList: any[] = [];
        for (const id of ids) {
            const meta = taskMetadata[id];
            if (!meta) continue;

            const entry: any = { vector_status_id: id };
            if (meta.user_context && (meta.user_context.content || meta.user_context.convert_to_memory)) {
                entry.user_context = {
                    content: meta.user_context.content || null,
                    convert_to_memory: meta.user_context.convert_to_memory
                };
            }
            if (meta.audio_processing_options) {
                const ao = meta.audio_processing_options;
                if (ao.is_voice_note || ao.is_song || ao.has_provided_lyrics || ao.use_whisper) {
                    entry.audio_processing_options = ao;
                }
            }
            if (Object.keys(entry).length > 1) {
                metaList.push(entry);
            }
        }
        return metaList.length > 0 ? metaList : null;
    };

    const handleDispatch = async () => {
        const idsToDispatch = Array.from(selectedIds);
        if (idsToDispatch.length === 0) return;

        setDispatching(true);
        setResult(null);
        try {
            const payload: any = { vector_status_ids: idsToDispatch };
            const metaPayload = buildTaskMetadataPayload(idsToDispatch);
            if (metaPayload) payload.task_metadata = metaPayload;

            const res = await axios.post('http://localhost:8000/tasks/dispatch', payload);
            const data = res.data;
            setResult(` ${data.tasks_updated || data.tasks_dispatched || 0} tarea(s) despachadas exitosamente!`);
            setSelectedIds(new Set());
            setTaskMetadata({});
            setTimeout(() => onDispatch(), 1500);
        } catch (err: any) {
            setResult(` Error: ${err.response?.data?.detail || err.message}`);
        } finally {
            setDispatching(false);
        }
    };

    const handleDispatchAll = async () => {
        setDispatching(true);
        setResult(null);
        try {
            const res = await axios.post('http://localhost:8000/tasks/dispatch', { dispatch_all: true });
            const data = res.data;
            setResult(` ${data.tasks_updated || data.tasks_dispatched || 0} tarea(s) despachadas exitosamente!`);
            setSelectedIds(new Set());
            setTaskMetadata({});
            setTimeout(() => onDispatch(), 1500);
        } catch (err: any) {
            setResult(` Error: ${err.response?.data?.detail || err.message}`);
        } finally {
            setDispatching(false);
        }
    };

    // Group filtered tasks by file for display
    const tasksByFile = useMemo(() => {
        const map = new Map<string, OnHoldTask[]>();
        for (const t of filteredTasks) {
            const existing = map.get(t.assetId) || [];
            existing.push(t);
            map.set(t.assetId, existing);
        }
        return map;
    }, [filteredTasks]);

    // Check if any selected task has metadata
    const selectedHaveMeta = Array.from(selectedIds).some(id => {
        const m = taskMetadata[id];
        if (!m) return false;
        if (m.user_context?.content || m.user_context?.convert_to_memory) return true;
        const ao = m.audio_processing_options;
        if (ao && (ao.is_voice_note || ao.is_song || ao.has_provided_lyrics || ao.use_whisper)) return true;
        return false;
    });

    return (
        <div style={{
            background: 'var(--surface)', borderRadius: 12, border: '1px solid var(--border)',
            padding: 20, marginBottom: 24
        }}>
            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Pause size={18} style={{ color: '#3b82f6' }} />
                    <h3 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                        Tareas ON_HOLD
                    </h3>
                    <span style={{
                        padding: '2px 10px', borderRadius: 10, fontSize: '0.7rem', fontWeight: 600,
                        background: '#3b82f620', color: '#60a5fa'
                    }}>
                        {filteredTasks.length} de {allOnHoldTasks.length}
                    </span>
                </div>
            </div>

            {/* Vector Type Filter Bar */}
            <div style={{ marginBottom: 16 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                    <Filter size={14} style={{ color: 'var(--text-secondary)' }} />
                    <span style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', fontWeight: 500 }}>
                        Filtrar por tipo de vector:
                    </span>
                    {activeFilters.size > 0 && (
                        <button onClick={() => setActiveFilters(new Set())}
                            style={{
                                padding: '2px 8px', borderRadius: 4, fontSize: '0.65rem',
                                background: '#ef444420', color: '#fca5a5', border: '1px solid #ef444430',
                                cursor: 'pointer'
                            }}>
                             Limpiar filtros
                        </button>
                    )}
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {availableVectorTypes.map(vt => {
                        const isActive = activeFilters.has(vt);
                        const countForType = allOnHoldTasks.filter(t => t.vectorType === vt).length;
                        return (
                            <button key={vt} onClick={() => toggleFilter(vt)}
                                style={{
                                    padding: '5px 12px', borderRadius: 8, fontSize: '0.75rem', fontWeight: 500,
                                    background: isActive ? '#6366f130' : 'var(--background-secondary)',
                                    color: isActive ? '#a5b4fc' : 'var(--text-muted)',
                                    border: `1px solid ${isActive ? '#6366f150' : 'var(--border)'}`,
                                    cursor: 'pointer', transition: 'all 0.15s',
                                    display: 'flex', alignItems: 'center', gap: 6
                                }}>
                                {vt.replace(/_/g, ' ')}
                                <span style={{
                                    padding: '0 5px', borderRadius: 4, fontSize: '0.65rem',
                                    background: isActive ? '#6366f140' : 'var(--surface)',
                                    color: isActive ? '#c7d2fe' : 'var(--text-muted)'
                                }}>
                                    {countForType}
                                </span>
                            </button>
                        );
                    })}
                </div>
            </div>

            {/* Select All + Dispatch Controls */}
            <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '10px 14px', borderRadius: 8, background: 'var(--background-secondary)',
                marginBottom: 12, border: '1px solid var(--surface)', flexWrap: 'wrap', gap: 8
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
                        <input type="checkbox"
                            checked={selectedIds.size === filteredTasks.length && filteredTasks.length > 0}
                            onChange={selectAllVisible}
                            style={{ accentColor: '#818cf8' }}
                        />
                        <span style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>
                            Seleccionar todas ({filteredTasks.length})
                        </span>
                    </label>
                    <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                        |  {selectedIds.size} seleccionada(s)
                    </span>
                    {selectedHaveMeta && (
                        <span style={{
                            padding: '2px 8px', borderRadius: 4, fontSize: '0.65rem',
                            background: '#a855f720', color: '#c4b5fd'
                        }}>
                             con metadatos
                        </span>
                    )}
                </div>

                <div style={{ display: 'flex', gap: 8 }}>
                    <button onClick={handleDispatchAll} disabled={dispatching}
                        style={{
                            padding: '6px 14px', borderRadius: 6, fontSize: '0.75rem',
                            background: 'var(--border)', color: 'var(--text-secondary)', border: '1px solid var(--text-muted)',
                            cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4
                        }}>
                        <Zap size={12} /> Dispatch TODAS ({allOnHoldTasks.length})
                    </button>
                    <button onClick={handleDispatch} disabled={selectedIds.size === 0 || dispatching}
                        style={{
                            padding: '6px 14px', borderRadius: 6, fontSize: '0.75rem', fontWeight: 600,
                            background: selectedIds.size > 0
                                ? 'var(--gradient-primary)' : 'var(--border)',
                            color: '#fff', border: 'none',
                            cursor: selectedIds.size > 0 ? 'pointer' : 'not-allowed',
                            display: 'flex', alignItems: 'center', gap: 4,
                            opacity: selectedIds.size > 0 ? 1 : 0.5,
                            boxShadow: selectedIds.size > 0 ? '0 2px 8px rgba(99,102,241,0.3)' : 'none'
                        }}>
                        {dispatching
                            ? <><Loader2 size={12} className="animate-spin" /> Despachando...</>
                            : <><Send size={12} /> Dispatch {selectedIds.size} seleccionada(s)</>
                        }
                    </button>
                </div>
            </div>

            {/* Task List grouped by File */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {Array.from(tasksByFile.entries()).map(([assetId, tasks]) => {
                    const first = tasks[0];
                    const allSelected = tasks.every(t => selectedIds.has(t.vsId));
                    const someSelected = tasks.some(t => selectedIds.has(t.vsId));

                    const toggleFileGroup = () => {
                        setSelectedIds(prev => {
                            const next = new Set(prev);
                            if (allSelected) {
                                for (const t of tasks) next.delete(t.vsId);
                            } else {
                                for (const t of tasks) next.add(t.vsId);
                            }
                            return next;
                        });
                    };

                    return (
                        <div key={assetId} style={{
                            background: 'var(--background-secondary)', borderRadius: 8, border: '1px solid var(--surface)',
                            overflow: 'hidden'
                        }}>
                            {/* File header */}
                            <div style={{
                                display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px',
                                borderBottom: '1px solid var(--surface)'
                            }}>
                                <input type="checkbox"
                                    checked={allSelected}
                                    ref={(el) => { if (el) el.indeterminate = someSelected && !allSelected; }}
                                    onChange={toggleFileGroup}
                                    style={{ accentColor: '#818cf8' }}
                                />
                                <span style={{ fontSize: '1rem' }}>{getMimeIcon(first.mimeType)}</span>
                                <span style={{ color: 'var(--text-primary)', fontSize: '0.85rem', fontWeight: 600 }}>
                                    {first.filename}
                                </span>
                                <select
                                    value={first.privacyLevel}
                                    onChange={(e) => onPrivacyChange && onPrivacyChange(assetId, e.target.value)}
                                    onClick={(e) => e.stopPropagation()}
                                    style={{
                                        padding: '1px 8px', borderRadius: 4, fontSize: '0.65rem',
                                        background: first.privacyLevel === 'strict_local' ? '#3b82f620' : '#eab30820',
                                        color: first.privacyLevel === 'strict_local' ? '#60a5fa' : '#fbbf24',
                                        border: '1px solid transparent', cursor: 'pointer', outline: 'none',
                                        appearance: 'none', textAlign: 'center', fontWeight: 600
                                    }}
                                    title="Cambiar proveedor Local ↔ Cloud"
                                >
                                    <option value="strict_local" style={{ background: 'var(--background-secondary)', color: '#60a5fa' }}> Local</option>
                                    <option value="public_cloud" style={{ background: 'var(--background-secondary)', color: '#fbbf24' }}> Cloud</option>
                                </select>
                                <span style={{
                                    marginLeft: 'auto', color: 'var(--text-muted)', fontSize: '0.7rem'
                                }}>
                                    {tasks.length} tarea(s)
                                </span>
                            </div>

                            {/* Individual tasks */}
                            {tasks.map(task => {
                                const isSelected = selectedIds.has(task.vsId);
                                const isExpanded = expandedTaskId === task.vsId;
                                const isTextSummary = task.vectorType === 'text_summary';
                                const hasMeta = (() => {
                                    const m = taskMetadata[task.vsId];
                                    if (!m) return false;
                                    if (m.user_context?.content || m.user_context?.convert_to_memory) return true;
                                    const ao = m.audio_processing_options;
                                    return !!(ao && (ao.is_voice_note || ao.is_song || ao.has_provided_lyrics || ao.use_whisper));
                                })();

                                return (
                                    <div key={task.vsId}>
                                        <div
                                            style={{
                                                display: 'flex', alignItems: 'center', gap: 10,
                                                padding: '8px 14px 8px 38px', cursor: 'pointer',
                                                borderBottom: '1px solid color-mix(in srgb, var(--surface) 6%, transparent)',
                                                transition: 'background 0.1s',
                                                background: isExpanded ? 'color-mix(in srgb, var(--surface) 19%, transparent)' : 'transparent'
                                            }}
                                            onMouseEnter={e => { if (!isExpanded) e.currentTarget.style.background = 'color-mix(in srgb, var(--surface) 25%, transparent)'; }}
                                            onMouseLeave={e => { if (!isExpanded) e.currentTarget.style.background = 'transparent'; }}
                                        >
                                            <input type="checkbox"
                                                checked={isSelected}
                                                onChange={() => toggleTask(task.vsId)}
                                                style={{ accentColor: '#818cf8' }}
                                            />
                                            <Pause size={12} style={{ color: '#3b82f6' }} />
                                            <span style={{
                                                color: 'var(--text-secondary)', fontSize: '0.8rem',
                                                padding: '2px 8px', borderRadius: 4,
                                                background: 'var(--surface)', border: '1px solid var(--border)'
                                            }}>
                                                {task.vectorType.replace(/_/g, ' ')}
                                            </span>

                                            {hasMeta && (
                                                <span style={{
                                                    padding: '1px 6px', borderRadius: 4, fontSize: '0.6rem',
                                                    background: '#a855f720', color: '#c4b5fd'
                                                }}>
                                                     meta
                                                </span>
                                            )}

                                            <span style={{ flex: 1 }} />

                                            {/* Expand button for text_summary tasks */}
                                            {isTextSummary && (
                                                <button
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        setExpandedTaskId(isExpanded ? null : task.vsId);
                                                    }}
                                                    style={{
                                                        padding: '2px 8px', borderRadius: 4, fontSize: '0.65rem',
                                                        background: isExpanded ? '#818cf830' : 'var(--border)',
                                                        color: isExpanded ? '#a5b4fc' : 'var(--text-muted)',
                                                        border: `1px solid ${isExpanded ? '#818cf850' : 'var(--text-muted)'}`,
                                                        cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4
                                                    }}>
                                                    {isExpanded ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
                                                     Opciones
                                                </button>
                                            )}

                                            <span style={{ color: 'var(--text-muted)', fontSize: '0.65rem' }}>
                                                {task.vsId.substring(0, 8)}...
                                            </span>
                                        </div>

                                        {/* Metadata Panel */}
                                        {isExpanded && isTextSummary && (
                                            <TaskMetadataPanel
                                                task={task}
                                                meta={taskMetadata[task.vsId] || {}}
                                                onMetaChange={updateTaskMeta}
                                            />
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    );
                })}
            </div>

            {/* Result message */}
            {result && (
                <div style={{
                    padding: '10px 14px', borderRadius: 8, fontSize: '0.85rem', marginTop: 12,
                    background: result.startsWith('') ? '#22c55e15' : '#ef444415',
                    color: result.startsWith('') ? '#86efac' : '#fca5a5',
                    border: `1px solid ${result.startsWith('') ? '#22c55e30' : '#ef444430'}`
                }}>
                    {result}
                </div>
            )}
        </div>
    );
}

// ==========================================
// COMPLETED TASKS SECTION
// ==========================================

function CompletedSection({ assets }: { assets: Asset[] }) {
    const [open, setOpen] = useState(false);
    const completed: { asset: string; vt: string; uuid: string }[] = [];
    for (const a of assets) {
        for (const vs of a.vector_statuses) {
            if (vs.status === 'COMPLETED') {
                completed.push({ asset: a.filename, vt: vs.vector_type, uuid: vs.weaviate_uuid || '—' });
            }
        }
    }
    if (completed.length === 0) return null;

    return (
        <div style={{
            background: '#22c55e08', border: '1px solid #22c55e20', borderRadius: 12,
            padding: '14px 20px', marginBottom: 24
        }}>
            <div onClick={() => setOpen(!open)}
                style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                <CheckCircle2 size={16} style={{ color: '#22c55e' }} />
                <span style={{ color: '#86efac', fontWeight: 600, fontSize: '0.9rem' }}>
                    Tareas Completadas ({completed.length})
                </span>
            </div>
            {open && (
                <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 4 }}>
                    {completed.slice(0, 30).map((c, i) => (
                        <div key={i} style={{ color: 'var(--text-secondary)', fontSize: '0.75rem' }}>
                            • <strong style={{ color: 'var(--text-secondary)' }}>{c.asset}</strong> → {c.vt}
                            <span style={{ color: '#4ade80', marginLeft: 8 }}>Weaviate: {c.uuid.substring(0, 12)}...</span>
                        </div>
                    ))}
                    {completed.length > 30 && (
                        <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>... y {completed.length - 30} más</span>
                    )}
                </div>
            )}
        </div>
    );
}

// ==========================================
// MAIN COMPONENT
// ==========================================

export default function TaskControlTab() {
    const [assets, setAssets] = useState<Asset[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchAssets = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await axios.get<Asset[]>('http://localhost:8000/tasks/assets-with-tasks');
            setAssets(Array.isArray(res.data) ? res.data : []);
        } catch (err: any) {
            console.error(err);
            setError(err.message || 'Cannot connect to backend');
        } finally {
            setLoading(false);
        }
    }, []);

    const handlePrivacyChange = async (assetId: string, newPrivacyLevel: string) => {
        try {
            await axios.put(`http://localhost:8000/tasks/asset/${assetId}/privacy`, { privacy_level: newPrivacyLevel });

            // Optimistic update
            setAssets(prev => prev.map(a =>
                a.id === assetId ? { ...a, privacy_level: newPrivacyLevel } : a
            ));
        } catch (err: any) {
            console.error("Failed to update privacy level:", err);
            alert("Error al actualizar la privacidad: " + (err.response?.data?.detail || err.message));
        }
    };

    useEffect(() => {
        fetchAssets();
    }, [fetchAssets]);

    if (loading) {
        return (
            <div style={{
                display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                minHeight: 400, gap: 12, color: 'var(--text-secondary)'
            }}>
                <Loader2 size={32} className="animate-spin" style={{ color: '#818cf8' }} />
                <p>Cargando tareas desde el backend...</p>
            </div>
        );
    }

    if (error) {
        return (
            <div style={{
                padding: 32, borderRadius: 12, background: '#ef444410', border: '1px solid #ef444430',
                textAlign: 'center', color: '#fca5a5'
            }}>
                <AlertTriangle size={32} style={{ marginBottom: 12, color: '#ef4444' }} />
                <h3 style={{ marginBottom: 8 }}>No se pudo conectar al backend</h3>
                <p style={{ fontSize: '0.85rem', marginBottom: 16 }}>{error}</p>
                <code style={{
                    display: 'block', background: 'var(--background-secondary)', padding: 8, borderRadius: 6,
                    fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: 16
                }}>
                    Backend URL: http://localhost:8000/tasks/assets-with-tasks
                </code>
                <button onClick={fetchAssets}
                    style={{
                        padding: '8px 20px', borderRadius: 8, background: '#ef4444', color: '#fff',
                        border: 'none', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 6
                    }}>
                    <RefreshCw size={14} /> Reintentar
                </button>
            </div>
        );
    }

    if (assets.length === 0) {
        return (
            <div style={{
                padding: 32, borderRadius: 12, background: '#22c55e08', border: '1px solid #22c55e20',
                textAlign: 'center', color: '#86efac'
            }}>
                 No hay assets con tareas registradas. Ingesta archivos primero.
            </div>
        );
    }

    return (
        <div>
            {/* Header with refresh */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
                <div>
                    <h2 style={{
                        fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-primary, var(--text-primary))',
                        marginBottom: 4
                    }}>
                         Dashboard de Tareas
                    </h2>
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                        Vista de assets, filtros por tipo de vector y control de dispatch.
                    </p>
                </div>
                <button onClick={fetchAssets}
                    style={{
                        display: 'flex', alignItems: 'center', gap: 6, padding: '8px 16px',
                        borderRadius: 8, background: 'var(--border)', color: 'var(--text-secondary)', border: '1px solid var(--text-muted)',
                        cursor: 'pointer', fontSize: '0.8rem'
                    }}>
                    <RefreshCw size={14} /> Refresh
                </button>
            </div>

            {/* Status Summary */}
            <StatusSummary assets={assets} />

            {/* Failed Tasks */}
            <FailedTasksSection assets={assets} onRetry={fetchAssets} />

            {/* ON_HOLD Task List with Filters & Selection */}
            <OnHoldTaskList assets={assets} onDispatch={fetchAssets} onPrivacyChange={handlePrivacyChange} />

            {/* Collapsible Processing Matrix */}
            <TaskMatrix assets={assets} onPrivacyChange={handlePrivacyChange} />

            {/* Completed */}
            <CompletedSection assets={assets} />
        </div>
    );
}
