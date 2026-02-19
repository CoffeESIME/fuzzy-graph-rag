import { useEffect, useState, useCallback, useMemo } from 'react';
import axios from 'axios';
import {
    RefreshCw, Loader2, AlertTriangle,
    Clock, Eye, XCircle, ChevronDown, ChevronRight,
    RotateCcw, Check, Edit3, Save, X
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
    vector_statuses: VectorStatus[];
    sidecar_data?: Record<string, any>;
}

interface ReviewTask {
    vsId: string;
    vectorType: string;
    status: string;
    errorMessage?: string;
    assetId: string;
    filename: string;
    mimeType: string;
    sidecarData?: Record<string, any>;
}

// ==========================================
// CONSTANTS
// ==========================================

const STATUS_CONFIG: Record<string, { icon: typeof Eye; color: string; bg: string; label: string }> = {
    REVIEW_REQUIRED: { icon: Eye, color: '#a855f7', bg: '#a855f720', label: 'Revisión' },
    FAILED: { icon: XCircle, color: '#ef4444', bg: '#ef444420', label: 'Fallido' },
};

const API = 'http://localhost:8000';

// ==========================================
// ERROR HINT HELPER
// ==========================================

function getErrorHint(error: string): string | null {
    const lower = error.toLowerCase();
    if (lower.includes('connection') || lower.includes('refused'))
        return '💡 Error de conexión. Verifica que los servicios estén corriendo.';
    if (lower.includes('minio'))
        return '💡 Error de MinIO. Verifica el bucket y las credenciales.';
    if (lower.includes('timeout'))
        return '💡 Timeout. El archivo puede ser demasiado grande o el servidor lento.';
    if (lower.includes('weaviate'))
        return '💡 Error de Weaviate. Verifica que el servicio esté disponible.';
    return null;
}

// ==========================================
// STRUCTURED SIDECAR EDITOR COMPONENT
// ==========================================

// --- Shared styles ---
const fieldLabelStyle: React.CSSProperties = {
    color: '#94a3b8', fontSize: '0.7rem', fontWeight: 600, display: 'block', marginBottom: 3
};
const fieldValueStyle: React.CSSProperties = {
    color: '#cbd5e1', fontSize: '0.75rem'
};
const badgeStyle = (color: string): React.CSSProperties => ({
    display: 'inline-flex', alignItems: 'center', gap: 3,
    padding: '2px 8px', borderRadius: 4, fontSize: '0.65rem', fontWeight: 600,
    color, background: `${color}20`, border: `1px solid ${color}30`
});
const sectionHeaderStyle: React.CSSProperties = {
    display: 'flex', alignItems: 'center', gap: 6, padding: '6px 0',
    cursor: 'pointer', fontSize: '0.8rem', fontWeight: 600, color: '#e2e8f0',
    userSelect: 'none'
};
const inputFieldStyle: React.CSSProperties = {
    width: '100%', padding: '6px 10px', borderRadius: 4, fontSize: '0.75rem',
    background: '#0f172a', border: '1px solid #334155', color: '#f8fafc', outline: 'none'
};

// --- Collapsible Section ---
function SidecarSection_({ title, icon, children, defaultOpen = false }: {
    title: string; icon: string; children: React.ReactNode; defaultOpen?: boolean;
}) {
    const [open, setOpen] = useState(defaultOpen);
    return (
        <div style={{ borderBottom: '1px solid #1e293b', paddingBottom: 8, marginBottom: 8 }}>
            <div style={sectionHeaderStyle} onClick={() => setOpen(!open)}>
                {open ? <ChevronDown size={12} style={{ color: '#818cf8' }} />
                    : <ChevronRight size={12} style={{ color: '#818cf8' }} />}
                <span>{icon} {title}</span>
            </div>
            {open && <div style={{ paddingLeft: 20, paddingTop: 4 }}>{children}</div>}
        </div>
    );
}

// --- Read-only key/value row ---
function InfoRow({ label, value, mono = false }: { label: string; value: React.ReactNode; mono?: boolean }) {
    return (
        <div style={{ marginBottom: 4 }}>
            <span style={fieldLabelStyle}>{label}</span>
            <span style={{ ...fieldValueStyle, ...(mono ? { fontFamily: 'monospace', fontSize: '0.7rem' } : {}) }}>
                {value ?? <span style={{ color: '#475569', fontStyle: 'italic' }}>N/A</span>}
            </span>
        </div>
    );
}

// --- Editable text field ---
function EditableField({ label, value, onChange, multiline = false, placeholder }: {
    label: string; value: string; onChange: (v: string) => void; multiline?: boolean; placeholder?: string;
}) {
    return (
        <div style={{ marginBottom: 8 }}>
            <label style={fieldLabelStyle}>{label}</label>
            {multiline ? (
                <textarea value={value} onChange={e => onChange(e.target.value)}
                    placeholder={placeholder}
                    style={{ ...inputFieldStyle, minHeight: 50, resize: 'vertical', fontFamily: 'inherit' }} />
            ) : (
                <input value={value} onChange={e => onChange(e.target.value)}
                    placeholder={placeholder} style={inputFieldStyle} />
            )}
        </div>
    );
}

// --- Main Structured Editor ---
function SidecarEditor({ assetId, sidecar, onSaved }: {
    assetId: string;
    sidecar: Record<string, any>;
    onSaved: () => void;
}) {
    const [isEditing, setIsEditing] = useState(false);
    const [draft, setDraft] = useState<Record<string, any>>({});
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [showRawJson, setShowRawJson] = useState(false);
    const [rawJsonText, setRawJsonText] = useState('');
    const [rawJsonError, setRawJsonError] = useState<string | null>(null);

    // Derive current data (draft when editing, sidecar when not)
    const data = isEditing ? draft : sidecar;

    const startEdit = () => {
        setDraft(JSON.parse(JSON.stringify(sidecar))); // deep clone
        setIsEditing(true);
        setError(null);
        setShowRawJson(false);
    };

    const cancelEdit = () => {
        setIsEditing(false);
        setShowRawJson(false);
        setRawJsonError(null);
    };

    // Deeply set a nested path value
    const setField = (path: string, value: any) => {
        setDraft(prev => {
            const next = JSON.parse(JSON.stringify(prev));
            const keys = path.split('.');
            let obj = next;
            for (let i = 0; i < keys.length - 1; i++) {
                if (obj[keys[i]] === undefined || obj[keys[i]] === null) obj[keys[i]] = {};
                obj = obj[keys[i]];
            }
            obj[keys[keys.length - 1]] = value;
            return next;
        });
    };

    const getField = (path: string, fallback: any = ''): any => {
        const keys = path.split('.');
        let obj = data;
        for (const k of keys) {
            if (obj === undefined || obj === null) return fallback;
            obj = obj[k];
        }
        return obj ?? fallback;
    };

    const handleSave = async () => {
        setError(null);
        setSaving(true);
        try {
            await axios.post(`${API}/sidecar/update/${assetId}`, { updates: draft });
            setIsEditing(false);
            onSaved();
        } catch (err: any) {
            setError(err.response?.data?.detail || err.message);
        } finally {
            setSaving(false);
        }
    };

    // Parse raw JSON back into draft
    const applyRawJson = () => {
        setRawJsonError(null);
        try {
            const parsed = JSON.parse(rawJsonText);
            setDraft(parsed);
            setShowRawJson(false);
        } catch (e: any) {
            setRawJsonError(`JSON inválido: ${e.message}`);
        }
    };

    // Status helpers
    const statusMap: Record<string, { emoji: string; color: string }> = {
        on_hold: { emoji: '⏸️', color: '#f59e0b' },
        ON_HOLD: { emoji: '⏸️', color: '#f59e0b' },
        pending: { emoji: '⏳', color: '#3b82f6' },
        PENDING: { emoji: '⏳', color: '#3b82f6' },
        processing: { emoji: '⚙️', color: '#6366f1' },
        PROCESSING: { emoji: '⚙️', color: '#6366f1' },
        review_required: { emoji: '👁️', color: '#a855f7' },
        REVIEW_REQUIRED: { emoji: '👁️', color: '#a855f7' },
        completed: { emoji: '✅', color: '#22c55e' },
        COMPLETED: { emoji: '✅', color: '#22c55e' },
        failed: { emoji: '❌', color: '#ef4444' },
        FAILED: { emoji: '❌', color: '#ef4444' },
        rejected: { emoji: '🚫', color: '#ef4444' },
        REJECTED: { emoji: '🚫', color: '#ef4444' },
    };

    const privLevel = getField('privacy_config.level', 'strict_local');
    const privLocked = getField('privacy_config.locked', false);
    const currentStatus = getField('workflow_state.current_status', 'unknown');
    const statusCfg = statusMap[currentStatus] || { emoji: '❓', color: '#64748b' };

    const formatBytes = (b: number) => {
        if (!b) return 'N/A';
        if (b < 1024) return `${b} B`;
        if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
        return `${(b / (1024 * 1024)).toFixed(2)} MB`;
    };

    return (
        <div style={{ fontSize: '0.8rem' }}>
            {/* ── SECTION 1: Core Identity (always read-only) ── */}
            <SidecarSection_ title="Identidad del Asset" icon="🆔" defaultOpen>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 16px' }}>
                    <InfoRow label="Archivo Original" value={getField('original_filename')} />
                    <InfoRow label="MIME Type" value={
                        <span style={badgeStyle('#3b82f6')}>{getField('mime_type', 'desconocido')}</span>
                    } />
                    <InfoRow label="Tamaño" value={formatBytes(getField('size_bytes', 0))} />
                    <InfoRow label="Hash" value={
                        <code style={{ fontSize: '0.65rem', color: '#64748b' }}>
                            {(getField('file_hash', '') as string).substring(0, 16)}...
                        </code>
                    } mono />
                    <InfoRow label="Fecha de Upload" value={
                        getField('upload_timestamp')
                            ? new Date(getField('upload_timestamp')).toLocaleString()
                            : 'N/A'
                    } />
                    <InfoRow label="Operación" value={
                        <span style={badgeStyle('#f59e0b')}>{getField('operation', 'standard')}</span>
                    } />
                </div>
                {getField('is_merged') && (
                    <div style={{
                        marginTop: 4, padding: '4px 8px', borderRadius: 4,
                        background: '#818cf815', color: '#a5b4fc', fontSize: '0.7rem'
                    }}>
                        📎 Asset fusionado desde {(getField('source_files', []) as any[]).length} archivo(s)
                    </div>
                )}
            </SidecarSection_>

            {/* ── SECTION 2: Upload Metadata (editable: user_notes, discard_original, vector_types) ── */}
            <SidecarSection_ title="Metadata de Upload" icon="📤" defaultOpen>
                {isEditing ? (
                    <>
                        <EditableField label="📝 Notas del Usuario" value={getField('user_notes', '')}
                            onChange={v => setField('user_notes', v || null)} multiline
                            placeholder="Contexto adicional sobre el archivo..." />
                        <label style={{
                            display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer',
                            fontSize: '0.75rem', color: '#cbd5e1', marginBottom: 8
                        }}>
                            <input type="checkbox" checked={getField('discard_original', false)}
                                onChange={e => setField('discard_original', e.target.checked)}
                                style={{ accentColor: '#ef4444' }} />
                            🗑️ Descartar Original
                        </label>
                        <div style={{ marginBottom: 8 }}>
                            <label style={fieldLabelStyle}>Tipos de Vector Solicitados</label>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                                {['visual_siglip', 'visual_semantic', 'text_ocr', 'text_chunk',
                                    'audio_clap', 'audio_transcript', 'user_memory_required'].map(vt => {
                                        const active = (getField('vector_types', []) as string[]).includes(vt);
                                        return (
                                            <button key={vt} onClick={() => {
                                                const curr = (getField('vector_types', []) as string[]);
                                                setField('vector_types',
                                                    active ? curr.filter(v => v !== vt) : [...curr, vt]);
                                            }} style={{
                                                padding: '2px 8px', borderRadius: 4, fontSize: '0.65rem', fontWeight: 600,
                                                background: active ? '#818cf820' : '#0f172a',
                                                color: active ? '#a5b4fc' : '#475569',
                                                border: `1px solid ${active ? '#818cf840' : '#334155'}`,
                                                cursor: 'pointer', transition: 'all 0.15s'
                                            }}>
                                                {active ? '✓ ' : ''}{vt}
                                            </button>
                                        );
                                    })}
                            </div>
                        </div>
                    </>
                ) : (
                    <>
                        <InfoRow label="Notas del Usuario" value={getField('user_notes') || <span style={{ color: '#475569', fontStyle: 'italic' }}>Sin notas</span>} />
                        <InfoRow label="Descartar Original" value={getField('discard_original') ? '✅ Sí' : '❌ No'} />
                        <div style={{ marginBottom: 4 }}>
                            <span style={fieldLabelStyle}>Vector Types</span>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3, marginTop: 2 }}>
                                {(getField('vector_types', []) as string[]).map(vt => (
                                    <span key={vt} style={badgeStyle('#818cf8')}>{vt}</span>
                                ))}
                                {(getField('vector_types', []) as string[]).length === 0 && (
                                    <span style={{ color: '#475569', fontSize: '0.7rem', fontStyle: 'italic' }}>Ninguno</span>
                                )}
                            </div>
                        </div>
                    </>
                )}
            </SidecarSection_>

            {/* ── SECTION 3: Privacy Config (editable) ── */}
            <SidecarSection_ title="Privacidad y Gobernanza" icon="🔐" defaultOpen>
                {isEditing ? (
                    <>
                        <div style={{ marginBottom: 8 }}>
                            <label style={fieldLabelStyle}>Nivel de Privacidad</label>
                            <select value={privLevel as string}
                                onChange={e => setField('privacy_config.level', e.target.value)}
                                style={{ ...inputFieldStyle, cursor: 'pointer' }}>
                                <option value="strict_local">🔒 Estricto Local</option>
                                <option value="public_cloud">☁️ Nube Pública</option>
                            </select>
                        </div>
                        <label style={{
                            display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer',
                            fontSize: '0.75rem', color: '#cbd5e1', marginBottom: 6
                        }}>
                            <input type="checkbox" checked={privLocked as boolean}
                                onChange={e => setField('privacy_config.locked', e.target.checked)}
                                style={{ accentColor: '#f59e0b' }} />
                            🔓 Bloqueo de compliance
                        </label>
                        {privLocked && (
                            <EditableField label="Razón del bloqueo"
                                value={getField('privacy_config.locked_reason', '')}
                                onChange={v => setField('privacy_config.locked_reason', v || null)}
                                placeholder="Ej: GDPR compliance, Legal hold..." />
                        )}
                    </>
                ) : (
                    <>
                        <InfoRow label="Nivel" value={
                            <span style={badgeStyle(privLevel === 'strict_local' ? '#22c55e' : '#3b82f6')}>
                                {privLevel === 'strict_local' ? '🔒 Estricto Local' : '☁️ Nube Pública'}
                            </span>
                        } />
                        <InfoRow label="Bloqueado" value={privLocked ? '🔒 Sí' : '🔓 No'} />
                        {privLocked && getField('privacy_config.locked_reason') && (
                            <InfoRow label="Razón" value={getField('privacy_config.locked_reason')} />
                        )}
                    </>
                )}
            </SidecarSection_>

            {/* ── SECTION 4: Workflow State (read-only) ── */}
            <SidecarSection_ title="Estado del Workflow" icon="⚙️">
                <InfoRow label="Estado Actual" value={
                    <span style={badgeStyle(statusCfg.color)}>
                        {statusCfg.emoji} {currentStatus}
                    </span>
                } />
                <div style={{ marginBottom: 4 }}>
                    <span style={fieldLabelStyle}>Pasos Completados</span>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3, marginTop: 2 }}>
                        {(getField('workflow_state.steps_completed', []) as string[]).length > 0
                            ? (getField('workflow_state.steps_completed', []) as string[]).map((s, i) => (
                                <span key={i} style={badgeStyle('#22c55e')}>✓ {s}</span>
                            ))
                            : <span style={{ color: '#475569', fontSize: '0.7rem', fontStyle: 'italic' }}>Ninguno</span>
                        }
                    </div>
                </div>
                <InfoRow label="Última Actualización" value={
                    getField('workflow_state.last_updated')
                        ? new Date(getField('workflow_state.last_updated')).toLocaleString()
                        : 'N/A'
                } />
                {(getField('workflow_state.error_log', []) as any[]).length > 0 && (
                    <div style={{ marginTop: 4 }}>
                        <span style={fieldLabelStyle}>
                            ⚠️ Errores ({(getField('workflow_state.error_log', []) as any[]).length})
                        </span>
                        <pre style={{
                            background: '#0f172a', padding: 6, borderRadius: 4, fontSize: '0.65rem',
                            color: '#fca5a5', maxHeight: 120, overflow: 'auto', whiteSpace: 'pre-wrap',
                            border: '1px solid #ef444420', margin: 0
                        }}>
                            {JSON.stringify(getField('workflow_state.error_log', []), null, 2)}
                        </pre>
                    </div>
                )}
            </SidecarSection_>

            {/* ── SECTION 5: Análisis AI (THE MAIN EDITABLE SECTION) ── */}
            <SidecarSection_ title="Análisis de Contenido (LLM)" icon="🧠" defaultOpen>
                {(() => {
                    // Use the REAL path where analysis lives
                    const A = 'data_layers.text_summary_analysis';
                    const analysis = getField(A);
                    if (!analysis) return (
                        <span style={{ color: '#475569', fontSize: '0.7rem', fontStyle: 'italic' }}>
                            Sin análisis disponible — el asset aún no ha sido procesado.
                        </span>
                    );

                    // Entity type config: what fields each entity type has
                    const entityConfigs: Record<string, { fields: string[]; labels: Record<string, string>; color: string }> = {
                        persons: {
                            fields: ['name', 'role', 'confidence', 'relation_type'],
                            labels: { name: 'Nombre', role: 'Rol', confidence: 'Confianza', relation_type: 'Relación' },
                            color: '#a855f7'
                        },
                        locations: {
                            fields: ['name', 'type', 'confidence', 'relation_type'],
                            labels: { name: 'Nombre', type: 'Tipo', confidence: 'Confianza', relation_type: 'Relación' },
                            color: '#22c55e'
                        },
                        organizations: {
                            fields: ['name', 'confidence'],
                            labels: { name: 'Nombre', confidence: 'Confianza' },
                            color: '#3b82f6'
                        },
                        events: {
                            fields: ['name', 'type', 'date', 'confidence', 'relation_type'],
                            labels: { name: 'Nombre', type: 'Tipo', date: 'Fecha', confidence: 'Confianza', relation_type: 'Relación' },
                            color: '#f59e0b'
                        },
                        projects: {
                            fields: ['title', 'type', 'year', 'confidence', 'relation_type'],
                            labels: { title: 'Título', type: 'Tipo', year: 'Año', confidence: 'Confianza', relation_type: 'Relación' },
                            color: '#ec4899'
                        },
                        concepts: {
                            fields: ['name', 'type', 'domain', 'definition', 'confidence'],
                            labels: { name: 'Nombre', type: 'Tipo', domain: 'Dominio', definition: 'Definición', confidence: 'Confianza' },
                            color: '#818cf8'
                        }
                    };

                    const entityEmojis: Record<string, string> = {
                        persons: '👤', locations: '📍', organizations: '🏢',
                        events: '📅', projects: '📐', concepts: '💡'
                    };

                    return (
                        <>
                            {/* ── SUMMARY (editable) ── */}
                            <div style={{ marginBottom: 10 }}>
                                <span style={{ ...fieldLabelStyle, fontSize: '0.72rem', color: '#a5b4fc' }}>📝 Resumen</span>
                                {isEditing ? (
                                    <textarea
                                        value={getField(`${A}.graph_core.summary`, '')}
                                        onChange={e => setField(`${A}.graph_core.summary`, e.target.value)}
                                        style={{ ...inputFieldStyle, minHeight: 70, resize: 'vertical', fontFamily: 'inherit' }}
                                        placeholder="Descripción densa del contenido..."
                                    />
                                ) : (
                                    <div style={{
                                        padding: 8, borderRadius: 4, fontSize: '0.75rem', color: '#cbd5e1',
                                        background: '#0f172a80', border: '1px solid #1e293b', lineHeight: 1.5
                                    }}>
                                        {getField(`${A}.graph_core.summary`) || <span style={{ color: '#475569', fontStyle: 'italic' }}>Sin resumen</span>}
                                    </div>
                                )}
                            </div>

                            {/* ── TAGS (editable: add/remove chips) ── */}
                            <div style={{ marginBottom: 10 }}>
                                <span style={{ ...fieldLabelStyle, fontSize: '0.72rem', color: '#a5b4fc' }}>🏷️ Tags</span>
                                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, alignItems: 'center' }}>
                                    {(getField(`${A}.graph_core.tags`, []) as string[]).map((tag, i) => (
                                        <span key={i} style={{
                                            ...badgeStyle('#f59e0b'),
                                            display: 'inline-flex', alignItems: 'center', gap: 4
                                        }}>
                                            #{tag}
                                            {isEditing && (
                                                <span onClick={() => {
                                                    const tags = [...(getField(`${A}.graph_core.tags`, []) as string[])];
                                                    tags.splice(i, 1);
                                                    setField(`${A}.graph_core.tags`, tags);
                                                }} style={{ cursor: 'pointer', color: '#ef4444', fontWeight: 700, fontSize: '0.7rem' }}>×</span>
                                            )}
                                        </span>
                                    ))}
                                    {isEditing && (
                                        <input
                                            placeholder="+ tag"
                                            style={{ ...inputFieldStyle, width: 80, padding: '2px 6px', fontSize: '0.65rem' }}
                                            onKeyDown={e => {
                                                if (e.key === 'Enter' && (e.target as HTMLInputElement).value.trim()) {
                                                    const tags = [...(getField(`${A}.graph_core.tags`, []) as string[])];
                                                    tags.push((e.target as HTMLInputElement).value.trim());
                                                    setField(`${A}.graph_core.tags`, tags);
                                                    (e.target as HTMLInputElement).value = '';
                                                    e.preventDefault();
                                                }
                                            }}
                                        />
                                    )}
                                    {!isEditing && (getField(`${A}.graph_core.tags`, []) as string[]).length === 0 && (
                                        <span style={{ color: '#475569', fontSize: '0.7rem', fontStyle: 'italic' }}>Sin tags</span>
                                    )}
                                </div>
                            </div>

                            {/* ── ENTITIES (fully editable per type) ── */}
                            <div style={{ marginBottom: 10 }}>
                                <span style={{ ...fieldLabelStyle, fontSize: '0.72rem', color: '#a5b4fc' }}>🕸️ Entidades del Grafo</span>
                                {Object.entries(entityConfigs).map(([entityType, cfg]) => {
                                    const path = `${A}.graph_core.entities.${entityType}`;
                                    const items = (getField(path, []) as any[]);
                                    const nameField = entityType === 'projects' ? 'title' : 'name';
                                    if (!isEditing && items.length === 0) return null;

                                    return (
                                        <div key={entityType} style={{
                                            marginBottom: 8, padding: 8, borderRadius: 6,
                                            background: `${cfg.color}08`, border: `1px solid ${cfg.color}15`
                                        }}>
                                            <div style={{
                                                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                                                marginBottom: 4
                                            }}>
                                                <span style={{ fontSize: '0.72rem', fontWeight: 600, color: cfg.color }}>
                                                    {entityEmojis[entityType]} {entityType.charAt(0).toUpperCase() + entityType.slice(1)} ({items.length})
                                                </span>
                                                {isEditing && (
                                                    <button onClick={() => {
                                                        const newItem: Record<string, any> = {};
                                                        cfg.fields.forEach(f => {
                                                            newItem[f] = f === 'confidence' ? 0.8 : '';
                                                        });
                                                        setField(path, [...items, newItem]);
                                                    }} style={{
                                                        padding: '1px 8px', borderRadius: 4, fontSize: '0.6rem',
                                                        background: `${cfg.color}20`, color: cfg.color,
                                                        border: `1px solid ${cfg.color}30`, cursor: 'pointer', fontWeight: 600
                                                    }}>
                                                        + Agregar
                                                    </button>
                                                )}
                                            </div>

                                            {items.map((entity: any, idx: number) => (
                                                <div key={idx} style={{
                                                    display: 'flex', gap: 6, alignItems: 'flex-start', marginBottom: 4,
                                                    padding: '4px 6px', borderRadius: 4,
                                                    background: isEditing ? '#0f172a60' : 'transparent'
                                                }}>
                                                    {isEditing ? (
                                                        <>
                                                            <div style={{ flex: 1, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                                                                {cfg.fields.map(field => {
                                                                    if (field === 'confidence') {
                                                                        return (
                                                                            <div key={field} style={{ width: 70 }}>
                                                                                <span style={{ ...fieldLabelStyle, fontSize: '0.58rem', marginBottom: 1 }}>{cfg.labels[field]}</span>
                                                                                <div style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                                                                                    <input type="range" min="0" max="1" step="0.05"
                                                                                        value={entity[field] ?? 0.8}
                                                                                        onChange={e => {
                                                                                            const updated = [...items];
                                                                                            updated[idx] = { ...updated[idx], [field]: parseFloat(e.target.value) };
                                                                                            setField(path, updated);
                                                                                        }}
                                                                                        style={{ width: 40, accentColor: cfg.color }}
                                                                                    />
                                                                                    <span style={{ fontSize: '0.6rem', color: '#94a3b8', minWidth: 28 }}>
                                                                                        {((entity[field] ?? 0.8) * 100).toFixed(0)}%
                                                                                    </span>
                                                                                </div>
                                                                            </div>
                                                                        );
                                                                    }
                                                                    if (field === 'relation_type') {
                                                                        return (
                                                                            <div key={field} style={{ minWidth: 110 }}>
                                                                                <span style={{ ...fieldLabelStyle, fontSize: '0.58rem', marginBottom: 1 }}>{cfg.labels[field]}</span>
                                                                                <input
                                                                                    value={entity[field] ?? ''}
                                                                                    onChange={e => {
                                                                                        const updated = [...items];
                                                                                        updated[idx] = { ...updated[idx], [field]: e.target.value };
                                                                                        setField(path, updated);
                                                                                    }}
                                                                                    style={{ ...inputFieldStyle, padding: '2px 6px', fontSize: '0.65rem' }}
                                                                                    placeholder="MENTIONS"
                                                                                />
                                                                            </div>
                                                                        );
                                                                    }
                                                                    const isDefinition = field === 'definition';
                                                                    return (
                                                                        <div key={field} style={{ flex: isDefinition ? '1 1 100%' : '1 1 80px', minWidth: isDefinition ? '100%' : 70 }}>
                                                                            <span style={{ ...fieldLabelStyle, fontSize: '0.58rem', marginBottom: 1 }}>{cfg.labels[field]}</span>
                                                                            {isDefinition ? (
                                                                                <textarea
                                                                                    value={entity[field] ?? ''}
                                                                                    onChange={e => {
                                                                                        const updated = [...items];
                                                                                        updated[idx] = { ...updated[idx], [field]: e.target.value };
                                                                                        setField(path, updated);
                                                                                    }}
                                                                                    style={{ ...inputFieldStyle, padding: '2px 6px', fontSize: '0.65rem', minHeight: 32, resize: 'vertical', fontFamily: 'inherit' }}
                                                                                    placeholder="Definición..."
                                                                                />
                                                                            ) : (
                                                                                <input
                                                                                    value={entity[field] ?? ''}
                                                                                    onChange={e => {
                                                                                        const updated = [...items];
                                                                                        updated[idx] = { ...updated[idx], [field]: e.target.value };
                                                                                        setField(path, updated);
                                                                                    }}
                                                                                    style={{ ...inputFieldStyle, padding: '2px 6px', fontSize: '0.65rem' }}
                                                                                    placeholder={cfg.labels[field]}
                                                                                />
                                                                            )}
                                                                        </div>
                                                                    );
                                                                })}
                                                            </div>
                                                            <button onClick={() => {
                                                                const updated = items.filter((_: any, i: number) => i !== idx);
                                                                setField(path, updated);
                                                            }} style={{
                                                                padding: '2px 4px', borderRadius: 3, fontSize: '0.6rem',
                                                                background: '#ef444420', color: '#fca5a5',
                                                                border: '1px solid #ef444430', cursor: 'pointer',
                                                                marginTop: 12, flexShrink: 0
                                                            }}>🗑️</button>
                                                        </>
                                                    ) : (
                                                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, alignItems: 'center' }}>
                                                            <span style={{
                                                                ...badgeStyle(cfg.color), fontSize: '0.62rem'
                                                            }}>
                                                                {entity[nameField] || entity.name}
                                                                {entity.confidence != null && entity.confidence < 1
                                                                    ? ` (${(entity.confidence * 100).toFixed(0)}%)`
                                                                    : ''}
                                                            </span>
                                                            {entity.role && <span style={{ fontSize: '0.6rem', color: '#64748b' }}>— {entity.role}</span>}
                                                            {entity.type && <span style={{ fontSize: '0.6rem', color: '#64748b' }}>· {entity.type}</span>}
                                                            {entity.domain && <span style={{ fontSize: '0.6rem', color: '#64748b' }}>· {entity.domain}</span>}
                                                            {entity.relation_type && (
                                                                <span style={{
                                                                    ...badgeStyle('#64748b'), fontSize: '0.55rem'
                                                                }}>{entity.relation_type}</span>
                                                            )}
                                                        </div>
                                                    )}
                                                </div>
                                            ))}
                                            {!isEditing && items.length === 0 && (
                                                <span style={{ color: '#475569', fontSize: '0.65rem', fontStyle: 'italic' }}>Ninguno</span>
                                            )}
                                        </div>
                                    );
                                })}
                            </div>

                            {/* ── VISUAL SPECIFICS (editable) ── */}
                            {getField(`${A}.visual_specifics`) && (
                                <div style={{ marginBottom: 10, padding: 8, borderRadius: 6, background: '#a855f708', border: '1px solid #a855f715' }}>
                                    <span style={{ fontSize: '0.72rem', fontWeight: 600, color: '#a855f7', display: 'block', marginBottom: 4 }}>
                                        🖼️ Especificaciones Visuales
                                    </span>
                                    {isEditing ? (
                                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
                                            <EditableField label="Tipo de Imagen" value={getField(`${A}.visual_specifics.image_type`, '')}
                                                onChange={v => setField(`${A}.visual_specifics.image_type`, v)} placeholder="photography | meme | art..." />
                                            <EditableField label="Composición" value={getField(`${A}.visual_specifics.composition`, '')}
                                                onChange={v => setField(`${A}.visual_specifics.composition`, v)} placeholder="Rule of thirds..." />
                                            <EditableField label="Iluminación" value={getField(`${A}.visual_specifics.lighting`, '')}
                                                onChange={v => setField(`${A}.visual_specifics.lighting`, v)} placeholder="Golden hour..." />
                                            <EditableField label="Estilo Artístico" value={getField(`${A}.visual_specifics.art_style`, '')}
                                                onChange={v => setField(`${A}.visual_specifics.art_style`, v)} placeholder="Cyberpunk, Baroque..." />
                                            <EditableField label="Mood Visual" value={getField(`${A}.visual_specifics.visual_mood`, '')}
                                                onChange={v => setField(`${A}.visual_specifics.visual_mood`, v)} placeholder="Atmosfera percibida..." />
                                            <EditableField label="OCR Text" value={getField(`${A}.visual_specifics.ocr_text`, '')}
                                                onChange={v => setField(`${A}.visual_specifics.ocr_text`, v)} placeholder="Texto literal en la imagen..." />
                                        </div>
                                    ) : (
                                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                                            {getField(`${A}.visual_specifics.image_type`) && <span style={badgeStyle('#a855f7')}>Tipo: {getField(`${A}.visual_specifics.image_type`)}</span>}
                                            {getField(`${A}.visual_specifics.composition`) && <span style={badgeStyle('#818cf8')}>Comp: {getField(`${A}.visual_specifics.composition`)}</span>}
                                            {getField(`${A}.visual_specifics.lighting`) && <span style={badgeStyle('#f59e0b')}>Luz: {getField(`${A}.visual_specifics.lighting`)}</span>}
                                            {getField(`${A}.visual_specifics.art_style`) && <span style={badgeStyle('#22c55e')}>Estilo: {getField(`${A}.visual_specifics.art_style`)}</span>}
                                            {getField(`${A}.visual_specifics.visual_mood`) && <span style={badgeStyle('#ec4899')}>Mood: {getField(`${A}.visual_specifics.visual_mood`)}</span>}
                                            {getField(`${A}.visual_specifics.ocr_text`) && <InfoRow label="OCR" value={getField(`${A}.visual_specifics.ocr_text`)} />}
                                        </div>
                                    )}
                                </div>
                            )}

                            {/* ── AUDIO SPECIFICS (editable) ── */}
                            {getField(`${A}.audio_specifics`) && (
                                <div style={{ marginBottom: 10, padding: 8, borderRadius: 6, background: '#22c55e08', border: '1px solid #22c55e15' }}>
                                    <span style={{ fontSize: '0.72rem', fontWeight: 600, color: '#22c55e', display: 'block', marginBottom: 4 }}>
                                        🎵 Especificaciones de Audio
                                    </span>
                                    {isEditing ? (
                                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
                                            <EditableField label="Tipo de Audio" value={getField(`${A}.audio_specifics.audio_type`, '')}
                                                onChange={v => setField(`${A}.audio_specifics.audio_type`, v)} placeholder="song | speech | instrumental..." />
                                            <EditableField label="Género" value={getField(`${A}.audio_specifics.genre`, '')}
                                                onChange={v => setField(`${A}.audio_specifics.genre`, v)} placeholder="Rock, Jazz, Keynote..." />
                                            <EditableField label="Tempo" value={getField(`${A}.audio_specifics.tempo`, '')}
                                                onChange={v => setField(`${A}.audio_specifics.tempo`, v)} placeholder="120 BPM / Lento..." />
                                            <EditableField label="Tono Emocional" value={getField(`${A}.audio_specifics.emotional_tone`, '')}
                                                onChange={v => setField(`${A}.audio_specifics.emotional_tone`, v)} placeholder="Melancólico, Energético..." />
                                            <div style={{ gridColumn: 'span 2' }}>
                                                <EditableField label="Resumen de Letra" value={getField(`${A}.audio_specifics.lyrics_summary`, '')}
                                                    onChange={v => setField(`${A}.audio_specifics.lyrics_summary`, v)} multiline placeholder="Tema de la letra..." />
                                            </div>
                                        </div>
                                    ) : (
                                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                                            {getField(`${A}.audio_specifics.audio_type`) && <span style={badgeStyle('#22c55e')}>Tipo: {getField(`${A}.audio_specifics.audio_type`)}</span>}
                                            {getField(`${A}.audio_specifics.genre`) && <span style={badgeStyle('#f59e0b')}>Género: {getField(`${A}.audio_specifics.genre`)}</span>}
                                            {getField(`${A}.audio_specifics.tempo`) && <span style={badgeStyle('#3b82f6')}>Tempo: {getField(`${A}.audio_specifics.tempo`)}</span>}
                                            {getField(`${A}.audio_specifics.emotional_tone`) && <span style={badgeStyle('#ec4899')}>Tono: {getField(`${A}.audio_specifics.emotional_tone`)}</span>}
                                            {getField(`${A}.audio_specifics.lyrics_summary`) && <InfoRow label="Letra" value={getField(`${A}.audio_specifics.lyrics_summary`)} />}
                                        </div>
                                    )}
                                </div>
                            )}

                            {/* ── TEXT SPECIFICS (editable) ── */}
                            {getField(`${A}.text_specifics`) && (
                                <div style={{ marginBottom: 10, padding: 8, borderRadius: 6, background: '#3b82f608', border: '1px solid #3b82f615' }}>
                                    <span style={{ fontSize: '0.72rem', fontWeight: 600, color: '#3b82f6', display: 'block', marginBottom: 4 }}>
                                        📝 Especificaciones de Texto
                                    </span>
                                    {isEditing ? (
                                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
                                            <EditableField label="Tipo de Documento" value={getField(`${A}.text_specifics.document_type`, '')}
                                                onChange={v => setField(`${A}.text_specifics.document_type`, v)} placeholder="article | quote | code..." />
                                            <EditableField label="Tono Retórico" value={getField(`${A}.text_specifics.rhetorical_tone`, '')}
                                                onChange={v => setField(`${A}.text_specifics.rhetorical_tone`, v)} placeholder="Académico, Informal..." />
                                            <EditableField label="Idioma" value={getField(`${A}.text_specifics.language`, '')}
                                                onChange={v => setField(`${A}.text_specifics.language`, v)} placeholder="es, en, fr..." />
                                            <div>
                                                <label style={{
                                                    display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer',
                                                    fontSize: '0.7rem', color: '#cbd5e1', marginTop: 18
                                                }}>
                                                    <input type="checkbox" checked={getField(`${A}.text_specifics.requires_action`, false)}
                                                        onChange={e => setField(`${A}.text_specifics.requires_action`, e.target.checked)}
                                                        style={{ accentColor: '#3b82f6' }} />
                                                    Requiere Acción
                                                </label>
                                            </div>
                                        </div>
                                    ) : (
                                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                                            {getField(`${A}.text_specifics.document_type`) && <span style={badgeStyle('#3b82f6')}>Tipo: {getField(`${A}.text_specifics.document_type`)}</span>}
                                            {getField(`${A}.text_specifics.rhetorical_tone`) && <span style={badgeStyle('#818cf8')}>Tono: {getField(`${A}.text_specifics.rhetorical_tone`)}</span>}
                                            {getField(`${A}.text_specifics.language`) && <span style={badgeStyle('#a855f7')}>Idioma: {getField(`${A}.text_specifics.language`)}</span>}
                                            {getField(`${A}.text_specifics.requires_action`) && <span style={badgeStyle('#ef4444')}>⚡ Requiere Acción</span>}
                                        </div>
                                    )}
                                </div>
                            )}

                            {/* ── MEMORY ANALYSIS (if present, editable) ── */}
                            {getField(`${A}.memory_analysis`) && (
                                <div style={{ marginBottom: 10, padding: 8, borderRadius: 6, background: '#c4b5fd08', border: '1px solid #c4b5fd15' }}>
                                    <span style={{ fontSize: '0.72rem', fontWeight: 600, color: '#c4b5fd', display: 'block', marginBottom: 4 }}>
                                        🧠 Análisis de Memoria
                                    </span>
                                    {isEditing ? (
                                        <>
                                            <EditableField label="Texto Enriquecido" value={getField(`${A}.memory_analysis.enriched_text`, '')}
                                                onChange={v => setField(`${A}.memory_analysis.enriched_text`, v)} multiline placeholder="Narrativa detallada..." />
                                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
                                                <EditableField label="Sentimiento" value={getField(`${A}.memory_analysis.sentiment`, '')}
                                                    onChange={v => setField(`${A}.memory_analysis.sentiment`, v)} placeholder="Nostálgico, Happy..." />
                                                <div>
                                                    <span style={fieldLabelStyle}>Intensidad Emocional</span>
                                                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                                        <input type="range" min="0" max="1" step="0.05"
                                                            value={getField(`${A}.memory_analysis.emotional_intensity`, 0.5)}
                                                            onChange={e => setField(`${A}.memory_analysis.emotional_intensity`, parseFloat(e.target.value))}
                                                            style={{ flex: 1, accentColor: '#c4b5fd' }}
                                                        />
                                                        <span style={{ fontSize: '0.65rem', color: '#94a3b8' }}>
                                                            {((getField(`${A}.memory_analysis.emotional_intensity`, 0.5) as number) * 100).toFixed(0)}%
                                                        </span>
                                                    </div>
                                                </div>
                                            </div>
                                        </>
                                    ) : (
                                        <>
                                            {getField(`${A}.memory_analysis.enriched_text`) && <InfoRow label="Narrativa" value={getField(`${A}.memory_analysis.enriched_text`)} />}
                                            <div style={{ display: 'flex', gap: 6, marginTop: 4 }}>
                                                {getField(`${A}.memory_analysis.sentiment`) && <span style={badgeStyle('#c4b5fd')}>{getField(`${A}.memory_analysis.sentiment`)}</span>}
                                                {getField(`${A}.memory_analysis.emotional_intensity`) != null && (
                                                    <span style={badgeStyle('#a855f7')}>
                                                        Intensidad: {((getField(`${A}.memory_analysis.emotional_intensity`, 0) as number) * 100).toFixed(0)}%
                                                    </span>
                                                )}
                                            </div>
                                        </>
                                    )}
                                </div>
                            )}

                            {/* ── USER CONTEXT ANALYSIS (if present) ── */}
                            {getField(`${A}.user_context_analysis`) && (
                                <div style={{ marginBottom: 10, padding: 8, borderRadius: 6, background: '#f59e0b08', border: '1px solid #f59e0b15' }}>
                                    <span style={{ fontSize: '0.72rem', fontWeight: 600, color: '#f59e0b', display: 'block', marginBottom: 4 }}>
                                        💬 Análisis de Contexto del Usuario
                                    </span>
                                    {isEditing ? (
                                        <>
                                            <EditableField label="Resumen del Contexto" value={getField(`${A}.user_context_analysis.summary`, '')}
                                                onChange={v => setField(`${A}.user_context_analysis.summary`, v)} multiline placeholder="Resumen de la anécdota o memoria..." />
                                            <EditableField label="Influencia de Mood" value={getField(`${A}.user_context_analysis.mood_influence`, '')}
                                                onChange={v => setField(`${A}.user_context_analysis.mood_influence`, v)} placeholder="Nostálgico, Celebratorio..." />
                                        </>
                                    ) : (
                                        <>
                                            <InfoRow label="Resumen" value={getField(`${A}.user_context_analysis.summary`)} />
                                            {getField(`${A}.user_context_analysis.mood_influence`) && <InfoRow label="Mood" value={getField(`${A}.user_context_analysis.mood_influence`)} />}
                                        </>
                                    )}
                                </div>
                            )}
                        </>
                    );
                })()}
            </SidecarSection_>

            {/* ── SECTION 5b: Intermediate Data & Vectors ── */}
            <SidecarSection_ title="Datos Intermedios y Vectores" icon="📊">
                {getField('data_layers') && (
                    <>
                        {getField('data_layers.intermediate_results') && (
                            <div style={{ marginBottom: 6 }}>
                                <span style={{ ...fieldLabelStyle, fontSize: '0.72rem', color: '#a5b4fc' }}>
                                    🔬 Resultados Intermedios
                                </span>
                                {getField('data_layers.intermediate_results.ocr_text') && (
                                    <div style={{ marginBottom: 4 }}>
                                        <span style={fieldLabelStyle}>OCR Text</span>
                                        {isEditing ? (
                                            <textarea value={getField('data_layers.intermediate_results.ocr_text', '')}
                                                onChange={e => setField('data_layers.intermediate_results.ocr_text', e.target.value)}
                                                style={{ ...inputFieldStyle, minHeight: 60, resize: 'vertical', fontFamily: 'monospace', fontSize: '0.7rem' }} />
                                        ) : (
                                            <pre style={{
                                                background: '#0f172a', padding: 6, borderRadius: 4, fontSize: '0.65rem',
                                                color: '#94a3b8', maxHeight: 100, overflow: 'auto', whiteSpace: 'pre-wrap',
                                                border: '1px solid #1e293b', margin: 0
                                            }}>
                                                {getField('data_layers.intermediate_results.ocr_text')}
                                            </pre>
                                        )}
                                    </div>
                                )}
                                {getField('data_layers.intermediate_results.audio_transcript') && (
                                    <div style={{ marginBottom: 4 }}>
                                        <span style={fieldLabelStyle}>Audio Transcript</span>
                                        <pre style={{
                                            background: '#0f172a', padding: 6, borderRadius: 4, fontSize: '0.65rem',
                                            color: '#94a3b8', maxHeight: 100, overflow: 'auto', whiteSpace: 'pre-wrap',
                                            border: '1px solid #1e293b', margin: 0
                                        }}>
                                            {getField('data_layers.intermediate_results.audio_transcript')}
                                        </pre>
                                    </div>
                                )}
                                {getField('data_layers.intermediate_results.user_context_transcript') && (
                                    <InfoRow label="User Context" value={getField('data_layers.intermediate_results.user_context_transcript')} />
                                )}
                            </div>
                        )}

                        {/* Vectors generated */}
                        <div style={{ marginBottom: 4 }}>
                            <span style={fieldLabelStyle}>Vectores Generados</span>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
                                {(getField('data_layers.vectors_generated', []) as string[]).length > 0
                                    ? (getField('data_layers.vectors_generated', []) as string[]).map(v => (
                                        <span key={v} style={badgeStyle('#22c55e')}>✓ {v}</span>
                                    ))
                                    : <span style={{ color: '#475569', fontSize: '0.7rem', fontStyle: 'italic' }}>Ninguno aún</span>
                                }
                            </div>
                        </div>
                    </>
                )}
            </SidecarSection_>

            {/* ── SECTION 6: User Context (if memory asset) ── */}
            {getField('user_context') && (
                <SidecarSection_ title="Contexto de Usuario (Memoria)" icon="🧠">
                    <pre style={{
                        background: '#0f172a', padding: 8, borderRadius: 4, fontSize: '0.65rem',
                        color: '#c4b5fd', maxHeight: 120, overflow: 'auto', whiteSpace: 'pre-wrap',
                        border: '1px solid #a855f720', margin: 0
                    }}>
                        {JSON.stringify(getField('user_context'), null, 2)}
                    </pre>
                </SidecarSection_>
            )}

            {/* ── RAW JSON FALLBACK (toggle) ── */}
            <div style={{ marginTop: 8, borderTop: '1px solid #1e293b', paddingTop: 8 }}>
                <button onClick={() => {
                    if (!showRawJson) setRawJsonText(JSON.stringify(isEditing ? draft : sidecar, null, 2));
                    setShowRawJson(!showRawJson);
                    setRawJsonError(null);
                }} style={{
                    padding: '3px 10px', borderRadius: 4, fontSize: '0.65rem',
                    background: 'transparent', color: '#475569', border: '1px solid #334155',
                    cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4
                }}>
                    {showRawJson ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
                    🔍 {showRawJson ? 'Ocultar' : 'Ver'} JSON Crudo
                </button>
                {showRawJson && (
                    <div style={{ marginTop: 6 }}>
                        {isEditing ? (
                            <>
                                <div style={{
                                    padding: '4px 8px', borderRadius: 4, fontSize: '0.65rem',
                                    background: '#eab30810', color: '#fbbf24', marginBottom: 4,
                                    border: '1px solid #eab30820'
                                }}>
                                    ⚠️ Edición avanzada — los cambios aquí sobreescriben el formulario.
                                </div>
                                <textarea value={rawJsonText}
                                    onChange={e => setRawJsonText(e.target.value)}
                                    style={{
                                        width: '100%', minHeight: 200, padding: 8, borderRadius: 4,
                                        fontSize: '0.65rem', fontFamily: 'monospace', color: '#f8fafc',
                                        background: '#0f172a', border: '1px solid #334155', outline: 'none',
                                        resize: 'vertical'
                                    }} />
                                {rawJsonError && (
                                    <div style={{
                                        padding: '4px 8px', borderRadius: 4, fontSize: '0.65rem', marginTop: 4,
                                        background: '#ef444415', color: '#fca5a5', border: '1px solid #ef444430'
                                    }}>
                                        ❌ {rawJsonError}
                                    </div>
                                )}
                                <button onClick={applyRawJson} style={{
                                    marginTop: 4, padding: '3px 10px', borderRadius: 4, fontSize: '0.65rem',
                                    background: '#f59e0b', color: '#0f172a', border: 'none', cursor: 'pointer',
                                    fontWeight: 600
                                }}>
                                    Aplicar JSON al formulario
                                </button>
                            </>
                        ) : (
                            <pre style={{
                                background: '#0f172a', padding: 8, borderRadius: 4, fontSize: '0.65rem',
                                color: '#94a3b8', maxHeight: 300, overflow: 'auto', whiteSpace: 'pre-wrap',
                                border: '1px solid #1e293b', margin: 0
                            }}>
                                {JSON.stringify(sidecar, null, 2)}
                            </pre>
                        )}
                    </div>
                )}
            </div>

            {/* ── ACTION BUTTONS ── */}
            <div style={{ marginTop: 12, display: 'flex', gap: 8, alignItems: 'center' }}>
                {isEditing ? (
                    <>
                        <button onClick={handleSave} disabled={saving} style={{
                            padding: '6px 16px', borderRadius: 4, fontSize: '0.75rem', fontWeight: 600,
                            background: 'linear-gradient(135deg, #22c55e, #4ade80)', color: '#0f172a',
                            border: 'none', cursor: saving ? 'not-allowed' : 'pointer',
                            display: 'flex', alignItems: 'center', gap: 4,
                            boxShadow: '0 2px 6px rgba(34,197,94,0.3)',
                            opacity: saving ? 0.7 : 1
                        }}>
                            {saving ? <Loader2 size={10} className="animate-spin" /> : <Save size={10} />}
                            Guardar Cambios
                        </button>
                        <button onClick={cancelEdit} style={{
                            padding: '6px 16px', borderRadius: 4, fontSize: '0.75rem',
                            background: '#334155', color: '#94a3b8', border: '1px solid #475569',
                            cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4
                        }}>
                            <X size={10} /> Cancelar
                        </button>
                    </>
                ) : (
                    <button onClick={startEdit} style={{
                        padding: '5px 14px', borderRadius: 4, fontSize: '0.75rem', fontWeight: 500,
                        background: '#334155', color: '#cbd5e1', border: '1px solid #475569',
                        cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4
                    }}>
                        <Edit3 size={10} /> Editar Sidecar
                    </button>
                )}
            </div>

            {error && (
                <div style={{
                    padding: '6px 10px', borderRadius: 4, fontSize: '0.7rem', marginTop: 8,
                    background: '#ef444415', color: '#fca5a5', border: '1px solid #ef444430'
                }}>
                    ❌ {error}
                </div>
            )}
        </div>
    );
}

// ==========================================
// TASK ITEM COMPONENT
// ==========================================

function ReviewTaskItem({ task, isSelected, onToggle, onRefresh }: {
    task: ReviewTask;
    isSelected: boolean;
    onToggle: () => void;
    onRefresh: () => void;
}) {
    const [expanded, setExpanded] = useState(false);
    const cfg = STATUS_CONFIG[task.status] || { icon: Clock, color: '#94a3b8', bg: '#94a3b820', label: task.status };
    const Icon = cfg.icon;

    return (
        <div style={{
            background: '#0f172a', borderRadius: 8, border: '1px solid #1e293b',
            overflow: 'hidden', marginBottom: 6
        }}>
            {/* Header row */}
            <div style={{
                display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px',
                cursor: 'pointer'
            }} onClick={() => setExpanded(!expanded)}>
                <input type="checkbox" checked={isSelected}
                    onChange={e => { e.stopPropagation(); onToggle(); }}
                    onClick={e => e.stopPropagation()}
                    style={{ accentColor: cfg.color }}
                />
                {expanded ? <ChevronDown size={14} style={{ color: '#64748b' }} />
                    : <ChevronRight size={14} style={{ color: '#64748b' }} />}
                <Icon size={14} style={{ color: cfg.color }} />
                <span style={{
                    display: 'inline-flex', alignItems: 'center', gap: 4,
                    padding: '2px 8px', borderRadius: 4, fontSize: '0.65rem', fontWeight: 600,
                    color: cfg.color, background: cfg.bg
                }}>
                    {cfg.label}
                </span>
                <span style={{
                    color: '#cbd5e1', fontSize: '0.8rem', padding: '2px 8px',
                    borderRadius: 4, background: '#1e293b', border: '1px solid #334155'
                }}>
                    {task.vectorType.replace(/_/g, ' ')}
                </span>
                <span style={{ color: '#f8fafc', fontSize: '0.85rem', fontWeight: 500 }}>
                    {task.filename}
                </span>
                <span style={{ color: '#475569', fontSize: '0.65rem', marginLeft: 'auto' }}>
                    {task.vsId.substring(0, 8)}...
                </span>
            </div>

            {/* Expanded details */}
            {expanded && (
                <div style={{
                    padding: '12px 14px 14px 48px', borderTop: '1px solid #1e293b',
                    background: '#0f172a80'
                }}>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 20px', marginBottom: 12 }}>
                        <span style={{ color: '#64748b', fontSize: '0.75rem' }}>
                            <strong>Estado:</strong> {task.status}
                        </span>
                        <span style={{ color: '#64748b', fontSize: '0.75rem' }}>
                            <strong>Archivo:</strong> <code style={{ color: '#cbd5e1' }}>{task.filename}</code>
                        </span>
                        <span style={{ color: '#64748b', fontSize: '0.75rem' }}>
                            <strong>Vector Type:</strong> <code style={{ color: '#cbd5e1' }}>{task.vectorType}</code>
                        </span>
                        <span style={{ color: '#64748b', fontSize: '0.75rem' }}>
                            <strong>ID:</strong> <code style={{ color: '#cbd5e1' }}>{task.vsId.substring(0, 12)}...</code>
                        </span>
                    </div>

                    {/* Error message */}
                    {task.errorMessage && (
                        <div style={{ marginBottom: 12 }}>
                            <div style={{
                                fontSize: '0.75rem', fontWeight: 600, color: '#fca5a5', marginBottom: 4
                            }}>
                                ⚠️ Mensaje de Error:
                            </div>
                            <pre style={{
                                background: '#0f172a', padding: 10, borderRadius: 6, fontSize: '0.7rem',
                                color: '#fca5a5', whiteSpace: 'pre-wrap', wordBreak: 'break-all',
                                border: '1px solid #ef444430', margin: 0
                            }}>
                                {task.errorMessage}
                            </pre>
                            {(() => {
                                const hint = getErrorHint(task.errorMessage);
                                if (!hint) return null;
                                return (
                                    <div style={{
                                        padding: '6px 10px', borderRadius: 4, fontSize: '0.7rem',
                                        background: '#3b82f610', color: '#60a5fa', marginTop: 6,
                                        border: '1px solid #3b82f620'
                                    }}>
                                        {hint}
                                    </div>
                                );
                            })()}
                        </div>
                    )}

                    {/* Sidecar data */}
                    {task.sidecarData && Object.keys(task.sidecarData).length > 0 && (
                        <SidecarSection assetId={task.assetId} sidecar={task.sidecarData} onRefresh={onRefresh} />
                    )}
                </div>
            )}
        </div>
    );
}

function SidecarSection({ assetId, sidecar, onRefresh }: {
    assetId: string;
    sidecar: Record<string, any>;
    onRefresh: () => void;
}) {
    const [open, setOpen] = useState(false);

    return (
        <div style={{
            background: '#1e293b', borderRadius: 6, border: '1px solid #334155',
            overflow: 'hidden'
        }}>
            <div onClick={() => setOpen(!open)} style={{
                display: 'flex', alignItems: 'center', gap: 6, padding: '8px 12px',
                cursor: 'pointer', fontSize: '0.75rem', fontWeight: 600, color: '#94a3b8'
            }}>
                {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                📝 Ver/Editar Sidecar
            </div>
            {open && (
                <div style={{ padding: '0 12px 12px' }}>
                    <SidecarEditor assetId={assetId} sidecar={sidecar} onSaved={onRefresh} />
                </div>
            )}
        </div>
    );
}

// ==========================================
// MAIN COMPONENT
// ==========================================

type SubTab = 'all' | 'review' | 'failed';

export default function ReviewQueueTab() {
    const [assets, setAssets] = useState<Asset[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
    const [activeTab, setActiveTab] = useState<SubTab>('all');
    const [actionResult, setActionResult] = useState<string | null>(null);
    const [acting, setActing] = useState(false);

    const fetchQueue = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await axios.get<Asset[]>(`${API}/tasks/review-queue`);
            setAssets(Array.isArray(res.data) ? res.data : []);
        } catch (err: any) {
            setError(err.message || 'No se pudo conectar al backend');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { fetchQueue(); }, [fetchQueue]);

    // Build flat task list
    const allTasks: ReviewTask[] = useMemo(() => {
        const tasks: ReviewTask[] = [];
        for (const a of assets) {
            for (const vs of a.vector_statuses) {
                tasks.push({
                    vsId: vs.id,
                    vectorType: vs.vector_type,
                    status: vs.status,
                    errorMessage: vs.error_message,
                    assetId: a.id,
                    filename: a.filename,
                    mimeType: a.mime_type,
                    sidecarData: a.sidecar_data,
                });
            }
        }
        return tasks;
    }, [assets]);

    const reviewCount = allTasks.filter(t => t.status === 'REVIEW_REQUIRED').length;
    const failedCount = allTasks.filter(t => t.status === 'FAILED').length;

    const filteredTasks = useMemo(() => {
        if (activeTab === 'review') return allTasks.filter(t => t.status === 'REVIEW_REQUIRED');
        if (activeTab === 'failed') return allTasks.filter(t => t.status === 'FAILED');
        return allTasks;
    }, [allTasks, activeTab]);

    const toggleSelect = (id: string) => {
        setSelectedIds(prev => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id); else next.add(id);
            return next;
        });
    };

    const selectAll = () => {
        if (selectedIds.size === filteredTasks.length) {
            setSelectedIds(new Set());
        } else {
            setSelectedIds(new Set(filteredTasks.map(t => t.vsId)));
        }
    };

    const handleAction = async (action: 'reset' | 'approve') => {
        const ids = Array.from(selectedIds);
        if (ids.length === 0) return;
        setActing(true);
        setActionResult(null);
        try {
            if (action === 'reset') {
                const res = await axios.post(`${API}/tasks/reset-to-hold`, { vector_status_ids: ids });
                setActionResult(`✅ ${res.data.tasks_reset || 0} tarea(s) reseteadas a ON_HOLD`);
            } else {
                const res = await axios.post(`${API}/tasks/approve`, { vector_status_ids: ids });
                setActionResult(`✅ ${res.data.tasks_approved || 0} tarea(s) aprobadas como COMPLETED`);
            }
            setSelectedIds(new Set());
            setTimeout(() => fetchQueue(), 1500);
        } catch (err: any) {
            setActionResult(`❌ Error: ${err.response?.data?.detail || err.message}`);
        } finally {
            setActing(false);
        }
    };

    // ── Loading / Error / Empty states ──
    if (loading) {
        return (
            <div style={{
                display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                minHeight: 400, gap: 12, color: '#94a3b8'
            }}>
                <Loader2 size={32} className="animate-spin" style={{ color: '#a855f7' }} />
                <p>Cargando cola de revisión...</p>
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
                <button onClick={fetchQueue} style={{
                    padding: '8px 20px', borderRadius: 8, background: '#ef4444', color: '#fff',
                    border: 'none', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 6
                }}>
                    <RefreshCw size={14} /> Reintentar
                </button>
            </div>
        );
    }

    if (allTasks.length === 0) {
        return (
            <div style={{
                padding: 32, borderRadius: 12, background: '#22c55e08', border: '1px solid #22c55e20',
                textAlign: 'center', color: '#86efac'
            }}>
                ✨ No hay tareas pendientes de revisión.
            </div>
        );
    }

    const tabStyle = (tab: SubTab): React.CSSProperties => ({
        padding: '8px 16px', borderRadius: 8, fontSize: '0.8rem', fontWeight: 600,
        background: activeTab === tab ? '#1e293b' : 'transparent',
        color: activeTab === tab ? '#f8fafc' : '#64748b',
        border: activeTab === tab ? '1px solid #334155' : '1px solid transparent',
        cursor: 'pointer', transition: 'all 0.15s',
        display: 'flex', alignItems: 'center', gap: 6
    });

    return (
        <div>
            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
                <div>
                    <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f8fafc', marginBottom: 4 }}>
                        👁️ Cola de Revisión
                    </h2>
                    <p style={{ color: '#94a3b8', fontSize: '0.85rem' }}>
                        Tareas que requieren revisión humana o que fallaron.
                    </p>
                </div>
                <button onClick={fetchQueue} style={{
                    display: 'flex', alignItems: 'center', gap: 6, padding: '8px 16px',
                    borderRadius: 8, background: '#334155', color: '#94a3b8', border: '1px solid #475569',
                    cursor: 'pointer', fontSize: '0.8rem'
                }}>
                    <RefreshCw size={14} /> Refresh
                </button>
            </div>

            {/* Metrics */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 24 }}>
                {[
                    { label: 'Review Required', count: reviewCount, icon: Eye, color: '#a855f7' },
                    { label: 'Fallidas', count: failedCount, icon: XCircle, color: '#ef4444' },
                    { label: 'Total', count: allTasks.length, icon: AlertTriangle, color: '#eab308' },
                ].map(m => (
                    <div key={m.label} style={{
                        background: `${m.color}10`, borderRadius: 12, padding: '16px 14px',
                        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
                        border: `1px solid ${m.color}30`
                    }}>
                        <m.icon size={18} style={{ color: m.color }} />
                        <span style={{ fontSize: '1.5rem', fontWeight: 700, color: m.color }}>{m.count}</span>
                        <span style={{ fontSize: '0.7rem', color: m.color, opacity: 0.8 }}>{m.label}</span>
                    </div>
                ))}
            </div>

            {/* Sub-tabs */}
            <div style={{ display: 'flex', gap: 6, marginBottom: 16 }}>
                <button onClick={() => setActiveTab('all')} style={tabStyle('all')}>
                    📊 Todas <span style={{ padding: '0 6px', borderRadius: 4, background: '#334155', fontSize: '0.65rem' }}>{allTasks.length}</span>
                </button>
                <button onClick={() => setActiveTab('review')} style={tabStyle('review')}>
                    👁️ Review <span style={{ padding: '0 6px', borderRadius: 4, background: '#a855f720', fontSize: '0.65rem', color: '#c4b5fd' }}>{reviewCount}</span>
                </button>
                <button onClick={() => setActiveTab('failed')} style={tabStyle('failed')}>
                    ❌ Fallidas <span style={{ padding: '0 6px', borderRadius: 4, background: '#ef444420', fontSize: '0.65rem', color: '#fca5a5' }}>{failedCount}</span>
                </button>
            </div>

            {/* Actions bar */}
            <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '10px 14px', borderRadius: 8, background: '#1e293b',
                marginBottom: 12, border: '1px solid #334155', flexWrap: 'wrap', gap: 8
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
                        <input type="checkbox"
                            checked={selectedIds.size === filteredTasks.length && filteredTasks.length > 0}
                            onChange={selectAll}
                            style={{ accentColor: '#a855f7' }}
                        />
                        <span style={{ color: '#94a3b8', fontSize: '0.8rem' }}>
                            Seleccionar todas ({filteredTasks.length})
                        </span>
                    </label>
                    <span style={{ color: '#475569', fontSize: '0.75rem' }}>
                        | {selectedIds.size} seleccionada(s)
                    </span>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                    <button onClick={() => handleAction('reset')}
                        disabled={selectedIds.size === 0 || acting}
                        style={{
                            padding: '6px 14px', borderRadius: 6, fontSize: '0.75rem',
                            background: selectedIds.size > 0 ? '#f97316' : '#334155',
                            color: '#fff', border: 'none',
                            cursor: selectedIds.size > 0 ? 'pointer' : 'not-allowed',
                            display: 'flex', alignItems: 'center', gap: 4,
                            opacity: selectedIds.size > 0 ? 1 : 0.5
                        }}>
                        <RotateCcw size={12} /> Reset a ON_HOLD
                    </button>
                    <button onClick={() => handleAction('approve')}
                        disabled={selectedIds.size === 0 || acting}
                        style={{
                            padding: '6px 14px', borderRadius: 6, fontSize: '0.75rem', fontWeight: 600,
                            background: selectedIds.size > 0 ? 'linear-gradient(135deg, #22c55e, #4ade80)' : '#334155',
                            color: selectedIds.size > 0 ? '#0f172a' : '#fff', border: 'none',
                            cursor: selectedIds.size > 0 ? 'pointer' : 'not-allowed',
                            display: 'flex', alignItems: 'center', gap: 4,
                            opacity: selectedIds.size > 0 ? 1 : 0.5,
                            boxShadow: selectedIds.size > 0 ? '0 2px 8px rgba(34,197,94,0.3)' : 'none'
                        }}>
                        {acting ? <Loader2 size={12} className="animate-spin" />
                            : <Check size={12} />}
                        Marcar como Done
                    </button>
                </div>
            </div>

            {/* Task list */}
            <div style={{ display: 'flex', flexDirection: 'column' }}>
                {filteredTasks.length === 0 ? (
                    <div style={{
                        padding: 20, borderRadius: 8, background: '#22c55e08',
                        border: '1px solid #22c55e20', textAlign: 'center', color: '#86efac'
                    }}>
                        ✨ No hay tareas en esta categoría.
                    </div>
                ) : (
                    filteredTasks.map(task => (
                        <ReviewTaskItem
                            key={task.vsId}
                            task={task}
                            isSelected={selectedIds.has(task.vsId)}
                            onToggle={() => toggleSelect(task.vsId)}
                            onRefresh={fetchQueue}
                        />
                    ))
                )}
            </div>

            {/* Action result */}
            {actionResult && (
                <div style={{
                    padding: '10px 14px', borderRadius: 8, fontSize: '0.85rem', marginTop: 12,
                    background: actionResult.startsWith('✅') ? '#22c55e15' : '#ef444415',
                    color: actionResult.startsWith('✅') ? '#86efac' : '#fca5a5',
                    border: `1px solid ${actionResult.startsWith('✅') ? '#22c55e30' : '#ef444430'}`
                }}>
                    {actionResult}
                </div>
            )}
        </div>
    );
}
