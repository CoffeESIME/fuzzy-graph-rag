import { useState } from 'react';

import {
    Search, Merge, Users, MapPin, FolderOpen, Building2, CalendarDays,
    Cpu, FlaskConical, CheckSquare, Square, X, Loader2, AlertCircle,
    Check, Crown, Tag, RefreshCcw, ArrowLeftRight, GitMerge
} from 'lucide-react';
import {
    getEntities, mergeEntityNodes, demoteEntityNodes,
    retypeEntityNode

} from '../../lib/api';
import type { EntityNode } from '../../lib/api';

// ── Constants ────────────────────────────────────────────────────────────────

const ENTITY_TYPES = [
    { label: 'Personas', value: 'Person', icon: Users },
    { label: 'Proyectos', value: 'Project', icon: FolderOpen },
    { label: 'Lugares', value: 'Location', icon: MapPin },
    { label: 'Organizaciones', value: 'Organization', icon: Building2 },
    { label: 'Eventos', value: 'Event', icon: CalendarDays },
    { label: 'Dispositivos', value: 'Device', icon: Cpu },
    { label: 'Métodos', value: 'Method', icon: FlaskConical },
];

const TABS = [
    { key: 'merge', label: 'Fusionar Duplicados', icon: Merge },
    { key: 'cross-merge', label: 'Fusión Cruzada', icon: ArrowLeftRight },
    { key: 'demote', label: 'Degradar a Tag', icon: Tag },
    { key: 'retype', label: 'Cambiar Tipo', icon: RefreshCcw },
] as const;
type TabKey = typeof TABS[number]['key'];

// ── Shared sub-components ────────────────────────────────────────────────────

const Feedback = ({ error, success }: { error: string | null; success: string | null }) => (
    <>
        {error && (
            <div style={{ padding: '12px 16px', background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', color: '#ef4444', borderRadius: 'var(--radius-md)', display: 'flex', gap: 8, alignItems: 'center', fontSize: 13 }}>
                <AlertCircle size={15} /> {error}
            </div>
        )}
        {success && (
            <div style={{ padding: '12px 16px', background: 'rgba(34,197,94,0.1)', border: '1px solid rgba(34,197,94,0.3)', color: '#22c55e', borderRadius: 'var(--radius-md)', display: 'flex', gap: 8, alignItems: 'center', fontSize: 13 }}>
                <Check size={15} /> {success}
            </div>
        )}
    </>
);

const TypePills = ({ value, onChange }: { value: string; onChange: (v: string) => void }) => (
    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {ENTITY_TYPES.map(({ label, value: v, icon: Icon }) => (
            <button
                key={v}
                onClick={() => onChange(v)}
                style={{
                    padding: '5px 13px', display: 'flex', alignItems: 'center', gap: 5, fontSize: 12,
                    background: value === v ? 'var(--brand-primary)' : 'var(--bg-secondary)',
                    color: value === v ? '#fff' : 'var(--text-secondary)',
                    border: `1px solid ${value === v ? 'var(--brand-primary)' : 'var(--border-subtle)'}`,
                    borderRadius: 20, cursor: 'pointer', fontWeight: value === v ? 600 : 400, transition: 'all 0.15s'
                }}
            >
                <Icon size={12} /> {label}
            </button>
        ))}
    </div>
);

interface EntityTableProps {
    entities: EntityNode[];
    selectedIds: Set<string>;
    keepId?: string | null;
    onToggle: (e: EntityNode) => void;
    onSetHub?: (e: EntityNode) => void;
    search: string;
    onSearchChange: (s: string) => void;
    onLoad: () => void;
    isLoading: boolean;
    total: number;
}
const EntityTable = ({ entities, selectedIds, keepId, onToggle, onSetHub, search, onSearchChange, onLoad, isLoading, total }: EntityTableProps) => {
    const filtered = entities.filter(e => e.name.toLowerCase().includes(search.toLowerCase()));
    return (
        <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-lg)', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
            <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', gap: 10, alignItems: 'center' }}>
                <div style={{ position: 'relative', flex: 1 }}>
                    <Search size={14} style={{ position: 'absolute', left: 10, top: 9, color: 'var(--text-secondary)' }} />
                    <input
                        type="text" value={search} onChange={e => onSearchChange(e.target.value)}
                        placeholder="Buscar..."
                        style={{ width: '100%', padding: '7px 12px 7px 30px', background: 'var(--bg-primary)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', color: 'var(--text-primary)', outline: 'none', fontSize: 13 }}
                    />
                </div>
                <button onClick={onLoad} disabled={isLoading} style={{ padding: '7px 14px', display: 'flex', alignItems: 'center', gap: 6, background: 'var(--brand-primary)', color: '#fff', border: 'none', borderRadius: 'var(--radius-md)', cursor: 'pointer', fontSize: 13, opacity: isLoading ? 0.7 : 1, whiteSpace: 'nowrap' }}>
                    {isLoading ? <Loader2 size={13} className="animate-spin" /> : <Search size={13} />} Cargar
                </button>
                <span style={{ fontSize: 11, color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>{filtered.length}/{total} · {selectedIds.size} sel.</span>
            </div>
            <div style={{ overflowY: 'auto', maxHeight: 460 }}>
                {filtered.length === 0 ? (
                    <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-secondary)', fontSize: 13 }}>
                        {total === 0 ? 'Haz clic en Cargar para ver entidades.' : 'Sin resultados.'}
                    </div>
                ) : (
                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <thead style={{ background: 'var(--bg-primary)', position: 'sticky', top: 0, zIndex: 1 }}>
                            <tr>
                                <th style={{ padding: '9px 14px', width: 36, borderBottom: '1px solid var(--border-subtle)' }} />
                                <th style={{ padding: '9px 14px', textAlign: 'left', fontWeight: 600, fontSize: 12, color: 'var(--text-secondary)', borderBottom: '1px solid var(--border-subtle)' }}>Nombre</th>
                                <th style={{ padding: '9px 14px', textAlign: 'right', fontWeight: 600, fontSize: 12, color: 'var(--text-secondary)', borderBottom: '1px solid var(--border-subtle)' }}>Conex.</th>
                                {onSetHub && <th style={{ padding: '9px 14px', width: 56, borderBottom: '1px solid var(--border-subtle)' }} />}
                            </tr>
                        </thead>
                        <tbody>
                            {filtered.map(entity => {
                                const isSel = selectedIds.has(entity.id);
                                const isHub = keepId === entity.id;
                                return (
                                    <tr key={entity.id} onClick={() => onToggle(entity)}
                                        style={{ borderBottom: '1px solid var(--border-subtle)', cursor: 'pointer', background: isHub ? 'rgba(6,182,212,0.08)' : isSel ? 'rgba(6,182,212,0.04)' : 'transparent' }}>
                                        <td style={{ padding: '9px 14px' }}>
                                            {isSel ? <CheckSquare size={16} style={{ color: 'var(--brand-primary)' }} /> : <Square size={16} style={{ color: 'var(--text-disabled)' }} />}
                                        </td>
                                        <td style={{ padding: '9px 14px' }}>
                                            <span style={{ fontWeight: isHub ? 700 : 400, color: isHub ? 'var(--brand-primary)' : 'var(--text-primary)', fontSize: 13 }}>{entity.name}</span>
                                            {isHub && <span style={{ marginLeft: 6, fontSize: 10, padding: '2px 7px', background: 'rgba(6,182,212,0.15)', color: 'var(--brand-primary)', borderRadius: 10, fontWeight: 600 }}>hub</span>}
                                        </td>
                                        <td style={{ padding: '9px 14px', textAlign: 'right', fontSize: 12, color: 'var(--text-secondary)' }}>{entity.connections}</td>
                                        {onSetHub && (
                                            <td style={{ padding: '9px 14px', textAlign: 'center' }}>
                                                {isSel && !isHub && (
                                                    <button onClick={e => { e.stopPropagation(); onSetHub(entity); }}
                                                        title="Establecer como hub (nodo que sobrevive)"
                                                        style={{ background: 'none', border: '1px solid var(--border-subtle)', color: 'var(--text-secondary)', borderRadius: 6, cursor: 'pointer', padding: '2px 6px', display: 'flex', alignItems: 'center', gap: 3, fontSize: 10 }}>
                                                        <Crown size={11} /> hub
                                                    </button>
                                                )}
                                            </td>
                                        )}
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                )}
            </div>
        </div>
    );
};

// ── Merge tab (same-type duplicates) ────────────────────────────────────────

function MergeTab({ nodeType }: { nodeType: string }) {
    const [entities, setEntities] = useState<EntityNode[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [isMerging, setIsMerging] = useState(false);
    const [search, setSearch] = useState('');
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
    const [keepId, setKeepId] = useState<string | null>(null);
    const [targetName, setTargetName] = useState('');
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);

    const load = async () => {
        setIsLoading(true); setError(null); setSuccess(null);
        setEntities([]); setSelectedIds(new Set()); setKeepId(null); setTargetName('');
        try { const r = await getEntities(nodeType, '', 500); setEntities(r.entities); }
        catch (e: any) { setError(e.response?.data?.detail || e.message); }
        finally { setIsLoading(false); }
    };

    const toggle = (entity: EntityNode) => {
        const ns = new Set(selectedIds);
        if (ns.has(entity.id)) {
            ns.delete(entity.id);
            if (keepId === entity.id) {
                const next = [...ns][0] ? entities.find(e => e.id === [...ns][0]) : null;
                setKeepId(next?.id ?? null); setTargetName(next?.name ?? '');
            }
        } else {
            ns.add(entity.id);
            if (ns.size === 1) { setKeepId(entity.id); setTargetName(entity.name); }
        }
        setSelectedIds(ns);
    };

    const canMerge = selectedIds.size >= 2 && keepId && targetName.trim();

    const executeMerge = async () => {
        if (!canMerge) return;
        setIsMerging(true); setError(null); setSuccess(null);
        try {
            const source_ids = [...selectedIds].filter(id => id !== keepId);
            const r = await mergeEntityNodes({ node_type: nodeType, target_name: targetName.trim(), source_ids, keep_id: keepId! });
            setSuccess(r.message);
            setEntities(prev => prev.filter(e => !source_ids.includes(e.id)).map(e => e.id === keepId ? { ...e, name: targetName.trim() } : e));
            setSelectedIds(new Set()); setKeepId(null); setTargetName('');
        } catch (e: any) { setError(e.response?.data?.detail || e.message); }
        finally { setIsMerging(false); }
    };

    const selectedEntities = [...selectedIds].map(id => entities.find(e => e.id === id)).filter(Boolean) as EntityNode[];

    return (
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,2fr) 340px', gap: 20 }}>
            <EntityTable entities={entities} selectedIds={selectedIds} keepId={keepId} onToggle={toggle}
                onSetHub={e => { setKeepId(e.id); setTargetName(e.name); }}
                search={search} onSearchChange={setSearch} onLoad={load} isLoading={isLoading} total={entities.length} />

            <div style={{ display: 'flex', flexDirection: 'column', gap: 16, height: 'max-content', background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-lg)', padding: 20 }}>
                <Feedback error={error} success={success} />

                <div>
                    <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Seleccionados ({selectedIds.size})</div>
                    {selectedEntities.length === 0
                        ? <div style={{ padding: 12, background: 'var(--bg-primary)', border: '1px dashed var(--border-subtle)', borderRadius: 'var(--radius-md)', color: 'var(--text-disabled)', fontSize: 12, textAlign: 'center' }}>Selecciona 2+ nodos</div>
                        : <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                            {selectedEntities.map(entity => (
                                <div key={entity.id} style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '3px 9px', background: keepId === entity.id ? 'rgba(6,182,212,0.12)' : 'var(--bg-primary)', border: `1px solid ${keepId === entity.id ? 'var(--brand-primary)' : 'var(--border-subtle)'}`, borderRadius: 20, fontSize: 12 }}>
                                    {keepId === entity.id && <Crown size={10} style={{ color: 'var(--brand-primary)' }} />}
                                    <span style={{ color: keepId === entity.id ? 'var(--brand-primary)' : 'var(--text-primary)', fontWeight: keepId === entity.id ? 600 : 400 }}>{entity.name}</span>
                                    <X size={11} style={{ cursor: 'pointer', color: 'var(--text-disabled)' }} onClick={() => toggle(entity)} />
                                </div>
                            ))}
                        </div>
                    }
                </div>

                {selectedIds.size >= 2 && (
                    <div style={{ padding: 10, background: 'rgba(6,182,212,0.06)', border: '1px solid rgba(6,182,212,0.18)', borderRadius: 'var(--radius-md)', fontSize: 11, color: 'var(--text-secondary)', display: 'flex', gap: 7 }}>
                        <Crown size={12} style={{ color: 'var(--brand-primary)', flexShrink: 0, marginTop: 1 }} />
                        El nodo <strong style={{ color: 'var(--brand-primary)' }}>hub</strong> sobrevivirá. Los demás se eliminarán y sus relaciones pasarán al hub. Usa el botón "hub" en la fila para cambiar.
                    </div>
                )}

                <div>
                    <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Nombre Canónico</div>
                    <input type="text" value={targetName} onChange={e => setTargetName(e.target.value)} placeholder="Nombre del nodo resultante"
                        style={{ width: '100%', padding: '8px 12px', background: 'var(--bg-primary)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', color: 'var(--text-primary)', outline: 'none', fontSize: 13 }} />
                </div>

                <div style={{ padding: 10, background: 'rgba(234,179,8,0.08)', border: '1px solid rgba(234,179,8,0.2)', borderRadius: 'var(--radius-md)', display: 'flex', gap: 7, fontSize: 11, color: 'var(--text-secondary)' }}>
                    <AlertCircle size={13} style={{ color: '#eab308', flexShrink: 0, marginTop: 1 }} />
                    Los nodos eliminados desaparecen permanentemente. Irreversible.
                </div>

                <button disabled={!canMerge || isMerging} onClick={executeMerge}
                    style={{ padding: '10px', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 7, background: canMerge ? 'var(--brand-primary)' : 'var(--bg-primary)', color: canMerge ? '#fff' : 'var(--text-disabled)', border: `1px solid ${canMerge ? 'var(--brand-primary)' : 'var(--border-subtle)'}`, borderRadius: 'var(--radius-md)', fontWeight: 600, cursor: canMerge ? 'pointer' : 'not-allowed', fontSize: 13 }}>
                    {isMerging ? <Loader2 size={14} className="animate-spin" /> : <Merge size={14} />}
                    {isMerging ? 'Fusionando...' : `Fusionar ${selectedIds.size > 0 ? selectedIds.size : ''} Nodos`}
                </button>
            </div>
        </div>
    );
}

// ── Cross-type merge tab ─────────────────────────────────────────────────────

function CrossMergeTab() {
    const [typeA, setTypeA] = useState('Person');
    const [typeB, setTypeB] = useState('Organization');
    const [entitiesA, setEntitiesA] = useState<EntityNode[]>([]);
    const [entitiesB, setEntitiesB] = useState<EntityNode[]>([]);
    const [isLoadingA, setIsLoadingA] = useState(false);
    const [isLoadingB, setIsLoadingB] = useState(false);
    const [searchA, setSearchA] = useState('');
    const [searchB, setSearchB] = useState('');
    const [sourceId, setSourceId] = useState<string | null>(null);   // will be deleted
    const [targetId, setTargetId] = useState<string | null>(null);   // will survive
    const [targetType, setTargetType] = useState<string>('');        // label for survivor
    const [targetName, setTargetName] = useState('');
    const [isMerging, setIsMerging] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);

    const loadA = async () => {
        setIsLoadingA(true); setError(null); setSourceId(null);
        try { const r = await getEntities(typeA, '', 500); setEntitiesA(r.entities); }
        catch (e: any) { setError(e.response?.data?.detail || e.message); }
        finally { setIsLoadingA(false); }
    };
    const loadB = async () => {
        setIsLoadingB(true); setError(null); setTargetId(null);
        try { const r = await getEntities(typeB, '', 500); setEntitiesB(r.entities); }
        catch (e: any) { setError(e.response?.data?.detail || e.message); }
        finally { setIsLoadingB(false); }
    };

    const sourceEntity = entitiesA.find(e => e.id === sourceId) ?? null;
    const targetEntity = entitiesB.find(e => e.id === targetId) ?? null;
    const canMerge = sourceId && targetId && targetName.trim() && targetType;

    const executeMerge = async () => {
        if (!canMerge) return;
        setIsMerging(true); setError(null); setSuccess(null);
        try {
            // merge source into target (target survives)
            const r = await mergeEntityNodes({
                node_type: typeA,          // used only for validation in backend (source node type)
                target_name: targetName.trim(),
                source_ids: [sourceId!],
                keep_id: targetId!,
            });
            // If the target type changed, also retype the hub
            if (targetType !== typeB) {
                await retypeEntityNode({ node_id: targetId!, from_type: typeB, to_type: targetType });
            }
            setSuccess(`${r.message}${targetType !== typeB ? ` El nodo resultante es ahora ${targetType}.` : ''}`);
            setEntitiesA(prev => prev.filter(e => e.id !== sourceId));
            setSourceId(null); setTargetId(null); setTargetName('');
        } catch (e: any) { setError(e.response?.data?.detail || e.message); }
        finally { setIsMerging(false); }
    };

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            <Feedback error={error} success={success} />

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                {/* Column A - Source (will be deleted) */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <span style={{ fontSize: 12, fontWeight: 600, color: '#ef4444', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Origen (se eliminará)</span>
                    </div>
                    <TypePills value={typeA} onChange={v => { setTypeA(v); setEntitiesA([]); setSourceId(null); }} />
                    <EntityTable
                        entities={entitiesA}
                        selectedIds={sourceId ? new Set([sourceId]) : new Set()}
                        onToggle={e => setSourceId(prev => prev === e.id ? null : e.id)}
                        search={searchA} onSearchChange={setSearchA}
                        onLoad={loadA} isLoading={isLoadingA} total={entitiesA.length}
                    />
                </div>

                {/* Column B - Target (will survive) */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--brand-primary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Destino (hub que sobrevive)</span>
                    <TypePills value={typeB} onChange={v => { setTypeB(v); setEntitiesB([]); setTargetId(null); }} />
                    <EntityTable
                        entities={entitiesB}
                        selectedIds={targetId ? new Set([targetId]) : new Set()}
                        onToggle={e => { setTargetId(prev => prev === e.id ? null : e.id); if (e.id !== targetId) { setTargetName(e.name); setTargetType(typeB); } }}
                        search={searchB} onSearchChange={setSearchB}
                        onLoad={loadB} isLoading={isLoadingB} total={entitiesB.length}
                    />
                </div>
            </div>

            {/* Merge config panel */}
            {(sourceEntity || targetEntity) && (
                <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-lg)', padding: 20, display: 'flex', flexDirection: 'column', gap: 16 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                        <div style={{ padding: '6px 14px', background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.25)', borderRadius: 10, fontSize: 13, color: '#ef4444', fontWeight: 500 }}>
                            {sourceEntity?.name ?? '—'} <span style={{ opacity: 0.6, fontSize: 11 }}>({typeA})</span>
                        </div>
                        <GitMerge size={18} style={{ color: 'var(--text-secondary)' }} />
                        <div style={{ padding: '6px 14px', background: 'rgba(6,182,212,0.1)', border: '1px solid rgba(6,182,212,0.25)', borderRadius: 10, fontSize: 13, color: 'var(--brand-primary)', fontWeight: 500 }}>
                            {targetEntity?.name ?? '—'} <span style={{ opacity: 0.6, fontSize: 11 }}>({typeB})</span>
                        </div>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 200px', gap: 12 }}>
                        <div>
                            <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Nombre canónico del nodo resultante</div>
                            <input type="text" value={targetName} onChange={e => setTargetName(e.target.value)} placeholder="Nombre final"
                                style={{ width: '100%', padding: '8px 12px', background: 'var(--bg-primary)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', color: 'var(--text-primary)', outline: 'none', fontSize: 13 }} />
                        </div>
                        <div>
                            <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Tipo final del hub</div>
                            <select value={targetType} onChange={e => setTargetType(e.target.value)}
                                style={{ width: '100%', padding: '8px 12px', background: 'var(--bg-primary)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', color: 'var(--text-primary)', outline: 'none', fontSize: 13 }}>
                                <option value="">— elegir —</option>
                                {ENTITY_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                            </select>
                        </div>
                    </div>

                    <button disabled={!canMerge || isMerging} onClick={executeMerge}
                        style={{ padding: '10px', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 7, background: canMerge ? 'var(--brand-primary)' : 'var(--bg-primary)', color: canMerge ? '#fff' : 'var(--text-disabled)', border: `1px solid ${canMerge ? 'var(--brand-primary)' : 'var(--border-subtle)'}`, borderRadius: 'var(--radius-md)', fontWeight: 600, cursor: canMerge ? 'pointer' : 'not-allowed', fontSize: 13 }}>
                        {isMerging ? <Loader2 size={14} className="animate-spin" /> : <ArrowLeftRight size={14} />}
                        {isMerging ? 'Fusionando...' : 'Ejecutar Fusión Cruzada'}
                    </button>
                </div>
            )}
        </div>
    );
}

// ── Demote tab ───────────────────────────────────────────────────────────────

function DemoteTab({ nodeType }: { nodeType: string }) {
    const [entities, setEntities] = useState<EntityNode[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [isDemoting, setIsDemoting] = useState(false);
    const [search, setSearch] = useState('');
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);

    const load = async () => {
        setIsLoading(true); setError(null); setSuccess(null); setEntities([]); setSelectedIds(new Set());
        try { const r = await getEntities(nodeType, '', 500); setEntities(r.entities); }
        catch (e: any) { setError(e.response?.data?.detail || e.message); }
        finally { setIsLoading(false); }
    };

    const toggle = (entity: EntityNode) => {
        const ns = new Set(selectedIds);
        ns.has(entity.id) ? ns.delete(entity.id) : ns.add(entity.id);
        setSelectedIds(ns);
    };

    const executeDemote = async () => {
        if (selectedIds.size === 0) return;
        setIsDemoting(true); setError(null); setSuccess(null);
        try {
            const r = await demoteEntityNodes({ node_type: nodeType, source_ids: [...selectedIds] });
            setSuccess(r.message);
            setEntities(prev => prev.filter(e => !selectedIds.has(e.id)));
            setSelectedIds(new Set());
        } catch (e: any) { setError(e.response?.data?.detail || e.message); }
        finally { setIsDemoting(false); }
    };

    const staging = [...selectedIds].map(id => entities.find(e => e.id === id)).filter(Boolean) as EntityNode[];

    return (
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,2fr) 320px', gap: 20 }}>
            <EntityTable entities={entities} selectedIds={selectedIds} onToggle={toggle}
                search={search} onSearchChange={setSearch} onLoad={load} isLoading={isLoading} total={entities.length} />

            <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-lg)', padding: 20, display: 'flex', flexDirection: 'column', gap: 16, height: 'max-content' }}>
                <Feedback error={error} success={success} />

                <div style={{ fontSize: 14, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Tag size={16} style={{ color: '#ef4444' }} /> Entidades a Degradar
                </div>
                <p style={{ margin: 0, fontSize: 12, color: 'var(--text-secondary)' }}>
                    El nombre de cada nodo se guardará como <code style={{ background: 'var(--bg-primary)', padding: '1px 5px', borderRadius: 4 }}>tag</code> en todos sus activos conectados. El nodo desaparecerá del grafo.
                </p>

                <div style={{ minHeight: 80, padding: 10, background: 'var(--bg-primary)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)' }}>
                    {staging.length === 0
                        ? <div style={{ color: 'var(--text-disabled)', fontSize: 12, textAlign: 'center', marginTop: 16 }}>Ninguno seleccionado</div>
                        : <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                            {staging.map(e => (
                                <span key={e.id} style={{ padding: '3px 9px', background: 'rgba(239,68,68,0.1)', color: '#ef4444', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 20, fontSize: 12, display: 'flex', alignItems: 'center', gap: 5 }}>
                                    {e.name}
                                    <X size={11} style={{ cursor: 'pointer' }} onClick={() => toggle(e)} />
                                </span>
                            ))}
                        </div>
                    }
                </div>

                <div style={{ padding: 10, background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 'var(--radius-md)', fontSize: 11, color: 'var(--text-secondary)', display: 'flex', gap: 7 }}>
                    <AlertCircle size={13} style={{ color: '#ef4444', flexShrink: 0, marginTop: 1 }} />
                    Esta operación es irreversible. El nodo se eliminará permanentemente del grafo.
                </div>

                <button disabled={selectedIds.size === 0 || isDemoting} onClick={executeDemote}
                    style={{ padding: '10px', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 7, background: selectedIds.size > 0 ? '#ef4444' : 'var(--bg-primary)', color: selectedIds.size > 0 ? '#fff' : 'var(--text-disabled)', border: `1px solid ${selectedIds.size > 0 ? '#ef4444' : 'var(--border-subtle)'}`, borderRadius: 'var(--radius-md)', fontWeight: 600, cursor: selectedIds.size > 0 ? 'pointer' : 'not-allowed', fontSize: 13 }}>
                    {isDemoting ? <Loader2 size={14} className="animate-spin" /> : <Tag size={14} />}
                    {isDemoting ? 'Degradando...' : `Degradar ${selectedIds.size > 0 ? selectedIds.size : ''} a Tags`}
                </button>
            </div>
        </div>
    );
}

// ── Retype tab ───────────────────────────────────────────────────────────────

function RetypeTab({ nodeType }: { nodeType: string }) {
    const [entities, setEntities] = useState<EntityNode[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [isRetyping, setIsRetyping] = useState(false);
    const [search, setSearch] = useState('');
    const [selectedId, setSelectedId] = useState<string | null>(null);
    const [toType, setToType] = useState('');
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);

    const load = async () => {
        setIsLoading(true); setError(null); setSuccess(null); setEntities([]); setSelectedId(null); setToType('');
        try { const r = await getEntities(nodeType, '', 500); setEntities(r.entities); }
        catch (e: any) { setError(e.response?.data?.detail || e.message); }
        finally { setIsLoading(false); }
    };

    const selectedEntity = entities.find(e => e.id === selectedId) ?? null;
    const canRetype = selectedId && toType && toType !== nodeType;

    const executeRetype = async () => {
        if (!canRetype) return;
        setIsRetyping(true); setError(null); setSuccess(null);
        try {
            const r = await retypeEntityNode({ node_id: selectedId!, from_type: nodeType, to_type: toType });
            setSuccess(r.message);
            setEntities(prev => prev.filter(e => e.id !== selectedId));
            setSelectedId(null); setToType('');
        } catch (e: any) { setError(e.response?.data?.detail || e.message); }
        finally { setIsRetyping(false); }
    };

    return (
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,2fr) 320px', gap: 20 }}>
            <EntityTable entities={entities} selectedIds={selectedId ? new Set([selectedId]) : new Set()}
                onToggle={e => setSelectedId(prev => prev === e.id ? null : e.id)}
                search={search} onSearchChange={setSearch} onLoad={load} isLoading={isLoading} total={entities.length} />

            <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-lg)', padding: 20, display: 'flex', flexDirection: 'column', gap: 16, height: 'max-content' }}>
                <Feedback error={error} success={success} />

                <div style={{ fontSize: 14, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}>
                    <RefreshCcw size={16} style={{ color: 'var(--brand-primary)' }} /> Cambiar Tipo
                </div>

                <div style={{ padding: 12, background: 'var(--bg-primary)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', fontSize: 13 }}>
                    {selectedEntity
                        ? <><strong>{selectedEntity.name}</strong><span style={{ color: 'var(--text-secondary)', fontSize: 12 }}> · {selectedEntity.connections} conexiones</span></>
                        : <span style={{ color: 'var(--text-disabled)' }}>Selecciona un nodo de la lista</span>
                    }
                </div>

                {selectedEntity && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <div style={{ padding: '5px 12px', background: 'var(--bg-primary)', border: '1px solid var(--border-subtle)', borderRadius: 20, fontSize: 12, color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>
                            {nodeType}
                        </div>
                        <RefreshCcw size={14} style={{ color: 'var(--text-secondary)', flexShrink: 0 }} />
                        <select value={toType} onChange={e => setToType(e.target.value)}
                            style={{ flex: 1, padding: '7px 10px', background: 'var(--bg-primary)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', color: 'var(--text-primary)', outline: 'none', fontSize: 13 }}>
                            <option value="">— nuevo tipo —</option>
                            {ENTITY_TYPES.filter(t => t.value !== nodeType).map(t => (
                                <option key={t.value} value={t.value}>{t.label}</option>
                            ))}
                        </select>
                    </div>
                )}

                <p style={{ margin: 0, fontSize: 12, color: 'var(--text-secondary)' }}>
                    El nodo conserva todas sus relaciones existentes — solo cambia su etiqueta en Neo4j.
                </p>

                <button disabled={!canRetype || isRetyping} onClick={executeRetype}
                    style={{ padding: '10px', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 7, background: canRetype ? 'var(--brand-primary)' : 'var(--bg-primary)', color: canRetype ? '#fff' : 'var(--text-disabled)', border: `1px solid ${canRetype ? 'var(--brand-primary)' : 'var(--border-subtle)'}`, borderRadius: 'var(--radius-md)', fontWeight: 600, cursor: canRetype ? 'pointer' : 'not-allowed', fontSize: 13 }}>
                    {isRetyping ? <Loader2 size={14} className="animate-spin" /> : <RefreshCcw size={14} />}
                    {isRetyping ? 'Cambiando...' : 'Aplicar Cambio de Tipo'}
                </button>
            </div>
        </div>
    );
}

// ── Root component ───────────────────────────────────────────────────────────

export default function EntityDedup() {
    const [activeTab, setActiveTab] = useState<TabKey>('merge');
    const [nodeType, setNodeType] = useState('Person');

    const handleTypeChange = (v: string) => setNodeType(v);

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            {/* Header */}
            <div>
                <h3 style={{ margin: '0 0 6px', fontSize: 18, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Users size={18} style={{ color: 'var(--brand-primary)' }} /> Dedup de Entidades
                </h3>
                <p style={{ margin: 0, fontSize: 13, color: 'var(--text-secondary)' }}>
                    Fusiona duplicados, cambia tipos y depura entidades (Personas, Proyectos, Lugares…)
                </p>
            </div>

            {/* Tab bar */}
            <div style={{ display: 'flex', gap: 4, background: 'var(--bg-secondary)', padding: 4, borderRadius: 'var(--radius-md)', width: 'max-content' }}>
                {TABS.map(({ key, label, icon: Icon }) => (
                    <button key={key} onClick={() => setActiveTab(key)}
                        style={{
                            padding: '7px 14px', display: 'flex', alignItems: 'center', gap: 6, fontSize: 13,
                            background: activeTab === key ? 'var(--bg-primary)' : 'transparent',
                            color: activeTab === key ? 'var(--text-primary)' : 'var(--text-secondary)',
                            fontWeight: activeTab === key ? 600 : 400,
                            border: 'none', borderRadius: 'var(--radius-sm)', cursor: 'pointer',
                            boxShadow: activeTab === key ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
                            transition: 'all 0.15s'
                        }}>
                        <Icon size={13} /> {label}
                    </button>
                ))}
            </div>

            {/* Entity type pills — shown for all tabs except cross-merge (it has its own) */}
            {activeTab !== 'cross-merge' && (
                <TypePills value={nodeType} onChange={handleTypeChange} />
            )}

            {/* Tab content */}
            {activeTab === 'merge' && <MergeTab nodeType={nodeType} />}
            {activeTab === 'cross-merge' && <CrossMergeTab />}
            {activeTab === 'demote' && <DemoteTab nodeType={nodeType} />}
            {activeTab === 'retype' && <RetypeTab nodeType={nodeType} />}
        </div>
    );
}
