import { useState, useEffect } from 'react';
import { Network, Search, Merge, AlertTriangle, AlertCircle, Sparkles, CheckSquare, Square, Check, X, ArrowRight, Loader2 } from 'lucide-react';
import { getConcepts, recommendConceptMerges, mergeConcepts, demoteConcepts } from '../../lib/api';
import type { ConceptNode, MergeConceptsRequest, DemoteConceptsRequest } from '../../lib/api';

export interface MergeRecommendation {
    cluster_id: number;
    concepts: ConceptNode[];
    similarity_score: number;
    recommended_hub_name?: string;
}

export default function OntologicalCleanup() {
    const [activeView, setActiveView] = useState<'list' | 'recommendations'>('list');
    const [concepts, setConcepts] = useState<ConceptNode[]>([]);
    const [isLoadingConcepts, setIsLoadingConcepts] = useState(false);
    const [searchQuery, setSearchQuery] = useState('');
    const [strategy, setStrategy] = useState('middle');

    // Recommendation State
    const [recommendations, setRecommendations] = useState<MergeRecommendation[]>([]);
    const [demoteRecommendations, setDemoteRecommendations] = useState<ConceptNode[]>([]);
    const [isRecommending, setIsRecommending] = useState(false);

    // Manual Merge State
    const [selectedConceptIds, setSelectedConceptIds] = useState<Set<string>>(new Set());
    const [targetName, setTargetName] = useState('');
    const [targetDomain, setTargetDomain] = useState('');
    const [isMerging, setIsMerging] = useState(false);
    const [isDemoting, setIsDemoting] = useState(false);

    // Global Messages
    const [error, setError] = useState<string | null>(null);
    const [successMessage, setSuccessMessage] = useState<string | null>(null);

    // Initial load
    useEffect(() => {
        fetchConcepts();
    }, []);

    const fetchConcepts = async () => {
        setIsLoadingConcepts(true);
        setError(null);
        try {
            const res = await getConcepts();
            setConcepts(res.concepts);
        } catch (err: any) {
            console.error('Error fetching concepts:', err);
            setError(err.response?.data?.detail || err.message || 'Error cargando conceptos.');
        } finally {
            setIsLoadingConcepts(false);
        }
    };

    const handleRecommendMerges = async () => {
        setIsRecommending(true);
        setError(null);
        setSuccessMessage(null);
        try {
            const res = await recommendConceptMerges(strategy);
            setRecommendations(res.recommendations);
            setDemoteRecommendations(res.demote_recommendations || []);
            setSuccessMessage(`Se encontraron ${res.total_clusters} grupos de conceptos similares y ${res.demote_recommendations?.length || 0} para degradar a tags.`);
            setActiveView('recommendations');
        } catch (err: any) {
            console.error('Error calculating recommendations:', err);
            setError(err.response?.data?.detail || err.message || 'Error calculando recomendaciones.');
        } finally {
            setIsRecommending(false);
        }
    };

    const handleExecuteMerge = async (sourceNames: string[], tName: string, tDomain: string, clusterId?: number) => {
        if (!tName.trim()) {
            setError("Debes especificar un nombre destino para la fusión.");
            return;
        }
        if (sourceNames.length < 1) {
            setError("Debes seleccionar al menos un nodo origen.");
            return;
        }

        setIsMerging(true);
        setError(null);
        setSuccessMessage(null);

        try {
            const req: MergeConceptsRequest = {
                target_name: tName.trim(),
                target_domain: tDomain.trim(),
                source_names: sourceNames
            };
            const res = await mergeConcepts(req);
            setSuccessMessage(res.message);

            // Clean up UI state
            if (clusterId) {
                // Remove cluster from recommendations
                setRecommendations(prev => prev.filter(c => c.cluster_id !== clusterId));
            } else {
                // Clear manual selection
                setSelectedConceptIds(new Set());
                setTargetName('');
                setTargetDomain('');
            }
            // Refresh list
            fetchConcepts();

        } catch (err: any) {
            console.error('Error merging concepts:', err);
            setError(err.response?.data?.detail || err.message || 'Error al fusionar conceptos.');
        } finally {
            setIsMerging(false);
        }
    };

    const handleExecuteDemote = async () => {
        if (demoteRecommendations.length === 0) return;

        setIsDemoting(true);
        setError(null);
        setSuccessMessage(null);

        try {
            const sourceNames = demoteRecommendations.map(c => c.name);
            const req: DemoteConceptsRequest = {
                source_names: sourceNames
            };
            const res = await demoteConcepts(req);
            setSuccessMessage(res.message);
            // Clear demotion state
            setDemoteRecommendations([]);
            // Refresh main concepts
            fetchConcepts();
        } catch (err: any) {
            console.error('Error demoting concepts:', err);
            setError(err.response?.data?.detail || err.message || 'Error al degradar conceptos a tags.');
        } finally {
            setIsDemoting(false);
        }
    };

    // Derived states
    const filteredConcepts = concepts.filter(c =>
        c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (c.domain || '').toLowerCase().includes(searchQuery.toLowerCase())
    );

    const toggleSelect = (id: string, name: string, domain: string) => {
        const newSet = new Set(selectedConceptIds);
        if (newSet.has(id)) {
            newSet.delete(id);
        } else {
            newSet.add(id);
            // Autofill target if it's the first selection
            if (newSet.size === 1) {
                setTargetName(name);
                setTargetDomain(domain || '');
            }
        }
        setSelectedConceptIds(newSet);
    };

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            {/* Header */}
            <div>
                <h2 style={{ fontSize: 24, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8, margin: 0 }}>
                    <Network size={24} style={{ color: 'var(--brand-primary)' }} />
                    Limpieza Ontológica
                </h2>
                <p style={{ color: 'var(--text-secondary)', margin: '8px 0 0' }}>
                    Identifica conceptos duplicados o similares y fusiónalos en hubs centrales.
                </p>
            </div>

            {/* Quick Actions & Tabs */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 16 }}>
                <div style={{ display: 'flex', gap: 8, background: 'var(--bg-secondary)', padding: 4, borderRadius: 'var(--radius-md)' }}>
                    <button
                        onClick={() => setActiveView('list')}
                        style={{
                            padding: '8px 16px', background: activeView === 'list' ? 'var(--bg-primary)' : 'transparent',
                            color: activeView === 'list' ? 'var(--text-primary)' : 'var(--text-secondary)',
                            fontWeight: activeView === 'list' ? 600 : 400,
                            border: 'none', borderRadius: 'var(--radius-sm)', cursor: 'pointer',
                            boxShadow: activeView === 'list' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none'
                        }}
                    >
                        Todos los Conceptos
                    </button>
                    <button
                        onClick={() => setActiveView('recommendations')}
                        style={{
                            padding: '8px 16px', background: activeView === 'recommendations' ? 'var(--bg-primary)' : 'transparent',
                            color: activeView === 'recommendations' ? 'var(--text-primary)' : 'var(--text-secondary)',
                            fontWeight: activeView === 'recommendations' ? 600 : 400,
                            border: 'none', borderRadius: 'var(--radius-sm)', cursor: 'pointer',
                            boxShadow: activeView === 'recommendations' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
                            display: 'flex', alignItems: 'center', gap: 6
                        }}
                    >
                        Recomendaciones Inteligentes
                        {(recommendations.length > 0 || demoteRecommendations.length > 0) && (
                            <span style={{
                                background: 'var(--brand-primary)', color: '#fff', fontSize: 11,
                                padding: '2px 6px', borderRadius: 10, fontWeight: 600
                            }}>
                                {recommendations.length + (demoteRecommendations.length > 0 ? 1 : 0)}
                            </span>
                        )}
                    </button>
                </div>

                <div style={{ display: 'flex', gap: 12 }}>
                    <select
                        value={strategy}
                        onChange={(e) => setStrategy(e.target.value)}
                        style={{
                            padding: '8px 12px', background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)',
                            color: 'var(--text-primary)', borderRadius: 'var(--radius-md)', outline: 'none', cursor: 'pointer'
                        }}
                    >
                        <option value="top">Conexiones: Alta (Top 200)</option>
                        <option value="upper-mid">Conexiones: Media-Alta</option>
                        <option value="middle">Conexiones: Media (Centro)</option>
                        <option value="lower-mid">Conexiones: Media-Baja</option>
                        <option value="bottom">Conexiones: Baja/Huérfanos</option>
                        <option value="random">Lote Aleatorio</option>
                    </select>
                    <button
                        onClick={handleRecommendMerges}
                        disabled={isRecommending || concepts.length === 0}
                        style={{
                            padding: '8px 16px', display: 'flex', alignItems: 'center', gap: 8,
                            background: 'var(--brand-primary)', color: '#ffffff',
                            border: 'none', borderRadius: 'var(--radius-md)', cursor: 'pointer',
                            fontWeight: 500, opacity: (isRecommending || concepts.length === 0) ? 0.7 : 1
                        }}
                    >
                        {isRecommending ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
                        Encontrar Hubs (Calcular Similitud)
                    </button>
                    <button
                        onClick={fetchConcepts}
                        disabled={isLoadingConcepts}
                        style={{
                            padding: '8px 16px', background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)',
                            color: 'var(--text-primary)', borderRadius: 'var(--radius-md)', cursor: 'pointer'
                        }}
                    >
                        Refrescar
                    </button>
                </div>
            </div>

            {/* Messages */}
            {error && (
                <div style={{ padding: 16, background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)', color: '#ef4444', borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'center', gap: 8 }}>
                    <AlertTriangle size={18} /> {error}
                </div>
            )}
            {successMessage && (
                <div style={{ padding: 16, background: 'rgba(34, 197, 94, 0.1)', border: '1px solid rgba(34, 197, 94, 0.3)', color: '#22c55e', borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Check size={18} /> {successMessage}
                </div>
            )}

            {/* Main Content Area */}
            {activeView === 'list' && (
                <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 2fr) 1fr', gap: 24 }}>
                    {/* List Panel */}
                    <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-lg)', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                        <div style={{ padding: 16, borderBottom: '1px solid var(--border-subtle)', display: 'flex', gap: 16, alignItems: 'center' }}>
                            <div style={{ position: 'relative', flex: 1 }}>
                                <Search size={16} style={{ position: 'absolute', left: 12, top: 10, color: 'var(--text-secondary)' }} />
                                <input
                                    type="text"
                                    placeholder="Buscar conceptos o dominios..."
                                    value={searchQuery}
                                    onChange={(e) => setSearchQuery(e.target.value)}
                                    style={{
                                        width: '100%', padding: '8px 12px 8px 36px', background: 'var(--bg-primary)',
                                        border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)',
                                        color: 'var(--text-primary)', outline: 'none'
                                    }}
                                />
                            </div>
                            <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                                {filteredConcepts.length} de {concepts.length}
                            </div>
                        </div>

                        <div style={{ overflowY: 'auto', maxHeight: 600 }}>
                            {isLoadingConcepts ? (
                                <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-secondary)' }}>Cargando conceptos...</div>
                            ) : filteredConcepts.length === 0 ? (
                                <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-secondary)' }}>No se encontraron conceptos.</div>
                            ) : (
                                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                                    <thead style={{ background: 'var(--bg-primary)', position: 'sticky', top: 0, zIndex: 1 }}>
                                        <tr>
                                            <th style={{ padding: '12px 16px', fontWeight: 600, borderBottom: '1px solid var(--border-subtle)', width: 40 }}></th>
                                            <th style={{ padding: '12px 16px', fontWeight: 600, borderBottom: '1px solid var(--border-subtle)' }}>Nombre</th>
                                            <th style={{ padding: '12px 16px', fontWeight: 600, borderBottom: '1px solid var(--border-subtle)' }}>Dominio</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {filteredConcepts.map(c => (
                                            <tr
                                                key={c.id}
                                                onClick={() => toggleSelect(c.id, c.name, c.domain || '')}
                                                style={{
                                                    borderBottom: '1px solid var(--border-subtle)',
                                                    background: selectedConceptIds.has(c.id) ? 'rgba(6, 182, 212, 0.05)' : 'transparent',
                                                    cursor: 'pointer'
                                                }}
                                                onMouseEnter={(e) => e.currentTarget.style.background = selectedConceptIds.has(c.id) ? 'rgba(6, 182, 212, 0.1)' : 'var(--bg-primary)'}
                                                onMouseLeave={(e) => e.currentTarget.style.background = selectedConceptIds.has(c.id) ? 'rgba(6, 182, 212, 0.05)' : 'transparent'}
                                            >
                                                <td style={{ padding: '12px 16px' }}>
                                                    {selectedConceptIds.has(c.id) ?
                                                        <CheckSquare size={18} style={{ color: 'var(--brand-primary)' }} /> :
                                                        <Square size={18} style={{ color: 'var(--text-disabled)' }} />
                                                    }
                                                </td>
                                                <td style={{ padding: '12px 16px', color: 'var(--text-primary)', fontWeight: 500 }}>
                                                    {c.name}
                                                </td>
                                                <td style={{ padding: '12px 16px', color: 'var(--text-secondary)' }}>
                                                    {c.domain || '-'}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            )}
                        </div>
                    </div>

                    {/* Manual Merge Editor */}
                    <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-lg)', padding: 24, height: 'max-content' }}>
                        <h3 style={{ fontSize: 18, fontWeight: 600, marginTop: 0, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
                            <Merge size={20} />
                            Fusión Manual
                        </h3>

                        <div style={{ marginBottom: 24 }}>
                            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8 }}>
                                Nodos de Origen ({selectedConceptIds.size} seleccionados)
                            </label>
                            {selectedConceptIds.size === 0 ? (
                                <div style={{ padding: 16, background: 'var(--bg-primary)', border: '1px dashed var(--border-subtle)', borderRadius: 'var(--radius-md)', color: 'var(--text-disabled)', fontSize: 13, textAlign: 'center' }}>
                                    Selecciona conceptos de la lista
                                </div>
                            ) : (
                                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                                    {Array.from(selectedConceptIds).map(id => {
                                        const c = concepts.find(x => x.id === id);
                                        return c ? (
                                            <span key={id} style={{ padding: '4px 10px', background: 'var(--bg-primary)', border: '1px solid var(--border-subtle)', borderRadius: 20, fontSize: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
                                                {c.name}
                                                <X size={12} style={{ cursor: 'pointer', color: 'var(--text-disabled)' }} onClick={(e) => { e.stopPropagation(); toggleSelect(c.id, c.name, c.domain || '') }} />
                                            </span>
                                        ) : null;
                                    })}
                                </div>
                            )}
                        </div>

                        <div style={{ marginBottom: 24 }}>
                            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8 }}>
                                Nombre Nodo Destino (Hub)
                            </label>
                            <input
                                type="text"
                                placeholder="Ej: Inteligencia Artificial"
                                value={targetName}
                                onChange={e => setTargetName(e.target.value)}
                                style={{ width: '100%', padding: '10px 14px', background: 'var(--bg-primary)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', color: 'var(--text-primary)', outline: 'none' }}
                            />
                        </div>

                        <div style={{ marginBottom: 24 }}>
                            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8 }}>
                                Dominio Destino (Opcional)
                            </label>
                            <input
                                type="text"
                                placeholder="Ej: Tecnología"
                                value={targetDomain}
                                onChange={e => setTargetDomain(e.target.value)}
                                style={{ width: '100%', padding: '10px 14px', background: 'var(--bg-primary)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', color: 'var(--text-primary)', outline: 'none' }}
                            />
                        </div>

                        <div style={{ padding: 16, background: 'rgba(234, 179, 8, 0.1)', border: '1px solid rgba(234, 179, 8, 0.2)', borderRadius: 'var(--radius-md)', marginBottom: 24 }}>
                            <p style={{ margin: 0, fontSize: 13, color: 'var(--text-secondary)', display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                                <AlertCircle size={16} style={{ color: '#eab308', flexShrink: 0, marginTop: 2 }} />
                                Se moverán todas las relaciones hacia el nodo destino. Los nodos origen desaparecerán. Esta acción es irreversible.
                            </p>
                        </div>

                        <button
                            disabled={selectedConceptIds.size === 0 || !targetName.trim() || isMerging}
                            onClick={() => {
                                const sourceNames = Array.from(selectedConceptIds).map(id => concepts.find(c => c.id === id)?.name).filter(Boolean) as string[];
                                handleExecuteMerge(sourceNames, targetName, targetDomain);
                            }}
                            style={{
                                width: '100%', padding: '12px', background: 'var(--brand-primary)', color: '#fff',
                                border: 'none', borderRadius: 'var(--radius-md)', fontWeight: 600, cursor: 'pointer',
                                opacity: (selectedConceptIds.size === 0 || !targetName.trim() || isMerging) ? 0.5 : 1,
                                display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 8
                            }}
                        >
                            {isMerging ? 'Fusionando...' : 'Ejecutar Fusión'}
                        </button>
                    </div>
                </div>
            )}

            {/* Recommendations View */}
            {activeView === 'recommendations' && (
                <div>
                    {recommendations.length === 0 && !isRecommending ? (
                        <div style={{ padding: 80, textAlign: 'center', background: 'var(--bg-secondary)', border: '1px dashed var(--border-subtle)', borderRadius: 'var(--radius-lg)' }}>
                            <Sparkles size={48} style={{ color: 'var(--text-disabled)', margin: '0 auto 16px' }} />
                            <h3 style={{ margin: '0 0 8px', color: 'var(--text-primary)' }}>Sin recomendaciones actuales</h3>
                            <p style={{ margin: 0, color: 'var(--text-secondary)' }}>Haz clic en "Encontrar Hubs" para que la IA agrupe conceptos similares usando similitud de coseno.</p>
                        </div>
                    ) : (
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(400px, 1fr))', gap: 24 }}>
                            {recommendations.map(cluster => (
                                <MergeRecommendationCard
                                    key={cluster.cluster_id}
                                    cluster={cluster}
                                    onMerge={(targetName, targetDomain, sourceNames) => {
                                        handleExecuteMerge(sourceNames, targetName, targetDomain, cluster.cluster_id);
                                    }}
                                    isMerging={isMerging}
                                />
                            ))}
                        </div>
                    )}

                    {demoteRecommendations.length > 0 && (
                        <div style={{ marginTop: 40, borderTop: '1px solid var(--border-subtle)', paddingTop: 32 }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
                                <div>
                                    <h3 style={{ fontSize: 20, fontWeight: 600, margin: '0 0 8px', display: 'flex', alignItems: 'center', gap: 8 }}>
                                        <AlertTriangle size={20} style={{ color: '#eab308' }} />
                                        Conceptos a Degradar a Tags ({demoteRecommendations.length})
                                    </h3>
                                    <p style={{ margin: 0, color: 'var(--text-secondary)' }}>
                                        El modelo identificó estos nodos como objetos físicos, formatos o descriptores simples que no deberían ser Hubs estructurales en el grafo. Serán eliminados y su nombre pasará a ser un Tag en los archivos conectados.
                                    </p>
                                </div>
                                <button
                                    onClick={handleExecuteDemote}
                                    disabled={isDemoting}
                                    style={{
                                        padding: '10px 20px', background: '#eab308', color: '#fff',
                                        border: 'none', borderRadius: 'var(--radius-md)', fontWeight: 600, cursor: 'pointer',
                                        opacity: isDemoting ? 0.7 : 1, display: 'flex', alignItems: 'center', gap: 8
                                    }}
                                >
                                    {isDemoting ? 'Procesando...' : 'Ejecutar Degradación Masiva'}
                                </button>
                            </div>

                            <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-lg)', padding: 20 }}>
                                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
                                    {demoteRecommendations.map(c => (
                                        <div key={c.id} style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'var(--bg-primary)', padding: '6px 12px', borderRadius: 20, border: '1px solid var(--border-subtle)' }}>
                                            <span style={{ fontSize: 13, fontWeight: 500 }}>{c.name}</span>
                                            {c.domain && <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>({c.domain})</span>}
                                            <button
                                                onClick={() => {
                                                    setDemoteRecommendations(prev => prev.filter(x => x.id !== c.id));
                                                }}
                                                style={{ background: 'none', border: 'none', color: 'var(--text-disabled)', cursor: 'pointer', display: 'flex', alignItems: 'center', padding: 2, marginLeft: 4 }}
                                                title="Excluir de la degradación (Mantener como Hub)"
                                            >
                                                <X size={14} />
                                            </button>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

// Sub-component for recommendation cards
function MergeRecommendationCard({ cluster, onMerge, isMerging }: {
    cluster: MergeRecommendation,
    onMerge: (targetName: string, targetDomain: string, sourceNames: string[]) => void,
    isMerging: boolean
}) {
    // Pick the recommended name if available, else shortest generic
    const targetCandidate = cluster.recommended_hub_name || cluster.concepts.reduce((prev, current) => (prev.name.length < current.name.length) ? prev : current).name;

    const [targetName, setTargetName] = useState(targetCandidate);
    const [targetDomain, setTargetDomain] = useState('');
    const [rejectedIds, setRejectedIds] = useState<Set<string>>(new Set());

    // Sync state if a new recommendation arrives with the same cluster_id but different data (or when data re-loads)
    useEffect(() => {
        setTargetName(targetCandidate);
        setRejectedIds(new Set());
        setTargetDomain('');
    }, [targetCandidate, cluster.cluster_id]);

    const activeConcepts = cluster.concepts.filter(c => !rejectedIds.has(c.id));

    return (
        <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-lg)', padding: 20 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
                <div>
                    <h4 style={{ margin: '0 0 4px', fontSize: 16, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 6 }}>
                        Grupo #{cluster.cluster_id}
                        {cluster.recommended_hub_name ? (
                            <span style={{ fontSize: 12, padding: '2px 8px', background: 'rgba(139, 92, 246, 0.1)', color: '#8b5cf6', borderRadius: 10, fontWeight: 500, display: 'flex', alignItems: 'center', gap: 4 }}>
                                <Sparkles size={12} /> Sugerido por IA
                            </span>
                        ) : (
                            <span style={{ fontSize: 12, padding: '2px 8px', background: 'rgba(34, 197, 94, 0.1)', color: '#22c55e', borderRadius: 10, fontWeight: 500 }}>
                                {(cluster.similarity_score * 100).toFixed(0)}% Similar
                            </span>
                        )}
                    </h4>
                    <p style={{ margin: 0, fontSize: 13, color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: 4 }}>
                        {activeConcepts.length} conceptos a fusionar
                    </p>
                </div>
            </div>

            <div style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', padding: 12, marginBottom: 16 }}>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                    {cluster.concepts.map(c => {
                        const isRejected = rejectedIds.has(c.id);
                        return (
                            <div key={c.id} style={{ display: 'inline-flex', alignItems: 'center', gap: 8, background: isRejected ? 'transparent' : 'var(--bg-secondary)', padding: '6px 10px', borderRadius: 'var(--radius-sm)', border: `1px solid ${isRejected ? 'transparent' : 'var(--border-subtle)'}`, opacity: isRejected ? 0.5 : 1 }}>
                                <div style={{ display: 'flex', flexDirection: 'column', textDecoration: isRejected ? 'line-through' : 'none' }}>
                                    <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>{c.name}</span>
                                    {c.domain && <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{c.domain}</span>}
                                </div>
                                <button
                                    onClick={() => {
                                        setRejectedIds(prev => {
                                            const newSet = new Set(prev);
                                            if (newSet.has(c.id)) newSet.delete(c.id);
                                            else newSet.add(c.id);
                                            return newSet;
                                        });
                                    }}
                                    style={{ background: 'none', border: 'none', color: isRejected ? 'var(--brand-primary)' : 'var(--text-disabled)', cursor: 'pointer', padding: 2, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 4 }}
                                    title={isRejected ? "Restaurar concepto" : "Excluir concepto de esta fusión"}
                                >
                                    {isRejected ? <Check size={14} /> : <X size={14} />}
                                </button>
                            </div>
                        )
                    })}
                </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
                <ArrowRight size={16} style={{ color: 'var(--text-disabled)' }} />
                <div style={{ flex: 1, display: 'flex', gap: 8 }}>
                    <input
                        type="text"
                        placeholder="Nombre destino"
                        value={targetName}
                        onChange={e => setTargetName(e.target.value)}
                        style={{ flex: 1, padding: '8px 12px', background: 'var(--bg-primary)', border: '1px dashed var(--brand-primary)', borderRadius: 'var(--radius-md)', color: 'var(--text-primary)', outline: 'none' }}
                        title="Nombre Final (Target Name)"
                    />
                    <input
                        type="text"
                        placeholder="Dominio"
                        value={targetDomain}
                        onChange={e => setTargetDomain(e.target.value)}
                        style={{ width: 120, padding: '8px 12px', background: 'var(--bg-primary)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', color: 'var(--text-primary)', outline: 'none' }}
                        title="Dominio Final (opcional)"
                    />
                </div>
            </div>

            <button
                disabled={isMerging || !targetName.trim() || activeConcepts.length < 2}
                onClick={() => {
                    const sourceNames = activeConcepts.map(c => c.name);
                    onMerge(targetName, targetDomain, sourceNames);
                }}
                style={{
                    width: '100%', padding: '10px', background: 'var(--brand-primary)', color: '#fff',
                    border: 'none', borderRadius: 'var(--radius-md)', fontWeight: 500, cursor: 'pointer',
                    opacity: (isMerging || !targetName.trim()) ? 0.7 : 1
                }}
            >
                Fusionar este Grupo
            </button>
        </div>
    );
}
