import { useState, useEffect } from 'react';
import { Search, Network, Check, X, Layers, RefreshCw, FileText, ChevronDown, ChevronUp, Edit2 } from 'lucide-react';

import {
    getExplorableSeeds,
    getLatentConnections,
    approveLatentConnection,
    getAssetPreview,
    getConcepts,
    getRelationTypes,
    searchGraphEntities,
} from '../../lib/api';
import type { SeedNode, LatentConnectionSuggestion, AssetPreviewResponse, ValidateConnectionItem, ConceptNode, GraphEntity } from '../../lib/api';
import { validateLatentConnections } from '../../lib/api';
import MediaPreview from '../search/MediaPreview';

// =================== AssetGroupCard ===================
interface AssetGroupProps {
    group: { assetId: string; assetName: string; items: LatentConnectionSuggestion[] };
    editedWeights: Record<string, number>;
    editedRelTypes: Record<string, string>;
    approvingIds: Set<string>;
    allConcepts: ConceptNode[];
    allRelationTypes: string[];
    onPreview: (id: string) => void;
    onApprove: (s: LatentConnectionSuggestion | {
        asset_id: string;
        target_concept_id: string;
        relation_type: string;
        proposed_weight: number;
        reasoning: string;
    }, key: string) => void;
    onDiscard: (key: string) => void;
    onWeightChange: (key: string, val: string) => void;
    onRelTypeChange: (key: string, val: string) => void;
    onFilterByKeys: (assetId: string, validKeys: string[]) => void;
}

function AssetGroupCard({ group, editedWeights, editedRelTypes, approvingIds, allConcepts, allRelationTypes, onApprove, onDiscard, onWeightChange, onRelTypeChange, onFilterByKeys }: AssetGroupProps) {
    const [preview, setPreview] = useState<AssetPreviewResponse | null>(null);
    const [loadingPreview, setLoadingPreview] = useState(false);
    const [expanded, setExpanded] = useState(true);
    const [textExpanded, setTextExpanded] = useState(false);
    const [validating, setValidating] = useState(false);
    const [llmNote, setLlmNote] = useState<{ text: string; removed: number } | null>(null);

    // Per-row relation type search open state
    const [relTypeDropdownOpen, setRelTypeDropdownOpen] = useState<string | null>(null);

    // Manual Connection State
    const [manualSearch, setManualSearch] = useState('');
    const [manualWeight, setManualWeight] = useState(0.8);
    const [selectedManualEntity, setSelectedManualEntity] = useState<GraphEntity | null>(null);
    const [manualRelType, setManualRelType] = useState('EVOKES_CONCEPT');
    const [manualRelSearch, setManualRelSearch] = useState('');
    const [manualRelDropdownOpen, setManualRelDropdownOpen] = useState(false);
    const [manualEntityResults, setManualEntityResults] = useState<GraphEntity[]>([]);

    useEffect(() => {
        setLoadingPreview(true);
        getAssetPreview(group.assetId)
            .then(setPreview)
            .catch(() => setPreview(null))
            .finally(() => setLoadingPreview(false));
    }, [group.assetId]);

    const handleValidateWithLLM = async () => {
        setValidating(true);
        setLlmNote(null);
        try {
            const suggestions: ValidateConnectionItem[] = group.items.map(s => ({
                key: `${s.asset_id}-${s.target_concept_id}-${s.relation_type}-${s.direction}`,
                asset_name: s.asset_name,
                target_concept_name: s.target_concept_name,
                relation_type: s.relation_type,
                direction: s.direction,
                reasoning: s.reasoning,
            }));
            const assetContent = preview?.content && preview.content !== 'No textual content available'
                ? preview.content.slice(0, 1200)
                : (preview?.tags ?? []).join(', ');
            const res = await validateLatentConnections({
                asset_name: group.assetName,
                asset_content: assetContent,
                asset_mime_type: preview?.mime_type ?? undefined,
                suggestions,
            });
            onFilterByKeys(group.assetId, res.valid_keys);
            setLlmNote({ text: res.llm_explanation, removed: res.removed_count });
        } catch (e: any) {
            setLlmNote({ text: `Error: ${e?.response?.data?.detail || e?.message || 'Error desconocido'}`, removed: 0 });
        } finally {
            setValidating(false);
        }
    };

    const handleManualApprove = () => {
        if (!selectedManualEntity || Number.isNaN(manualWeight)) return;

        const uniqueKey = `manual-${group.assetId}-${selectedManualEntity.id}`;
        const manualSuggestion = {
            asset_id: group.assetId,
            target_concept_id: selectedManualEntity.id,
            relation_type: manualRelType,
            proposed_weight: Math.min(Math.max(manualWeight, 0), 1),
            reasoning: `Manual connection via Latent Explorer (${selectedManualEntity.entity_type})`
        };

        onApprove(manualSuggestion, uniqueKey);

        // Reset manual form
        setManualSearch('');
        setSelectedManualEntity(null);
        setManualWeight(0.8);
        setManualRelType('EVOKES_CONCEPT');
        setManualEntityResults([]);
    };

    const handleManualSearchChange = async (val: string) => {
        setManualSearch(val);
        setSelectedManualEntity(null);
        if (val.trim().length >= 2) {
            try {
                const res = await searchGraphEntities(val.trim(), 15, group.assetId);
                setManualEntityResults(res.entities);
            } catch {
                setManualEntityResults([]);
            }
        } else {
            setManualEntityResults([]);
        }
    };

    const filteredManualRelTypes = allRelationTypes.filter(t =>
        t.toLowerCase().includes(manualRelSearch.toLowerCase())
    );

    return (
        <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', borderRadius: 16, overflow: 'hidden' }}>

            {/* Parent Card Header */}
            <div style={{ padding: '16px 20px', background: 'var(--bg-tertiary)', borderBottom: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{ width: 36, height: 36, borderRadius: 8, background: 'rgba(236,72,153,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                    <FileText size={18} color="#ec4899" />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 2 }}>Archivo Semilla</div>
                    <div style={{ fontWeight: 700, color: 'var(--text-primary)', fontSize: '0.92rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={group.assetName}>
                        {group.assetName}
                    </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
                    <span style={{ fontSize: '0.7rem', background: 'rgba(236,72,153,0.15)', color: '#f472b6', padding: '2px 10px', borderRadius: 12, fontWeight: 600 }}>
                        {group.items.length} conexión{group.items.length > 1 ? 'es' : ''}
                    </span>
                    <button
                        onClick={handleValidateWithLLM}
                        disabled={validating || group.items.length === 0}
                        title="Validar conexiones con el LLM local"
                        style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: '0.7rem', fontWeight: 600, padding: '4px 10px', borderRadius: 8, border: '1px solid rgba(99,102,241,0.4)', background: 'rgba(99,102,241,0.1)', color: '#818cf8', cursor: validating ? 'not-allowed' : 'pointer', opacity: group.items.length === 0 ? 0.4 : 1 }}
                    >
                        {validating ? <RefreshCw size={12} className="animate-spin" /> : '🤖'}
                        {validating ? 'Validando…' : 'Validar con LLM'}
                    </button>
                    <button onClick={() => setExpanded(e => !e)} style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: 4 }}>
                        {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                    </button>
                </div>
            </div>

            {/* LLM validation result note */}
            {llmNote && (
                <div style={{ padding: '8px 20px', background: llmNote.removed > 0 ? 'rgba(99,102,241,0.08)' : 'rgba(16,185,129,0.08)', borderBottom: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                    <span style={{ fontSize: '1rem', flexShrink: 0 }}>{llmNote.removed > 0 ? '🧠' : '✅'}</span>
                    <div style={{ flex: 1 }}>
                        <div style={{ fontSize: '0.72rem', fontWeight: 600, color: llmNote.removed > 0 ? '#818cf8' : '#34d399', marginBottom: 2 }}>
                            {llmNote.removed > 0 ? `${llmNote.removed} conexión(es) descartada(s) por el LLM` : 'El LLM validó todas las conexiones'}
                        </div>
                        <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', lineHeight: 1.4 }}>{llmNote.text}</div>
                    </div>
                    <button onClick={() => setLlmNote(null)} style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: 2, flexShrink: 0 }}>×</button>
                </div>
            )}

            {expanded && (
                <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 16 }}>

                    {/* Inline Asset Preview */}
                    <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                        {(preview?.download_url || preview?.minio_path) && (
                            <div style={{ flexShrink: 0, width: 160 }}>
                                <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 6 }}>Vista Previa</div>
                                <MediaPreview url={preview.download_url || undefined} path={preview.minio_path || undefined} />
                            </div>
                        )}
                        <div style={{ flex: 1, minWidth: 200, display: 'flex', flexDirection: 'column', gap: 8 }}>
                            {preview && preview.tags?.length > 0 && (
                                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                                    {preview.tags.map((t, i) => (
                                        <span key={i} style={{ fontSize: '0.65rem', background: 'rgba(99,102,241,0.15)', color: '#818cf8', border: '1px solid rgba(99,102,241,0.3)', padding: '1px 8px', borderRadius: 12 }}>#{t}</span>
                                    ))}
                                </div>
                            )}
                            {loadingPreview && <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Cargando metadatos…</div>}
                            {preview?.content && preview.content !== 'No textual content available' && (
                                <div>
                                    <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border-subtle)', borderRadius: 8, padding: '8px 12px', fontFamily: 'monospace', lineHeight: 1.5, maxHeight: textExpanded ? 400 : 100, overflowY: 'auto', transition: 'max-height 0.2s ease' }} className="custom-scrollbar">
                                        {textExpanded ? preview.content : preview.content.slice(0, 400)}
                                        {!textExpanded && preview.content.length > 400 ? '…' : ''}
                                    </div>
                                    {preview.content.length > 400 && (
                                        <button
                                            onClick={() => setTextExpanded(e => !e)}
                                            style={{ marginTop: 4, fontSize: '0.68rem', color: '#818cf8', background: 'transparent', border: 'none', cursor: 'pointer', padding: '2px 4px' }}
                                        >
                                            {textExpanded ? 'Ver menos ▴' : 'Ver todo ▾'}
                                        </button>
                                    )}
                                </div>
                            )}
                            {preview && !preview.download_url && !preview.minio_path && !loadingPreview && (
                                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{preview.type} — sin vista previa de medios</div>
                            )}
                        </div>
                    </div>

                    {/* Manual Connection Section */}
                    <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: 16, marginTop: 4, display: 'flex', flexDirection: 'column', gap: 10 }}>
                        <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 4 }}>Agregar Conexión Manual</div>
                        <div style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-subtle)', borderRadius: 10, padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 10 }}>

                            {/* Row 1: Entity search + rel type */}
                            <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start', flexWrap: 'wrap' }}>
                                {/* Entity search */}
                                <div style={{ flex: 1, minWidth: 200, display: 'flex', flexDirection: 'column', gap: 4 }}>
                                    <label style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Entidad (Concepto / Persona / Evento…)</label>
                                    <div style={{ position: 'relative' }}>
                                        <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
                                        <input
                                            value={manualSearch}
                                            onChange={e => handleManualSearchChange(e.target.value)}
                                            placeholder="Escribe 2+ caracteres para buscar..."
                                            style={{ width: '100%', boxSizing: 'border-box', background: 'var(--bg-primary)', border: selectedManualEntity ? '1px solid #10b981' : '1px solid var(--border-subtle)', borderRadius: 6, padding: '6px 12px 6px 30px', fontSize: '0.8rem', color: 'var(--text-primary)', outline: 'none' }}
                                        />
                                        {manualEntityResults.length > 0 && !selectedManualEntity && (
                                            <div style={{ position: 'absolute', top: '100%', left: 0, right: 0, background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', borderRadius: 6, marginTop: 4, zIndex: 20, maxHeight: 180, overflowY: 'auto', boxShadow: '0 4px 12px rgba(0,0,0,0.5)' }} className="custom-scrollbar">
                                                {manualEntityResults.map(ent => (
                                                    <div
                                                        key={ent.id}
                                                        onClick={() => {
                                                            if (ent.already_connected) return;
                                                            setSelectedManualEntity(ent);
                                                            setManualSearch(ent.name);
                                                            setManualEntityResults([]);
                                                        }}
                                                        style={{
                                                            padding: '6px 12px',
                                                            fontSize: '0.8rem',
                                                            cursor: ent.already_connected ? 'default' : 'pointer',
                                                            borderBottom: '1px solid var(--border-subtle)',
                                                            display: 'flex',
                                                            alignItems: 'center',
                                                            gap: 8,
                                                            opacity: ent.already_connected ? 0.55 : 1,
                                                        }}
                                                        onMouseEnter={el => { if (!ent.already_connected) (el.currentTarget as HTMLElement).style.background = 'var(--bg-tertiary)'; }}
                                                        onMouseLeave={el => (el.currentTarget as HTMLElement).style.background = 'transparent'}
                                                    >
                                                        <span style={{ fontSize: '0.65rem', background: ent.already_connected ? 'rgba(245,158,11,0.15)' : 'rgba(99,102,241,0.2)', color: ent.already_connected ? '#f59e0b' : '#818cf8', padding: '1px 6px', borderRadius: 4, flexShrink: 0, fontWeight: 600 }}>
                                                            {ent.entity_type}
                                                        </span>
                                                        <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{ent.name}</span>
                                                        {ent.already_connected && (
                                                            <span style={{ fontSize: '0.6rem', background: 'rgba(245,158,11,0.15)', color: '#f59e0b', border: '1px solid rgba(245,158,11,0.3)', padding: '1px 6px', borderRadius: 4, flexShrink: 0 }}>Ya conectado</span>
                                                        )}
                                                    </div>
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                </div>

                                {/* Relation type selector */}
                                <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 160 }}>
                                    <label style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Tipo de Relación</label>
                                    <div style={{ position: 'relative' }}>
                                        <button
                                            onClick={() => setManualRelDropdownOpen(v => !v)}
                                            style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 4, fontSize: '0.78rem', background: 'var(--bg-primary)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)', padding: '7px 10px', borderRadius: 6, fontFamily: 'monospace', cursor: 'pointer' }}
                                        >
                                            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{manualRelType}</span>
                                            <Edit2 size={11} style={{ flexShrink: 0 }} />
                                        </button>
                                        {manualRelDropdownOpen && (
                                            <div style={{ position: 'absolute', top: '100%', left: 0, background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', borderRadius: 8, marginTop: 4, zIndex: 30, boxShadow: '0 8px 24px rgba(0,0,0,0.5)', display: 'flex', flexDirection: 'column', minWidth: 200 }}>
                                                <div style={{ padding: '6px 8px', borderBottom: '1px solid var(--border-subtle)' }}>
                                                    <input
                                                        autoFocus
                                                        value={manualRelSearch}
                                                        onChange={e => setManualRelSearch(e.target.value)}
                                                        placeholder="Filtrar..."
                                                        style={{ width: '100%', boxSizing: 'border-box', background: 'var(--bg-tertiary)', border: '1px solid var(--border-subtle)', borderRadius: 5, padding: '4px 8px', fontSize: '0.75rem', color: 'var(--text-primary)', outline: 'none' }}
                                                    />
                                                </div>
                                                <div style={{ maxHeight: 160, overflowY: 'auto' }}>
                                                    {filteredManualRelTypes.map(rt => (
                                                        <div key={rt} onClick={() => { setManualRelType(rt); setManualRelDropdownOpen(false); setManualRelSearch(''); }}
                                                            style={{ padding: '6px 10px', fontSize: '0.77rem', cursor: 'pointer', fontFamily: 'monospace', borderBottom: '1px solid var(--border-subtle)', color: rt === manualRelType ? '#f59e0b' : 'var(--text-primary)', background: rt === manualRelType ? 'rgba(245,158,11,0.1)' : 'transparent' }}
                                                            onMouseEnter={el => { if (rt !== manualRelType) (el.currentTarget as HTMLElement).style.background = 'var(--bg-tertiary)'; }}
                                                            onMouseLeave={el => { if (rt !== manualRelType) (el.currentTarget as HTMLElement).style.background = 'transparent'; }}
                                                        >
                                                            {rt}
                                                        </div>
                                                    ))}
                                                    {filteredManualRelTypes.length === 0 && <div style={{ padding: '8px 10px', fontSize: '0.75rem', color: 'var(--text-muted)' }}>Sin resultados</div>}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>

                            {/* Row 2: Weight + Vincular button */}
                            <div style={{ display: 'flex', gap: 10, alignItems: 'flex-end' }}>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: 4, width: 90 }}>
                                    <label style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Peso (0–1)</label>
                                    <input
                                        type="number" step="0.05" min="0" max="1"
                                        value={manualWeight}
                                        onChange={e => setManualWeight(parseFloat(e.target.value))}
                                        style={{ width: '100%', boxSizing: 'border-box', background: 'var(--bg-primary)', border: '1px solid var(--border-subtle)', borderRadius: 6, padding: '6px 8px', fontSize: '0.8rem', textAlign: 'center', color: 'var(--text-primary)' }}
                                    />
                                </div>
                                <button
                                    onClick={handleManualApprove}
                                    disabled={!selectedManualEntity || Number.isNaN(manualWeight)}
                                    style={{ background: 'var(--brand-primary)', color: '#fff', border: 'none', borderRadius: 6, padding: '7px 20px', fontSize: '0.82rem', fontWeight: 600, cursor: (!selectedManualEntity || Number.isNaN(manualWeight)) ? 'not-allowed' : 'pointer', opacity: (!selectedManualEntity || Number.isNaN(manualWeight)) ? 0.5 : 1 }}
                                >
                                    Vincular
                                </button>
                            </div>
                        </div>
                    </div>

                    {/* Connection Suggestion Rows */}
                    <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
                        <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 4 }}>Conexiones Sugeridas</div>
                        {group.items.map(s => {
                            const uniqueKey = `${s.asset_id}-${s.target_concept_id}-${s.relation_type}-${s.direction}`;
                            const isApproving = approvingIds.has(uniqueKey);
                            const currentW = editedWeights[uniqueKey] !== undefined ? editedWeights[uniqueKey] : s.proposed_weight;
                            const currentRelType = editedRelTypes[uniqueKey] ?? s.relation_type;
                            const relTypeSearch = typeof relTypeDropdownOpen === 'string' && relTypeDropdownOpen.startsWith(uniqueKey + '::') ? relTypeDropdownOpen.split('::')[1] : '';
                            const filteredRelTypes = allRelationTypes.filter(t => t.toLowerCase().includes(relTypeSearch.toLowerCase()));
                            return (
                                <div key={uniqueKey} style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-subtle)', borderRadius: 10, padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 10 }}>
                                    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
                                        <div style={{ flex: 1, minWidth: 0 }}>
                                            <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)', marginBottom: 3 }}>
                                                {s.direction === 'seed_to_neighbor' ? 'Semilla ➞ Vecino' : 'Vecino ➞ Semilla'}
                                            </div>
                                            <div style={{ fontWeight: 700, color: '#f472b6', fontSize: '1rem' }}>{s.target_concept_name}</div>
                                         </div>
                                    </div>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                        <div style={{ flex: 1, background: 'rgba(0,0,0,0.2)', borderRadius: 6, padding: '4px 8px', textAlign: 'center' }}>
                                            <div style={{ fontSize: '0.55rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Grafo</div>
                                            <div style={{ fontSize: '0.8rem', fontWeight: 600 }}>{s.current_weight.toFixed(2)}</div>
                                        </div>
                                        <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>+</span>
                                        <div style={{ flex: 1, background: 'rgba(99,102,241,0.1)', borderRadius: 6, padding: '4px 8px', textAlign: 'center' }}>
                                            <div style={{ fontSize: '0.55rem', color: '#818cf8', textTransform: 'uppercase' }}>Vector</div>
                                            <div style={{ fontSize: '0.8rem', fontWeight: 600, color: '#a5b4fc' }}>{s.cosine_similarity.toFixed(2)}</div>
                                        </div>
                                        <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>=</span>
                                        <div style={{ flex: 1, background: 'rgba(236,72,153,0.1)', borderRadius: 6, padding: '4px 8px', textAlign: 'center' }}>
                                            <div style={{ fontSize: '0.55rem', color: '#f472b6', textTransform: 'uppercase' }}>Final</div>
                                            <div style={{ fontSize: '0.8rem', fontWeight: 700, color: '#f472b6' }}>{s.proposed_weight.toFixed(2)}</div>
                                        </div>
                                    </div>
                                    <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', background: 'rgba(0,0,0,0.15)', borderRadius: 6, padding: '6px 10px', lineHeight: 1.5 }}>
                                        <strong style={{ color: 'var(--text-primary)' }}>Motivación: </strong>{s.reasoning}
                                    </div>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                                        {/* Relation type selector */}
                                        <div style={{ position: 'relative', marginRight: 'auto' }}>
                                            <button
                                                onClick={() => setRelTypeDropdownOpen(prev => prev?.startsWith(uniqueKey) ? null : uniqueKey + '::')}
                                                title="Cambiar tipo de relación"
                                                style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.7rem', background: 'var(--bg-primary)', color: currentRelType !== s.relation_type ? '#f59e0b' : 'var(--text-muted)', border: currentRelType !== s.relation_type ? '1px solid #f59e0b' : '1px solid var(--border-subtle)', padding: '4px 10px', borderRadius: 6, fontFamily: 'monospace', cursor: 'pointer' }}
                                            >
                                                {currentRelType}
                                                <Edit2 size={11} />
                                            </button>
                                            {relTypeDropdownOpen?.startsWith(uniqueKey) && (
                                                <div style={{ position: 'absolute', bottom: '110%', left: 0, background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', borderRadius: 8, marginBottom: 4, zIndex: 50, boxShadow: '0 8px 24px rgba(0,0,0,0.5)', display: 'flex', flexDirection: 'column', minWidth: 220 }}>
                                                    <div style={{ padding: '8px 10px', borderBottom: '1px solid var(--border-subtle)' }}>
                                                        <input
                                                            autoFocus
                                                            value={relTypeSearch}
                                                            onChange={e => setRelTypeDropdownOpen(uniqueKey + '::' + e.target.value)}
                                                            placeholder="Buscar tipo de relación..."
                                                            style={{ width: '100%', boxSizing: 'border-box', background: 'var(--bg-tertiary)', border: '1px solid var(--border-subtle)', borderRadius: 6, padding: '5px 8px', fontSize: '0.78rem', color: 'var(--text-primary)', outline: 'none' }}
                                                        />
                                                    </div>
                                                    <div style={{ maxHeight: 180, overflowY: 'auto' }}>
                                                        {filteredRelTypes.map(rt => (
                                                            <div key={rt} onClick={() => { onRelTypeChange(uniqueKey, rt); setRelTypeDropdownOpen(null); }}
                                                                style={{ padding: '7px 12px', fontSize: '0.78rem', cursor: 'pointer', fontFamily: 'monospace', borderBottom: '1px solid var(--border-subtle)', color: rt === currentRelType ? '#f59e0b' : 'var(--text-primary)', background: rt === currentRelType ? 'rgba(245,158,11,0.1)' : 'transparent', transition: 'background 0.1s' }}
                                                                onMouseEnter={e => { if (rt !== currentRelType) (e.currentTarget as HTMLElement).style.background = 'var(--bg-tertiary)'; }}
                                                                onMouseLeave={e => { if (rt !== currentRelType) (e.currentTarget as HTMLElement).style.background = 'transparent'; }}
                                                            >
                                                                {rt}
                                                            </div>
                                                        ))}
                                                        {filteredRelTypes.length === 0 && <div style={{ padding: '8px 12px', fontSize: '0.75rem', color: 'var(--text-muted)' }}>Sin resultados</div>}
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                        <label style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Peso:</label>
                                        <input
                                            type="number" step="0.05" min="0" max="1"
                                            value={currentW}
                                            onChange={e => onWeightChange(uniqueKey, e.target.value)}
                                            style={{ width: 64, background: 'var(--bg-primary)', border: '1px solid var(--border-subtle)', borderRadius: 6, padding: '3px 8px', fontSize: '0.8rem', textAlign: 'center', color: 'var(--text-primary)' }}
                                        />
                                        <button onClick={() => onDiscard(uniqueKey)} style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: '4px 8px', borderRadius: 6 }} title="Descartar">
                                            <X size={16} />
                                        </button>
                                        <button
                                            onClick={() => onApprove({ ...s, relation_type: currentRelType }, uniqueKey)}
                                            disabled={isApproving}
                                            style={{ display: 'flex', alignItems: 'center', gap: 6, background: '#059669', color: '#fff', border: 'none', borderRadius: 7, padding: '5px 14px', fontSize: '0.82rem', fontWeight: 700, cursor: isApproving ? 'not-allowed' : 'pointer' }}
                                        >
                                            {isApproving ? <RefreshCw size={14} className="animate-spin" /> : <Check size={14} />}
                                            Aprobar
                                        </button>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}
        </div>
    );
}

export default function LatentExplorer() {
    // Search State
    const [limit] = useState(40);
    const [sortBy, setSortBy] = useState<'top_connected' | 'random' | 'least_connected'>('top_connected');
    const [seedSearch, setSeedSearch] = useState('');
    const [seeds, setSeeds] = useState<SeedNode[]>([]);
    const [isLoadingSeeds, setIsLoadingSeeds] = useState(false);

    // Selection State
    const [selectedSeed, setSelectedSeed] = useState<SeedNode | null>(null);
    const [suggestions, setSuggestions] = useState<LatentConnectionSuggestion[]>([]);
    const [isLoadingLatent, setIsLoadingLatent] = useState(false);
    const [alpha, setAlpha] = useState(0.3); // Default weight for vector similarity

    // UI states
    const [error, setError] = useState<string | null>(null);
    const [toast, setToast] = useState<{ message: string, type: 'success' | 'error' } | null>(null);
    const [approvingIds, setApprovingIds] = useState<Set<string>>(new Set());

    const showToast = (message: string, type: 'success' | 'error') => {
        setToast({ message, type });
        setTimeout(() => setToast(null), 3000);
    };

    // Asset Preview State
    const [previewAsset, setPreviewAsset] = useState<AssetPreviewResponse | null>(null);
    const [isLoadingPreview, setIsLoadingPreview] = useState(false);

    // Weights local edits
    const [editedWeights, setEditedWeights] = useState<Record<string, number>>({});
    // Relation type overrides per suggestion
    const [editedRelTypes, setEditedRelTypes] = useState<Record<string, string>>({});
    // All available relation types from the graph
    const [allRelationTypes, setAllRelationTypes] = useState<string[]>([]);

    // Graph Concepts for manual linking
    const [allConcepts, setAllConcepts] = useState<ConceptNode[]>([]);

    useEffect(() => {
        // Pre-fetch concepts on mount once, for manual linking combo box
        getConcepts()
            .then(res => setAllConcepts(res.concepts))
            .catch(err => console.error("Failed to load concepts for manual linking", err));
        getRelationTypes()
            .then(res => setAllRelationTypes(res.relation_types))
            .catch(err => console.error("Failed to load relation types", err));
    }, []);

    const fetchSeeds = async (overrideSortBy?: string) => {
        setIsLoadingSeeds(true);
        setSelectedSeed(null);
        setSuggestions([]);
        try {
            const res = await getExplorableSeeds('DigitalAsset', limit, overrideSortBy ?? sortBy, seedSearch);
            setSeeds(res.seeds);
        } catch (err: any) {
            console.error('Failed to fetch seeds:', err);
        } finally {
            setIsLoadingSeeds(false);
        }
    };

    const handleExplore = async () => {
        if (!selectedSeed) return;

        setIsLoadingLatent(true);
        setError(null);
        setSuggestions([]);
        setEditedWeights({});

        try {
            const res = await getLatentConnections(selectedSeed.id, 5, alpha);

            // Deduplicate by the same key used for rendering to prevent broken weight-edit state
            const seen = new Map<string, LatentConnectionSuggestion>();
            for (const s of res.suggestions) {
                const key = `${s.asset_id}-${s.target_concept_id}-${s.relation_type}-${s.direction}`;
                if (!seen.has(key)) seen.set(key, s);
            }
            const unique = Array.from(seen.values());

            setSuggestions(unique);
            setEditedWeights({});
            setEditedRelTypes({});
            if (unique.length === 0) {
                setError('No se encontraron conexiones latentes nuevas para este nodo.');
            }
        } catch (err: any) {
            console.error(err);
            setError(err.response?.data?.detail || err.message || 'Error al explorar conexiones latentes');
        } finally {
            setIsLoadingLatent(false);
        }
    };

    const handleApprove = async (suggestion: LatentConnectionSuggestion | {
        asset_id: string;
        target_concept_id: string;
        relation_type: string;
        proposed_weight: number;
        reasoning: string;
    }, uniqueKey: string) => {
        setApprovingIds(prev => new Set(prev).add(uniqueKey));

        const finalWeight = editedWeights[uniqueKey] !== undefined ? editedWeights[uniqueKey] : suggestion.proposed_weight;

        try {
            await approveLatentConnection({
                asset_id: suggestion.asset_id,
                target_concept_id: suggestion.target_concept_id,
                relation_type: suggestion.relation_type,
                proposed_weight: Math.min(Math.max(finalWeight, 0), 1),
                reasoning: suggestion.reasoning
            });

            // Remove from list on success
            setSuggestions(prev => prev.filter(s => `${s.asset_id}-${s.target_concept_id}-${s.relation_type}-${s.direction}` !== uniqueKey));
            showToast('¡Conexión aprobada e inyectada en el Grafo!', 'success');

        } catch (err: any) {
            console.error(err);
            showToast(err.response?.data?.detail || 'Error al aprobar la conexión', 'error');
        } finally {
            setApprovingIds(prev => {
                const next = new Set(prev);
                next.delete(uniqueKey);
                return next;
            });
        }
    };

    const handleDiscard = (uniqueKey: string) => {
        setSuggestions(prev => prev.filter(s => `${s.asset_id}-${s.target_concept_id}-${s.relation_type}-${s.direction}` !== uniqueKey));
    };

    const handleFilterByKeys = (assetId: string, validKeys: string[]) => {
        const validSet = new Set(validKeys);
        setSuggestions(prev => prev.filter(s => {
            if (s.asset_id !== assetId) return true; // keep other assets untouched
            const key = `${s.asset_id}-${s.target_concept_id}-${s.relation_type}-${s.direction}`;
            return validSet.has(key);
        }));
    };

    const handleWeightChange = (uniqueKey: string, val: string) => {
        const num = parseFloat(val);
        setEditedWeights(prev => ({
            ...prev,
            [uniqueKey]: isNaN(num) ? 0 : num
        }));
    };

    const handleRelTypeChange = (uniqueKey: string, val: string) => {
        setEditedRelTypes(prev => ({ ...prev, [uniqueKey]: val }));
    };

    const handleExportJson = () => {
        const exportData = {
            exported_at: new Date().toISOString(),
            seed: selectedSeed
                ? { id: selectedSeed.id, name: selectedSeed.name, type: selectedSeed.type, connections: selectedSeed.connections }
                : null,
            config: { alpha, sort_by: sortBy },
            total_suggestions: suggestions.length,
            suggestions: suggestions.map(s => {
                const key = `${s.asset_id}-${s.target_concept_id}-${s.relation_type}-${s.direction}`;
                return {
                    asset_id: s.asset_id,
                    asset_name: s.asset_name,
                    target_concept_id: s.target_concept_id,
                    target_concept_name: s.target_concept_name,
                    relation_type: s.relation_type,
                    direction: s.direction,
                    graph_weight: s.current_weight,
                    vector_similarity: s.cosine_similarity,
                    proposed_weight: editedWeights[key] !== undefined ? editedWeights[key] : s.proposed_weight,
                    reasoning: s.reasoning,
                };
            }),
        };
        const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        const seedLabel = selectedSeed?.name?.replace(/[^a-z0-9]/gi, '_').toLowerCase() ?? 'latent';
        a.href = url;
        a.download = `latent_explorer_${seedLabel}_${Date.now()}.json`;
        a.click();
        URL.revokeObjectURL(url);
    };

    const handlePreviewAsset = async (assetId: string) => {
        setIsLoadingPreview(true);
        try {
            const data = await getAssetPreview(assetId);

            // Auto-fetch raw text content if it's missing (No textual content available) but we have the download URL for a text file
            if (data.download_url && data.content === 'No textual content available' &&
                (data.mime_type === 'text/plain' || data.mime_type === 'text/markdown' || data.name.endsWith('.txt') || data.name.endsWith('.md'))) {
                try {
                    const res = await fetch(data.download_url);
                    if (res.ok) {
                        const rawText = await res.text();
                        data.content = rawText.slice(0, 1500) + (rawText.length > 1500 ? '\n\n... (Contenido truncado para la vista previa)' : '');
                    }
                } catch (e) {
                    console.error("Failed to fetch text directly from MinIO", e);
                }
            }

            setPreviewAsset(data);
        } catch (err: any) {
            console.error("Failed to load asset preview", err);
            setError(err.response?.data?.detail || err.message || 'Error al cargar previsualización del activo');
        } finally {
            setIsLoadingPreview(false);
        }
    };

    return (
        <div className="flex flex-col gap-6" style={{ background: 'var(--bg-primary)', color: 'var(--text-primary)' }}>
            <div className="flex gap-6 items-start">

                {/* Lateral Control Panel */}
                <div style={{ width: 320, background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', borderRadius: 16, padding: 24, display: 'flex', flexDirection: 'column', gap: 20 }}>
                    <h2 style={{ fontSize: '1.2rem', fontWeight: 600, borderBottom: '1px solid var(--border-subtle)', paddingBottom: 12 }}>
                        Configuración de Exploración
                    </h2>

                    <div>
                        {/* Search input */}
                        <div style={{ position: 'relative', marginBottom: 10 }}>
                            <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
                            <input
                                value={seedSearch}
                                onChange={e => setSeedSearch(e.target.value)}
                                onKeyDown={e => e.key === 'Enter' && fetchSeeds()}
                                placeholder="Filtrar por nombre…"
                                style={{ width: '100%', boxSizing: 'border-box', background: 'var(--bg-tertiary)', border: '1px solid var(--border-subtle)', borderRadius: 8, padding: '8px 12px 8px 32px', fontSize: '0.83rem', color: 'var(--text-primary)', outline: 'none' }}
                            />
                        </div>

                        {/* Sort mode buttons */}
                        <div style={{ display: 'flex', gap: 4, marginBottom: 10 }}>
                            {([
                                { id: 'top_connected', label: '🏆 Top', title: 'Más conectados' },
                                { id: 'random', label: '🎲 Aleatorio', title: 'Muestra aleatoria' },
                                { id: 'least_connected', label: '🌱 Menos explorados', title: 'Menos conexiones' },
                            ] as const).map(opt => (
                                <button
                                    key={opt.id}
                                    title={opt.title}
                                    onClick={() => { setSortBy(opt.id); fetchSeeds(opt.id); }}
                                    style={{
                                        flex: 1, fontSize: '0.65rem', fontWeight: 600, padding: '5px 4px', borderRadius: 6, border: '1px solid var(--border-subtle)', cursor: 'pointer',
                                        background: sortBy === opt.id ? 'rgba(236,72,153,0.2)' : 'var(--bg-tertiary)',
                                        color: sortBy === opt.id ? '#f472b6' : 'var(--text-muted)',
                                    }}
                                >
                                    {opt.label}
                                </button>
                            ))}
                        </div>

                        {/* Fetch button */}
                        <button
                            className="btn-primary w-full justify-center mb-3"
                            onClick={() => fetchSeeds()}
                            disabled={isLoadingSeeds}
                            style={{ background: 'var(--accent-primary)', color: 'white', border: 'none', padding: '10px', borderRadius: '8px', cursor: isLoadingSeeds ? 'not-allowed' : 'pointer', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '8px' }}
                        >
                            <Search size={16} />
                            {isLoadingSeeds ? 'Cargando...' : `Buscar Seeds (${sortBy === 'top_connected' ? 'Top' : sortBy === 'random' ? 'Aleatorio' : 'Menos explorados'})`}
                        </button>

                        {/* Seeds list */}
                        <div style={{ maxHeight: 280, overflowY: 'auto', background: 'var(--bg-tertiary)', borderRadius: 8, border: '1px solid var(--border-subtle)' }}>
                            {seeds.length === 0 && !isLoadingSeeds ? (
                                <div className="p-4 text-center text-sm text-gray-500">Selecciona un modo y haz clic en Buscar</div>
                            ) : isLoadingSeeds ? (
                                <div className="p-4 text-center text-sm text-gray-500">Cargando...</div>
                            ) : (
                                <div className="flex flex-col">
                                    {seeds.map(seed => (
                                        <button
                                            key={seed.id}
                                            onClick={() => setSelectedSeed(seed)}
                                            style={{
                                                padding: '8px 12px', textAlign: 'left', borderBottom: '1px solid var(--border-subtle)',
                                                background: selectedSeed?.id === seed.id ? 'rgba(236, 72, 153, 0.1)' : 'transparent',
                                                borderLeft: selectedSeed?.id === seed.id ? '2px solid #ec4899' : '2px solid transparent'
                                            }}
                                            className="hover:bg-gray-800/50 transition-colors"
                                        >
                                            <div className="font-medium text-sm truncate" title={seed.name}>{seed.name}</div>
                                            <div className="text-xs text-pink-500 flex justify-between mt-1">
                                                <span>{seed.type}</span>
                                                <span className="text-gray-400">{seed.connections} refs</span>
                                            </div>
                                        </button>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>

                    <div>
                        <div className="flex justify-between items-center mb-2">
                            <label style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Fusión de Vectores (Alpha)</label>
                            <span className="text-sm font-bold text-pink-500">{Math.round(alpha * 100)}%</span>
                        </div>
                        <input
                            type="range"
                            min="0"
                            max="1"
                            step="0.05"
                            value={alpha}
                            onChange={(e) => setAlpha(parseFloat(e.target.value))}
                            style={{ width: '100%', accentColor: '#ec4899' }}
                        />
                        <p className="text-xs text-gray-500 mt-2 leading-relaxed">
                            Controla cuánto peso se le da a la similitud vectorial ({Math.round(alpha * 100)}%) frente al peso estructural existente del grafo ({Math.round((1 - alpha) * 100)}%).
                        </p>
                    </div>

                    <button
                        onClick={handleExplore}
                        disabled={!selectedSeed || isLoadingLatent}
                        style={{
                            width: '100%', background: selectedSeed ? 'var(--accent-primary)' : 'var(--bg-tertiary)',
                            color: selectedSeed ? '#fff' : 'var(--text-muted)', padding: '10px 14px', borderRadius: 8,
                            border: 'none', cursor: selectedSeed && !isLoadingLatent ? 'pointer' : 'not-allowed',
                            display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 8, fontWeight: 600,
                            marginTop: 10
                        }}
                        className="transition-colors"
                    >
                        {isLoadingLatent ? <RefreshCw size={18} className="animate-spin" /> : <Network size={18} />}
                        Explorar Latencias
                    </button>
                </div>

                {/* Main View Panel */}
                <div className="flex-1 flex flex-col gap-4">
                    {error && (
                        <div style={{ padding: 16, background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', borderRadius: 8, border: '1px solid #ef4444' }}>
                            {error}
                        </div>
                    )}

                    {!selectedSeed && !isLoadingLatent && suggestions.length === 0 && (
                        <div style={{ padding: 60, textAlign: 'center', color: 'var(--text-muted)', background: 'var(--bg-secondary)', border: '1px dashed var(--border-subtle)', borderRadius: 16 }}>
                            <Layers size={48} className="mx-auto mb-4 opacity-50" />
                            <h3 className="text-lg font-medium mb-2">Buscador Latente</h3>
                            <p>Selecciona un nodo semilla a la izquierda y presiona explorar para descubrir conexiones ocultas generadas mediante topología vectorial.</p>
                        </div>
                    )}

                    {isLoadingLatent && (
                        <div style={{ padding: 60, textAlign: 'center', color: 'var(--text-muted)', background: 'var(--bg-secondary)', borderRadius: 16, border: '1px solid var(--border-subtle)' }}>
                            <div className="loading-spinner mb-4 mx-auto" />
                            <p>Mapeando espacios vectoriales y contrastando grafo estructural...</p>
                        </div>
                    )}

                    {!isLoadingLatent && suggestions.length > 0 && (() => {
                        // ── Group suggestions by asset_id ──
                        const grouped = suggestions.reduce<Record<string, { assetName: string; assetId: string; items: typeof suggestions }>>((acc, s) => {
                            if (!acc[s.asset_id]) acc[s.asset_id] = { assetName: s.asset_name, assetId: s.asset_id, items: [] };
                            acc[s.asset_id].items.push(s);
                            return acc;
                        }, {});

                        return (
                            <div className="flex flex-col gap-6">
                                {Object.values(grouped).map(group => (
                                    <AssetGroupCard
                                        key={group.assetId}
                                        group={group}
                                        editedWeights={editedWeights}
                                        editedRelTypes={editedRelTypes}
                                        approvingIds={approvingIds}
                                        onPreview={handlePreviewAsset}
                                        onApprove={handleApprove}
                                        onDiscard={handleDiscard}
                                        onWeightChange={handleWeightChange}
                                        onRelTypeChange={handleRelTypeChange}
                                        onFilterByKeys={handleFilterByKeys}
                                        allConcepts={allConcepts}
                                        allRelationTypes={allRelationTypes}
                                    />
                                ))}
                            </div>
                        );
                    })()}

                </div>
            </div>

            {/* Preview Modals */}
            {isLoadingPreview && (
                <div style={{ position: 'fixed', inset: 0, zIndex: 50, background: 'rgba(0,0,0,0.5)', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
                    <div className="bg-gray-900 p-6 rounded-xl border border-gray-700 flex items-center gap-4 text-white">
                        <RefreshCw size={20} className="animate-spin text-pink-500" /> Cargando vista previa...
                    </div>
                </div>
            )}

            {previewAsset && (
                <div style={{ position: 'fixed', inset: 0, zIndex: 100, background: 'rgba(0,0,0,0.75)', display: 'flex', justifyContent: 'center', alignItems: 'center', backdropFilter: 'blur(4px)' }}>
                    <div className="bg-gray-900 border border-gray-700 rounded-xl shadow-2xl w-11/12 max-w-2xl max-h-[85vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-200">
                        <div className="flex justify-between items-center p-4 border-b border-gray-800 bg-gray-900/50">
                            <div className="flex items-center gap-3">
                                <div className="w-10 h-10 rounded-lg bg-indigo-500/10 flex items-center justify-center border border-indigo-500/20 text-indigo-400">
                                    <FileText size={20} />
                                </div>
                                <h3 className="font-semibold text-lg text-white truncate max-w-sm" title={previewAsset.name}>{previewAsset.name}</h3>
                            </div>
                            <button onClick={() => setPreviewAsset(null)} className="p-2 rounded-lg hover:bg-gray-800 text-gray-400 hover:text-white transition-colors">
                                <X size={20} />
                            </button>
                        </div>
                        <div className="p-6 overflow-y-auto custom-scrollbar flex-1 text-sm text-gray-300">
                            <div className="mb-4 flex flex-wrap items-center gap-2">
                                <span className="bg-gray-800 border border-gray-700 text-gray-300 px-2 py-1 rounded text-xs">Tipo: {previewAsset.type}</span>
                                {previewAsset.tags.map((tag, idx) => (
                                    <span key={idx} className="bg-indigo-900/30 text-indigo-300 border border-indigo-500/30 px-2 py-1 rounded-full text-xs">#{tag}</span>
                                ))}
                            </div>

                            {(previewAsset.minio_path || previewAsset.download_url) && (
                                <div className="mb-4">
                                    <MediaPreview
                                        path={previewAsset.minio_path}
                                        url={previewAsset.download_url}
                                    />
                                </div>
                            )}

                            <div className="bg-black/40 border border-gray-800 rounded-lg p-4 font-mono text-xs whitespace-pre-wrap leading-relaxed text-gray-400 select-text">
                                {previewAsset.content}
                            </div>
                        </div>
                        <div className="p-4 border-t border-gray-800 bg-gray-900/50 text-right">
                            <button onClick={() => setPreviewAsset(null)} className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-white rounded-lg transition-colors font-medium text-sm border border-gray-700">
                                Cerrar Vista Previa
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Toast Notification */}
            {toast && (
                <div style={{
                    position: 'fixed', bottom: 24, right: 24, zIndex: 9999,
                    background: toast.type === 'success' ? 'rgba(16, 185, 129, 0.95)' : 'rgba(239, 68, 68, 0.95)',
                    color: 'white', padding: '14px 24px', borderRadius: '12px',
                    boxShadow: '0 10px 25px rgba(0,0,0,0.5)', fontWeight: 500,
                    display: 'flex', alignItems: 'center', gap: 10,
                    backdropFilter: 'blur(8px)', border: '1px solid rgba(255,255,255,0.1)',
                    animation: 'fadeInUp 0.3s ease-out'
                }}>
                    {toast.type === 'success' ? <Check size={20} className="text-emerald-200" /> : <X size={20} className="text-red-200" />}
                    {toast.message}
                </div>
            )}
        </div>
    );
}

