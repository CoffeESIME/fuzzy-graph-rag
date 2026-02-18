import { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import {
    RefreshCw, Loader2, AlertTriangle, CheckCircle2,
    Clock, Pause, Eye, XCircle, Ban, Zap,
    ChevronDown, ChevronRight, FileText, RotateCcw, Send
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
    'image/': '🖼️', 'audio/': '🎵', 'video/': '🎬', 'text/': '📝', 'application/pdf': '📄'
};

function getMimeIcon(mime: string): string {
    for (const [prefix, icon] of Object.entries(MIME_ICONS)) {
        if (mime.startsWith(prefix)) return icon;
    }
    return '📎';
}

// ==========================================
// STATUS BADGE COMPONENT
// ==========================================

function StatusBadge({ status }: { status: string }) {
    const config = STATUS_CONFIG[status] || { icon: Clock, color: '#94a3b8', bg: '#94a3b820', label: status };
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
                            background: selectedIds.size > 0 ? '#f97316' : '#334155', color: '#fff',
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
                        background: '#1e293b', borderRadius: 8, border: '1px solid #334155', overflow: 'hidden'
                    }}>
                        <div style={{
                            display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px', cursor: 'pointer'
                        }} onClick={() => setExpandedId(expandedId === vs.id ? null : vs.id)}>
                            <input type="checkbox" checked={selectedIds.has(vs.id)}
                                onChange={() => toggleSelect(vs.id)} onClick={(e) => e.stopPropagation()}
                                style={{ accentColor: '#ef4444' }}
                            />
                            {expandedId === vs.id ? <ChevronDown size={14} style={{ color: '#94a3b8' }} />
                                : <ChevronRight size={14} style={{ color: '#94a3b8' }} />}
                            <XCircle size={14} style={{ color: '#ef4444' }} />
                            <span style={{ color: '#f8fafc', fontSize: '0.85rem', fontWeight: 500 }}>{asset}</span>
                            <span style={{ color: '#94a3b8', fontSize: '0.75rem' }}>→ {vs.vector_type}</span>
                        </div>

                        {expandedId === vs.id && (
                            <div style={{ padding: '0 14px 14px 42px' }}>
                                <p style={{ color: '#94a3b8', fontSize: '0.75rem', marginBottom: 4 }}>
                                    <strong>Task ID:</strong> {vs.id}
                                </p>
                                <pre style={{
                                    background: '#0f172a', padding: 12, borderRadius: 6, fontSize: '0.75rem',
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
// TASK MATRIX TABLE
// ==========================================

function TaskMatrix({ assets }: { assets: Asset[] }) {
    const [expandedAssetId, setExpandedAssetId] = useState<string | null>(null);

    // Find which vector types are actually in use
    const usedVectorTypes = new Set<string>();
    for (const a of assets) {
        for (const vs of a.vector_statuses) {
            usedVectorTypes.add(vs.vector_type);
        }
    }
    const columns = ALL_VECTOR_TYPES.filter(vt => usedVectorTypes.has(vt));

    return (
        <div style={{ marginBottom: 24 }}>
            <h3 style={{
                fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary, #f8fafc)',
                marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8
            }}>
                <FileText size={16} style={{ color: '#818cf8' }} />
                Processing Matrix ({assets.length} assets)
            </h3>

            <div style={{ overflowX: 'auto', borderRadius: 12, border: '1px solid var(--border-subtle, #1e293b)' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
                    <thead>
                        <tr style={{ background: '#1e293b' }}>
                            <th style={thStyle}>📎</th>
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
                            const isExpanded = expandedAssetId === asset.id;

                            return (
                                <tr key={asset.id}
                                    onClick={() => setExpandedAssetId(isExpanded ? null : asset.id)}
                                    style={{
                                        background: isExpanded ? '#1e293b40' : 'transparent',
                                        cursor: 'pointer', borderBottom: '1px solid #1e293b',
                                        transition: 'background 0.15s'
                                    }}
                                    onMouseEnter={e => (e.currentTarget.style.background = '#1e293b60')}
                                    onMouseLeave={e => (e.currentTarget.style.background = isExpanded ? '#1e293b40' : 'transparent')}
                                >
                                    <td style={tdStyle}>{getMimeIcon(asset.mime_type)}</td>
                                    <td style={{ ...tdStyle, textAlign: 'left', fontWeight: 500, color: '#f8fafc' }}>
                                        {asset.filename}
                                    </td>
                                    <td style={tdStyle}>
                                        <span style={{
                                            padding: '2px 8px', borderRadius: 4, fontSize: '0.7rem',
                                            background: asset.privacy_level === 'strict_local' ? '#3b82f620' : '#eab30820',
                                            color: asset.privacy_level === 'strict_local' ? '#60a5fa' : '#fbbf24'
                                        }}>
                                            {asset.privacy_level === 'strict_local' ? '🔒 Local' : '☁️ Cloud'}
                                        </span>
                                    </td>
                                    {columns.map(col => {
                                        const vs = statusMap[col];
                                        return (
                                            <td key={col} style={{ ...tdStyle, textAlign: 'center' }}>
                                                {vs ? <StatusBadge status={vs.status} /> : (
                                                    <span style={{ color: '#334155' }}>—</span>
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
        </div>
    );
}

const thStyle: React.CSSProperties = {
    padding: '10px 12px', textAlign: 'center', fontWeight: 600, color: '#94a3b8',
    borderBottom: '1px solid #334155', whiteSpace: 'nowrap', fontSize: '0.75rem'
};

const tdStyle: React.CSSProperties = {
    padding: '10px 12px', textAlign: 'center', color: '#cbd5e1'
};

// ==========================================
// DISPATCH SECTION
// ==========================================

function DispatchSection({ assets, onDispatch }: { assets: Asset[]; onDispatch: () => void }) {
    const [dispatching, setDispatching] = useState(false);
    const [dispatchAll, setDispatchAll] = useState(false);
    const [result, setResult] = useState<string | null>(null);

    const onHoldIds: string[] = [];
    for (const a of assets) {
        for (const vs of a.vector_statuses) {
            if (vs.status === 'ON_HOLD') onHoldIds.push(vs.id);
        }
    }

    if (onHoldIds.length === 0) {
        return (
            <div style={{
                padding: 20, borderRadius: 12, background: '#22c55e10',
                border: '1px solid #22c55e30', textAlign: 'center', color: '#86efac'
            }}>
                ✨ No hay tareas en estado ON_HOLD.
            </div>
        );
    }

    const handleDispatch = async () => {
        setDispatching(true);
        setResult(null);
        try {
            const payload = dispatchAll
                ? { dispatch_all: true }
                : { vector_status_ids: onHoldIds };

            const res = await axios.post('http://localhost:8000/tasks/dispatch', payload);
            const data = res.data;
            setResult(`✅ ${data.tasks_updated || data.tasks_dispatched || 0} tarea(s) despachadas exitosamente!`);
            setTimeout(() => onDispatch(), 1500);
        } catch (err: any) {
            setResult(`❌ Error: ${err.response?.data?.detail || err.message}`);
        } finally {
            setDispatching(false);
        }
    };

    return (
        <div style={{
            background: '#1e293b', borderRadius: 12, padding: 20,
            border: '1px solid #334155', marginBottom: 24
        }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                <div>
                    <h3 style={{
                        fontSize: '1rem', fontWeight: 600, color: '#f8fafc',
                        display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4
                    }}>
                        <Zap size={16} style={{ color: '#eab308' }} />
                        Dispatch Jobs
                    </h3>
                    <p style={{ color: '#94a3b8', fontSize: '0.8rem' }}>
                        {onHoldIds.length} tarea(s) en ON_HOLD listas para procesar.
                    </p>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <label style={{
                        display: 'flex', alignItems: 'center', gap: 6, color: '#94a3b8',
                        fontSize: '0.8rem', cursor: 'pointer'
                    }}>
                        <input type="checkbox" checked={dispatchAll}
                            onChange={(e) => setDispatchAll(e.target.checked)}
                            style={{ accentColor: '#818cf8' }}
                        />
                        Dispatch todas
                    </label>

                    <button onClick={handleDispatch} disabled={dispatching}
                        style={{
                            display: 'flex', alignItems: 'center', gap: 6, padding: '10px 24px',
                            borderRadius: 8, fontWeight: 600, fontSize: '0.85rem',
                            background: dispatching ? '#334155' : 'linear-gradient(135deg, #6366f1, #818cf8)',
                            color: '#fff', border: 'none', cursor: dispatching ? 'not-allowed' : 'pointer',
                            boxShadow: dispatching ? 'none' : '0 4px 12px rgba(99, 102, 241, 0.3)'
                        }}>
                        {dispatching
                            ? <><Loader2 size={14} className="animate-spin" /> Despachando...</>
                            : <><Send size={14} /> Dispatch {onHoldIds.length} tareas</>
                        }
                    </button>
                </div>
            </div>

            {result && (
                <div style={{
                    padding: '10px 14px', borderRadius: 8, fontSize: '0.85rem', marginTop: 8,
                    background: result.startsWith('✅') ? '#22c55e15' : '#ef444415',
                    color: result.startsWith('✅') ? '#86efac' : '#fca5a5',
                    border: `1px solid ${result.startsWith('✅') ? '#22c55e30' : '#ef444430'}`
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
                        <div key={i} style={{ color: '#94a3b8', fontSize: '0.75rem' }}>
                            • <strong style={{ color: '#cbd5e1' }}>{c.asset}</strong> → {c.vt}
                            <span style={{ color: '#4ade80', marginLeft: 8 }}>Weaviate: {c.uuid.substring(0, 12)}...</span>
                        </div>
                    ))}
                    {completed.length > 30 && (
                        <span style={{ color: '#64748b', fontSize: '0.7rem' }}>... y {completed.length - 30} más</span>
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

    useEffect(() => {
        fetchAssets();
    }, [fetchAssets]);

    if (loading) {
        return (
            <div style={{
                display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                minHeight: 400, gap: 12, color: '#94a3b8'
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
                    display: 'block', background: '#0f172a', padding: 8, borderRadius: 6,
                    fontSize: '0.75rem', color: '#94a3b8', marginBottom: 16
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
                ✨ No hay assets con tareas registradas. Ingesta archivos primero.
            </div>
        );
    }

    return (
        <div>
            {/* Header with refresh */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
                <div>
                    <h2 style={{
                        fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-primary, #f8fafc)',
                        marginBottom: 4
                    }}>
                        📊 Dashboard de Tareas
                    </h2>
                    <p style={{ color: '#94a3b8', fontSize: '0.85rem' }}>
                        Vista en matriz de assets y sus estados de procesamiento de vectores.
                    </p>
                </div>
                <button onClick={fetchAssets}
                    style={{
                        display: 'flex', alignItems: 'center', gap: 6, padding: '8px 16px',
                        borderRadius: 8, background: '#334155', color: '#94a3b8', border: '1px solid #475569',
                        cursor: 'pointer', fontSize: '0.8rem'
                    }}>
                    <RefreshCw size={14} /> Refresh
                </button>
            </div>

            {/* Status Summary */}
            <StatusSummary assets={assets} />

            {/* Failed Tasks */}
            <FailedTasksSection assets={assets} onRetry={fetchAssets} />

            {/* Processing Matrix */}
            <TaskMatrix assets={assets} />

            {/* Dispatch */}
            <DispatchSection assets={assets} onDispatch={fetchAssets} />

            {/* Completed */}
            <CompletedSection assets={assets} />
        </div>
    );
}
