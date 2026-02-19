import { useState, useMemo, useCallback, useRef, useEffect } from 'react';
import axios from 'axios';
import {
    Upload, Loader2, FolderPlus, Trash2, Send,
    ChevronDown, ChevronRight, FileText, Image, Music,
    Video, File, Check, Type, Brain
} from 'lucide-react';

// ==========================================
// TYPES & CONSTANTS
// ==========================================

const API = 'http://localhost:8000';

const VECTOR_OPTS = [
    { id: 'visual_siglip', label: 'Visual SigLIP', icon: '🖼️' },
    { id: 'visual_semantic', label: 'Visual Semantic', icon: '🎨' },
    { id: 'text_ocr', label: 'Text OCR', icon: '📝' },
    { id: 'audio_clap', label: 'Audio CLAP', icon: '🎵' },
    { id: 'audio_transcript', label: 'Audio Transcript', icon: '🎙️' },
    { id: 'text_chunk', label: 'Text Chunk', icon: '📄' },
    { id: 'user_memory_required', label: 'User Memory', icon: '🧠' },
];

const OPERATION_OPTS = [
    { id: 'standard', label: '📄 Estándar (1 archivo = 1 asset)' },
    { id: 'merge_ocr', label: '📑 Merge OCR (N archivos = 1 asset)' },
];

const PRIVACY_OPTS = [
    { id: 'strict_local', label: '🔒 Estricto Local (no cloud AI)' },
    { id: 'public_cloud', label: '☁️ Nube Pública (OpenAI, etc.)' },
];

interface FileGroup {
    id: number;
    fileNames: string[];
    operation: string;
    vectors: string[];
    privacyLevel: string;
    discardOriginal: boolean;
    notes: string;
}

interface AssetCreated {
    id: string;
    filename: string;
    minio_path: string;
    sidecar_path: string;
    is_merged: boolean;
    vector_tasks_created: number;
}

// ==========================================
// MIME HELPERS
// ==========================================

function getMimeIcon(mime: string) {
    if (mime.startsWith('image/')) return <Image size={14} style={{ color: '#a855f7' }} />;
    if (mime.startsWith('audio/')) return <Music size={14} style={{ color: '#22c55e' }} />;
    if (mime.startsWith('video/')) return <Video size={14} style={{ color: '#ef4444' }} />;
    if (mime.startsWith('text/')) return <FileText size={14} style={{ color: '#3b82f6' }} />;
    return <File size={14} style={{ color: '#64748b' }} />;
}

function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

// ==========================================
// FILE PREVIEW COMPONENT
// ==========================================

function FilePreview({ file }: { file: File }) {
    const [previewUrl, setPreviewUrl] = useState<string | null>(null);
    const [textContent, setTextContent] = useState<string | null>(null);

    useEffect(() => {
        const mime = file.type || '';
        if (mime.startsWith('image/') || mime.startsWith('audio/') || mime.startsWith('video/')) {
            const url = URL.createObjectURL(file);
            setPreviewUrl(url);
            return () => URL.revokeObjectURL(url);
        }
        if (mime.startsWith('text/') || file.name.endsWith('.txt') || file.name.endsWith('.md') || file.name.endsWith('.csv')) {
            const reader = new FileReader();
            reader.onload = () => {
                const text = reader.result as string;
                setTextContent(text.substring(0, 1000) + (text.length > 1000 ? '\n\n... (contenido truncado)' : ''));
            };
            reader.readAsText(file);
        }
    }, [file]);

    const mime = file.type || '';

    if (mime.startsWith('image/') && previewUrl) {
        return <img src={previewUrl} alt={file.name} style={{
            maxWidth: '100%', maxHeight: 200, borderRadius: 6, objectFit: 'contain'
        }} />;
    }
    if (mime.startsWith('audio/') && previewUrl) {
        return <audio controls src={previewUrl} style={{ width: '100%' }} />;
    }
    if (mime.startsWith('video/') && previewUrl) {
        return <video controls src={previewUrl} style={{
            maxWidth: '100%', maxHeight: 200, borderRadius: 6
        }} />;
    }
    if (textContent !== null) {
        return <pre style={{
            background: '#0f172a', padding: 10, borderRadius: 6, fontSize: '0.7rem',
            color: '#94a3b8', maxHeight: 200, overflow: 'auto', whiteSpace: 'pre-wrap',
            border: '1px solid #1e293b', margin: 0
        }}>{textContent}</pre>;
    }

    return <p style={{ color: '#475569', fontSize: '0.75rem', fontStyle: 'italic' }}>
        📄 Preview no disponible para <code>{mime || 'tipo desconocido'}</code>
    </p>;
}

// ==========================================
// FILE UPLOADER
// ==========================================

function FileUploader({ onFilesAdded }: { onFilesAdded: (files: File[]) => void }) {
    const inputRef = useRef<HTMLInputElement>(null);
    const [dragging, setDragging] = useState(false);

    const handleFiles = (fileList: FileList | null) => {
        if (!fileList) return;
        onFilesAdded(Array.from(fileList));
    };

    return (
        <div>
            <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#f8fafc', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
                <Upload size={16} style={{ color: '#818cf8' }} /> Cargar Archivos
            </h3>
            <div
                onDragOver={e => { e.preventDefault(); setDragging(true); }}
                onDragLeave={() => setDragging(false)}
                onDrop={e => { e.preventDefault(); setDragging(false); handleFiles(e.dataTransfer.files); }}
                onClick={() => inputRef.current?.click()}
                style={{
                    border: `2px dashed ${dragging ? '#818cf8' : '#334155'}`,
                    borderRadius: 12, padding: '32px 24px', textAlign: 'center',
                    cursor: 'pointer', transition: 'all 0.2s',
                    background: dragging ? '#818cf810' : '#1e293b40',
                }}
            >
                <Upload size={28} style={{ color: dragging ? '#818cf8' : '#475569', marginBottom: 8 }} />
                <p style={{ color: '#94a3b8', fontSize: '0.85rem', marginBottom: 4 }}>
                    Arrastra archivos aquí o <strong style={{ color: '#818cf8' }}>haz clic para seleccionar</strong>
                </p>
                <p style={{ color: '#475569', fontSize: '0.7rem' }}>
                    Imágenes, audio, video, texto, PDF, etc.
                </p>
            </div>
            <input ref={inputRef} type="file" multiple style={{ display: 'none' }}
                onChange={e => handleFiles(e.target.files)} />
        </div>
    );
}

// ==========================================
// UNGROUPED FILES LIST
// ==========================================

function UngroupedFiles({ files, ungroupedNames }: { files: File[]; ungroupedNames: string[] }) {
    const [expandedFile, setExpandedFile] = useState<string | null>(null);

    const ungroupedFiles = useMemo(
        () => files.filter(f => ungroupedNames.includes(f.name)),
        [files, ungroupedNames]
    );

    if (ungroupedFiles.length === 0) {
        return (
            <div style={{
                padding: 16, borderRadius: 8, background: '#22c55e08',
                border: '1px solid #22c55e20', color: '#86efac', fontSize: '0.85rem'
            }}>
                ✨ Todos los archivos han sido asignados a grupos.
            </div>
        );
    }

    return (
        <div>
            <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#f8fafc', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
                📋 Archivos Sin Asignar
            </h3>
            <p style={{ color: '#64748b', fontSize: '0.75rem', marginBottom: 10 }}>
                <strong>{ungroupedFiles.length}</strong> archivo(s) disponibles para agrupar
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {ungroupedFiles.map(f => {
                    const expanded = expandedFile === f.name;
                    return (
                        <div key={f.name} style={{
                            background: '#0f172a', borderRadius: 8, border: '1px solid #1e293b', overflow: 'hidden'
                        }}>
                            <div onClick={() => setExpandedFile(expanded ? null : f.name)}
                                style={{
                                    display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px',
                                    cursor: 'pointer', fontSize: '0.8rem'
                                }}>
                                {expanded ? <ChevronDown size={12} style={{ color: '#64748b' }} /> : <ChevronRight size={12} style={{ color: '#64748b' }} />}
                                {getMimeIcon(f.type || '')}
                                <span style={{ color: '#f8fafc', fontWeight: 500 }}>{f.name}</span>
                                <span style={{ color: '#475569', fontSize: '0.7rem' }}>({formatSize(f.size)})</span>
                                <span style={{
                                    padding: '1px 6px', borderRadius: 4, fontSize: '0.6rem',
                                    background: '#334155', color: '#94a3b8'
                                }}>{f.type || 'unknown'}</span>
                            </div>
                            {expanded && (
                                <div style={{ padding: '8px 12px 12px 32px', borderTop: '1px solid #1e293b' }}>
                                    <FilePreview file={f} />
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

// ==========================================
// GROUP BUILDER
// ==========================================

function GroupBuilder({ ungroupedNames, onCreateGroup }: {
    ungroupedNames: string[];
    onCreateGroup: (group: Omit<FileGroup, 'id'>) => void;
}) {
    const [selectedFiles, setSelectedFiles] = useState<Set<string>>(new Set());
    const [operation, setOperation] = useState('standard');
    const [vectors, setVectors] = useState<Set<string>>(new Set());
    const [privacy, setPrivacy] = useState('strict_local');
    const [discard, setDiscard] = useState(false);
    const [notes, setNotes] = useState('');
    const [error, setError] = useState<string | null>(null);

    const toggleFile = (name: string) => {
        setSelectedFiles(prev => {
            const next = new Set(prev);
            if (next.has(name)) next.delete(name); else next.add(name);
            return next;
        });
    };

    const toggleVector = (id: string) => {
        setVectors(prev => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id); else next.add(id);
            return next;
        });
    };

    const handleCreate = () => {
        setError(null);
        if (selectedFiles.size === 0) { setError('Selecciona al menos un archivo.'); return; }
        if (vectors.size === 0) { setError('Selecciona al menos un tipo de vector.'); return; }

        onCreateGroup({
            fileNames: Array.from(selectedFiles),
            operation,
            vectors: Array.from(vectors),
            privacyLevel: privacy,
            discardOriginal: discard,
            notes,
        });

        // Reset form
        setSelectedFiles(new Set());
        setVectors(new Set());
        setNotes('');
        setDiscard(false);
    };

    if (ungroupedNames.length === 0) {
        return (
            <div style={{ padding: 16, borderRadius: 8, background: '#eab30808', border: '1px solid #eab30820', color: '#fbbf24', fontSize: '0.85rem' }}>
                ⚠️ No hay archivos disponibles para agrupar. Carga archivos primero.
            </div>
        );
    }

    const inputStyle: React.CSSProperties = {
        width: '100%', padding: '8px 12px', borderRadius: 6, fontSize: '0.8rem',
        background: '#0f172a', border: '1px solid #334155', color: '#f8fafc', outline: 'none'
    };

    return (
        <div style={{ background: '#1e293b', borderRadius: 12, border: '1px solid #334155', padding: 20 }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#f8fafc', marginBottom: 16, display: 'flex', alignItems: 'center', gap: 6 }}>
                <FolderPlus size={16} style={{ color: '#818cf8' }} /> Crear Nuevo Grupo
            </h3>

            {/* File selection */}
            <div style={{ marginBottom: 16 }}>
                <label style={{ color: '#94a3b8', fontSize: '0.75rem', fontWeight: 600, display: 'block', marginBottom: 6 }}>
                    Selecciona archivos para el grupo
                </label>
                <div style={{
                    display: 'flex', flexDirection: 'column', gap: 4,
                    maxHeight: 180, overflow: 'auto', padding: 8, borderRadius: 6,
                    background: '#0f172a', border: '1px solid #334155'
                }}>
                    {ungroupedNames.map(name => (
                        <label key={name} style={{
                            display: 'flex', alignItems: 'center', gap: 8, padding: '4px 6px',
                            borderRadius: 4, cursor: 'pointer', fontSize: '0.8rem',
                            background: selectedFiles.has(name) ? '#818cf815' : 'transparent',
                            color: '#f8fafc'
                        }}>
                            <input type="checkbox" checked={selectedFiles.has(name)}
                                onChange={() => toggleFile(name)} style={{ accentColor: '#818cf8' }} />
                            {name}
                        </label>
                    ))}
                </div>
                {selectedFiles.size > 0 && (
                    <span style={{ color: '#818cf8', fontSize: '0.7rem', marginTop: 4, display: 'block' }}>
                        {selectedFiles.size} archivo(s) seleccionado(s)
                    </span>
                )}
            </div>

            {/* Operation & Privacy */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
                <div>
                    <label style={{ color: '#94a3b8', fontSize: '0.75rem', fontWeight: 600, display: 'block', marginBottom: 4 }}>
                        Tipo de Operación
                    </label>
                    <select value={operation} onChange={e => setOperation(e.target.value)}
                        style={{ ...inputStyle, cursor: 'pointer' }}>
                        {OPERATION_OPTS.map(o => (
                            <option key={o.id} value={o.id}>{o.label}</option>
                        ))}
                    </select>
                </div>
                <div>
                    <label style={{ color: '#94a3b8', fontSize: '0.75rem', fontWeight: 600, display: 'block', marginBottom: 4 }}>
                        🔐 Nivel de Privacidad
                    </label>
                    <select value={privacy} onChange={e => setPrivacy(e.target.value)}
                        style={{ ...inputStyle, cursor: 'pointer' }}>
                        {PRIVACY_OPTS.map(p => (
                            <option key={p.id} value={p.id}>{p.label}</option>
                        ))}
                    </select>
                </div>
            </div>

            {/* Vector types */}
            <div style={{ marginBottom: 16 }}>
                <label style={{ color: '#94a3b8', fontSize: '0.75rem', fontWeight: 600, display: 'block', marginBottom: 6 }}>
                    Vectores Deseados
                </label>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {VECTOR_OPTS.map(v => (
                        <button key={v.id} onClick={() => toggleVector(v.id)}
                            style={{
                                padding: '5px 10px', borderRadius: 6, fontSize: '0.7rem', fontWeight: 600,
                                background: vectors.has(v.id) ? '#818cf825' : '#0f172a',
                                color: vectors.has(v.id) ? '#a5b4fc' : '#64748b',
                                border: `1px solid ${vectors.has(v.id) ? '#818cf850' : '#334155'}`,
                                cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4,
                                transition: 'all 0.15s'
                            }}>
                            {v.icon} {v.label}
                        </button>
                    ))}
                </div>
            </div>

            {/* Discard + Notes */}
            <div style={{ marginBottom: 16 }}>
                <label style={{
                    display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer',
                    fontSize: '0.8rem', color: '#cbd5e1', marginBottom: 10
                }}>
                    <input type="checkbox" checked={discard} onChange={e => setDiscard(e.target.checked)}
                        style={{ accentColor: '#ef4444' }} />
                    🗑️ Descartar Original (eliminar binarios después de extracción)
                </label>
                <label style={{ color: '#94a3b8', fontSize: '0.75rem', fontWeight: 600, display: 'block', marginBottom: 4 }}>
                    Notas del Usuario (Opcional)
                </label>
                <textarea value={notes} onChange={e => setNotes(e.target.value)}
                    placeholder="Ej: Twitter thread sobre IA, Screenshots de tutorial, etc."
                    style={{ ...inputStyle, minHeight: 60, resize: 'vertical', fontFamily: 'inherit' }}
                />
            </div>

            {/* Error */}
            {error && (
                <div style={{
                    padding: '6px 12px', borderRadius: 6, fontSize: '0.75rem', marginBottom: 10,
                    background: '#ef444415', color: '#fca5a5', border: '1px solid #ef444430'
                }}>
                    ❌ {error}
                </div>
            )}

            {/* Create button */}
            <button onClick={handleCreate} style={{
                padding: '10px 20px', borderRadius: 8, fontSize: '0.85rem', fontWeight: 600,
                background: 'linear-gradient(135deg, #6366f1, #818cf8)', color: '#fff',
                border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
                boxShadow: '0 2px 8px rgba(99,102,241,0.3)'
            }}>
                <Check size={14} /> Crear Grupo
            </button>
        </div>
    );
}

// ==========================================
// READY GROUPS
// ==========================================

function ReadyGroups({ groups, onDeleteGroup }: {
    groups: FileGroup[];
    onDeleteGroup: (id: number) => void;
}) {
    const [expandedId, setExpandedId] = useState<number | null>(null);

    if (groups.length === 0) {
        return (
            <div style={{
                padding: 16, borderRadius: 8, background: '#1e293b30',
                border: '1px solid #1e293b', color: '#64748b', fontSize: '0.85rem'
            }}>
                📭 No hay grupos creados aún.
            </div>
        );
    }

    return (
        <div>
            <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#f8fafc', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
                📦 Grupos Listos ({groups.length})
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {groups.map(g => {
                    const exp = expandedId === g.id;
                    const privIcon = g.privacyLevel === 'strict_local' ? '🔒' : '☁️';
                    return (
                        <div key={g.id} style={{
                            background: '#0f172a', borderRadius: 8, border: '1px solid #1e293b', overflow: 'hidden'
                        }}>
                            <div onClick={() => setExpandedId(exp ? null : g.id)}
                                style={{
                                    display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px',
                                    cursor: 'pointer', fontSize: '0.85rem'
                                }}>
                                {exp ? <ChevronDown size={12} style={{ color: '#818cf8' }} /> : <ChevronRight size={12} style={{ color: '#818cf8' }} />}
                                <span style={{ color: '#f8fafc', fontWeight: 600 }}>Grupo {g.id}</span>
                                <span style={{ color: '#64748b', fontSize: '0.75rem' }}>
                                    — {g.fileNames.length} archivo(s)
                                </span>
                                <span style={{
                                    padding: '1px 6px', borderRadius: 4, fontSize: '0.6rem',
                                    background: '#334155', color: '#94a3b8'
                                }}>{g.operation}</span>
                                <span style={{ fontSize: '0.7rem' }}>{privIcon}</span>
                                <button onClick={e => { e.stopPropagation(); onDeleteGroup(g.id); }}
                                    style={{
                                        marginLeft: 'auto', background: 'transparent', border: 'none',
                                        cursor: 'pointer', color: '#ef4444', padding: 4, borderRadius: 4
                                    }}>
                                    <Trash2 size={12} />
                                </button>
                            </div>
                            {exp && (
                                <div style={{ padding: '0 14px 12px 32px', borderTop: '1px solid #1e293b' }}>
                                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 20px', marginTop: 8 }}>
                                        <div>
                                            <span style={{ color: '#64748b', fontSize: '0.7rem' }}><strong>Archivos:</strong></span>
                                            {g.fileNames.map(fn => (
                                                <div key={fn} style={{ color: '#94a3b8', fontSize: '0.75rem', paddingLeft: 8 }}>• {fn}</div>
                                            ))}
                                        </div>
                                        <div>
                                            <p style={{ color: '#64748b', fontSize: '0.7rem' }}>
                                                <strong>Operación:</strong> <code style={{ color: '#cbd5e1' }}>{g.operation}</code>
                                            </p>
                                            <p style={{ color: '#64748b', fontSize: '0.7rem' }}>
                                                <strong>Privacidad:</strong> {privIcon} {g.privacyLevel === 'strict_local' ? 'Estricto Local' : 'Nube Pública'}
                                            </p>
                                            <p style={{ color: '#64748b', fontSize: '0.7rem' }}>
                                                <strong>Descartar Original:</strong> {g.discardOriginal ? '✅ Sí' : '❌ No'}
                                            </p>
                                            <p style={{ color: '#64748b', fontSize: '0.7rem' }}>
                                                <strong>Vectores:</strong>{' '}
                                                {g.vectors.map(v => (
                                                    <code key={v} style={{ color: '#a5b4fc', marginRight: 4 }}>{v}</code>
                                                ))}
                                            </p>
                                        </div>
                                    </div>
                                    {g.notes && (
                                        <p style={{ color: '#64748b', fontSize: '0.7rem', marginTop: 6 }}>
                                            <strong>Notas:</strong> {g.notes}
                                        </p>
                                    )}
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

// ==========================================
// TEXT INGEST FORM
// ==========================================

function TextIngestForm() {
    const [isMemory, setIsMemory] = useState(false);
    const [title, setTitle] = useState('');
    const [content, setContent] = useState('');
    const [userNotes, setUserNotes] = useState('');
    const [privacy, setPrivacy] = useState('strict_local');
    const [sending, setSending] = useState(false);
    const [result, setResult] = useState<{ success: boolean; message: string; asset?: AssetCreated } | null>(null);

    const charCount = content.length;
    const wordCount = content.trim() ? content.trim().split(/\s+/).length : 0;

    const handleSubmit = async () => {
        if (!content.trim()) { setResult({ success: false, message: 'El contenido del texto no puede estar vacío.' }); return; }

        setSending(true);
        setResult(null);
        try {
            const payload: Record<string, any> = {
                content,
                is_user_memory: isMemory,
                privacy_level: isMemory ? 'strict_local' : privacy,
            };
            if (title.trim()) payload.title = title.trim();
            if (userNotes.trim()) payload.user_notes = userNotes.trim();

            const res = await axios.post(`${API}/ingest/text`, payload);
            setResult({ success: true, message: res.data.message, asset: res.data.asset });
            // Reset form on success
            setContent('');
            setTitle('');
            setUserNotes('');
        } catch (err: any) {
            setResult({ success: false, message: err.response?.data?.detail || err.message });
        } finally {
            setSending(false);
        }
    };

    const inputStyle: React.CSSProperties = {
        width: '100%', padding: '8px 12px', borderRadius: 6, fontSize: '0.8rem',
        background: '#0f172a', border: '1px solid #334155', color: '#f8fafc', outline: 'none'
    };

    return (
        <div>
            <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#f8fafc', marginBottom: 4 }}>
                📝 Ingesta de Texto
            </h3>
            <p style={{ color: '#94a3b8', fontSize: '0.85rem', marginBottom: 16 }}>
                Ingresa texto directamente al sistema. Se guardará en MinIO y las tareas quedarán en <strong>ON_HOLD</strong>.
            </p>

            {/* Memory toggle */}
            <div style={{
                display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16,
                padding: '10px 14px', borderRadius: 8,
                background: isMemory ? '#a855f715' : '#1e293b',
                border: `1px solid ${isMemory ? '#a855f730' : '#334155'}`
            }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                    <input type="checkbox" checked={isMemory} onChange={e => setIsMemory(e.target.checked)}
                        style={{ accentColor: '#a855f7' }} />
                    <Brain size={16} style={{ color: isMemory ? '#a855f7' : '#64748b' }} />
                    <span style={{ color: isMemory ? '#c4b5fd' : '#94a3b8', fontSize: '0.85rem', fontWeight: 600 }}>
                        Memoria de Usuario
                    </span>
                </label>
                <span style={{
                    padding: '2px 8px', borderRadius: 4, fontSize: '0.65rem',
                    background: isMemory ? '#a855f720' : '#334155',
                    color: isMemory ? '#c4b5fd' : '#64748b'
                }}>
                    {isMemory ? '🧠 memory_ prefix, STRICT_LOCAL, USER_MEMORY' : '📝 text_ prefix, TEXT_CHUNK'}
                </span>
            </div>

            {/* Title */}
            <div style={{ marginBottom: 12 }}>
                <label style={{ color: '#94a3b8', fontSize: '0.75rem', fontWeight: 600, display: 'block', marginBottom: 4 }}>
                    📌 Título (opcional)
                </label>
                <input value={title} onChange={e => setTitle(e.target.value)}
                    placeholder="Ej: Notas de la reunión, Ideas del proyecto..."
                    style={inputStyle} />
            </div>

            {/* Content */}
            <div style={{ marginBottom: 12 }}>
                <label style={{ color: '#94a3b8', fontSize: '0.75rem', fontWeight: 600, display: 'block', marginBottom: 4 }}>
                    📄 Contenido del texto
                </label>
                <textarea value={content} onChange={e => setContent(e.target.value)}
                    placeholder="Escribe o pega aquí el texto que deseas guardar y analizar..."
                    style={{ ...inputStyle, minHeight: 180, resize: 'vertical', fontFamily: 'inherit' }} />
                {content && (
                    <span style={{ color: '#475569', fontSize: '0.7rem', marginTop: 2, display: 'block' }}>
                        📊 {charCount.toLocaleString()} caracteres | {wordCount.toLocaleString()} palabras
                    </span>
                )}
            </div>

            {/* Notes */}
            <div style={{ marginBottom: 12 }}>
                <label style={{ color: '#94a3b8', fontSize: '0.75rem', fontWeight: 600, display: 'block', marginBottom: 4 }}>
                    💬 Notas adicionales (opcional)
                </label>
                <textarea value={userNotes} onChange={e => setUserNotes(e.target.value)}
                    placeholder="Contexto adicional, recordatorios, por qué es importante..."
                    style={{ ...inputStyle, minHeight: 60, resize: 'vertical', fontFamily: 'inherit' }} />
            </div>

            {/* Privacy */}
            {!isMemory && (
                <div style={{ marginBottom: 16 }}>
                    <label style={{ color: '#94a3b8', fontSize: '0.75rem', fontWeight: 600, display: 'block', marginBottom: 4 }}>
                        🔐 Nivel de Privacidad
                    </label>
                    <select value={privacy} onChange={e => setPrivacy(e.target.value)}
                        style={{ ...inputStyle, cursor: 'pointer' }}>
                        {PRIVACY_OPTS.map(p => (
                            <option key={p.id} value={p.id}>{p.label}</option>
                        ))}
                    </select>
                </div>
            )}
            {isMemory && (
                <p style={{ color: '#a855f7', fontSize: '0.7rem', marginBottom: 16 }}>
                    🔒 Privacidad forzada a <strong>Estricto Local</strong> para memorias de usuario
                </p>
            )}

            {/* Submit */}
            <button onClick={handleSubmit} disabled={sending} style={{
                padding: '10px 24px', borderRadius: 8, fontSize: '0.85rem', fontWeight: 600,
                background: 'linear-gradient(135deg, #22c55e, #4ade80)', color: '#0f172a',
                border: 'none', cursor: sending ? 'not-allowed' : 'pointer',
                display: 'flex', alignItems: 'center', gap: 6,
                boxShadow: '0 2px 8px rgba(34,197,94,0.3)',
                opacity: sending ? 0.7 : 1
            }}>
                {sending ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
                Guardar Texto
            </button>

            {/* Result */}
            {result && (
                <div style={{
                    marginTop: 12, padding: '10px 14px', borderRadius: 8, fontSize: '0.85rem',
                    background: result.success ? '#22c55e15' : '#ef444415',
                    color: result.success ? '#86efac' : '#fca5a5',
                    border: `1px solid ${result.success ? '#22c55e30' : '#ef444430'}`
                }}>
                    {result.success ? '✅' : '❌'} {result.message}

                    {result.success && result.asset && (
                        <div style={{ marginTop: 8, fontSize: '0.75rem', color: '#94a3b8' }}>
                            <p><strong>ID:</strong> <code style={{ color: '#818cf8' }}>{result.asset.id}</code></p>
                            <p><strong>Archivo:</strong> <code style={{ color: '#cbd5e1' }}>{result.asset.filename}</code></p>
                            <p><strong>Ruta MinIO:</strong> <code style={{ color: '#cbd5e1' }}>{result.asset.minio_path}</code></p>
                            <p><strong>Tareas creadas:</strong> {result.asset.vector_tasks_created}</p>
                            <p style={{ color: '#60a5fa', marginTop: 4 }}>
                                💡 Las tareas están en ON_HOLD. Ve a "Control de Tareas" para iniciar el procesamiento.
                            </p>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

// ==========================================
// MAIN COMPONENT
// ==========================================

type SubTab = 'files' | 'text';

export default function IngestGroupingTab() {
    const [subTab, setSubTab] = useState<SubTab>('files');
    const [files, setFiles] = useState<File[]>([]);
    const [groups, setGroups] = useState<FileGroup[]>([]);
    const [nextGroupId, setNextGroupId] = useState(1);
    const [sending, setSending] = useState(false);
    const [sendResult, setSendResult] = useState<{ success: boolean; message: string; assets?: AssetCreated[] } | null>(null);

    // Compute ungrouped file names
    const groupedNames = useMemo(() => {
        const names = new Set<string>();
        for (const g of groups) g.fileNames.forEach(n => names.add(n));
        return names;
    }, [groups]);

    const ungroupedNames = useMemo(
        () => files.map(f => f.name).filter(n => !groupedNames.has(n)),
        [files, groupedNames]
    );

    const handleFilesAdded = useCallback((newFiles: File[]) => {
        setFiles(prev => {
            const existing = new Set(prev.map(f => f.name));
            const unique = newFiles.filter(f => !existing.has(f.name));
            return [...prev, ...unique];
        });
    }, []);

    const handleCreateGroup = useCallback((groupData: Omit<FileGroup, 'id'>) => {
        setGroups(prev => [...prev, { ...groupData, id: nextGroupId }]);
        setNextGroupId(prev => prev + 1);
    }, [nextGroupId]);

    const handleDeleteGroup = useCallback((id: number) => {
        setGroups(prev => prev.filter(g => g.id !== id));
    }, []);

    const handleSend = async () => {
        if (groups.length === 0) return;

        setSending(true);
        setSendResult(null);

        try {
            // Build FormData with files and upload_map
            const formData = new FormData();

            // Collect all files referenced by groups in order
            const fileNameOrder: string[] = [];
            const fileMap = new Map(files.map(f => [f.name, f]));

            const uploadMap = groups.map(g => {
                const indices: number[] = [];
                for (const fn of g.fileNames) {
                    let idx = fileNameOrder.indexOf(fn);
                    if (idx === -1) {
                        idx = fileNameOrder.length;
                        fileNameOrder.push(fn);
                    }
                    indices.push(idx);
                }
                return {
                    file_indices: indices,
                    operation: g.operation,
                    vector_types: g.vectors,
                    privacy_level: g.privacyLevel,
                    user_notes: g.notes || undefined,
                    discard_original: g.discardOriginal,
                };
            });

            // Append files in order
            for (const fn of fileNameOrder) {
                const f = fileMap.get(fn);
                if (f) formData.append('files', f, f.name);
            }
            formData.append('upload_map', JSON.stringify(uploadMap));

            const res = await axios.post(`${API}/ingest/upload`, formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
                timeout: 60000,
            });

            if (res.data.success) {
                setSendResult({ success: true, message: res.data.message, assets: res.data.assets_created });
                // Clean state
                setGroups([]);
                setFiles([]);
            } else {
                setSendResult({ success: false, message: 'Upload failed' });
            }
        } catch (err: any) {
            setSendResult({ success: false, message: err.response?.data?.detail || err.message });
        } finally {
            setSending(false);
        }
    };

    const tabBtnStyle = (tab: SubTab): React.CSSProperties => ({
        padding: '8px 16px', borderRadius: 8, fontSize: '0.8rem', fontWeight: 600,
        background: subTab === tab ? '#1e293b' : 'transparent',
        color: subTab === tab ? '#f8fafc' : '#64748b',
        border: subTab === tab ? '1px solid #334155' : '1px solid transparent',
        cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6
    });

    return (
        <div>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f8fafc', marginBottom: 4 }}>
                📤 Ingesta y Agrupación
            </h2>
            <p style={{ color: '#94a3b8', fontSize: '0.85rem', marginBottom: 20 }}>
                Carga de archivos, agrupación por operación, configuración de vectores y envío al backend.
            </p>

            {/* Sub-tabs */}
            <div style={{ display: 'flex', gap: 6, marginBottom: 20 }}>
                <button onClick={() => setSubTab('files')} style={tabBtnStyle('files')}>
                    <Upload size={14} /> Archivos
                </button>
                <button onClick={() => setSubTab('text')} style={tabBtnStyle('text')}>
                    <Type size={14} /> Texto
                </button>
            </div>

            {/* Files sub-tab */}
            {subTab === 'files' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
                    <FileUploader onFilesAdded={handleFilesAdded} />

                    {files.length > 0 && (
                        <>
                            <UngroupedFiles files={files} ungroupedNames={ungroupedNames} />
                            <GroupBuilder ungroupedNames={ungroupedNames} onCreateGroup={handleCreateGroup} />
                            <ReadyGroups groups={groups} onDeleteGroup={handleDeleteGroup} />

                            {/* Send button */}
                            {groups.length > 0 && (
                                <div>
                                    <button onClick={handleSend} disabled={sending}
                                        style={{
                                            padding: '12px 28px', borderRadius: 8, fontSize: '0.9rem', fontWeight: 700,
                                            background: 'linear-gradient(135deg, #22c55e, #4ade80)', color: '#0f172a',
                                            border: 'none', cursor: sending ? 'not-allowed' : 'pointer',
                                            display: 'flex', alignItems: 'center', gap: 8, width: '100%',
                                            justifyContent: 'center',
                                            boxShadow: '0 4px 16px rgba(34,197,94,0.3)',
                                            opacity: sending ? 0.7 : 1, transition: 'all 0.2s'
                                        }}>
                                        {sending ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
                                        🚀 Enviar al Servidor ({groups.length} grupo(s), {files.length} archivo(s))
                                    </button>

                                    {sendResult && (
                                        <div style={{
                                            marginTop: 12, padding: '12px 16px', borderRadius: 8,
                                            background: sendResult.success ? '#22c55e15' : '#ef444415',
                                            color: sendResult.success ? '#86efac' : '#fca5a5',
                                            border: `1px solid ${sendResult.success ? '#22c55e30' : '#ef444430'}`
                                        }}>
                                            {sendResult.success ? '✅' : '❌'} {sendResult.message}

                                            {sendResult.success && sendResult.assets && (
                                                <div style={{ marginTop: 8, fontSize: '0.75rem', color: '#94a3b8' }}>
                                                    {sendResult.assets.map((a, i) => (
                                                        <div key={i} style={{ marginBottom: 4 }}>
                                                            <strong>{i + 1}.</strong>{' '}
                                                            <code style={{ color: '#818cf8' }}>{a.filename}</code>{' '}
                                                            — {a.vector_tasks_created} tareas creadas
                                                        </div>
                                                    ))}
                                                    <p style={{ color: '#60a5fa', marginTop: 6 }}>
                                                        🔄 Estado limpiado. Puedes cargar nuevos archivos.
                                                    </p>
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </div>
                            )}
                        </>
                    )}
                </div>
            )}

            {/* Text sub-tab */}
            {subTab === 'text' && <TextIngestForm />}
        </div>
    );
}
