import { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import {
    useReactTable, getCoreRowModel, flexRender,
    createColumnHelper
} from '@tanstack/react-table';
import type { ColumnDef } from '@tanstack/react-table';
import {
    RefreshCw, Loader2, CheckCircle2,
    ChevronDown, ChevronRight, Plus, Trash2, Rocket,
    Inbox, PenTool, Database, Hash
} from 'lucide-react';

// ==========================================
// TYPES
// ==========================================

const API = 'http://localhost:8000';

interface EntityRow {
    name: string;
    description: string;
    [key: string]: any;
}

interface PersonRow extends EntityRow { role: string; confidence: number; }
interface LocationRow extends EntityRow { type: string; confidence: number; }
interface OrgRow extends EntityRow { type: string; confidence: number; }
interface ConceptRow { name: string; definition: string; domain: string; reasoning: string; confidence: number; }

interface InboxItem {
    file_hash: string;
    filename: string;
    processing_status: string;
    ai_summary: string;
    suggested_entities: {
        persons?: PersonRow[];
        locations?: LocationRow[];
        organizations?: OrgRow[];
    };
    suggested_concepts: ConceptRow[];
    tags: string[];
}

interface InboxStats { pending: number; approved: number; rejected: number; total: number; }
interface NodeType { id: string; name: string; label: string; description: string; properties: string[]; }
interface ConnectionType { id: string; name: string; label: string; description: string; }

// ==========================================
// EDITABLE TABLE COMPONENT
// ==========================================

function EditableTable<T extends Record<string, any>>({
    data, columns, onDataChange, emptyRow
}: {
    data: T[];
    columns: ColumnDef<T, any>[];
    onDataChange: (data: T[]) => void;
    emptyRow: T;
}) {
    const table = useReactTable({
        data,
        columns,
        getCoreRowModel: getCoreRowModel(),
    });

    const addRow = () => onDataChange([...data, { ...emptyRow }]);
    const removeRow = (index: number) => onDataChange(data.filter((_, i) => i !== index));
    const updateCell = (rowIndex: number, columnId: string, value: any) => {
        const newData = data.map((row, i) =>
            i === rowIndex ? { ...row, [columnId]: value } : row
        );
        onDataChange(newData);
    };

    const cellStyle: React.CSSProperties = {
        padding: '6px 8px', borderBottom: '1px solid var(--surface)', fontSize: '0.75rem', color: 'var(--text-secondary)'
    };
    const headerStyle: React.CSSProperties = {
        padding: '8px 8px', textAlign: 'left', fontSize: '0.7rem', fontWeight: 600,
        color: 'var(--text-secondary)', borderBottom: '1px solid var(--border)', whiteSpace: 'nowrap'
    };
    const inputStyle: React.CSSProperties = {
        width: '100%', padding: '4px 6px', borderRadius: 4, fontSize: '0.75rem',
        background: 'var(--background-secondary)', border: '1px solid var(--border)', color: 'var(--text-primary)', outline: 'none'
    };

    return (
        <div>
            <div style={{ overflowX: 'auto', border: '1px solid var(--surface)', borderRadius: 6 }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                        {table.getHeaderGroups().map(hg => (
                            <tr key={hg.id} style={{ background: 'var(--background-secondary)' }}>
                                {hg.headers.map(h => (
                                    <th key={h.id} style={headerStyle}>
                                        {flexRender(h.column.columnDef.header, h.getContext())}
                                    </th>
                                ))}
                                <th style={{ ...headerStyle, width: 40 }}></th>
                            </tr>
                        ))}
                    </thead>
                    <tbody>
                        {table.getRowModel().rows.map((row, rowIdx) => (
                            <tr key={row.id}
                                onMouseEnter={e => (e.currentTarget.style.background = 'color-mix(in srgb, var(--surface) 19%, transparent)')}
                                onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                            >
                                {row.getVisibleCells().map(cell => {
                                    const colId = cell.column.id;
                                    const value = cell.getValue();
                                    const meta = (cell.column.columnDef.meta as any) || {};

                                    return (
                                        <td key={cell.id} style={cellStyle}>
                                            {meta.type === 'select' ? (
                                                <select value={value as string}
                                                    onChange={e => updateCell(rowIdx, colId, e.target.value)}
                                                    style={{ ...inputStyle, cursor: 'pointer' }}>
                                                    {(meta.options || []).map((opt: string) => (
                                                        <option key={opt} value={opt}>{opt}</option>
                                                    ))}
                                                </select>
                                            ) : meta.type === 'number' ? (
                                                <input type="number" value={value as number}
                                                    onChange={e => updateCell(rowIdx, colId, parseFloat(e.target.value) || 0)}
                                                    step={0.1} min={0} max={1}
                                                    style={{ ...inputStyle, width: 60 }}
                                                />
                                            ) : (
                                                <input value={value as string}
                                                    onChange={e => updateCell(rowIdx, colId, e.target.value)}
                                                    style={inputStyle}
                                                />
                                            )}
                                        </td>
                                    );
                                })}
                                <td style={cellStyle}>
                                    <button onClick={() => removeRow(rowIdx)} style={{
                                        background: 'transparent', border: 'none', cursor: 'pointer',
                                        color: '#ef4444', padding: 4, borderRadius: 4
                                    }}>
                                        <Trash2 size={12} />
                                    </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
            <button onClick={addRow} style={{
                padding: '4px 12px', borderRadius: 4, fontSize: '0.7rem', marginTop: 6,
                background: 'var(--border)', color: 'var(--text-secondary)', border: '1px solid var(--text-muted)',
                cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4
            }}>
                <Plus size={10} /> Agregar fila
            </button>
        </div>
    );
}

// ==========================================
// ENTITY EDITOR (5 tabs within an inbox item)
// ==========================================

const personColumnHelper = createColumnHelper<PersonRow>();
const personColumns: ColumnDef<PersonRow, any>[] = [
    personColumnHelper.accessor('name', { header: 'Nombre', meta: { type: 'text' } }),
    personColumnHelper.accessor('description', { header: 'Descripción', meta: { type: 'text' } }),
    personColumnHelper.accessor('role', { header: 'Rol', meta: { type: 'text' } }),
    personColumnHelper.accessor('confidence', { header: 'Confianza', meta: { type: 'number' } }),
];
const emptyPerson: PersonRow = { name: '', description: '', role: '', confidence: 1.0 };

const locationColumnHelper = createColumnHelper<LocationRow>();
const locationColumns: ColumnDef<LocationRow, any>[] = [
    locationColumnHelper.accessor('name', { header: 'Nombre', meta: { type: 'text' } }),
    locationColumnHelper.accessor('description', { header: 'Descripción', meta: { type: 'text' } }),
    locationColumnHelper.accessor('type', {
        header: 'Tipo',
        meta: { type: 'text' }
    }),
    locationColumnHelper.accessor('confidence', { header: 'Confianza', meta: { type: 'number' } }),
];
const emptyLocation: LocationRow = { name: '', description: '', type: 'Otro', confidence: 1.0 };

const orgColumnHelper = createColumnHelper<OrgRow>();
const orgColumns: ColumnDef<OrgRow, any>[] = [
    orgColumnHelper.accessor('name', { header: 'Nombre', meta: { type: 'text' } }),
    orgColumnHelper.accessor('description', { header: 'Descripción', meta: { type: 'text' } }),
    orgColumnHelper.accessor('type', {
        header: 'Tipo',
        meta: { type: 'select', options: ['company', 'government', 'ngo', 'educational', 'media', 'other'] }
    }),
    orgColumnHelper.accessor('confidence', { header: 'Confianza', meta: { type: 'number' } }),
];
const emptyOrg: OrgRow = { name: '', description: '', type: 'other', confidence: 1.0 };

const conceptColumnHelper = createColumnHelper<ConceptRow>();
const conceptColumns: ColumnDef<ConceptRow, any>[] = [
    conceptColumnHelper.accessor('name', { header: 'Nombre', meta: { type: 'text' } }),
    conceptColumnHelper.accessor('definition', { header: 'Definición', meta: { type: 'text' } }),
    conceptColumnHelper.accessor('domain', {
        header: 'Dominio',
        meta: { type: 'text' }
    }),
    conceptColumnHelper.accessor('reasoning', { header: 'Razonamiento', meta: { type: 'text' } }),
    conceptColumnHelper.accessor('confidence', { header: 'Confianza', meta: { type: 'number' } }),
];
const emptyConcept: ConceptRow = { name: '', definition: '', domain: 'general', reasoning: '', confidence: 1.0 };

type EntityTab = 'persons' | 'locations' | 'organizations' | 'concepts' | 'tags';

function EntityEditor({ item, onApprove }: { item: InboxItem; onApprove: (data: any) => void }) {
    const [activeTab, setActiveTab] = useState<EntityTab>('persons');
    const [persons, setPersons] = useState<PersonRow[]>(() =>
        (item.suggested_entities?.persons || []).map(p => ({ name: p.name || '', description: p.description || '', role: p.role || '', confidence: p.confidence ?? 1.0 }))
    );
    const [locations, setLocations] = useState<LocationRow[]>(() =>
        (item.suggested_entities?.locations || []).map(l => ({ name: l.name || '', description: l.description || '', type: l.type || 'other', confidence: l.confidence ?? 1.0 }))
    );
    const [orgs, setOrgs] = useState<OrgRow[]>(() =>
        (item.suggested_entities?.organizations || []).map(o => ({ name: o.name || '', description: o.description || '', type: o.type || 'other', confidence: o.confidence ?? 1.0 }))
    );
    const [concepts, setConcepts] = useState<ConceptRow[]>(() =>
        (item.suggested_concepts || []).map(c => ({ name: c.name || '', definition: c.definition || '', domain: c.domain || 'general', reasoning: c.reasoning || '', confidence: c.confidence ?? 1.0 }))
    );
    const [tagsStr, setTagsStr] = useState(() => (item.tags || []).join(', '));

    const handleApprove = () => {
        const cleanRows = <T extends { name: string }>(rows: T[]) =>
            rows.filter(r => r.name && r.name.trim());

        onApprove({
            entities: {
                persons: cleanRows(persons),
                locations: cleanRows(locations),
                organizations: cleanRows(orgs),
            },
            concepts: cleanRows(concepts),
            tags: tagsStr.split(',').map(t => t.trim()).filter(Boolean),
        });
    };

    const tabs: { key: EntityTab; label: string; count: number }[] = [
        { key: 'persons', label: ' Personas', count: persons.length },
        { key: 'locations', label: ' Lugares', count: locations.length },
        { key: 'organizations', label: ' Organizaciones', count: orgs.length },
        { key: 'concepts', label: ' Conceptos', count: concepts.length },
        { key: 'tags', label: ' Tags', count: tagsStr.split(',').filter(t => t.trim()).length },
    ];

    const tabBtnStyle = (key: EntityTab): React.CSSProperties => ({
        padding: '6px 12px', borderRadius: 6, fontSize: '0.7rem', fontWeight: 600,
        background: activeTab === key ? 'var(--border)' : 'transparent',
        color: activeTab === key ? 'var(--text-primary)' : 'var(--text-muted)',
        border: activeTab === key ? '1px solid var(--text-muted)' : '1px solid transparent',
        cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4
    });

    return (
        <div>
            {/* Entity sub-tabs */}
            <div style={{ display: 'flex', gap: 4, marginBottom: 12, flexWrap: 'wrap' }}>
                {tabs.map(t => (
                    <button key={t.key} onClick={() => setActiveTab(t.key)} style={tabBtnStyle(t.key)}>
                        {t.label}
                        <span style={{
                            padding: '0 5px', borderRadius: 4, fontSize: '0.6rem',
                            background: 'var(--surface)', color: 'var(--text-muted)'
                        }}>{t.count}</span>
                    </button>
                ))}
            </div>

            {/* Table content */}
            {activeTab === 'persons' && (
                <EditableTable data={persons} columns={personColumns} onDataChange={setPersons} emptyRow={emptyPerson} />
            )}
            {activeTab === 'locations' && (
                <EditableTable data={locations} columns={locationColumns} onDataChange={setLocations} emptyRow={emptyLocation} />
            )}
            {activeTab === 'organizations' && (
                <EditableTable data={orgs} columns={orgColumns} onDataChange={setOrgs} emptyRow={emptyOrg} />
            )}
            {activeTab === 'concepts' && (
                <EditableTable data={concepts} columns={conceptColumns} onDataChange={setConcepts} emptyRow={emptyConcept} />
            )}
            {activeTab === 'tags' && (
                <div>
                    <p style={{ color: 'var(--text-muted)', fontSize: '0.7rem', marginBottom: 6 }}>
                        Tags separados por comas. Los duplicados con nombres de entidades se filtrarán automáticamente.
                    </p>
                    <textarea value={tagsStr} onChange={e => setTagsStr(e.target.value)}
                        placeholder="ciencia ficción, robots, futuro, IA..."
                        style={{
                            width: '100%', minHeight: 60, padding: '8px 12px', borderRadius: 6,
                            fontSize: '0.8rem', background: 'var(--background-secondary)', border: '1px solid var(--border)',
                            color: 'var(--text-primary)', outline: 'none', resize: 'vertical', fontFamily: 'inherit'
                        }}
                    />
                    {tagsStr && (
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 6 }}>
                            {tagsStr.split(',').map(t => t.trim()).filter(Boolean).map((tag, i) => (
                                <span key={i} style={{
                                    padding: '2px 8px', borderRadius: 4, fontSize: '0.65rem',
                                    background: '#818cf820', color: '#a5b4fc', border: '1px solid #818cf830'
                                }}>{tag}</span>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* Approve button */}
            <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
                <button onClick={handleApprove} style={{
                    padding: '8px 20px', borderRadius: 6, fontSize: '0.8rem', fontWeight: 600,
                    background: 'var(--gradient-primary)',
                    color: 'var(--background-secondary)', border: 'none', cursor: 'pointer',
                    display: 'flex', alignItems: 'center', gap: 6,
                    boxShadow: '0 2px 8px rgba(34,197,94,0.3)'
                }}>
                    <CheckCircle2 size={14} /> Aprobar e Ingestar al Grafo
                </button>
                <button style={{
                    padding: '8px 16px', borderRadius: 6, fontSize: '0.8rem',
                    background: 'var(--border)', color: 'var(--text-secondary)', border: '1px solid var(--text-muted)',
                    cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6
                }}>
                    <Trash2 size={14} /> Rechazar
                </button>
            </div>
        </div>
    );
}

// ==========================================
// SUB-TAB 1: INBOX CURATOR (HITL)
// ==========================================

function InboxCurator() {
    const [stats, setStats] = useState<InboxStats>({ pending: 0, approved: 0, rejected: 0, total: 0 });
    const [items, setItems] = useState<InboxItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [expandedHash, setExpandedHash] = useState<string | null>(null);
    const [actionResult, setActionResult] = useState<string | null>(null);

    const fetchData = useCallback(async () => {
        setLoading(true);
        try {
            const [statsRes, itemsRes] = await Promise.all([
                axios.get(`${API}/inbox/stats`).catch(() => ({ data: { pending: 0, approved: 0, rejected: 0, total: 0 } })),
                axios.get<InboxItem[]>(`${API}/inbox/pending`)
            ]);
            setStats(statsRes.data);
            setItems(Array.isArray(itemsRes.data) ? itemsRes.data : []);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { fetchData(); }, [fetchData]);

    const handleApprove = async (fileHash: string, data: any) => {
        setActionResult(null);
        try {
            const res = await axios.post(`${API}/inbox/${fileHash}/approve`, data);
            const d = res.data;
            setActionResult(` Aprobado: ${d.nodes_created || 0} nodos, ${d.relationships_created || 0} relaciones creadas`);
            setTimeout(() => fetchData(), 1500);
        } catch (err: any) {
            setActionResult(` Error: ${err.response?.data?.detail || err.message}`);
        }
    };

    if (loading) {
        return (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 200, gap: 8, color: 'var(--text-secondary)' }}>
                <Loader2 size={20} className="animate-spin" /> Cargando inbox...
            </div>
        );
    }

    return (
        <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                    Revisa y aprueba las entidades extraídas por IA antes de ingestarlas al grafo.
                </p>
                <button onClick={fetchData} style={{
                    display: 'flex', alignItems: 'center', gap: 6, padding: '6px 14px',
                    borderRadius: 6, background: 'var(--border)', color: 'var(--text-secondary)', border: '1px solid var(--text-muted)',
                    cursor: 'pointer', fontSize: '0.75rem'
                }}>
                    <RefreshCw size={12} /> Refrescar
                </button>
            </div>

            {/* Stats */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 20 }}>
                {[
                    { label: 'Pendientes', value: stats.pending, icon: Inbox, color: '#eab308' },
                    { label: 'Aprobados', value: stats.approved, icon: CheckCircle2, color: '#22c55e' },
                    { label: 'Rechazados', value: stats.rejected, icon: Trash2, color: '#ef4444' },
                    { label: 'Total', value: stats.total, icon: Hash, color: '#818cf8' },
                ].map(s => (
                    <div key={s.label} style={{
                        background: `${s.color}10`, borderRadius: 10, padding: '12px 10px',
                        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2,
                        border: `1px solid ${s.color}30`
                    }}>
                        <s.icon size={16} style={{ color: s.color }} />
                        <span style={{ fontSize: '1.3rem', fontWeight: 700, color: s.color }}>{s.value}</span>
                        <span style={{ fontSize: '0.65rem', color: s.color }}>{s.label}</span>
                    </div>
                ))}
            </div>

            {/* Items */}
            {items.length === 0 ? (
                <div style={{
                    padding: 24, borderRadius: 10, background: '#22c55e08',
                    border: '1px solid #22c55e20', textAlign: 'center', color: '#86efac'
                }}>
                     ¡Todo al día! No hay items pendientes de revisión.
                </div>
            ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    <div style={{
                        padding: '8px 12px', borderRadius: 6, fontSize: '0.8rem',
                        background: '#eab30815', color: '#fbbf24', border: '1px solid #eab30830'
                    }}>
                         <strong>{items.length}</strong> items pendientes de revisión
                    </div>

                    {items.map((item) => {
                        const hash = item.file_hash;
                        const isExpanded = expandedHash === hash;
                        const entities = item.suggested_entities || {};
                        const totalEntities = (entities.persons?.length || 0) + (entities.locations?.length || 0) + (entities.organizations?.length || 0);
                        const totalConcepts = (item.suggested_concepts || []).length;

                        return (
                            <div key={hash} style={{
                                background: 'var(--surface)', borderRadius: 8, border: '1px solid var(--border)',
                                overflow: 'hidden'
                            }}>
                                {/* Item header */}
                                <div onClick={() => setExpandedHash(isExpanded ? null : hash)}
                                    style={{
                                        display: 'flex', alignItems: 'center', gap: 10, padding: '12px 16px',
                                        cursor: 'pointer', transition: 'background 0.15s'
                                    }}
                                    onMouseEnter={e => (e.currentTarget.style.background = 'var(--border)')}
                                    onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                                >
                                    {isExpanded ? <ChevronDown size={14} style={{ color: '#818cf8' }} />
                                        : <ChevronRight size={14} style={{ color: '#818cf8' }} />}
                                    <span style={{ color: '#eab308' }}></span>
                                    <span style={{ color: 'var(--text-primary)', fontWeight: 600, fontSize: '0.9rem' }}>
                                        {item.filename}
                                    </span>
                                    <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                                        — {totalEntities} entidades, {totalConcepts} conceptos
                                    </span>
                                    <span style={{ color: 'var(--text-muted)', fontSize: '0.6rem', marginLeft: 'auto' }}>
                                        {hash.substring(0, 12)}...
                                    </span>
                                </div>

                                {/* Expanded content */}
                                {isExpanded && (
                                    <div style={{ padding: '0 16px 16px', borderTop: '1px solid var(--border)' }}>
                                        {/* AI Summary */}
                                        <div style={{ marginTop: 12, marginBottom: 16 }}>
                                            <h4 style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: 6 }}>
                                                 Resumen AI
                                            </h4>
                                            <div style={{
                                                padding: 10, borderRadius: 6, fontSize: '0.8rem',
                                                background: 'var(--background-secondary)', border: '1px solid var(--surface)',
                                                color: 'var(--text-secondary)', maxHeight: 100, overflow: 'auto'
                                            }}>
                                                {item.ai_summary || 'Sin resumen disponible'}
                                            </div>
                                        </div>

                                        {/* Entity Editor */}
                                        <h4 style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: 10 }}>
                                             Editar Entidades y Conceptos
                                        </h4>
                                        <EntityEditor
                                            item={item}
                                            onApprove={(data) => handleApprove(hash, data)}
                                        />
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            )}

            {/* Result */}
            {actionResult && (
                <div style={{
                    padding: '10px 14px', borderRadius: 8, fontSize: '0.85rem', marginTop: 12,
                    background: actionResult.startsWith('') ? '#22c55e15' : '#ef444415',
                    color: actionResult.startsWith('') ? '#86efac' : '#fca5a5',
                    border: `1px solid ${actionResult.startsWith('') ? '#22c55e30' : '#ef444430'}`
                }}>
                    {actionResult}
                </div>
            )}
        </div>
    );
}

// ==========================================
// SUB-TAB 2: MANUAL NODE CREATOR
// ==========================================

function ManualNodeCreator() {
    const [nodeTypes, setNodeTypes] = useState<NodeType[]>([]);
    const [selectedType, setSelectedType] = useState('');
    const [properties, setProperties] = useState<Record<string, string>>({});
    const [creating, setCreating] = useState(false);
    const [result, setResult] = useState<string | null>(null);
    const [createdNodes, setCreatedNodes] = useState<{ type: string; nodeId: string; props: Record<string, string> }[]>([]);

    useEffect(() => {
        axios.get<NodeType[]>(`${API}/graph/node-types`).then(res => {
            setNodeTypes(res.data || []);
            if (res.data?.length) setSelectedType(res.data[0].id);
        }).catch(() => { });
    }, []);

    const selectedNode = nodeTypes.find(n => n.id === selectedType);

    useEffect(() => {
        if (selectedNode) {
            const props: Record<string, string> = {};
            for (const p of selectedNode.properties) props[p] = '';
            setProperties(props);
        }
    }, [selectedType, selectedNode]);

    const handleCreate = async () => {
        const filtered = Object.fromEntries(Object.entries(properties).filter(([_, v]) => v.trim()));
        if (Object.keys(filtered).length === 0) {
            setResult(' Debes llenar al menos una propiedad');
            return;
        }
        setCreating(true);
        setResult(null);
        try {
            const res = await axios.post(`${API}/graph/nodes`, {
                node_type: selectedType,
                properties: filtered
            });
            if (res.data.success) {
                setResult(` ${res.data.message}`);
                setCreatedNodes(prev => [...prev, {
                    type: selectedType, nodeId: res.data.neo4j_node_id || '?', props: filtered
                }]);
                if (selectedNode) {
                    const props: Record<string, string> = {};
                    for (const p of selectedNode.properties) props[p] = '';
                    setProperties(props);
                }
            }
        } catch (err: any) {
            setResult(` Error: ${err.response?.data?.detail || err.message}`);
        } finally {
            setCreating(false);
        }
    };

    const inputStyle: React.CSSProperties = {
        width: '100%', padding: '8px 12px', borderRadius: 6, fontSize: '0.8rem',
        background: 'var(--background-secondary)', border: '1px solid var(--border)', color: 'var(--text-primary)', outline: 'none'
    };

    return (
        <div>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: 16 }}>
                Crea nodos manualmente en el grafo de conocimiento.
            </p>

            {nodeTypes.length === 0 ? (
                <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                    Cargando tipos de nodo...
                </div>
            ) : (
                <>
                    <div style={{ marginBottom: 16 }}>
                        <label style={{ color: 'var(--text-secondary)', fontSize: '0.75rem', fontWeight: 600, display: 'block', marginBottom: 4 }}>
                            Tipo de Nodo
                        </label>
                        <select value={selectedType} onChange={e => setSelectedType(e.target.value)}
                            style={{ ...inputStyle, cursor: 'pointer' }}>
                            {nodeTypes.map(nt => (
                                <option key={nt.id} value={nt.id}>{nt.name}</option>
                            ))}
                        </select>
                    </div>

                    {selectedNode && (
                        <div style={{ marginBottom: 16 }}>
                            <span style={{ color: 'var(--text-secondary)', fontSize: '0.75rem', fontWeight: 600 }}>
                                Propiedades para {selectedNode.name}:
                            </span>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 8 }}>
                                {selectedNode.properties.map(prop => (
                                    <div key={prop}>
                                        <label style={{ color: 'var(--text-muted)', fontSize: '0.7rem', display: 'block', marginBottom: 2 }}>
                                            {prop.charAt(0).toUpperCase() + prop.slice(1)}
                                        </label>
                                        {['content', 'description', 'summary'].includes(prop) ? (
                                            <textarea value={properties[prop] || ''} onChange={e => setProperties(p => ({ ...p, [prop]: e.target.value }))}
                                                style={{ ...inputStyle, minHeight: 60, resize: 'vertical', fontFamily: 'inherit' }}
                                            />
                                        ) : (
                                            <input value={properties[prop] || ''} onChange={e => setProperties(p => ({ ...p, [prop]: e.target.value }))}
                                                style={inputStyle}
                                            />
                                        )}
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    <button onClick={handleCreate} disabled={creating} style={{
                        padding: '8px 20px', borderRadius: 6, fontSize: '0.8rem', fontWeight: 600,
                        background: 'var(--gradient-primary)', color: '#fff',
                        border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
                        boxShadow: '0 2px 8px rgba(99,102,241,0.3)'
                    }}>
                        {creating ? <Loader2 size={14} className="animate-spin" /> : <Rocket size={14} />}
                        Crear Nodo
                    </button>
                </>
            )}

            {result && (
                <div style={{
                    padding: '8px 12px', borderRadius: 6, fontSize: '0.8rem', marginTop: 12,
                    background: result.startsWith('') ? '#22c55e15' : result.startsWith('') ? '#eab30815' : '#ef444415',
                    color: result.startsWith('') ? '#86efac' : result.startsWith('') ? '#fbbf24' : '#fca5a5',
                    border: `1px solid ${result.startsWith('') ? '#22c55e30' : result.startsWith('') ? '#eab30830' : '#ef444430'}`
                }}>
                    {result}
                </div>
            )}

            {/* Created nodes in session */}
            {createdNodes.length > 0 && (
                <div style={{ marginTop: 20 }}>
                    <h4 style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>
                         Nodos Creados en Esta Sesión
                    </h4>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                        {createdNodes.map((n, i) => (
                            <div key={i} style={{ color: 'var(--text-secondary)', fontSize: '0.75rem' }}>
                                <strong style={{ color: 'var(--text-secondary)' }}>{i + 1}.</strong>{' '}
                                <code style={{ color: '#818cf8' }}>{n.type}</code> — ID: <code style={{ color: '#4ade80' }}>{n.nodeId}</code>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}

// ==========================================
// SUB-TAB 3: SCHEMA VIEWER
// ==========================================

function SchemaViewer() {
    const [nodeTypes, setNodeTypes] = useState<NodeType[]>([]);
    const [connectionTypes, setConnectionTypes] = useState<ConnectionType[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        Promise.all([
            axios.get<NodeType[]>(`${API}/graph/node-types`).catch(() => ({ data: [] })),
            axios.get<ConnectionType[]>(`${API}/graph/connection-types`).catch(() => ({ data: [] })),
        ]).then(([nt, ct]) => {
            setNodeTypes(nt.data || []);
            setConnectionTypes(ct.data || []);
        }).finally(() => setLoading(false));
    }, []);

    if (loading) {
        return (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 200, gap: 8, color: 'var(--text-secondary)' }}>
                <Loader2 size={20} className="animate-spin" /> Cargando schema...
            </div>
        );
    }

    return (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
            {/* Node Types */}
            <div>
                <h4 style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: 10 }}>
                    Tipos de Nodos
                </h4>
                {nodeTypes.map(nt => (
                    <ExpandableSchemaCard key={nt.id} title={` ${nt.name}`}>
                        <p style={{ color: 'var(--text-muted)', fontSize: '0.75rem', marginBottom: 4 }}>
                            <strong>Label:</strong> <code style={{ color: '#818cf8' }}>{nt.label}</code>
                        </p>
                        <p style={{ color: 'var(--text-muted)', fontSize: '0.75rem', marginBottom: 4 }}>
                            <strong>Descripción:</strong> {nt.description}
                        </p>
                        <p style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                            <strong>Propiedades:</strong> {nt.properties.map(p => (
                                <code key={p} style={{ color: 'var(--text-secondary)', marginRight: 4 }}>{p}</code>
                            ))}
                        </p>
                    </ExpandableSchemaCard>
                ))}
                {nodeTypes.length === 0 && (
                    <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>No se encontraron tipos de nodo.</p>
                )}
            </div>

            {/* Connection Types */}
            <div>
                <h4 style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: 10 }}>
                    Tipos de Relaciones
                </h4>
                {connectionTypes.map(ct => (
                    <ExpandableSchemaCard key={ct.id} title={`↔ ${ct.name}`}>
                        <p style={{ color: 'var(--text-muted)', fontSize: '0.75rem', marginBottom: 4 }}>
                            <strong>Label:</strong> <code style={{ color: '#818cf8' }}>{ct.label}</code>
                        </p>
                        <p style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                            <strong>Descripción:</strong> {ct.description}
                        </p>
                    </ExpandableSchemaCard>
                ))}
                {connectionTypes.length === 0 && (
                    <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>No se encontraron tipos de relación.</p>
                )}
            </div>
        </div>
    );
}

function ExpandableSchemaCard({ title, children }: { title: string; children: React.ReactNode }) {
    const [open, setOpen] = useState(false);
    return (
        <div style={{ background: 'var(--background-secondary)', borderRadius: 8, border: '1px solid var(--surface)', overflow: 'hidden', marginBottom: 6 }}>
            <div onClick={() => setOpen(!open)} style={{
                display: 'flex', alignItems: 'center', gap: 6, padding: '10px 12px',
                cursor: 'pointer', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)'
            }}>
                {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                {title}
            </div>
            {open && <div style={{ padding: '0 12px 10px 28px' }}>{children}</div>}
        </div>
    );
}

// ==========================================
// MAIN COMPONENT
// ==========================================

type MainTab = 'curator' | 'manual' | 'schema';

export default function GraphGeneratorTab() {
    const [activeTab, setActiveTab] = useState<MainTab>('curator');

    const tabStyle = (tab: MainTab): React.CSSProperties => ({
        padding: '8px 16px', borderRadius: 8, fontSize: '0.8rem', fontWeight: 600,
        background: activeTab === tab ? 'var(--surface)' : 'transparent',
        color: activeTab === tab ? 'var(--text-primary)' : 'var(--text-muted)',
        border: activeTab === tab ? '1px solid var(--border)' : '1px solid transparent',
        cursor: 'pointer', transition: 'all 0.15s',
        display: 'flex', alignItems: 'center', gap: 6
    });

    return (
        <div>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>
                 Generador de Nodos & Curador
            </h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: 20 }}>
                Gestiona la creación de nodos en el grafo de conocimiento.
            </p>

            {/* Sub-tabs */}
            <div style={{ display: 'flex', gap: 6, marginBottom: 20 }}>
                <button onClick={() => setActiveTab('curator')} style={tabStyle('curator')}>
                    <Inbox size={14} /> Curaduría HITL
                </button>
                <button onClick={() => setActiveTab('manual')} style={tabStyle('manual')}>
                    <PenTool size={14} /> Crear Manual
                </button>
                <button onClick={() => setActiveTab('schema')} style={tabStyle('schema')}>
                    <Database size={14} /> Schema
                </button>
            </div>

            {/* Content */}
            {activeTab === 'curator' && <InboxCurator />}
            {activeTab === 'manual' && <ManualNodeCreator />}
            {activeTab === 'schema' && <SchemaViewer />}
        </div>
    );
}
